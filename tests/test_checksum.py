"""Tests for checksum module."""
from __future__ import annotations

from custom_components.syr_connect.checksum import SyrChecksum


def test_checksum_init():
    """Test checksum initialization."""
    checksum = SyrChecksum("ABCDEFGHIJKLMNOP", "TESTKEY")
    assert checksum.base_characters == "ABCDEFGHIJKLMNOP"
    assert checksum.key == "TESTKEY"
    assert checksum.checksum_value == 0


def test_extract_bits():
    """Test bit extraction."""
    # 0b11010110 = 214
    # Extract 3 bits starting at position 2: bits 2,3,4 = 101 = 5
    result = SyrChecksum.extract_bits(214, 2, 3)
    assert result == 5

    # Extract 5 bits starting at position 0: bits 0-4 = 10110 = 22
    result = SyrChecksum.extract_bits(214, 0, 5)
    assert result == 22


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


def test_compute_xml_checksum_invalid_xml():
    """Test that compute_xml_checksum returns '0' for invalid XML."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    result = checksum.compute_xml_checksum("not valid xml <unclosed")
    assert result == "0"


def test_compute_checksum_next_byte_and_offset_negative() -> None:
    """Force next-byte branch and missing key character offset path."""
    # base characters long enough for wrapping logic and indexing
    base = ''.join(chr(65 + i) for i in range(64))

    # Use a key character that is NOT present in base to trigger offset < 0 path
    checksum = SyrChecksum(base, "!")

    # Two-character ASCII input will generate multiple 5-bit chunks and cause
    # the implementation to hit the `bit_offset > 3` branch (next_byte logic).
    result = checksum.compute_checksum_value("zz")
    assert isinstance(result, int)
    assert result >= 0


def test_compute_checksum_with_high_offset_key() -> None:
    """Use a key with a high offset to exercise the wrapping branch."""
    # Create a 32-length base so offsets can be large and wrapping can occur
    base32 = ''.join(chr(65 + i) for i in range(32))
    # pick last char to maximize offset
    key = base32[-1]
    checksum = SyrChecksum(base32, key)
    # Use a short string that still produces multiple chunks
    result = checksum.compute_checksum_value("zz")
    assert isinstance(result, int)
    assert result > 0
