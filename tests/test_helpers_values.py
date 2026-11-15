"""Tests for the status value helpers (helpers/values.py)."""

import logging
from typing import Any, cast

import pytest

from custom_components.syr_connect.aiosyrconnect import (
    SyrConnectStatus,
    SyrConnectStatusValue,
)
from custom_components.syr_connect.helpers.values import (
    build_set_ab_command,
    get_sensor_ab_value,
    get_sensor_avo_value,
    get_sensor_bat_value,
    get_sensor_iwh_value,
    get_sensor_lng_value,
    get_sensor_net_value,
    get_sensor_rtm_value,
    get_sensor_vol_value,
    is_empty_ip,
    set_sensor_rtm_value,
    to_float,
    to_int,
)


def test_get_sensor_rtm_and_set_additional() -> None:
    """Test get sensor rtm and set additional."""
    # Combined string representation
    status: SyrConnectStatus = {"getRTH": "", "getRTM": "07:30"}
    assert get_sensor_rtm_value(status) == "07:30"
    assert set_sensor_rtm_value(status, "08:15") == [("setRTM", "08:15")]

    # Separate numeric representation
    status = {"getRTH": "7", "getRTM": "30"}
    assert get_sensor_rtm_value(status) == "07:30"
    assert set_sensor_rtm_value(status, "09:45") == [
        ("setRTH", 9),
        ("setRTM", 45),
    ]

    # Invalid option
    assert set_sensor_rtm_value(status, "bad") == []


def test_get_sensor_ab_and_build_set_additional() -> None:
    """Test get sensor ab and build set additional."""
    assert get_sensor_ab_value(cast(Any, None)) is None
    assert get_sensor_ab_value({"getAB": True}) is True
    assert get_sensor_ab_value({"getAB": 2}) is True
    assert get_sensor_ab_value({"getAB": 1}) is False
    assert get_sensor_ab_value({"getAB": "true"}) is True
    assert get_sensor_ab_value({"getAB": "2"}) is True

    # build set command mirrors device format
    assert build_set_ab_command({"getAB": "true"}, False) == ("setAB", "false")
    assert build_set_ab_command({"getAB": True}, False) == ("setAB", "false")
    assert build_set_ab_command({"getAB": 1}, True) == ("setAB", 2)
    assert build_set_ab_command({"getAB": "1"}, True) == ("setAB", 2)


def test_get_sensor_avo_value() -> None:
    """Test flow value extraction from strings."""
    # Test standard format - values in mL converted to L
    assert get_sensor_avo_value("1655mL") == 1.655
    assert get_sensor_avo_value("0mL") == 0.0
    assert get_sensor_avo_value("999mL") == 0.999
    assert get_sensor_avo_value("1000mL") == 1.0

    # Test numeric inputs - treated as mL and converted to L
    assert get_sensor_avo_value(1655) == 1.655
    assert get_sensor_avo_value(0) == 0.0
    assert get_sensor_avo_value(100.5) == 0.1005

    # Test None input
    assert get_sensor_avo_value(None) is None

    # Test fallback: extract number at start and convert to L
    assert get_sensor_avo_value("1655") == 1.655
    assert get_sensor_avo_value("100abc") == 0.1

    # Test invalid inputs
    assert get_sensor_avo_value("mL") is None
    assert get_sensor_avo_value("abc") is None
    assert get_sensor_avo_value("") is None
    assert get_sensor_avo_value("no numbers here") is None


# Tests merged from test_clean_sensor_value.py
def test_clean_value_with_prefix() -> None:
    """Test cleaning value with prefix like 'Vol[L]6530'."""
    assert get_sensor_vol_value("Vol[L]6530") == "6530"
    assert get_sensor_vol_value("Temp[C]25") == "25"
    assert get_sensor_vol_value("Press[bar]48") == "48"


def test_clean_value_with_prefix_and_decimals() -> None:
    """Test cleaning value with prefix and decimal numbers."""
    assert get_sensor_vol_value("Vol[L]123.45") == "123.45"
    assert get_sensor_vol_value("Temp[C]25.5") == "25.5"


def test_clean_value_with_prefix_and_spaces() -> None:
    """Test cleaning value with prefix and extra spaces."""
    assert get_sensor_vol_value("Vol[L] 6530") == "6530"
    assert get_sensor_vol_value("Temp[C]  25") == "25"


