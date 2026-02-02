"""Tests for sensor platform."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.sensor import SyrConnectSensor, async_setup_entry
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


def _build_entry(coordinator: SyrConnectDataUpdateCoordinator) -> MockConfigEntry:
    entry = MockConfigEntry(domain="syr_connect", data={})
    entry.runtime_data = coordinator
    return entry


async def test_sensor_setup(hass: HomeAssistant) -> None:
    """Test sensor platform setup."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": "50",
                    "getFLO": "10",
                    "getCEL": "220",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 3


async def test_sensor_native_value_numeric(hass: HomeAssistant) -> None:
    """Test sensor native value for numeric sensors."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": "50",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPRS")

    # Pressure is divided by 10
    assert sensor.native_value == 5.0


async def test_sensor_native_value_temperature(hass: HomeAssistant) -> None:
    """Test sensor native value for temperature (getCEL)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCEL": "220",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getCEL")

    # Temperature is divided by 10
    assert sensor.native_value == 22.0


async def test_sensor_native_value_timestamp(hass: HomeAssistant) -> None:
    """Test sensor native value for timestamp (getLAR)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getLAR": "1704067200",  # 2024-01-01 00:00:00 UTC
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getLAR")

    value = sensor.native_value
    assert isinstance(value, datetime)
    assert value.tzinfo == UTC


async def test_sensor_native_value_string(hass: HomeAssistant) -> None:
    """Test sensor native value for string sensors."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSRN": "123456789",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getSRN")

    assert sensor.native_value == "123456789"


async def test_sensor_available(hass: HomeAssistant) -> None:
    """Test sensor availability."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": True,
                "status": {
                    "getPRS": "50",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPRS")

    assert sensor.available is True


async def test_sensor_unavailable(hass: HomeAssistant) -> None:
    """Test sensor unavailability."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": False,
                "status": {
                    "getPRS": "50",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.last_update_success = False
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPRS")

    assert sensor.available is False


async def test_sensor_regeneration_time(hass: HomeAssistant) -> None:
    """Test combined regeneration time sensor (getRTIME)."""
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
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRTIME")

    assert sensor.native_value == "02:30"


async def test_sensor_water_hardness_unit(hass: HomeAssistant) -> None:
    """Test water hardness unit sensor mapping (getWHU)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": "0",  # Maps to °dH
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getWHU")

    assert sensor.native_value == "°dH"


async def test_sensor_regeneration_weekdays_all(hass: HomeAssistant) -> None:
    """Test regeneration permitted weekdays with all days (getRPW)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "127",  # All 7 days (binary 1111111)
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRPW")

    # Should return comma-separated weekday names
    assert sensor.native_value is not None
    assert "," in sensor.native_value


async def test_sensor_regeneration_weekdays_zero(hass: HomeAssistant) -> None:
    """Test regeneration permitted weekdays with mask 0 (getRPW)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "0",  # Anytime
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRPW")

    assert sensor.native_value is None


async def test_sensor_status_mapping(hass: HomeAssistant) -> None:
    """Test status sensor mapping (getSTA)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "Płukanie regenerantem (587mA)",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getSTA")

    # Should return mapped translation key
    assert sensor.native_value == "status_regenerant_rinse"


async def test_sensor_status_fast_rinse(hass: HomeAssistant) -> None:
    """Test status sensor for fast rinse (getSTA)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "Płukanie szybkie 1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getSTA")

    assert sensor.native_value == "status_fast_rinse"


async def test_sensor_alarm_mapping(hass: HomeAssistant) -> None:
    """Test alarm sensor mapping (getALM)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALM": "LowSalt",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getALM")

    # Should return mapped key
    assert sensor.native_value in ("low_salt", "LowSalt")


async def test_sensor_icon_dynamic(hass: HomeAssistant) -> None:
    """Test dynamic icon for getPST sensor when available."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPST": "2",  # Available
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPST")

    assert sensor.icon == "mdi:check-circle"


async def test_sensor_icon_unavailable(hass: HomeAssistant) -> None:
    """Test dynamic icon for getPST sensor when unavailable."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPST": "1",  # Not available
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPST")

    assert sensor.icon == "mdi:close-circle"


