"""Tests for button platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.syr_connect.button import SyrConnectButton, async_setup_entry
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


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry creates button entities."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should create regeneration button
    assert len(entities) >= 1


async def test_async_setup_entry_multiple_devices(hass: HomeAssistant) -> None:
    """Test async_setup_entry with multiple devices."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},
            },
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {},
            },
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should create buttons for both devices
    assert len(entities) >= 2


async def test_button_press_other_command(hass: HomeAssistant) -> None:
    """Test button press with non-setSIR command uses value 1."""
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
    
    # Use a different command that should use value=1
    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setOTHER", "Other Action")

    await button.async_press()

    # Should use value=1 for non-setSIR commands
    coordinator.async_set_device_value.assert_called_once_with("device1", "setOTHER", 1)


async def test_button_press_unexpected_error(hass: HomeAssistant) -> None:
    """Test button press handles unexpected errors."""
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
    coordinator.async_set_device_value = AsyncMock(side_effect=Exception("Unexpected error"))
    
    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR", "Regenerate Now")

    with pytest.raises(HomeAssistantError, match="Unexpected error pressing button"):
        await button.async_press()


async def test_button_unavailable_coordinator(hass: HomeAssistant) -> None:
    """Test button unavailable when coordinator update fails."""
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
    coordinator.last_update_success = False
    
    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR", "Regenerate Now")

    assert button.available is False


async def test_button_unavailable_device(hass: HomeAssistant) -> None:
    """Test button unavailable when device is marked unavailable."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": False,
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    
    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR", "Regenerate Now")

    assert button.available is False


async def test_button_missing_device(hass: HomeAssistant) -> None:
    """Test button when device not in coordinator data."""
    data = {
        "devices": [
            {
                "id": "other_device",
                "name": "Other Device",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    
    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR", "Regenerate Now")

    # Should return True when device not found (default availability)
    assert button.available is True
