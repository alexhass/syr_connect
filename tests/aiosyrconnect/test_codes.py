"""Tests for the alarm, notification and warning codes (codes.py)."""

from collections.abc import Mapping
import re

import pytest

from custom_components.syr_connect.aiosyrconnect import codes
from custom_components.syr_connect.aiosyrconnect.codes import (
    NO_CODE_VALUES,
    is_code_active,
)

# The code tables of the module: every Mapping constant named *_CODES_*.
_CODE_TABLES = {
    name: value
    for name, value in vars(codes).items()
    if "_CODES_" in name and isinstance(value, Mapping)
}


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


def test_code_tables_are_found() -> None:
    """The alarm, notification and warning tables of every family are checked."""
    assert sorted(_CODE_TABLES) == [
        "ALA_CODES_ALLINONEPLUS",
        "ALA_CODES_COMMON",
        "ALA_CODES_DOSINGPUMP",
        "ALA_CODES_HVA",
        "ALA_CODES_HYGBOX",
        "ALA_CODES_HYGIENEMODULE",
        "ALA_CODES_LEX",
        "ALA_CODES_LEXPLUS10SL",
        "ALA_CODES_SAFEFLOOR",
        "ALA_CODES_SAFETECH",
        "ALA_CODES_SAFETPLUS",
        "NOT_CODES_COMMON",
        "NOT_CODES_NONE",
        "WRN_CODES_COMMON",
        "WRN_CODES_NONE",
    ]


@pytest.mark.parametrize("name", sorted(_CODE_TABLES))
def test_code_table_keys_are_normalized(name: str) -> None:
    """The caller looks codes up after strip().upper(), so the keys are stored that way."""
    table = _CODE_TABLES[name]
    assert all(code == code.strip().upper() for code in table), name


@pytest.mark.parametrize("name", sorted(_CODE_TABLES))
def test_code_table_meanings_are_keys(name: str) -> None:
    """Every meaning is a lowercase key that the caller can translate."""
    table = _CODE_TABLES[name]
    assert all(re.fullmatch(r"[a-z0-9_]+", key) for key in table.values()), name
