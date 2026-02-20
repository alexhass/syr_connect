"""Tests for valve platform.""" 
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, Mock

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.valve import ValveEntityFeature
import pytest

from custom_components.syr_connect.valve import SyrConnectValve, async_setup_entry
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry


def _build_coordinator(hass: HomeAssistant, data: dict) -> SyrConnectDataUpdateCoordinator:
    coordinator = SyrConnectDataUpdateCoordinator(
        hass,
        MagicMock(),
        "test@example.com",
        "password",
        60,
    )
    coordinator.async_set_updated_data(data)
    coordinator.last_update_success = True
    return coordinator


async def test_open_close_calls_set(hass: HomeAssistant) -> None:
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getAB": "2"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    valve = SyrConnectValve(coordinator, "device1", "Device 1")

    await valve.async_open()
    coordinator.async_set_device_value.assert_called_with("device1", "setAB", 1)

    await valve.async_close()
    coordinator.async_set_device_value.assert_called_with("device1", "setAB", 2)


async def test_open_close_error_raises(hass: HomeAssistant) -> None:
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getAB": "1"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock(side_effect=ValueError("Test"))

    valve = SyrConnectValve(coordinator, "device1", "Device 1")

    try:
        await valve.async_close()
    except HomeAssistantError:
        pass
    else:
        raise AssertionError("Expected HomeAssistantError on failure")


