"""Tests for getCOF water consumption sensor on LEXplus10SL."""

import pytest
from unittest.mock import Mock
from custom_components.syr_connect.sensor import SyrConnectSensor
from custom_components.syr_connect.const import (
    _SYR_CONNECT_SENSOR_DEVICE_CLASS,
    _SYR_CONNECT_SENSOR_STATE_CLASS,
)


def test_getcof_has_water_device_class():
    """Test that getCOF sensor has device_class=water for Energy Dashboard."""
    assert "getCOF" in _SYR_CONNECT_SENSOR_DEVICE_CLASS
    from homeassistant.components.sensor import SensorDeviceClass

    assert _SYR_CONNECT_SENSOR_DEVICE_CLASS["getCOF"] == SensorDeviceClass.WATER


def test_getcof_has_total_increasing_state_class():
    """Test that getCOF sensor has state_class=total_increasing for statistics."""
    assert "getCOF" in _SYR_CONNECT_SENSOR_STATE_CLASS
    assert _SYR_CONNECT_SENSOR_STATE_CLASS["getCOF"] == "total_increasing"


def test_getcof_returns_correct_value():
    """Test that getCOF sensor returns the correct water consumption value."""
    # Create mock coordinator with test data
    mock_coordinator = Mock()
    mock_coordinator.data = {
        "devices": [
            {
                "id": "210836887",
                "name": "Test Device",
                "status": {
                    "getCOF": 888518,  # Water consumption in liters
                },
            }
        ]
    }

    # Create sensor instance
    sensor = SyrConnectSensor(
        coordinator=mock_coordinator,
        device_id="210836887",
        device_name="Test Device",
        project_id="test-project",
        sensor_key="getCOF",
    )

    # Test that native_value returns getCOF value
    assert sensor.native_value == 888518


def test_getcof_handles_string_values():
    """Test that getCOF sensor correctly converts string values to float."""
    mock_coordinator = Mock()
    mock_coordinator.data = {
        "devices": [
            {
                "id": "210836887",
                "name": "Test Device",
                "status": {
                    "getCOF": "888518",  # String value
                },
            }
        ]
    }

    sensor = SyrConnectSensor(
        coordinator=mock_coordinator,
        device_id="210836887",
        device_name="Test Device",
        project_id="test-project",
        sensor_key="getCOF",
    )

    # Should convert string to float
    assert sensor.native_value == 888518.0
    assert isinstance(sensor.native_value, float)


def test_getcof_not_excluded():
    """Test that getCOF is not in the excluded sensors list."""
    from custom_components.syr_connect.const import (
        _SYR_CONNECT_EXCLUDED_SENSORS,
    )

    assert "getCOF" not in _SYR_CONNECT_EXCLUDED_SENSORS
