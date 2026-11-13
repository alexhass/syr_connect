"""Tests for the entities of the hygiene module and the Safe-T Hygiene module."""

# The tests build the entities with the private builders of the platforms.
# ruff: noqa: SLF001

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.syr_connect.button import SyrConnectButton, _build_device_buttons
from custom_components.syr_connect.data import SyrConnectDevice
from custom_components.syr_connect.helpers import (
    get_hygiene_module_value,
    get_sensor_ala_map,
)
from custom_components.syr_connect.models import MODEL_SIGNATURES, SyrConnectModel
from custom_components.syr_connect.select import (
    SyrConnectHygieneModuleSelect,
    _build_device_selects,
)
from custom_components.syr_connect.sensor import SyrConnectSensor
from custom_components.syr_connect.valve import _build_device_valves
from homeassistant.core import HomeAssistant


def _model(name: str) -> SyrConnectModel:
    """Return the signature with the name."""
    return next(model for model in MODEL_SIGNATURES if model.name == name)


_SYR_CONNECT_TEST_HYGIENE_MODULE_MODEL = _model("hygienemodulehotcold")
_SYR_CONNECT_TEST_HYGIENE_MODULE_COLD_MODEL = _model("hygienemodulecold")
_SYR_CONNECT_TEST_HYGIENE_MODULE_HOT_MODEL = _model("hygienemodulehot")
_SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_MODEL = _model("safethygienemodule")
_SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_COLD_MODEL = _model("safethygienemodulecold")

_SYR_CONNECT_TEST_COLD_KEYS = {"getSCF", "getCCF", "getCCL", "getCSS", "getCSL"}
_SYR_CONNECT_TEST_HOT_KEYS = {"getSWF", "getCWF", "getWCL", "getWSS", "getWSL"}

# Settings of both lines, with and without the suffix the cloud probably adds (assumed)
_SYR_CONNECT_TEST_HYGIENE_MODULE_STATUS = {
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
    ("raw", "expected"),
    [
        pytest.param("3", 3, id="number"),
        pytest.param("3 [1-7]", 3, id="suffix"),
        pytest.param("3[1-7]", 3, id="suffix-without-space"),
        pytest.param(" 14.0 ", 14, id="float-text"),
        pytest.param(6, 6, id="int"),
        pytest.param("", None, id="empty"),
        pytest.param(None, None, id="none"),
        pytest.param(True, None, id="bool"),
        pytest.param("[1-7]", None, id="suffix-only"),
        pytest.param("x", None, id="text"),
        pytest.param("inf", None, id="overflow"),
    ],
)
def test_hygiene_module_value(raw: Any, expected: int | None) -> None:
    """Only the number before a space or a "[" counts."""
    assert get_hygiene_module_value(raw) == expected


@pytest.mark.parametrize(
    ("key", "raw", "expected"),
    [
        pytest.param("getSCF", "3 [1-7]", 3, id="stagnation-days"),
        pytest.param("getCSS", "6[1-99]", 60, id="stop-time-in-seconds"),
        pytest.param("getWCL", "55", 55, id="temperature"),
        pytest.param("getCSL", "", None, id="empty"),
    ],
)
def test_hygiene_module_sensors(
    create_mock_coordinator: Callable[..., MagicMock],
    key: str,
    raw: str,
    expected: int | None,
) -> None:
    """The sensors show the number of the setting in its unit."""
    device = _device(_SYR_CONNECT_TEST_HYGIENE_MODULE_MODEL, {key: raw})
    coordinator = create_mock_coordinator({"devices": [device]})
    sensor = SyrConnectSensor(coordinator, "device1", "D", key)

    assert sensor.native_value == expected