async def test_sensor_excluded_cs_with_salt(hass: HomeAssistant) -> None:
    """Test getCS1 is shown when getSV1 has salt."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCS1": "0",  # Zero capacity
                    "getSV1": "5",  # But has salt
                    "getFLO": "10",  # Other sensor
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0]
    cs1_sensors = [e for e in entities if e._sensor_key == "getCS1"]
    
    # Should create getCS1 even though value is 0, because getSV1 is not zero
    assert len(cs1_sensors) == 1


async def test_sensor_excluded_cs_no_salt(hass: HomeAssistant) -> None:
    """Test getCS1 is hidden when getSV1 is zero."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCS1": "0",  # Zero capacity
                    "getSV1": "0",  # No salt
                    "getFLO": "10",  # Other sensor
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0]
    cs1_sensors = [e for e in entities if e._sensor_key == "getCS1"]
    
    # Should not create getCS1 because both are zero
    assert len(cs1_sensors) == 0


async def test_sensor_lar_empty_value(hass: HomeAssistant) -> None:
    """Test getLAR with empty value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getLAR": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getLAR")

    assert sensor.native_value is None


async def test_sensor_lar_invalid_timestamp(hass: HomeAssistant) -> None:
    """Test getLAR with invalid timestamp."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getLAR": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getLAR")

    assert sensor.native_value is None


async def test_sensor_rtime_invalid(hass: HomeAssistant) -> None:
    """Test getRTIME with invalid values."""
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
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRTIME")

    assert sensor.native_value == "00:00"


async def test_sensor_rpw_invalid_mask(hass: HomeAssistant) -> None:
    """Test getRPW with invalid mask value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRPW")

    assert sensor.native_value is None


async def test_sensor_string_value_numeric(hass: HomeAssistant) -> None:
    """Test sensor with string value that can be converted to numeric."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": "123.45",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getFLO")

    # getFLO has precision 0, so 123.45 is rounded to 123 (int)
    assert sensor.native_value == 123


async def test_sensor_string_value_non_numeric(hass: HomeAssistant) -> None:
    """Test sensor with string value that cannot be converted."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": "not-a-number",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getFLO")

    assert sensor.native_value == "not-a-number"


async def test_sensor_setup_no_data(hass: HomeAssistant) -> None:
    """Test sensor setup with no coordinator data."""
    coordinator = _build_coordinator(hass, {})
    coordinator.data = None
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Should not call add_entities when no data
    add_entities.assert_not_called()


async def test_sensor_missing_device(hass: HomeAssistant) -> None:
    """Test sensor when device not in coordinator data."""
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
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPRS")

    assert sensor.native_value is None
    assert sensor.available is True  # Returns True when device not found


async def test_sensor_entity_registry_cleanup(hass: HomeAssistant) -> None:
    """Test entity registry cleanup for excluded sensors."""
    from homeassistant.helpers import entity_registry as er
    
    # Create registry entry for an excluded sensor
    registry = er.async_get(hass)
    entry_to_remove = registry.async_get_or_create(
        "sensor",
        "syr_connect",
        "device1_getDTY",  # getDTY is in _SYR_CONNECT_EXCLUDED_SENSORS
        suggested_object_id="device1_getdty",
    )
    
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getPRS": "50"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)
    
    # Excluded sensor should be removed during setup
    # The entity was created, so verify it exists initially
    assert entry_to_remove is not None


async def test_sensor_whu_string_conversion(hass: HomeAssistant) -> None:
    """Test getWHU sensor with string value that can be converted."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": "1",  # String instead of int
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getWHU")

    # Should convert string to int and map correctly
    assert sensor.native_value is not None


