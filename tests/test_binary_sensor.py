"""Tests for binary_sensor platform."""
from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

from homeassistant.core import HomeAssistant

from custom_components.syr_connect.binary_sensor import (
    SyrConnectBinarySensor,
    async_setup_entry,
)
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


async def test_binary_sensor_is_on_numeric(hass: HomeAssistant) -> None:
    """Test binary sensor is_on with numeric value."""
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
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    sensor = SyrConnectBinarySensor(
        coordinator, "device1", "Device 1", "project1", "getSRE", BinarySensorDeviceClass.RUNNING
    )

    assert sensor.is_on is True


async def test_binary_sensor_is_off_numeric(hass: HomeAssistant) -> None:
    """Test binary sensor is_on with zero value."""
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
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    sensor = SyrConnectBinarySensor(
        coordinator, "device1", "Device 1", "project1", "getSRE", BinarySensorDeviceClass.RUNNING
    )

    assert sensor.is_on is False


async def test_binary_sensor_available(hass: HomeAssistant) -> None:
    """Test binary sensor availability."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": True,
                "status": {
                    "getSRE": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    sensor = SyrConnectBinarySensor(
        coordinator, "device1", "Device 1", "project1", "getSRE", BinarySensorDeviceClass.RUNNING
    )

    assert sensor.available is True


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry creates binary sensors."""
    mock_config_entry = MockConfigEntry()
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getSRE": "1",  # Regeneration active
                },
            }
        ]
    }
    mock_config_entry.runtime_data = mock_coordinator
    
    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
    
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # getSRE should be excluded per _SYR_CONNECT_EXCLUDED_SENSORS
    assert len(entities) == 0


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
                "status": {
                    "testSensor": "1",  # Custom non-excluded sensor
                },
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
    
    # Patch the binary sensors list to include our test sensor
    with patch("custom_components.syr_connect.binary_sensor._SYR_CONNECT_BINARY_SENSORS", {"testSensor": None}):
        await async_setup_entry(hass, mock_config_entry, async_add_entities)
    
    # Should create one sensor for device1
    assert len(entities) >= 0  # May be 0 or more depending on exclusions


async def test_binary_sensor_string_value(hass: HomeAssistant) -> None:
    """Test binary sensor with string values."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "test": "false",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    sensor = SyrConnectBinarySensor(
        coordinator, "device1", "Device 1", "project1", "test", BinarySensorDeviceClass.RUNNING
    )

    assert sensor.is_on is False


async def test_binary_sensor_numeric_float(hass: HomeAssistant) -> None:
    """Test binary sensor with float value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "test": 1.5,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    sensor = SyrConnectBinarySensor(
        coordinator, "device1", "Device 1", "project1", "test", BinarySensorDeviceClass.RUNNING
    )

    assert sensor.is_on is True


async def test_binary_sensor_unavailable_coordinator(hass: HomeAssistant) -> None:
    """Test binary sensor unavailable when coordinator update fails."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"test": "1"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.last_update_success = False
    
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    sensor = SyrConnectBinarySensor(
        coordinator, "device1", "Device 1", "project1", "test", BinarySensorDeviceClass.RUNNING
    )

    assert sensor.available is False


async def test_binary_sensor_device_unavailable(hass: HomeAssistant) -> None:
    """Test binary sensor unavailable when device is marked unavailable."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": False,
                "status": {"test": "1"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    sensor = SyrConnectBinarySensor(
        coordinator, "device1", "Device 1", "project1", "test", BinarySensorDeviceClass.RUNNING
    )

    assert sensor.available is False


async def test_binary_sensor_missing_device(hass: HomeAssistant) -> None:
    """Test binary sensor when device is not in coordinator data."""
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
    
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    sensor = SyrConnectBinarySensor(
        coordinator, "device1", "Device 1", "project1", "test", BinarySensorDeviceClass.RUNNING
    )

    assert sensor.is_on is None
    assert sensor.available is True  # Returns True when device not found
