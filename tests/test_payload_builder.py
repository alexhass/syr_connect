"""Test the SYR Connect payload builder."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001

from datetime import UTC, datetime
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
from custom_components.syr_connect.devices import safefloor
from custom_components.syr_connect.payload_builder import PayloadBuilder

_TEMPERATURE, _HUMIDITY = safefloor.STATISTICS


def test_compute_locale_lang_reg_from_language() -> None:
    """Locale parsing returns language and region from instance `language`."""
    pb = PayloadBuilder("1.0", MagicMock(), "SYR Connect")
    pb.language = "de_DE"
    lang, reg = pb._compute_locale_lang_reg()

    assert lang == "de"
    assert reg == "DE"


def test_compute_locale_lang_reg_default() -> None:
    """Without a language argument, the default en-US is used."""
    pb = PayloadBuilder("1.0", MagicMock(), "SYR Connect")

    assert pb._compute_locale_lang_reg() == ("en", "US")


def test_compute_locale_lang_reg_from_constructor() -> None:
    """The language passed to the constructor is used."""
    pb = PayloadBuilder("1.0", MagicMock(), "SYR Connect", language="en-DE")

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
    pb = PayloadBuilder("1.2.3", MagicMock(), "SYR Connect")

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
    pb = PayloadBuilder("1.2.3", fake_checksum, "SYR Connect")

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
    pb = PayloadBuilder("1.2.3", fake_checksum, "SYR Connect")

    device_list = DefusedET.fromstring(pb.build_device_get_list_payload(value, value))
    assert device_list.find(".//us").attrib["ug"] == value
    assert device_list.find(".//pr").attrib["pg"] == value

    status = DefusedET.fromstring(pb.build_device_get_status_payload(value, value))
    assert status.find(".//us").attrib["ug"] == value
    assert status.find(".//dcl").attrib["dclg"] == value

    stats = DefusedET.fromstring(
        pb.build_device_get_statistics_payload(value, value, _TEMPERATURE)
    )
    assert stats.find(".//us").attrib["ug"] == value
    assert stats.find(".//dcl").attrib["dclg"] == value


def test_none_attribute_value_raises_instead_of_sending_none_string() -> None:
    """A missing id must fail fast rather than be sent as ``"None"``."""
    pb = PayloadBuilder("1.2.3", MagicMock(), "SYR Connect")

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
    pb = PayloadBuilder("1.2.3", fake_checksum, "SYR Connect")

    payload = pb.build_device_get_status_payload("sess", "dev")

    assert tags_at_checksum_time == [["si", "us", "col"]]
    root = DefusedET.fromstring(payload)
    assert list(root)[-1].tag == "cs"
    assert [child.tag for child in root] == ["si", "us", "col", "cs"]


def test_add_checksum_is_idempotent() -> None:
    """Adding the checksum twice to the same root gives one <cs> and the same payload."""
    pb = PayloadBuilder(
        "1.2.3",
        SyrChecksum(
            _SYR_CONNECT_CLIENT_CHECKSUM_KEY1, _SYR_CONNECT_CLIENT_CHECKSUM_KEY2
        ),
        "SYR Connect",
    )
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
    "temperature": "ExampleRequest_GetSafeFloorStatistics_Temperature.xml",
    "humidity": "ExampleRequest_GetSafeFloorStatistics_Humidity.xml",
}


def _build_reference_payloads() -> dict[str, str]:
    session, project, device = (
        "9f3c1a52-7d4e-4b8a-a1c6-2e5d8b07f413",
        "8625a6fc-3547-45c4-b394-671b5c99b6b9",
        "0b09f7ce-41a0-4085-9e69-fa8827a32b6f",
    )
    pb = PayloadBuilder(
        "App-3.9.7-de-DE-iOS-iPhone-27.0.0-de.consoft.syr.connect",
        SyrChecksum(
            _SYR_CONNECT_CLIENT_CHECKSUM_KEY1, _SYR_CONNECT_CLIENT_CHECKSUM_KEY2
        ),
        "SYR Connect",
    )
    with (
        patch.object(
            PayloadBuilder, "get_timestamp", return_value="2026-10-17 10:00:00"
        ),
        patch.object(PayloadBuilder, "_compute_local_tzo", return_value="02:00:00"),
        patch.object(
            PayloadBuilder, "_compute_locale_lang_reg", return_value=("de", "DE")
        ),
    ):
        return {
            "login": pb.build_login_payload("user@example.com", "secret"),
            "list": pb.build_device_get_list_payload(session, project),
            "status": pb.build_device_get_status_payload(session, device),
            "set": pb.build_device_set_status_payload(
                session, device, [("setAB", 1), ("setSIR", "")]
            ),
            "temperature": pb.build_device_get_statistics_payload(
                session, device, _TEMPERATURE
            ),
            "humidity": pb.build_device_get_statistics_payload(
                session, device, _HUMIDITY
            ),
        }


@pytest.mark.parametrize("name", list(_REQUEST_FIXTURES))
def test_payloads_match_request_fixtures(name: str) -> None:
    """Payloads equal the fixture (canonical XML, incl. real checksum, which pins attribute order)."""
    expected = (REQUEST_FIXTURE_DIR / _REQUEST_FIXTURES[name]).read_text(
        encoding="utf-8"
    )
    actual = _build_reference_payloads()[name]
    assert canonicalize(actual, strip_text=True) == canonicalize(
        expected, strip_text=True
    )


def test_build_login_payload_escapes_and_includes_tzo_lang() -> None:
    """Login payload should include escaped credentials and computed tzo/lang/reg."""
    fake_checksum = MagicMock()
    fake_checksum.compute_element_checksum.return_value = "CHK"
    pb = PayloadBuilder("1.2.3", fake_checksum, "SYR Connect")

    with (
        patch.object(PayloadBuilder, "_compute_local_tzo", return_value="01:00:00"),
        patch.object(
            PayloadBuilder, "_compute_locale_lang_reg", return_value=("de", "DE")
        ),
    ):
        payload = pb.build_login_payload("user<&>", "pwd<&>")

    # escaped characters should be present (XML escaped)
    assert "user&lt;&amp;&gt;" in payload
    assert "pwd&lt;&amp;&gt;" in payload
    # tzo and locale tags should be present
    assert 'tzo="01:00:00"' in payload
    assert 'lng="de"' in payload and 'reg="DE"' in payload


def test_build_device_get_statistics_payload_uses_series_checksum_and_lang() -> None:
    """The <sh> element carries the series attributes and the locale; a checksum is added."""
    fake_checksum = MagicMock()
    fake_checksum.compute_element_checksum.return_value = "CHK"
    pb = PayloadBuilder("1.2.3", fake_checksum, "SYR Connect")

    with patch.object(
        PayloadBuilder, "_compute_locale_lang_reg", return_value=("it", "IT")
    ):
        payload = pb.build_device_get_statistics_payload("sess", "dev", _HUMIDITY)

    root = DefusedET.fromstring(payload)
    assert root.find("cs").attrib["v"] == "CHK"
    assert root.find(".//sh").attrib == {
        "t": "2",
        "rtyp": "4",
        "lg": "it",
        "rg": "IT",
        "unit": "%",
    }


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
def test_compute_local_tzo_uses_ha_time_zone(
    time_zone: str, month: int, expected: str
) -> None:
    """The offset comes from the HA time zone incl. DST; positive offsets have no sign."""
    now = datetime(2026, month, 15, 12, 0, tzinfo=ZoneInfo(time_zone))
    with patch(
        "custom_components.syr_connect.payload_builder.dt_util.now", return_value=now
    ):
        assert PayloadBuilder._compute_local_tzo() == expected


def test_compute_locale_lang_reg_dash_and_single() -> None:
    """Locale parsing handles dash-separated and single-part locales."""
    pb = PayloadBuilder("1.0", MagicMock(), "SYR Connect")

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


@pytest.mark.parametrize("value", _ATTR_SPECIAL_VALUES)
def test_app_version_roundtrips_special_characters(value: str) -> None:
    """The app version is escaped like every other attribute value."""
    fake_checksum = MagicMock()
    fake_checksum.compute_element_checksum.return_value = "CHK"
    pb = PayloadBuilder(value, fake_checksum, "SYR Connect")

    root = DefusedET.fromstring(pb.build_device_get_list_payload("sess", "proj"))

    assert root.find("si").attrib == {"v": value}


def test_get_timestamp_is_utc() -> None:
    """The request timestamp is the current UTC time as YYYY-MM-DD HH:MM:SS."""
    now = datetime(2026, 10, 17, 8, 5, 9, tzinfo=UTC)
    with patch(
        "custom_components.syr_connect.payload_builder.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = now
        assert PayloadBuilder.get_timestamp() == "2026-10-17 08:05:09"

    mock_datetime.now.assert_called_once_with(UTC)
