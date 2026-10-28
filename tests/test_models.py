"""Tests for the model detection."""

from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.syr_connect.devices import muco_triolock
from custom_components.syr_connect.models import (
    MODEL_SIGNATURES,
    UNKNOWN_MODEL,
    detect_model,
)
from custom_components.syr_connect.response_parser import ResponseParser

FIXTURE_DIR = Path(__file__).parent / "fixtures/xml"


def _load_xml(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_lexplus10_detection_synthetic() -> None:
    """Synthetic flattened dict with getCNA should detect lexplus10."""
    flat = {"getCNA": "LEXplus10"}
    assert detect_model(flat).name == "lexplus10"
    assert detect_model(flat).manufacturer == "SYR"


def test_lexplus10s_detection() -> None:
    """Test lexplus10s detection."""
    xml = _load_xml("SyrLEXplus10S_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat).name == "lexplus10s"
    assert detect_model(flat).manufacturer == "SYR"


def test_lexplus10sl_detection() -> None:
    """Test lexplus10sl detection."""
    xml = _load_xml("SyrLEXplus10SL_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat).name == "lexplus10sl"
    assert detect_model(flat).manufacturer == "SYR"


def test_neosoft2500_detection() -> None:
    """Test neosoft2500 detection."""
    xml = _load_xml("SyrNeoSoft2500_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat).name == "neosoft2500"
    assert detect_model(flat).manufacturer == "SYR"


def test_neosoft5000_detection() -> None:
    """Test neosoft5000 detection."""
    xml = _load_xml("SyrNeoSoft5000_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat).name == "neosoft5000"
    assert detect_model(flat).manufacturer == "SYR"


def test_syrtriolockconnect_detection() -> None:
    """SYR TRIO Lock Connect (dkv=506, getDFM=5) detected via real fixture."""
    xml = _load_xml("SyrTrioLock_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    result = detect_model(flat)
    assert result.name == "syrtriolockconnect"
    assert result.device_profile is muco_triolock.PROFILE
    assert result.manufacturer == "SYR"


def test_trio_dfrls_detection() -> None:
    """Test trio dfrls detection."""
    xml = _load_xml("SyrTrioDFRLS_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat).name == "trio"
    assert detect_model(flat).manufacturer == "SYR"


def test_safetplus_detection() -> None:
    """Test safetplus detection."""
    xml = _load_xml("SyrSafeTPlus_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat).name == "safetplus"
    assert detect_model(flat).manufacturer == "SYR"


def test_unknown_model_detection() -> None:
    """Unknown or empty flattened dict should yield the unknown fallback."""
    result = detect_model({})
    assert result.name == "unknown"
    assert result.manufacturer == "Unknown"


def test_detect_model_none_input() -> None:
    """Passing a non-dict (None) returns the unknown model dict."""
    result = detect_model(None)
    assert result.name == "unknown"
    assert result.display_name == "Unknown model"
    assert result.manufacturer == "Unknown"
    assert result.base_path is None


def test_safetechplus_detection_synthetic() -> None:
    """Safe-Tech+ should be detected by ver_prefix 'Safe-Tech'."""
    flat = {"getSRN": "112AAA00001", "getVER": "Safe-Tech-1.2.3"}
    result = detect_model(flat)
    assert result.name == "safetechplus"
    assert result.display_name == "SafeTech Plus Connect"
    assert result.manufacturer == "SYR"


def test_branded_returns_service_branding() -> None:
    """A service with its own branding returns its manufacturer and display name."""
    model = replace(
        UNKNOWN_MODEL,
        display_name="Default Name",
        manufacturer="Default",
        service_branding={
            "vendor.service": ("Vendor", "Vendor Name"),
        },
    )
    assert model.branded("vendor.service") == ("Vendor", "Vendor Name")
    assert model.branded("other.service") == ("Default", "Default Name")
    assert model.branded(None) == ("Default", "Default Name")


def test_branded_without_service_branding_returns_default() -> None:
    """A model without branding always returns its default names."""
    model = replace(UNKNOWN_MODEL, display_name="Default Name", manufacturer="Default")
    assert model.branded("vendor.service") == ("Default", "Default Name")


def test_safefloor_vendor_branding() -> None:
    """The SafeFloor sold by other vendors is named after their cloud service."""
    result = detect_model({"getVER": "Syr Floorsensor 2.23"})
    assert result.name == "safefloor"
    assert result.branded("de.consoft.gc.conel.connect") == (
        "CONEL",
        "CLEAR PRO Floor Sensor",
    )
    assert result.branded("de.consoft.gsh.comfort.connect") == (
        "Sanibel",
        "Wireless Floor Sensor A25",
    )
    assert result.branded("de.consoft.isg.concept.connect") == (
        "CONCEPT",
        "concept SafeFloor Floor Sensor",
    )
    assert result.branded("de.consoft.isg.optima.connect") == (
        "OPTIMA",
        "Optima T2 Floor Sensor",
    )
    assert result.branded("de.consoft.polygonvatro.connect") == (
        "POLYGONVATRO",
        "Wireless Floor Sensor",
    )
    assert result.branded("de.consoft.sanitaerunion.ditech.connect") == (
        "DITECH",
        "Ditech Wireless Floor Sensor",
    )
    assert result.branded("de.consoft.syr.connect") == ("SYR", "SafeFloor Connect")


def test_lexplus10_with_display_name_and_base_path() -> None:
    """Verify display_name, base_path, and manufacturer are returned correctly."""
    flat = {"getCNA": "LEXplus10"}
    result = detect_model(flat)
    assert result.name == "lexplus10"
    assert result.display_name == "LEX Plus 10 Connect"
    assert result.base_path is None
    assert result.manufacturer == "SYR"


def test_getcna_none_converted_to_empty_string() -> None:
    """The getCNA of None should be safely converted to empty string."""
    flat = {"getSRN": "112AAA12345", "getCNA": None, "getVER": "Safe-Tech-1"}
    result = detect_model(flat)
    # Should still detect by version
    assert result.name == "safetechplus"


def test_getver_none_converted_to_empty_string() -> None:
    """The getVER of None should be safely converted to empty string."""
    flat = {"getCNA": "LEXplus10", "getVER": None}
    result = detect_model(flat)
    # Should still detect by getCNA
    assert result.name == "lexplus10"


def test_both_getcna_and_getver_none() -> None:
    """Both getCNA and getVER None should not cause errors."""
    flat = {"getCNA": None, "getVER": None}
    result = detect_model(flat)
    assert result.name == "unknown"


def test_non_dict_input_returns_unknown() -> None:
    """Non-dict inputs like string or list should return the unknown model dict."""
    for invalid in ("not a dict", [1, 2, 3], 123):
        result = detect_model(invalid)
        assert result.name == "unknown"
        assert result.display_name == "Unknown model"
        assert result.manufacturer == "Unknown"
        assert result.base_path is None


def test_ver_contains_synthetic() -> None:
    """Test signature matching with ver_contains attribute."""
    # Create a synthetic signature scenario where ver_contains is used
    # Since no real signature uses it, we test the version_match logic
    flat = {"getVER": "some-Safe-version-text"}
    # This won't match Safe-Tech (requires prefix), but tests the ver_contains code path
    result = detect_model(flat)
    # Should be unknown since no signature with ver_contains matches
    assert result.name == "unknown"


def test_signature_priority_first_match_wins() -> None:
    """When multiple signatures could match, first one wins."""
    # LEXplus10S has exact getCNA match, should win even if other conditions exist
    flat = {"getCNA": "LEXplus10S", "getVER": "NSS.V.2.36"}
    result = detect_model(flat)
    assert result.name == "lexplus10s"


def test_neosoft5000_serial_prefix_detection() -> None:
    """The NeoSoft 5000 is detected by its serial number prefix (dkv=200)."""
    flat = {"getSRN": "200AAA12345", "getVER": "NSS.V.2.36"}
    result = detect_model(flat)
    assert result.name == "neosoft5000"
    assert result.display_name == "NeoSoft 5000 Connect"


def test_version_match_prefix_only() -> None:
    """Test version matching with only ver_prefix."""
    flat = {"getVER": "Safe-T+ V2.00e"}
    result = detect_model(flat)
    assert result.name == "safetplus"


def test_version_match_prefix_mismatch() -> None:
    """Version prefix mismatch should skip signature."""
    flat = {"getAFW": "1", "getVER2": "176", "getVER": "wrong-prefix"}
    result = detect_model(flat)
    assert result.name == "unknown"


def test_empty_flat_dict_returns_unknown() -> None:
    """Empty dict with no keys should return unknown."""
    result = detect_model({})
    assert result.name == "unknown"
    assert result.display_name == "Unknown model"
    assert result.base_path is None


def test_unknown_model_has_correct_structure() -> None:
    """Unknown model return should be the UNKNOWN_MODEL signature."""
    flat = {"getSomeRandomKey": "value"}
    result = detect_model(flat)
    assert result is UNKNOWN_MODEL
    assert result.name == "unknown"


def test_multiple_keys_with_no_signature_match() -> None:
    """Dict with many keys but no signature match should return unknown."""
    flat = {
        "getXYZ": "1",
        "getABC": "2",
        "getDEF": "BUTT",
        "getVER": "unknown-version",
    }
    result = detect_model(flat)
    assert result.name == "unknown"


def test_lexplus10sl_with_exact_cna() -> None:
    """LEXplus10SL exact CNA match should detect correctly."""
    flat = {"getCNA": "LEXplus10SL"}
    result = detect_model(flat)
    assert result.name == "lexplus10sl"


def test_neosoft_base_path() -> None:
    """NeoSoft models should return 'neosoft' as base_path."""
    flat = {"getSRN": "200AAA12345"}
    result = detect_model(flat)
    assert result.base_path == "/neosoft"


def test_safetechplus_base_path() -> None:
    """Safe-Tech+ should return 'trio' as base_path."""
    flat = {"getSRN": "112AAA22222", "getVER": "Safe-T+ V2.00e"}
    result = detect_model(flat)
    assert result.name == "safetechplus"
    assert result.base_path == "/trio"


def test_lexplus_base_path_none() -> None:
    """LEX Plus models should have None as base_path."""
    flat = {"getCNA": "LEXplus10S"}
    result = detect_model(flat)
    assert result.base_path is None


def test_serial_prefix_detection_113() -> None:
    """Serial number starting with 113AAA... detects model 113."""
    flat = {"getSRN": "113AAA54321"}
    result = detect_model(flat)
    assert result.name == "trio"
    assert result.display_name.startswith("Trio DFR/LS")


def test_serial_prefix_detection_206() -> None:
    """Serial number starting with 206AAA... detects model 206."""
    flat = {"getSRN": "206AAA54321"}
    result = detect_model(flat)
    assert result.name == "neosoft2500"
    assert result.display_name.startswith("NeoSoft 2500")


def test_serial_prefix_priority_over_getcna() -> None:
    """serial_prefix has higher priority than getCNA match."""
    flat = {"getSRN": "113AAA99999", "getCNA": "LEXplus10"}
    result = detect_model(flat)
    assert result.name == "trio"


def test_serial_prefix_no_match_falls_back() -> None:
    """Unknown prefix falls back to other detection or unknown."""
    flat = {"getSRN": "999AAA12345", "getCNA": "LEXplus10"}
    result = detect_model(flat)
    # Should fall back to getCNA match
    assert result.name == "lexplus10"


def test_serial_prefix_short_serial() -> None:
    """Too short serial number does not match any prefix."""
    flat = {"getSRN": "11A"}
    result = detect_model(flat)
    assert result.name == "unknown"


def test_ver_contains_signature_matches_and_skips() -> None:
    """Test signature using ver_contains matches when present and skips when absent."""
    test_sig = [
        replace(
            UNKNOWN_MODEL,
            display_name="Test Ver Contains",
            base_path="/test",
            name="testver",
            ver_contains="MAGIC",
        )
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        assert detect_model({"getVER": "prefixMAGICsuffix"}).name == "testver"
        assert detect_model({"getVER": "nope"}).name == "unknown"


# ---------------------------------------------------------------------------
# Manufacturer field tests
# ---------------------------------------------------------------------------


def test_manufacturer_syr_via_cna() -> None:
    """SYR devices detected by cna_equals should return manufacturer 'SYR'."""
    for cna, expected_name in [
        ("LEXplus10", "lexplus10"),
        ("LEXplus10S", "lexplus10s"),
        ("LEXplus10SL", "lexplus10sl"),
    ]:
        result = detect_model({"getCNA": cna})
        assert result.manufacturer == "SYR", (
            f"Expected SYR for {cna}, got {result.manufacturer}"
        )
        assert result.name == expected_name


def test_manufacturer_syr_via_srn_prefix() -> None:
    """SYR devices detected by srn_prefix should return manufacturer 'SYR'."""
    for srn, expected_name in [
        ("206AAA00001", "neosoft2500"),
        ("112AAA00001", "safetechplus"),
        ("113AAA00001", "trio"),
    ]:
        result = detect_model({"getSRN": srn})
        assert result.manufacturer == "SYR", (
            f"Expected SYR for SRN {srn}, got {result.manufacturer}"
        )
        assert result.name == expected_name


def test_manufacturer_syr_via_ver_prefix() -> None:
    """SYR devices detected by ver_prefix should return manufacturer 'SYR'."""
    for ver, expected_name in [
        ("Safe-Tech V4.1", "safetechv4"),
        ("Safe-T+ V2.00e", "safetplus"),
    ]:
        flat = {"getVER": ver}
        result = detect_model(flat)
        assert result.manufacturer == "SYR", (
            f"Expected SYR for VER {ver!r}, got {result.manufacturer}"
        )
        assert result.name == expected_name


def test_manufacturer_hansgrohe_pontosbase() -> None:
    """Hansgrohe Pontos Base should return manufacturer 'Hansgrohe'."""
    result = detect_model({"getVER": "PontosBase V1.31"})
    assert result.name == "pontosbase"
    assert result.manufacturer == "Hansgrohe"


def test_manufacturer_sanibel_via_srn_prefix() -> None:
    """Sanibel devices detected by srn_prefix should return manufacturer 'Sanibel'."""
    for srn, extra_attrs, expected_name in [
        # sanibelleakprotect additionally requires getDFM==1 (its MultiController role).
        ("501AAA00001", {"getDFM": 1}, "sanibelleakprotect"),
        ("207AAA00001", {}, "sanibelsoftwateruno"),
    ]:
        result = detect_model({"getSRN": srn, **extra_attrs})
        assert result.manufacturer == "Sanibel", (
            f"Expected Sanibel for SRN {srn}, got {result.manufacturer}"
        )
        assert result.name == expected_name


def test_manufacturer_unknown_for_undetected_model() -> None:
    """Unknown model fallback should return manufacturer 'Unknown'."""
    result = detect_model({})
    assert result.name == "unknown"
    assert result.manufacturer == "Unknown"


def test_manufacturer_field_present_in_all_return_paths() -> None:
    """Every detect_model return value must contain a non-None 'manufacturer' key."""
    test_cases = [
        {"getCNA": "LEXplus10"},  # cna_equals path
        {"getSRN": "113AAA00001"},  # srn_prefix path
        {"getVER": "Safe-T+ V2.00e"},  # ver_prefix path
        {},  # unknown fallback
    ]
    for flat in test_cases:
        result = detect_model(flat)
        assert result.manufacturer is not None, (
            f"'manufacturer' is None for input {flat}"
        )


def test_manufacturer_via_xml_fixtures() -> None:
    """Verify manufacturer is correctly set when detecting from real XML fixtures."""
    fixture_dir_xml = Path(__file__).parent / "fixtures/xml"
    parser = ResponseParser()

    expected = [
        (
            "SanibelLeakProtectionModuleA25_GetDeviceCollectionStatus.xml",
            "sanibelleakprotect",
            "Sanibel",
        ),
        (
            "SanibelSoftwaterUNOA25_GetDeviceCollectionStatus.xml",
            "sanibelsoftwateruno",
            "Sanibel",
        ),
        ("SyrSafeTechPlus_GetDeviceCollectionStatus.xml", "safetechplus", "SYR"),
    ]
    for filename, expected_name, expected_manufacturer in expected:
        xml = (fixture_dir_xml / filename).read_text(encoding="utf-8")
        flat = parser.parse_device_status_response(xml)
        assert flat is not None
        result = detect_model(flat)
        assert result.name == expected_name, f"{filename}: name mismatch"
        assert result.manufacturer == expected_manufacturer, (
            f"{filename}: expected manufacturer {expected_manufacturer!r}, got {result.manufacturer!r}"
        )


def test_neosoft_detection_via_json_fixtures() -> None:
    """The NeoSoft 2500 and 5000 JSON fixtures are told apart by their serial number."""
    for filename, expected_name in (
        ("SyrNeoSoft2500_get_all.json", "neosoft2500"),
        ("SyrNeoSoft5000_get_all.json", "neosoft5000"),
    ):
        fixture_path = Path(__file__).parent / "fixtures/json" / filename
        flat = json.loads(fixture_path.read_text(encoding="utf-8"))
        assert detect_model(flat).name == expected_name, filename


def test_manufacturer_via_json_fixture_pontosbase() -> None:
    """Verify manufacturer 'Hansgrohe' when detecting from Pontos Base JSON fixture."""
    fixture_path = (
        Path(__file__).parent / "fixtures/json/HansgrohePontosBase_get_all.json"
    )
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    # The JSON fixture is a flat status dict already
    flat = (
        data
        if any(k.startswith("get") for k in data)
        else next(iter(data.values()), data)
    )
    result = detect_model(flat)
    assert result.name == "pontosbase"
    assert result.manufacturer == "Hansgrohe"


def test_safetech_detection_via_json_fixture() -> None:
    """Verify SafeTech Connect is detected from the SyrSafeTech_get_all.json fixture."""
    fixture_path = Path(__file__).parent / "fixtures/json/SyrSafeTech_get_all.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    flat = (
        data
        if any(k.startswith("get") for k in data)
        else next(iter(data.values()), data)
    )
    result = detect_model(flat)
    assert result.name == "safetech"
    assert result.display_name == "SafeTech Connect"
    assert result.manufacturer == "SYR"
    assert result.base_path == "/trio"


def test_safetech_v3_detection_local() -> None:
    """SafeTech with 'Safe-Tech V3' firmware should be detected via ver_prefix.

    Regression for a V3 unit (dk=140) reported over the local /safe-tec API
    whose serial matches no srn_prefix and whose firmware is not 'Safe-Tech V4',
    so it previously fell through to the unknown model.
    """
    flat = {
        "getSRN": "219999999",
        "getVER": "Safe-Tech V3.56",
        "getTYP": "140",
        "getAB": "1",
        "getVLV": "20",
    }
    result = detect_model(flat)
    assert result.name == "safetechv3"
    assert result.display_name == "SafeTech V3 Connect"
    assert result.base_path == "/safe-tec"
    assert result.manufacturer == "SYR"


def test_safetech_v4_not_shadowed_by_v3() -> None:
    """Adding the V3 signature must not steal detection from V4 firmware."""
    flat = {"getSRN": "987654321", "getVER": "Safe-Tech V4.08", "getTYP": "140"}
    result = detect_model(flat)
    assert result.name == "safetechv4"


# ---------------------------------------------------------------------------
# CONEL CLEAR PRO SOFT tests
# ---------------------------------------------------------------------------


def test_conelclearprosoft_detection_synthetic() -> None:
    """CONEL CLEAR PRO SOFT is detected by SRN prefix '215AAA'."""
    flat = {"getSRN": "215AAA12345"}
    result = detect_model(flat)
    assert result.name == "conelclearprosoft"
    assert result.display_name == "CLEAR PRO SOFT"
    assert result.manufacturer == "CONEL"
    assert result.base_path == "/neosoft"


def test_conelclearprosoft_srn_prefix_priority_over_cna() -> None:
    """SRN prefix '215AAA' wins over a concurrent getCNA value."""
    flat = {"getSRN": "215AAA99999", "getCNA": "LEXplus10"}
    result = detect_model(flat)
    assert result.name == "conelclearprosoft"


def test_conelclearprosoft_wrong_srn_infix_no_match() -> None:
    """SRN '215' with non-standard infix must NOT match conelclearprosoft."""
    flat = {"getSRN": "215BBB12345"}
    result = detect_model(flat)
    assert result.name != "conelclearprosoft"


def test_conelclearprosoft_base_path_is_neosoft() -> None:
    """CONEL CLEAR PRO SOFT must report '/neosoft' as its base path."""
    flat = {"getSRN": "215AAA00001"}
    result = detect_model(flat)
    assert result.base_path == "/neosoft"


def test_manufacturer_conel_via_srn_prefix() -> None:
    """CONEL devices detected by srn_prefix should return manufacturer 'CONEL'."""
    result = detect_model({"getSRN": "215AAA00001"})
    assert result.manufacturer == "CONEL"
    assert result.name == "conelclearprosoft"


def test_conelclearprosoft_detection_via_json_fixture() -> None:
    """Verify CONEL CLEAR PRO SOFT is detected from the JSON get_all fixture."""
    fixture_path = (
        Path(__file__).parent / "fixtures/json/ConelClearProSoft_get_all.json"
    )
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    flat = (
        data
        if any(k.startswith("get") for k in data)
        else next(iter(data.values()), data)
    )
    result = detect_model(flat)
    assert result.name == "conelclearprosoft"
    assert result.display_name == "CLEAR PRO SOFT"
    assert result.manufacturer == "CONEL"
    assert result.base_path == "/neosoft"


def test_detect_model_unique_device_kind_needs_no_status() -> None:
    """A device kind of one signature selects it, even without a status."""
    assert detect_model({}, dk=2, dkv=2).name == "safetmaster"
    assert detect_model(None, dk=141, dkv=35).name == "safetech141"


def test_detect_model_subtype_selects_the_signature() -> None:
    """The subtype (sbt) selects one of the signatures with the same dk/dkv."""
    assert detect_model({}, dk=80, dkv=25, sbt=2).name == "lexplus10s"
    assert detect_model({}, dk=80, dkv=25, sbt=7).name == "lexplus10sl"


def test_detect_model_status_decides_within_the_family() -> None:
    """In a family of several signatures the status decides between them."""
    assert detect_model({"getCNA": "L20"}, dk=40, dkv=16, sbt=0).name == "l20"
    status = {"getSRN": "506AAA00001", "getDFM": "5"}
    assert detect_model(status, dk=1506, dkv=506).name == "syrtriolockconnect"
    status = {"getVER": "Safe-Tech V4.08"}
    assert detect_model(status, dk=140, dkv=35).name == "safetechv4"


def test_detect_model_family_without_status_match_is_unknown() -> None:
    """A status that matches no signature of the family does not leave the family."""
    status = {"getVER": "Safe-T+ V2.00e"}
    assert detect_model(status).name == "safetplus"
    assert detect_model(status, dk=40, dkv=16, sbt=0) is UNKNOWN_MODEL


def test_detect_model_unknown_device_kind_uses_the_status() -> None:
    """A device kind no signature knows falls back to the status of all signatures."""
    assert detect_model({"getCNA": "LEXplus10"}, dk=9999, dkv=9999).name == "lexplus10"


def test_detect_model_device_kind_matches_status_for_xml_fixtures() -> None:
    """For every cloud fixture the device kind detects the model the status detects."""
    parser = ResponseParser()
    checked = 0
    for list_file in sorted(FIXTURE_DIR.glob("*_GetProjectDeviceCollections.xml")):
        status_file = FIXTURE_DIR / list_file.name.replace(
            "_GetProjectDeviceCollections.xml", "_GetDeviceCollectionStatus.xml"
        )
        if not status_file.exists():
            continue
        devices = parser.parse_device_list_response(
            list_file.read_text(encoding="utf-8")
        )
        status = parser.parse_device_status_response(
            status_file.read_text(encoding="utf-8")
        )
        by_status = detect_model(status)
        device = next(d for d in devices if d.get("dk") == by_status.dk)
        by_kind = detect_model(
            status, dk=device.get("dk"), dkv=device.get("dkv"), sbt=device.get("sbt")
        )
        assert by_kind is by_status, list_file.name
        assert by_kind is not UNKNOWN_MODEL, list_file.name
        checked += 1
    assert checked >= 9


def test_detect_model_unknown_multicontroller_role_is_unknown() -> None:
    """A MultiController with an unknown role (getDFM) is an unknown model."""
    status = {"getSRN": "506AAA00001", "getDFM": "9"}
    assert detect_model(status) is UNKNOWN_MODEL
    assert detect_model(status, dk=1506, dkv=506) is UNKNOWN_MODEL


@pytest.mark.parametrize(
    ("dk", "dfm", "expected_name"),
    [
        (1500, 1, "conelclearproleakprotection"),
        (1500, 2, "conelclearproconnectioncentre"),
        (1500, 3, "conelclearprofill"),
        (1500, 4, "conelclearprobackwash"),
        (1501, 1, "sanibelleakprotect"),
        (1501, 2, "sanibelconnectioncentre"),
        (1501, 4, "sanibelrsa"),
        (1502, 1, "ditechleakprotect"),
        (1502, 2, "ditechconnectioncentre"),
        (1502, 4, "ditechbackwash"),
        (1502, 5, "ditechbackwashfilter"),
        (1503, 1, "takeleakprotect"),
        (1503, 2, "takeconnectioncentre"),
        (1503, 4, "takebackwash"),
        (1503, 5, "takebackwashfilter"),
        (1504, 1, "conceptleakprotect"),
        (1504, 2, "conceptconnectioncentre"),
        (1504, 4, "conceptbackwash"),
        (1504, 5, "concepttriolock"),
        (1505, 1, "optimaleakprotect"),
        (1505, 2, "optimaconnectioncentre"),
        (1505, 4, "optimabackwash"),
        (1505, 5, "optimatriolock"),
        (1506, 1, "syrsafetechlockconnect"),
        (1506, 2, "syrac3200connect"),
        (1506, 3, "syrac3228connect"),
        (1506, 4, "syrrsaconnect"),
        (1506, 5, "syrtriolockconnect"),
    ],
)
def test_detect_model_multicontroller_roles(
    dk: int, dfm: int, expected_name: str
) -> None:
    """Every MultiController role (getDFM) has its signature.

    The serial number detects the same role as the device kind (local JSON API).
    """
    dkv = dk - 1000
    status = {"getSRN": f"{dkv}AAA00001", "getDFM": str(dfm)}
    assert detect_model(status, dk=dk, dkv=dkv).name == expected_name
    assert detect_model(status).name == expected_name


def test_detect_model_multicontroller_without_role_is_unknown() -> None:
    """A MultiController without a role (getDFM) is an unknown model."""
    assert detect_model({"getSRN": "502AAA00001"}, dk=1502, dkv=502) is UNKNOWN_MODEL
    assert detect_model({}, dk=1505, dkv=505) is UNKNOWN_MODEL


def test_model_signature_names_are_unique() -> None:
    """Every signature has its own name; a duplicate would never be detected."""
    names = [signature.name for signature in MODEL_SIGNATURES]
    assert sorted(name for name in set(names) if names.count(name) > 1) == []


def test_detect_model_neosoft_device_kinds() -> None:
    """Device kind "NeoSoft" (dk=1200) is the NeoSoft 5000, "NeoSoft Single" (dk=1206) the 2500."""
    assert detect_model({}, dk=1200, dkv=200).name == "neosoft5000"
    status = {"getSRN": "206AAA12345"}
    assert detect_model(status, dk=1206, dkv=206).name == "neosoft2500"


def test_detect_model_dfm_as_number_or_text() -> None:
    """The local API reports getDFM as a number, the cloud API as text."""
    for dfm in (2, "2"):
        status = {"getSRN": "506AAA12345", "getDFM": dfm}
        assert detect_model(status).name == "syrac3200connect", repr(dfm)


def test_detect_model_dfm_alone_does_not_detect_a_role() -> None:
    """Without a matching serial number or device kind, getDFM alone detects no role."""
    assert detect_model({"getDFM": 1}) is UNKNOWN_MODEL
    assert detect_model({"getSRN": "123456789", "getDFM": 1}) is UNKNOWN_MODEL