def test_hygiene_module_selects(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The hygiene module offers the five settings of both lines."""
    selects = _selects(
        create_mock_coordinator,
        _SYR_CONNECT_TEST_HYGIENE_MODULE_MODEL,
        _SYR_CONNECT_TEST_HYGIENE_MODULE_STATUS,
    )

    assert set(selects) == _SYR_CONNECT_TEST_COLD_KEYS | _SYR_CONNECT_TEST_HOT_KEYS
    scf = selects["getSCF"]
    assert scf.options == [f"{days} d" for days in range(1, 8)]
    assert scf.current_option == "3 d"
    ccf = selects["getCCF"]
    assert ccf.options == ["off", *(f"{days} d" for days in range(1, 31))]
    assert ccf.current_option == "off"
    assert selects["getCWF"].current_option == "14 d"
    ccl = selects["getCCL"]
    assert ccl.options == ["off", *(f"{value} °C" for value in range(15, 26))]
    assert ccl.current_option == "20 °C"
    wcl = selects["getWCL"]
    assert wcl.options == ["off", *(f"{value} °C" for value in range(55, 66))]
    # A value below the range means "off"
    assert wcl.current_option == "off"
    css = selects["getCSS"]
    assert css.options[0] == "10 s"
    assert css.options[-1] == "990 s"
    assert css.current_option == "60 s"
    assert selects["getWSS"].current_option == "990 s"
    assert selects["getCSL"].options[0] == "1 L"
    assert selects["getWSL"].current_option == "100 L"


@pytest.mark.parametrize(
    ("model", "keys"),
    [
        pytest.param(
            _SYR_CONNECT_TEST_HYGIENE_MODULE_COLD_MODEL,
            _SYR_CONNECT_TEST_COLD_KEYS,
            id="cold",
        ),
        pytest.param(
            _SYR_CONNECT_TEST_HYGIENE_MODULE_HOT_MODEL,
            _SYR_CONNECT_TEST_HOT_KEYS,
            id="hot",
        ),
        pytest.param(
            _SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_COLD_MODEL,
            _SYR_CONNECT_TEST_COLD_KEYS,
            id="safet-cold",
        ),
    ],
)
def test_hygiene_module_one_line(
    create_mock_coordinator: Callable[..., MagicMock],
    model: SyrConnectModel,
    keys: set[str],
) -> None:
    """A module with one line has no selects of the other line, even if it reports them."""
    selects = _selects(
        create_mock_coordinator, model, _SYR_CONNECT_TEST_HYGIENE_MODULE_STATUS
    )

    assert set(selects) == keys


def test_safet_hygiene_module_temperature_ranges(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The Safe-T Hygiene module has other temperature ranges and no "off" for them."""
    selects = _selects(
        create_mock_coordinator,
        _SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_MODEL,
        {**_SYR_CONNECT_TEST_HYGIENE_MODULE_STATUS, "getCCL": "1"},
    )

    assert selects["getCCL"].options == [f"{value} °C" for value in range(2, 41)]
    assert selects["getCCL"].current_option is None
    assert selects["getWCL"].options == [f"{value} °C" for value in range(50, 71)]
    assert selects["getWCL"].current_option == "50 °C"
    assert selects["getCCF"].options[0] == "off"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param({"getCCF": "31"}, None, id="above-the-range"),
        pytest.param({"getCCF": "x"}, None, id="invalid"),
    ],
)
def test_hygiene_module_select_unknown_value(
    create_mock_coordinator: Callable[..., MagicMock],
    status: dict[str, Any],
    expected: str | None,
) -> None:
    """A value that is no option is not shown."""
    device = _device(_SYR_CONNECT_TEST_HYGIENE_MODULE_MODEL, status)
    coordinator = create_mock_coordinator({"devices": [device]})
    select = SyrConnectHygieneModuleSelect(
        coordinator, "device1", "D", "getCCF", {"off": 0, "1 d": 1}, 0
    )

    assert select.current_option == expected


