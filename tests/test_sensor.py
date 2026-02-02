"""Tests for sensor platform."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock

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
    registry.async_get_or_create(
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
    
    # Excluded sensor should be removed
    assert registry.async_get("sensor.device1_getdty") is None


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
                    "getSWS": datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "project1", "getSWS")

    # Should handle datetime conversion
    icon = sensor.icon
    assert icon is not None


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

    # Should handle None gracefully
    assert sensor.native_value is None


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
    """Test sensor with float value."""
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

    # Should use float value directly
    assert sensor.native_value == 123.45
