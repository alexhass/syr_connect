"""Tests for the device helpers (helpers/device.py)."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001
from typing import Any, cast

import pytest

from custom_components.syr_connect import sensor
from custom_components.syr_connect.aiosyrconnect import (
    SyrConnectStatus,
    get_current_mac,
    is_device_offline,
)
from custom_components.syr_connect.data import SyrConnectDevice
from custom_components.syr_connect.helpers.device import (
    build_device_info,
    detect_device_model,
    get_device,
    get_device_model,
)
from custom_components.syr_connect.models import MODELS, UNKNOWN_MODEL, SyrConnectModel
from custom_components.syr_connect.sensor import is_sensor_visible


def _signature(name: str) -> SyrConnectModel:
    """Return the model signature with the given name."""
    return next(signature for signature in MODELS if signature.name == name)


def _keys_hidden_when(rule: str) -> set[str]:
    """Return the sensor keys whose description hides them for the given empty rule."""
    return {
        description.key
        for description in sensor._SYR_CONNECT_SENSOR_TYPES
        if description.hidden_when == rule
    }


def test_build_device_info_fallback_and_entity_id_additional() -> None:
    """Test build device info fallback and entity id additional."""
    # No device info in coordinator -> fallback model
    coord: Any = {"devices": []}
    di = build_device_info("dev123", "My Dev", coord)
    assert di.serial_number == "dev123"
    assert di.model == "Unknown model"


def test_get_device() -> None:
    """get_device returns the device with the id, None if it is missing."""
    device = {"id": "DEVICE123", "dclg": "DCLG123", "name": "Test Device"}
    coordinator_data = {"devices": [device], "projects": []}

    assert get_device(cast(Any, coordinator_data), "DEVICE123") is device
    assert get_device(cast(Any, coordinator_data), "OTHER") is None
    assert get_device(None, "DEVICE123") is None


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
                    "getIPA": "192.168.178.100",  # Added to trigger MAC detection
                },
            }
        ]
    }

    device_info = build_device_info(
        "DEVICE123", "Test Device", cast(Any, coordinator_data)
    )

    assert device_info.name == "Test Device"
    assert device_info.manufacturer == "SYR"  # LEXplus10S is a SYR device
    assert device_info.model == "LEX Plus 10 S Connect"
    assert device_info.sw_version == "1.0.0"
    assert device_info.hw_version == "SLPS"
    assert device_info.serial_number == "DEVICE123"
    assert device_info.connections == {("mac", "00:11:22:33:44:55")}


def test_build_device_info_service_branding() -> None:
    """The model and manufacturer follow the branding of the cloud service."""
    coordinator_data = {
        "devices": [
            {
                "id": "DEVICE123",
                "name": "Floor",
                "status": {"getVER": "Syr Floorsensor 2.23"},
            }
        ],
        "service": "de.consoft.gc.conel.connect",
    }

    device_info = build_device_info("DEVICE123", "Floor", cast(Any, coordinator_data))

    assert device_info.manufacturer == "CONEL"
    assert device_info.model == "CLEAR PRO Floor Sensor"


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

    device_info = build_device_info(
        "DEVICE123", "Test Device", cast(Any, coordinator_data)
    )

    assert device_info.name == "Test Device"
    assert device_info.manufacturer == "Unknown"  # Fallback when model is undetected
    assert device_info.model == "Unknown model"  # Fallback
    assert device_info.serial_number == "DEVICE123"


# ---------------------------------------------------------------------------
# Coverage fill-ins
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# get_model_supported_keys - per-model devices/<name>.py override resolution
# ---------------------------------------------------------------------------


def test_get_device_model_prefers_the_stored_model() -> None:
    """The model stored by the coordinator wins over detecting it from the status."""
    stored = _signature("trio")
    device: SyrConnectDevice = {
        "id": "dev1",
        "dclg": "dclg1",
        "name": "Device 1",
        "status": {"getCNA": "LEXplus10"},
        "model": stored,
    }
    assert get_device_model(device) is stored


def test_detect_device_model_uses_the_cloud_device_kind() -> None:
    """The device kind from the cloud device list detects the model without a status."""
    device: SyrConnectDevice = {
        "id": "dev1",
        "dclg": "dclg1",
        "name": "Device 1",
        "dk": 122,
        "dkv": 34,
        "sbt": 0,
        "status": {},
    }
    assert detect_device_model(device).name == "safefloor122"


def test_get_device_model_without_stored_model() -> None:
    """Without a device the model is unknown; without a stored model it is detected."""
    assert get_device_model(None) is UNKNOWN_MODEL
    device: SyrConnectDevice = {
        "id": "dev1",
        "dclg": "dclg1",
        "name": "Device 1",
        "status": {"getCNA": "LEXplus10"},
    }
    assert get_device_model(device).name == "lexplus10"


@pytest.mark.parametrize(
    ("dst", "expected"),
    [
        ("0", True),
        ("1", True),
        (" 1 ", True),
        (1, True),
        ("2", False),
        ("3", False),
        ("", False),
        (None, False),
    ],
)
def test_is_device_offline(dst: Any, expected: Any) -> None:
    """The dst values 0 (never online) and 1 (offline) mean offline; everything else does not."""
    assert is_device_offline(dst) is expected


def test_empty_ip_hides_sensor_and_skips_mac() -> None:
    """The unspecified IPv6 address "::" hides an empty_ip sensor and its MAC, like 0.0.0.0."""
    key_ip = next(iter(_keys_hidden_when("empty_ip")))
    assert is_sensor_visible({}, key_ip, "::") is False

    status: SyrConnectStatus = {
        "getIPA": "::",
        "getMAC": "AA:BB",
        "getEIP": "192.168.1.10",
        "getMAC2": "CC:DD",
    }
    assert get_current_mac(status) == "CC:DD"
