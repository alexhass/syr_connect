"""Tests for the entities of the dosing pump."""

# The tests build the entities with the private builders of the platforms.
# ruff: noqa: SLF001

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from custom_components.syr_connect.button import SyrConnectButton, _build_device_buttons
from custom_components.syr_connect.data import SyrConnectDevice
from custom_components.syr_connect.helpers import get_sensor_ala_map
from custom_components.syr_connect.models import MODEL_SIGNATURES
from custom_components.syr_connect.select import _build_device_selects
from custom_components.syr_connect.sensor import SyrConnectSensor
from homeassistant.core import HomeAssistant

_SYR_CONNECT_TEST_DOSINGPUMP_MODEL = next(
    model for model in MODEL_SIGNATURES if model.name == "dosingpump"
)

_SYR_CONNECT_TEST_DOSINGPUMP_STATUS = {
    "getCAS": "2",
    "getDSL": "1",
    "getDMO": "0",
    "getDAM": "150",
    "getFLO": "320",
}


def _device(status: dict[str, Any]) -> SyrConnectDevice:
    """Return a dosing pump with the status."""
    return cast(
        SyrConnectDevice,
        {
            "id": "device1",
            "name": "Device 1",
            "model": _SYR_CONNECT_TEST_DOSINGPUMP_MODEL,
            "status": status,
        },
    )


def test_dosingpump_selects(create_mock_coordinator: Callable[..., MagicMock]) -> None:
    """The dosing pump offers canister size, dosing liquid and operating mode."""
    device = _device(_SYR_CONNECT_TEST_DOSINGPUMP_STATUS)
    coordinator = create_mock_coordinator({"devices": [device]})
    selects = {
        str(getattr(entity, "_sensor_key", None)): entity
        for entity in _build_device_selects(coordinator, device)
    }

    assert set(selects) == {"getCAS", "getDMO", "getDSL"}
    assert selects["getCAS"].options == ["5 L", "10 L"]
    assert selects["getCAS"].current_option == "10 L"
    assert selects["getDSL"].options == ["1", "2"]
    assert selects["getDSL"].current_option == "1"
    assert selects["getDMO"].options == ["0", "1", "2", "3"]
    assert selects["getDMO"].current_option == "0"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("1", 5, id="5-liters"),
        pytest.param("2", 10, id="10-liters"),
        pytest.param("0", None, id="not-defined"),
        pytest.param("", None, id="empty"),
        pytest.param("x", None, id="invalid"),
    ],
)
def test_dosingpump_canister_size_in_liters(
    create_mock_coordinator: Callable[..., MagicMock], raw: str, expected: int | None
) -> None:
    """The canister size (getCAS) is shown in liters."""
    device = _device({"getCAS": raw})
    coordinator = create_mock_coordinator({"devices": [device]})
    sensor = SyrConnectSensor(coordinator, "device1", "D", "getCAS")

    assert sensor.native_value == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param("A3", "alarm_dosing_liquid_empty", id="empty"),
        pytest.param("FF", "no_alarm", id="none"),
    ],
)
def test_dosingpump_alarm_codes(code: str, expected: str) -> None:
    """The dosing pump has its own alarm codes."""
    assert get_sensor_ala_map(_SYR_CONNECT_TEST_DOSINGPUMP_MODEL, code)[0] == expected


def test_dosingpump_alarm_reset_button(
    hass: HomeAssistant,
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The dosing pump gets only the alarm reset button, no warning or notification reset."""
    device = _device({"getALA": "A1", "getWRN": "01", "getNOT": "01"})
    coordinator = create_mock_coordinator({"devices": [device]})

    buttons = [
        entity._command
        for entity in _build_device_buttons(hass, coordinator, device)
        if isinstance(entity, SyrConnectButton)
    ]

    assert buttons == ["setALA"]
