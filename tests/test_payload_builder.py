"""Test the SYR Connect payload builder."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from xml.etree.ElementTree import Element, canonicalize
from zoneinfo import ZoneInfo

from defusedxml import ElementTree as DefusedET
import pytest

from custom_components.syr_connect.checksum import SyrChecksum
from custom_components.syr_connect.const import (
    _SYR_CONNECT_CLIENT_CHECKSUM_KEY1,
    _SYR_CONNECT_CLIENT_CHECKSUM_KEY2,
)
from custom_components.syr_connect.payload_builder import PayloadBuilder


def test_compute_locale_lang_reg_from_getlocale() -> None:
    """Locale parsing returns language and region from instance `language`."""
    pb = PayloadBuilder("1.0", MagicMock())
    pb.language = "de_DE"
    lang, reg = pb._compute_locale_lang_reg()

    assert lang == "de"
    assert reg == "DE"


def test_compute_locale_lang_reg_from_env() -> None:
    """When instance language is set from an env-like value, return language and region."""
    pb = PayloadBuilder("1.0", MagicMock())
    pb.language = "fr_FR"
    lang, reg = pb._compute_locale_lang_reg()

    assert lang == "fr"
    assert reg == "FR"


def test_compute_locale_lang_reg_default() -> None:
    """Without a language argument, the default en-US is used."""
    pb = PayloadBuilder("1.0", MagicMock())

    assert pb._compute_locale_lang_reg() == ("en", "US")


def test_compute_locale_lang_reg_from_constructor() -> None:
    """The language passed to the constructor is used."""
    pb = PayloadBuilder("1.0", MagicMock(), language="en-DE")

    assert pb._compute_locale_lang_reg() == ("en", "DE")


_ATTR_SPECIAL_VALUES = [
    'pa"ss',
    "it's",
    """both ' and " quotes""",
    'x" admin="1',
    "a&b<c>d",
    "tab\there",
    "line\nbreak",
    "cr\rreturn",
    '"',
]


@pytest.mark.parametrize("value", _ATTR_SPECIAL_VALUES)
def test_login_payload_roundtrips_special_characters(value: str) -> None:
    """Credentials with quotes/markup/whitespace arrive unchanged and cannot inject attributes."""
    pb = PayloadBuilder("1.2.3", MagicMock())

    payload = pb.build_login_payload(value, value)

    usr = DefusedET.fromstring(payload).find(".//usr")
    assert usr is not None
    assert set(usr.attrib) == {"n", "v"}  # nothing injected
    assert usr.attrib["n"] == value
    assert usr.attrib["v"] == value


@pytest.mark.parametrize("value", _ATTR_SPECIAL_VALUES)
def test_set_status_payload_roundtrips_special_characters(value: str) -> None:
    """Command name/value and ids are escaped for attribute context."""
    fake_checksum = MagicMock()
    fake_checksum.compute_element_checksum.return_value = "CHK"
    pb = PayloadBuilder("1.2.3", fake_checksum)

    payload = pb.build_device_set_status_payload(value, value, [("setAB", value)])

    # The checksum is computed over the unescaped attribute values of the tree.
    checksum_input = fake_checksum.compute_element_checksum.call_args.args[0]
    assert checksum_input.find(".//c").attrib["v"] == value

    root = DefusedET.fromstring(payload)
    cmd = root.find(".//c")
    assert cmd is not None
    assert set(cmd.attrib) == {"n", "v"}
    assert cmd.attrib["n"] == "setAB"
    assert cmd.attrib["v"] == value
    assert root.find(".//us").attrib["ug"] == value
    assert root.find(".//dcl").attrib["dclg"] == value


@pytest.mark.parametrize("value", _ATTR_SPECIAL_VALUES)
def test_session_and_device_payloads_roundtrip_special_characters(value: str) -> None:
    """Session, project and device ids are escaped in every payload builder."""
    fake_checksum = MagicMock()
    fake_checksum.compute_element_checksum.return_value = "CHK"
    pb = PayloadBuilder("1.2.3", fake_checksum)

    device_list = DefusedET.fromstring(pb.build_device_get_list_payload(value, value))
    assert device_list.find(".//us").attrib["ug"] == value
    assert device_list.find(".//pr").attrib["pg"] == value

    status = DefusedET.fromstring(pb.build_device_get_status_payload(value, value))
    assert status.find(".//us").attrib["ug"] == value
    assert status.find(".//dcl").attrib["dclg"] == value

    stats = DefusedET.fromstring(pb.build_device_get_statistics_payload(value, value))
    assert stats.find(".//us").attrib["ug"] == value
    assert stats.find(".//dcl").attrib["dclg"] == value


