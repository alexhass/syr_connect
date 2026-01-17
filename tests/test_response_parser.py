FIXTURE_PATH_10S_PROJECT_COLLECTIONS = os.path.join(os.path.dirname(__file__), "fixtures", "LEXplus10S_GetProjectDeviceCollections.xml")

@pytest.fixture
def lexplus10s_project_collections_xml():
    with open(FIXTURE_PATH_10S_PROJECT_COLLECTIONS, encoding="utf-8") as f:
        return f.read()

def test_parse_device_list_alias_reference(lexplus10s_project_collections_xml):
    """Test parsing device list and alias extraction via references."""
    parser = ResponseParser()
    devices = parser.parse_device_list_response(lexplus10s_project_collections_xml)
    assert isinstance(devices, list)
    assert len(devices) == 1
    device = devices[0]
    # The alias should be correctly extracted from the dclg reference
    assert device["name"] == "Water Softener"
    assert device["dclg"] == "0b09f7ce-41a0-4085-9e69-fa8827a32b6f"
    assert device["serial_number"] == "123456789"


"""Unit tests for SYR Connect XML response parser."""
import os
import pytest
from custom_components.syr_connect.response_parser import ResponseParser

FIXTURE_PATH_10S = os.path.join(os.path.dirname(__file__), "fixtures", "LEXplus10S_GetDeviceCollectionStatus.xml")
FIXTURE_PATH_10SL = os.path.join(os.path.dirname(__file__), "fixtures", "LEXplus10SL_GetDeviceCollectionStatus.xml")

@pytest.fixture
def lexplus10s_xml():
    with open(FIXTURE_PATH_10S, encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def lexplus10sl_xml():
    with open(FIXTURE_PATH_10SL, encoding="utf-8") as f:
        return f.read()


def test_parse_device_status_response_10s(lexplus10s_xml):
    """Test parsing of LEXplus10S device status XML."""
    parser = ResponseParser()
    result = parser.parse_device_status_response(lexplus10s_xml)
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

def test_parse_device_status_response_10sl(lexplus10sl_xml):
    """Test parsing of LEXplus10SL device status XML."""
    parser = ResponseParser()
    result = parser.parse_device_status_response(lexplus10sl_xml)
    assert isinstance(result, dict)
    assert "getCNA" in result
    assert result["getCNA"] == "LEXplus10SL"
    assert "getSRN" in result
    assert "getFLO" in result
    assert "getPRS" in result
    assert "getSS1" in result
    # Check some typical values (adjust as needed for your fixture)
    assert int(result["getPRS"]) >= 0
    assert int(result["getFLO"]) >= 0
    # assert result["getALM_meta"]["m"] == "LowSalt"
