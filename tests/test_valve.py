"""Tests for valve platform.""" 
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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
