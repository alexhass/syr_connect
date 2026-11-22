"""Tests for the allowed values of the settings (settings.py)."""

from dataclasses import replace

import pytest

from custom_components.syr_connect.aiosyrconnect.model_detection import (
    MODEL_SIGNATURES,
    UNKNOWN_MODEL_SIGNATURE,
)
from custom_components.syr_connect.aiosyrconnect.settings import (
    FLUSHING_TEMPERATURE_GAP,
    FLUSHING_TEMPERATURE_RANGES,
    SETTING_OFF_VALUES,
    SETTING_VALUES,
)


@pytest.mark.parametrize("key", sorted(SETTING_VALUES))
def test_setting_values_are_ascending_and_unique(key: str) -> None:
    """The raw values of a setting are in ascending order, each once."""
    values = list(SETTING_VALUES[key])
    assert values
    assert values == sorted(set(values)), key


@pytest.mark.parametrize("key", sorted(SETTING_OFF_VALUES))
def test_off_values_are_outside_the_range(key: str) -> None:
    """The value that switches a setting off is none of its other values."""
    assert SETTING_OFF_VALUES[key] not in SETTING_VALUES[key]


def test_values_of_the_models_are_ascending_and_unique() -> None:
    """The values a model names for a setting are in ascending order, each once."""
    for sig in MODEL_SIGNATURES:
        for key, values in sig.setting_values.items():
            assert list(values) == sorted(set(values)), (sig.name, key)
        for key, value in sig.setting_off_values.items():
            allowed = sig.allowed_values(key)
            assert allowed is not None, (sig.name, key)
            assert value not in allowed, (sig.name, key)


def test_allowed_values_of_the_model_replace_the_defaults() -> None:
    """A model's own values replace the values of `SETTING_VALUES`."""
    sig = replace(
        UNKNOWN_MODEL_SIGNATURE,
        setting_values={
            "getRMT": [5, 10],
        },
    )
    assert sig.allowed_values("getRMT") == [5, 10]
    assert sig.allowed_values("getRVT") is SETTING_VALUES["getRVT"]
    assert sig.allowed_values("getXYZ") is None


def test_off_value_of_the_model_replaces_the_default() -> None:
    """A model's own off value replaces the value of `SETTING_OFF_VALUES`."""
    sig = replace(
        UNKNOWN_MODEL_SIGNATURE,
        setting_off_values={
            "getCCF": 0,
            "getMIT": -500,
        },
    )
    assert sig.off_value("getCCF") == 0
    assert sig.off_value("getMIT") == -500
    assert sig.off_value("getMXT") == SETTING_OFF_VALUES["getMXT"]
    assert sig.off_value("getRMT") is None


def test_flushing_temperature_ranges_leave_room_for_the_gap() -> None:
    """Start and stop temperature of every water type can keep the smallest distance."""
    for low, high in FLUSHING_TEMPERATURE_RANGES.values():
        assert high - low >= FLUSHING_TEMPERATURE_GAP


def test_hardness_ranges_are_valid() -> None:
    """Every hardness range of a model is (lowest, highest, step) with lowest <= highest."""
    for sig in MODEL_SIGNATURES:
        for key, ranges in sig.hardness_ranges.items():
            assert sig.whu_units is not None, sig.name
            assert set(ranges) <= set(sig.whu_units), (sig.name, key)
            for lowest, highest, step in ranges.values():
                assert lowest <= highest, (sig.name, key)
                assert step >= 1, (sig.name, key)
