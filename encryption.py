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

            # Remove padding manually (handle non-standard padding)
            result = decrypted.decode('utf-8').rstrip('\x00').rstrip()
            _LOGGER.debug("Decryption successful (result length: %d chars)", len(result))
            return result
        except Exception as err:
            _LOGGER.error("Decryption failed: %s", err)
            raise ValueError(f"Failed to decrypt payload: {err}") from err
