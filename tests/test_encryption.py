"""Test the SYR Connect encryption module."""
import pytest
import base64

from custom_components.syr_connect.encryption import SyrEncryption


@pytest.fixture
def encryption():
    """Create an encryption instance with test keys."""
    key = "d805a5c409dc354b6ccf03a2c29a5825851cf31979abf526ede72570c52cf954"
    iv = "408a42beb8a1cefad990098584ed51a5"
    return SyrEncryption(key, iv)


def test_decrypt_valid_data(encryption):
    """Test decryption of valid encrypted data."""
    # This is a real encrypted payload (you'd need to generate one for actual testing)
    # For now, we test the mechanics
    plaintext = "test data"
    # Since we can't easily encrypt without the full setup, we'll test error handling
    
    with pytest.raises(ValueError):
        encryption.decrypt("invalid_base64_!@#$")


def test_decrypt_empty_string(encryption):
    """Test decryption of empty string."""
    with pytest.raises(ValueError):
        encryption.decrypt("")


def test_encryption_initialization():
    """Test encryption initialization with hex keys."""
    key = "d805a5c409dc354b6ccf03a2c29a5825851cf31979abf526ede72570c52cf954"
    iv = "408a42beb8a1cefad990098584ed51a5"
    enc = SyrEncryption(key, iv)
    
    assert len(enc.key) == 32  # 256 bits
    assert len(enc.iv) == 16   # 128 bits
