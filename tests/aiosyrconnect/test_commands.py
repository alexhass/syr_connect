"""Tests for the commands of the devices (commands.py)."""

from dataclasses import replace
import logging

import pytest

from custom_components.syr_connect.aiosyrconnect.commands import (
    COMMAND_STATUS_KEYS,
    JSON_ONLY_COMMANDS,
    TRIGGER_COMMANDS,
    build_cartridge_type_commands,
    build_dex_command,
    build_flag_command,
    build_reset_command,
    build_sir_command,
    build_trigger_command,
    command_status_key,
    filling_refusal,
    is_flag_enabled,
    is_microleakage_test_running,
    set_command,
)
from custom_components.syr_connect.aiosyrconnect.model_detection import (
    MODEL_SIGNATURES,
    UNKNOWN_MODEL_SIGNATURE,
)
from custom_components.syr_connect.aiosyrconnect.models import (
    SyrConnectModelSignature,
    SyrConnectStatus,
    SyrConnectStatusValue,
)

_ALM_SIGNATURE = replace(
    UNKNOWN_MODEL_SIGNATURE,
    alarm_clear_via_set=True,
    alarm_style_alm=True,
)
_INVERTED_SIGNATURE = replace(
    UNKNOWN_MODEL_SIGNATURE,
    inverted_flags=frozenset(
        {
            "getDFI",
            "getFD1",
        }
    ),
)


def test_set_command() -> None:
    """The set command of a status key replaces "get" with "set"."""
    assert set_command("getRMN") == "setRMN"
    assert set_command("getAB") == "setAB"


@pytest.mark.parametrize(
    ("signature", "command", "expected"),
    [
        (UNKNOWN_MODEL_SIGNATURE, "setALA", "getALA"),
        (_ALM_SIGNATURE, "setALA", "getALM"),
        (UNKNOWN_MODEL_SIGNATURE, "setDEX", "getDSV"),
        (UNKNOWN_MODEL_SIGNATURE, "setMFC", "getSCF"),
        (UNKNOWN_MODEL_SIGNATURE, "setMFW", "getSWF"),
        (UNKNOWN_MODEL_SIGNATURE, "setNOT", "getNOT"),
        (UNKNOWN_MODEL_SIGNATURE, "setSIR", "getSIR"),
    ],
)
def test_command_status_key(
    signature: SyrConnectModelSignature, command: str, expected: str
) -> None:
    """The status key of a command tells that the device has its function."""
    assert command_status_key(signature, command) == expected


def test_command_sets() -> None:
    """The command sets name the commands with a special handling."""
    assert set(COMMAND_STATUS_KEYS) == {"setDEX", "setMFC", "setMFW"}
    assert {"setDEX"} == JSON_ONLY_COMMANDS
    assert {"setMFC", "setMFW", "setUPG"} == TRIGGER_COMMANDS


@pytest.mark.parametrize("command", sorted(TRIGGER_COMMANDS))
def test_build_trigger_command(command: str) -> None:
    """A trigger command takes an empty value."""
    assert build_trigger_command(command) == (command, "")


def test_build_reset_command() -> None:
    """Alarms follow the model; notifications and warnings send the clear value."""
    assert build_reset_command(UNKNOWN_MODEL_SIGNATURE, "setALA", "FF") == (
        "clrALA",
        "",
    )
    assert build_reset_command(_ALM_SIGNATURE, "setALA", 255) == ("setALM", 255)
    assert build_reset_command(UNKNOWN_MODEL_SIGNATURE, "setNOT", "FF") == (
        "setNOT",
        "FF",
    )
    assert build_reset_command(UNKNOWN_MODEL_SIGNATURE, "setWRN", 255) == (
        "setWRN",
        255,
    )


@pytest.mark.parametrize(
    ("sir", "expected"),
    [
        (False, "true"),
        ("false", "true"),
        (" False ", "true"),
        ("1", 0),
        (1, 0),
        (None, 0),
    ],
)
def test_build_sir_command(sir: SyrConnectStatusValue, expected: int | str) -> None:
    """The value of setSIR follows the format of getSIR."""
    assert build_sir_command({"getSIR": sir}) == ("setSIR", expected)


@pytest.mark.parametrize(
    ("typ", "expected"),
    [
        ("50", 1),
        (99, 1),
        ("100", "true"),
        (None, "true"),
        ("x", "true"),
    ],
)
def test_build_dex_command(typ: SyrConnectStatusValue, expected: int | str) -> None:
    """The value of setDEX depends on the device type (getTYP)."""
    assert build_dex_command({"getTYP": typ}) == ("setDEX", expected)


def test_is_microleakage_test_running() -> None:
    """A microleakage test runs while getDSV is 1."""
    assert is_microleakage_test_running({"getDSV": "1"}) is True
    assert is_microleakage_test_running({"getDSV": 1}) is True
    assert is_microleakage_test_running({"getDSV": "0"}) is False
    assert is_microleakage_test_running({}) is False


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("getBUZ", True, True),
        ("getBUZ", "0", False),
        ("getBUZ", "", False),
        ("getFD1", True, False),
        ("getFD1", "0", True),
    ],
)
def test_is_flag_enabled(
    key: str, value: SyrConnectStatusValue, expected: bool
) -> None:
    """A flag of inverted_flags reports the opposite."""
    assert is_flag_enabled(_INVERTED_SIGNATURE, key, value) is expected


