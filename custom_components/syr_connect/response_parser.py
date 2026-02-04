"""Response parser and validator for SYR Connect API."""
from __future__ import annotations

import defusedxml.ElementTree as etree  # noqa: N813
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class ResponseParser:
    """Parse and validate SYR Connect API responses."""

    @staticmethod
    def validate_structure(data: dict, required_path: list[str]) -> bool:
        """Validate that a nested dictionary contains a required path.

        Args:
            data: Dictionary to validate
            required_path: List of keys representing the path to validate

        Returns:
            True if path exists, False otherwise
        """
        current = data
        for key in required_path:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]
        return True

    @staticmethod
    def parse_xml(xml_string: str) -> dict[str, Any]:
        """Parse XML string to dictionary using ElementTree.

        Args:
            xml_string: XML string to parse

        Returns:
            Parsed dictionary representation of XML

        Raises:
            ValueError: If XML parsing fails
        """
        try:
            # defusedxml provides secure XML parsing by default (prevents XXE attacks)
            root = etree.fromstring(xml_string)
            # Wrap in root tag like xmltodict does
            return {root.tag: ResponseParser._element_to_dict(root)}
        except etree.ParseError as err:
            _LOGGER.error("Failed to parse XML: %s", err)
            raise ValueError(f"Invalid XML response: {err}") from err

    @staticmethod
    def _element_to_dict(element: etree.Element) -> Any:
        """Convert XML element to dictionary.

        Args:
            element: XML element to convert

        Returns:
            Dictionary representation of the element
        """
        result: dict[str, Any] = {}

        # Add attributes with @ prefix
        if element.attrib:
            for key, value in element.attrib.items():
                result[f"@{key}"] = value

        # Handle child elements
        children = list(element)
        if children:
            child_dict: dict[str, Any] = {}
            for child in children:
                child_data = ResponseParser._element_to_dict(child)

                # Handle multiple children with same tag
                if child.tag in child_dict:
                    # Convert to list if not already
                    if not isinstance(child_dict[child.tag], list):
                        child_dict[child.tag] = [child_dict[child.tag]]
                    child_dict[child.tag].append(child_data)
                else:
                    child_dict[child.tag] = child_data

            result.update(child_dict)

        # Add text content if present
        if element.text and element.text.strip():
            text = element.text.strip()
            # If there are no children and no attributes, return just the text string
            if not children and not element.attrib:
                return text
            # Otherwise add it as #text key
            result['#text'] = text

        return result if result else {}

    def parse_login_response(self, xml_response: str) -> tuple[str, dict[str, Any]]:
        """Parse login response and extract session ID and projects.

        Args:
            xml_response: XML response string

        Returns:
            Tuple of (session_id, projects_list)

        Raises:
            ValueError: If response structure is invalid
        """
        parsed = self.parse_xml(xml_response)

        # Validate response structure
        if not self.validate_structure(parsed, ['sc', 'api']):
            raise ValueError("Authentication failed: Invalid login response structure")

        # The api element contains the encrypted session data as a string
        api_data = parsed['sc']['api']
        if isinstance(api_data, dict):
            # If it has attributes, the text is in #text
            encrypted_text = api_data.get('#text', '')
        else:
            # Otherwise it's a direct string
            encrypted_text = api_data

        return encrypted_text, parsed

    def parse_decrypted_login(self, decrypted_xml: str) -> tuple[str, list[dict[str, Any]]]:
        """Parse decrypted login data.

        Args:
            decrypted_xml: Decrypted XML string

        Returns:
            Tuple of (session_id, projects_list)

        Raises:
            ValueError: If structure is invalid
        """
        wrapped_xml = f'<xml>{decrypted_xml}</xml>'
        parsed = self.parse_xml(wrapped_xml)

        # Validate session structure
        if not self.validate_structure(parsed, ['xml', 'usr', '@id']):
            raise ValueError("Authentication failed: Invalid credentials or session data")

        session_id = parsed['xml']['usr']['@id']

        # Validate projects structure
        if not self.validate_structure(parsed, ['xml', 'prs', 'pre']):
            raise ValueError("Authentication succeeded but no projects found in account")

        projects_data = parsed['xml']['prs']['pre']

        # Ensure projects is a list
        if not isinstance(projects_data, list):
            projects_data = [projects_data]

        # Parse projects
        projects = []
        for project in projects_data:
            projects.append({
                'id': project['@id'],
                'name': project['@n'],
            })

        return session_id, projects

    def parse_device_list_response(self, xml_response: str) -> list[dict[str, Any]]:
        """Parse device list response.

        Args:
            xml_response: XML response string

        Returns:
            List of devices with their information
        """
        parsed = self.parse_xml(xml_response)
        devices: list[dict[str, Any]] = []
        device_aliases: dict[str, str] = {}

        # Extract device aliases
        if self.validate_structure(parsed, ['sc', 'col']):
            col = parsed['sc']['col']
            if 'dcl' in col:
                dcl_list = col['dcl'] if isinstance(col['dcl'], list) else [col['dcl']]
                for dcl in dcl_list:
                    if '@dclg' in dcl and '@ali' in dcl:
                        device_aliases[dcl['@dclg']] = dcl['@ali']

        # Extract devices
        if not self.validate_structure(parsed, ['sc', 'dvs']):
            _LOGGER.debug("No 'dvs' element found in device list response")
            return devices

        dvs = parsed['sc']['dvs']

        # Check if dvs contains 'd' element(s)
        if 'd' in dvs:
            device_list = dvs['d']
            if not isinstance(device_list, list):
                device_list = [device_list]
        elif isinstance(dvs, dict) and '@dclg' in dvs:
            # dvs itself is a device
            device_list = [dvs]
        else:
            _LOGGER.debug("No devices found in 'dvs' element: %s", dvs)
            return devices

        _LOGGER.debug("Found %d device(s) in response", len(device_list))

        for device in device_list:
            if '@dclg' in device:
                dclg_id = device['@dclg']
                serial_number = device.get('@sn', 'Unknown')
                device_name = device_aliases.get(dclg_id, serial_number)

                _LOGGER.debug("Adding device: %s (DCLG: %s, SN: %s)", device_name, dclg_id, serial_number)

                devices.append({
                    'id': serial_number,  # Use serial number as device ID
                    'dclg': dclg_id,
                    'serial_number': serial_number,
                    'name': device_name,
                })
            else:
                _LOGGER.debug("Skipping device without @dclg: %s", device)

        return devices

    def parse_device_status_response(self, xml_response: str) -> dict[str, Any] | None:
        """Parse device status response.

        Args:
            xml_response: XML response string

        Returns:
            Dictionary of status attributes or None if response is incomplete
        """
        parsed = self.parse_xml(xml_response)

        if 'sc' not in parsed:
            _LOGGER.warning("No 'sc' element in status response")
            return None

        # Prefer responses that include the detailed device entries under
        # <dvs><d>...<c n="..." v="..."/>...</d></dvs>. If that detailed
        # structure is missing (e.g. response only contains <col><dcl .../>),
        # treat the response as incomplete and skip updating sensors.
        sc = parsed['sc']
        if 'dvs' not in sc:
            _LOGGER.debug("Status response missing 'dvs' element; treating as incomplete: %s", sc.get('col'))
            return None

        dvs = sc['dvs']
        # Normalize device list
        device_list = None
        if isinstance(dvs, dict) and 'd' in dvs:
            device_list = dvs['d']
        elif isinstance(dvs, list):
            device_list = dvs
        elif isinstance(dvs, dict) and '@dclg' in dvs:
            device_list = [dvs]

        if not device_list:
            _LOGGER.warning("Status response 'dvs' element contains no device entries; skipping update: %s", dvs)
            return None

        # Ensure at least one device entry contains detailed <c> children
        has_c = False
        if isinstance(device_list, list):
            for d in device_list:
                if isinstance(d, dict) and 'c' in d:
                    has_c = True
                    break
        elif isinstance(device_list, dict) and 'c' in device_list:
            has_c = True

        if not has_c:
            _LOGGER.warning("Device entries in 'dvs' lack <c> children; skipping update")
            return None

        return self._flatten_attributes(parsed['sc'])

    def parse_statistics_response(self, xml_response: str) -> dict[str, Any]:
        """Parse statistics response.

        Args:
            xml_response: XML response string

        Returns:
            Dictionary of statistics data
        """
        parsed = self.parse_xml(xml_response)

        # Check for error messages
        if self.validate_structure(parsed, ['sc', 'msg']):
            _LOGGER.warning("Statistics API returned message: %s", parsed['sc']['msg'])
            return {}

        if 'sc' not in parsed:
            _LOGGER.warning("No 'sc' element in statistics response")
            return {}

        # Remove checksum before flattening
        if 'cs' in parsed['sc']:
            del parsed['sc']['cs']

        return self._flatten_attributes(parsed['sc'])

    @staticmethod
    def _flatten_attributes(data: dict | list, prefix: str = "") -> dict[str, Any]:
        """Flatten XML attributes to simple dict.

        Args:
            data: Data structure to flatten
            prefix: Prefix for nested keys

        Returns:
            Flattened dictionary
        """
        result = {}

        if isinstance(data, dict):
            for key, value in data.items():
                # Skip checksum
                if key == 'cs':
                    continue

                # Handle attributes (starting with @)
                if key.startswith('@'):
                    result[key[1:]] = value

                # Handle text content
                elif key == '#text':
                    result['_text'] = value

                # Handle 'c' tags which contain actual data
                elif key == 'c':
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict) and '@n' in item and '@v' in item:
                                name = item['@n']
                                result[name] = item['@v']
                                for extra in ("dt", "m", "acd", "ih"):
                                    if f"@{extra}" in item:
                                        result[f"{name}_{extra}"] = item[f"@{extra}"]
                    elif isinstance(value, dict) and '@n' in value and '@v' in value:
                        name = value['@n']
                        result[name] = value['@v']
                        for extra in ("dt", "m", "acd", "ih"):
                            if f"@{extra}" in value:
                                result[f"{name}_{extra}"] = value[f"@{extra}"]

                # Handle nested structures
                elif isinstance(value, dict | list):
                    nested = ResponseParser._flatten_attributes(value, prefix)
                    result.update(nested)

                # Handle simple values
                else:
                    result[key] = value

        elif isinstance(data, list):
            for item in data:
                nested = ResponseParser._flatten_attributes(item, prefix)
                result.update(nested)

        return result
