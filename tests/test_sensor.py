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
