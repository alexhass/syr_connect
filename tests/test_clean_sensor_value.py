"""Tests for sensor value cleaning."""
from custom_components.syr_connect.helpers import get_sensor_vol_value


def test_clean_value_with_prefix():
    """Test cleaning value with prefix like 'Vol[L]6530'."""
    assert get_sensor_vol_value("Vol[L]6530") == "6530"
    assert get_sensor_vol_value("Temp[C]25") == "25"
    assert get_sensor_vol_value("Press[bar]48") == "48"


def test_clean_value_with_prefix_and_decimals():
    """Test cleaning value with prefix and decimal numbers."""
    assert get_sensor_vol_value("Vol[L]123.45") == "123.45"
    assert get_sensor_vol_value("Temp[C]25.5") == "25.5"


def test_clean_value_with_prefix_and_spaces():
    """Test cleaning value with prefix and extra spaces."""
    assert get_sensor_vol_value("Vol[L] 6530") == "6530"
    assert get_sensor_vol_value("Temp[C]  25") == "25"


def test_clean_value_numeric_passthrough():
    """Test that numeric values pass through unchanged."""
    assert get_sensor_vol_value(6530) == 6530
    assert get_sensor_vol_value(123.45) == 123.45
    assert get_sensor_vol_value(0) == 0


def test_clean_value_string_without_prefix():
    """Test that strings without prefix pass through unchanged."""
    assert get_sensor_vol_value("6530") == "6530"
    assert get_sensor_vol_value("123.45") == "123.45"
    assert get_sensor_vol_value("normal_string") == "normal_string"
    assert get_sensor_vol_value("") == ""


def test_clean_value_complex_strings():
    """Test that complex strings without matching pattern pass through."""
    assert get_sensor_vol_value("Status: Active") == "Status: Active"
    assert get_sensor_vol_value("Error[123]") == "Error[123]"  # No value after bracket
    assert get_sensor_vol_value("Test") == "Test"


