"""Tests for binary_sensor platform."""
from __future__ import annotations

from unittest.mock import MagicMock, Mock

from homeassistant.core import HomeAssistant

from custom_components.syr_connect.binary_sensor import SyrConnectBinarySensor
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
