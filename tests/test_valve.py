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


async def test_async_setup_entry_empty_string_values(hass: HomeAssistant) -> None:
    """Test that empty string values are not treated as valid."""
    data = {
        "devices": [
            {
                "id": "empty1",
                "name": "Empty1",
                "project_id": "p1",
                "status": {"getAB": ""},  # Empty string
            },
            {
                "id": "empty2",
                "name": "Empty2",
                "project_id": "p1",
                "status": {"getVLV": ""},  # Empty string
            },
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Empty strings should not create valve entities
    add_entities.assert_not_called()


async def test_async_setup_entry_typeerror_values(hass: HomeAssistant) -> None:
    """Test that TypeError during value conversion is handled."""
    data = {
        "devices": [
            {
                "id": "type1",
                "name": "Type1",
                "project_id": "p1",
                "status": {"getAB": None},  # Will cause TypeError
            },
            {
                "id": "type2",
                "name": "Type2",
                "project_id": "p1",
                "status": {"getVLV": ["list"]},  # Will cause TypeError/ValueError
            },
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # TypeError values should not create valve entities
    add_entities.assert_not_called()


async def test_async_setup_entry_getab_value_3_not_valid(hass: HomeAssistant) -> None:
    """Test that getAB value of 3 is not valid (only 1/2 are valid)."""
    data = {
        "devices": [
            {
                "id": "ab3",
                "name": "AB3",
                "project_id": "p1",
                "status": {"getAB": "3"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # getAB=3 should not create valve
    add_entities.assert_not_called()


async def test_async_setup_entry_getvlv_value_5_not_valid(hass: HomeAssistant) -> None:
    """Test that getVLV value of 5 is not valid (only 10/11/20/21 are valid)."""
    data = {
        "devices": [
            {
                "id": "vlv5",
                "name": "VLV5",
                "project_id": "p1",
                "status": {"getVLV": "5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # getVLV=5 should not create valve
    add_entities.assert_not_called()


async def test_is_closed_with_getvlv_11_closing(hass: HomeAssistant) -> None:
    """Test is_closed returns False for getVLV=11 (closing)."""
    data = {"devices": [{"id": "v11", "name": "V11", "status": {"getVLV": "11"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "v11", "V11")

    # getVLV=11 is closing, not closed, so is_closed should be False
    assert valve.is_closed is False
    assert valve.is_closing is True


async def test_is_closed_with_getvlv_20_open(hass: HomeAssistant) -> None:
    """Test is_closed returns False for getVLV=20 (open)."""
    data = {"devices": [{"id": "v20", "name": "V20", "status": {"getVLV": "20"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "v20", "V20")

    # getVLV=20 is open, so is_closed should be False
    assert valve.is_closed is False
    assert valve.is_opening is False


async def test_is_closed_with_getvlv_21_opening(hass: HomeAssistant) -> None:
    """Test is_closed returns False for getVLV=21 (opening)."""
    data = {"devices": [{"id": "v21", "name": "V21", "status": {"getVLV": "21"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "v21", "V21")

    # getVLV=21 is opening, not closed, so is_closed should be False
    assert valve.is_closed is False
    assert valve.is_opening is True


async def test_cached_ab_false_value(hass: HomeAssistant) -> None:
    """Test cached_ab with False value (open) overrides getVLV."""
    data = {"devices": [{"id": "cf", "name": "CF", "status": {"getVLV": "10"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "cf", "CF")

    # Initially getVLV=10 -> closed
    assert valve.is_closed is True

    # Set cached_ab to False (open) with future expiry
    valve._cached_ab = {"value": False, "expires": time.time() + 10}

    # Should use cached value False (open)
    assert valve.is_closed is False


async def test_is_closed_getvlv_valueerror(hass: HomeAssistant) -> None:
    """Test is_closed handles ValueError in getVLV parsing."""
    data = {"devices": [{"id": "ve", "name": "VE", "status": {"getVLV": "not_a_number", "getAB": "2"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "ve", "VE")

    # Invalid getVLV should fall back to getAB
    # getAB=2 means closed
    assert valve.is_closed is True


async def test_is_opening_valueerror(hass: HomeAssistant) -> None:
    """Test is_opening handles ValueError in getVLV parsing."""
    data = {"devices": [{"id": "ove", "name": "OVE", "status": {"getVLV": "invalid"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "ove", "OVE")

    # Invalid getVLV should return None
    assert valve.is_opening is None


async def test_is_closing_valueerror(hass: HomeAssistant) -> None:
    """Test is_closing handles ValueError in getVLV parsing."""
    data = {"devices": [{"id": "cve", "name": "CVE", "status": {"getVLV": "bad_value"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "cve", "CVE")

    # Invalid getVLV should return None
    assert valve.is_closing is None


async def test_async_close_handles_write_state_exception(hass: HomeAssistant) -> None:
    """Test async_close handles async_write_ha_state exception."""
    data = {"devices": [{"id": "w2", "name": "W2", "status": {}}]}
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    valve = SyrConnectValve(coordinator, "w2", "W2")

    # Make async_write_ha_state raise; async_close should swallow it
    def _fail():
        raise Exception("ui fail")

    valve.async_write_ha_state = _fail

    await valve.async_close()
    # Command sent and cache set despite UI failure
    coordinator.async_set_device_value.assert_awaited_with("w2", "setAB", 2)
    assert valve._cached_ab is not None and valve._cached_ab["value"] is True


async def test_async_close_clears_cache_on_failure(hass: HomeAssistant) -> None:
    """Test async_close clears optimistic cache on command failure."""
    data = {"devices": [{"id": "cf1", "name": "CF1", "status": {}}]}
    coordinator = _build_coordinator(hass, data)

    # Make async_set_device_value fail
    async def _fail(*args, **kwargs):
        raise Exception("command failed")

    coordinator.async_set_device_value = AsyncMock(side_effect=_fail)
    valve = SyrConnectValve(coordinator, "cf1", "CF1")
    valve.async_write_ha_state = Mock()

    # Set initial cache
    valve._cached_ab = {"value": True, "expires": time.time() + 10}

    try:
        await valve.async_close()
        raise AssertionError("Expected HomeAssistantError")
    except HomeAssistantError:
        # Cache should be cleared on failure
        assert valve._cached_ab is None


async def test_async_open_clears_cache_on_failure(hass: HomeAssistant) -> None:
    """Test async_open clears optimistic cache on command failure."""
    data = {"devices": [{"id": "of1", "name": "OF1", "status": {}}]}
    coordinator = _build_coordinator(hass, data)

    # Make async_set_device_value fail
    async def _fail(*args, **kwargs):
        raise Exception("command failed")

    coordinator.async_set_device_value = AsyncMock(side_effect=_fail)
    valve = SyrConnectValve(coordinator, "of1", "OF1")
    valve.async_write_ha_state = Mock()

    # Set initial cache
    valve._cached_ab = {"value": False, "expires": time.time() + 10}

    try:
        await valve.async_open()
        raise AssertionError("Expected HomeAssistantError")
    except HomeAssistantError:
        # Cache should be cleared on failure
        assert valve._cached_ab is None


async def test_async_open_second_write_state_exception_on_failure(hass: HomeAssistant) -> None:
    """Test async_open handles exception in second async_write_ha_state (on failure path)."""
    data = {"devices": [{"id": "ws1", "name": "WS1", "status": {}}]}
    coordinator = _build_coordinator(hass, data)

    # Make async_set_device_value fail
    async def _fail(*args, **kwargs):
        raise Exception("command failed")

    coordinator.async_set_device_value = AsyncMock(side_effect=_fail)
    valve = SyrConnectValve(coordinator, "ws1", "WS1")

    # Make async_write_ha_state always raise
    def _write_fail():
        raise Exception("write state failed")

    valve.async_write_ha_state = _write_fail

    try:
        await valve.async_open()
        raise AssertionError("Expected HomeAssistantError")
    except HomeAssistantError:
        # Should still raise HomeAssistantError despite write_state failure
        assert valve._cached_ab is None


async def test_async_close_second_write_state_exception_on_failure(hass: HomeAssistant) -> None:
    """Test async_close handles exception in second async_write_ha_state (on failure path)."""
    data = {"devices": [{"id": "ws2", "name": "WS2", "status": {}}]}
    coordinator = _build_coordinator(hass, data)

    # Make async_set_device_value fail
    async def _fail(*args, **kwargs):
        raise Exception("command failed")

    coordinator.async_set_device_value = AsyncMock(side_effect=_fail)
    valve = SyrConnectValve(coordinator, "ws2", "WS2")

    # Make async_write_ha_state always raise
    def _write_fail():
        raise Exception("write state failed")

    valve.async_write_ha_state = _write_fail

    try:
        await valve.async_close()
        raise AssertionError("Expected HomeAssistantError")
    except HomeAssistantError:
        # Should still raise HomeAssistantError despite write_state failure
        assert valve._cached_ab is None


async def test_is_closed_getvlv_empty_string(hass: HomeAssistant) -> None:
    """Test is_closed handles empty string getVLV."""
    data = {"devices": [{"id": "es", "name": "ES", "status": {"getVLV": "", "getAB": "1"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "es", "ES")

    # Empty getVLV should fall back to getAB
    # getAB=1 means open
    assert valve.is_closed is False


async def test_is_opening_empty_string(hass: HomeAssistant) -> None:
    """Test is_opening returns None for empty string getVLV."""
    data = {"devices": [{"id": "oes", "name": "OES", "status": {"getVLV": ""}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "oes", "OES")

    # Empty getVLV should return None
    assert valve.is_opening is None


async def test_is_closing_empty_string(hass: HomeAssistant) -> None:
    """Test is_closing returns None for empty string getVLV."""
    data = {"devices": [{"id": "ces", "name": "CES", "status": {"getVLV": ""}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "ces", "CES")

    # Empty getVLV should return None
    assert valve.is_closing is None


async def test_is_closed_getvlv_typeerror(hass: HomeAssistant) -> None:
    """Test is_closed handles TypeError in getVLV parsing."""
    data = {"devices": [{"id": "te", "name": "TE", "status": {"getVLV": None, "getAB": "2"}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "te", "TE")

    # None getVLV triggers empty string check, falls back to getAB
    # getAB=2 means closed
    assert valve.is_closed is True


async def test_is_opening_typeerror(hass: HomeAssistant) -> None:
    """Test is_opening handles TypeError in getVLV parsing."""
    data = {"devices": [{"id": "ote", "name": "OTE", "status": {"getVLV": None}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "ote", "OTE")

    # None getVLV should return None
    assert valve.is_opening is None


async def test_is_closing_typeerror(hass: HomeAssistant) -> None:
    """Test is_closing handles TypeError in getVLV parsing."""
    data = {"devices": [{"id": "cte", "name": "CTE", "status": {"getVLV": None}}]}
    coordinator = _build_coordinator(hass, data)
    valve = SyrConnectValve(coordinator, "cte", "CTE")

    # None getVLV should return None
    assert valve.is_closing is None


async def test_async_setup_entry_getvlv_all_valid_codes(hass: HomeAssistant) -> None:
    """Test async_setup_entry creates valves for all valid getVLV codes."""
    data = {
        "devices": [
            {"id": "v10", "name": "V10", "status": {"getVLV": "10"}},  # closed
            {"id": "v11", "name": "V11", "status": {"getVLV": "11"}},  # closing
            {"id": "v20", "name": "V20", "status": {"getVLV": "20"}},  # open
            {"id": "v21", "name": "V21", "status": {"getVLV": "21"}},  # opening
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Should create 4 valves
    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 4


async def test_async_setup_entry_getab_valid_values_1_and_2(hass: HomeAssistant) -> None:
    """Test async_setup_entry creates valves for getAB values 1 and 2."""
    data = {
        "devices": [
            {"id": "ab1", "name": "AB1", "status": {"getAB": "1"}},
            {"id": "ab2", "name": "AB2", "status": {"getAB": "2"}},
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Should create 2 valves
    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 2


async def test_valve_initialization_with_sensor_key(hass: HomeAssistant) -> None:
    """Test valve initialization with explicit sensor_key parameter."""
    data = {"devices": [{"id": "sk1", "name": "SK1", "status": {}}]}
    coordinator = _build_coordinator(hass, data)

    # Create valve with explicit sensor_key
    valve = SyrConnectValve(coordinator, "sk1", "SK1", sensor_key="getVLV")

    assert valve._sensor_key == "getVLV"
    assert valve._attr_unique_id == "sk1_getVLV"
    assert valve._attr_translation_key == "getvlv"


async def test_valve_initialization_default_sensor_key(hass: HomeAssistant) -> None:
    """Test valve initialization defaults to 'getAB' sensor_key."""
    data = {"devices": [{"id": "dsk", "name": "DSK", "status": {}}]}
    coordinator = _build_coordinator(hass, data)

    # Create valve without sensor_key (should default to getAB)
    valve = SyrConnectValve(coordinator, "dsk", "DSK")

    assert valve._sensor_key == "getAB"
    assert valve._attr_unique_id == "dsk_getAB"
