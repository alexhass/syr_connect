"""Tests for the alarm, notification and warning codes (codes.py)."""

import pytest

from custom_components.syr_connect.aiosyrconnect.codes import (
    NO_CODE_VALUES,
    is_code_active,
)


@pytest.mark.parametrize(
    "value",
    [None, "", " ", "0", "00", "FF", "ff", " ff ", "A0X0000", "a0x0000", "255", 255, 0],
)
def test_no_code(value: object) -> None:
    """None and the values of NO_CODE_VALUES, in any case and padding, are no code."""
    assert is_code_active(value) is False


@pytest.mark.parametrize("value", ["01", "0D", "A5", "FE", 1, 13, "A0X0001"])
def test_active_code(value: object) -> None:
    """Every other value is an active code."""
    assert is_code_active(value) is True


def test_no_code_values_are_normalized() -> None:
    """The values are compared after strip().upper(), so they are stored that way."""
    assert all(value == value.strip().upper() for value in NO_CODE_VALUES)