def test_none_attribute_value_raises_instead_of_sending_none_string() -> None:
    """A missing id must fail fast rather than be sent as ``"None"``."""
    pb = PayloadBuilder("1.2.3", MagicMock())

    with pytest.raises(TypeError, match="ug"):
        pb.build_device_get_list_payload(None, "p")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="pg"):
        pb.build_device_get_list_payload("s", None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="dclg"):
        pb.build_device_get_status_payload("s", None)  # type: ignore[arg-type]


def test_checksum_is_computed_without_cs_and_appended_as_last_element() -> None:
    """The checksum input excludes <cs>; <cs> ends up as the last child of <sc>."""
    # The root is mutated after the call, so record its children at call time.
    tags_at_checksum_time: list[list[str]] = []

    def record_tags(root: Element) -> str:
        tags_at_checksum_time.append([child.tag for child in root])
        return "CHK"

    fake_checksum = MagicMock()
    fake_checksum.compute_element_checksum.side_effect = record_tags
    pb = PayloadBuilder("1.2.3", fake_checksum)

    payload = pb.build_device_get_status_payload("sess", "dev")

    assert tags_at_checksum_time == [["si", "us", "col"]]
    root = DefusedET.fromstring(payload)
    assert list(root)[-1].tag == "cs"
    assert [child.tag for child in root] == ["si", "us", "col", "cs"]


def test_add_checksum_is_idempotent() -> None:
    """Adding the checksum twice to the same root gives one <cs> and the same payload."""
    pb = PayloadBuilder("1.2.3", SyrChecksum(_SYR_CONNECT_CLIENT_CHECKSUM_KEY1, _SYR_CONNECT_CLIENT_CHECKSUM_KEY2))
    root = pb._new_request("sess")

    first = pb._add_checksum(root)
    second = pb._add_checksum(root)

    assert second == first
    assert len(DefusedET.fromstring(second).findall("cs")) == 1


# Request fixtures: realistic payload structure with placeholder ids; checksums are computed by
# the integration itself, not captured from the app.
REQUEST_FIXTURE_DIR = Path(__file__).parent / "fixtures/xml/requests"
_REQUEST_FIXTURES = {
    "login": "ExampleRequest_Login.xml",
    "list": "ExampleRequest_GetProjectDeviceCollections.xml",
    "status": "ExampleRequest_GetDeviceCollectionStatus.xml",
    "set": "ExampleRequest_SetDeviceCollectionStatus.xml",
    "water": "ExampleRequest_GetStatistics_Water.xml",
    "salt": "ExampleRequest_GetStatistics_Salt.xml",
}


def _build_reference_payloads() -> dict[str, str]:
    session, project, device = (
        "9f3c1a52-7d4e-4b8a-a1c6-2e5d8b07f413",
        "8625a6fc-3547-45c4-b394-671b5c99b6b9",
        "0b09f7ce-41a0-4085-9e69-fa8827a32b6f",
    )
    pb = PayloadBuilder(
        "App-3.9.7-de-DE-iOS-iPhone-27.0.0-de.consoft.syr.connect",
        SyrChecksum(_SYR_CONNECT_CLIENT_CHECKSUM_KEY1, _SYR_CONNECT_CLIENT_CHECKSUM_KEY2),
    )
    with (
        patch.object(PayloadBuilder, "get_timestamp", return_value="2026-10-17 10:00:00"),
        patch.object(PayloadBuilder, "_compute_local_tzo", return_value="02:00:00"),
        patch.object(PayloadBuilder, "_compute_locale_lang_reg", return_value=("de", "DE")),
    ):
        return {
            "login": pb.build_login_payload("user@example.com", "secret"),
            "list": pb.build_device_get_list_payload(session, project),
            "status": pb.build_device_get_status_payload(session, device),
            "set": pb.build_device_set_status_payload(session, device, [("setAB", 1), ("setSIR", "")]),
            "water": pb.build_device_get_statistics_payload(session, device, "water"),
            "salt": pb.build_device_get_statistics_payload(session, device, "salt"),
        }


