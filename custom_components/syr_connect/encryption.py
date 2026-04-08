"""Encryption and decryption utilities for SYR Connect API."""
from __future__ import annotations

import base64
import logging

from Cryptodome.Cipher import AES

_LOGGER = logging.getLogger(__name__)


class SyrEncryption:
    """Handle encryption and decryption for SYR Connect API."""

    def __init__(self, key: str, iv: str) -> None:
        """Initialize encryption handler.

        Args:
            key: Hexadecimal encryption key
            iv: Hexadecimal initialization vector

        Note:
            Both ``key`` and ``iv`` are fixed constants defined by the SYR Connect
            cloud API protocol. Using a static IV with AES-CBC is a known weakness:
            identical plaintext blocks produce identical ciphertext, which can leak
            patterns to an observer. This is an API constraint that cannot be
            changed on the client side. The risk is limited in practice because
            the IV is only used to decrypt server-side login responses, not to
            encrypt user-controlled data, and each response carries a unique
            session token that varies per login.
        """
        self.key = bytes.fromhex(key)
        self.iv = bytes.fromhex(iv)

    def decrypt(self, encrypted_payload: str) -> str:
        """Decrypt an encrypted payload.

        Args:
            encrypted_payload: Base64-encoded encrypted string

        Returns:
            Decrypted string

        Raises:
            ValueError: If decryption fails or payload is empty
        """
        if not encrypted_payload:
            raise ValueError("Encrypted payload cannot be empty")

        _LOGGER.debug("Decrypting payload (length: %d bytes)", len(encrypted_payload))
        try:
            encrypted_data = base64.b64decode(encrypted_payload)
            _LOGGER.debug("Decoded base64 data (length: %d bytes)", len(encrypted_data))

            cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
            decrypted = cipher.decrypt(encrypted_data)

            # Remove padding manually due to non-standard padding scheme
            # SYR devices use a custom padding approach where the plaintext
            # may be padded with null bytes (\x00) followed by spaces.
            # Standard PKCS7 unpadding would fail, so we manually strip:
            # 1. Null bytes (\x00) - may be present at the end
            # 2. Whitespace - may be used as additional padding
            result = decrypted.decode('utf-8').rstrip('\x00').rstrip()
            _LOGGER.debug("Decryption successful (result length: %d chars)", len(result))
            return result
        except Exception as err:
            _LOGGER.error("Decryption failed: %s", err)
            raise ValueError(f"Failed to decrypt payload: {err}") from err
