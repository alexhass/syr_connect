"""Tests for the data models of the library (models.py): the lookups of a signature."""

from typing import Any

import pytest

from custom_components.syr_connect.aiosyrconnect.model_detection import (
    MODEL_SIGNATURES,
    UNKNOWN_MODEL_SIGNATURE,
)
from custom_components.syr_connect.aiosyrconnect.models import (
    SyrConnectModelSignature,
    SyrConnectStatus,
    SyrConnectStatusValue,
)


def _signature(name: str) -> SyrConnectModelSignature:
    """Return the signature with the given name, "unknown" for the unknown model."""
    if name == "unknown":
        return UNKNOWN_MODEL_SIGNATURE
    return next(sig for sig in MODEL_SIGNATURES if sig.name == name)


@pytest.mark.parametrize(
    ("name", "code", "expected"),
    [
        ("neosoft2500", "FF", "no_alarm"),
        ("neosoft2500", "a1", "alarm_end_switch"),
        ("neosoft2500", " AC ", "alarm_increased_water_hardness"),
        ("safetplus", "LowBat", "alarm_battery_low"),
        ("lexplus10", "0", "no_alarm"),
        ("lexplus10", "ZZ", None),
        ("neosoft2500", None, None),
        ("unknown", "A5", None),
    ],
)
def test_alarm_meaning(name: str, code: Any, expected: str | None) -> None:
    """Alarm codes are looked up in the table of the family, in upper case."""
    assert _signature(name).alarm_meaning(code) == expected


@pytest.mark.parametrize(
    ("name", "code", "expected"),
    [
        ("neosoft2500", "01", "new_software_available"),
        ("neosoft2500", "", "no_notification"),
        ("lex10", "01", None),
        ("unknown", "01", None),
    ],
)
def test_notification_meaning(name: str, code: Any, expected: str | None) -> None:
    """Notification codes are looked up in the table of the family."""
    assert _signature(name).notification_meaning(code) == expected


@pytest.mark.parametrize(
    ("name", "code", "expected"),
    [
        ("neosoft2500", "01", "power_outage"),
        ("hva", "ff", "no_warning"),
        ("safetech", "01", None),
        ("unknown", None, None),
    ],
)
def test_warning_meaning(name: str, code: Any, expected: str | None) -> None:
    """Warning codes are looked up in the table of the family."""
    assert _signature(name).warning_meaning(code) == expected


@pytest.mark.parametrize(
    ("name", "code", "expected"),
    [
        ("lex30", "5", "mmol/l"),
        ("neosoft2500", 1, "mmol/l"),
        ("conelclearprofill", "2.0", "°fH"),
        ("lex30", "9", None),
        ("lex30", None, None),
        ("lex30", "x", None),
        ("unknown", "0", None),
    ],
)
def test_whu_unit(name: str, code: Any, expected: str | None) -> None:
    """The unit of getWHU follows the table of the family."""
    assert _signature(name).whu_unit(code) == expected


@pytest.mark.parametrize(
    ("name", "code", "expected"),
    [
        ("neosoft2500", "1", 10),
        ("neosoft2500", "0", 1),
        ("neosoft2500", None, 1),
        ("lex30", "5", 1),
    ],
)
def test_hardness_divisor(name: str, code: Any, expected: int) -> None:
    """NeoSoft reports the water hardness in tenths of mmol/l."""
    assert _signature(name).hardness_divisor(code) == expected


@pytest.mark.parametrize(
    ("name", "status", "expected"),
    [
        ("conelclearprofill", {"getCRT": "0"}, {"getOHW"}),
        ("conelclearprofill", {"getCRT": " 2 "}, {"getLOT"}),
        ("allinoneplus", {"getCRT": "0", "getCRS": "0"}, {"getOWH", "getFCS"}),
        ("allinoneplus", {"getCRT": "1", "getCRS": "3"}, set()),
        ("conelclearprofill", {}, set()),
        ("unknown", {"getCRT": "0"}, set()),
        ("conelclearprofill", {"getCRT": "0", "getWTR": False}, set()),
        (
            "allinoneplus",
            {"getCRT": "0", "getCRS": "0", "getWTR": "0"},
            {"getFCS"},
        ),
    ],
)
def test_reported_cartridge_keys(
    name: str, status: SyrConnectStatus, expected: set[str]
) -> None:
    """The keys of the reported cartridge type and size."""
    assert _signature(name).reported_cartridge_keys(status) == expected


