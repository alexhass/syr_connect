"""Test the SYR Connect payload builder."""
import pytest

from custom_components.syr_connect.payload_builder import PayloadBuilder
from custom_components.syr_connect.checksum import SyrChecksum


@pytest.fixture
def payload_builder():
    """Create a payload builder instance."""
    checksum = SyrChecksum(
        "L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP",
        "KHGK5X29LVNZU56T"
    )
    return PayloadBuilder("App-3.7.10-de-DE-iOS-iPhone", checksum)


def test_build_login_payload(payload_builder):
    """Test building login payload."""
    payload = payload_builder.build_login_payload("test@example.com", "password123")
    
    assert "<?xml version=" in payload
    assert "test@example.com" in payload
    assert "password123" in payload
    assert "<usr n=" in payload


def test_build_login_payload_xml_escaping(payload_builder):
    """Test XML escaping in login payload."""
    # Test special characters that need escaping
    payload = payload_builder.build_login_payload("test&user", "pass<word>")
    
    # & should be escaped to &amp;
    assert "&amp;" in payload
    # < and > should be escaped
    assert "&lt;" in payload
    assert "&gt;" in payload
    # Original dangerous characters should not appear unescaped
    assert 'n="test&user"' not in payload
    assert 'v="pass<word>"' not in payload


def test_build_device_list_payload(payload_builder):
    """Test building device list payload."""
    payload = payload_builder.build_device_list_payload("session123", "project456")
    
    assert "session123" in payload
    assert "project456" in payload
    assert "<cs v=" in payload  # Checksum should be added


def test_build_device_status_payload(payload_builder):
    """Test building device status payload."""
    payload = payload_builder.build_device_status_payload("session123", "device789")
    
    assert "session123" in payload
    assert "device789" in payload
    assert "fref=\"1\"" in payload


def test_build_set_status_payload(payload_builder):
    """Test building set status payload."""
    payload = payload_builder.build_set_status_payload("session123", "device789", "setSIR", 0)
    
    assert "session123" in payload
    assert "device789" in payload
    assert "setSIR" in payload
    assert 'v="0"' in payload


def test_build_set_status_payload_with_string_value(payload_builder):
    """Test building set status payload with string value."""
    payload = payload_builder.build_set_status_payload("session123", "device789", "setCNA", "NewName")
    
    assert "NewName" in payload


def test_build_statistics_payload_water(payload_builder):
    """Test building statistics payload for water."""
    payload = payload_builder.build_statistics_payload("session123", "device789", "water")
    
    assert "session123" in payload
    assert "device789" in payload
    assert 't="1"' in payload  # Water type
    assert 'unit="l"' in payload


def test_build_statistics_payload_salt(payload_builder):
    """Test building statistics payload for salt."""
    payload = payload_builder.build_statistics_payload("session123", "device789", "salt")
    
    assert "session123" in payload
    assert "device789" in payload
    assert 't="2"' in payload  # Salt type
    assert 'unit="kg"' in payload


def test_get_timestamp(payload_builder):
    """Test timestamp generation."""
    timestamp = payload_builder.get_timestamp()
    
    # Should be in format YYYY-MM-DD HH:MM:SS
    assert len(timestamp) == 19
    assert timestamp[4] == "-"
    assert timestamp[7] == "-"
    assert timestamp[10] == " "
    assert timestamp[13] == ":"
    assert timestamp[16] == ":"


def test_xml_injection_protection(payload_builder):
    """Test protection against XML injection attacks."""
    malicious_input = '"><script>alert("xss")</script><x y="'
    
    payload = payload_builder.build_login_payload(malicious_input, "password")
    
    # The dangerous parts should be escaped
    assert "<script>" not in payload
    assert "alert(" not in payload or "&" in payload  # Should be escaped


def test_special_characters_escaping(payload_builder):
    """Test escaping of all special XML characters."""
    special_chars_user = 'user&name"with<special>chars'
    special_chars_pass = "pass'word&test"
    
    payload = payload_builder.build_login_payload(special_chars_user, special_chars_pass)
    
    # All special characters should be escaped
    assert "&amp;" in payload
    assert "&lt;" in payload or "&gt;" in payload
    # Quotes might be escaped depending on context
    assert 'n="user&name"' not in payload  # & should be escaped