@pytest.mark.parametrize("name", list(_REQUEST_FIXTURES))
def test_payloads_match_request_fixtures(name: str) -> None:
    """Payloads equal the fixture (canonical XML, incl. real checksum, which pins attribute order)."""
    expected = (REQUEST_FIXTURE_DIR / _REQUEST_FIXTURES[name]).read_text(encoding="utf-8")
    actual = _build_reference_payloads()[name]
    assert canonicalize(actual, strip_text=True) == canonicalize(expected, strip_text=True)


def test_build_login_payload_escapes_and_includes_tzo_lang() -> None:
    """Login payload should include escaped credentials and computed tzo/lang/reg."""
    fake_checksum = MagicMock()
    fake_checksum.compute_element_checksum.return_value = "CHK"
    pb = PayloadBuilder("1.2.3", fake_checksum)

    with patch.object(PayloadBuilder, "_compute_local_tzo", return_value="01:00:00"), patch.object(
        PayloadBuilder, "_compute_locale_lang_reg", return_value=("de", "DE")
    ):
        payload = pb.build_login_payload("user<&>", "pwd<&>")

    # escaped characters should be present (XML escaped)
    assert "user&lt;&amp;&gt;" in payload
    assert "pwd&lt;&amp;&gt;" in payload
    # tzo and locale tags should be present
    assert 'tzo="01:00:00"' in payload
    assert 'lng="de"' in payload and 'reg="DE"' in payload


def test_build_device_get_statistics_payload_salt_and_water_use_checksum_and_lang(caplog) -> None:
    """Statistics payload branches for salt and water include correct units and checksum."""
    fake_checksum = MagicMock()
    fake_checksum.compute_element_checksum.return_value = "CHK"
    pb = PayloadBuilder("1.2.3", fake_checksum)

    with patch.object(PayloadBuilder, "_compute_locale_lang_reg", return_value=("it", "IT")):
        salt_payload = pb.build_device_get_statistics_payload("sess", "dev", statistic_type="salt")
        water_payload = pb.build_device_get_statistics_payload("sess", "dev", statistic_type="water")

    # Checksum added
    assert DefusedET.fromstring(salt_payload).find("cs").attrib["v"] == "CHK"
    assert DefusedET.fromstring(water_payload).find("cs").attrib["v"] == "CHK"

    # salt uses kg, water uses l
    assert 'unit="kg"' in salt_payload
    assert 'unit="l"' in water_payload

    # lang/region are injected
    assert 'lg="it"' in salt_payload
    assert 'rg="IT"' in water_payload


@pytest.mark.parametrize(
    ("time_zone", "month", "expected"),
    [
        ("Europe/Berlin", 7, "02:00:00"),  # CEST
        ("Europe/Berlin", 1, "01:00:00"),  # CET
        ("UTC", 7, "00:00:00"),
        ("Asia/Kolkata", 1, "05:30:00"),
        ("America/St_Johns", 1, "-03:30:00"),
    ],
)
def test_compute_local_tzo_uses_ha_time_zone(time_zone: str, month: int, expected: str) -> None:
    """The offset comes from the HA time zone incl. DST; positive offsets have no sign."""
    now = datetime(2026, month, 15, 12, 0, tzinfo=ZoneInfo(time_zone))
    with patch("custom_components.syr_connect.payload_builder.dt_util.now", return_value=now):
        assert PayloadBuilder._compute_local_tzo() == expected


def test_compute_locale_lang_reg_dash_and_single() -> None:
    """Locale parsing handles dash-separated and single-part locales."""
    pb = PayloadBuilder("1.0", MagicMock())

    # dash-separated
    pb.language = "en-US"
    lang, reg = pb._compute_locale_lang_reg()
    assert lang == "en"
    assert reg == "US"

    # single-part (no region) should default to US
    pb.language = "es"
    lang2, reg2 = pb._compute_locale_lang_reg()
    assert lang2 == "es"
    assert reg2 == "US"