def test_clean_value_numeric_passthrough() -> None:
    """Test that numeric values pass through unchanged."""
    assert get_sensor_vol_value(6530) == 6530
    assert get_sensor_vol_value(123.45) == 123.45
    assert get_sensor_vol_value(0) == 0


def test_clean_value_string_without_prefix() -> None:
    """Test that strings without prefix pass through unchanged."""
    assert get_sensor_vol_value("6530") == "6530"
    assert get_sensor_vol_value("123.45") == "123.45"
    assert get_sensor_vol_value("normal_string") == "normal_string"
    assert get_sensor_vol_value("") is None


def test_clean_value_complex_strings() -> None:
    """Test that complex strings without matching pattern pass through."""
    assert get_sensor_vol_value("Status: Active") == "Status: Active"
    assert get_sensor_vol_value("Error[123]") == "Error[123]"  # No value after bracket
    assert get_sensor_vol_value("Test") == "Test"


def test_get_sensor_bat_value_variants() -> None:
    """Test parsing of battery voltage in various formats."""
    # Safe-T+ multi-value -> take first token and parse comma as decimal
    assert get_sensor_bat_value("6,12 4,38 3,90") == 6.12

    # Safe-Tech+ single value with comma decimal
    assert get_sensor_bat_value("9,36") == 9.36

    # Digits-only Trio format -> divide by 100
    assert get_sensor_bat_value("363") == 3.63

    # Numeric input (int/float) assumed in 1/100 V -> divide
    assert get_sensor_bat_value(363) == 3.63
    assert get_sensor_bat_value(363.0) == 3.63

    # Empty or invalid -> None
    assert get_sensor_bat_value("") is None
    assert get_sensor_bat_value(None) is None
    assert get_sensor_bat_value("not-a-number") is None


def test_get_sensor_net_value_safe_t_plus_format() -> None:
    """Safe-T+ format: 'ADC:950 6,16V' -> 6.16."""
    assert get_sensor_net_value("ADC:950 6,16V") == 6.16


def test_get_sensor_net_value_safe_t_plus_format_lowercase_v() -> None:
    """Safe-T+ format with lowercase v is handled."""
    assert get_sensor_net_value("ADC:950 6,16v") == 6.16


def test_get_sensor_net_value_safe_tech_plus_format() -> None:
    """Safe-Tech+ format: '11,86' -> 11.86."""
    assert get_sensor_net_value("11,86") == 11.86


def test_get_sensor_net_value_trio_format() -> None:
    """Trio DFR/LS format: '363' -> 3.63."""
    assert get_sensor_net_value("363") == 3.63


def test_get_sensor_net_value_numeric_int() -> None:
    """Integer input assumed in 1/100 V -> divide by 100."""
    assert get_sensor_net_value(363) == 3.63


def test_get_sensor_iwh_returns_int_when_getiwh_int() -> None:
    """Test get sensor iwh returns int when getIWH int."""
    status: SyrConnectStatus = {"getIWH": 10, "getWHU": 0}
    assert get_sensor_iwh_value(status) == 10


def test_get_sensor_iwh_returns_float_when_getiwh_string_float() -> None:
    """Test get sensor iwh returns float when getIWH string float."""
    status: SyrConnectStatus = {"getIWH": "12.5", "getWHU": 0}
    assert get_sensor_iwh_value(status) == 12.5


def test_get_sensor_iwh_derived_from_getcnd_integer_result() -> None:
    """Test get sensor iwh derived from getCND integer result."""
    status: SyrConnectStatus = {"getCND": 540}
    # 540 / 35 == 15.428571... -> float
    assert get_sensor_iwh_value(status) == 540 / 35


def test_get_sensor_iwh_derived_from_getcnd_float_result() -> None:
    """Test get sensor iwh derived from getCND float result."""
    status: SyrConnectStatus = {"getCND": "378"}
    # 378 / 35 == 10.8 -> float
    assert get_sensor_iwh_value(status) == 378 / 35


def test_get_sensor_iwh_returns_none_on_invalid_getcnd() -> None:
    """Test get sensor iwh returns none on invalid getCND."""
    status: SyrConnectStatus = {"getCND": "not-a-number"}
    assert get_sensor_iwh_value(status) is None


def test_get_sensor_iwh_missing_both_returns_none() -> None:
    """Test get sensor iwh missing both returns none."""
    status: dict[str, Any] = {}
    assert get_sensor_iwh_value(status) is None


