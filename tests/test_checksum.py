"""Tests for checksum module."""
from custom_components.syr_connect.checksum import calculate_checksum, verify_checksum


def test_calculate_checksum_empty() -> None:
    """Test checksum calculation with empty data."""
    result = calculate_checksum(b"")
    assert isinstance(result, int)
    assert result >= 0


def test_calculate_checksum_basic() -> None:
    """Test checksum calculation with basic data."""
    data = b"Hello World"
    result = calculate_checksum(data)
    assert isinstance(result, int)
    assert result >= 0


def test_calculate_checksum_deterministic() -> None:
    """Test checksum is deterministic."""
    data = b"Test Data 123"
    result1 = calculate_checksum(data)
    result2 = calculate_checksum(data)
    assert result1 == result2


def test_calculate_checksum_different_data() -> None:
    """Test different data produces different checksums."""
    data1 = b"Data 1"
    data2 = b"Data 2"
    result1 = calculate_checksum(data1)
    result2 = calculate_checksum(data2)
    # High probability of different checksums
    assert result1 != result2


def test_verify_checksum_valid() -> None:
    """Test checksum verification with valid checksum."""
    data = b"Verify This"
    checksum = calculate_checksum(data)
    assert verify_checksum(data, checksum) is True


def test_verify_checksum_invalid() -> None:
    """Test checksum verification with invalid checksum."""
    data = b"Verify This"
    checksum = calculate_checksum(data)
    assert verify_checksum(data, checksum + 1) is False


def test_verify_checksum_zero() -> None:
    """Test checksum verification with zero checksum."""
    data = b"Test"
    assert verify_checksum(data, 0) is False or calculate_checksum(data) == 0
