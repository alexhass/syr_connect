"""Tests for select platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

from homeassistant.core import HomeAssistant

from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.select import (
    SyrConnectNumericSelect,
    SyrConnectRegenerationSelect,
    async_setup_entry,
    _build_time_options,
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


def test_build_time_options_default():
    """Test building time options with default 15-minute step."""
    options = _build_time_options(15)
    assert "00:00" in options
    assert "00:15" in options
    assert "00:30" in options
    assert "23:45" in options
    assert len(options) == 96  # 24 hours * 4 (every 15 min)


def test_build_time_options_30min():
    """Test building time options with 30-minute step."""
    options = _build_time_options(30)
    assert "00:00" in options
    assert "00:30" in options
    assert "23:30" in options
    assert len(options) == 48  # 24 hours * 2


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry creates select entities."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getRTH": "2",
                    "getRTM": "30",
                    "getSV1": "5",
                    "getRPD": "2",
                    "getCNA": "LEXPLUS10S",
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should create regeneration time select + salt select + RPD select
    assert len(entities) >= 3


async def test_async_setup_entry_no_entities(hass: HomeAssistant) -> None:
    """Test async_setup_entry with no valid select entities."""
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
    
    # Should only create regeneration select (always created if getRTH/getRTM exist)
    assert len(entities) == 0  # No status values, so no selects


async def test_regeneration_select_missing_data(hass: HomeAssistant) -> None:
    """Test regeneration select when RTH/RTM missing."""
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
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    assert select.current_option is None


async def test_regeneration_select_invalid_format(hass: HomeAssistant) -> None:
    """Test regeneration select with invalid time values."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRTH": "invalid",
                    "getRTM": "30",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    assert select.current_option is None


async def test_regeneration_select_invalid_option_format(hass: HomeAssistant) -> None:
    """Test regeneration select with invalid option format."""
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

    await select.async_select_option("invalid")

    # Should not call async_set_device_value due to invalid format
    coordinator.async_set_device_value.assert_not_called()


async def test_regeneration_select_unavailable_coordinator(hass: HomeAssistant) -> None:
    """Test regeneration select unavailable when coordinator fails."""
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
    coordinator.last_update_success = False
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    assert select.available is False


async def test_regeneration_select_device_unavailable(hass: HomeAssistant) -> None:
    """Test regeneration select unavailable when device unavailable."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": False,
                "status": {
                    "getRTH": "2",
                    "getRTM": "30",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    assert select.available is False


async def test_numeric_select_missing_data(hass: HomeAssistant) -> None:
    """Test numeric select when data missing."""
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
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)

    assert select.current_option is None


async def test_numeric_select_invalid_value(hass: HomeAssistant) -> None:
    """Test numeric select with invalid value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSV1": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)

    assert select.current_option is None


async def test_numeric_select_invalid_option(hass: HomeAssistant) -> None:
    """Test numeric select with invalid option."""
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

    await select.async_select_option("invalid")

    # Should not call async_set_device_value due to invalid option
    coordinator.async_set_device_value.assert_not_called()


async def test_numeric_select_without_unit(hass: HomeAssistant) -> None:
    """Test numeric select without unit label."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPD": "2",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    # getRPD typically has "days" unit, but test without
    with patch("custom_components.syr_connect.select._SYR_CONNECT_SENSOR_UNITS", {}):
        select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getRPD", 1, 4, 1)
        
        # Options should be plain numbers
        assert "1" in select.options
        assert "2" in select.options


async def test_numeric_select_unavailable_coordinator(hass: HomeAssistant) -> None:
    """Test numeric select unavailable when coordinator fails."""
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
    coordinator.last_update_success = False
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)

    assert select.available is False


async def test_numeric_select_device_unavailable(hass: HomeAssistant) -> None:
    """Test numeric select unavailable when device unavailable."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": False,
                "status": {
                    "getSV1": "5",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)

    assert select.available is False


async def test_async_setup_entry_skip_zero_values(hass: HomeAssistant) -> None:
    """Test async_setup_entry skips zero salt values."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getSV1": "0",  # Zero value should be skipped
                    "getSV2": "5",  # Non-zero should be created
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should only create select for getSV2 (getSV1 is zero)
    sv1_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV1']
    sv2_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV2']
    
    assert len(sv1_entities) == 0  # Skipped because value is 0
    assert len(sv2_entities) == 1  # Created