def test_hygiene_module_select_without_device(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """A device missing from the data has no current option."""
    coordinator = create_mock_coordinator({"devices": []})
    select = SyrConnectHygieneModuleSelect(
        coordinator, "device1", "D", "getCCF", {"off": 0, "1 d": 1}, 0
    )

    assert select.current_option is None


@pytest.mark.parametrize(
    ("key", "option", "expected"),
    [
        pytest.param("getCCL", "off", 14, id="temperature-off"),
        pytest.param("getCCF", "off", 0, id="periodic-off"),
        pytest.param("getCSS", "60 s", 6, id="stop-time-in-10-seconds"),
    ],
)
async def test_hygiene_module_select_writes_the_raw_value(
    create_mock_coordinator: Callable[..., MagicMock],
    key: str,
    option: str,
    expected: int,
) -> None:
    """An option writes the raw value of the setting."""
    device = _device(
        _SYR_CONNECT_TEST_HYGIENE_MODULE_MODEL, _SYR_CONNECT_TEST_HYGIENE_MODULE_STATUS
    )
    coordinator = create_mock_coordinator({"devices": [device]})
    coordinator.async_set_device_value = AsyncMock()
    select = _selects(
        create_mock_coordinator,
        _SYR_CONNECT_TEST_HYGIENE_MODULE_MODEL,
        _SYR_CONNECT_TEST_HYGIENE_MODULE_STATUS,
    )[key]
    select.coordinator = coordinator

    await select.async_select_option(option)

    coordinator.async_set_device_value.assert_awaited_once_with(
        "device1", f"set{key[3:]}", expected
    )


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        pytest.param(
            _SYR_CONNECT_TEST_HYGIENE_MODULE_MODEL,
            ["setALA", "setMFC", "setMFW"],
            id="both-lines",
        ),
        pytest.param(
            _SYR_CONNECT_TEST_HYGIENE_MODULE_COLD_MODEL,
            ["setALA", "setMFC"],
            id="cold",
        ),
        pytest.param(
            _SYR_CONNECT_TEST_HYGIENE_MODULE_HOT_MODEL,
            ["setALA", "setMFW"],
            id="hot",
        ),
        pytest.param(
            _SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_MODEL,
            ["setALA"],
            id="safet-without-manual-flushing",
        ),
    ],
)
def test_hygiene_module_buttons(
    hass: HomeAssistant,
    create_mock_coordinator: Callable[..., MagicMock],
    model: SyrConnectModel,
    expected: list[str],
) -> None:
    """The manual flushing of a line is offered by the hygiene module only."""
    device = _device(model, _SYR_CONNECT_TEST_HYGIENE_MODULE_STATUS)
    coordinator = create_mock_coordinator({"devices": [device]})

    buttons = [
        entity._command
        for entity in _build_device_buttons(hass, coordinator, device)
        if isinstance(entity, SyrConnectButton)
    ]

    assert buttons == expected


def test_hygiene_module_manual_flushing_needs_the_line(
    hass: HomeAssistant,
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Without the stagnation time of a line there is no manual flushing of it."""
    device = _device(_SYR_CONNECT_TEST_HYGIENE_MODULE_MODEL, {"getSCF": "3"})
    coordinator = create_mock_coordinator({"devices": [device]})

    buttons = [
        entity._command
        for entity in _build_device_buttons(hass, coordinator, device)
        if isinstance(entity, SyrConnectButton)
    ]

    assert buttons == ["setMFC"]


async def test_hygiene_module_manual_flushing_sends_no_value(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The manual flushing is sent with an empty value."""
    device = _device(_SYR_CONNECT_TEST_HYGIENE_MODULE_MODEL, {"getSWF": "3"})
    coordinator = create_mock_coordinator({"devices": [device]})
    coordinator.async_set_device_value = AsyncMock()
    button = SyrConnectButton(coordinator, "device1", "D", "setMFW")

    await button.async_press()

    coordinator.async_set_device_value.assert_awaited_once_with("device1", "setMFW", "")


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        pytest.param(_SYR_CONNECT_TEST_HYGIENE_MODULE_MODEL, 0, id="hygiene-module"),
        pytest.param(_SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_MODEL, 1, id="safet"),
    ],
)
def test_hygiene_module_valve(
    create_mock_coordinator: Callable[..., MagicMock],
    model: SyrConnectModel,
    expected: int,
) -> None:
    """Only the Safe-T Hygiene module has a shut-off valve."""
    device = _device(model, {"getAB": "1", "getVLV": "20"})
    coordinator = create_mock_coordinator({"devices": [device]})

    assert len(_build_device_valves(coordinator, device)) == expected


@pytest.mark.parametrize(
    ("model", "code", "expected"),
    [
        pytest.param(
            _SYR_CONNECT_TEST_HYGIENE_MODULE_MODEL,
            "AC",
            "alarm_combination_module_communication",
            id="hygiene-module",
        ),
        pytest.param(
            _SYR_CONNECT_TEST_HYGIENE_MODULE_COLD_MODEL,
            "A6",
            "alarm_temperature_cold_exceeded",
            id="hygiene-module-cold",
        ),
        pytest.param(
            _SYR_CONNECT_TEST_SAFET_HYGIENE_MODULE_COLD_MODEL,
            "A0",
            "alarm_safet_microleakage_detected",
            id="safet-uses-the-safet-codes",
        ),
    ],
)
def test_hygiene_module_alarm_codes(
    model: SyrConnectModel, code: str, expected: str
) -> None:
    """The hygiene module has its own alarm codes, the Safe-T Hygiene module those of the Safe-T."""
    assert get_sensor_ala_map(model, code)[0] == expected
