"""Tests for the visibility of sensors (sensor.is_sensor_visible)."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001

from custom_components.syr_connect import sensor
from custom_components.syr_connect.helpers.values import is_value_true
from custom_components.syr_connect.sensor import is_sensor_visible


def _keys_hidden_when(rule: str) -> set[str]:
    """Return the sensor keys whose description hides them for the given empty rule."""
    return {
        description.key
        for description in sensor._SYR_CONNECT_SENSOR_TYPES
        if description.hidden_when == rule
    }


def test_is_sensor_visible_group_control_and_cs_and_empty_ip() -> None:
    """Test group-controlled visibility, getCS1 at zero, and empty-IP exclusions."""
    # Group-controlled: getPA1 false -> getPV1 hidden
    status = {"getPA1": "0"}
    assert not is_sensor_visible(status, "getPV1", "1")

    # getCS1 visible at '0' without looking at getSV1
    assert is_sensor_visible({"getSV1": 0}, "getCS1", "0") is True

    # Empty-IP exclusion: pick a key from the exclusion set
    key_ip = next(iter(_keys_hidden_when("empty_ip")))
    assert is_sensor_visible({}, key_ip, "0.0.0.0") is False


def test_is_sensor_visible_empty_string_and_value_exclusions() -> None:
    """Test is sensor visible empty string and value exclusions."""
    # Use a key from the empty-string exclusion set
    key_es = next(iter(_keys_hidden_when("empty")))
    assert not is_sensor_visible({}, key_es, None)
    assert not is_sensor_visible({}, key_es, "   ")

    # Zero is a value, not an empty value: the sensor stays visible
    assert is_sensor_visible({}, key_es, 0)
    assert is_sensor_visible({}, key_es, 0.0)
    assert is_sensor_visible({}, key_es, "0")

    # Empty IP exclusion set
    key_ip = next(iter(_keys_hidden_when("empty_ip")))
    assert not is_sensor_visible({}, key_ip, None)
    assert not is_sensor_visible({}, key_ip, "   ")
    assert not is_sensor_visible({}, key_ip, "0.0.0.0")


def test_is_sensor_visible_group_pa_true_shows_group_keys() -> None:
    """If getPAx is truthy, related group keys should be visible."""
    status = {"getPA1": "1"}
    assert is_sensor_visible(status, "getPV1", "0") is True


def test_is_value_true_bool_value() -> None:
    """is_sensor_visible: is_value_true returns bool value directly (line 789)."""
    # Passing a boolean True for getPAx means the group key must be visible
    assert is_sensor_visible({"getPA1": True}, "getPV1", "1") is True
    assert is_sensor_visible({"getPA1": False}, "getPV1", "1") is False


def test_is_value_true_numeric_value() -> None:
    """is_sensor_visible: is_value_true handles int/float (lines 791-794)."""
    # Non-zero int -> True (PA is active, group key shown)
    assert is_sensor_visible({"getPA2": 1}, "getPV2", "1") is True
    # Zero int -> False
    assert is_sensor_visible({"getPA2": 0}, "getPV2", "1") is False
    # Float non-zero
    assert is_sensor_visible({"getPA3": 1.5}, "getPT3", "1") is True


def test_is_value_true_str_numeric_parse() -> None:
    """is_sensor_visible: is_value_true parses numeric strings (lines 801-805)."""
    # String "2" parses to non-zero -> True
    assert is_sensor_visible({"getPA1": "2"}, "getPV1", "1") is True
    # String "0.0" parses to zero -> False
    assert is_sensor_visible({"getPA1": "0.0"}, "getPV1", "1") is False
    # String "bad" can't parse -> False (except branch) -> group key hidden
    assert is_sensor_visible({"getPA1": "bad"}, "getPV1", "1") is False
    # Non-bool/int/float/str type -> is_value_true returns False -> key hidden
    assert is_sensor_visible({"getPA1": [1, 2]}, "getPV1", "1") is False


def test_is_value_true_infinity_returns_false() -> None:
    """Infinity cannot be converted to int (OverflowError) and counts as not true."""
    assert is_value_true(float("inf")) is False
    assert is_value_true(float("-inf")) is False
    assert is_value_true("inf") is False
    assert is_value_true(" -Infinity ") is False


# ---------------------------------------------------------------------------
# is_sensor_visible - getBAP firmware-bug suppression (lines 1077-1088)
# ---------------------------------------------------------------------------


def test_is_sensor_visible_getbap_suppressed_when_zero_and_bat_positive() -> None:
    """getBAP=0 with getBAT>0 is suppressed (firmware exposes spurious % field)."""
    assert is_sensor_visible({"getBAT": 4.5}, "getBAP", 0) is False


def test_is_sensor_visible_getbap_suppressed_when_string_zero_and_bat_positive() -> (
    None
):
    """getBAP='0' (string) with getBAT>0 is also suppressed."""
    assert is_sensor_visible({"getBAT": "3.7"}, "getBAP", "0") is False


def test_is_sensor_visible_getbap_not_suppressed_when_bat_absent() -> None:
    """getBAP=0 is visible when getBAT is not in status."""
    assert is_sensor_visible({}, "getBAP", 0) is True


def test_is_sensor_visible_getbap_not_suppressed_when_bat_zero() -> None:
    """getBAP=0 is visible when getBAT==0 (device runs on USB, no real voltage)."""
    assert is_sensor_visible({"getBAT": 0}, "getBAP", 0) is True


def test_is_sensor_visible_getbap_not_suppressed_when_bat_non_numeric() -> None:
    """getBAP=0 is visible when getBAT is non-numeric (ValueError branch → pass)."""
    assert is_sensor_visible({"getBAT": "n/a"}, "getBAP", 0) is True


def test_is_sensor_visible_getbap_suppressed_when_value_none_and_bat_positive() -> None:
    """getBAP=None triggers the TypeError branch; bap_zero=True → suppressed when getBAT>0."""
    assert is_sensor_visible({"getBAT": 4.5}, "getBAP", None) is False


def test_is_sensor_visible_getbap_suppressed_when_value_empty_string_and_bat_positive() -> (
    None
):
    """getBAP='' triggers the ValueError branch; bap_zero=True → suppressed when getBAT>0."""
    assert is_sensor_visible({"getBAT": 4.5}, "getBAP", "") is False


def test_is_sensor_visible_getbap_not_suppressed_when_nonzero_value() -> None:
    """getBAP=50 (non-zero) → bap_zero=False → not suppressed regardless of getBAT."""
    assert is_sensor_visible({"getBAT": 4.5}, "getBAP", 50) is True
