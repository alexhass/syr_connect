"""SYR Connect API client."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
import base64
from Cryptodome.Cipher import AES

import aiohttp
import xmltodict

from .const import (
    API_LOGIN_URL,
    API_DEVICE_LIST_URL,
    API_DEVICE_STATUS_URL,
    API_SET_STATUS_URL,
    API_STATISTICS_URL,
    ENCRYPTION_KEY,
    ENCRYPTION_IV,
    CHECKSUM_KEY1,
    CHECKSUM_KEY2,
    APP_VERSION,
    USER_AGENT,
)
from .checksum import SyrChecksum

_LOGGER = logging.getLogger(__name__)


class SyrConnectAPI:
    """API client for SYR Connect."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        """Initialize the API client."""
        self.session = session
        self.username = username
        self.password = password
        self.session_data: str = ""  # Session ID as string
        self.projects: list[dict[str, Any]] = []
        self.devices: list[dict[str, Any]] = []
        
        # Setup encryption
        self.key = bytes.fromhex(ENCRYPTION_KEY)
        self.iv = bytes.fromhex(ENCRYPTION_IV)
        
        # Setup checksum calculator
        self.checksum = SyrChecksum(CHECKSUM_KEY1, CHECKSUM_KEY2)

    def _decrypt_payload(self, encrypted_payload: str) -> str:
        """Decrypt an encrypted payload."""
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
            raise

    def _get_timestamp(self) -> str:
        """Get current timestamp in required format."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async def login(self) -> bool:
        """Login to SYR Connect API."""
        _LOGGER.info("Attempting login for user: %s", self.username)
        timestamp = self._get_timestamp()
        _LOGGER.debug("Using timestamp: %s", timestamp)
        
        payload = (
            f'<nfo v="SYR Connect" version="3.7.10" osv="15.8.3" '
            f'os="iOS" dn="iPhone" ts="{timestamp}" tzo="01:00:00" '
            f'lng="de" reg="DE" />'
            f'<usr n="{self.username}" v="{self.password}" />'
        )
        
        xml_data = f'<?xml version="1.0" encoding="utf-8"?><sc><api version="1.0">{payload}</api></sc>'
        _LOGGER.debug("Login request payload prepared (length: %d)", len(xml_data))
        
        headers = {
            'Content-Type': 'text/xml',
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'User-Agent': USER_AGENT,
            'Accept-Language': 'de-DE,de;q=0.9',
        }
        
        try:
            _LOGGER.debug("Sending login request to %s", API_LOGIN_URL)
            async with self.session.post(
                API_LOGIN_URL, data=xml_data, headers=headers
            ) as response:
                _LOGGER.debug("Login response status: %d", response.status)
                response.raise_for_status()
                xml_response = await response.text()
                _LOGGER.debug("Login response received (length: %d)", len(xml_response))
                _LOGGER.debug("Login XML response: %s", xml_response)
                
                # Parse XML response
                parsed = xmltodict.parse(xml_response)
                _LOGGER.debug("Login response parsed successfully")
                
                # Decrypt the encrypted response
                encrypted_text = parsed['sc']['api']['#text']
                _LOGGER.debug("Extracting encrypted payload from response")
                decrypted = self._decrypt_payload(encrypted_text)
                _LOGGER.debug("Decrypted login payload: %s", decrypted)
                
                # Parse decrypted XML
                decrypted_xml = f'<xml>{decrypted}</xml>'
                parsed_decrypted = xmltodict.parse(decrypted_xml)
                _LOGGER.debug("Decrypted XML parsed successfully")
                
                # Store session data
                self.session_data = parsed_decrypted['xml']['usr']['@id']
                _LOGGER.info("Session ID obtained: %s", self.session_data)
                
                # Store projects
                projects = parsed_decrypted['xml']['prs']['pre']
                _LOGGER.debug("Raw projects data type: %s", type(projects))
                if not isinstance(projects, list):
                    projects = [projects]
                    _LOGGER.debug("Converted single project to list")
                
                self.projects = []
                for project in projects:
                    project_info = {
                        'id': project['@id'],
                        'name': project['@n'],
                    }
                    self.projects.append(project_info)
                    _LOGGER.debug("Found project: %s (ID: %s)", project_info['name'], project_info['id'])
                
                _LOGGER.info("Login successful, found %d project(s)", len(self.projects))
                return True
                
        except Exception as err:
            _LOGGER.error("Login failed: %s", err)
            raise

    def _create_payload_with_checksum(self, payload: str) -> str:
        """Add checksum to payload."""
        self.checksum.reset_checksum()
        self.checksum.add_xml_to_checksum(payload)
        checksum_value = self.checksum.get_checksum()
        
        return payload.replace('</sc>', f'<cs v="{checksum_value}"/></sc>')

    async def get_devices(self, project_id: str) -> list[dict[str, Any]]:
        """Get devices for a project."""
        _LOGGER.info("Getting devices for project: %s", project_id)
        
        # Build the XML payload like ioBroker adapter
        payload = (
            f'<?xml version="1.0" encoding="utf-8"?><sc>'
            f'<si v="{APP_VERSION}"/>'
            f'<us ug="{self.session_data}"/>'
            f'<prs><pr pg="{project_id}"/></prs>'
            f'</sc>'
        )
        
        # Calculate checksum like ioBroker: checksum of entire payload before adding <cs>
        self.checksum.reset_checksum()
        self.checksum.add_xml_to_checksum(payload)
        checksum_value = self.checksum.get_checksum()
        
        # Replace </sc> with <cs> tag
        payload = payload.replace('</sc>', f'<cs v="{checksum_value}"/></sc>')
        _LOGGER.debug("Payload prepared: %s", payload)
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'User-Agent': USER_AGENT,
            'Accept-Language': 'de-DE,de;q=0.9',
        }
        
        try:
            _LOGGER.debug("Sending device list request to %s", API_DEVICE_LIST_URL)
            async with self.session.post(
                API_DEVICE_LIST_URL,
                data={'xml': payload},
                headers=headers
            ) as response:
                _LOGGER.debug("Device list response status: %d", response.status)
                response.raise_for_status()
                xml_response = await response.text()
                _LOGGER.debug("Device list response received (length: %d)", len(xml_response))
                _LOGGER.debug("Device list XML response: %s", xml_response)
                
                parsed = xmltodict.parse(xml_response)
                _LOGGER.debug("Device list XML parsed successfully")
                
                devices = []
                
                # Extract device aliases (pretty names) from col/dcl structure
                device_aliases = {}
                if 'sc' in parsed and 'col' in parsed['sc']:
                    col = parsed['sc']['col']
                    _LOGGER.debug("Found 'col' in response, type: %s", type(col))
                    if 'dcl' in col:
                        dcl_list = col['dcl']
                        if not isinstance(dcl_list, list):
                            dcl_list = [dcl_list]
                        
                        for dcl in dcl_list:
                            if '@dclg' in dcl and '@ali' in dcl:
                                device_id = dcl['@dclg']
                                alias = dcl['@ali']
                                device_aliases[device_id] = alias
                                _LOGGER.info("Found device alias: %s -> %s", device_id, alias)
                else:
                    _LOGGER.warning("No 'col' element found in device list response")
                
                # Handle different API response structures
                if 'sc' in parsed and 'dvs' in parsed['sc']:
                    dvs = parsed['sc']['dvs']
                    _LOGGER.debug("Found 'dvs' in response, type: %s", type(dvs))
                    
                    # Check if dvs.d exists (current API structure)
                    if 'd' in dvs:
                        device_list = dvs['d']
                        _LOGGER.debug("Using dvs.d structure")
                    elif isinstance(dvs, list):
                        device_list = dvs
                        _LOGGER.debug("dvs is already a list")
                    else:
                        device_list = [dvs]
                        _LOGGER.debug("Wrapped dvs in list")
                    
                    if not isinstance(device_list, list):
                        device_list = [device_list]
                        _LOGGER.debug("Converted single device to list")
                    
                    for idx, device in enumerate(device_list):
                        _LOGGER.debug("Processing device %d: %s", idx + 1, type(device))
                        if '@dclg' in device:
                            dclg_id = device['@dclg']
                            serial_number = device.get('@sn', 'Unknown')
                            
                            _LOGGER.debug("Device DCLG ID: %s, SN: %s", dclg_id, serial_number)
                            _LOGGER.debug("Available aliases: %s", device_aliases)
                            
                            # Use alias (ali) if available, otherwise fall back to serial number (sn)
                            if dclg_id in device_aliases:
                                device_name = device_aliases[dclg_id]
                                _LOGGER.info("Using alias for device %s: %s", dclg_id, device_name)
                            else:
                                device_name = serial_number
                                _LOGGER.info("No alias found for device %s, using SN: %s", dclg_id, device_name)
                            
                            device_info = {
                                'id': serial_number,  # Use serial number as device ID
                                'dclg': dclg_id,  # Keep DCLG for API calls
                                'name': device_name,
                                'project_id': project_id,
                            }
                            devices.append(device_info)
                            _LOGGER.debug("Device found: %s (ID: %s, DCLG: %s)", device_info['name'], device_info['id'], dclg_id)
                        else:
                            _LOGGER.warning("Device %d missing @dclg attribute", idx + 1)
                
                _LOGGER.info("Found %d device(s) in project %s", len(devices), project_id)
                return devices
                
        except Exception as err:
            _LOGGER.error("Failed to get devices: %s", err)
            raise

    async def get_device_status(self, device_id: str) -> dict[str, Any]:
        """Get status of a device."""
        _LOGGER.debug("Getting status for device: %s", device_id)
        
        # Build the XML payload like ioBroker adapter
        payload = (
            f'<?xml version="1.0" encoding="utf-8"?><sc>'
            f'<si v="{APP_VERSION}"/>'
            f'<us ug="{self.session_data}"/>'
            f'<col><dcl dclg="{device_id}" fref="1"/></col>'
            f'</sc>'
        )
        
        # Calculate checksum like ioBroker: checksum of entire payload before adding <cs>
        self.checksum.reset_checksum()
        self.checksum.add_xml_to_checksum(payload)
        checksum_value = self.checksum.get_checksum()
        
        # Replace </sc> with <cs> tag
        payload = payload.replace('</sc>', f'<cs v="{checksum_value}"/></sc>')
        _LOGGER.debug("Status request payload: %s", payload)
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'User-Agent': USER_AGENT,
            'Accept-Language': 'de-DE,de;q=0.9',
        }
        
        try:
            _LOGGER.debug("Sending status request to %s", API_DEVICE_STATUS_URL)
            async with self.session.post(
                API_DEVICE_STATUS_URL,
                data={'xml': payload},
                headers=headers
            ) as response:
                _LOGGER.debug("Status response status: %d", response.status)
                response.raise_for_status()
                xml_response = await response.text()
                _LOGGER.debug("Status response received (length: %d)", len(xml_response))
                _LOGGER.debug("Status XML response: %s", xml_response)
                
                parsed = xmltodict.parse(xml_response)
                
                if 'sc' in parsed:
                    status_data = self._flatten_attributes(parsed['sc'])
                    _LOGGER.debug("Status data flattened: %d attributes", len(status_data))
                    return status_data
                
                _LOGGER.warning("No 'sc' element in status response")
                return {}
                
        except Exception as err:
            _LOGGER.error("Failed to get device status: %s", err)
            raise

    async def set_device_status(self, device_id: str, command: str, value: Any) -> bool:
        """Set device status/command."""
        _LOGGER.info("Setting device %s command %s to %s", device_id, command, value)
        
        # Convert boolean to int
        original_value = value
        if isinstance(value, bool):
            value = 1 if value else 0
            _LOGGER.debug("Converted boolean %s to int %s", original_value, value)
        
        # Build the XML payload like ioBroker adapter
        payload = (
            f'<?xml version="1.0" encoding="utf-8"?><sc>'
            f'<si v="{APP_VERSION}"/>'
            f'<us ug="{self.session_data}"/>'
            f'<col><dcl dclg="{device_id}" fref="1">'
            f'<c n="{command}" v="{value}"/>'
            f'</dcl></col>'
            f'</sc>'
        )
        
        # Calculate checksum like ioBroker: checksum of entire payload before adding <cs>
        self.checksum.reset_checksum()
        self.checksum.add_xml_to_checksum(payload)
        checksum_value = self.checksum.get_checksum()
        
        # Replace </sc> with <cs> tag
        payload = payload.replace('</sc>', f'<cs v="{checksum_value}"/></sc>')
        _LOGGER.debug("Set status payload: %s", payload)
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'User-Agent': USER_AGENT,
            'Accept-Language': 'de-DE,de;q=0.9',
        }
        
        try:
            _LOGGER.debug("Sending set status request to %s", API_SET_STATUS_URL)
            async with self.session.post(
                API_SET_STATUS_URL,
                data={'xml': payload},
                headers=headers
            ) as response:
                _LOGGER.debug("Set status response status: %d", response.status)
                response.raise_for_status()
                xml_response = await response.text()
                _LOGGER.debug("Set status XML response: %s", xml_response)
                _LOGGER.info("Successfully set %s=%s for device %s", command, value, device_id)
                return True
                
        except Exception as err:
            _LOGGER.error("Failed to set device status: %s", err)
            raise

    async def get_statistics(self, device_id: str, statistic_type: str = "water") -> dict[str, Any]:
        """Get statistics for a device (LexPlus).
        
        Args:
            device_id: The device ID
            statistic_type: Type of statistic - "water" or "salt"
            
        Returns:
            Dictionary with statistics data
        """
        _LOGGER.debug("Getting %s statistics for device: %s", statistic_type, device_id)
        
        # Build the base XML payload like ioBroker adapter
        payload = (
            f'<?xml version="1.0" encoding="utf-8"?><sc>'
            f'<si v="{APP_VERSION}"/>'
            f'<us ug="{self.session_data}"/>'
            f'<col><dcl dclg="{device_id}"></dcl></col>'
            f'</sc>'
        )
        
        # Add statistic-specific payload inside <dcl> tag like ioBroker
        if statistic_type == "salt":
            # Salt statistics: t="2" for salt
            statistic_payload = '<sh t="2" rtyp="1" lg="de" rg="DE" unit="kg"/>'
        else:
            # Water statistics: t="1" for water (default)
            statistic_payload = '<sh t="1" rtyp="1" lg="de" rg="DE" unit="l"/>'
        
        # Insert the statistic payload before </dcl>
        payload = payload.replace('></dcl>', f'>{statistic_payload}</dcl>')
        
        # Calculate checksum like ioBroker: checksum of entire payload before adding <cs>
        self.checksum.reset_checksum()
        self.checksum.add_xml_to_checksum(payload)
        checksum_value = self.checksum.get_checksum()
        
        # Replace </sc> with <cs> tag
        payload = payload.replace('</sc>', f'<cs v="{checksum_value}"/></sc>')
        _LOGGER.debug("Statistics payload: %s", payload)
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'User-Agent': USER_AGENT,
            'Accept-Language': 'de-DE,de;q=0.9',
        }
        
        try:
            _LOGGER.debug("Sending statistics request to %s", API_STATISTICS_URL)
            async with self.session.post(
                API_STATISTICS_URL,
                data={'xml': payload},
                headers=headers
            ) as response:
                _LOGGER.debug("Statistics response status: %d", response.status)
                response.raise_for_status()
                xml_response = await response.text()
                _LOGGER.debug("Statistics response received (length: %d)", len(xml_response))
                _LOGGER.debug("Statistics XML response: %s", xml_response)
                
                parsed = xmltodict.parse(xml_response)
                
                # Check for errors in response
                if 'sc' in parsed and 'msg' in parsed['sc']:
                    error_msg = parsed['sc']['msg']
                    _LOGGER.warning("Statistics API returned message: %s", error_msg)
                    return {}
                
                if 'sc' in parsed:
                    # Remove checksum from response
                    if 'cs' in parsed['sc']:
                        del parsed['sc']['cs']
                    
                    stats_data = self._flatten_attributes(parsed['sc'])
                    _LOGGER.debug("Statistics data flattened: %d attributes", len(stats_data))
                    return stats_data
                
                _LOGGER.warning("No 'sc' element in statistics response")
                return {}
                
        except Exception as err:
            _LOGGER.error("Failed to get %s statistics: %s", statistic_type, err)
            raise

    def _flatten_attributes(self, data: dict | list, prefix: str = "") -> dict[str, Any]:
        """Flatten XML attributes to simple dict, handling SYR Connect API structure.
        
        This method specifically handles the structure from GetDeviceCollectionStatus
        where data is in <c n="name" v="value" /> tags.
        """
        result = {}
        
        if isinstance(data, dict):
            for key, value in data.items():
                # Skip checksum
                if key == 'cs':
                    continue
                    
                # Handle attributes (starting with @)
                if key.startswith('@'):
                    clean_key = key[1:]
                    result[clean_key] = value
                    
                # Handle text content
                elif key == '#text':
                    result['_text'] = value
                    
                # Handle 'c' tags which contain the actual data as attributes
                elif key == 'c':
                    if isinstance(value, list):
                        # Multiple <c> tags
                        for item in value:
                            if isinstance(item, dict) and '@n' in item and '@v' in item:
                                # Use the 'n' attribute as key and 'v' attribute as value
                                name = item['@n']
                                val = item['@v']
                                result[name] = val
                                # Also include dt (datetime) if present
                                if '@dt' in item:
                                    result[f"{name}_dt"] = item['@dt']
                    elif isinstance(value, dict):
                        # Single <c> tag
                        if '@n' in value and '@v' in value:
                            name = value['@n']
                            val = value['@v']
                            result[name] = val
                            if '@dt' in value:
                                result[f"{name}_dt"] = value['@dt']
                                
                # Handle nested structures
                elif isinstance(value, (dict, list)):
                    nested = self._flatten_attributes(value, prefix)
                    result.update(nested)
                    
                # Handle simple values
                else:
                    result[key] = value
                    
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                nested = self._flatten_attributes(item, prefix)
                result.update(nested)
        
        return result
