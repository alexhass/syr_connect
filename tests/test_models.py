from pathlib import Path

from custom_components.syr_connect.response_parser import ResponseParser
from custom_components.syr_connect.models import detect_model


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_xml(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


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


def test_lexplus10_detection_synthetic():
    """Synthetic flattened dict with getCNA should detect lexplus10."""
    flat = {"getCNA": "LEXplus10"}
    assert detect_model(flat)["name"] == "lexplus10"


def test_neosoft5000_detection_synthetic():
    """Detect neosoft5000 via ver_prefix + v_keys."""
    flat = {"getVER": "NSS-1.2", "getRE1": "x", "getRE2": "y"}
    assert detect_model(flat)["name"] == "neosoft5000"
