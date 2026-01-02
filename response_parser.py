"""Response parser and validator for SYR Connect API."""
from __future__ import annotations

import logging
from typing import Any

import xmltodict

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
        """Parse XML string to dictionary.
        
        Args:
            xml_string: XML string to parse
            
        Returns:
            Parsed dictionary
            
        Raises:
            ValueError: If XML parsing fails
        """
        try:
            return xmltodict.parse(xml_string)
        except Exception as err:
            _LOGGER.error("Failed to parse XML: %s", err)
            raise ValueError(f"Invalid XML response: {err}") from err

    def parse_login_response(self, xml_response: str) -> tuple[str, list[dict[str, Any]]]:
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
        if not self.validate_structure(parsed, ['sc', 'api', '#text']):
            raise ValueError("Invalid login response structure")
        
        return parsed['sc']['api']['#text'], parsed

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
            raise ValueError("Invalid decrypted response structure")
        
        session_id = parsed['xml']['usr']['@id']
        
        # Validate projects structure
        if not self.validate_structure(parsed, ['xml', 'prs', 'pre']):
            raise ValueError("No projects found in response")
        
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
        devices = []
        device_aliases = {}
        
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
            return devices
        
        dvs = parsed['sc']['dvs']
        device_list = dvs.get('d', dvs)
        
        if not isinstance(device_list, list):
            device_list = [device_list]
        
        for device in device_list:
            if '@dclg' in device:
                dclg_id = device['@dclg']
                serial_number = device.get('@sn', 'Unknown')
                device_name = device_aliases.get(dclg_id, serial_number)
                
                devices.append({
                    'dclg': dclg_id,
                    'serial_number': serial_number,
                    'name': device_name,
                })
        
        return devices

    def parse_device_status_response(self, xml_response: str) -> dict[str, Any]:
        """Parse device status response.
        
        Args:
            xml_response: XML response string
            
        Returns:
            Dictionary of status attributes
        """
        parsed = self.parse_xml(xml_response)
        
        if 'sc' not in parsed:
            _LOGGER.warning("No 'sc' element in status response")
            return {}
        
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
                                if '@dt' in item:
                                    result[f"{name}_dt"] = item['@dt']
                    elif isinstance(value, dict) and '@n' in value and '@v' in value:
                        name = value['@n']
                        result[name] = value['@v']
                        if '@dt' in value:
                            result[f"{name}_dt"] = value['@dt']
                
                # Handle nested structures
                elif isinstance(value, (dict, list)):
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
