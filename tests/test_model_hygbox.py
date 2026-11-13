"""Tests for the entities of the HygBox."""

# The tests build the entities with the private builders of the platforms.
# ruff: noqa: SLF001

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.syr_connect.button import SyrConnectButton, _build_device_buttons
from custom_components.syr_connect.data import SyrConnectDevice
from custom_components.syr_connect.helpers import get_sensor_ala_map
from custom_components.syr_connect.models import MODEL_SIGNATURES, SyrConnectModel
from custom_components.syr_connect.select import (
    SyrConnectDiscreteSelect,
    SyrConnectFlushingTemperatureSelect,
    SyrConnectNumericSelect,
    _build_device_selects,
)
from custom_components.syr_connect.switch import (
    SyrConnectBooleanSwitch,
    _build_device_switches,
)
from homeassistant.core import HomeAssistant

_SYR_CONNECT_TEST_HYGBOX_MODEL = next(
    model for model in MODEL_SIGNATURES if model.name == "hygbox"
)
# Default settings of a HygBox for cold water
_SYR_CONNECT_TEST_HYGBOX_STATUS = {
    "getWTY": "1",
    "getFD1": "False",
    "getFD2": "True",
    "getFD3": "False",
    "getSTP": "2880",
    "getSTV": "10",
    "getTTT": "25",
    "getF2W": "10",
    "getF2T": "30",
    "getMTF": "5",
    "getF3P": "720",
    "getF3V": "10",
    "getRCP": "43200",
    "getBUZ": "True",
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
) -> dict[str, Any]:
    """Return the selects of a device by key."""
    device = _device(model, status)
    coordinator = create_mock_coordinator({"devices": [device]})
    return {
        str(getattr(entity, "_sensor_key", None)): entity
        for entity in _build_device_selects(coordinator, device)
    }


def test_hygbox_selects(create_mock_coordinator: Callable[..., MagicMock]) -> None:
    """The HygBox offers its settings with the documented ranges."""
    selects = _selects(
        create_mock_coordinator,
        _SYR_CONNECT_TEST_HYGBOX_MODEL,
        _SYR_CONNECT_TEST_HYGBOX_STATUS,
    )

    assert set(selects) == {
        "getF2T",
        "getF2W",
        "getF3P",
        "getF3V",
        "getMTF",
        "getRCP",
        "getSTP",
        "getSTV",
        "getTTT",
        "getWTY",
    }
    assert isinstance(selects["getWTY"], SyrConnectDiscreteSelect)
    assert selects["getWTY"].options == ["1", "2"]
    assert selects["getWTY"].current_option == "1"
    stp = selects["getSTP"]
    assert isinstance(stp, SyrConnectNumericSelect)
    assert stp.options[0] == "60 min"
    assert stp.options[23] == "1440 min"
    assert stp.options[-1] == "43200 min"
    assert stp.current_option == "2880 min"
    assert selects["getF3P"].options[-1] == "17280 min"
    assert selects["getF3P"].current_option == "720 min"
    assert selects["getSTV"].options[0] == "1 L"
    assert selects["getSTV"].options[-1] == "100 L"
    assert selects["getF3V"].current_option == "10 L"
    assert selects["getF2T"].options[0] == "30 s"
    assert selects["getF2T"].options[-1] == "600 s"
    assert selects["getMTF"].options[0] == "1"
    assert selects["getMTF"].options[-1] == "50"
    assert selects["getMTF"].current_option == "5"
    # The synchronization interval keeps to 6 hours - 8 days
    assert selects["getRCP"].options == [
        "21600",
        "43200",
        "86400",
        "172800",
        "259200",
        "345600",
        "432000",
        "518400",
        "604800",
        "691200",
    ]


@pytest.mark.parametrize(
    ("status", "start", "stop"),
    [
        pytest.param(
            {"getWTY": "1", "getTTT": "25", "getF2W": "10"},
            (12, 25),
            (10, 23),
            id="cold-water",
        ),
        pytest.param(
            {"getWTY": "2", "getTTT": "50", "getF2W": "60"},
            (50, 58),
            (52, 60),
            id="hot-water",
        ),
        pytest.param(
            {"getWTY": "1", "getTTT": "", "getF2W": ""},
            (10, 25),
            (10, 25),
            id="without-the-other-temperature",
        ),
    ],
)
def test_hygbox_flushing_temperatures_follow_the_water_type(
    create_mock_coordinator: Callable[..., MagicMock],
    status: dict[str, Any],
    start: tuple[int, int],
    stop: tuple[int, int],
) -> None:
    """The start and stop temperature keep to the water type and 2 °C apart."""
    device = _device(_SYR_CONNECT_TEST_HYGBOX_MODEL, status)
    coordinator = create_mock_coordinator({"devices": [device]})
    ttt = SyrConnectFlushingTemperatureSelect(coordinator, "device1", "D", "getTTT")
    f2w = SyrConnectFlushingTemperatureSelect(coordinator, "device1", "D", "getF2W")

    assert ttt.options == [f"{v} °C" for v in range(start[0], start[1] + 1)]
    assert f2w.options == [f"{v} °C" for v in range(stop[0], stop[1] + 1)]
    expected_start = f"{status['getTTT']} °C" if status["getTTT"] else None
    assert ttt.current_option == expected_start


