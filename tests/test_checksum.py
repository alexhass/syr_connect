"""Tests for checksum module."""

from pathlib import Path

from defusedxml import ElementTree as DefusedET
import pytest

from custom_components.syr_connect.checksum import SyrChecksum


def test_checksum_init():
    """Test checksum initialization."""
    checksum = SyrChecksum("ABCDEFGHIJKLMNOP", "TESTKEY")
    assert checksum.base_characters == "ABCDEFGHIJKLMNOP"
    assert checksum.key == "TESTKEY"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("a", 122),
        ("test", 395),
        (" test ", 395),
        ("zz", 287),
        ("üöä", 738),
        ("0b09f7ce-41a0-4085-9e69-fa8827a32b6f", 4011),
        ("App-3.9.7-de-DE-iOS-iPhone-27.0.0-de.consoft.syr.connect", 6169),
    ],
)
def test_compute_checksum_value_exact(value: str, expected: int):
    """Exact values of the SYR algorithm, recorded from the original bitwise implementation."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    assert checksum.compute_checksum_value(value) == expected


def test_compute_checksum_value_empty():
    """Test checksum computation with empty string."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    result = checksum.compute_checksum_value("")
    assert result == 0

    result = checksum.compute_checksum_value("   ")
    assert result == 0

    result = checksum.compute_checksum_value(None)
    assert result == 0


def test_compute_checksum_value_basic():
    """Test checksum computation with basic strings."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    result = checksum.compute_checksum_value("test")
    assert isinstance(result, int)
    assert result > 0


def test_compute_checksum_value_with_unicode():
    """Test checksum computation with Unicode characters."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    result = checksum.compute_checksum_value("üöä")
    assert isinstance(result, int)
    assert result > 0


def test_checksum_value_wrapping():
    """Test checksum value wrapping when sum >= base_characters length."""
    # Use actual production constants from const.py to ensure valid operation
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    result = checksum.compute_checksum_value("test")
    assert isinstance(result, int)
    assert result > 0


def test_compute_xml_checksum_with_attributes():
    """Test that compute_xml_checksum correctly processes XML attributes."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    xml_string = '<root><element a="value1" b="value2" n="ignored"/></root>'

    result = checksum.compute_xml_checksum(xml_string)

    # Must produce a non-zero hex string, and 'n' attribute must be ignored
    assert result != "0"
    result_without_n = checksum.compute_xml_checksum('<root><element a="value1" b="value2"/></root>')
    assert result == result_without_n


def test_compute_element_checksum_matches_xml_checksum():
    """The tree-based checksum equals the checksum of the same tree as XML string."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    xml_string = '<sc><si v="1.2.3"/><us ug="a &amp; &lt;b&gt;"/><col><dcl dclg="d" fref="1"><c n="x" v="1"/></dcl></col></sc>'

    assert checksum.compute_element_checksum(DefusedET.fromstring(xml_string)) == checksum.compute_xml_checksum(xml_string)


def test_compute_xml_checksum_invalid_xml():
    """Test that compute_xml_checksum returns '0' for invalid XML."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    result = checksum.compute_xml_checksum("not valid xml <unclosed")
    assert result == "0"


def test_compute_checksum_next_byte_and_offset_negative() -> None:
    """A key character missing from base_characters uses offset 0."""
    # base characters long enough for wrapping logic and indexing
    base = ''.join(chr(65 + i) for i in range(64))

    # Use a key character that is NOT present in base to trigger the offset 0 fallback
    checksum = SyrChecksum(base, "!")

    # Two ASCII characters span several 5-bit chunks, including chunks across a byte boundary
    result = checksum.compute_checksum_value("zz")
    assert result == 313


def test_compute_checksum_with_high_offset_key() -> None:
    """Use a key with a high offset to exercise the wrapping branch."""
    # Create a 32-length base so offsets can be large and wrapping can occur
    base32 = ''.join(chr(65 + i) for i in range(32))
    # pick last char to maximize offset
    key = base32[-1]
    checksum = SyrChecksum(base32, key)
    # Use a short string that still produces multiple chunks
    result = checksum.compute_checksum_value("zz")
    assert result == 344


_XML_FIXTURES = sorted(
    [
        *(Path(__file__).parent / "fixtures/xml").glob("*.xml"),
        *(Path(__file__).parent / "fixtures/xml/requests").glob("*.xml"),
    ]
)


@pytest.mark.parametrize("fixture", _XML_FIXTURES, ids=lambda p: p.name)
def test_fixture_checksum_is_valid(fixture: Path) -> None:
    """Requests and server responses share one checksum (all attribute values except `n`, without <cs>).

    Verified against real responses; keeps the fixtures consistent after anonymizing values.
    """
    from custom_components.syr_connect.const import (
        _SYR_CONNECT_CLIENT_CHECKSUM_KEY1,
        _SYR_CONNECT_CLIENT_CHECKSUM_KEY2,
    )

    root = DefusedET.fromstring(fixture.read_bytes())
    cs_elements = root.findall("cs")
    if not cs_elements:
        pytest.skip("fixture has no <cs> element")
    expected = cs_elements[0].get("v")
    for cs in cs_elements:
        root.remove(cs)

    checksum = SyrChecksum(_SYR_CONNECT_CLIENT_CHECKSUM_KEY1, _SYR_CONNECT_CLIENT_CHECKSUM_KEY2)
    assert checksum.compute_element_checksum(root) == expected
