"""Tests for getFCO water consumption sensor fix on LEXplus10SL."""
import pytest
from unittest.mock import Mock, patch
from custom_components.syr_connect.sensor import SyrConnectSensor
from custom_components.syr_connect.const import _SYR_CONNECT_SENSOR_DEVICE_CLASS, _SYR_CONNECT_SENSOR_STATE_CLASS


def test_getfco_has_water_device_class():
    """Test that getFCO sensor has device_class=water for Energy Dashboard compatibility."""
    assert "getFCO" in _SYR_CONNECT_SENSOR_DEVICE_CLASS
    from homeassistant.components.sensor import SensorDeviceClass
    assert _SYR_CONNECT_SENSOR_DEVICE_CLASS["getFCO"] == SensorDeviceClass.WATER


def test_getfco_has_total_increasing_state_class():
    """Test that getFCO sensor has state_class=total_increasing for statistics."""
    assert "getFCO" in _SYR_CONNECT_SENSOR_STATE_CLASS
    assert _SYR_CONNECT_SENSOR_STATE_CLASS["getFCO"] == "total_increasing"


def test_getfco_uses_getcof_value():
    """Test that getFCO sensor reads value from getCOF on LEXplus10SL."""
    # Create mock coordinator with test data
    mock_coordinator = Mock()
    mock_coordinator.data = {
        'devices': [{
            'id': '210836887',
            'name': 'Test Device',
            'status': {
                'getFCO': 0,        # XML value is 0
                'getCOF': 888518,   # Actual value in getCOF
            }
        }]
    }
    
    # Create sensor instance
    sensor = SyrConnectSensor(
        coordinator=mock_coordinator,
        device_id='210836887',
        device_name='Test Device',
        project_id='test-project',
        sensor_key='getFCO'
    )
    
    # Test that native_value returns getCOF value, not getFCO
    assert sensor.native_value == 888518
    assert sensor.native_value != 0


def test_getfco_fallback_when_getcof_missing():
    """Test that getFCO falls back to default handling when getCOF is not available."""
    mock_coordinator = Mock()
    mock_coordinator.data = {
        'devices': [{
            'id': '210836887',
            'name': 'Test Device',
            'status': {
                'getFCO': 100,  # Only getFCO available (older devices)
                # getCOF not present
            }
        }]
    }
    
    sensor = SyrConnectSensor(
        coordinator=mock_coordinator,
        device_id='210836887',
        device_name='Test Device',
        project_id='test-project',
        sensor_key='getFCO'
    )
    
    # Should fall back to getFCO value when getCOF is not available
    assert sensor.native_value == 100


def test_getfco_handles_string_values():
    """Test that getFCO sensor correctly converts string values to float."""
    mock_coordinator = Mock()
    mock_coordinator.data = {
        'devices': [{
            'id': '210836887',
            'name': 'Test Device',
            'status': {
                'getFCO': '0',
                'getCOF': '888518',  # String value
            }
        }]
    }
    
    sensor = SyrConnectSensor(
        coordinator=mock_coordinator,
        device_id='210836887',
        device_name='Test Device',
        project_id='test-project',
        sensor_key='getFCO'
    )
    
    # Should convert string to float
    assert sensor.native_value == 888518.0
    assert isinstance(sensor.native_value, float)


def test_getcof_not_excluded():
    """Test that getCOF is not in the excluded sensors list."""
    from custom_components.syr_connect.const import _SYR_CONNECT_EXCLUDED_SENSORS
    assert 'getCOF' not in _SYR_CONNECT_EXCLUDED_SENSORS


def test_getfco_not_excluded_when_zero():
    """Test that getFCO is not in the exclude-when-zero list."""
    from custom_components.syr_connect.const import _SYR_CONNECT_EXCLUDE_WHEN_ZERO
    assert 'getFCO' not in _SYR_CONNECT_EXCLUDE_WHEN_ZERO