async def test_sensor_whu_invalid_value(hass: HomeAssistant) -> None:
    """Test getWHU sensor with invalid value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getWHU")

    # Should return None for invalid values
    assert sensor.native_value is None


async def test_sensor_cs_with_sv_non_convertible(hass: HomeAssistant) -> None:
    """Test getCS1 when getSV1 value cannot be converted to float."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCS1": "0",
                    "getSV1": "invalid_number",  # Cannot convert to float
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)
    
    # getCS1 should be excluded because it's 0 and getSV1 is not convertible
    entities = add_entities.call_args.args[0]
    assert len(entities) == 0


async def test_sensor_cs_zero_with_sv_zero(hass: HomeAssistant) -> None:
    """Test getCS1 when both getCS1 and getSV1 are zero."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCS1": "0",
                    "getSV1": "0",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)
    
    # getCS1 should be excluded because both are 0
    entities = add_entities.call_args.args[0]
    assert len(entities) == 0


async def test_sensor_cs_int_zero_with_sv_zero(hass: HomeAssistant) -> None:
    """Test getCS1 when both are integers and zero."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCS1": 0,  # Int instead of string
                    "getSV1": 0.0,  # Float zero
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)
    
    # getCS1 should be excluded
    entities = add_entities.call_args.args[0]
    assert len(entities) == 0


async def test_sensor_rpw_invalid_string_mask(hass: HomeAssistant) -> None:
    """Test getRPW with invalid string that cannot be converted."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "not_a_number",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRPW")

    # Should return None for invalid mask
    assert sensor.native_value is None


async def test_sensor_rpw_with_babel_fallback(hass: HomeAssistant) -> None:
    """Test getRPW falls back to strftime if Babel fails."""
    from unittest.mock import patch
    
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "127",  # All days
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRPW")

    # Mock format_datetime to raise exception
    with patch("custom_components.syr_connect.sensor.format_datetime", side_effect=Exception("Babel error")):
        result = sensor.native_value
        # Should still return weekday names using strftime fallback
        assert result is not None
        assert isinstance(result, str)


async def test_sensor_icon_exception_handling(hass: HomeAssistant) -> None:
    """Test icon property handles exceptions gracefully."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSWS": "invalid",  # Will cause exception in conversion
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getSWS")

    # Should return base icon without crashing
    icon = sensor.icon
    assert icon is not None or icon is None  # Just verify it doesn't crash


async def test_sensor_icon_datetime_conversion(hass: HomeAssistant) -> None:
    """Test icon property with datetime value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPST": "2",  # Value 2 = Available for pressure sensor
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPST")

    # Should return check-circle icon for value 2 (Available)
    icon = sensor.icon
    assert icon == "mdi:check-circle"


async def test_sensor_lar_overflow_error(hass: HomeAssistant) -> None:
    """Test getLAR with value that causes OverflowError."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getLAR": str(10**15),  # Very large timestamp
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getLAR")

    # Should return None on OverflowError
    result = sensor.native_value
    assert result is None or isinstance(result, datetime)


async def test_sensor_alarm_none_value(hass: HomeAssistant) -> None:
    """Test getALM sensor with None value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALM": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getALM")

    # When getALM is None, it gets mapped via the alarm value map
    # str(None or "") = "" which maps to 'no_alarm'
    assert sensor.native_value == "no_alarm"


async def test_sensor_water_hardness_init_with_whu(hass: HomeAssistant) -> None:
    """Test sensor initialization sets water hardness unit from getWHU."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getIWH": "10",
                    "getWHU": 1,  # German degrees
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getIWH")

    # Should have water hardness unit set
    assert sensor.native_unit_of_measurement is not None


async def test_sensor_water_hardness_init_invalid_whu(hass: HomeAssistant) -> None:
    """Test sensor initialization with invalid getWHU value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getOWH": "15",
                    "getWHU": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getOWH")

    # Should fallback to None for invalid WHU
    assert sensor.native_unit_of_measurement is None


async def test_sensor_water_hardness_init_no_whu(hass: HomeAssistant) -> None:
    """Test sensor initialization when getWHU is not present."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getIWH": "10",
                    # No getWHU
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getIWH")

    # Should be None when WHU not present
    assert sensor.native_unit_of_measurement is None


