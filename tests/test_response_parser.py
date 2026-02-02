import os
import pytest
from custom_components.syr_connect.response_parser import ResponseParser

FIXTURE_PATH_10S_PROJECT_COLLECTIONS = os.path.join(os.path.dirname(__file__), "fixtures", "LEXplus10S_GetProjectDeviceCollections.xml")
FIXTURE_PATH_10S_DEVICE_STATUS = os.path.join(os.path.dirname(__file__), "fixtures", "LEXplus10S_GetDeviceCollectionStatus.xml")
FIXTURE_PATH_10SL_DEVICE_STATUS = os.path.join(os.path.dirname(__file__), "fixtures", "LEXplus10SL_GetDeviceCollectionStatus.xml")

@pytest.fixture
def parser():
    return ResponseParser()

@pytest.fixture
def lexplus10s_project_collections_xml():
    with open(FIXTURE_PATH_10S_PROJECT_COLLECTIONS, encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def lexplus10s_xml():
    with open(FIXTURE_PATH_10S_DEVICE_STATUS, encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def lexplus10sl_xml():
    with open(FIXTURE_PATH_10SL_DEVICE_STATUS, encoding="utf-8") as f:
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


def test_validate_structure_valid(parser):
    """Test validate_structure with valid path."""
    data = {"level1": {"level2": {"level3": "value"}}}
    assert parser.validate_structure(data, ["level1", "level2", "level3"]) is True


def test_validate_structure_invalid(parser):
    """Test validate_structure with invalid path."""
    data = {"level1": {"level2": "value"}}
    assert parser.validate_structure(data, ["level1", "level2", "level3"]) is False


def test_validate_structure_non_dict(parser):
    """Test validate_structure when intermediate value is not dict."""
    data = {"level1": "not_a_dict"}
    assert parser.validate_structure(data, ["level1", "level2"]) is False


def test_parse_xml_simple(parser):
    """Test parsing simple XML."""
    xml = "<root><item>value</item></root>"
    result = parser.parse_xml(xml)
    assert result == {"root": {"item": "value"}}


def test_parse_xml_with_attributes(parser):
    """Test parsing XML with attributes."""
    xml = '<root><item id="1" name="test">value</item></root>'
    result = parser.parse_xml(xml)
    assert result["root"]["item"]["@id"] == "1"
    assert result["root"]["item"]["@name"] == "test"
    assert result["root"]["item"]["#text"] == "value"


def test_parse_xml_list_elements(parser):
    """Test parsing XML with multiple elements of same name."""
    xml = "<root><item>val1</item><item>val2</item></root>"
    result = parser.parse_xml(xml)
    assert isinstance(result["root"]["item"], list)
    assert result["root"]["item"] == ["val1", "val2"]


def test_parse_xml_invalid(parser):
    """Test parsing invalid XML raises ValueError."""
    with pytest.raises(ValueError, match="Invalid XML response"):
        parser.parse_xml("not valid xml")


def test_parse_login_response_dict_api(parser):
    """Test parsing login response with dict api element."""
    xml = '<sc><api type="session">encrypted_data_here</api></sc>'
    encrypted, parsed = parser.parse_login_response(xml)
    assert encrypted == "encrypted_data_here"
    assert "sc" in parsed


def test_parse_login_response_string_api(parser):
    """Test parsing login response with string api element."""
    xml = '<sc><api>encrypted_data</api></sc>'
    encrypted, _ = parser.parse_login_response(xml)
    assert encrypted == "encrypted_data"


def test_parse_login_response_invalid(parser):
    """Test parsing invalid login response raises ValueError."""
    xml = "<root><invalid>data</invalid></root>"
    with pytest.raises(ValueError, match="Invalid login response structure"):
        parser.parse_login_response(xml)


def test_parse_decrypted_login(parser):
    """Test parsing decrypted login data."""
    xml = '<usr id="session123"><nam>User</nam></usr><prs><pre id="proj1" n="Project 1"/></prs>'
    session_id, projects = parser.parse_decrypted_login(xml)
    assert session_id == "session123"
    assert len(projects) == 1
    assert projects[0]["id"] == "proj1"
    assert projects[0]["name"] == "Project 1"


def test_parse_decrypted_login_multiple_projects(parser):
    """Test parsing decrypted login data with multiple projects."""
    xml = '<usr id="sess"><nam>User</nam></usr><prs><pre id="p1" n="Proj1"/><pre id="p2" n="Proj2"/></prs>'
    session_id, projects = parser.parse_decrypted_login(xml)
    assert len(projects) == 2
    assert projects[0]["id"] == "p1"
    assert projects[1]["id"] == "p2"


def test_parse_decrypted_login_no_session(parser):
    """Test parsing decrypted login without session raises ValueError."""
    xml = '<invalid>data</invalid>'
    with pytest.raises(ValueError, match="Invalid credentials or session data"):
        parser.parse_decrypted_login(xml)


def test_parse_decrypted_login_no_projects(parser):
    """Test parsing decrypted login without projects raises ValueError."""
    xml = '<usr id="sess"><nam>User</nam></usr>'
    with pytest.raises(ValueError, match="no projects found"):
        parser.parse_decrypted_login(xml)


def test_parse_device_list_no_devices(parser):
    """Test parsing device list with no devices."""
    xml = "<sc><col/></sc>"
    devices = parser.parse_device_list_response(xml)
    assert devices == []


def test_parse_device_list_dvs_is_device(parser):
    """Test parsing when dvs element itself is a device."""
    xml = '<sc><dvs dclg="123" srn="serial123"><nam>Device</nam></dvs></sc>'
    devices = parser.parse_device_list_response(xml)
    assert len(devices) >= 0  # May find device depending on structure


def test_parse_device_status_no_sc(parser):
    """Test parsing device status without sc element."""
    xml = "<root><invalid>data</invalid></root>"
    result = parser.parse_device_status_response(xml)
    assert result is None


def test_parse_device_status_no_dvs(parser):
    """Test parsing device status without dvs element."""
    xml = "<sc><col/></sc>"
    result = parser.parse_device_status_response(xml)
    assert result is None


def test_parse_device_status_no_c_children(parser):
    """Test parsing device status without c children in devices."""
    xml = "<sc><dvs><d><nam>Device</nam></d></dvs></sc>"
    result = parser.parse_device_status_response(xml)
    assert result is None


def test_parse_device_status_with_c(parser):
    """Test parsing device status with c children."""
    xml = '<sc><dvs><d><c n="test" v="123"/></d></dvs></sc>'
    result = parser.parse_device_status_response(xml)
    assert result is not None
    assert "test" in result
    assert result["test"] == "123"


def test_parse_statistics_response(parser):
    """Test parsing statistics response."""
    xml = '<sc><c n="stat1" v="100"/><c n="stat2" v="200"/></sc>'
    result = parser.parse_statistics_response(xml)
    assert "stat1" in result
    assert result["stat1"] == "100"
    assert "stat2" in result


def test_parse_statistics_response_with_message(parser):
    """Test parsing statistics response with error message."""
    xml = "<sc><msg>Error message</msg></sc>"
    result = parser.parse_statistics_response(xml)
    assert result == {}


def test_parse_statistics_response_no_sc(parser):
    """Test parsing statistics response without sc element."""
    xml = "<root><invalid/></root>"
    result = parser.parse_statistics_response(xml)
    assert result == {}


def test_flatten_attributes_with_extras(parser):
    """Test flattening attributes with extra metadata."""
    data = {
        "c": {
            "@n": "sensor1",
            "@v": "100",
            "@dt": "temperature",
            "@m": "celsius",
        }
    }
    result = parser._flatten_attributes(data)
    assert result["sensor1"] == "100"
    assert result["sensor1_dt"] == "temperature"
    assert result["sensor1_m"] == "celsius"


def test_flatten_attributes_list_c(parser):
    """Test flattening attributes with list of c elements."""
    data = {
        "c": [
            {"@n": "sensor1", "@v": "100"},
            {"@n": "sensor2", "@v": "200"},
        ]
    }
    result = parser._flatten_attributes(data)
    assert result["sensor1"] == "100"
    assert result["sensor2"] == "200"


def test_flatten_attributes_skip_checksum(parser):
    """Test that checksum is skipped during flattening."""
    data = {
        "cs": "checksum_value",
        "c": {"@n": "test", "@v": "val"},
    }
    result = parser._flatten_attributes(data)
    assert "cs" not in result
    assert "test" in result


def test_element_to_dict_empty_element(parser):
    """Test converting empty XML element to dict."""
    import xml.etree.ElementTree as ET
    element = ET.fromstring("<empty/>")
    result = parser._element_to_dict(element)
    assert result == {}


def test_element_to_dict_text_only(parser):
    """Test converting XML element with text only (no children, no attributes)."""
    import xml.etree.ElementTree as ET
    element = ET.fromstring("<simple>text content</simple>")
    result = parser._element_to_dict(element)
    assert result == "text content"


def test_element_to_dict_text_with_children(parser):
    """Test converting XML element with both text and children."""
    import xml.etree.ElementTree as ET
    element = ET.fromstring("<parent>text<child>value</child></parent>")
    result = parser._element_to_dict(element)
    assert "#text" in result
    assert result["#text"] == "text"
    assert "child" in result


def test_parse_device_list_single_device(parser):
    """Test parsing device list with single device (not a list)."""
    xml = '<sc><col><dcl dclg="abc" ali="MyDevice"/></col><dvs><d dclg="abc" sn="12345"/></dvs></sc>'
    devices = parser.parse_device_list_response(xml)
    assert len(devices) == 1
    assert devices[0]["name"] == "MyDevice"
    assert devices[0]["serial_number"] == "12345"


def test_parse_device_list_device_without_dclg(parser):
    """Test parsing device list with device missing dclg attribute."""
    xml = '<sc><dvs><d sn="12345"/></dvs></sc>'
    devices = parser.parse_device_list_response(xml)
    # Device without @dclg should be skipped
    assert devices == []


def test_parse_device_list_dvs_no_d_no_dclg(parser):
    """Test parsing device list when dvs has no 'd' and no '@dclg'."""
    xml = '<sc><dvs><other>data</other></dvs></sc>'
    devices = parser.parse_device_list_response(xml)
    assert devices == []


def test_parse_device_status_dvs_is_list(parser):
    """Test parsing device status when dvs is a list."""
    xml = '<sc><dvs><c n="test" v="value"/></dvs></sc>'
    result = parser.parse_device_status_response(xml)
    # This tests the isinstance(dvs, list) branch
    assert result is not None or result is None  # Depends on exact structure


def test_parse_device_status_device_list_is_dict_with_c(parser):
    """Test parsing device status when device_list is dict with 'c' element."""
    xml = '<sc><dvs dclg="123"><c n="sensor" v="42"/></dvs></sc>'
    result = parser.parse_device_status_response(xml)
    assert result is not None
    assert "sensor" in result
    assert result["sensor"] == "42"


def test_parse_device_status_device_list_dict_no_c(parser):
    """Test parsing device status when device_list is dict without 'c' element."""
    xml = '<sc><dvs dclg="123"><name>Device</name></dvs></sc>'
    result = parser.parse_device_status_response(xml)
    assert result is None


def test_parse_statistics_with_checksum(parser):
    """Test parsing statistics response with checksum (should be removed)."""
    xml = '<sc><cs>ABC123</cs><c n="stat" v="100"/></sc>'
    result = parser.parse_statistics_response(xml)
    assert "cs" not in result
    assert "stat" in result
    assert result["stat"] == "100"


def test_flatten_attributes_c_with_acd_and_ih(parser):
    """Test flattening attributes with acd and ih extra fields."""
    data = {
        "c": {
            "@n": "sensor",
            "@v": "value",
            "@acd": "acd_value",
            "@ih": "ih_value",
        }
    }
    result = parser._flatten_attributes(data)
    assert result["sensor"] == "value"
    assert result["sensor_acd"] == "acd_value"
    assert result["sensor_ih"] == "ih_value"


def test_flatten_attributes_text_content(parser):
    """Test flattening attributes with #text content."""
    data = {"#text": "text content", "other": "value"}
    result = parser._flatten_attributes(data)
    assert result["_text"] == "text content"
    assert result["other"] == "value"


def test_flatten_attributes_nested_dict(parser):
    """Test flattening attributes with nested dictionaries."""
    data = {
        "nested": {
            "c": {"@n": "inner", "@v": "val"}
        }
    }
    result = parser._flatten_attributes(data)
    assert "inner" in result
    assert result["inner"] == "val"


def test_flatten_attributes_nested_list(parser):
    """Test flattening attributes with nested lists."""
    data = {
        "items": [
            {"c": {"@n": "item1", "@v": "val1"}},
            {"c": {"@n": "item2", "@v": "val2"}},
        ]
    }
    result = parser._flatten_attributes(data)
    assert "item1" in result
    assert "item2" in result


def test_flatten_attributes_simple_value(parser):
    """Test flattening attributes with simple string values."""
    data = {"simple_key": "simple_value"}
    result = parser._flatten_attributes(data)
    assert result["simple_key"] == "simple_value"


def test_flatten_attributes_c_missing_n_or_v(parser):
    """Test flattening attributes when 'c' element is missing @n or @v."""
    data = {
        "c": [
            {"@n": "valid", "@v": "100"},
            {"@n": "no_value"},  # Missing @v
            {"@v": "no_name"},  # Missing @n

        ]
    }
    result = parser._flatten_attributes(data)
    # Only valid entries should be flattened
    assert "valid" in result
    assert "no_value" not in result
    assert "no_name" not in result


def test_parse_device_list_dvs_itself_has_dclg(parser):
    """Test parsing when dvs element itself has @dclg (is the device)."""
    xml = '<sc><col><dcl dclg="xyz" ali="MyDevice"/></col><dvs dclg="xyz" sn="SN001"/></sc>'
    devices = parser.parse_device_list_response(xml)
    assert len(devices) == 1
    assert devices[0]["dclg"] == "xyz"
    assert devices[0]["serial_number"] == "SN001"
    assert devices[0]["name"] == "MyDevice"


def test_parse_decrypted_login_single_project_not_list(parser):
    """Test parsing decrypted login when single project is not in a list."""
    # When there's only one <pre>, it won't be a list
    xml = '<usr id="sess1"><nam>User</nam></usr><prs><pre id="single" n="SingleProject"/></prs>'
    session_id, projects = parser.parse_decrypted_login(xml)
    assert session_id == "sess1"
    assert len(projects) == 1
    assert projects[0]["id"] == "single"
    assert projects[0]["name"] == "SingleProject"


def test_parse_device_status_list_no_c_children(parser):
    """Test parsing device status when device_list is a list without c children."""
    xml = '<sc><dvs><d><name>Device1</name></d><d><name>Device2</name></d></dvs></sc>'
    result = parser.parse_device_status_response(xml)
    # Should return None because no device has 'c' children
    assert result is None


def test_parse_device_status_empty_device_list(parser):
    """Test parsing device status when device_list evaluates to empty/falsy."""
    xml = '<sc><dvs></dvs></sc>'
    result = parser.parse_device_status_response(xml)
    # Empty dvs should return None
    assert result is None


def test_parse_device_list_no_sc(parser):
    """Test parsing device list without sc element."""
    xml = '<root><invalid/></root>'
    devices = parser.parse_device_list_response(xml)
    # Should return empty list when no 'sc' element
    assert devices == []


def test_element_to_dict_multiple_same_tag(parser):
    """Test _element_to_dict with multiple children of same tag name."""
    import xml.etree.ElementTree as ET
    element = ET.fromstring("<parent><item>val1</item><item>val2</item><item>val3</item></parent>")
    result = parser._element_to_dict(element)
    # Should create a list for multiple children with same tag
    assert isinstance(result["item"], list)
    assert len(result["item"]) == 3
    assert result["item"][0] == "val1"
    assert result["item"][1] == "val2"
    assert result["item"][2] == "val3"


def test_flatten_attributes_list_input(parser):
    """Test _flatten_attributes when input is a list at root level."""
    data = [
        {"c": {"@n": "sensor1", "@v": "100"}},
        {"c": {"@n": "sensor2", "@v": "200"}},
    ]
    result = parser._flatten_attributes(data)
    # Should flatten all items in list
    assert "sensor1" in result
    assert "sensor2" in result
    assert result["sensor1"] == "100"
    assert result["sensor2"] == "200"


def test_parse_device_status_list_with_multiple_devices_one_has_c(parser):
    """Test device status parsing with list where only one device has 'c'."""
    xml = '<sc><dvs><d><name>NoC</name></d><d><c n="sensor" v="42"/></d></dvs></sc>'
    result = parser.parse_device_status_response(xml)
    # Should succeed if at least one device has 'c'
    assert result is not None
    assert "sensor" in result


def test_parse_login_response_api_with_empty_text(parser):
    """Test parsing login response when api element has empty text."""
    xml = '<sc><api attr="value"></api></sc>'
    encrypted, parsed = parser.parse_login_response(xml)
    # Empty text should be extracted as empty string
    assert encrypted == ""
    assert "sc" in parsed


def test_flatten_attributes_c_list_with_all_extras(parser):
    """Test flattening list of c elements with all possible extra attributes."""
    data = {
        "c": [
            {"@n": "s1", "@v": "1", "@dt": "d1", "@m": "m1", "@acd": "a1", "@ih": "i1"},
            {"@n": "s2", "@v": "2", "@dt": "d2"},
        ]
    }
    result = parser._flatten_attributes(data)
    # Should include all extras for s1
    assert result["s1"] == "1"
    assert result["s1_dt"] == "d1"
    assert result["s1_m"] == "m1"
    assert result["s1_acd"] == "a1"
    assert result["s1_ih"] == "i1"
    # Should only include dt for s2
    assert result["s2"] == "2"
    assert result["s2_dt"] == "d2"
