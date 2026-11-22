"""Tests for the water hardness units (units.py)."""

import pytest

from custom_components.syr_connect.aiosyrconnect.units import (
    WHU_FACTORS_FROM_DH,
    WHU_UNITS_LEX,
    WHU_UNITS_MUCO,
    WHU_UNITS_NEOSOFT,
    round_hardness,
)


def test_every_unit_of_a_family_in_dh_has_a_factor() -> None:
    """The MuCo keeps °dH; every unit of its table can be converted."""
    assert set(WHU_UNITS_MUCO.values()) <= set(WHU_FACTORS_FROM_DH)


def test_unit_tables_start_with_dh() -> None:
    """Code 0 is °dH in every family."""
    for table in (WHU_UNITS_LEX, WHU_UNITS_MUCO, WHU_UNITS_NEOSOFT):
        assert table[0] == "°dH"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, 0),
        (4.48, 4),
        (2.5, 3),
        (3.5, 4),
    ],
)
def test_round_hardness(value: float, expected: int) -> None:
    """A converted water hardness is rounded to a whole number, halves up."""
    assert round_hardness(value) == expected
