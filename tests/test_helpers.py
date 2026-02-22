"""Tests for helpers module."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.syr_connect.helpers import (
    build_device_info,
    build_entity_id,
    get_sensor_vol_value,
    get_sensor_avo_value,
    get_current_mac,
    get_sensor_bat_value,
    get_sensor_ala_map,
    get_sensor_not_map,
    get_sensor_wrn_map,
    get_sensor_ab_value,
)


def test_build_entity_id() -> None:
    """Test entity ID building."""
    entity_id = build_entity_id("sensor", "DEVICE123", "getPRS")
    
    assert entity_id == "sensor.syr_connect_device123_getprs"


def test_build_device_info() -> None:
    """Test device info building."""
    coordinator_data = {
        "devices": [
            {
                "id": "DEVICE123",
                "name": "Test Device",
                "status": {
                    "getCNA": "LEXplus10S",
                    "getVER": "1.0.0",
                    "getFIR": "SLPS",
                    "getMAC": "00:11:22:33:44:55",
                },
            }
        ]
    }
    
    device_info = build_device_info("DEVICE123", "Test Device", coordinator_data)
    
    assert device_info["name"] == "Test Device"
    assert device_info["manufacturer"] == "SYR"
    assert device_info["model"] == "LEX Plus 10 S Connect"
    assert device_info["sw_version"] == "1.0.0"
    assert device_info["hw_version"] == "SLPS"
    assert device_info["serial_number"] == "DEVICE123"
    assert ("mac", "00:11:22:33:44:55") in device_info["connections"]


def test_build_device_info_minimal() -> None:
    """Test device info building with minimal data."""
    coordinator_data = {
        "devices": [
            {
                "id": "DEVICE123",
                "name": "Test Device",
                "status": {},
            }
        ]
    }
    
    device_info = build_device_info("DEVICE123", "Test Device", coordinator_data)
    
    assert device_info["name"] == "Test Device"
    assert device_info["manufacturer"] == "SYR"
    assert device_info["model"] == "Unknown model"  # Fallback
    assert device_info["serial_number"] == "DEVICE123"


def test_get_sensor_avo_value() -> None:
    """Test flow value extraction from strings."""
    # Test standard format - values in mL converted to L
    assert get_sensor_avo_value("1655mL") == 1.655
    assert get_sensor_avo_value("0mL") == 0.0
    assert get_sensor_avo_value("999mL") == 0.999
    assert get_sensor_avo_value("1000mL") == 1.0
    
    # Test numeric inputs - treated as mL and converted to L
    assert get_sensor_avo_value(1655) == 1.655
    assert get_sensor_avo_value(0) == 0.0
    assert get_sensor_avo_value(100.5) == 0.1005
    
    # Test None input
    assert get_sensor_avo_value(None) is None
    
    # Test fallback: extract number at start and convert to L
    assert get_sensor_avo_value("1655") == 1.655
    assert get_sensor_avo_value("100abc") == 0.1
    
    # Test invalid inputs
    assert get_sensor_avo_value("mL") is None
    assert get_sensor_avo_value("abc") is None
    assert get_sensor_avo_value("") is None
    assert get_sensor_avo_value("no numbers here") is None


# Tests merged from test_clean_sensor_value.py
def test_clean_value_with_prefix() -> None:
    """Test cleaning value with prefix like 'Vol[L]6530'."""
    assert get_sensor_vol_value("Vol[L]6530") == "6530"
    assert get_sensor_vol_value("Temp[C]25") == "25"
    assert get_sensor_vol_value("Press[bar]48") == "48"


def test_clean_value_with_prefix_and_decimals() -> None:
    """Test cleaning value with prefix and decimal numbers."""
    assert get_sensor_vol_value("Vol[L]123.45") == "123.45"
    assert get_sensor_vol_value("Temp[C]25.5") == "25.5"


def test_clean_value_with_prefix_and_spaces() -> None:
    """Test cleaning value with prefix and extra spaces."""
    assert get_sensor_vol_value("Vol[L] 6530") == "6530"
    assert get_sensor_vol_value("Temp[C]  25") == "25"


def test_clean_value_numeric_passthrough() -> None:
    """Test that numeric values pass through unchanged."""
    assert get_sensor_vol_value(6530) == 6530
    assert get_sensor_vol_value(123.45) == 123.45
    assert get_sensor_vol_value(0) == 0


def test_clean_value_string_without_prefix() -> None:
    """Test that strings without prefix pass through unchanged."""
    assert get_sensor_vol_value("6530") == "6530"
    assert get_sensor_vol_value("123.45") == "123.45"
    assert get_sensor_vol_value("normal_string") == "normal_string"
    assert get_sensor_vol_value("") == ""


def test_clean_value_complex_strings() -> None:
    """Test that complex strings without matching pattern pass through."""
    assert get_sensor_vol_value("Status: Active") == "Status: Active"
    assert get_sensor_vol_value("Error[123]") == "Error[123]"  # No value after bracket
    assert get_sensor_vol_value("Test") == "Test"


def test_get_current_mac_empty_and_none() -> None:
    """Empty or None status returns None."""
    assert get_current_mac({}) is None


def test_get_current_mac_priority_getIPA() -> None:
    """If getIPA present, prefer getMAC."""
    status = {
        "getIPA": "1.2.3.4",
        "getMAC": "AA:BB:CC:DD:EE:FF",
        "getMAC1": "11:22:33:44:55:66",
        "getMAC2": "77:88:99:AA:BB:CC",
    }
    assert get_current_mac(status) == "AA:BB:CC:DD:EE:FF"


def test_get_current_mac_getIPA_mac_empty_fallback() -> None:
    """If preferred MAC is empty, fall back to first available MAC."""
    status = {
        "getIPA": "1.2.3.4",
        "getMAC": "   ",  # whitespace should be treated as empty
        "getMAC1": "11:22:33:44:55:66",
    }
    assert get_current_mac(status) == "11:22:33:44:55:66"


def test_get_current_mac_zero_ip_treated_as_empty() -> None:
    """An IP value of '0.0.0.0' should be treated as empty and fall back."""
    status = {
        "getIPA": "0.0.0.0",
        "getMAC": "   ",  # preferred MAC empty
        "getMAC1": "11:22:33:44:55:66",
    }
    assert get_current_mac(status) == "11:22:33:44:55:66"


def test_get_current_mac_priority_getWIP_and_getEIP() -> None:
    """Test selection when getWIP/getEIP are present."""
    status_wip = {"getWIP": "10.0.0.1", "getMAC1": "11:11:11:11:11:11"}
    assert get_current_mac(status_wip) == "11:11:11:11:11:11"

    status_eip = {"getEIP": "10.0.0.2", "getMAC2": "22:22:22:22:22:22"}
    assert get_current_mac(status_eip) == "22:22:22:22:22:22"


def test_get_sensor_bat_value_variants() -> None:
    """Test parsing of battery voltage in various formats."""
    # Safe-T+ multi-value -> take first token and parse comma as decimal
    assert get_sensor_bat_value("6,12 4,38 3,90") == 6.12

    # Digits-only Trio format -> divide by 100
    assert get_sensor_bat_value("363") == 3.63

    # Numeric input (int/float) assumed in 1/100 V -> divide
    assert get_sensor_bat_value(363) == 3.63
    assert get_sensor_bat_value(363.0) == 3.63

    # Empty or invalid -> None
    assert get_sensor_bat_value("") is None
    assert get_sensor_bat_value(None) is None
    assert get_sensor_bat_value("not-a-number") is None


def test_clean_sensor_vol_value() -> None:
    """Clean sensor values with and without prefixes."""
    assert get_sensor_vol_value("Vol[L]6530") == "6530"
    # Non-matching string should be returned unchanged
    assert get_sensor_vol_value("plain_value") == "plain_value"
    # Non-string values are returned unchanged
    assert get_sensor_vol_value(123) == 123
    assert get_sensor_vol_value(12.34) == 12.34


def test_get_sensor_rtm_and_setters() -> None:
    """Test parsing and building of regeneration time values."""
    from custom_components.syr_connect.helpers import (
        get_sensor_rtm_value,
        set_sensor_rtm_value,
    )

    # Combined representation: getRTM contains HH:MM
    status_combined = {"getRTM": "02:05", "getRTH": None}
    assert get_sensor_rtm_value(status_combined) == "02:05"

    # Separate numeric values
    status_sep = {"getRTH": "2", "getRTM": "30"}
    assert get_sensor_rtm_value(status_sep) == "02:30"

    # Invalid combined string
    status_bad = {"getRTM": "bad", "getRTH": None}
    assert get_sensor_rtm_value(status_bad) is None

    # set_sensor_rtm_value: combined mode should return single setRTM
    status_for_set = {"getRTH": None, "getRTM": "02:30"}
    cmds = set_sensor_rtm_value(status_for_set, "03:45")
    assert cmds == [("setRTM", "03:45")]

    # set_sensor_rtm_value: separate mode returns two commands
    status_for_set2 = {"getRTH": "1", "getRTM": "15"}
    cmds2 = set_sensor_rtm_value(status_for_set2, "04:20")
    assert ("setRTH", 4) in cmds2 and ("setRTM", 20) in cmds2


def test_get_sensor_ab_and_build_command() -> None:
    """Test parsing of getAB and building set commands."""
    from custom_components.syr_connect.helpers import (
        get_sensor_ab_value,
        build_set_ab_command,
    )

    # Numeric values
    assert get_sensor_ab_value({"getAB": 2}) is True
    assert get_sensor_ab_value({"getAB": 1}) is False

    # String boolean-like
    assert get_sensor_ab_value({"getAB": "true"}) is True
    assert get_sensor_ab_value({"getAB": "false"}) is False

    # Numeric string
    assert get_sensor_ab_value({"getAB": "2"}) is True

    # Invalid or missing
    assert get_sensor_ab_value({}) is None
    assert get_sensor_ab_value({"getAB": "x"}) is None

    # build_set_ab_command: prefer boolean-string if raw looks boolean
    assert build_set_ab_command({"getAB": "true"}, closed=True) == ("setAB", "true")
    assert build_set_ab_command({"getAB": True}, closed=False) == ("setAB", "false")
    # fallback numeric
    assert build_set_ab_command({"getAB": None}, closed=True) == ("setAB", 2)


def test_sensor_code_mappings_and_unknown_model() -> None:
    """Test ALA/NOT/WRN mapping functions and unknown-model behavior."""

    # ALA: LEX family (detect via getCNA)
    status_lex = {"getCNA": "LEXplus10S"}
    mapped, raw = get_sensor_ala_map(status_lex, "0")
    assert mapped == "no_alarm" and raw == "0"

    # ALA: NeoSoft family (detect via getVER prefix and v_keys)
    status_neo = {"getVER": "NSS-1", "getRE1": "x", "getRE2": "y"}
    mapped2, raw2 = get_sensor_ala_map(status_neo, "FF")
    assert mapped2 == "no_alarm" and raw2 == "FF"

    # ALA: Safe-T+ family (detect via getVER contains)
    status_safet = {"getVER": "Something Safe-T Something"}
    mapped3, raw3 = get_sensor_ala_map(status_safet, "A1")
    assert mapped3 == "alarm_end_switch" and raw3 == "A1"

    # ALA: unknown model -> returns (None, raw)
    mapped4, raw4 = get_sensor_ala_map({}, "A5")
    assert mapped4 is None and raw4 == "A5"

    # NOT mapping
    mapped_not, raw_not = get_sensor_not_map({}, "01")
    assert mapped_not == "new_software_available" and raw_not == "01"
    mapped_not2, raw_not2 = get_sensor_not_map({}, "")
    assert mapped_not2 == "no_notification" and raw_not2 == ""

    # WRN mapping
    mapped_wrn, raw_wrn = get_sensor_wrn_map({}, "02")
    assert mapped_wrn == "salt_supply_low" and raw_wrn == "02"
    mapped_wrn2, raw_wrn2 = get_sensor_wrn_map({}, None)
    assert mapped_wrn2 is None and raw_wrn2 == ""


def test_get_sensor_ab_string_numeric_edge() -> None:
    """Cover numeric-string branch for getAB ('1' -> False)."""

    assert get_sensor_ab_value({"getAB": "1"}) is False


def test_mapping_none_inputs() -> None:
    """Ensure mapping functions handle None/empty raw codes."""
    mapped_ala, raw_ala = get_sensor_ala_map({}, None)
    assert mapped_ala is None and raw_ala == ""

    mapped_not, raw_not = get_sensor_not_map({}, None)
    assert mapped_not is None and raw_not == ""

