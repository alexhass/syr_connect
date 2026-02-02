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


async def test_async_setup_entry_no_data(hass: HomeAssistant) -> None:
    """Test async_setup_entry with no coordinator data."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should return early with no entities
    assert len(entities) == 0


async def test_regeneration_select_empty_rth_rtm(hass: HomeAssistant) -> None:
    """Test regeneration select with empty string RTH/RTM."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRTH": "",
                    "getRTM": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    assert select.current_option is None


async def test_regeneration_select_rollover_time(hass: HomeAssistant) -> None:
    """Test regeneration select with time values needing rollover."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRTH": "25",  # Should roll over to 1 (25 % 24)
                    "getRTM": "65",  # Should roll over to 5 (65 % 60)
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    assert select.current_option == "01:05"


async def test_regeneration_select_device_not_found(hass: HomeAssistant) -> None:
    """Test regeneration select when device not found in data."""
    data = {
        "devices": [
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {
                    "getRTH": "2",
                    "getRTM": "30",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")  # device1 doesn't exist

    assert select.current_option is None


async def test_regeneration_select_available_device_not_found(hass: HomeAssistant) -> None:
    """Test regeneration select availability when device not found."""
    data = {
        "devices": [
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")  # device1 doesn't exist

    # Should default to True when device not found
    assert select.available is True


async def test_numeric_select_current_option_no_matching_option(hass: HomeAssistant) -> None:
    """Test numeric select current option when value doesn't match options."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSV1": "100",  # Out of range (max 25)
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)

    # Should fall back to returning the numeric string
    assert select.current_option == "100"


async def test_numeric_select_empty_value(hass: HomeAssistant) -> None:
    """Test numeric select with empty string value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSV1": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)

    assert select.current_option is None


async def test_numeric_select_device_not_found(hass: HomeAssistant) -> None:
    """Test numeric select when device not found in data."""
    data = {
        "devices": [
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {
                    "getSV1": "5",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)  # device1 doesn't exist

    assert select.current_option is None


async def test_numeric_select_available_device_not_found(hass: HomeAssistant) -> None:
    """Test numeric select availability when device not found."""
    data = {
        "devices": [
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)  # device1 doesn't exist

    # Should default to True when device not found
    assert select.available is True


async def test_async_setup_entry_skip_empty_sv_values(hass: HomeAssistant) -> None:
    """Test async_setup_entry skips empty salt values."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getSV1": "",  # Empty value should be skipped
                    "getSV2": "5",
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should only create select for getSV2
    sv1_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV1']
    sv2_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV2']
    
    assert len(sv1_entities) == 0
    assert len(sv2_entities) == 1


async def test_async_setup_entry_skip_none_sv_values(hass: HomeAssistant) -> None:
    """Test async_setup_entry skips None salt values."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getSV1": None,  # None value should be skipped
                    "getSV2": "5",
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should only create select for getSV2
    sv1_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV1']
    
    assert len(sv1_entities) == 0


async def test_async_setup_entry_skip_invalid_float_sv_values(hass: HomeAssistant) -> None:
    """Test async_setup_entry skips invalid float salt values."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getSV1": "invalid",  # Invalid value should be skipped
                    "getSV2": "5",
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should only create select for getSV2
    sv1_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV1']
    
    assert len(sv1_entities) == 0


async def test_async_setup_entry_skip_zero_rpd(hass: HomeAssistant) -> None:
    """Test async_setup_entry skips zero RPD values."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getRPD": "0",  # Zero value should be skipped
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should not create RPD select
    rpd_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getRPD']
    assert len(rpd_entities) == 0


async def test_async_setup_entry_skip_empty_rpd(hass: HomeAssistant) -> None:
    """Test async_setup_entry skips empty RPD values."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getRPD": "",  # Empty value should be skipped
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should not create RPD select
    rpd_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getRPD']
    assert len(rpd_entities) == 0


async def test_async_setup_entry_skip_none_rpd(hass: HomeAssistant) -> None:
    """Test async_setup_entry skips None RPD values."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getRPD": None,
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should not create RPD select
    rpd_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getRPD']
    assert len(rpd_entities) == 0


async def test_async_setup_entry_skip_invalid_rpd(hass: HomeAssistant) -> None:
    """Test async_setup_entry skips invalid RPD values."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getRPD": "invalid",
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should not create RPD select
    rpd_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getRPD']
    assert len(rpd_entities) == 0


async def test_async_setup_entry_custom_model_capacity(hass: HomeAssistant) -> None:
    """Test async_setup_entry uses model-specific salt capacity."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "type": "LEXPLUS10SL",
                "project_id": "project1",
                "status": {
                    "getCNA": "LEXPLUS10SL",
                    "getSV1": "5",
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Find the getSV1 select entity
    sv1_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV1']
    assert len(sv1_entities) == 1


async def test_async_setup_entry_model_from_type_field(hass: HomeAssistant) -> None:
    """Test async_setup_entry gets model from type field when getCNA missing."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "type": "CUSTOMMODEL",
                "project_id": "project1",
                "status": {
                    "getSV1": "5",
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should use default capacity (25) for unknown model
    sv1_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV1']
    assert len(sv1_entities) == 1


async def test_numeric_select_unit_exception_handling(hass: HomeAssistant) -> None:
    """Test numeric select handles exception when converting unit to string."""
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
    
    # Mock a unit that raises exception when converted to string
    class BadUnit:
        def __str__(self):
            raise ValueError("Cannot convert to string")
    
    with patch("custom_components.syr_connect.select._SYR_CONNECT_SENSOR_UNITS", {"getSV1": BadUnit()}):
        select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)
        
        # Should fall back to no unit label
        assert "0" in select.options
        assert "25" in select.options
        # Verify no unit is appended
        assert select.options[0] == "0"


async def test_async_setup_entry_multiple_sv_keys(hass: HomeAssistant) -> None:
    """Test async_setup_entry creates entities for all SV keys."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getSV1": "5",
                    "getSV2": "10",
                    "getSV3": "15",
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should create select for all 3 SV keys
    sv1_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV1']
    sv2_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV2']
    sv3_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV3']
    
    assert len(sv1_entities) == 1
    assert len(sv2_entities) == 1
    assert len(sv3_entities) == 1
