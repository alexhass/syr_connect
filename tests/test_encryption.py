"""Test the SYR Connect encryption module."""
import base64

import pytest
from Cryptodome.Cipher import AES

from custom_components.syr_connect.encryption import SyrEncryption


@pytest.fixture
def encryption():
    """Create an encryption instance with test keys."""
    key = "d805a5c409dc354b6ccf03a2c29a5825851cf31979abf526ede72570c52cf954"
    iv = "408a42beb8a1cefad990098584ed51a5"
    return SyrEncryption(key, iv)


def test_encryption_initialization():
    """Test encryption initialization with hex keys."""
    key = "d805a5c409dc354b6ccf03a2c29a5825851cf31979abf526ede72570c52cf954"
    iv = "408a42beb8a1cefad990098584ed51a5"
    enc = SyrEncryption(key, iv)
    
    assert len(enc.key) == 32  # 256 bits
    assert len(enc.iv) == 16   # 128 bits


def test_decrypt_empty_string(encryption):
    """Test decryption of empty string raises ValueError."""
    with pytest.raises(ValueError, match="Encrypted payload cannot be empty"):
        encryption.decrypt("")


def test_decrypt_invalid_base64(encryption):
    """Test decryption with invalid base64 raises ValueError."""
    with pytest.raises(ValueError, match="Failed to decrypt payload"):
        encryption.decrypt("invalid_base64_!@#$")


def test_decrypt_valid_data(encryption):
    """Test successful decryption of valid encrypted data."""
    # Create a properly encrypted payload for testing
    plaintext = "test data"
    
    # Pad the plaintext to AES block size (16 bytes)
    padded = plaintext.ljust(16, '\x00')
    
    # Encrypt using the same key/iv
    cipher = AES.new(encryption.key, AES.MODE_CBC, encryption.iv)
    encrypted_bytes = cipher.encrypt(padded.encode('utf-8'))
    encrypted_payload = base64.b64encode(encrypted_bytes).decode('utf-8')
    
    # Test decryption
    result = encryption.decrypt(encrypted_payload)
    assert result == plaintext


def test_decrypt_with_padding(encryption):
    """Test decryption correctly removes padding."""
    # Create payload with null byte padding
    plaintext = "short"
    padded = plaintext + '\x00' * 11  # Pad to 16 bytes
    
    # Encrypt
    cipher = AES.new(encryption.key, AES.MODE_CBC, encryption.iv)
    encrypted_bytes = cipher.encrypt(padded.encode('utf-8'))
    encrypted_payload = base64.b64encode(encrypted_bytes).decode('utf-8')
    
    # Test decryption strips padding
    result = encryption.decrypt(encrypted_payload)
    assert result == plaintext
    assert '\x00' not in result


def test_decrypt_with_whitespace_padding(encryption):
    """Test decryption correctly removes whitespace padding."""
    # Create payload with whitespace padding
    plaintext = "test"
    padded = (plaintext + "   ").ljust(16, '\x00')
    
    # Encrypt
    cipher = AES.new(encryption.key, AES.MODE_CBC, encryption.iv)
    encrypted_bytes = cipher.encrypt(padded.encode('utf-8'))
    encrypted_payload = base64.b64encode(encrypted_bytes).decode('utf-8')
    
    # Test decryption strips both whitespace and null padding
    result = encryption.decrypt(encrypted_payload)
    assert result == plaintext


def test_decrypt_invalid_utf8(encryption):
    """Test decryption with invalid UTF-8 data raises ValueError."""
    # Create encrypted data that won't decode as UTF-8
    invalid_bytes = b'\xff\xfe\xfd' + b'\x00' * 13  # Invalid UTF-8 sequence
    
    cipher = AES.new(encryption.key, AES.MODE_CBC, encryption.iv)
    encrypted_bytes = cipher.encrypt(invalid_bytes)
    encrypted_payload = base64.b64encode(encrypted_bytes).decode('utf-8')
    
    with pytest.raises(ValueError, match="Failed to decrypt payload"):
        encryption.decrypt(encrypted_payload)


def test_decrypt_wrong_key():
    """Test decryption with wrong key produces garbled output or error."""
    # Create encryption with one key
    key1 = "d805a5c409dc354b6ccf03a2c29a5825851cf31979abf526ede72570c52cf954"
    iv1 = "408a42beb8a1cefad990098584ed51a5"
    enc1 = SyrEncryption(key1, iv1)
    
    # Encrypt with different key
    key2 = "0000000000000000000000000000000000000000000000000000000000000000"
    iv2 = "00000000000000000000000000000000"
    enc2 = SyrEncryption(key2, iv2)
    
    plaintext = "secret message"
    padded = plaintext.ljust(16, '\x00')
    cipher = AES.new(enc2.key, AES.MODE_CBC, enc2.iv)
    encrypted_bytes = cipher.encrypt(padded.encode('utf-8'))
    encrypted_payload = base64.b64encode(encrypted_bytes).decode('utf-8')
    
    # Decrypting with wrong key should either fail or produce different result
    try:
        result = enc1.decrypt(encrypted_payload)
        assert result != plaintext  # Wrong key produces wrong output
    except ValueError:
        pass  # Or it might fail entirely
