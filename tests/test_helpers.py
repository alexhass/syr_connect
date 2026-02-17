"""Tests for helpers module."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.syr_connect.helpers import (
    build_device_info,
    build_entity_id,
    clean_sensor_value,
    extract_flow_value,
    get_current_mac,
)


def test_build_entity_id() -> None:
    """Test entity ID building."""
    entity_id = build_entity_id("sensor", "DEVICE123", "getPRS")
    
    assert entity_id == "sensor.syr_connect_device123_getprs"


def test_build_device_info() -> None:
    """Test device info building."""
    coordinator_data = {
        "devices": [
            {
                "id": "DEVICE123",
                "name": "Test Device",
                "status": {
                    "getCNA": "LEXplus10S",
                    "getVER": "1.0.0",
                    "getFIR": "SLPS",
                    "getMAC": "00:11:22:33:44:55",
                },
            }
        ]
    }
    
    device_info = build_device_info("DEVICE123", "Test Device", coordinator_data)
    
    assert device_info["name"] == "Test Device"
    assert device_info["manufacturer"] == "SYR"
    assert device_info["model"] == "LEXplus10S"
    assert device_info["sw_version"] == "1.0.0"
    assert device_info["hw_version"] == "SLPS"
    assert device_info["serial_number"] == "DEVICE123"
    assert ("mac", "00:11:22:33:44:55") in device_info["connections"]


def test_build_device_info_minimal() -> None:
    """Test device info building with minimal data."""
    coordinator_data = {
        "devices": [
            {
                "id": "DEVICE123",
                "name": "Test Device",
                "status": {},
            }
        ]
    }
    
    device_info = build_device_info("DEVICE123", "Test Device", coordinator_data)
    
    assert device_info["name"] == "Test Device"
    assert device_info["manufacturer"] == "SYR"
    assert device_info["model"] == "SYR Connect"  # Fallback
    assert device_info["serial_number"] == "DEVICE123"


def test_extract_flow_value() -> None:
    """Test flow value extraction from strings."""
    # Test standard format - values in mL converted to L
    assert extract_flow_value("1655mL") == 1.655
    assert extract_flow_value("0mL") == 0.0
    assert extract_flow_value("999mL") == 0.999
    assert extract_flow_value("1000mL") == 1.0
    
    # Test numeric inputs - treated as mL and converted to L
    assert extract_flow_value(1655) == 1.655
    assert extract_flow_value(0) == 0.0
    assert extract_flow_value(100.5) == 0.1005
    
    # Test None input
    assert extract_flow_value(None) is None
    
    # Test fallback: extract number at start and convert to L
    assert extract_flow_value("1655") == 1.655
    assert extract_flow_value("100abc") == 0.1
    
    # Test invalid inputs
    assert extract_flow_value("mL") is None
    assert extract_flow_value("abc") is None
    assert extract_flow_value("") is None
    assert extract_flow_value("no numbers here") is None


def test_get_current_mac_empty_and_none() -> None:
    """Empty or None status returns None."""
    assert get_current_mac({}) is None


def test_get_current_mac_priority_getIPA() -> None:
    """If getIPA present, prefer getMAC."""
    status = {
        "getIPA": "1.2.3.4",
        "getMAC": "AA:BB:CC:DD:EE:FF",
        "getMAC1": "11:22:33:44:55:66",
        "getMAC2": "77:88:99:AA:BB:CC",
    }
    assert get_current_mac(status) == "AA:BB:CC:DD:EE:FF"


def test_get_current_mac_getIPA_mac_empty_fallback() -> None:
    """If preferred MAC is empty, fall back to first available MAC."""
    status = {
        "getIPA": "1.2.3.4",
        "getMAC": "   ",  # whitespace should be treated as empty
        "getMAC1": "11:22:33:44:55:66",
    }
    assert get_current_mac(status) == "11:22:33:44:55:66"


def test_get_current_mac_priority_getWIP_and_getEIP() -> None:
    """Test selection when getWIP/getEIP are present."""
    status_wip = {"getWIP": "10.0.0.1", "getMAC1": "11:11:11:11:11:11"}
    assert get_current_mac(status_wip) == "11:11:11:11:11:11"

    status_eip = {"getEIP": "10.0.0.2", "getMAC2": "22:22:22:22:22:22"}
    assert get_current_mac(status_eip) == "22:22:22:22:22:22"


def test_clean_sensor_value_various() -> None:
    """Clean sensor values with and without prefixes."""
    assert clean_sensor_value("Vol[L]6530") == "6530"
    assert clean_sensor_value("Temp[C] 25 ") == "25"
    # Non-matching string should be returned unchanged
    assert clean_sensor_value("plain_value") == "plain_value"
    # Non-string values are returned unchanged
    assert clean_sensor_value(123) == 123
    assert clean_sensor_value(12.34) == 12.34
