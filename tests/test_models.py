from pathlib import Path

from custom_components.syr_connect.response_parser import ResponseParser
from custom_components.syr_connect.models import detect_model


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