@pytest.mark.parametrize(
    "status",
    [
        pytest.param({"getWTY": "0", "getTTT": "25", "getF2W": "10"}, id="undefined"),
        pytest.param({"getWTY": "", "getTTT": "25", "getF2W": "10"}, id="empty"),
        pytest.param({"getWTY": "1", "getTTT": "25", "getF2W": "24"}, id="no-gap"),
    ],
)
def test_hygbox_flushing_temperature_without_range(
    create_mock_coordinator: Callable[..., MagicMock], status: dict[str, Any]
) -> None:
    """Without a water type or with a too small distance, no temperature can be selected."""
    device = _device(_SYR_CONNECT_TEST_HYGBOX_MODEL, status)
    coordinator = create_mock_coordinator({"devices": [device]})
    ttt = SyrConnectFlushingTemperatureSelect(coordinator, "device1", "D", "getTTT")

    assert ttt.options == []
    assert ttt.current_option is None


def test_hygbox_flushing_temperature_without_device(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """A device missing from the data has no current temperature."""
    coordinator = create_mock_coordinator({"devices": []})
    ttt = SyrConnectFlushingTemperatureSelect(coordinator, "device1", "D", "getTTT")

    assert ttt.current_option is None


def test_hygbox_switches_are_inverted(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """getFD1-3 report the flushing as disabled, the switches show it as enabled."""
    device = _device(_SYR_CONNECT_TEST_HYGBOX_MODEL, _SYR_CONNECT_TEST_HYGBOX_STATUS)
    coordinator = create_mock_coordinator({"devices": [device]})
    switches = {
        entity._sensor_key: entity
        for entity in _build_device_switches(coordinator, device)
        if isinstance(entity, SyrConnectBooleanSwitch)
    }

    assert set(switches) == {"getBUZ", "getFD1", "getFD2", "getFD3"}
    assert switches["getFD1"].is_on is True
    assert switches["getFD2"].is_on is False
    assert switches["getFD3"].is_on is True
    assert switches["getBUZ"].is_on is True


@pytest.mark.parametrize(
    ("turn_on", "expected"),
    [
        pytest.param(True, "False", id="enable"),
        pytest.param(False, "True", id="disable"),
    ],
)
async def test_hygbox_inverted_switch_writes_the_opposite(
    create_mock_coordinator: Callable[..., MagicMock], turn_on: bool, expected: str
) -> None:
    """Turning a flushing on writes "disabled = False" to the device."""
    device = _device(_SYR_CONNECT_TEST_HYGBOX_MODEL, {"getFD1": "False"})
    coordinator = create_mock_coordinator({"devices": [device]})
    coordinator.async_set_device_value = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    switch = SyrConnectBooleanSwitch(coordinator, "device1", "D", "getFD1")

    if turn_on:
        await switch.async_turn_on()
    else:
        await switch.async_turn_off()

    coordinator.async_set_device_value.assert_awaited_once_with(
        "device1", "setFD1", expected
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param("A4", "alarm_solenoid_valve_fault", id="solenoid-valve"),
        pytest.param("a9", "alarm_periodic_flushing_time_exceeded", id="lowercase"),
    ],
)
def test_hygbox_alarm_codes(code: str, expected: str) -> None:
    """The HygBox has its own alarm codes."""
    assert get_sensor_ala_map(_SYR_CONNECT_TEST_HYGBOX_MODEL, code)[0] == expected


def test_hygbox_alarm_reset_button(
    hass: HomeAssistant,
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The HygBox gets only the alarm reset button, no warning or notification reset."""
    device = _device(
        _SYR_CONNECT_TEST_HYGBOX_MODEL,
        {"getALA": "A1", "getWRN": "01", "getNOT": "01"},
    )
    coordinator = create_mock_coordinator({"devices": [device]})

    buttons = [
        entity._command
        for entity in _build_device_buttons(hass, coordinator, device)
        if isinstance(entity, SyrConnectButton)
    ]

    assert buttons == ["setALA"]