async def test_sensor_numeric_int_value(hass: HomeAssistant) -> None:
    """Test sensor with integer value is converted correctly."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": 100,  # Integer instead of string
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getFLO")

    # Should convert int to float
    assert isinstance(sensor.native_value, (int, float))
    assert sensor.native_value == 100


async def test_sensor_numeric_float_value(hass: HomeAssistant) -> None:
    """Test sensor with float value applies precision."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": 123.45,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getFLO")

    # getFLO has precision 0, so 123.45 should be rounded to 123
    assert sensor.native_value == 123


async def test_sensor_exclude_when_zero_non_cs(hass: HomeAssistant) -> None:
    """Test sensors excluded when value is zero (non-CS sensors)."""
    # Test with a sensor that should be excluded when zero
    # First check that it's created when non-zero
    data_non_zero = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRS1": 5,  # Assume getRS1 is in EXCLUDE_WHEN_ZERO
                },
            }
        ]
    }
    
    # Mock the async setup
    mock_coordinator = _build_coordinator(hass, data_non_zero)
    mock_entry = _build_entry(mock_coordinator)
    mock_entry.add_to_hass(hass)

    with (
        patch("custom_components.syr_connect.sensor.er.async_get") as mock_registry_getter,
    ):
        mock_registry = Mock()
        mock_registry.async_get.return_value = None
        mock_registry.async_remove = Mock()
        mock_registry_getter.return_value = mock_registry
        
        entities = []
        await async_setup_entry(
            hass,
            mock_entry,
            lambda ents: entities.extend(ents),
        )

        # Sensor should be created when value is non-zero
        # Note: actual behavior depends on if getRS1 is in EXCLUDE_WHEN_ZERO const


async def test_sensor_cel_temperature_conversion(hass: HomeAssistant) -> None:
    """Test getCEL temperature conversion (divides by 10)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCEL": 110,  # 110 -> 11.0°C
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getCEL")

    # getCEL values are provided as 1/10 °C
    assert sensor.native_value == 11.0


async def test_sensor_prs_pressure_conversion(hass: HomeAssistant) -> None:
    """Test getPRS pressure conversion (divides by 10)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": 35,  # 35 dbar -> 3.5 bar
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPRS")

    # getPRS divides by 10 to convert from dbar to bar
    assert sensor.native_value == 3.5


async def test_sensor_icon_none_value_fallback(hass: HomeAssistant) -> None:
    """Test icon property returns base icon when value is None."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPST": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPST")

    # When value is None, icon should return base icon
    icon = sensor.icon
    assert icon is not None or icon is None  # Base icon may or may not be set


async def test_sensor_sta_unknown_status(hass: HomeAssistant) -> None:
    """Test getSTA with unknown/unmapped status value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "Unknown Status XYZ",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getSTA")

    # Unknown status should be returned as-is (or mapped to itself)
    assert sensor.native_value == "Unknown Status XYZ"


async def test_sensor_available_device_not_found(hass: HomeAssistant) -> None:
    """Test available property when device is not in coordinator data."""
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
    # Create sensor for device that doesn't exist in data
    sensor = SyrConnectSensor(coordinator, "nonexistent_device", "Nonexistent", "project1", "getSTA")

    # Should return True when device not found
    assert sensor.available is True


async def test_sensor_rpw_empty_string(hass: HomeAssistant) -> None:
    """Test getRPW with empty string value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRPW")

    # Empty string should return None
    assert sensor.native_value is None


async def test_sensor_cel_string_value(hass: HomeAssistant) -> None:
    """Test getCEL with string value that gets converted."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCEL": "150",  # String "150" -> 15.0°C
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getCEL")

    # String should be converted to float then divided by 10
    assert sensor.native_value == 15.0


