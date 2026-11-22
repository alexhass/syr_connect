"""Tests for the model signatures and their detection (model_detection.py)."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.syr_connect.aiosyrconnect.model_detection import (
    MODEL_SIGNATURES,
    UNKNOWN_MODEL_SIGNATURE,
    detect_model_signature,
)
from custom_components.syr_connect.aiosyrconnect.models import SyrConnectModelSignature
from custom_components.syr_connect.aiosyrconnect.values import WHU_FACTORS_FROM_DH
from custom_components.syr_connect.aiosyrconnect.xml_parser import ResponseParser

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def _signature(
    name: str, dk: int | None = None, dkv: int | None = None, **checks: Any
) -> SyrConnectModelSignature:
    """Return a synthetic signature without device kind unless one is given."""
    return SyrConnectModelSignature(
        base_path=None,
        display_name=name,
        dk=dk,
        dkv=dkv,
        manufacturer="Test",
        name=name,
        **checks,
    )


def test_model_signature_names_are_unique() -> None:
    """Every signature has its own name; a duplicate would never be detected."""
    names = [signature.name for signature in MODEL_SIGNATURES]
    assert sorted(name for name in set(names) if names.count(name) > 1) == []


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("ConelClearProFill_GetDeviceCollectionStatus.xml", "conelclearprofill"),
        (
            "ConelClearProLeakProtection_GetDeviceCollectionStatus.xml",
            "conelclearproleakprotection",
        ),
        (
            "SanibelLeakProtectionModuleA25_GetDeviceCollectionStatus.xml",
            "sanibelleakprotect",
        ),
        ("SanibelSoftwaterUNOA25_GetDeviceCollectionStatus.xml", "sanibelsoftwateruno"),
        ("SyrAllInOnePlus_GetDeviceCollectionStatus.xml", "allinoneplus"),
        ("SyrL20_GetDeviceCollectionStatus.xml", "l20"),
        ("SyrLEX30_GetDeviceCollectionStatus.xml", "lex30"),
        ("SyrLEXplus10SL_GetDeviceCollectionStatus.xml", "lexplus10sl"),
        ("SyrLEXplus10S_GetDeviceCollectionStatus.xml", "lexplus10s"),
        ("SyrNeoSoft2500_GetDeviceCollectionStatus.xml", "neosoft2500"),
        ("SyrNeoSoft5000_GetDeviceCollectionStatus.xml", "neosoft5000"),
        ("SyrSafeFloor_GetDeviceCollectionStatus.xml", "safefloor"),
        ("SyrSafeTPlus_GetDeviceCollectionStatus.xml", "safetplus"),
        ("SyrSafeTechPlus_GetDeviceCollectionStatus.xml", "safetechplus"),
        ("SyrSafeTechV4_GetDeviceCollectionStatus.xml", "safetechv4"),
        ("SyrTrioDFRLS_GetDeviceCollectionStatus.xml", "trio"),
        ("SyrTrioLock_GetDeviceCollectionStatus.xml", "syrtriolockconnect"),
    ],
)
def test_cloud_fixture_is_detected_from_its_status(fixture: str, expected: str) -> None:
    """The status of every cloud fixture alone detects its model."""
    xml = (_FIXTURE_DIR / "xml" / fixture).read_text(encoding="utf-8")
    status = ResponseParser().parse_device_status_response(xml)

    signature = detect_model_signature(status, MODEL_SIGNATURES)

    assert signature is not None
    assert signature.name == expected


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("ConelClearProFill_get_all.json", "conelclearprofill"),
        ("ConelClearProLeakProtection.json", "conelclearproleakprotection"),
        ("ConelClearProSoft_get_all.json", "conelclearprosoft"),
        ("HansgrohePontosBase_get_all.json", "pontosbase"),
        ("SanibelLeakProtectionModuleA25_get_all.json", "sanibelleakprotect"),
        ("SanibelSoftwaterUNOA25_get_all.json", "sanibelsoftwateruno"),
        ("SyrAllInOnePlus_get_all.json", "allinoneplus"),
        ("SyrNeoSoft2500_get_all.json", "neosoft2500"),
        ("SyrNeoSoft5000_get_all.json", "neosoft5000"),
        ("SyrSafeTechPlus_get_all.json", "safetechplus"),
        ("SyrSafeTechV3_get_all.json", "safetechv3"),
        ("SyrSafeTechV4_get_all.json", "safetechv4"),
        ("SyrSafeTechV4_old_get_all.json", "safetechv4"),
        ("SyrSafeTech_get_all.json", "safetech"),
        ("SyrTrioDFRLS_get_all.json", "trio"),
        ("SyrTrioLock_get_all.json", "syrtriolockconnect"),
    ],
)
def test_local_fixture_is_detected_from_its_status(fixture: str, expected: str) -> None:
    """The local status (/get/all) of every JSON fixture detects its model."""
    status = json.loads((_FIXTURE_DIR / "json" / fixture).read_text(encoding="utf-8"))

    signature = detect_model_signature(status, MODEL_SIGNATURES)

    assert signature is not None
    assert signature.name == expected


def test_device_kind_of_cloud_fixtures_detects_the_model_of_the_status() -> None:
    """For every cloud fixture with a device list, the device kind detects the same model."""
    parser = ResponseParser()
    checked = 0
    for list_file in sorted(
        (_FIXTURE_DIR / "xml").glob("*_GetProjectDeviceCollections.xml")
    ):
        status_file = list_file.with_name(
            list_file.name.replace(
                "_GetProjectDeviceCollections.xml", "_GetDeviceCollectionStatus.xml"
            )
        )
        if not status_file.exists():
            continue
        devices = parser.parse_device_list_response(
            list_file.read_text(encoding="utf-8")
        )
        status = parser.parse_device_status_response(
            status_file.read_text(encoding="utf-8")
        )
        by_status = detect_model_signature(status, MODEL_SIGNATURES)
        assert by_status is not None, status_file.name
        # The device list may hold other devices of the project, too
        device = next(d for d in devices if d.get("dk") == by_status.dk)
        by_kind = detect_model_signature(
            status,
            MODEL_SIGNATURES,
            dk=device.get("dk"),
            dkv=device.get("dkv"),
            sbt=device.get("sbt"),
        )
        assert by_kind is by_status, list_file.name
        checked += 1
    assert checked >= 9


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

    model = _Model(
        base_path=None,
        display_name="Own",
        dk=2,
        dkv=3,
        label="Own model",
        manufacturer="Test",
        name="own",
    )

    assert detect_model_signature({}, [model], dk=2, dkv=3) is model


@pytest.mark.parametrize(
    ("alarm_style_alm", "alarm_clear_via_set", "key", "cloud", "device"),
    [
        (False, False, "getALA", ("clrALA", ""), ("clrALA", "")),
        (True, False, "getALM", ("clrALM", ""), ("clrALM", "")),
        (False, True, "getALA", ("setALA", "FF"), ("setALA", 255)),
        (True, True, "getALM", ("setALM", "FF"), ("setALM", 255)),
    ],
)
def test_alarm_status_key_and_reset_command(
    alarm_style_alm: bool,
    alarm_clear_via_set: bool,
    key: str,
    cloud: tuple[str, str | int],
    device: tuple[str, str | int],
) -> None:
    """The alarm style gives the status key, the clear method the reset command.

    A set command takes the clear value of the client: "FF" for the cloud,
    255 for the device. A clr command has no value.
    """
    signature = _signature(
        "alarm",
        alarm_style_alm=alarm_style_alm,
        alarm_clear_via_set=alarm_clear_via_set,
    )

    assert signature.alarm_status_key == key
    assert signature.alarm_reset_command("FF") == cloud
    assert signature.alarm_reset_command(255) == device


def test_branded_returns_the_branding_of_the_service() -> None:
    """A cloud service with a branding of its own names the model its way."""
    signature = _signature(
        "branded",
        service_branding={"vendor.service": ("Vendor", "Vendor Name")},
    )

    assert signature.branded("vendor.service") == ("Vendor", "Vendor Name")
    assert signature.branded("other.service") == ("Test", "branded")
    # The local JSON API has no cloud service
    assert signature.branded(None) == ("Test", "branded")


def test_branded_without_branding_returns_the_default() -> None:
    """Without a branding every service gets the manufacturer and the display name."""
    signature = _signature("plain")

    assert signature.branded("vendor.service") == ("Test", "plain")


def test_safefloor_is_branded_per_cloud_service() -> None:
    """The SafeFloor (dk 120/dkv 34) is sold under other names by other services."""
    safefloor = next(sig for sig in MODEL_SIGNATURES if sig.name == "safefloor")

    assert safefloor.branded("de.consoft.gc.conel.connect") == (
        "CONEL",
        "CLEAR PRO Floor Sensor",
    )
    assert safefloor.branded("de.consoft.syr.connect") == ("SYR", "SafeFloor Connect")


def test_unknown_model_signature_is_never_detected() -> None:
    """The unknown signature names an unknown model and is not one of the signatures."""
    assert UNKNOWN_MODEL_SIGNATURE.name == "unknown"
    assert UNKNOWN_MODEL_SIGNATURE.base_path is None
    assert UNKNOWN_MODEL_SIGNATURE.branded(None) == ("Unknown", "Unknown model")
    assert UNKNOWN_MODEL_SIGNATURE not in MODEL_SIGNATURES
    assert all(sig.name != "unknown" for sig in MODEL_SIGNATURES)
    assert UNKNOWN_MODEL_SIGNATURE.ala_codes is None
    assert UNKNOWN_MODEL_SIGNATURE.not_codes is None
    assert UNKNOWN_MODEL_SIGNATURE.wrn_codes is None


def test_every_signature_names_the_alarm_codes_of_its_family() -> None:
    """Every known model has the alarm code table of its family."""
    assert [sig.name for sig in MODEL_SIGNATURES if sig.ala_codes is None] == []


def test_water_hardness_units_of_models_in_dh_can_be_converted() -> None:
    """A model that keeps the hardness in °dH has a factor for every unit of getWHU."""
    for sig in MODEL_SIGNATURES:
        if sig.hardness_in_dh:
            assert sig.whu_units is not None, sig.name
            assert set(sig.whu_units.values()) <= set(WHU_FACTORS_FROM_DH), sig.name


def test_hardness_divisors_belong_to_units_of_the_model() -> None:
    """A hardness divisor applies to a getWHU code of the model."""
    for sig in MODEL_SIGNATURES:
        if sig.hardness_divisors:
            assert sig.whu_units is not None, sig.name
            assert set(sig.hardness_divisors) <= set(sig.whu_units), sig.name


def test_statistics_series_are_unique() -> None:
    """Every measurement history series of a model reads another key."""
    for sig in MODEL_SIGNATURES:
        keys = [statistic.key for statistic in sig.statistics]
        assert len(keys) == len(set(keys)), sig.name


def test_safefloor_reports_temperature_and_humidity_history() -> None:
    """The SafeFloor signatures name the series the cloud keeps."""
    safefloors = [sig for sig in MODEL_SIGNATURES if sig.name.startswith("safefloor")]
    assert safefloors
    for sig in safefloors:
        assert [statistic.key for statistic in sig.statistics] == ["getCEL", "getHMD"]
        assert sig.bat_in_percent is True
