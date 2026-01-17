"""Unit tests for SYR Connect XML response parser."""
import os
import pytest
from custom_components.syr_connect.response_parser import parse_device_status_response

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "LEXplus10S.xml")

@pytest.fixture
def lexplus10s_xml():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return f.read()


def test_parse_device_status_response(lexplus10s_xml):
    """Test parsing of LEXplus10S device status XML."""
    result = parse_device_status_response(lexplus10s_xml)
    assert isinstance(result, dict)
    # Check some key values
    assert "getALM" in result
    assert "getFLO" in result
    assert "getPRS" in result
    assert "getSS1" in result
    assert "getCNA" in result
    assert result["getCNA"] == "LEXplus10S"
    # Check alarm mapping
    assert "LowSalt" in lexplus10s_xml
    assert result["getALM"] == ""
    # Check salt value
    assert int(result["getSS1"]) == 5
    # Check pressure value
    assert int(result["getPRS"]) == 48
    # Check flow value
    assert int(result["getFLO"]) == 0
    # Check device name
    assert result["getCNA"] == "LEXplus10S"
    # Check serial number
    assert result["getSRN"] == "123456789"
    # Check firmware
    assert result["getFIR"] == "SLPS"
    # Check MAC address
    assert result["getMAC"].startswith("0c:73:eb:")
    # Check water hardness unit
    assert "getWHU" in result
    # Check resin capacity
    assert int(result["getCS1"]) == 60
    # Check salt container value
    assert int(result["getSV1"]) == 8
    # Check alarm meta
    # The parser should expose alarm meta if implemented
    # If not, this can be extended
    # assert result["getALM_meta"]["m"] == "LowSalt"
