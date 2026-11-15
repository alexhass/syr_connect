"""Tests for the device helpers (helpers/device.py)."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001
from typing import Any, cast

import pytest

from custom_components.syr_connect import sensor
from custom_components.syr_connect.data import SyrConnectDevice
from custom_components.syr_connect.helpers.device import (
    build_device_info,
    detect_device_model,
    get_current_mac,
    get_device,
    get_device_model,
    is_device_offline,
)
from custom_components.syr_connect.models import (
    MODEL_SIGNATURES,
    UNKNOWN_MODEL,
    SyrConnectModel,
)
from custom_components.syr_connect.sensor import is_sensor_visible


def _signature(name: str) -> SyrConnectModel:
    """Return the model signature with the given name."""
    return next(signature for signature in MODEL_SIGNATURES if signature.name == name)


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


def test_get_current_mac_priorities_additional() -> None:
    """Test get current mac priorities additional."""
    # Primary IP -> getMAC
    s = {"getIPA": "192.168.1.2", "getMAC": "AA:BB:CC"}
    assert get_current_mac(s) == "AA:BB:CC"

    # WiFi IP with WFS==2 -> getMAC1
    s = {"getWIP": "192.168.1.3", "getWFS": "2", "getMAC1": "11:22:33"}
    assert get_current_mac(s) == "11:22:33"

    # Ethernet IP -> getMAC2
    s = {"getEIP": "10.0.0.1", "getMAC2": "22:33:44"}
    assert get_current_mac(s) == "22:33:44"

    # Empty status
    assert get_current_mac({}) is None


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


def test_get_current_mac_priority_getipa() -> None:
    """If getIPA present, prefer getMAC."""
    status = {
        "getIPA": "1.2.3.4",
        "getMAC": "AA:BB:CC:DD:EE:FF",
        "getMAC1": "11:22:33:44:55:66",
        "getMAC2": "77:88:99:AA:BB:CC",
    }
    assert get_current_mac(status) == "AA:BB:CC:DD:EE:FF"


def test_get_current_mac_getipa_mac_empty_fallback() -> None:
    """If preferred MAC is empty, fall back to first available MAC."""
    status = {
        "getIPA": "1.2.3.4",
        "getMAC": "   ",  # whitespace should be treated as empty
        "getWIP": "192.168.178.21",
        "getMAC1": "11:22:33:44:55:66",
        "getWFS": 2,
    }
    assert get_current_mac(status) == "11:22:33:44:55:66"


def test_get_current_mac_zero_ip_treated_as_empty() -> None:
    """An IP value of '0.0.0.0' should be treated as empty and fall back."""
    status = {
        "getIPA": "0.0.0.0",
        "getMAC": "   ",  # preferred MAC empty
        "getWIP": "192.168.178.22",
        "getMAC1": "11:22:33:44:55:66",
        "getWFS": 2,
    }
    assert get_current_mac(status) == "11:22:33:44:55:66"


def test_get_current_mac_priority_getwip_and_geteip() -> None:
    """Test selection when getWIP/getEIP are present."""
    status_wip = {"getWIP": "10.0.0.1", "getMAC1": "11:11:11:11:11:11", "getWFS": 2}
    assert get_current_mac(status_wip) == "11:11:11:11:11:11"

    status_eip = {"getEIP": "10.0.0.2", "getMAC2": "22:22:22:22:22:22"}
    assert get_current_mac(status_eip) == "22:22:22:22:22:22"


def test_get_current_mac_non_string_ip_value() -> None:
    """Test that non-string IP values (int, float, bool, etc.) are treated as present.

    This covers the case where is_not_empty_ip returns True for non-string values.
    """
    # IP value as int should be treated as present
    status_int = {"getIPA": 123456, "getMAC": "AA:BB:CC:DD:EE:FF"}
    assert get_current_mac(status_int) == "AA:BB:CC:DD:EE:FF"

    # IP value as float should be treated as present
    status_float = {"getWIP": 192.168, "getMAC1": "11:22:33:44:55:66", "getWFS": 2}
    assert get_current_mac(status_float) == "11:22:33:44:55:66"

    # IP value as bool should be treated as present
    status_bool = {"getEIP": True, "getMAC2": "77:88:99:AA:BB:CC"}
    assert get_current_mac(status_bool) == "77:88:99:AA:BB:CC"


def test_get_current_mac_wifi_not_connected() -> None:
    """The Wi-Fi MAC is only used while the Wi-Fi is connected (getWFS 2)."""
    # Wi-Fi present but WFS indicates not connected
    status = {"getWIP": "10.0.0.5", "getWFS": "1", "getMAC1": "11:11:11:11:11:11"}
    assert get_current_mac(status) is None

    # Wi-Fi present but WFS unparsable -> skip Wi-Fi MAC
    status2 = {"getWIP": "10.0.0.6", "getWFS": "bad", "getMAC1": "22:22:22:22:22:22"}
    assert get_current_mac(status2) is None


def test_get_current_mac_eip_fallback_when_wfs_unparsable() -> None:
    """When getWFS unparsable, ensure getEIP/getMAC2 fallback is used."""
    status = {
        "getWIP": "192.168.1.10",
        "getWFS": "bad",
        "getMAC1": "",
        "getEIP": "10.0.0.2",
        "getMAC2": "22:22:22:22:22:22",
    }
    assert get_current_mac(status) == "22:22:22:22:22:22"


# ---------------------------------------------------------------------------
# Coverage fill-ins
# ---------------------------------------------------------------------------


def test_get_current_mac_wip_present_wfs_none() -> None:
    """When getWIP is set but getWFS key is absent, wfs_int stays None (line 246)."""
    # getWFS missing entirely -> else branch sets wfs_int = None -> MAC1 not returned
    status = {"getWIP": "192.168.1.5", "getMAC1": "AA:BB:CC:DD:EE:FF"}
    # wfs_int is None, so wfs_int == 2 is False -> falls through to getEIP (absent)
    assert get_current_mac(status) is None


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

    status = {
        "getIPA": "::",
        "getMAC": "AA:BB",
        "getEIP": "192.168.1.10",
        "getMAC2": "CC:DD",
    }
    assert get_current_mac(status) == "CC:DD"