@pytest.fixture
def payload_builder():
    """Create a payload builder instance."""
    checksum = SyrChecksum(
        "L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP",
        "KHGK5X29LVNZU56T"
    )
    return PayloadBuilder("App-3.9.7-de-DE-iOS-iPhone", checksum)


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


def test_build_device_get_list_payload(payload_builder):
    """Test building device list payload."""
    payload = payload_builder.build_device_get_list_payload("session123", "project456")

    assert "session123" in payload
    assert "project456" in payload
    assert "<cs v=" in payload  # Checksum should be added


def test_build_device_get_status_payload(payload_builder):
    """Test building device status payload."""
    payload = payload_builder.build_device_get_status_payload("session123", "device789")

    assert "session123" in payload
    assert "device789" in payload
    assert "fref=\"1\"" in payload


def test_build_device_set_status_payload(payload_builder):
    """Test building set status payload."""
    payload = payload_builder.build_device_set_status_payload("session123", "device789", [("setSIR", 0)])

    assert "session123" in payload
    assert "device789" in payload
    assert "setSIR" in payload
    assert 'v="0"' in payload


def test_build_device_set_status_payload_with_string_value(payload_builder):
    """Test building set status payload with string value."""
    payload = payload_builder.build_device_set_status_payload("session123", "device789", [("setCNA", "NewName")])

    assert "NewName" in payload


def test_build_device_get_statistics_payload_water(payload_builder):
    """Test building statistics payload for water."""
    payload = payload_builder.build_device_get_statistics_payload("session123", "device789", "water")

    assert "session123" in payload
    assert "device789" in payload
    assert 't="1"' in payload  # Water type
    assert 'unit="l"' in payload


def test_build_device_get_statistics_payload_salt(payload_builder):
    """Test building statistics payload for salt."""
    payload = payload_builder.build_device_get_statistics_payload("session123", "device789", "salt")

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


def test_build_device_get_list_payload_escaping(payload_builder):
    """Test XML escaping in device list payload."""
    session = "session&123"
    project = "project<456>"

    payload = payload_builder.build_device_get_list_payload(session, project)

    # Special characters should be escaped
    assert "&amp;" in payload
    assert "&lt;" in payload
    assert "&gt;" in payload


def test_build_device_get_status_payload_escaping(payload_builder):
    """Test XML escaping in device status payload."""
    session = "session'123"
    device = 'device"456'

    payload = payload_builder.build_device_get_status_payload(session, device)

    # Should contain escaped versions
    assert "session" in payload and "123" in payload


def test_build_device_set_status_payload_escaping(payload_builder):
    """Test XML escaping in set status payload."""
    payload = payload_builder.build_device_set_status_payload(
        "session&123",
        "device<456>",
        [("command\"test", "value'123")],
    )

    # Special characters should be escaped
    assert "&amp;" in payload
    assert "&lt;" in payload or "&gt;" in payload


def test_build_device_get_statistics_payload_escaping(payload_builder):
    """Test XML escaping in statistics payload."""
    session = "session&test"
    device = "device<test>"

    payload = payload_builder.build_device_get_statistics_payload(session, device, "water")

    # Special characters should be escaped
    assert "&amp;" in payload
    assert "&lt;" in payload or "&gt;" in payload


def test_build_device_get_statistics_payload_default_type(payload_builder):
    """Test building statistics payload with default type (water)."""
    payload = payload_builder.build_device_get_statistics_payload("session123", "device789")

    # Should default to water
    assert 't="1"' in payload
    assert 'unit="l"' in payload


def test_add_checksum_integration(payload_builder):
    """Test that checksum is properly added to payloads."""
    payload = payload_builder.build_device_get_list_payload("sess", "proj")

    # Checksum should be at the end before closing tag
    assert '<cs v="' in payload
    assert payload.index('<cs v="') < payload.index('</sc>')


def test_build_device_set_status_payload_int_value(payload_builder):
    """Test set status payload with integer value."""
    payload = payload_builder.build_device_set_status_payload("sess", "dev", [("cmd", 42)])

    # Integer should be converted to string
    assert 'v="42"' in payload


def test_app_version_escaping_in_payloads(payload_builder):
    """Test that app version is escaped in payloads."""
    # Create builder with special characters in app version
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    builder = PayloadBuilder("App&Version<Test>", checksum)

    payload = builder.build_device_get_list_payload("sess", "proj")

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
