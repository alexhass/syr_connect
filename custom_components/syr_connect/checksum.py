"""Checksum calculation for SYR Connect API."""

import base64
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as etree

# Standard Base32 alphabet (RFC 4648); the index of a character is its 5-bit value
_SYR_CONNECT_BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


class SyrChecksum:
    """Calculate checksums for SYR Connect API requests."""

    def __init__(self, base_characters: str, key: str) -> None:
        """Initialize the checksum calculator.

        Args:
            base_characters: A string representing the character set used for encoding
            key: A keyword used in the encoding process
        """
        self.base_characters = base_characters
        self.key = key
        # Position of each key character in base_characters (0 if missing)
        self._key_offsets = [max(base_characters.find(char), 0) for char in key]

    def compute_checksum_value(self, value: str) -> int:
        """Compute a checksum-compatible numeric value from the input string.

        Proprietary SYR algorithm; only step 1 is a standard method:
        1. Base32-encode (RFC 4648) the UTF-8 bytes of the stripped string, giving
           one 5-bit value per character
        2. Shift each value by the position of a key character in base_characters,
           cycling through the key (Vigenère-like)
        3. Wrap values past the alphabet to 1 instead of 0 (a SYR quirk, not a modulo)
        4. Sum the character codes of the resulting base_characters

        This is an obfuscation, not a cryptographic checksum: both keys ship with
        every app, and a sum does not depend on the order of its parts.

        Args:
            value: The input string to process

        Returns:
            Computed numeric checksum contribution
        """
        normalized = (value or '').strip()
        if not normalized:
            return 0

        # Step 1 is standard Base32: each character stands for one 5-bit chunk of the
        # UTF-8 bytes, the last chunk zero-padded. The "=" padding is not a chunk.
        encoded = base64.b32encode(normalized.encode('utf-8')).decode('ascii').rstrip('=')

        contribution = 0
        for chunk_index, char in enumerate(encoded):
            # Shift the chunk by the key character for this position (Vigenère-like)
            index = _SYR_CONNECT_BASE32_ALPHABET.index(char) + self._key_offsets[chunk_index % len(self._key_offsets)]

            # SYR wraps to 1, not 0 (not a modulo); the checksums depend on this quirk
            if index >= len(self.base_characters):
                index -= len(self.base_characters) - 1

            contribution += ord(self.base_characters[index]) & 0xff

        return contribution

    def compute_xml_checksum(self, xml_string: str) -> str:
        """Compute the checksum for an XML string.

        Uses a local accumulator — does not touch any instance state and is
        safe to call concurrently on the same instance.

        Args:
            xml_string: The XML string to process

        Returns:
            Checksum value in uppercase hexadecimal
        """
        try:
            root = etree.fromstring(xml_string)
        except etree.ParseError:
            return format(0, 'X')
        return self.compute_element_checksum(root)

    def compute_element_checksum(self, root: Element) -> str:
        """Compute the checksum for an already built element tree.

        Sums the contributions of all attribute values except ``n`` across ``root`` and its
        descendants. Gives the same result as ``compute_xml_checksum`` on the serialised tree,
        without serialising and re-parsing it.

        Args:
            root: Root element of the request

        Returns:
            Checksum value in uppercase hexadecimal
        """
        checksum_value = sum(
            self.compute_checksum_value(str(value))
            for element in root.iter()
            for key, value in element.attrib.items()
            if key != 'n'
        )
        return format(checksum_value, 'X')
