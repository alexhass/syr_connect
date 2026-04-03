import logging
from pathlib import Path
from unittest.mock import patch

from custom_components.syr_connect.models import detect_model
from custom_components.syr_connect.response_parser import ResponseParser

FIXTURE_DIR = Path(__file__).parent / "fixtures/xml"


def _load_xml(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_lexplus10_detection_synthetic():
    """Synthetic flattened dict with getCNA should detect lexplus10."""
    flat = {"getCNA": "LEXplus10"}
    assert detect_model(flat)["name"] == "lexplus10"


def test_lexplus10s_detection():
    xml = _load_xml("LEXplus10S_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat)["name"] == "lexplus10s"


def test_lexplus10sl_detection():
    xml = _load_xml("LEXplus10SL_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat)["name"] == "lexplus10sl"


def test_neosoft2500_detection():
    xml = _load_xml("NeoSoft2500_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat)["name"] == "neosoft2500"


def test_neosoft5000_detection():
    xml = _load_xml("NeoSoft5000_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat)["name"] == "neosoft5000"


def test_trio_dfrls_detection():
    xml = _load_xml("TrioDFRLS_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat)["name"] == "trio"


def test_safetplus_detection():
    xml = _load_xml("SafeTPlus_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat)["name"] == "safetplus"


def test_unknown_model_detection():
    """Unknown or empty flattened dict should yield the unknown fallback."""
    assert detect_model({})["name"] == "unknown"


def test_detect_model_none_input():
    """Passing a non-dict (None) returns None."""
    assert detect_model(None) is None


def test_neosoft_vkeys_version_mismatch_returns_unknown():
    """If v_keys match but version constraints fail, signature is skipped and result is unknown."""
    flat = {"getRE1": "1", "getRE2": "2", "getVER": "XXX"}
    assert detect_model(flat)["name"] == "unknown"


def test_insufficient_v_keys_and_no_other_match():
    """If a signature requires more v_keys than present and nothing else matches, return unknown."""
    flat = {"getRE1": "1", "getVER": "NOTNSS"}
    assert detect_model(flat)["name"] == "unknown"


def test_attrs_equals_mismatch_skips_signature():
    """When attrs_equals is present but values don't match, signature should be skipped."""
    flat = {"getVER2": "999"}
    assert detect_model(flat)["name"] == "unknown"


def test_safetechplus_detection_synthetic():
    """Safe-Tech+ should be detected by ver_prefix 'Safe-Tech'."""
    flat = {"getSRN": "112AAA00001", "getVER": "Safe-Tech-1.2.3"}
    result = detect_model(flat)
    assert result["name"] == "safetechplus"
    assert result["display_name"] == "Safe-Tech Plus Connect"


def test_lexplus10_with_display_name_and_base_path():
    """Verify display_name and base_path are returned correctly."""
    flat = {"getCNA": "LEXplus10"}
    result = detect_model(flat)
    assert result["name"] == "lexplus10"
    assert result["display_name"] == "LEX Plus 10 Connect"
    assert result["base_path"] is None


def test_getcna_none_converted_to_empty_string():
    """getCNA of None should be safely converted to empty string."""
    flat = {"getSRN": "112AAA12345", "getCNA": None, "getVER": "Safe-Tech-1"}
    result = detect_model(flat)
    # Should still detect by version
    assert result["name"] == "safetechplus"


def test_getver_none_converted_to_empty_string():
    """getVER of None should be safely converted to empty string."""
    flat = {"getCNA": "LEXplus10", "getVER": None}
    result = detect_model(flat)
    # Should still detect by getCNA
    assert result["name"] == "lexplus10"


def test_both_getcna_and_getver_none():
    """Both getCNA and getVER None should not cause errors."""
    flat = {"getCNA": None, "getVER": None}
    result = detect_model(flat)
    assert result["name"] == "unknown"


def test_non_dict_input_returns_none():
    """Non-dict inputs like string or list should return None."""
    assert detect_model("not a dict") is None
    assert detect_model([1, 2, 3]) is None
    assert detect_model(123) is None


def test_ver_contains_synthetic():
    """Test signature matching with ver_contains attribute."""
    # Create a synthetic signature scenario where ver_contains is used
    # Since no real signature uses it, we test the version_match logic
    flat = {"getVER": "some-Safe-version-text"}
    # This won't match Safe-Tech (requires prefix), but tests the ver_contains code path
    result = detect_model(flat)
    # Should be unknown since no signature with ver_contains matches
    assert result["name"] == "unknown"


def test_signature_priority_first_match_wins():
    """When multiple signatures could match, first one wins."""
    # LEXplus10S has exact getCNA match, should win even if other conditions exist
    flat = {"getCNA": "LEXplus10S", "getVER": "NSS-1.0"}
    result = detect_model(flat)
    assert result["name"] == "lexplus10s"


def test_neosoft5000_vkeys_match_with_version():
    """NeoSoft 5000 requires 2 v_keys and NSS version prefix."""
    flat = {"getRE1": "1", "getRE2": "2", "getVER": "NSS-2.0"}
    result = detect_model(flat)
    assert result["name"] == "neosoft5000"
    assert result["display_name"] == "NeoSoft 5000 Connect"


def test_version_match_prefix_only():
    """Test version matching with only ver_prefix."""
    flat = {"getVER": "Safe-T-Plus-1.2.3"}
    result = detect_model(flat)
    assert result["name"] == "safetplus"


def test_version_match_prefix_mismatch():
    """Version prefix mismatch should skip signature."""
    flat = {"getAFW": "1", "getVER2": "176", "getVER": "wrong-prefix"}
    result = detect_model(flat)
    assert result["name"] == "unknown"


def test_empty_flat_dict_returns_unknown():
    """Empty dict with no keys should return unknown."""
    result = detect_model({})
    assert result["name"] == "unknown"
    assert result["display_name"] == "Unknown model"
    assert result["base_path"] is None


def test_unknown_model_has_correct_structure():
    """Unknown model return should have proper structure."""
    flat = {"getSomeRandomKey": "value"}
    result = detect_model(flat)
    assert "name" in result
    assert "display_name" in result
    assert "base_path" in result
    assert result["name"] == "unknown"


def test_multiple_keys_with_no_signature_match():
    """Dict with many keys but no signature match should return unknown."""
    flat = {
        "getXYZ": "1",
        "getABC": "2",
        "getDEF": "3",
        "getVER": "unknown-version",
    }
    result = detect_model(flat)
    assert result["name"] == "unknown"


def test_lexplus10sl_with_exact_cna():
    """LEXplus10SL exact CNA match should detect correctly."""
    flat = {"getCNA": "LEXplus10SL"}
    result = detect_model(flat)
    assert result["name"] == "lexplus10sl"


def test_neosoft_base_path():
    """NeoSoft models should return 'neosoft' as base_path."""
    flat = {"getRE1": "1", "getRE2": "2", "getVER": "NSS-3.0"}
    result = detect_model(flat)
    assert result["base_path"] == "/neosoft"


def test_safetechplus_base_path():
    """Safe-Tech+ should return 'trio' as base_path."""
    flat = {"getSRN": "112AAA22222", "getVER": "Safe-Tech-v2"}
    result = detect_model(flat)
    assert result["name"] == "safetechplus"
    assert result["base_path"] == "/trio"


def test_lexplus_base_path_none():
    """LEX Plus models should have None as base_path."""
    flat = {"getCNA": "LEXplus10S"}
    result = detect_model(flat)
    assert result["base_path"] is None


# Tests for attrs_match logic
# Since no current MODEL_SIGNATURES use attrs_equals, we use mocking to test this logic


def test_attrs_match_none_returns_true():
    """When attrs_equals is None, attrs_match should return True."""
    # Create a test signature with no attrs_equals
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": "TEST",
            "attrs_equals": None,
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        flat = {"getVER": "TEST-1.0"}
        result = detect_model(flat)
        assert result["name"] == "testmodel"


def test_attrs_match_empty_dict_returns_true():
    """When attrs_equals is an empty dict, attrs_match should return True."""
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": "TEST",
            "attrs_equals": {},
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        flat = {"getVER": "TEST-1.0"}
        result = detect_model(flat)
        assert result["name"] == "testmodel"


def test_attrs_match_single_attribute_matches():
    """When attrs_equals has one attribute that matches, should return True."""
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": None,
            "attrs_equals": {"getATTR": "value1"},
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        flat = {"getATTR": "value1", "getVER": "TEST"}
        result = detect_model(flat)
        assert result["name"] == "testmodel"


def test_attrs_match_single_attribute_mismatch():
    """When attrs_equals has one attribute that doesn't match, should skip signature."""
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": None,
            "attrs_equals": {"getATTR": "value1"},
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        flat = {"getATTR": "value2", "getVER": "TEST"}
        result = detect_model(flat)
        # Should not match testmodel, should fall back to unknown
        assert result["name"] == "unknown"


def test_attrs_match_multiple_attributes_all_match():
    """When attrs_equals has multiple attributes that all match, should return True."""
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": None,
            "attrs_equals": {"getATTR1": "val1", "getATTR2": "val2", "getATTR3": "val3"},
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        flat = {"getATTR1": "val1", "getATTR2": "val2", "getATTR3": "val3", "getVER": "TEST"}
        result = detect_model(flat)
        assert result["name"] == "testmodel"


def test_attrs_match_multiple_attributes_one_mismatch():
    """When attrs_equals has multiple attributes and one doesn't match, should skip signature."""
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": None,
            "attrs_equals": {"getATTR1": "val1", "getATTR2": "val2", "getATTR3": "val3"},
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        # ATTR2 has wrong value
        flat = {"getATTR1": "val1", "getATTR2": "wrong", "getATTR3": "val3", "getVER": "TEST"}
        result = detect_model(flat)
        assert result["name"] == "unknown"


def test_attrs_match_type_conversion_int_to_str():
    """Attrs_match should convert values to strings for comparison."""
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": None,
            "attrs_equals": {"getATTR": "123"},
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        # Value in flat is int, should be converted to string for comparison
        flat = {"getATTR": 123}
        result = detect_model(flat)
        assert result["name"] == "testmodel"


def test_attrs_match_missing_key_in_flat():
    """When required attr key is missing in flat, should use empty string and fail match."""
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": None,
            "attrs_equals": {"getATTR": "value"},
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        # getATTR is missing from flat
        flat = {"getVER": "TEST"}
        result = detect_model(flat)
        assert result["name"] == "unknown"


def test_attrs_match_with_version_constraints():
    """Attrs_match combined with version constraints should work together."""
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": "TEST",
            "attrs_equals": {"getATTR": "value"},
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        # Both attrs and version match
        flat = {"getATTR": "value", "getVER": "TEST-1.0"}
        result = detect_model(flat)
        assert result["name"] == "testmodel"


def test_attrs_match_pass_but_version_fail():
    """When attrs match but version doesn't, model is still detected.

    attrs_equals takes precedence in detection logic, version is not checked
    when attrs_equals matches.
    """
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": "TEST",
            "attrs_equals": {"getATTR": "value"},
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        # Attrs match but version doesn't - attrs_equals takes precedence
        flat = {"getATTR": "value", "getVER": "WRONG"}
        result = detect_model(flat)
        assert result["name"] == "testmodel"


def test_attrs_match_with_v_keys():
    """Attrs_match combined with v_keys should work together."""
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": "TEST",
            "attrs_equals": {"getATTR": "value"},
            "v_keys": {"getKEY1", "getKEY2"},
            "v_keys_required": 2,
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        # All conditions satisfied: attrs, version, and v_keys
        flat = {"getATTR": "value", "getVER": "TEST-1.0", "getKEY1": "1", "getKEY2": "2"}
        result = detect_model(flat)
        assert result["name"] == "testmodel"


def test_attrs_match_bool_conversion():
    """Test that boolean values are correctly converted to strings."""
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": None,
            "attrs_equals": {"getATTR": "True"},
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        flat = {"getATTR": True}
        result = detect_model(flat)
        assert result["name"] == "testmodel"


def test_attrs_match_none_value_in_flat():
    """Test that None values in flat are converted to string 'None'."""
    test_sig = [
        {
            "display_name": "Test Model",
            "base_path": "test",
            "name": "testmodel",
            "cna_equals": None,
            "ver_prefix": None,
            "attrs_equals": {"getATTR": "None"},
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        flat = {"getATTR": None}
        result = detect_model(flat)
        assert result["name"] == "testmodel"


def test_serial_prefix_detection_113():
    """Serial number starting with 113AAA... detects model 113."""
    flat = {"getSRN": "113AAA54321"}
    result = detect_model(flat)
    assert result["name"] == "trio"
    assert result["display_name"].startswith("Trio DFR/LS")


def test_serial_prefix_detection_206():
    """Serial number starting with 206AAA... detects model 206."""
    flat = {"getSRN": "206AAA54321"}
    result = detect_model(flat)
    assert result["name"] == "neosoft2500"
    assert result["display_name"].startswith("NeoSoft 2500")


def test_serial_prefix_priority_over_getcna():
    """serial_prefix has higher priority than getCNA match."""
    flat = {"getSRN": "113AAA99999", "getCNA": "LEXplus10"}
    result = detect_model(flat)
    assert result["name"] == "trio"


def test_serial_prefix_no_match_falls_back():
    """Unknown prefix falls back to other detection or unknown."""
    flat = {"getSRN": "999AAA12345", "getCNA": "LEXplus10"}
    result = detect_model(flat)
    # Should fall back to getCNA match
    assert result["name"] == "lexplus10"


def test_serial_prefix_short_serial():
    """Too short serial number does not match any prefix."""
    flat = {"getSRN": "11A"}
    result = detect_model(flat)
    assert result["name"] == "unknown"


def test_srn_contains_signature_matches_and_skips():
    """Test signature using srn_contains matches when present and skips when absent."""
    test_sig = [
        {
            "display_name": "Test SRN Contains",
            "base_path": "/test",
            "name": "testsrn",
            "srn_contains": "XYZ",
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        assert detect_model({"getSRN": "AAAXYZBBB"})["name"] == "testsrn"
        assert detect_model({"getSRN": "AABBB"})["name"] == "unknown"


def test_ver_contains_signature_matches_and_skips():
    """Test signature using ver_contains matches when present and skips when absent."""
    test_sig = [
        {
            "display_name": "Test Ver Contains",
            "base_path": "/test",
            "name": "testver",
            "ver_contains": "MAGIC",
        }
    ]
    with patch("custom_components.syr_connect.models.MODEL_SIGNATURES", test_sig):
        assert detect_model({"getVER": "prefixMAGICsuffix"})["name"] == "testver"
        assert detect_model({"getVER": "nope"})["name"] == "unknown"


def test_v_keys_insufficient_logs_debug(caplog):
    """When v_keys match count is insufficient, a debug log is emitted."""
    caplog.set_level(logging.DEBUG)
    flat = {"getRE1": "1", "getVER": "NOTNSS"}
    result = detect_model(flat)
    assert result["name"] == "unknown"
    assert "v_keys matched" in caplog.text


def test_v_keys_version_constraints_not_satisfied_logs_debug(caplog):
    """When v_keys match but version constraints fail, a debug log is emitted."""
    caplog.set_level(logging.DEBUG)
    flat = {"getRE1": "1", "getRE2": "2", "getVER": "XXX"}
    result = detect_model(flat)
    assert result["name"] == "unknown"
    assert "version constraints not satisfied" in caplog.text