async def test_async_setup_entry_creates_valve(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {"getAB": "1"},
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert len(entities) >= 1


async def test_valve_from_vlv_only(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Valve should be created when only getVLV present and state properties derive from it."""
    data = {
        "devices": [
            {
                "id": "device2",
                "name": "Test Device 2",
                "project_id": "project1",
                "status": {"getVLV": "21"},
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert len(entities) >= 1
    # Inspect created valve entity's runtime properties
    valve = entities[0]
    # coordinator was set on created entity in async_setup_entry; ensure properties
    assert getattr(valve, "is_opening") is True
    assert getattr(valve, "is_closing") is False
    assert getattr(valve, "is_closed") is False


async def test_available(hass: HomeAssistant) -> None:
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": True,
                "status": {"getAB": "1"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "device1", "Device 1")

    assert valve.available is True


def _build_coordinator(hass: HomeAssistant, data: dict) -> SyrConnectDataUpdateCoordinator:
    coordinator = SyrConnectDataUpdateCoordinator(
        hass,
        MagicMock(),
        "test@example.com",
        "password",
        60,
    )
    coordinator.async_set_updated_data(data)
    coordinator.last_update_success = True
    return coordinator


def _build_entry(coordinator: SyrConnectDataUpdateCoordinator) -> MockConfigEntry:
    entry = MockConfigEntry(domain="syr_connect", data={})
    entry.runtime_data = coordinator
    return entry


async def test_async_setup_entry_creates_valves(hass: HomeAssistant) -> None:
    data = {
        "devices": [
            {
                "id": "d1",
                "name": "Device 1",
                "project_id": "p1",
                "status": {"getAB": "1"},
            },
            {
                "id": "d2",
                "name": "Device 2",
                "project_id": "p1",
                "status": {"getVLV": "10"},
            },
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    # Two devices should produce two valve entities
    assert len(entities) == 2


async def test_entity_properties_and_state_transitions(hass: HomeAssistant) -> None:
    data = {
        "devices": [
            {
                "id": "dev",
                "name": "Dev",
                "project_id": "p1",
                "status": {"getVLV": "10", "getAB": "2"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "dev", "Dev")

    # Raw attributes are exposed as strings
    attrs = valve.extra_state_attributes
    assert attrs["getVLV"] == "10"
    assert attrs["getAB"] == "2"

    # getVLV=10 -> closed
    assert valve.is_closed is True
    assert valve.is_opening is False
    assert valve.is_closing is False
    assert valve.icon == "mdi:valve-closed"

    # Update status to opening (21)
    coordinator.async_set_updated_data(
        {"devices": [{"id": "dev", "name": "Dev", "status": {"getVLV": "21"}}]}
    )
    # Opening maps to moving icon
    assert valve.is_opening is True
    assert valve.icon == "mdi:valve"


async def test_cached_ab_overrides_vlv_and_expires(hass: HomeAssistant) -> None:
    data = {
        "devices": [
            {"id": "dev2", "name": "Dev2", "status": {"getVLV": "20"}}
        ]
    }
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "dev2", "Dev2")

    # By default getVLV=20 -> open
    assert valve.is_closed is False

    # Inject cached getAB=2 (closed) with future expiry (store boolean True)
    valve._cached_ab = {"value": True, "expires": time.time() + 5}
    assert valve.is_closed is True

    # Expire the cache and confirm we return to authoritative VLV
    valve._cached_ab["expires"] = time.time() - 1
    assert valve.is_closed is False


async def test_fallback_to_getab_and_invalid_values(hass: HomeAssistant) -> None:
    data = {"devices": [{"id": "x", "name": "X", "status": {"getAB": "2"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "x", "X")

    # No getVLV, fallback to getAB
    assert valve.is_closed is True

    # Invalid getAB -> unknown
    coordinator.async_set_updated_data({"devices": [{"id": "x", "name": "X", "status": {"getAB": "abc"}}]})
    assert valve.is_closed is None


async def test_available_checks(hass: HomeAssistant) -> None:
    data = {"devices": [{"id": "a", "name": "A", "status": {}, "available": True}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "a", "A")
    assert valve.available is True

    coordinator.last_update_success = False
    assert valve.available is False

    # If device present but marked unavailable
    coordinator.last_update_success = True
    coordinator.async_set_updated_data({"devices": [{"id": "a", "name": "A", "status": {}, "available": False}]})
    assert valve.available is False


async def test_async_open_close_success_and_failure(hass: HomeAssistant) -> None:
    data = {"devices": [{"id": "op", "name": "Op", "status": {}}]}
    coordinator = _build_coordinator(hass, data)
    # Replace async_set_device_value with a mock
    coordinator.async_set_device_value = AsyncMock()
    valve = SyrConnectValve(coordinator, "op", "Op")

    # Patch async_write_ha_state to avoid hass dependency
    valve.async_write_ha_state = Mock()

    await valve.async_open()
    coordinator.async_set_device_value.assert_awaited_with("op", "setAB", 1)
    assert valve._cached_ab is not None and valve._cached_ab["value"] is False

    # Test close
    coordinator.async_set_device_value.reset_mock()
    await valve.async_close()
    coordinator.async_set_device_value.assert_awaited_with("op", "setAB", 2)
    assert valve._cached_ab is not None and valve._cached_ab["value"] is True

    # Simulate failure
    async def _fail(*args, **kwargs):
        raise Exception("boom")

    coordinator.async_set_device_value = AsyncMock(side_effect=_fail)
    valve._cached_ab = None
    try:
        await valve.async_open()
        raise AssertionError("Expected HomeAssistantError")
    except HomeAssistantError:
        # expected
        pass


async def test_sync_service_wrappers_schedule_tasks(hass: HomeAssistant) -> None:
    data = {"devices": [{"id": "s1", "name": "S1", "status": {}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "s1", "S1")

    # Provide a hass with async_create_task spy that consumes the coro
    fake_hass = MagicMock()
    fake_hass.async_create_task = Mock(side_effect=lambda coro: coro.close())
    valve.hass = fake_hass
    valve.open_valve()
    fake_hass.async_create_task.assert_called()
    valve.close_valve()
    assert fake_hass.async_create_task.call_count >= 2


async def test_icon_fallback_when_no_status(hass: HomeAssistant) -> None:
    data = {"devices": []}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "missing", "Missing")
    # No status -> closed is None -> icon should be base icon
    assert valve.icon == valve._base_icon


async def test_is_closing_state_and_icon(hass: HomeAssistant) -> None:
    data = {"devices": [{"id": "c1", "name": "C1", "status": {"getVLV": "11"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "c1", "C1")

    # getVLV=11 -> closing True, is_closed False
    assert valve.is_closing is True
    assert valve.is_opening is False
    assert valve.is_closed is False
    # moving icon for closing
    assert valve.icon == "mdi:valve"


async def test_extra_state_attributes_none_when_no_status(hass: HomeAssistant) -> None:
    data = {"devices": []}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "no_status", "NoStatus")
    assert valve.extra_state_attributes is None


async def test_is_closed_none_when_device_missing(hass: HomeAssistant) -> None:
    # Coordinator has devices but not our device id
    data = {"devices": [{"id": "other", "name": "Other", "status": {"getVLV": "20"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "missing_device", "Missing")
    assert valve._get_device() is None
    assert valve._get_status() is None
    assert valve.is_closed is None


async def test_async_open_handles_write_state_exception(hass: HomeAssistant) -> None:
    data = {"devices": [{"id": "w1", "name": "W1", "status": {}}]}
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    valve = SyrConnectValve(coordinator, "w1", "W1")

    # Make async_write_ha_state raise; async_open should swallow it
    def _fail():
        raise Exception("ui fail")

    valve.async_write_ha_state = _fail

    await valve.async_open()
    # Command sent and cache set despite UI failure
    coordinator.async_set_device_value.assert_awaited_with("w1", "setAB", 1)
    assert valve._cached_ab is not None and valve._cached_ab["value"] is False


async def test_async_setup_entry_with_no_coordinator_data(hass: HomeAssistant) -> None:
    # If entry.runtime_data.data is falsy, async_setup_entry should not call add_entities
    coordinator = _build_coordinator(hass, {"devices": []})
    # Simulate missing data
    coordinator.data = None
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # add_entities should not be called when coordinator.data is falsy
    assert not add_entities.called


async def test_invalid_getvlv_does_not_raise_and_falls_back(hass: HomeAssistant) -> None:
    data = {"devices": [{"id": "v1", "name": "V1", "status": {"getVLV": "abc", "getAB": "1"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "v1", "V1")

    # Invalid getVLV string should not raise and we fall back to getAB
    assert valve.is_opening is None
    assert valve.is_closing is None
    # getAB '1' should be present and maps to open -> is_closed False
    attrs = valve.extra_state_attributes
    assert attrs is not None and attrs.get("getAB") == "1"
    assert valve.is_closed == False


async def test_supported_features_and_device_class_and_reports_position() -> None:
    # Directly instantiate without hass for attribute checks
    coordinator = MagicMock()
    coordinator.data = {"devices": []}
    valve = SyrConnectValve(coordinator, "id", "Name")

    assert valve._attr_device_class is not None
    assert valve._attr_reports_position is False
    # Expect supported features include OPEN and CLOSE bits
    try:
        from homeassistant.components.valve import ValveEntityFeature as _VEF
    except Exception:
        pytest.skip("ValveEntityFeature not available in this test environment")

    assert int(valve._attr_supported_features) & int(_VEF.OPEN) == int(_VEF.OPEN)
    assert int(valve._attr_supported_features) & int(_VEF.CLOSE) == int(_VEF.CLOSE)


async def test_async_service_entrypoints_call_underlying(hass: HomeAssistant) -> None:
    data = {"devices": [{"id": "as1", "name": "AS1", "status": {}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "as1", "AS1")

    # Patch async_open/async_close to verify they are awaited
    valve.async_open = AsyncMock()
    valve.async_close = AsyncMock()

    await valve.async_open_valve()
    valve.async_open.assert_awaited()

    await valve.async_close_valve()
    valve.async_close.assert_awaited()


async def test_sync_wrappers_without_hass_do_nothing(hass: HomeAssistant) -> None:
    coordinator = _build_coordinator(hass, {"devices": []})
    valve = SyrConnectValve(coordinator, "no_hass", "NoHass")
    # Ensure hass is None
    valve.hass = None
    # Should not raise
    valve.open_valve()
    valve.close_valve()


async def test_icon_open_state(hass: HomeAssistant) -> None:
    data = {"devices": [{"id": "o1", "name": "O1", "status": {"getVLV": "20"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "o1", "O1")
    # getVLV=20 -> open -> icon should be open
    assert valve.is_closed is False
    assert valve.icon == "mdi:valve-open"


async def test_async_setup_entry_skips_invalid_values(hass: HomeAssistant) -> None:
    """If getAB and getVLV don't contain known numeric codes, no valve should be created."""
    data = {
        "devices": [
            {
                "id": "bad",
                "name": "Bad",
                "project_id": "p",
                "status": {"getAB": "3", "getVLV": "5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Should not create any valve entities
    add_entities.assert_not_called()


async def test_async_open_close_with_boolean_string_status(hass: HomeAssistant) -> None:
    """When device uses boolean-string getAB, setAB should use 'true'/'false'."""
    data = {"devices": [{"id": "b1", "name": "B1", "status": {"getAB": "true"}}]}
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    valve = SyrConnectValve(coordinator, "b1", "B1")

    # Patch async_write_ha_state to avoid hass dependency
    valve.async_write_ha_state = Mock()

    await valve.async_open()
    # Opening should send 'false' to open
    coordinator.async_set_device_value.assert_awaited_with("b1", "setAB", "false")

    coordinator.async_set_device_value.reset_mock()
    await valve.async_close()
    # Closing should send 'true' to close
    coordinator.async_set_device_value.assert_awaited_with("b1", "setAB", "true")
