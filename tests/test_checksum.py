"""Tests for checksum module."""
from __future__ import annotations

import pytest

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


def test_add_to_checksum():
    """Test adding values to checksum."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    assert checksum.checksum_value == 0
    
    checksum.add_to_checksum("hello")
    value1 = checksum.checksum_value
    assert value1 > 0
    
    checksum.add_to_checksum("world")
    value2 = checksum.checksum_value
    assert value2 > value1


def test_reset_checksum():
    """Test checksum reset."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    checksum.add_to_checksum("test")
    assert checksum.checksum_value > 0
    
    checksum.reset_checksum()
    assert checksum.checksum_value == 0


def test_get_checksum():
    """Test getting checksum as hex string."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    checksum.checksum_value = 255
    assert checksum.get_checksum() == "FF"
    
    checksum.checksum_value = 4096
    assert checksum.get_checksum() == "1000"


def test_set_checksum():
    """Test setting checksum from hex string."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    checksum.set_checksum("FF")
    assert checksum.checksum_value == 255
    
    checksum.set_checksum("1000")
    assert checksum.checksum_value == 4096
    
    checksum.set_checksum("ABCD")
    assert checksum.checksum_value == 43981


def test_add_xml_to_checksum():
    """Test adding XML attributes to checksum."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    
    xml_string = '<root><element a="value1" b="value2" n="ignored"/></root>'
    checksum.add_xml_to_checksum(xml_string)
    assert checksum.checksum_value > 0


def test_add_xml_to_checksum_nested():
    """Test adding nested XML to checksum."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    
    xml_string = '''
    <root>
        <parent id="1">
            <child name="test" value="123"/>
        </parent>
    </root>
    '''
    checksum.add_xml_to_checksum(xml_string)
    assert checksum.checksum_value > 0


def test_add_xml_to_checksum_ignores_n_attribute():
    """Test that 'n' attributes are ignored."""
    checksum1 = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    checksum2 = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    
    # Same XML except one has 'n' attribute
    xml1 = '<root a="test"/>'
    xml2 = '<root a="test" n="ignored"/>'
    
    checksum1.add_xml_to_checksum(xml1)
    checksum2.add_xml_to_checksum(xml2)
    
    # Should produce same checksum since 'n' is ignored
    assert checksum1.checksum_value == checksum2.checksum_value


def test_add_xml_to_checksum_invalid_xml():
    """Test that invalid XML is handled gracefully."""
    checksum = SyrChecksum("L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP", "KHGK5X29LVNZU56T")
    
    # Invalid XML should not raise exception
    checksum.add_xml_to_checksum("not valid xml <unclosed")
    # Checksum should remain 0 since no valid data was added
    assert checksum.checksum_value == 0


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
