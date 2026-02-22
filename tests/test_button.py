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


async def test_async_setup_entry(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry creates button entities."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {"getSIR": 1},
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should create regeneration button
    assert len(entities) >= 1


async def test_async_setup_entry_multiple_devices(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry with multiple devices."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getSIR": 1},
            },
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {"getSIR": 1},
            },
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()
    
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


async def test_async_setup_entry_no_data(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry with no coordinator data."""
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(None)
    entities, async_add_entities = mock_add_entities()
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should not add any entities when no data
    async_add_entities.assert_not_called()


async def test_button_initialization_attributes(hass: HomeAssistant) -> None:
    """Test button initialization sets correct attributes."""
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
    
    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR", "Regenerate Now")

    # Check attributes
    assert button._attr_unique_id == "device1_setSIR"
    assert button._attr_has_entity_name is True
    assert button._attr_translation_key == "setsir"
    assert button._device_id == "device1"
    assert button._command == "setSIR"


async def test_async_setup_entry_skip_setsir_when_getsir_missing(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry skips setSIR button when getSIR is not available."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getBAR": "4077 mbar",
                    "getBAT": "6,12 4,38 3,90",
                    # getSIR is missing - setSIR button should not be created
                },
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should not create any buttons since getSIR is not available
    assert len(entities) == 0


async def test_async_setup_entry_create_setsir_when_getsir_present(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry creates setSIR button when getSIR is available."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getSIR": "1",  # getSIR is present - setSIR button should be created
                },
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should create setSIR button
    assert len(entities) == 1
    assert entities[0]._command == "setSIR"


async def test_async_setup_entry_no_getsir(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry with device that does not support setSIR (no getSIR in status)."""
    data = {
        "devices": [
            {
                "id": "safe_t_plus",
                "name": "Safe-T+",
                "project_id": "project1",
                "status": {},  # Kein getSIR vorhanden
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    # Es sollte kein Button erstellt werden
    assert len(entities) == 0


async def test_button_reset_no_reset_required(hass: HomeAssistant) -> None:
    """Reset button raises when no reset required (missing/empty get key)."""
    data = {
        "devices": [
            {
                "id": "device_reset",
                "name": "Device Reset",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    button = SyrConnectButton(coordinator, "device_reset", "Device Reset", "project1", "setALA", "Reset alarm")

    with pytest.raises(HomeAssistantError, match=r"No reset required for getALA on device_reset"):
        await button.async_press()


async def test_button_reset_send_empty_for_lex10_and_safet(hass: HomeAssistant) -> None:
    """When model is lex10/safetplus, reset sends empty string."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getALA": "A5", "getCNA": "LEXplus10S"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setALA", "Reset alarm")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device1", "setALA", "")


async def test_button_reset_send_FF_for_other_models(hass: HomeAssistant) -> None:
    """When model unknown/other, reset sends 'FF'."""
    data = {
        "devices": [
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {"getALA": "A5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    button = SyrConnectButton(coordinator, "device2", "Device 2", "project1", "setALA", "Reset alarm")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device2", "setALA", "FF")


async def test_button_reset_detect_model_exception(hass: HomeAssistant, monkeypatch) -> None:
    """If detect_model raises, the code falls back and sends 'FF'."""
    from custom_components.syr_connect import button as button_mod

    data = {
        "devices": [
            {
                "id": "device3",
                "name": "Device 3",
                "project_id": "project1",
                "status": {"getALA": "A5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    # Make detect_model raise
    monkeypatch.setattr(button_mod, "detect_model", lambda *_: (_ for _ in ()).throw(Exception("boom")))

    button = SyrConnectButton(coordinator, "device3", "Device 3", "project1", "setALA", "Reset alarm")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device3", "setALA", "FF")
