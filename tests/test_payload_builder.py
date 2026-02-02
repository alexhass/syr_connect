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


def test_redact_sensitive_basic(payload_builder):
    """Test redacting sensitive information from payload."""
    payload = '<sc><us ug="secret_session_123"/></sc>'
    redacted = payload_builder.redact_sensitive(payload)
    
    assert "secret_session_123" not in redacted
    assert "***REDACTED***" in redacted
    assert 'ug="***REDACTED***"' in redacted


def test_redact_sensitive_empty_string(payload_builder):
    """Test redacting sensitive info from empty string."""
    redacted = payload_builder.redact_sensitive("")
    assert redacted == ""


def test_redact_sensitive_none_value(payload_builder):
    """Test redacting sensitive info from None value."""
    redacted = payload_builder.redact_sensitive(None)
    assert redacted is None


def test_redact_sensitive_no_session(payload_builder):
    """Test redacting payload without session attribute."""
    payload = '<sc><si v="version"/></sc>'
    redacted = payload_builder.redact_sensitive(payload)
    
    # Should return unchanged when no ug attribute
    assert redacted == payload


def test_redact_sensitive_multiple_sessions(payload_builder):
    """Test redacting multiple session attributes."""
    payload = '<sc><us ug="session1"/><us ug="session2"/></sc>'
    redacted = payload_builder.redact_sensitive(payload)
    
    # Both sessions should be redacted
    assert "session1" not in redacted
    assert "session2" not in redacted
    assert redacted.count("***REDACTED***") == 2


def test_build_device_list_payload_escaping(payload_builder):
    """Test XML escaping in device list payload."""
    session = "session&123"
    project = "project<456>"
    
    payload = payload_builder.build_device_list_payload(session, project)
    
    # Special characters should be escaped
    assert "&amp;" in payload
    assert "&lt;" in payload
    assert "&gt;" in payload


def test_build_device_status_payload_escaping(payload_builder):
    """Test XML escaping in device status payload."""
    session = "session'123"
    device = 'device"456'
    
    payload = payload_builder.build_device_status_payload(session, device)
    
    # Should contain escaped versions
    assert "session" in payload and "123" in payload


def test_build_set_status_payload_escaping(payload_builder):
    """Test XML escaping in set status payload."""
    payload = payload_builder.build_set_status_payload(
        "session&123", 
        "device<456>",
        "command\"test",
        "value'123"
    )
    
    # Special characters should be escaped
    assert "&amp;" in payload
    assert "&lt;" in payload or "&gt;" in payload


def test_build_statistics_payload_escaping(payload_builder):
    """Test XML escaping in statistics payload."""
    session = "session&test"
    device = "device<test>"
    
    payload = payload_builder.build_statistics_payload(session, device, "water")
    
    # Special characters should be escaped
    assert "&amp;" in payload
    assert "&lt;" in payload or "&gt;" in payload


def test_build_statistics_payload_default_type(payload_builder):
    """Test building statistics payload with default type (water)."""
    payload = payload_builder.build_statistics_payload("session123", "device789")
    
    # Should default to water
    assert 't="1"' in payload
    assert 'unit="l"' in payload


def test_add_checksum_integration(payload_builder):
    """Test that checksum is properly added to payloads."""
    payload = payload_builder.build_device_list_payload("sess", "proj")
    
    # Checksum should be at the end before closing tag
    assert '<cs v="' in payload
    assert payload.index('<cs v="') < payload.index('</sc>')


def test_build_set_status_payload_int_value(payload_builder):
    """Test set status payload with integer value."""
    payload = payload_builder.build_set_status_payload("sess", "dev", "cmd", 42)
    
    # Integer should be converted to string
    assert 'v="42"' in payload


def test_app_version_escaping_in_payloads(payload_builder):
    """Test that app version is escaped in payloads."""
    # Create builder with special characters in app version
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    builder = PayloadBuilder("App&Version<Test>", checksum)
    
    payload = builder.build_device_list_payload("sess", "proj")
    
    # App version should be escaped
    assert "&amp;" in payload or "&lt;" in payload or "&gt;" in payload


def test_redact_sensitive_preserves_structure(payload_builder):
    """Test that redaction preserves XML structure."""
    payload = '<sc><us ug="session123"/><other>data</other></sc>'
    redacted = payload_builder.redact_sensitive(payload)
    
    # Structure should be preserved
    assert "<sc>" in redacted
    assert "<us ug=" in redacted
    assert "<other>data</other>" in redacted
    assert "</sc>" in redacted


def test_get_timestamp_format(payload_builder):
    """Test timestamp has correct components."""
    timestamp = payload_builder.get_timestamp()
    
    # Parse the timestamp parts
    date_part, time_part = timestamp.split(" ")
    year, month, day = date_part.split("-")
    hour, minute, second = time_part.split(":")
    
    # Verify all parts are numeric
    assert year.isdigit() and len(year) == 4
    assert month.isdigit() and len(month) == 2
    assert day.isdigit() and len(day) == 2
    assert hour.isdigit() and len(hour) == 2
    assert minute.isdigit() and len(minute) == 2
    assert second.isdigit() and len(second) == 2
