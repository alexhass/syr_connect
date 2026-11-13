"""Tests for the entities of the Safe-T Hygiene module."""

# The tests build the entities with the private builders of the platforms.
# ruff: noqa: SLF001

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from custom_components.syr_connect.button import SyrConnectButton, _build_device_buttons
from custom_components.syr_connect.data import SyrConnectDevice
from custom_components.syr_connect.helpers import get_sensor_ala_map
from custom_components.syr_connect.models import MODEL_SIGNATURES, SyrConnectModel
from custom_components.syr_connect.select import (
    SyrConnectHygieneModuleSelect,
    _build_device_selects,
)
from custom_components.syr_connect.valve import _build_device_valves
from homeassistant.core import HomeAssistant


def _model(name: str) -> SyrConnectModel:
    """Return the signature with the name."""
    return next(model for model in MODEL_SIGNATURES if model.name == name)


_SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_MODEL = _model("safethygienemodule")
_SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_COLD_MODEL = _model("safethygienemodulecold")

_SYR_CONNECT_TEST_COLD_KEYS = {"getSCF", "getCCF", "getCCL", "getCSS", "getCSL"}
_SYR_CONNECT_TEST_HOT_KEYS = {"getSWF", "getCWF", "getWCL", "getWSS", "getWSL"}

# Settings of both lines, with and without the suffix the cloud probably adds (assumed)
_SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_STATUS = {
    "getSCF": "3 [1-7]",
    "getCCF": "0",
    "getCCL": "20",
    "getCSS": "6[1-99]",
    "getCSL": "10",
    "getSWF": "7",
    "getCWF": "14 [0-30]",
    "getWCL": "50",
    "getWSS": "99",
    "getWSL": "100",
    "getALA": "FF",
}


def _device(model: SyrConnectModel, status: dict[str, Any]) -> SyrConnectDevice:
    """Return a device of the model with the status."""
    return cast(
        SyrConnectDevice,
        {"id": "device1", "name": "Device 1", "model": model, "status": status},
    )


def _selects(
    create_mock_coordinator: Callable[..., MagicMock],
    model: SyrConnectModel,
    status: dict[str, Any],
) -> dict[str, SyrConnectHygieneModuleSelect]:
    """Return the hygiene module selects of a device by key."""
    device = _device(model, status)
    coordinator = create_mock_coordinator({"devices": [device]})
    return {
        entity._sensor_key: entity
        for entity in _build_device_selects(coordinator, device)
        if isinstance(entity, SyrConnectHygieneModuleSelect)
    }


@pytest.mark.parametrize(
    ("model", "keys"),
    [
        pytest.param(
            _SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_MODEL,
            _SYR_CONNECT_TEST_COLD_KEYS | _SYR_CONNECT_TEST_HOT_KEYS,
            id="both-lines",
        ),
        pytest.param(
            _SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_COLD_MODEL,
            _SYR_CONNECT_TEST_COLD_KEYS,
            id="cold",
        ),
    ],
)
def test_safet_hygiene_module_lines(
    create_mock_coordinator: Callable[..., MagicMock],
    model: SyrConnectModel,
    keys: set[str],
) -> None:
    """A module with one line has no selects of the other line, even if it reports them."""
    selects = _selects(
        create_mock_coordinator, model, _SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_STATUS
    )

    assert set(selects) == keys


def test_safet_hygiene_module_temperature_ranges(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The Safe-T Hygiene module has other temperature ranges and no "off" for them."""
    selects = _selects(
        create_mock_coordinator,
        _SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_MODEL,
        {**_SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_STATUS, "getCCL": "1"},
    )

    assert selects["getCCL"].options == [f"{value} °C" for value in range(2, 41)]
    assert selects["getCCL"].current_option is None
    assert selects["getWCL"].options == [f"{value} °C" for value in range(50, 71)]
    assert selects["getWCL"].current_option == "50 °C"
    assert selects["getCCF"].options[0] == "off"


def test_safet_hygiene_module_buttons(
    hass: HomeAssistant,
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The Safe-T Hygiene module has no manual flushing, only the alarm reset."""
    device = _device(
        _SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_MODEL,
        _SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_STATUS,
    )
    coordinator = create_mock_coordinator({"devices": [device]})

    buttons = [
        entity._command
        for entity in _build_device_buttons(hass, coordinator, device)
        if isinstance(entity, SyrConnectButton)
    ]

    assert buttons == ["setALA"]


def test_safet_hygiene_module_valve(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The Safe-T Hygiene module has a shut-off valve."""
    device = _device(
        _SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_MODEL, {"getAB": "1", "getVLV": "20"}
    )
    coordinator = create_mock_coordinator({"devices": [device]})

    assert len(_build_device_valves(coordinator, device)) == 1


def test_safet_hygiene_module_alarm_codes() -> None:
    """The Safe-T Hygiene module uses the alarm codes of the Safe-T."""
    assert (
        get_sensor_ala_map(_SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_COLD_MODEL, "A0")[0]
        == "alarm_safet_microleakage_detected"
    )
