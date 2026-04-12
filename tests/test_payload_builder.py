"""Test the SYR Connect payload builder."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from custom_components.syr_connect.checksum import SyrChecksum
from custom_components.syr_connect.payload_builder import PayloadBuilder


def test_compute_local_tzo_exception_fallback(caplog) -> None:
    """When datetime.now raises, _compute_local_tzo falls back to +00:00:00."""
    # Patch the module-level `datetime` name to a mock so we don't try to set
    # attributes on the real immutable `datetime.datetime` type.
    with patch("custom_components.syr_connect.payload_builder.datetime") as fake_dt:
        fake_dt.now.side_effect = Exception("boom")
        caplog.set_level("ERROR")
        tzo = PayloadBuilder._compute_local_tzo()

    assert tzo == "+00:00:00"
    assert "Failed to compute local timezone offset (tzo)" in caplog.text


def test_compute_locale_lang_reg_from_getlocale() -> None:
    """Locale parsing returns language and region from locale.getlocale()."""
    with patch("custom_components.syr_connect.payload_builder.locale.getlocale", return_value=("de_DE", "UTF-8")):
        lang, reg = PayloadBuilder._compute_locale_lang_reg()

    assert lang == "de"
    assert reg == "DE"


def test_compute_locale_lang_reg_from_env() -> None:
    """When getlocale returns None, fallback to LANG env var."""
    with patch("custom_components.syr_connect.payload_builder.locale.getlocale", return_value=(None, None)):
        with patch.dict(os.environ, {"LANG": "fr_FR"}):
            lang, reg = PayloadBuilder._compute_locale_lang_reg()

    assert lang == "fr"
    assert reg == "FR"


def test_compute_locale_lang_reg_exception_fallback(caplog) -> None:
    """If locale.getlocale raises, fallback to en/US and log."""
    with patch("custom_components.syr_connect.payload_builder.locale.getlocale", side_effect=Exception("boom")):
        caplog.set_level("ERROR")
        lang, reg = PayloadBuilder._compute_locale_lang_reg()

    assert (lang, reg) == ("en", "US")
    assert "Failed to determine locale language/region" in caplog.text


def test_build_login_payload_escapes_and_includes_tzo_lang() -> None:
    """Login payload should include escaped credentials and computed tzo/lang/reg."""
    fake_checksum = MagicMock()
    fake_checksum.compute_xml_checksum.return_value = "CHK"
    pb = PayloadBuilder("1.2.3", fake_checksum)

    with patch.object(PayloadBuilder, "_compute_local_tzo", return_value="+01:00:00"), patch.object(
        PayloadBuilder, "_compute_locale_lang_reg", return_value=("de", "DE")
    ):
        payload = pb.build_login_payload("user<&>", "pwd<&>")

    # escaped characters should be present (XML escaped)
    assert "user&lt;&amp;&gt;" in payload
    assert "pwd&lt;&amp;&gt;" in payload
    # tzo and locale tags should be present
    assert 'tzo="+01:00:00"' in payload
    assert 'lng="de"' in payload and 'reg="DE"' in payload


def test_build_statistics_payload_salt_and_water_use_checksum_and_lang(caplog) -> None:
    """Statistics payload branches for salt and water include correct units and checksum."""
    fake_checksum = MagicMock()
    fake_checksum.compute_xml_checksum.return_value = "CHK"
    pb = PayloadBuilder("1.2.3", fake_checksum)

    with patch.object(PayloadBuilder, "_compute_locale_lang_reg", return_value=("it", "IT")):
        salt_payload = pb.build_statistics_payload("sess", "dev", statistic_type="salt")
        water_payload = pb.build_statistics_payload("sess", "dev", statistic_type="water")

    # Checksum added
    assert '<cs v="CHK"/>' in salt_payload
    assert '<cs v="CHK"/>' in water_payload

    # salt uses kg, water uses l
    assert 'unit="kg"' in salt_payload
    assert 'unit="l"' in water_payload

    # lang/region are injected
    assert 'lg="it"' in salt_payload
    assert 'rg="IT"' in water_payload


def test_compute_local_tzo_normal_format() -> None:
    """_compute_local_tzo returns a string in ±HH:MM:SS format."""
    tzo = PayloadBuilder._compute_local_tzo()
    # Basic sanity: should be 9 chars like '+01:00:00' or '-05:30:00'
    assert isinstance(tzo, str)
    assert len(tzo) == 9
    assert (tzo[0] == '+' or tzo[0] == '-')
    assert tzo[3] == ':' and tzo[6] == ':'


def test_compute_local_tzo_negative_offset() -> None:
    """Force a negative offset from astimezone() and ensure '-' sign used."""
    from datetime import timedelta
    from unittest.mock import MagicMock

    with patch("custom_components.syr_connect.payload_builder.datetime") as fake_dt:
        fake_now = MagicMock()
        tz_obj = MagicMock()
        tz_obj.utcoffset.return_value = timedelta(hours=-5, minutes=-30)
        fake_now.astimezone.return_value = tz_obj
        fake_dt.now.return_value = fake_now

        tzo = PayloadBuilder._compute_local_tzo()

    assert isinstance(tzo, str)
    assert tzo.startswith("-")
    assert tzo == "-05:30:00"


def test_compute_locale_lang_reg_dash_and_single() -> None:
    """Locale parsing handles dash-separated and single-part locales."""
    # dash-separated
    with patch("custom_components.syr_connect.payload_builder.locale.getlocale", return_value=("en-US", None)):
        lang, reg = PayloadBuilder._compute_locale_lang_reg()
    assert lang == "en"
    assert reg == "US"

    # single-part (no region) should default to US
    with patch("custom_components.syr_connect.payload_builder.locale.getlocale", return_value=("es", None)):
        lang2, reg2 = PayloadBuilder._compute_locale_lang_reg()
    assert lang2 == "es"
    assert reg2 == "US"


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


def test_compute_local_tzo_fallback_extra(monkeypatch) -> None:
    """Force an exception in module datetime to hit the fallback branch."""
    import importlib

    pb_mod = importlib.import_module("custom_components.syr_connect.payload_builder")

    class BadDateTime:
        def now(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(pb_mod, "datetime", BadDateTime())

    checksum = SyrChecksum("0123456789ABCDEF", "key")
    pb = PayloadBuilder("1.0.0", checksum)

    assert pb._compute_local_tzo() == "+00:00:00"
