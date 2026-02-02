"""Tests for helpers module."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.syr_connect.helpers import build_device_info, build_entity_id


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