def test_get_sensor_iwh_whu_missing_defaults_to_zero_and_derive() -> None:
    """Test get sensor iwh whu missing defaults to zero and derive."""
    status: SyrConnectStatus = {"getCND": 300, "getWHU": ""}
    # 300 / 35 == 8.571428... -> float
    assert get_sensor_iwh_value(status) == 300 / 35


def test_get_sensor_iwh_derived_from_getcnd_zero() -> None:
    """Test get sensor iwh derived from getCND zero."""
    status: SyrConnectStatus = {"getCND": 0}
    # 0 / 35 == 0 -> int
    assert get_sensor_iwh_value(status) == 0


def test_get_sensor_iwh_derived_from_getcnd_empty_string() -> None:
    """Test get sensor iwh derived from getCND empty string."""
    status: SyrConnectStatus = {"getCND": ""}
    # empty string treated as missing -> None
    assert get_sensor_iwh_value(status) is None


def test_get_sensor_iwh_whu_key_missing_defaults_to_zero_and_derive() -> None:
    """Test get sensor iwh whu key missing defaults to zero and derive."""
    status: SyrConnectStatus = {"getCND": 30}
    # getWHU missing -> default 0; 30 / 35 == 0.857142... -> float
    assert get_sensor_iwh_value(status) == 30 / 35


def test_get_sensor_iwh_whu_invalid_string_defaults_to_zero_and_persists() -> None:
    """Invalid getWHU string should default to 0 and be persisted."""
    status: SyrConnectStatus = {"getCND": 300, "getWHU": "invalid"}
    result = get_sensor_iwh_value(status)
    assert result == 300 / 35
    # getWHU should have been normalized to 0
    assert status.get("getWHU") == 0


def test_get_sensor_iwh_whole_float_string_returns_int() -> None:
    """A getIWH text with a whole number ("12.0") is returned as int."""
    value = get_sensor_iwh_value({"getIWH": "12.0", "getWHU": 0})

    assert value == 12
    assert isinstance(value, int)


def test_get_sensor_iwh_invalid_getiwh_falls_back_to_derive() -> None:
    """If explicit getIWH is invalid but getCND exists, derive from getCND."""
    status: SyrConnectStatus = {"getIWH": "bad", "getWHU": 0, "getCND": 350}
    # Should fall back and compute 350 / 35 == 10
    assert get_sensor_iwh_value(status) == 10


def test_get_sensor_net_value_numeric_float() -> None:
    """Float input assumed in 1/100 V -> divide by 100."""
    assert get_sensor_net_value(363.0) == 3.63


def test_get_sensor_net_value_empty_string() -> None:
    """Empty string returns None."""
    assert get_sensor_net_value("") is None


def test_get_sensor_net_value_none() -> None:
    """None input returns None."""
    assert get_sensor_net_value(None) is None


def test_get_sensor_net_value_invalid_string() -> None:
    """Unrecognized string returns None."""
    assert get_sensor_net_value("not-a-number") is None


def test_get_sensor_net_value_non_str_non_numeric() -> None:
    """Non-string, non-numeric types return None."""
    assert get_sensor_net_value([1, 2, 3]) is None


def test_get_sensor_net_value_adc_format_no_v_token() -> None:
    """ADC: prefix present but no token ending in V returns None."""
    assert get_sensor_net_value("ADC:950 616") is None


def test_get_sensor_net_value_adc_format_unparseable_v_token() -> None:
    """ADC: prefix with non-numeric V token returns None."""
    assert get_sensor_net_value("ADC:950 badV") is None


def test_get_sensor_lng_value_with_annotation() -> None:
    """The getLNG value with trailing annotation is stripped to the leading integer."""
    assert get_sensor_lng_value("0 (0=Deutsch 1=English)") == "0"
    assert get_sensor_lng_value("1 (0=Deutsch 1=English)") == "1"


def test_get_sensor_lng_value_plain() -> None:
    """The getLNG plain integer string is returned unchanged."""
    assert get_sensor_lng_value("0") == "0"
    assert get_sensor_lng_value("1") == "1"


def test_get_sensor_lng_value_non_string() -> None:
    """Non-string values are returned as-is."""
    assert get_sensor_lng_value(0) == 0
    assert get_sensor_lng_value(1.0) == 1.0


def test_get_sensor_lng_value_empty() -> None:
    """Empty string returns None."""
    assert get_sensor_lng_value("") is None
    assert get_sensor_lng_value("  ") is None


def test_get_sensor_lng_value_non_integer_token() -> None:
    """Non-integer leading token returns the original value unchanged."""
    assert get_sensor_lng_value("unknown") == "unknown"


