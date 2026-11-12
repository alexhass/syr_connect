"""Test the SYR Connect encryption module."""

import base64
from typing import Any

from Cryptodome.Cipher import AES
import pytest

from custom_components.syr_connect.const import (
    _SYR_CONNECT_API_SERVICES,
    _SYR_CONNECT_DEFAULT_CF_BUNDLE_IDENTIFIER,
)
from custom_components.syr_connect.encryption import SyrEncryption

_SYR_KEY = "d805a5c409dc354b6ccf03a2c29a5825851cf31979abf526ede72570c52cf954"
_SYR_IV = "408a42beb8a1cefad990098584ed51a5"
_SYR_SERVICE = _SYR_CONNECT_API_SERVICES[_SYR_CONNECT_DEFAULT_CF_BUNDLE_IDENTIFIER]


@pytest.fixture
def encryption() -> Any:
    """Create an encryption instance with the SYR Connect key."""
    return SyrEncryption(_SYR_SERVICE.crypt_key, _SYR_SERVICE.crypt_vector)


def test_encryption_initialization(encryption: SyrEncryption) -> None:
    """The crypt values of SYR Connect decrypt to its AES-256 key and IV."""
    assert encryption.key.hex() == _SYR_KEY
    assert encryption.iv.hex() == _SYR_IV


@pytest.mark.parametrize(
    ("bundle_id", "key", "iv"),
    [
        ("de.consoft.syr.connect", _SYR_KEY, _SYR_IV),
        ("de.consoft.gc.conel.connect", _SYR_KEY, _SYR_IV),
        ("de.consoft.gsh.comfort.connect", _SYR_KEY, _SYR_IV),
        ("de.consoft.isg.concept.connect", _SYR_KEY, _SYR_IV),
        ("de.consoft.sanitaerunion.ditech.connect", _SYR_KEY, _SYR_IV),
        ("de.consoft.isg.optima.connect", _SYR_KEY, _SYR_IV),
        (
            "de.consoft.rwc.connect",
            "ecb1552e674668f493c8be1792cfc299ec335d34fe6a9289729a0daf7c210b17",
            "2482879480e5c67a09888a7526f33a70",
        ),
        (
            "de.consoft.polygonvatro.connect",
            "d86dace397d434ac7ae3a8fcf5ce32f8fa15d683dac02ebf7eebaf0a300be97c",
            "4d5ab24c4bc18e544c8804e921ca451a",
        ),
    ],
)
def test_service_crypt_values(bundle_id: str, key: str, iv: str) -> None:
    """The crypt values of every service decrypt to its key and IV."""
    svc = _SYR_CONNECT_API_SERVICES[bundle_id]

    enc = SyrEncryption(svc.crypt_key, svc.crypt_vector)

    assert enc.key.hex() == key
    assert enc.iv.hex() == iv


def test_decrypt_empty_string(encryption: SyrEncryption) -> None:
    """Test decryption of empty string raises ValueError."""
    with pytest.raises(ValueError, match="Encrypted payload cannot be empty"):
        encryption.decrypt("")


def test_decrypt_invalid_base64(encryption: SyrEncryption) -> None:
    """Test decryption with invalid base64 raises ValueError."""
    with pytest.raises(ValueError, match="Failed to decrypt payload"):
        encryption.decrypt("invalid_base64_!@#$")


def test_decrypt_valid_data(encryption: SyrEncryption) -> None:
    """Test successful decryption of valid encrypted data."""
    # Create a properly encrypted payload for testing
    plaintext = "test data"

    # Pad the plaintext to AES block size (16 bytes)
    padded = plaintext.ljust(16, "\x00")

    # Encrypt using the same key/iv
    cipher = AES.new(encryption.key, AES.MODE_CBC, encryption.iv)
    encrypted_bytes = cipher.encrypt(padded.encode("utf-8"))
    encrypted_payload = base64.b64encode(encrypted_bytes).decode("utf-8")

    # Test decryption
    result = encryption.decrypt(encrypted_payload)
    assert result == plaintext


def test_decrypt_with_padding(encryption: SyrEncryption) -> None:
    """Test decryption correctly removes padding."""
    # Create payload with null byte padding
    plaintext = "short"
    padded = plaintext + "\x00" * 11  # Pad to 16 bytes

    # Encrypt
    cipher = AES.new(encryption.key, AES.MODE_CBC, encryption.iv)
    encrypted_bytes = cipher.encrypt(padded.encode("utf-8"))
    encrypted_payload = base64.b64encode(encrypted_bytes).decode("utf-8")

    # Test decryption strips padding
    result = encryption.decrypt(encrypted_payload)
    assert result == plaintext
    assert "\x00" not in result


def test_decrypt_with_whitespace_padding(encryption: SyrEncryption) -> None:
    """Test decryption correctly removes whitespace padding."""
    # Create payload with whitespace padding
    plaintext = "test"
    padded = (plaintext + "   ").ljust(16, "\x00")

    # Encrypt
    cipher = AES.new(encryption.key, AES.MODE_CBC, encryption.iv)
    encrypted_bytes = cipher.encrypt(padded.encode("utf-8"))
    encrypted_payload = base64.b64encode(encrypted_bytes).decode("utf-8")

    # Test decryption strips both whitespace and null padding
    result = encryption.decrypt(encrypted_payload)
    assert result == plaintext


def test_decrypt_invalid_utf8(encryption: SyrEncryption) -> None:
    """Test decryption with invalid UTF-8 data raises ValueError."""
    # Create encrypted data that won't decode as UTF-8
    invalid_bytes = b"\xff\xfe\xfd" + b"\x00" * 13  # Invalid UTF-8 sequence

    cipher = AES.new(encryption.key, AES.MODE_CBC, encryption.iv)
    encrypted_bytes = cipher.encrypt(invalid_bytes)
    encrypted_payload = base64.b64encode(encrypted_bytes).decode("utf-8")

    with pytest.raises(ValueError, match="Failed to decrypt payload"):
        encryption.decrypt(encrypted_payload)


def test_decrypt_wrong_key() -> None:
    """Test decryption with wrong key produces garbled output or error."""
    # Create encryption with one key
    enc1 = SyrEncryption(_SYR_SERVICE.crypt_key, _SYR_SERVICE.crypt_vector)

    # Encrypt with the different key of another service
    svc = _SYR_CONNECT_API_SERVICES["de.consoft.rwc.connect"]
    enc2 = SyrEncryption(svc.crypt_key, svc.crypt_vector)

    plaintext = "secret message"
    padded = plaintext.ljust(16, "\x00")
    cipher = AES.new(enc2.key, AES.MODE_CBC, enc2.iv)
    encrypted_bytes = cipher.encrypt(padded.encode("utf-8"))
    encrypted_payload = base64.b64encode(encrypted_bytes).decode("utf-8")

    # Decrypting with wrong key should either fail or produce different result
    try:
        result = enc1.decrypt(encrypted_payload)
        assert result != plaintext  # Wrong key produces wrong output
    except ValueError:
        pass  # Or it might fail entirely
