"""Tests for button platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.syr_connect.button import SyrConnectButton
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


async def test_button_press_success(hass: HomeAssistant) -> None:
    """Test button press succeeds."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    
    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR", "Regenerate Now")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device1", "setSIR", 0)


async def test_button_press_failure(hass: HomeAssistant) -> None:
    """Test button press handles failure."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock(side_effect=ValueError("Test error"))
    
    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR", "Regenerate Now")

    with pytest.raises(HomeAssistantError):
        await button.async_press()


async def test_button_available(hass: HomeAssistant) -> None:
    """Test button availability."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": True,
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    
    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR", "Regenerate Now")

    assert button.available is True