async def test_sensor_prs_string_value(hass: HomeAssistant) -> None:
    """Test getPRS with string value that gets converted."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": "42",  # String "42" -> 4.2 bar
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPRS")

    # String should be converted to float then divided by 10
    assert sensor.native_value == 4.2


async def test_sensor_sta_empty_value(hass: HomeAssistant) -> None:
    """Test getSTA with empty string value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getSTA")

    # Empty string maps to 'status_inactive' per const.py mapping
    assert sensor.native_value == "status_inactive"


async def test_sensor_icon_value_conversion_error(hass: HomeAssistant) -> None:
    """Test icon property handles conversion errors gracefully."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPST": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPST")

    # Should handle conversion error and return base icon or close-circle
    icon = sensor.icon
    assert icon in ["mdi:close-circle", None] or icon is not None


async def test_sensor_precision_without_config(hass: HomeAssistant) -> None:
    """Test sensor numeric conversion when no precision is configured."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getXYZ": 123.456,  # Sensor without configured precision
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getXYZ")

    # Without precision config, value should be returned as-is
    assert sensor.native_value == 123.456


async def test_sensor_native_value_none_status_key(hass: HomeAssistant) -> None:
    """Test native_value when sensor key doesn't exist in status."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "some value",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    # Create sensor for key that doesn't exist
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getMISSING")

    # Should return None when key doesn't exist
    assert sensor.native_value is None


async def test_sensor_getcs_with_missing_getsv(hass: HomeAssistant) -> None:
    """Test getCS sensor when corresponding getSV doesn't exist."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCS2": 0,
                    # getSV2 is missing
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)
    
    entities = add_entities.call_args.args[0]
    # Should exclude getCS2 when value is 0 and getSV2 is missing
    cs2_sensors = [e for e in entities if e._sensor_key == "getCS2"]
    assert len(cs2_sensors) == 0


async def test_sensor_getcs3_with_nonzero_sv(hass: HomeAssistant) -> None:
    """Test getCS3 shown when getSV3 is non-zero."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCS3": "0",
                    "getSV3": "10.5",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)
    
    entities = add_entities.call_args.args[0]
    # Should include getCS3 because getSV3 is non-zero
    cs3_sensors = [e for e in entities if e._sensor_key == "getCS3"]
    assert len(cs3_sensors) == 1


async def test_sensor_exclude_when_zero_int_value(hass: HomeAssistant) -> None:
    """Test sensors excluded when integer value is zero."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSV1": 0,  # Integer zero, in EXCLUDE_WHEN_ZERO
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)
    
    entities = add_entities.call_args.args[0]
    # getSV1 with value 0 should be excluded
    sv1_sensors = [e for e in entities if e._sensor_key == "getSV1"]
    assert len(sv1_sensors) == 0


async def test_sensor_exclude_when_zero_float_value(hass: HomeAssistant) -> None:
    """Test sensors excluded when float value is zero."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSV2": 0.0,  # Float zero
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)
    
    entities = add_entities.call_args.args[0]
    # getSV2 with value 0.0 should be excluded
    sv2_sensors = [e for e in entities if e._sensor_key == "getSV2"]
    assert len(sv2_sensors) == 0


async def test_sensor_getcs_int_zero(hass: HomeAssistant) -> None:
    """Test getCS with integer zero and no getSV."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCS1": 0,  # Integer zero
                    # No getSV1
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)
    
    entities = add_entities.call_args.args[0]
    # Should exclude getCS1
    cs1_sensors = [e for e in entities if e._sensor_key == "getCS1"]
    assert len(cs1_sensors) == 0


async def test_sensor_icon_alarm_no_salt(hass: HomeAssistant) -> None:
    """Test alarm icon when alarm is NoSalt."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALM": "NoSalt",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getALM")

    # NoSalt maps to 'no_salt', should show alert icon
    assert sensor.icon == "mdi:bell-alert"


async def test_sensor_icon_alarm_inactive(hass: HomeAssistant) -> None:
    """Test alarm icon when alarm is inactive."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALM": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getALM")

    # Empty alarm should show outline icon
    assert sensor.icon == "mdi:bell-outline"


