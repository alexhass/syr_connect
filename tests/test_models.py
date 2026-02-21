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
    assert detect_model(flat) == "lexplus10s"


def test_lexplus10sl_detection():
    xml = _load_xml("LEXplus10SL_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat) == "lexplus10sl"


def test_neosoft2500_detection():
    xml = _load_xml("NeoSoft2500_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat) == "neosoft"


def test_trio_dfrls_detection():
    xml = _load_xml("TrioDFRLS_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat) == "trio"


def test_safetplus_detection():
    xml = _load_xml("SafeTPlus_GetDeviceCollectionStatus.xml")
    parser = ResponseParser()
    flat = parser.parse_device_status_response(xml)
    assert flat is not None
    assert detect_model(flat) == "safetplus"