@pytest.mark.parametrize(
    ("key", "status", "expected"),
    [
        pytest.param("getMIH", {"getMXH": "20"}, [0, 5, 10, 15], id="below-upper"),
        pytest.param("getMXH", {"getMIH": "85"}, [90, 95, 100], id="above-lower"),
        pytest.param(
            "getMIT",
            {"getMXT": "-250"},
            [-300, -290, -280, -270, -260],
            id="below-upper-distance",
        ),
        pytest.param(
            "getMIT",
            {"getMXT": "700"},
            list(range(-300, 501, 10)),
            id="upper-limit-off",
        ),
        pytest.param(
            "getMIT",
            {"getMXT": "500"},
            list(range(-300, 491, 10)),
            id="below-highest-upper",
        ),
        pytest.param(
            "getMXT",
            {"getMIT": "-400"},
            list(range(10, 501, 10)),
            id="lower-limit-off",
        ),
        pytest.param(
            "getWMP",
            {"getRCP": "21600"},
            [60, 600, 900, 1800, 3600, 7200, 10800, 21600],
            id="at-most-upper",
        ),
        pytest.param(
            "getWMP",
            {"getRCP": "abc"},
            [
                60,
                600,
                900,
                1800,
                3600,
                7200,
                10800,
                21600,
                32400,
                43200,
                57600,
                72000,
                86400,
            ],
            id="invalid-limit",
        ),
        pytest.param("getRMN", {}, list(range(1, 11)), id="no-limit"),
        pytest.param("getXYZ", {}, None, id="unknown-setting"),
    ],
)
def test_limited_values(
    key: str, status: SyrConnectStatus, expected: list[int] | None
) -> None:
    """A setting stays within the limit that another setting of the device sets."""
    assert _signature("safefloor").limited_values(key, status) == expected


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("allinoneplus", "0", True),
        ("allinoneplus", "1", False),
        ("conelclearprofill", False, True),
        ("conelclearprofill", True, False),
        ("conelclearprofill", " False ", True),
        ("conelclearprofill", "True", False),
        ("conelclearprofill", 0, True),
        ("conelclearprofill", "", False),
        ("conelclearprofill", None, False),
        ("lex30", "0", False),
    ],
)
def test_is_water_treatment_off(
    name: str, value: SyrConnectStatusValue, expected: bool
) -> None:
    """Only a model with cartridge types has a water treatment that can be off."""
    status: SyrConnectStatus = {} if value is None else {"getWTR": value}

    assert _signature(name).is_water_treatment_off(status) is expected


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        pytest.param("conelclearprofill", {"getLOT", "getOHW"}, id="muco-filling"),
        pytest.param("allinoneplus", {"getFCS", "getOWH"}, id="allinoneplus"),
        pytest.param("lex30", set(), id="softener"),
        pytest.param("unknown", set(), id="unknown-model"),
    ],
)
def test_cartridge_dependent_keys(model: str, expected: set[str]) -> None:
    """The signature names the keys that only apply to one cartridge type or size."""
    signature = _signature(model)

    assert signature.cartridge_dependent_keys == expected


@pytest.mark.parametrize(
    ("model", "key", "raw_code", "expected"),
    [
        pytest.param("allinoneplus", "getIWH", "3", (10, 900, 10), id="ppm"),
        pytest.param("allinoneplus", "getOWH", 1, (0, 16, 1), id="e"),
        pytest.param("allinoneplus", "getOWH", "7", None, id="unknown-unit"),
        pytest.param("allinoneplus", "getOWH", None, None, id="no-unit"),
        pytest.param("lex30", "getIWH", "0", None, id="fixed-range"),
        pytest.param("unknown", "getIWH", "0", None, id="unknown-model"),
    ],
)
def test_hardness_range(
    model: str, key: str, raw_code: Any, expected: tuple[int, int, int] | None
) -> None:
    """The signature names the water hardness range per unit (getWHU)."""
    signature = _signature(model)

    assert signature.hardness_range(key, raw_code) == expected


@pytest.mark.parametrize(
    ("model", "raw_code", "expected"),
    [
        pytest.param("conelclearprofill", "0", 1.0, id="dh"),
        pytest.param("conelclearprofill", 1, 1.25216338, id="e"),
        pytest.param("conelclearprofill", "2.0", 1.78480457, id="fh"),
        pytest.param("conelclearprofill", "3", 17.8480457, id="ppm"),
        pytest.param("conelclearprofill", "7", 1.0, id="unknown-unit"),
        pytest.param("conelclearprofill", None, 1.0, id="no-unit"),
        pytest.param("allinoneplus", "3", 1.0, id="values-in-the-unit"),
        pytest.param("unknown", "3", 1.0, id="unknown-model"),
    ],
)
def test_hardness_factor(model: str, raw_code: Any, expected: float) -> None:
    """Only a device that keeps the water hardness in °dH converts it to the unit."""
    signature = _signature(model)

    assert signature.hardness_factor(raw_code) == expected