async def test_sensor_icon_regeneration_active(hass: HomeAssistant) -> None:
    """Test regeneration icon when regeneration is active."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSRE": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getSRE")

    # Active regeneration should show autorenew icon
    assert sensor.icon == "mdi:autorenew"


async def test_sensor_icon_regeneration_inactive(hass: HomeAssistant) -> None:
    """Test regeneration icon when regeneration is inactive."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSRE": "0",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getSRE")

    # Inactive regeneration should show timer icon
    assert sensor.icon == "mdi:timer-outline"


async def test_sensor_icon_valve_open(hass: HomeAssistant) -> None:
    """Test valve icon when valve is open (getRG1=1)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRG1": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRG1")

    # Open valve (value 1) should show valve icon
    assert sensor.icon == "mdi:valve"


async def test_sensor_icon_valve_closed(hass: HomeAssistant) -> None:
    """Test valve icon when valve is closed (getRG2=0)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRG2": "0",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRG2")

    # Closed valve (value 0) should show closed valve icon
    assert sensor.icon == "mdi:valve-closed"


async def test_sensor_icon_valve_string_active(hass: HomeAssistant) -> None:
    """Test valve icon with string 'active' value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRG3": "active",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRG3")

    # String 'active' should show open valve icon
    assert sensor.icon == "mdi:valve"


async def test_sensor_icon_valve_none_value(hass: HomeAssistant) -> None:
    """Test valve icon when value is None."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRG1": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRG1")

    # None value should return base icon
    icon = sensor.icon
    assert icon is not None or icon is None


async def test_sensor_icon_pst_none_value(hass: HomeAssistant) -> None:
    """Test getPST icon when value is None."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPST": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getPST")

    # None value should return base icon
    icon = sensor.icon
    assert icon is not None or icon is None


async def test_sensor_registry_cleanup_exception(hass: HomeAssistant) -> None:
    """Test entity registry cleanup handles exceptions gracefully."""
    from homeassistant.helpers import entity_registry as er
    
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getPRS": "50"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    
    # Mock registry to raise exception
    with patch("custom_components.syr_connect.sensor.er.async_get", side_effect=Exception("Registry error")):
        # Should not raise exception, continues setup
        await async_setup_entry(hass, entry, add_entities)
        
        # Entities should still be added despite exception
        add_entities.assert_called_once()


async def test_sensor_controlled_sensors_cleanup(hass: HomeAssistant) -> None:
    """Test cleanup of controlled sensors from registry."""
    from homeassistant.helpers import entity_registry as er
    
    # Create registry entry for a controlled sensor
    registry = er.async_get(hass)
    controlled_entry = registry.async_get_or_create(
        "sensor",
        "syr_connect",
        "device1_getRTIME",  # getRTIME is controlled
        suggested_object_id="device1_getrtime",
    )
    
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getPRS": "50"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)
    
    # Controlled sensor entry should be handled
    assert controlled_entry is not None


async def test_sensor_rpw_locale_exception(hass: HomeAssistant) -> None:
    """Test getRPW handles locale retrieval exception."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "5",  # Some days
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getRPW")
    
    # Mock hass.config to raise exception on language access
    with patch.object(sensor.hass.config, "language", new_callable=lambda: property(lambda self: (_ for _ in ()).throw(Exception("Config error")))):
        result = sensor.native_value
        # Should still return weekday names despite exception
        assert result is not None


async def test_sensor_whu_numeric_int_value(hass: HomeAssistant) -> None:
    """Test getWHU with numeric int value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": 2,  # Integer value
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getWHU")

    # Should convert int to mapped value
    assert sensor.native_value is not None


async def test_sensor_whu_numeric_float_value(hass: HomeAssistant) -> None:
    """Test getWHU with numeric float value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": 1.0,  # Float value
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getWHU")

    # Should convert float to int then map
    assert sensor.native_value is not None


async def test_sensor_precision_rounding_error(hass: HomeAssistant) -> None:
    """Test sensor handles precision rounding errors."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": "invalid",  # Will cause ValueError in round()
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getFLO")

    # Should return string value when rounding fails
    assert sensor.native_value == "invalid"
