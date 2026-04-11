"""Tests for helpers module."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from custom_components.syr_connect import helpers
from custom_components.syr_connect.const import API_TYPE_JSON
from custom_components.syr_connect.helpers import (
    build_device_info,
    build_entity_id,
    get_current_mac,
    get_sensor_ab_value,
    get_sensor_ala_map,
    get_sensor_avo_value,
    get_sensor_bat_value,
    get_sensor_lng_value,
    get_sensor_net_value,
    get_sensor_not_map,
    get_sensor_vol_value,
    get_sensor_wrn_map,
    is_sensor_visible,
)


def test_get_default_scan_interval_for_entry_none():
    assert helpers.get_default_scan_interval_for_entry(None) == helpers._SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT


def test_get_default_scan_interval_for_entry_options_and_data():
    # Use an object with attributes (ConfigEntry-like) rather than a plain dict
    entry = SimpleNamespace(options={helpers._SYR_CONNECT_SCAN_INTERVAL_CONF: "30"}, data={helpers.CONF_API_TYPE: API_TYPE_JSON})
    assert helpers.get_default_scan_interval_for_entry(entry) == 30

    # invalid option falls back to API default
    entry = SimpleNamespace(options={helpers._SYR_CONNECT_SCAN_INTERVAL_CONF: "bad"}, data={helpers.CONF_API_TYPE: API_TYPE_JSON})
    assert helpers.get_default_scan_interval_for_entry(entry) == helpers._SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT


def test_build_device_info_fallback_and_entity_id_additional():
    # No device info in coordinator -> fallback model
    coord = {"devices": []}
    di = helpers.build_device_info("dev123", "My Dev", coord)
    # DeviceInfo is a mapping-like object; assert via keys
    assert di["serial_number"] == "dev123"
    assert di["model"] == "Unknown model"
    # entity id builder
    assert helpers.build_entity_id("sensor", "DevID", "getFOO").startswith("sensor.")


def test_registry_cleanup_handles_exception():
    hass = MagicMock()
    # Make er.async_get raise
    with patch("custom_components.syr_connect.helpers.er.async_get", side_effect=RuntimeError("boom")):
        # Should not raise
        helpers.registry_cleanup(hass, {"devices": [{"id": "DEV"}]}, "sensor", allowed_keys={"getPRS"})


def test_get_current_mac_priorities_additional():
    # Primary IP -> getMAC
    s = {"getIPA": "192.168.1.2", "getMAC": "AA:BB:CC"}
    assert helpers.get_current_mac(s) == "AA:BB:CC"

    # WiFi IP with WFS==2 -> getMAC1
    s = {"getWIP": "192.168.1.3", "getWFS": "2", "getMAC1": "11:22:33"}
    assert helpers.get_current_mac(s) == "11:22:33"

    # Ethernet IP -> getMAC2
    s = {"getEIP": "10.0.0.1", "getMAC2": "22:33:44"}
    assert helpers.get_current_mac(s) == "22:33:44"

    # Empty status
    assert helpers.get_current_mac({}) is None


def test_get_sensor_avo_value_variants_additional():
    assert helpers.get_sensor_avo_value(None) is None
    assert helpers.get_sensor_avo_value(1655) == 1.655
    assert helpers.get_sensor_avo_value("1655mL") == 1.655
    assert helpers.get_sensor_avo_value("1655") == 1.655
    assert helpers.get_sensor_avo_value("bad") is None


def test_get_sensor_vol_value_additional():
    assert helpers.get_sensor_vol_value(6530) == 6530
    assert helpers.get_sensor_vol_value("") is None
    assert helpers.get_sensor_vol_value("Vol[L]6530") == "6530"
    assert helpers.get_sensor_vol_value("Xyz123") == "Xyz123"


def test_get_sensor_bat_value_formats_additional():
    assert helpers.get_sensor_bat_value(None) is None
    assert helpers.get_sensor_bat_value(363) == 3.63
    assert helpers.get_sensor_bat_value("6,11 4,38 3,90") == 6.11
    assert helpers.get_sensor_bat_value("9,36") == 9.36
    assert helpers.get_sensor_bat_value("bad") is None


def test_get_sensor_rtm_and_set_additional():
    # Combined string representation
    status = {"getRTH": "", "getRTM": "07:30"}
    assert helpers.get_sensor_rtm_value(status) == "07:30"
    assert helpers.set_sensor_rtm_value(status, "08:15") == [("setRTM", "08:15")]

    # Separate numeric representation
    status = {"getRTH": "7", "getRTM": "30"}
    assert helpers.get_sensor_rtm_value(status) == "07:30"
    assert helpers.set_sensor_rtm_value(status, "09:45") == [("setRTH", 9), ("setRTM", 45)]

    # Invalid option
    assert helpers.set_sensor_rtm_value(status, "bad") == []


def test_get_sensor_ab_and_build_set_additional():
    assert helpers.get_sensor_ab_value(None) is None
    assert helpers.get_sensor_ab_value({"getAB": True}) is True
    assert helpers.get_sensor_ab_value({"getAB": 2}) is True
    assert helpers.get_sensor_ab_value({"getAB": 1}) is False
    assert helpers.get_sensor_ab_value({"getAB": "true"}) is True
    assert helpers.get_sensor_ab_value({"getAB": "2"}) is True

    # build set command mirrors device format
    assert helpers.build_set_ab_command({"getAB": "true"}, False) == ("setAB", "false")
    assert helpers.build_set_ab_command({"getAB": True}, False) == ("setAB", "false")
    assert helpers.build_set_ab_command({"getAB": 1}, True) == ("setAB", 2)
    assert helpers.build_set_ab_command({"getAB": "1"}, True) == ("setAB", 2)


def test_get_sensor_maps_and_visibility_additional():
    # NOT/WRN mapping
    assert helpers.get_sensor_not_map({}, "01")[0] == "new_software_available"
    assert helpers.get_sensor_wrn_map({}, "01")[0] == "power_outage"

    # ALA mapping with detected model
    status = {"getCNA": "LEXplus10"}
    assert helpers.get_sensor_ala_map(status, "0")[0] == "no_alarm"

    # Unknown model returns None mapping and raw code
    assert helpers.get_sensor_ala_map({}, "A5")[0] is None

    # Visibility rules
    status = {"getPA1": "true", "getPV1": "5"}
    assert helpers.is_sensor_visible(status, "getPV1", "1") is True
    # getRTIME is not in the allowlist, so it is never passed to is_sensor_visible;
    # the function only applies visibility rules, not exclusions.
    assert helpers.is_sensor_visible({}, "getRTIME", "x") is True


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
                    "getIPA": "192.168.178.100",  # Added to trigger MAC detection
                },
            }
        ]
    }

    device_info = build_device_info("DEVICE123", "Test Device", coordinator_data)

    assert device_info["name"] == "Test Device"
    assert device_info["manufacturer"] == "SYR"  # LEXplus10S is a SYR device
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
    assert device_info["manufacturer"] == "Unknown"  # Fallback when model is undetected
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
    assert get_sensor_vol_value("") is None


def test_clean_value_complex_strings() -> None:
    """Test that complex strings without matching pattern pass through."""
    assert get_sensor_vol_value("Status: Active") == "Status: Active"
    assert get_sensor_vol_value("Error[123]") == "Error[123]"  # No value after bracket
    assert get_sensor_vol_value("Test") == "Test"


def test_get_current_mac_empty_and_none() -> None:
    """Empty or None status returns None."""
    assert get_current_mac({}) is None


def test_get_current_mac_priority_getipa() -> None:
    """If getIPA present, prefer getMAC."""
    status = {
        "getIPA": "1.2.3.4",
        "getMAC": "AA:BB:CC:DD:EE:FF",
        "getMAC1": "11:22:33:44:55:66",
        "getMAC2": "77:88:99:AA:BB:CC",
    }
    assert get_current_mac(status) == "AA:BB:CC:DD:EE:FF"


def test_get_current_mac_getipa_mac_empty_fallback() -> None:
    """If preferred MAC is empty, fall back to first available MAC."""
    status = {
        "getIPA": "1.2.3.4",
        "getMAC": "   ",  # whitespace should be treated as empty
        "getWIP": "192.168.178.21",
        "getMAC1": "11:22:33:44:55:66",
        "getWFS": 2,
    }
    assert get_current_mac(status) == "11:22:33:44:55:66"


def test_get_current_mac_zero_ip_treated_as_empty() -> None:
    """An IP value of '0.0.0.0' should be treated as empty and fall back."""
    status = {
        "getIPA": "0.0.0.0",
        "getMAC": "   ",  # preferred MAC empty
        "getWIP": "192.168.178.22",
        "getMAC1": "11:22:33:44:55:66",
        "getWFS": 2,
    }
    assert get_current_mac(status) == "11:22:33:44:55:66"


def test_get_current_mac_priority_getwip_and_geteip() -> None:
    """Test selection when getWIP/getEIP are present."""
    status_wip = {"getWIP": "10.0.0.1", "getMAC1": "11:11:11:11:11:11", "getWFS": 2}
    assert get_current_mac(status_wip) == "11:11:11:11:11:11"

    status_eip = {"getEIP": "10.0.0.2", "getMAC2": "22:22:22:22:22:22"}
    assert get_current_mac(status_eip) == "22:22:22:22:22:22"


def test_get_current_mac_non_string_ip_value() -> None:
    """Test that non-string IP values (int, float, bool, etc.) are treated as present.

    This covers the case where is_not_empty_ip returns True for non-string values
    (line 130 in helpers.py).
    """
    # IP value as int should be treated as present
    status_int = {"getIPA": 123456, "getMAC": "AA:BB:CC:DD:EE:FF"}
    assert get_current_mac(status_int) == "AA:BB:CC:DD:EE:FF"

    # IP value as float should be treated as present
    status_float = {"getWIP": 192.168, "getMAC1": "11:22:33:44:55:66", "getWFS": 2}
    assert get_current_mac(status_float) == "11:22:33:44:55:66"

    # IP value as bool should be treated as present
    status_bool = {"getEIP": True, "getMAC2": "77:88:99:AA:BB:CC"}
    assert get_current_mac(status_bool) == "77:88:99:AA:BB:CC"


def test_get_sensor_bat_value_variants() -> None:
    """Test parsing of battery voltage in various formats."""
    # Safe-T+ multi-value -> take first token and parse comma as decimal
    assert get_sensor_bat_value("6,12 4,38 3,90") == 6.12

    # Safe-Tech+ single value with comma decimal
    assert get_sensor_bat_value("9,36") == 9.36

    # Digits-only Trio format -> divide by 100
    assert get_sensor_bat_value("363") == 3.63

    # Numeric input (int/float) assumed in 1/100 V -> divide
    assert get_sensor_bat_value(363) == 3.63
    assert get_sensor_bat_value(363.0) == 3.63

    # Empty or invalid -> None
    assert get_sensor_bat_value("") is None
    assert get_sensor_bat_value(None) is None
    assert get_sensor_bat_value("not-a-number") is None


def test_get_sensor_net_value_safe_t_plus_format() -> None:
    """Safe-T+ format: 'ADC:950 6,16V' -> 6.16."""
    assert get_sensor_net_value("ADC:950 6,16V") == 6.16


def test_get_sensor_net_value_safe_t_plus_format_uppercase_v() -> None:
    """Safe-T+ format with uppercase V is handled."""
    assert get_sensor_net_value("ADC:950 6,16v") == 6.16


def test_get_sensor_net_value_safe_tech_plus_format() -> None:
    """Safe-Tech+ format: '11,86' -> 11.86."""
    assert get_sensor_net_value("11,86") == 11.86


def test_get_sensor_net_value_trio_format() -> None:
    """Trio DFR/LS format: '363' -> 3.63."""
    assert get_sensor_net_value("363") == 3.63


def test_get_sensor_net_value_numeric_int() -> None:
    """Integer input assumed in 1/100 V -> divide by 100."""
    assert get_sensor_net_value(363) == 3.63


def test_get_sensor_net_value_numeric_float() -> None:
    """Float input assumed in 1/100 V -> divide by 100."""
    assert get_sensor_net_value(363.0) == 3.63


def test_get_sensor_net_value_empty_string() -> None:
    """Empty string returns None."""
    assert get_sensor_net_value("") is None


def test_get_sensor_net_value_none() -> None:
    """None input returns None."""
    assert get_sensor_net_value(None) is None


def test_get_sensor_net_value_invalid_string() -> None:
    """Unrecognized string returns None."""
    assert get_sensor_net_value("not-a-number") is None


def test_get_sensor_net_value_non_str_non_numeric() -> None:
    """Non-string, non-numeric types return None."""
    assert get_sensor_net_value([1, 2, 3]) is None


def test_get_sensor_net_value_adc_format_no_v_token() -> None:
    """ADC: prefix present but no token ending in V returns None."""
    assert get_sensor_net_value("ADC:950 616") is None


def test_get_sensor_net_value_adc_format_unparseable_v_token() -> None:
    """ADC: prefix with non-numeric V token returns None."""
    assert get_sensor_net_value("ADC:950 badV") is None


def test_clean_sensor_vol_value() -> None:
    """Clean sensor values with and without prefixes."""
    assert get_sensor_vol_value("Vol[L]6530") == "6530"
    # Non-matching string should be returned unchanged
    assert get_sensor_vol_value("plain_value") == "plain_value"
    # Non-string values are returned unchanged
    assert get_sensor_vol_value(123) == 123
    assert get_sensor_vol_value(12.34) == 12.34


def test_get_sensor_lng_value_with_annotation() -> None:
    """getLNG value with trailing annotation is stripped to the leading integer."""
    assert get_sensor_lng_value("0 (0=Deutsch 1=English)") == "0"
    assert get_sensor_lng_value("1 (0=Deutsch 1=English)") == "1"


def test_get_sensor_lng_value_plain() -> None:
    """getLNG plain integer string is returned unchanged."""
    assert get_sensor_lng_value("0") == "0"
    assert get_sensor_lng_value("1") == "1"


def test_get_sensor_lng_value_non_string() -> None:
    """Non-string values are returned as-is."""
    assert get_sensor_lng_value(0) == 0
    assert get_sensor_lng_value(1.0) == 1.0


def test_get_sensor_lng_value_empty() -> None:
    """Empty string returns None."""
    assert get_sensor_lng_value("") is None
    assert get_sensor_lng_value("  ") is None


def test_get_sensor_lng_value_non_integer_token() -> None:
    """Non-integer leading token returns the original value unchanged."""
    assert get_sensor_lng_value("unknown") == "unknown"


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


def test_get_sensor_ab_and_build_command(caplog) -> None:
    """Test parsing of getAB and building set commands."""
    from custom_components.syr_connect.helpers import (
        build_set_ab_command,
        get_sensor_ab_value,
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
    assert build_set_ab_command({"getAB": "false"}, closed=True) == ("setAB", "true")
    assert build_set_ab_command({"getAB": True}, closed=False) == ("setAB", "false")
    assert build_set_ab_command({"getAB": False}, closed=True) == ("setAB", "true")
    # native integer (JSON API devices reporting getAB as int 1/2) → numeric
    assert build_set_ab_command({"getAB": 1}, closed=True) == ("setAB", 2)
    assert build_set_ab_command({"getAB": 1}, closed=False) == ("setAB", 1)
    assert build_set_ab_command({"getAB": 2}, closed=True) == ("setAB", 2)
    assert build_set_ab_command({"getAB": 2}, closed=False) == ("setAB", 1)
    # numeric string (XML API and some JSON API devices) → numeric
    assert build_set_ab_command({"getAB": "1"}, closed=True) == ("setAB", 2)
    assert build_set_ab_command({"getAB": "2"}, closed=False) == ("setAB", 1)
    # absent getAB key or explicit None → logs error and returns None
    import logging
    with caplog.at_level(logging.ERROR, logger="custom_components.syr_connect.helpers"):
        result = build_set_ab_command({}, closed=True)
    assert result is None
    assert "unexpected getAB format" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.ERROR, logger="custom_components.syr_connect.helpers"):
        result2 = build_set_ab_command({"getAB": None}, closed=True)
    assert result2 is None
    assert "unexpected getAB format" in caplog.text


def test_sensor_code_mappings_and_unknown_model() -> None:
    """Test ALA/NOT/WRN mapping functions and unknown-model behavior."""

    # ALA: LEX family (detect via getCNA)
    status_lex = {"getCNA": "LEXplus10S"}
    mapped, raw = get_sensor_ala_map(status_lex, "0")
    assert mapped == "no_alarm" and raw == "0"

    # ALA: NeoSoft family (detect via getVER prefix and v_keys)
    status_neo = {"getVER": "NSS.V.2.028", "getRE1": "x", "getRE2": "y"}
    mapped2, raw2 = get_sensor_ala_map(status_neo, "FF")
    assert mapped2 == "no_alarm" and raw2 == "FF"

    # ALA: Safe-T+ family (detect via getVER prefix)
    status_safet = {"getVER": "Safe-T+ V2.00e"}
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


def test_get_sensor_ab_invalid_numeric_values() -> None:
    """Test that invalid numeric values (0, 3, etc.) return None (line 399 in helpers.py).

    Valid values are 1 (open) and 2 (closed). Any other numeric value should return None.
    """
    # Test with int 0 (invalid value)
    assert get_sensor_ab_value({"getAB": 0}) is None

    # Test with int 3 (invalid value)
    assert get_sensor_ab_value({"getAB": 3}) is None

    # Test with other invalid int values
    assert get_sensor_ab_value({"getAB": 5}) is None
    assert get_sensor_ab_value({"getAB": 100}) is None

    # Test with numeric string invalid values
    assert get_sensor_ab_value({"getAB": "0"}) is None
    assert get_sensor_ab_value({"getAB": "3"}) is None
    assert get_sensor_ab_value({"getAB": "999"}) is None


def test_mapping_none_inputs() -> None:
    """Ensure mapping functions handle None/empty raw codes."""
    mapped_ala, raw_ala = get_sensor_ala_map({}, None)
    assert mapped_ala is None and raw_ala == ""

    mapped_not, raw_not = get_sensor_not_map({}, None)
    assert mapped_not is None and raw_not == ""


def test_get_default_scan_interval_for_entry_with_dict() -> None:
    """Entry provided as plain dict should be handled like a mapping."""
    entry = {"options": {helpers._SYR_CONNECT_SCAN_INTERVAL_CONF: "30"}, "data": {helpers.CONF_API_TYPE: API_TYPE_JSON}}
    # Current implementation treats plain dicts as objects and falls back
    # to the legacy XML default when attributes are not present.
    assert helpers.get_default_scan_interval_for_entry(entry) == helpers._SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT


def test_registry_cleanup_remove_called() -> None:
    """Allowlist mode: entity with key NOT in allowed_keys is removed."""
    hass = MagicMock()
    registry = MagicMock()
    device_id = "DEV"
    unlisted_entity_id = build_entity_id("sensor", device_id, "getFOO")
    listed_entity_id = build_entity_id("sensor", device_id, "getPRS")
    registry.entities.values.return_value = [
        SimpleNamespace(entity_id=unlisted_entity_id),
        SimpleNamespace(entity_id=listed_entity_id),
    ]
    registry.async_remove = MagicMock()
    # No conditional entities exist in the registry for this test.
    registry.async_get = MagicMock(return_value=None)

    with patch("custom_components.syr_connect.helpers.er.async_get", return_value=registry):
        coordinator = {"devices": [{"id": device_id}]}
        helpers.registry_cleanup(hass, coordinator, "sensor", allowed_keys={"getPRS"})

    registry.async_remove.assert_called_once_with(unlisted_entity_id)


def test_registry_cleanup_remove_raises_does_not_propagate() -> None:
    """If registry.async_remove raises, cleanup should not propagate the exception."""
    hass = MagicMock()
    registry = MagicMock()
    device_id = "DEV2"
    unlisted_entity_id = build_entity_id("sensor", device_id, "getFOO")
    registry.entities.values.return_value = [SimpleNamespace(entity_id=unlisted_entity_id)]
    registry.async_remove.side_effect = RuntimeError("boom")

    with patch("custom_components.syr_connect.helpers.er.async_get", return_value=registry):
        coordinator = {"devices": [{"id": device_id}]}
        # Should not raise despite async_remove throwing
        helpers.registry_cleanup(hass, coordinator, "sensor", allowed_keys=set())


def test_registry_cleanup_allowed_keys_none_is_noop() -> None:
    """registry_cleanup with allowed_keys=None must return immediately without accessing registry."""
    hass = MagicMock()
    with patch("custom_components.syr_connect.helpers.er.async_get") as mock_get:
        helpers.registry_cleanup(hass, {"devices": [{"id": "DEV"}]}, "sensor", allowed_keys=None)
        mock_get.assert_not_called()


def test_registry_cleanup_skips_device_with_no_id() -> None:
    """Devices without an 'id' key must be silently skipped."""
    hass = MagicMock()
    registry = MagicMock()
    registry.entities.values.return_value = []
    registry.async_remove = MagicMock()

    with patch("custom_components.syr_connect.helpers.er.async_get", return_value=registry):
        # One device with no id, one with empty-string id
        helpers.registry_cleanup(
            hass,
            {"devices": [{"name": "no-id"}, {"id": ""}]},
            "sensor",
            allowed_keys={"getPRS"},
        )

    registry.async_remove.assert_not_called()


def test_registry_cleanup_removes_conditionally_hidden_sensor() -> None:
    """Stale registry entry for a conditionally hidden sensor is removed when value is empty."""
    hass = MagicMock()
    registry = MagicMock()
    device_id = "DEV"
    # getTYP is in EXCLUDED_WHEN_EMPTY_STRING – registry entry exists but device reports ""
    entity_id = build_entity_id("sensor", device_id, "getTYP")
    registry.entities.values.return_value = []
    registry.async_get = MagicMock(return_value=SimpleNamespace(entity_id=entity_id))
    registry.async_remove = MagicMock()

    # Only return an entity entry for the specific entity_id under test.
    registry.async_get = MagicMock(side_effect=lambda eid: SimpleNamespace(entity_id=eid) if eid == entity_id else None)

    coordinator = {"devices": [{"id": device_id, "status": {"getTYP": ""}}]}
    with patch("custom_components.syr_connect.helpers.er.async_get", return_value=registry):
        helpers.registry_cleanup(hass, coordinator, "sensor", allowed_keys={"getTYP"})

    registry.async_remove.assert_called_once_with(entity_id)


def test_registry_cleanup_keeps_conditionally_visible_sensor() -> None:
    """Registry entry for a conditionally shown sensor is NOT removed when value is non-empty."""
    hass = MagicMock()
    registry = MagicMock()
    device_id = "DEV"
    # getTYP is in EXCLUDED_WHEN_EMPTY_STRING – device reports a real value
    entity_id = build_entity_id("sensor", device_id, "getTYP")
    registry.entities.values.return_value = []
    registry.async_get = MagicMock(return_value=SimpleNamespace(entity_id=entity_id))
    registry.async_remove = MagicMock()

    # Only return an entity entry for the specific entity_id under test.
    registry.async_get = MagicMock(side_effect=lambda eid: SimpleNamespace(entity_id=eid) if eid == entity_id else None)

    coordinator = {"devices": [{"id": device_id, "status": {"getTYP": "SafeTech"}}]}
    with patch("custom_components.syr_connect.helpers.er.async_get", return_value=registry):
        helpers.registry_cleanup(hass, coordinator, "sensor", allowed_keys={"getTYP"})

    registry.async_remove.assert_not_called()


def test_registry_cleanup_conditional_only_applies_to_sensor_domain() -> None:
    """Conditional hidden-sensor cleanup must NOT run for non-sensor domains."""
    hass = MagicMock()
    registry = MagicMock()
    device_id = "DEV"
    # getTYP is conditionally hidden – but domain is "binary_sensor", so no removal expected
    entity_id = build_entity_id("binary_sensor", device_id, "getTYP")
    registry.entities.values.return_value = []
    registry.async_get = MagicMock(return_value=SimpleNamespace(entity_id=entity_id))
    registry.async_remove = MagicMock()

    coordinator = {"devices": [{"id": device_id, "status": {"getTYP": ""}}]}
    with patch("custom_components.syr_connect.helpers.er.async_get", return_value=registry):
        helpers.registry_cleanup(hass, coordinator, "binary_sensor", allowed_keys={"getTYP"})

    registry.async_remove.assert_not_called()



    # Wi-Fi present but WFS indicates not connected
    status = {"getWIP": "10.0.0.5", "getWFS": "1", "getMAC1": "11:11:11:11:11:11"}
    assert get_current_mac(status) is None

    # Wi-Fi present but WFS unparsable -> skip Wi-Fi MAC
    status2 = {"getWIP": "10.0.0.6", "getWFS": "bad", "getMAC1": "22:22:22:22:22:22"}
    assert get_current_mac(status2) is None


def test_get_sensor_rtm_invalid_values() -> None:
    """Invalid RTM strings (out-of-range) should return None."""
    assert helpers.get_sensor_rtm_value({"getRTH": "", "getRTM": "24:00"}) is None
    assert helpers.get_sensor_rtm_value({"getRTH": "", "getRTM": "12:60"}) is None


def test_get_sensor_ala_map_detect_model_raises() -> None:
    """If detect_model raises an exception, get_sensor_ala_map should return (None, raw)."""
    with patch("custom_components.syr_connect.helpers.detect_model", side_effect=ValueError("boom")):
        mapped, raw = helpers.get_sensor_ala_map({}, "A1")
        assert mapped is None and raw == "A1"


def test_is_sensor_visible_group_control_and_cs_and_empty_ip() -> None:
    """Test group-controlled visibility, CS special-case, and empty-IP exclusions."""
    # Group-controlled: getPA1 false -> getPV1 hidden
    status = {"getPA1": "0"}
    assert not helpers.is_sensor_visible(status, "getPV1", "1")

    # CS1 visible when corresponding getSV1 non-zero even if value is '0'
    status2 = {"getSV1": 5}
    assert helpers.is_sensor_visible(status2, "getCS1", "0") is True

    # Empty-IP exclusion: pick a key from the exclusion set
    key_ip = next(iter(helpers._SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_IPADDRESS))
    assert helpers.is_sensor_visible({}, key_ip, "0.0.0.0") is False


def test_get_default_scan_interval_entry_getattr_raises() -> None:
    """If accessing attributes on entry raises, function should handle it and return XML default."""

    class BadEntry:
        @property
        def options(self):
            raise AttributeError("no options")

        @property
        def data(self):
            raise AttributeError("no data")

    be = BadEntry()
    assert helpers.get_default_scan_interval_for_entry(be) == helpers._SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT


def test_get_sensor_ala_map_known_model_unmapped_codes() -> None:
    """Known models but with unmapped raw codes should return (None, raw)."""
    with patch("custom_components.syr_connect.helpers.detect_model", return_value={"name": "lexplus10"}):
        mapped, raw = get_sensor_ala_map({"getCNA": "LEXplus10"}, "ZZ")
        assert mapped is None and raw == "ZZ"

    with patch("custom_components.syr_connect.helpers.detect_model", return_value={"name": "safetplus"}):
        mapped, raw = get_sensor_ala_map({"getVER": "Safe-T+ V2"}, "ZZ")
        assert mapped is None and raw == "ZZ"

    with patch("custom_components.syr_connect.helpers.detect_model", return_value={"name": "neosoft2500"}):
        mapped, raw = get_sensor_ala_map({"getVER": "NSS"}, "ZZ")
        assert mapped is None and raw == "ZZ"


def test_get_sensor_not_and_wrn_map_unmapped_and_none() -> None:
    # unmapped code
    mapped_not, raw_not = get_sensor_not_map({}, "ZZ")
    assert mapped_not is None and raw_not == "ZZ"

    # none input returns empty raw
    mapped_not2, raw_not2 = get_sensor_not_map({}, None)
    assert mapped_not2 is None and raw_not2 == ""

    mapped_wrn, raw_wrn = get_sensor_wrn_map({}, "ZZ")
    assert mapped_wrn is None and raw_wrn == "ZZ"


def test_is_sensor_visible_empty_string_and_value_exclusions() -> None:
    # Use a key from the empty-string exclusion set
    key_es = next(iter(helpers._SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_STRING))
    assert not is_sensor_visible({}, key_es, None)
    assert not is_sensor_visible({}, key_es, "   ")

    # Use a key from the empty-value exclusion set
    key_ev = next(iter(helpers._SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_VALUE))
    assert not is_sensor_visible({}, key_ev, None)
    assert not is_sensor_visible({}, key_ev, 0)
    assert not is_sensor_visible({}, key_ev, "0")

    # Empty IP exclusion set
    key_ip = next(iter(helpers._SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_IPADDRESS))
    assert not is_sensor_visible({}, key_ip, None)
    assert not is_sensor_visible({}, key_ip, "   ")
    assert not is_sensor_visible({}, key_ip, "0.0.0.0")


def test_get_sensor_ab_value_string_variants() -> None:
    # String boolean-like values accepted by helpers
    assert get_sensor_ab_value({"getAB": "true"}) is True
    assert get_sensor_ab_value({"getAB": "false"}) is False


def test_get_sensor_bat_value_first_token_unparseable() -> None:
    # First token is non-numeric -> should return None
    assert get_sensor_bat_value("bad 4,38 3,90") is None


def test_get_current_mac_eip_fallback_when_wfs_unparsable() -> None:
    """When getWFS unparsable, ensure getEIP/getMAC2 fallback is used."""
    status = {
        "getWIP": "192.168.1.10",
        "getWFS": "bad",
        "getMAC1": "",
        "getEIP": "10.0.0.2",
        "getMAC2": "22:22:22:22:22:22",
    }
    assert get_current_mac(status) == "22:22:22:22:22:22"


def test_get_sensor_bat_value_non_str_non_numeric_returns_none() -> None:
    """Non-string, non-numeric types should return None."""
    assert get_sensor_bat_value([1, 2, 3]) is None


def test_get_sensor_ab_value_unexpected_type_returns_none() -> None:
    """An unexpected type for getAB should be handled and return None."""
    assert get_sensor_ab_value({"getAB": object()}) is None


def test_is_sensor_visible_group_pa_true_shows_group_keys() -> None:
    """If getPAx is truthy, related group keys should be visible."""
    status = {"getPA1": "1"}
    assert is_sensor_visible(status, "getPV1", "0") is True


def test_is_sensor_visible_cs_sv_non_numeric_falls_back() -> None:
    """When getSVx is non-numeric, CS follows empty/value rules and is hidden for '0'."""
    status = {"getSV1": "bad", "getCS1": "0"}
    assert is_sensor_visible(status, "getCS1", "0") is False


# ---------------------------------------------------------------------------
# Coverage fill-ins
# ---------------------------------------------------------------------------

def test_get_current_mac_wip_present_wfs_none() -> None:
    """When getWIP is set but getWFS key is absent, wfs_int stays None (line 246)."""
    # getWFS missing entirely -> else branch sets wfs_int = None -> MAC1 not returned
    status = {"getWIP": "192.168.1.5", "getMAC1": "AA:BB:CC:DD:EE:FF"}
    # wfs_int is None, so wfs_int == 2 is False -> falls through to getEIP (absent)
    assert get_current_mac(status) is None


def test_get_sensor_avo_value_non_string_non_numeric_returns_none() -> None:
    """Non-string, non-numeric types return None from get_sensor_avo_value (line 286)."""
    assert get_sensor_avo_value([1, 2]) is None
    assert get_sensor_avo_value({"v": 1}) is None


def test_get_sensor_net_value_numeric_type_error() -> None:
    """Numeric path exception branch in get_sensor_net_value (lines 369-370)."""
    with patch("builtins.round", side_effect=ValueError("boom")):
        assert get_sensor_net_value(363) is None


def test_get_sensor_net_value_comma_decimal_exception() -> None:
    """Comma-decimal exception branch in get_sensor_net_value (lines 394-395)."""
    with patch("builtins.round", side_effect=ValueError("boom")):
        assert get_sensor_net_value("11,86") is None


def test_get_sensor_net_value_digit_only_exception() -> None:
    """Digit-only exception branch in get_sensor_net_value (lines 401-402)."""
    with patch("builtins.round", side_effect=ValueError("boom")):
        assert get_sensor_net_value("363") is None


def test_get_sensor_bat_value_numeric_exception() -> None:
    """Numeric path exception branch in get_sensor_bat_value (lines 424-425)."""
    with patch("builtins.round", side_effect=TypeError("boom")):
        assert get_sensor_bat_value(363) is None


def test_get_sensor_bat_value_comma_decimal_exception() -> None:
    """Comma-decimal exception branch in get_sensor_bat_value (lines 446-447)."""
    with patch("builtins.round", side_effect=ValueError("boom")):
        assert get_sensor_bat_value("9,36") is None


def test_get_sensor_bat_value_digit_only_exception() -> None:
    """Digit-only exception branch in get_sensor_bat_value (lines 453-454)."""
    with patch("builtins.round", side_effect=ValueError("boom")):
        assert get_sensor_bat_value("363") is None


def test_get_sensor_rtm_combined_mode_exception_in_parse() -> None:
    """RTM combined-mode parse exception branch (lines 490-492).

    A match is found by the regex but int() on the group raises – this is
    only reachable via the except block since int/IndexError are caught.
    Force by patching int() on the re match groups via a bad match object.
    """
    # Patch re.match to return a match whose group() raises ValueError
    mock_match = MagicMock()
    mock_match.group.side_effect = ValueError("bad group")
    with patch("custom_components.syr_connect.helpers.re.match", return_value=mock_match):
        result = helpers.get_sensor_rtm_value({"getRTH": None, "getRTM": "12:30"})
    assert result is None


def test_set_sensor_rtm_value_empty_option_returns_empty() -> None:
    """set_sensor_rtm_value returns [] for empty/non-string option (line 521)."""
    assert helpers.set_sensor_rtm_value({}, "") == []
    assert helpers.set_sensor_rtm_value({}, None) == []
    assert helpers.set_sensor_rtm_value({}, 123) == []


def test_get_sensor_ab_value_unexpected_exception() -> None:
    """Unexpected exception in getAB parse is caught and returns None (lines 599-601)."""

    class _BadInt(int):
        """int subclass whose float() conversion raises TypeError."""

        def __float__(self):
            raise TypeError("unexpected error in float()")

    # Pass a numeric-like object that causes TypeError inside the try block
    result = get_sensor_ab_value({"getAB": _BadInt(2)})
    assert result is None


def test_get_sensor_ala_map_unrecognized_known_model() -> None:
    """Unrecognized model (not in any family) returns (None, code) (line 665)."""
    # Patch detect_model to return a recognized non-unknown model name not in any family
    with patch(
        "custom_components.syr_connect.helpers.detect_model",
        return_value={"name": "futuredevice2100"},
    ):
        mapped, raw = get_sensor_ala_map({"getSRN": "X"}, "FF")
    assert mapped is None
    assert raw == "FF"


def test_is_value_true_bool_value() -> None:
    """is_sensor_visible: is_value_true returns bool value directly (line 789)."""
    # Passing a boolean True for getPAx means the group key must be visible
    assert is_sensor_visible({"getPA1": True}, "getPV1", "1") is True
    assert is_sensor_visible({"getPA1": False}, "getPV1", "1") is False


def test_is_value_true_numeric_value() -> None:
    """is_sensor_visible: is_value_true handles int/float (lines 791-794)."""
    # Non-zero int -> True (PA is active, group key shown)
    assert is_sensor_visible({"getPA2": 1}, "getPV2", "1") is True
    # Zero int -> False
    assert is_sensor_visible({"getPA2": 0}, "getPV2", "1") is False
    # Float non-zero
    assert is_sensor_visible({"getPA3": 1.5}, "getPT3", "1") is True


def test_is_value_true_str_numeric_parse() -> None:
    """is_sensor_visible: is_value_true parses numeric strings (lines 801-805)."""
    # String "2" parses to non-zero -> True
    assert is_sensor_visible({"getPA1": "2"}, "getPV1", "1") is True
    # String "0.0" parses to zero -> False
    assert is_sensor_visible({"getPA1": "0.0"}, "getPV1", "1") is False
    # String "bad" can't parse -> False (except branch) -> group key hidden
    assert is_sensor_visible({"getPA1": "bad"}, "getPV1", "1") is False
    # Non-bool/int/float/str type -> is_value_true returns False -> key hidden
    assert is_sensor_visible({"getPA1": [1, 2]}, "getPV1", "1") is False


def test_is_sensor_visible_cs_value_none_returns_false() -> None:
    """getCS with None value and non-zero getSVx falls through to value is None check (line 826)."""
    # getSV1 is non-zero so the early True is NOT triggered (sv_val is zero string),
    # then value=None hits the 'if value is None: return False' branch.
    status = {"getSV1": "0"}
    assert is_sensor_visible(status, "getCS1", None) is False


# ---------------------------------------------------------------------------
# Lines 297-298 — get_sensor_avo_value: mL-pattern except branch
# ---------------------------------------------------------------------------

def test_get_sensor_avo_value_ml_pattern_except() -> None:
    """Lines 297-298: except(ValueError, TypeError) in the mL pattern block.

    Patch re.match so the first call ('^(<digits>)mL$') returns a mock whose
    group(1) raises ValueError, triggering the inner except branch.
    """
    from unittest.mock import MagicMock, patch

    from custom_components.syr_connect.helpers import get_sensor_avo_value

    bad_match = MagicMock()
    bad_match.group = MagicMock(side_effect=ValueError("bad group"))

    # Only intercept the first re.match call (the mL pattern)
    with patch("custom_components.syr_connect.helpers.re.match", return_value=bad_match):
        result = get_sensor_avo_value("1655mL")

    assert result is None


# ---------------------------------------------------------------------------
# Lines 306-307 — get_sensor_avo_value: fallback-pattern except branch
# ---------------------------------------------------------------------------

def test_get_sensor_avo_value_fallback_pattern_except() -> None:
    """Lines 306-307: except(ValueError, TypeError) in the fallback pattern block.

    Make the first re.match (mL pattern) return None so the code falls
    through to the ^(<digits>) fallback, then patch that match's group(1) to raise.
    """
    from unittest.mock import MagicMock, patch

    from custom_components.syr_connect.helpers import get_sensor_avo_value

    bad_match = MagicMock()
    bad_match.group = MagicMock(side_effect=ValueError("bad group"))

    call_count = 0

    def _match_side_effect(pattern, string):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return None        # mL pattern misses → fall through
        return bad_match       # fallback pattern → group(1) raises

    with patch("custom_components.syr_connect.helpers.re.match", side_effect=_match_side_effect):
        result = get_sensor_avo_value("1655")

    assert result is None


# ---------------------------------------------------------------------------
# Lines 793-794 — is_sensor_visible is_value_true: int/float except branch
# ---------------------------------------------------------------------------

def test_is_sensor_visible_is_value_true_int_subclass_float_raises() -> None:
    """Lines 793-794: is_value_true except(ValueError, TypeError) for int|float branch.

    Use an int subclass whose __float__ raises ValueError so the except path
    fires and is_value_true returns False, hiding the getPA group sensor.
    """
    class _BadFloat(int):
        def __float__(self):
            raise ValueError("bad float")

    status = {"getPA1": _BadFloat(1), "getPN1": "value"}
    # getPN1 is a PA-group key controlled by getPA1; is_value_true(_BadFloat(1))
    # hits the except → returns False → getPN1 is hidden
    assert is_sensor_visible(status, "getPN1", "value") is False

