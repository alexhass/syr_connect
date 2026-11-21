"""Tests for the model signatures and their detection (model_detection.py)."""

from dataclasses import dataclass
from typing import Any

import pytest

from custom_components.syr_connect.aiosyrconnect.model_detection import (
    MODEL_SIGNATURES,
    detect_model_signature,
)
from custom_components.syr_connect.aiosyrconnect.models import SyrConnectModelSignature


def _signature(
    name: str, dk: int | None = None, dkv: int | None = None, **checks: Any
) -> SyrConnectModelSignature:
    """Return a synthetic signature without device kind unless one is given."""
    return SyrConnectModelSignature(base_path=None, dk=dk, dkv=dkv, name=name, **checks)


def test_model_signature_names_are_unique() -> None:
    """Every signature has its own name; a duplicate would never be detected."""
    names = [signature.name for signature in MODEL_SIGNATURES]
    assert sorted(name for name in set(names) if names.count(name) > 1) == []


def test_device_kind_family_of_one_is_the_result() -> None:
    """A device kind with one signature needs no status checks."""
    signatures = [
        _signature("other", dk=1, dkv=1),
        _signature("kind", dk=2, dkv=3),
    ]

    assert detect_model_signature({}, signatures, dk=2, dkv=3) is signatures[1]


def test_status_decides_within_the_family() -> None:
    """In a family of several signatures, only its signatures are checked."""
    signatures = [
        _signature("outside", cna_equals="X"),
        _signature("small", dk=2, dkv=3, cna_equals="S"),
        _signature("large", dk=2, dkv=3, cna_equals="X"),
    ]

    result = detect_model_signature({"getCNA": "X"}, signatures, dk=2, dkv=3)

    assert result is signatures[2]


def test_subtype_and_role_narrow_the_family() -> None:
    """A signature with sbt or dfm only matches a device with that subtype or role."""
    signatures = [
        _signature("sbt1", dk=2, dkv=3, sbt=1),
        _signature("sbt2", dk=2, dkv=3, sbt=2),
        _signature("role1", dk=4, dkv=5, dfm=1),
        _signature("role2", dk=4, dkv=5, dfm=2),
    ]

    assert detect_model_signature({}, signatures, dk=2, dkv=3, sbt=2) is signatures[1]
    # getDFM is text in the cloud status and a number in the local status
    for dfm in ("2", 2):
        result = detect_model_signature({"getDFM": dfm}, signatures, dk=4, dkv=5)
        assert result is signatures[3]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        # The serial number wins over getCNA and getVER
        ({"getSRN": "77AAA1", "getCNA": "C", "getVER": "V1"}, "srn"),
        ({"getSRN": "77BBB1", "getCNA": "C", "getVER": "V1"}, "cna"),
        ({"getVER": "V1.2 Floor"}, "ver"),
        # ver_prefix and ver_contains must both match
        ({"getVER": "V1.2"}, None),
        ({"getVER": "X Floor"}, None),
    ],
)
def test_status_checks_in_order(status: dict[str, str], expected: str | None) -> None:
    """Without a device kind, serial number, getCNA and getVER decide, in this order."""
    signatures = [
        _signature("ver", ver_prefix="V1", ver_contains="Floor"),
        _signature("cna", cna_equals="C"),
        _signature("srn", srn_prefix="77"),
    ]

    result = detect_model_signature(status, signatures)

    assert (result.name if result else None) == expected


def test_no_status_no_match() -> None:
    """A status that is no dict, or matches no signature, detects nothing."""
    signatures = [_signature("cna", cna_equals="C")]

    assert detect_model_signature(None, signatures) is None
    assert detect_model_signature({"getCNA": "D"}, signatures) is None


def test_signatures_of_the_caller_are_returned() -> None:
    """The caller may pass its own subclass of the signature and gets it back."""

    @dataclass(frozen=True, kw_only=True)
    class _Model(SyrConnectModelSignature):
        label: str

    model = _Model(base_path=None, dk=2, dkv=3, name="own", label="Own model")

    assert detect_model_signature({}, [model], dk=2, dkv=3) is model


@pytest.mark.parametrize(
    ("alarm_style_alm", "alarm_clear_via_set", "key", "command"),
    [
        (False, False, "getALA", ("clrALA", "")),
        (True, False, "getALM", ("clrALM", "")),
        (False, True, "getALA", ("setALA", "FF")),
        (True, True, "getALM", ("setALM", "FF")),
    ],
)
def test_alarm_status_key_and_reset_command(
    alarm_style_alm: bool,
    alarm_clear_via_set: bool,
    key: str,
    command: tuple[str, str],
) -> None:
    """The alarm style gives the status key, the clear method the reset command."""
    signature = _signature(
        "alarm",
        alarm_style_alm=alarm_style_alm,
        alarm_clear_via_set=alarm_clear_via_set,
    )

    assert signature.alarm_status_key == key
    assert signature.alarm_reset_command == command