@pytest.mark.parametrize(
    ("current", "enabled", "expected"),
    [
        (True, True, True),
        (False, False, False),
        (0, True, 1),
        (1, False, 0),
        ("0", True, "1"),
        (" 1 ", False, "0"),
        ("true", True, "True"),
        (None, False, "False"),
    ],
)
def test_build_flag_command_follows_the_format(
    current: SyrConnectStatusValue, enabled: bool, expected: bool | int | str
) -> None:
    """The value follows the format the device reports for the flag."""
    status: SyrConnectStatus = {"getBUZ": current}
    assert build_flag_command(_INVERTED_SIGNATURE, status, "getBUZ", enabled) == (
        "setBUZ",
        expected,
    )


_ALLINONEPLUS_SIGNATURE = next(
    sig for sig in MODEL_SIGNATURES if sig.name == "allinoneplus"
)
_MUCO_FILLING_SIGNATURE = next(
    sig for sig in MODEL_SIGNATURES if sig.name == "conelclearprofill"
)


@pytest.mark.parametrize(
    ("signature", "status", "cartridge_type", "expected"),
    [
        pytest.param(
            _ALLINONEPLUS_SIGNATURE,
            {"getCRT": "1", "getWTR": "1"},
            None,
            [("setWTR", "0")],
            id="none-switches-off",
        ),
        pytest.param(
            _MUCO_FILLING_SIGNATURE,
            {"getCRT": "1", "getWTR": True},
            None,
            [("setWTR", False)],
            id="none-switches-off-bool",
        ),
        pytest.param(
            _MUCO_FILLING_SIGNATURE,
            {"getCRT": ""},
            None,
            [],
            id="none-without-water-treatment",
        ),
        pytest.param(
            UNKNOWN_MODEL_SIGNATURE,
            {"getCRT": "1", "getWTR": "1"},
            None,
            [],
            id="none-model-without-cartridges",
        ),
        pytest.param(
            _ALLINONEPLUS_SIGNATURE,
            {"getCRT": "1", "getWTR": "1"},
            2,
            [("setCRT", 2)],
            id="type-water-treatment-on",
        ),
        pytest.param(
            _ALLINONEPLUS_SIGNATURE,
            {"getCRT": "1", "getWTR": "0"},
            0,
            [("setCRT", 0), ("setWTR", "1")],
            id="type-switches-on",
        ),
        pytest.param(
            _MUCO_FILLING_SIGNATURE,
            {"getCRT": "1", "getWTR": "False"},
            2,
            [("setCRT", 2), ("setWTR", "True")],
            id="type-switches-on-text",
        ),
        pytest.param(
            _MUCO_FILLING_SIGNATURE,
            {"getCRT": "1"},
            0,
            [("setCRT", 0)],
            id="type-without-water-treatment",
        ),
    ],
)
def test_build_cartridge_type_commands(
    signature: SyrConnectModelSignature,
    status: SyrConnectStatus,
    cartridge_type: int | None,
    expected: list[tuple[str, object]],
) -> None:
    """No cartridge switches the water treatment off, a type switches it on."""
    assert build_cartridge_type_commands(signature, status, cartridge_type) == expected


def test_build_flag_command_inverts() -> None:
    """A flag of inverted_flags is written inverted."""
    status: SyrConnectStatus = {"getFD1": True}
    assert build_flag_command(_INVERTED_SIGNATURE, status, "getFD1", True) == (
        "setFD1",
        False,
    )


@pytest.mark.parametrize(
    ("signature", "status", "key", "expected"),
    [
        (UNKNOWN_MODEL_SIGNATURE, {}, "getIFL", None),
        (UNKNOWN_MODEL_SIGNATURE, {"getDFI": "1"}, "getMFL", "filling_mode"),
        (UNKNOWN_MODEL_SIGNATURE, {"getDFI": "0", "getSTA": "0"}, "getIFL", None),
        (_INVERTED_SIGNATURE, {"getDFI": "0"}, "getMFL", "filling_mode"),
        (_INVERTED_SIGNATURE, {"getDFI": "1", "getSTA": "2"}, "getIFL", "not_standby"),
        (UNKNOWN_MODEL_SIGNATURE, {"getSTA": 2}, "getMFL", None),
    ],
)
def test_filling_refusal(
    signature: SyrConnectModelSignature,
    status: SyrConnectStatus,
    key: str,
    expected: str | None,
) -> None:
    """A filling starts only without the automatic filling mode; initial only when idle."""
    assert filling_refusal(signature, status, key) == expected


def test_filling_refusal_is_logged_at_debug_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The library logs a refusal at debug level only."""
    with caplog.at_level(logging.DEBUG, logger="custom_components.syr_connect"):
        filling_refusal(UNKNOWN_MODEL_SIGNATURE, {"getDFI": "1"}, "getMFL")
    assert "automatic filling mode is on" in caplog.text
    assert not [r for r in caplog.records if r.levelno > logging.DEBUG]
