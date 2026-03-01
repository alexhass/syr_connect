"""Tests for select platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.select import (
    SyrConnectNumericSelect,
    SyrConnectPrfSelect,
    SyrConnectRegenerationSelect,
    _build_time_options,
    async_setup_entry,
)


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


async def test_async_setup_entry(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry creates select entities."""
    data = {
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should create regeneration time select + salt select + RPD select
    assert len(entities) >= 3


async def test_async_setup_entry_no_entities(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry with no valid select entities."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should only create regeneration select (always created if getRTH/getRTM exist)
    assert len(entities) == 0  # No status values, so no selects


async def test_async_setup_entry_no_prf_when_all_pa_false(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry does not create PRF select when all getPA values are false or None."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getRTM": "02:30",
                    "getPA3": "false",
                    "getPA4": "False",
                    "getPA5": "FALSE",
                    "getPA6": None,
                    "getPRF": "1",
                },
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should only create regeneration select (no PRF select because no PA is true)
    prf_entities = [e for e in entities if isinstance(e, SyrConnectPrfSelect)]
    assert len(prf_entities) == 0


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
    with patch("custom_components.syr_connect.select._SYR_CONNECT_SENSOR_UNIT", {}):
        select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getRPD", 1, 4, 1)

        # Options should be plain numbers
        assert "1" in select.options


async def test_prf_select_options_and_current(hass: HomeAssistant) -> None:
    """Test SyrConnectPrfSelect options and current_option behavior."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPRF": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    assert select.options == ["Profile A"]
    assert select.current_option == "Profile A"


async def test_async_setup_entry_registry_exception(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Ensure async_setup_entry handles exceptions from entity registry cleanup."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getRTH": "2",
                    "getRTM": "30",
                },
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    # Force the entity registry accessor to raise to hit the exception branch
    with patch("custom_components.syr_connect.select.er.async_get", side_effect=Exception("boom")):
        await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should still proceed and add the regeneration select
    assert len(entities) >= 1


async def test_numeric_select_options_include_unit(hass: HomeAssistant) -> None:
    """Ensure numeric select options include the configured unit label."""
    data = {
        "devices": [
            {"id": "device1", "name": "Device 1", "project_id": "project1", "status": {"getSV1": "5"}},
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 2, 1)
    # Unit for getSV1 is kilograms -> options should include 'kg'
    assert any(opt.endswith("kg") for opt in select.options)


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


async def test_async_setup_entry_skip_zero_values(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry skips zero salt values."""
    data = {
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should only create select for getSV2 (getSV1 is zero)
    sv1_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV1']
    sv2_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV2']

    assert len(sv1_entities) == 0  # Skipped because value is 0
    assert len(sv2_entities) == 1  # Created


async def test_async_setup_entry_no_data(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry with no coordinator data."""
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(None)
    entities, async_add_entities = mock_add_entities()

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

    # Current integration returns None for out-of-range values instead of applying rollover
    assert select.current_option is None


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


async def test_regeneration_select_combined_current_option(hass: HomeAssistant) -> None:
    """Test current_option when device reports combined getRTM string and no getRTH."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    # Combined representation: no getRTH, getRTM holds HH:MM
                    "getRTM": "07:15",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    assert select.current_option == "07:15"


async def test_regeneration_select_combined_invalid_current_option(hass: HomeAssistant) -> None:
    """Invalid combined getRTM string should result in None for current_option."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    # Invalid format
                    "getRTM": "25:61",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    assert select.current_option is None


async def test_regeneration_select_handles_coordinator_exception(hass: HomeAssistant) -> None:
    """Ensure exceptions from coordinator are caught when setting RTM."""
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
    async def raiser(*args, **kwargs):
        raise Exception("boom")

    coordinator.async_set_device_value = AsyncMock(side_effect=raiser)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    # Should not raise despite coordinator raising internally
    await select.async_select_option("03:45")


async def test_regeneration_select_no_commands_returns(hass: HomeAssistant) -> None:
    """When set_sensor_rtm_value returns no commands, nothing is sent."""
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

    with patch("custom_components.syr_connect.select.set_sensor_rtm_value", return_value=[]):
        await select.async_select_option("03:45")

    coordinator.async_set_device_value.assert_not_called()


async def test_numeric_select_handles_coordinator_exception(hass: HomeAssistant) -> None:
    """Ensure exceptions from coordinator are caught when setting numeric selects."""
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
    async def raiser(*args, **kwargs):
        raise Exception("boom")

    coordinator.async_set_device_value = AsyncMock(side_effect=raiser)
    select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)

    # Should not raise despite coordinator raising internally
    await select.async_select_option("10 kg")


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


async def test_async_setup_entry_skip_empty_sv_values(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry skips empty salt values."""
    data = {
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should only create select for getSV2
    sv1_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV1']
    sv2_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV2']

    assert len(sv1_entities) == 0
    assert len(sv2_entities) == 1


async def test_async_setup_entry_skip_none_sv_values(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry skips None salt values."""
    data = {
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

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


async def test_async_setup_entry_skip_zero_rpd(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry skips zero RPD values."""
    data = {
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should not create RPD select
    rpd_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getRPD']
    assert len(rpd_entities) == 0


async def test_async_setup_entry_skip_empty_rpd(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry skips empty RPD values."""
    data = {
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should not create RPD select
    rpd_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getRPD']
    assert len(rpd_entities) == 0


async def test_async_setup_entry_skip_none_rpd(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry skips None RPD values."""
    data = {
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should not create RPD select
    rpd_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getRPD']
    assert len(rpd_entities) == 0


async def test_async_setup_entry_skip_invalid_rpd(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry skips invalid RPD values."""
    data = {
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should not create RPD select
    rpd_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getRPD']
    assert len(rpd_entities) == 0


async def test_async_setup_entry_custom_model_capacity(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry uses model-specific salt capacity."""
    data = {
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Find the getSV1 select entity
    sv1_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV1']
    assert len(sv1_entities) == 1


async def test_async_setup_entry_model_from_type_field(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry gets model from type field when getCNA missing."""
    data = {
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

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

    with patch("custom_components.syr_connect.select._SYR_CONNECT_SENSOR_UNIT", {"getSV1": BadUnit()}):
        select = SyrConnectNumericSelect(coordinator, "device1", "Device 1", "getSV1", 0, 25, 1)

        # Should fall back to no unit label
        assert "0" in select.options
        assert "25" in select.options
        # Verify no unit is appended
        assert select.options[0] == "0"


async def test_async_setup_entry_multiple_sv_keys(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry creates entities for all SV keys."""
    data = {
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should create select for all 3 SV keys
    sv1_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV1']
    sv2_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV2']
    sv3_entities = [e for e in entities if hasattr(e, '_sensor_key') and e._sensor_key == 'getSV3']

    assert len(sv1_entities) == 1
    assert len(sv2_entities) == 1
    assert len(sv3_entities) == 1


async def test_regeneration_select_combined_mode_sends_only_set_rtm(hass: HomeAssistant) -> None:
    """When device reports combined getRTM (HH:MM) and no getRTH, selection should send only setRTM as string."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    # Combined representation: no getRTH, getRTM holds HH:MM
                    "getRTM": "07:15",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    await select.async_select_option("07:15")

    # Only setRTM should be called with the HH:MM string
    assert coordinator.async_set_device_value.call_count == 1
    coordinator.async_set_device_value.assert_called_once_with("device1", "setRTM", "07:15")
    # Ensure setRTH was not called
    assert not any(c.args[1] == "setRTH" for c in coordinator.async_set_device_value.call_args_list)


async def test_async_setup_entry_removes_excluded_from_registry(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities):
    """Ensure async_setup_entry removes previously-registered excluded selects from the registry."""
    from custom_components.syr_connect import select as select_module

    device_id = "device_del"
    data = {"devices": [{"id": device_id, "name": "Device Del", "status": {}}]}
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    class RegistryEntry:
        def __init__(self, eid):
            self.entity_id = eid

    mock_registry = MagicMock()
    # Make registry.async_get return a RegistryEntry (simulating a previously-registered entity)
    def _get(eid):
        return RegistryEntry(eid)

    mock_registry.async_get.side_effect = _get
    mock_registry.async_remove = MagicMock()

    # Patch the entity registry accessor used by the module to return our mock
    with patch("custom_components.syr_connect.select.er.async_get", return_value=mock_registry):
        await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Verify that async_remove was called at least once for an excluded sensor
    assert mock_registry.async_remove.called


def test_build_time_options_step_60_additional():
    """Build time options with 60-minute step (additional coverage)."""
    opts = _build_time_options(60)
    assert len(opts) == 24
    assert opts[0] == "00:00"
    assert opts[-1] == "23:00"



async def test_regeneration_select_current_and_select_with_mock(create_mock_coordinator, hass):
    data = {"devices": [{"id": "mdev1", "name": "Device M", "status": {"getRTM": "07:30"}, "available": True}]}
    coord = create_mock_coordinator(data)
    coord.last_update_success = True
    coord.async_set_device_value = AsyncMock()

    sel = SyrConnectRegenerationSelect(coord, "mdev1", "Device M")
    assert sel.current_option == "07:30"
    await sel.async_select_option("08:15")
    assert coord.async_set_device_value.await_count >= 1


async def test_numeric_select_current_and_select_with_mock(create_mock_coordinator):
    data = {"devices": [{"id": "mdev2", "status": {"getSV1": "5"}, "available": True}]}
    coord = create_mock_coordinator(data)
    coord.last_update_success = True
    coord.async_set_device_value = AsyncMock()

    num = SyrConnectNumericSelect(coord, "mdev2", "Device M2", "getSV1", 0, 10, 1)
    assert any(opt.startswith("5") for opt in num.options)
    assert num.current_option is not None and num.current_option.startswith("5")
    await num.async_select_option("3")
    coord.async_set_device_value.assert_awaited()


async def test_numeric_select_invalid_option_with_mock(create_mock_coordinator):
    data = {"devices": [{"id": "mdev3", "status": {"getSV1": "5"}}]}
    coord = create_mock_coordinator(data)
    coord.last_update_success = True
    coord.async_set_device_value = AsyncMock()

    num = SyrConnectNumericSelect(coord, "mdev3", "Device M3", "getSV1", 0, 2, 1)
    await num.async_select_option("bad-option")
    coord.async_set_device_value.assert_not_awaited()


def test_prf_select_options_and_current_with_mock(create_mock_coordinator):
    data = {"devices": [{"id": "mdev4", "status": {"getPA1": "true", "getPN1": "Profile A", "getPA2": "false", "getPRF": "1"}, "available": True}]}
    coord = create_mock_coordinator(data)
    coord.last_update_success = True
    prf = SyrConnectPrfSelect(coord, "mdev4", "Device M4")
    opts = prf.options
    assert "Profile A" in opts
    assert prf.current_option == "Profile A"


def test_availability_properties_with_mock(create_mock_coordinator):
    data = {"devices": [{"id": "mdev5", "status": {}, "available": False}]}
    coord = create_mock_coordinator(data)
    coord.last_update_success = False

    regen = SyrConnectRegenerationSelect(coord, "mdev5", "Device M5")
    numeric = SyrConnectNumericSelect(coord, "mdev5", "Device M5", "getSV1", 0, 1, 1)
    prf = SyrConnectPrfSelect(coord, "mdev5", "Device M5")

    assert regen.available is False
    assert numeric.available is False
    assert prf.available is False


async def test_prf_select_handles_coordinator_exception(hass: HomeAssistant) -> None:
    """Ensure exceptions from coordinator are caught when setting PRF."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPRF": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    async def raiser(*args, **kwargs):
        raise Exception("boom")

    coordinator.async_set_device_value = AsyncMock(side_effect=raiser)
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    # Should not raise despite coordinator raising internally
    await select.async_select_option("Profile A")


async def test_prf_select_invalid_current_option_conversion(hass: HomeAssistant) -> None:
    """Test PRF select when getPRF cannot be converted to int."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPRF": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    assert select.current_option is None


async def test_prf_select_profile_not_found(hass: HomeAssistant) -> None:
    """Test PRF select when selected profile is not found."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPRF": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    # Try to select a profile that doesn't exist
    await select.async_select_option("Profile B")

    # Should not call async_set_device_value when profile not found
    coordinator.async_set_device_value.assert_not_called()


async def test_prf_select_unavailable_coordinator(hass: HomeAssistant) -> None:
    """Test PRF select unavailable when coordinator fails."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPRF": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.last_update_success = False
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    assert select.available is False


async def test_prf_select_device_unavailable(hass: HomeAssistant) -> None:
    """Test PRF select unavailable when device unavailable."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": False,
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPRF": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    assert select.available is False


async def test_prf_select_device_not_found_in_current_option(hass: HomeAssistant) -> None:
    """Test PRF select returns None when device not found."""
    data = {
        "devices": [
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPRF": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    assert select.current_option is None


async def test_prf_select_device_not_found_in_available(hass: HomeAssistant) -> None:
    """Test PRF select available returns True when device not found."""
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
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    assert select.available is True


async def test_prf_select_empty_prf_value(hass: HomeAssistant) -> None:
    """Test PRF select when getPRF is empty string."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPRF": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    assert select.current_option is None


async def test_prf_select_none_prf_value(hass: HomeAssistant) -> None:
    """Test PRF select when getPRF is None."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPRF": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    assert select.current_option is None


async def test_prf_select_multiple_profiles(hass: HomeAssistant) -> None:
    """Test PRF select with multiple enabled profiles."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPA2": "true",
                    "getPN2": "Profile B",
                    "getPA3": "false",
                    "getPN3": "Profile C",
                    "getPRF": "2",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    assert "Profile A" in select.options
    assert "Profile B" in select.options
    assert "Profile C" not in select.options
    assert select.current_option == "Profile B"


async def test_prf_select_option_selection(hass: HomeAssistant) -> None:
    """Test PRF select option selection."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPA2": "true",
                    "getPN2": "Profile B",
                    "getPRF": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    await select.async_select_option("Profile B")

    coordinator.async_set_device_value.assert_called_once_with("device1", "setPRF", 2)


async def test_prf_select_missing_profile_name(hass: HomeAssistant) -> None:
    """Test PRF select when profile name (getPN) is missing, fallback to index."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPRF": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    # Should use "1" as fallback when getPN1 is missing
    assert "1" in select.options

    # Current option should be None because getPN1 is missing
    assert select.current_option is None


async def test_async_setup_entry_with_none_pa_values(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry handles None PA values (line 99-100)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getRTM": "02:30",
                    "getPA1": "true",
                    "getPA2": None,
                    "getPA3": None,
                    "getPN1": "Profile A",
                    "getPRF": "1",
                },
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should create PRF select because PA1 is true (None values are skipped)
    prf_entities = [e for e in entities if isinstance(e, SyrConnectPrfSelect)]
    assert len(prf_entities) == 1


async def test_regeneration_select_options_property(hass: HomeAssistant) -> None:
    """Test regeneration select options property (line 189)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRTM": "02:30",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectRegenerationSelect(coordinator, "device1", "Device 1")

    # Access the options property
    options = select.options
    assert isinstance(options, list)
    assert len(options) == 96  # 24 hours * 4 (every 15 min)
    assert "00:00" in options
    assert "23:45" in options


async def test_prf_select_entity_category(hass: HomeAssistant) -> None:
    """Test PRF select has entity_category set (line 378)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPRF": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    # PRF should have entity_category set if in _SYR_CONNECT_SENSOR_CONFIG
    # This tests line 378
    assert hasattr(select, '_attr_entity_category')


async def test_prf_select_options_with_none_pa(hass: HomeAssistant) -> None:
    """Test PRF select options when some PA values are None (line 385)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPA2": None,
                    "getPN2": "Profile B",
                    "getPA3": "true",
                    "getPN3": "Profile C",
                    "getPRF": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    # Should only include profiles where PA is "true", skip None values
    assert "Profile A" in select.options
    assert "Profile B" not in select.options  # PA2 is None
    assert "Profile C" in select.options


async def test_prf_select_async_select_option_with_none_pa(hass: HomeAssistant) -> None:
    """Test PRF select async_select_option skips None PA values (line 421)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "true",
                    "getPN1": "Profile A",
                    "getPA2": None,
                    "getPN2": "Profile B",
                    "getPA3": "true",
                    "getPN3": "Profile C",
                    "getPRF": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    select = SyrConnectPrfSelect(coordinator, "device1", "Device 1")

    # Try to select Profile C (should work, PA3 is true)
    await select.async_select_option("Profile C")
    coordinator.async_set_device_value.assert_called_once_with("device1", "setPRF", 3)

    # Try to select Profile B (should not call because PA2 is None)
    coordinator.async_set_device_value.reset_mock()
    await select.async_select_option("Profile B")
    coordinator.async_set_device_value.assert_not_called()