def test_get_sensor_rtm_and_setters() -> None:
    """Test parsing and building of regeneration time values."""

    # Combined representation: getRTM contains HH:MM
    status_combined: SyrConnectStatus = {"getRTM": "02:05", "getRTH": None}
    assert get_sensor_rtm_value(status_combined) == "02:05"

    # Separate numeric values
    status_sep: SyrConnectStatus = {"getRTH": "2", "getRTM": "30"}
    assert get_sensor_rtm_value(status_sep) == "02:30"

    # Invalid combined string
    status_bad: SyrConnectStatus = {"getRTM": "bad", "getRTH": None}
    assert get_sensor_rtm_value(status_bad) is None

    # set_sensor_rtm_value: combined mode should return single setRTM
    status_for_set: SyrConnectStatus = {"getRTH": None, "getRTM": "02:30"}
    cmds = set_sensor_rtm_value(status_for_set, "03:45")
    assert cmds == [("setRTM", "03:45")]

    # set_sensor_rtm_value: separate mode returns two commands
    status_for_set2: SyrConnectStatus = {"getRTH": "1", "getRTM": "15"}
    cmds2 = set_sensor_rtm_value(status_for_set2, "04:20")
    assert cmds2 == [("setRTH", 4), ("setRTM", 20)]


def test_get_sensor_ab_and_build_command(caplog: pytest.LogCaptureFixture) -> None:
    """Test parsing of getAB and building set commands."""

    # Numeric values
    assert get_sensor_ab_value({"getAB": 2}) is True
    assert get_sensor_ab_value({"getAB": 1}) is False

    # String boolean-like
    assert get_sensor_ab_value({"getAB": "true"}) is True
    assert get_sensor_ab_value({"getAB": "false"}) is False

    # Numeric string
    assert get_sensor_ab_value({"getAB": "2"}) is True

    # Invalid or missing
    assert get_sensor_ab_value({}) is None
    assert get_sensor_ab_value({"getAB": "x"}) is None

    # build_set_ab_command: prefer boolean-string if raw looks boolean
    assert build_set_ab_command({"getAB": "true"}, closed=True) == ("setAB", "true")
    assert build_set_ab_command({"getAB": "false"}, closed=True) == ("setAB", "true")
    assert build_set_ab_command({"getAB": True}, closed=False) == ("setAB", "false")
    assert build_set_ab_command({"getAB": False}, closed=True) == ("setAB", "true")
    # native integer (JSON API devices reporting getAB as int 1/2) → numeric
    assert build_set_ab_command({"getAB": 1}, closed=True) == ("setAB", 2)
    assert build_set_ab_command({"getAB": 1}, closed=False) == ("setAB", 1)
    assert build_set_ab_command({"getAB": 2}, closed=True) == ("setAB", 2)
    assert build_set_ab_command({"getAB": 2}, closed=False) == ("setAB", 1)
    # numeric string (XML API and some JSON API devices) → numeric
    assert build_set_ab_command({"getAB": "1"}, closed=True) == ("setAB", 2)
    assert build_set_ab_command({"getAB": "2"}, closed=False) == ("setAB", 1)
    # absent getAB key or explicit None → logs error and returns None
    with caplog.at_level(logging.ERROR, logger="custom_components.syr_connect.helpers"):
        result = build_set_ab_command({}, closed=True)
    assert result is None
    assert "unexpected getAB format" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.ERROR, logger="custom_components.syr_connect.helpers"):
        result2 = build_set_ab_command({"getAB": None}, closed=True)
    assert result2 is None
    assert "unexpected getAB format" in caplog.text


def test_get_sensor_ab_string_numeric_edge() -> None:
    """Cover numeric-string branch for getAB ('1' -> False)."""

    assert get_sensor_ab_value({"getAB": "1"}) is False


def test_get_sensor_ab_invalid_numeric_values() -> None:
    """Test that invalid numeric values (0, 3, etc.) return None.

    Valid values are 1 (open) and 2 (closed). Any other numeric value should return None.
    """
    # Test with int 0 (invalid value)
    assert get_sensor_ab_value({"getAB": 0}) is None

    # Test with int 3 (invalid value)
    assert get_sensor_ab_value({"getAB": 3}) is None

    # Test with other invalid int values
    assert get_sensor_ab_value({"getAB": 5}) is None
    assert get_sensor_ab_value({"getAB": 100}) is None

    # Test with numeric string invalid values
    assert get_sensor_ab_value({"getAB": "0"}) is None
    assert get_sensor_ab_value({"getAB": "3"}) is None
    assert get_sensor_ab_value({"getAB": "999"}) is None


