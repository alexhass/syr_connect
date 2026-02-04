"""Checksum calculation for SYR Connect API."""
from __future__ import annotations

import defusedxml.ElementTree as etree


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
        self.checksum_value = 0

    @staticmethod
    def extract_bits(byte: int, start: int, length: int) -> int:
        """Extract a subset of bits from a byte.

        Args:
            byte: The byte to extract bits from
            start: The starting bit position
            length: The number of bits to extract

        Returns:
            Extracted bits as a number
        """
        return (byte >> start) & ((1 << length) - 1)

    def compute_checksum_value(self, value: str) -> int:
        """Compute a checksum-compatible numeric value from the input string.

        Args:
            value: The input string to process

        Returns:
            Computed numeric checksum contribution
        """
        normalized = (value or '').strip()
        if not normalized:
            return 0

        # Convert the normalized string to bytes (UTF-8)
        buf = normalized.encode('utf-8')
        bytes_arr = list(buf)  # array of numbers in 0..255

        # Calculate how many 5-bit chunks are available
        total_bits = len(bytes_arr) * 8
        num_chunks = (total_bits + 4) // 5  # equivalent to Math.ceil(totalBits / 5)

        contribution = 0
        bit_offset = 0
        byte_index = 0

        # Process each 5-bit chunk
        for chunk_index in range(num_chunks):
            if bit_offset >= 8:
                byte_index += 1
                bit_offset = bit_offset % 8

            # Get the current byte (or 0 if out-of-range)
            current_byte = bytes_arr[byte_index] if byte_index < len(bytes_arr) else 0

            # Shift current byte
            shifted = (current_byte << bit_offset) & 0xff  # keep only 8 bits

            # If bit_offset > 3, we need bits from the next byte
            if bit_offset > 3:
                next_byte = bytes_arr[byte_index + 1] if byte_index + 1 < len(bytes_arr) else 0
                shift_amt = 8 - (bit_offset - 3)
                next_part = ((next_byte >> shift_amt) << 3) & 0xff
                shifted = shifted | next_part

            # Extract the 5-bit value
            five_bit_value = shifted >> 3  # this is the extracted 5-bit chunk (0..31)

            # Use the secret keys
            key_char = self.key[chunk_index % len(self.key)]
            offset = self.base_characters.find(key_char)
            if offset < 0:
                offset = 0  # safeguard

            sum_val = five_bit_value + offset

            # If the sum is greater than or equal to base_characters length, wrap it
            if sum_val >= len(self.base_characters):
                sum_val = sum_val - len(self.base_characters) + 1

            # Add the character code from base_characters
            contribution += ord(self.base_characters[sum_val]) & 0xff

            # Advance the bit offset by 5 for the next chunk
            bit_offset += 5

        return contribution

    def add_to_checksum(self, input_str: str) -> None:
        """Add a string's computed value to the checksum total.

        Args:
            input_str: The input string to process
        """
        self.checksum_value += self.compute_checksum_value(input_str)

    def add_xml_to_checksum(self, xml_string: str) -> None:
        """Parse an XML string, extract all attribute values, and add them to the checksum.

        Args:
            xml_string: The XML string to process
        """
        try:
            # Parse XML using ElementTree
            root = etree.fromstring(xml_string)
            values: list[str] = []

            def extract_values(element: etree.Element) -> None:
                """Recursively extract all attribute values from XML element.

                Args:
                    element: The XML element to extract values from
                """
                # Extract attribute values (except 'n')
                for key, value in element.attrib.items():
                    if key != 'n':
                        values.append(str(value))

                # Recursively process child elements
                for child in element:
                    extract_values(child)

            extract_values(root)

            # Add each extracted value to the checksum calculation
            for value in values:
                self.add_to_checksum(value)

        except etree.ParseError:
            # In case of error, silently continue
            pass

    def reset_checksum(self) -> None:
        """Reset the checksum to zero."""
        self.checksum_value = 0

    def get_checksum(self) -> str:
        """Return the computed checksum as a hexadecimal string.

        Returns:
            Checksum value in uppercase hexadecimal
        """
        return format(self.checksum_value, 'X')

    def set_checksum(self, hex_string: str) -> None:
        """Manually set the checksum value from a hex string.

        Args:
            hex_string: Hexadecimal string representation of the checksum
        """
        self.checksum_value = int(hex_string, 16)
