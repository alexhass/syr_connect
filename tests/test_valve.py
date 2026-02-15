"""Tests for valve platform.""" 
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, Mock

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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

    # Inject cached getAB=2 (closed) with future expiry
    valve._cached_ab = {"value": "2", "expires": time.time() + 5}
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
    assert valve._cached_ab is not None and valve._cached_ab["value"] == "1"

    # Test close
    coordinator.async_set_device_value.reset_mock()
    await valve.async_close()
    coordinator.async_set_device_value.assert_awaited_with("op", "setAB", 2)
    assert valve._cached_ab is not None and valve._cached_ab["value"] == "2"

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

    # Provide a hass with async_create_task spy
    fake_hass = MagicMock()
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
