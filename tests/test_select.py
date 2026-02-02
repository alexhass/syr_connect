"""Tests for select platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant

from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.select import (
    SyrConnectNumericSelect,
    SyrConnectRegenerationSelect,
)
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


async def test_regeneration_select_current_option(hass: HomeAssistant) -> None:
    """Test regeneration select current option."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRTH": "2",
                    "getRTM": "30",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    assert select.current_option == "02:30"


async def test_regeneration_select_option_selection(hass: HomeAssistant) -> None:
    """Test regeneration select option selection."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRTH": "2",
                    "getRTM": "30",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    await select.async_select_option("03:45")

    assert coordinator.async_set_device_value.call_count == 2
    coordinator.async_set_device_value.assert_any_call("device1", "setRTH", 3)
    coordinator.async_set_device_value.assert_any_call("device1", "setRTM", 45)


async def test_numeric_select_current_option(hass: HomeAssistant) -> None:
    """Test numeric select current option."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSV1": "5",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)

    assert select.current_option == "5 kg"


async def test_numeric_select_option_selection(hass: HomeAssistant) -> None:
    """Test numeric select option selection."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSV1": "5",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)

    await select.async_select_option("10 kg")

    coordinator.async_set_device_value.assert_called_once_with("device1", "setSV1", 10)


async def test_select_available(hass: HomeAssistant) -> None:
    """Test select availability."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": True,
                "status": {
                    "getRTH": "2",
                    "getRTM": "30",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    assert select.available is True
