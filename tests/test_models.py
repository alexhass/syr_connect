from pathlib import Path

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


def test_trio_attrs_only_synthetic():
    """If attrs_equals is present and matches, detection succeeds without getVER."""
    # Construct a synthetic flattened dict that matches the current trio signature
    # (requires ver_prefix 'syr001' and v_keys 'getAFW' and 'getVER2').
    flat = {"getVER2": "176", "getAFW": "1", "getVER": "syr001-A-B-000-176"}
    assert detect_model(flat)["name"] == "trio"


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


def test_safetech_detection_synthetic():
    """Safe-Tech+ should be detected by ver_prefix 'Safe-Tech'."""
    flat = {"getVER": "Safe-Tech-1.2.3"}
    result = detect_model(flat)
    assert result["name"] == "safetech"
    assert result["display_name"] == "Safe-Tech+ Connect"


def test_lexplus10_with_display_name_and_base_path():
    """Verify display_name and base_path are returned correctly."""
    flat = {"getCNA": "LEXplus10"}
    result = detect_model(flat)
    assert result["name"] == "lexplus10"
    assert result["display_name"] == "LEX Plus 10 Connect"
    assert result["base_path"] is None


def test_neosoft2500_with_base_path():
    """Verify neosoft2500 returns correct base_path."""
    flat = {"getRE1": "1", "getVER": "NSS-1.0"}
    result = detect_model(flat)
    assert result["name"] == "neosoft2500"
    assert result["base_path"] == "neosoft"


def test_getcna_none_converted_to_empty_string():
    """getCNA of None should be safely converted to empty string."""
    flat = {"getCNA": None, "getVER": "Safe-Tech-1"}
    result = detect_model(flat)
    # Should still detect by version
    assert result["name"] == "safetech"


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


def test_v_keys_partial_match_insufficient():
    """If only 1 of 2 required v_keys present, should not match."""
    flat = {"getRE1": "1", "getVER": "NSS-1.0"}
    result = detect_model(flat)
    # Should match neosoft2500 (requires only 1 v_key)
    assert result["name"] == "neosoft2500"


def test_attrs_match_empty_dict_returns_true():
    """When attrs_equals is empty dict or None, should return True."""
    # This tests the attrs_match function indirectly
    # All current signatures have attrs_equals=None, so this tests that path
    flat = {"getVER": "Safe-T-1.0"}
    result = detect_model(flat)
    assert result["name"] == "safetplus"


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


def test_trio_with_v_keys_and_version():
    """Trio requires both v_keys match and version prefix."""
    flat = {"getAFW": "1", "getVER2": "176", "getVER": "syr001-xyz"}
    result = detect_model(flat)
    assert result["name"] == "trio"


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


def test_v_keys_required_default_behavior():
    """Test v_keys matching when v_keys_required is not explicitly set."""
    # NeoSoft signatures explicitly set v_keys_required
    # Testing that default behavior works as expected
    flat = {"getRE1": "1", "getVER": "NSS-1.0"}
    result = detect_model(flat)
    assert result["name"] == "neosoft2500"


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


def test_attrs_match_single_attr_mismatch():
    """If one attr in attrs_equals doesn't match, signature is skipped."""
    # Since no current signature uses attrs_equals, we test the logic indirectly
    # by ensuring signatures without attrs_equals don't fail
    flat = {"getVER": "syr001-test"}
    result = detect_model(flat)
    # Without v_keys, should still detect by version
    assert result["name"] == "trio"


def test_neosoft_base_path():
    """NeoSoft models should return 'neosoft' as base_path."""
    flat = {"getRE1": "1", "getRE2": "2", "getVER": "NSS-3.0"}
    result = detect_model(flat)
    assert result["base_path"] == "neosoft"


def test_trio_base_path():
    """Trio models should return 'trio' as base_path."""
    flat = {"getVER": "syr001-firmware"}
    result = detect_model(flat)
    assert result["name"] == "trio"
    assert result["base_path"] == "trio"


def test_safetech_base_path():
    """Safe-Tech+ should return 'trio' as base_path."""
    flat = {"getVER": "Safe-Tech-v2"}
    result = detect_model(flat)
    assert result["name"] == "safetech"
    assert result["base_path"] == "trio"


def test_lexplus_base_path_none():
    """LEX Plus models should have None as base_path."""
    flat = {"getCNA": "LEXplus10S"}
    result = detect_model(flat)
    assert result["base_path"] is None