def test_get_sensor_rtm_invalid_values() -> None:
    """Invalid RTM strings (out-of-range) should return None."""
    assert get_sensor_rtm_value({"getRTH": "", "getRTM": "24:00"}) is None
    assert get_sensor_rtm_value({"getRTH": "", "getRTM": "12:60"}) is None


def test_get_sensor_rtm_value_number_without_hour_returns_none() -> None:
    """Without getRTH only an "HH:MM" text is a time; a number in getRTM is none."""
    assert get_sensor_rtm_value({"getRTM": 1230}) is None


def test_get_sensor_bat_value_first_token_unparseable() -> None:
    """Test get sensor bat value first token unparsable."""
    # First token is non-numeric -> should return None
    assert get_sensor_bat_value("bad 4,38 3,90") is None


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("a,b", id="comma-without-number"),
        # str.isdigit() accepts superscript digits, int() does not
        pytest.param("²", id="superscript-digit"),
    ],
)
def test_get_sensor_net_and_bat_value_unparsable_text(value: str) -> None:
    """A text that only looks like a voltage gives no value."""
    assert get_sensor_net_value(value) is None
    assert get_sensor_bat_value(value) is None


def test_get_sensor_bat_value_non_str_non_numeric_returns_none() -> None:
    """Non-string, non-numeric types should return None."""
    assert get_sensor_bat_value([1, 2, 3]) is None


def test_get_sensor_ab_value_unexpected_type_returns_none() -> None:
    """An unexpected type for getAB should be handled and return None."""
    assert get_sensor_ab_value({"getAB": cast(Any, object())}) is None


def test_get_sensor_avo_value_non_string_non_numeric_returns_none() -> None:
    """Non-string, non-numeric types return None from get_sensor_avo_value (line 286)."""
    assert get_sensor_avo_value([1, 2]) is None
    assert get_sensor_avo_value({"v": 1}) is None


def test_set_sensor_rtm_value_empty_option_returns_empty() -> None:
    """set_sensor_rtm_value returns [] for empty/non-string option (line 521)."""
    assert set_sensor_rtm_value({}, "") == []
    assert set_sensor_rtm_value({}, None) == []  # type: ignore[arg-type]
    assert set_sensor_rtm_value({}, 123) == []  # type: ignore[arg-type]


def test_helpers_infinite_values_count_as_invalid() -> None:
    """Infinity cannot be converted to int (OverflowError) and counts as invalid."""
    assert get_sensor_rtm_value({"getRTH": "inf", "getRTM": "30"}) is None
    # An invalid getWHU defaults to 0
    assert get_sensor_iwh_value({"getCND": 300, "getWHU": "inf"}) == 300 / 35
    assert get_sensor_ab_value({"getAB": float("inf")}) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),
        ("", True),
        ("  ", True),
        ("0.0.0.0", True),
        ("::", True),
        (" 0.0.0.0 ", True),
        ("192.168.1.10", False),
        ("fe80::1", False),
        ("device.local", False),
        (0, False),
    ],
)
def test_is_empty_ip(value: Any, expected: Any) -> None:
    """Missing, blank and unspecified IP addresses count as empty."""
    assert is_empty_ip(value) is expected


@pytest.mark.parametrize(
    ("value", "expected_float", "expected_int"),
    [
        ("5", 5.0, 5),
        (7, 7.0, 7),
        (2.5, 2.5, 2),
        (True, 1.0, 1),
    ],
)
def test_to_float_and_to_int_convert_like_the_builtins(
    value: SyrConnectStatusValue, expected_float: float, expected_int: int
) -> None:
    """Text and numbers are converted like float() and int()."""
    assert to_float(value) == expected_float
    assert to_int(value) == expected_int


@pytest.mark.parametrize("value", [None, [1, 2], {"a": 1}])
def test_to_float_and_to_int_reject_values_that_are_no_number(
    value: SyrConnectStatusValue,
) -> None:
    """None, a list or an object raises TypeError, like float() and int()."""
    with pytest.raises(TypeError):
        to_float(value)
    with pytest.raises(TypeError):
        to_int(value)


def test_to_float_and_to_int_reject_text_that_is_no_number() -> None:
    """Text that is no number raises ValueError, like float() and int()."""
    with pytest.raises(ValueError):
        to_float("abc")
    with pytest.raises(ValueError):
        to_int("2.5")
