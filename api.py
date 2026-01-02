"""SYR Connect API client."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

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
from .encryption import SyrEncryption
from .payload_builder import PayloadBuilder
from .response_parser import ResponseParser
from .http_client import HTTPClient

_LOGGER = logging.getLogger(__name__)


class SyrConnectAPI:
    """API client for SYR Connect."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.session_data: str = ""  # Session ID as string
        self.projects: list[dict[str, Any]] = []
        
        # Initialize helper components
        self.encryption = SyrEncryption(ENCRYPTION_KEY, ENCRYPTION_IV)
        self.checksum = SyrChecksum(CHECKSUM_KEY1, CHECKSUM_KEY2)
        self.payload_builder = PayloadBuilder(APP_VERSION, self.checksum)
        self.response_parser = ResponseParser()
        self.http_client = HTTPClient(session, USER_AGENT)

    async def login(self) -> bool:
        """Login to SYR Connect API."""
        _LOGGER.debug("Attempting login for user: %s", self.username)
        
        # Build login payload
        xml_data = self.payload_builder.build_login_payload(self.username, self.password)
        _LOGGER.debug("Login payload prepared")
        
        try:
            # Make login request
            xml_response = await self.http_client.post(
                API_LOGIN_URL, 
                xml_data, 
                content_type='text/xml'
            )
            _LOGGER.debug("Login XML response: %s", xml_response)
            
            # Parse and decrypt response
            encrypted_text, _ = self.response_parser.parse_login_response(xml_response)
            decrypted = self.encryption.decrypt(encrypted_text)
            _LOGGER.debug("Decrypted login payload: %s", decrypted)
            
            # Parse decrypted data
            self.session_data, self.projects = self.response_parser.parse_decrypted_login(decrypted)
            _LOGGER.info("Login successful, session ID: %s", self.session_data)
            _LOGGER.info("Found %d project(s)", len(self.projects))
            
            for project in self.projects:
                _LOGGER.debug("Project: %s (ID: %s)", project['name'], project['id'])
            
            return True
            
        except Exception as err:
            _LOGGER.error("Login failed: %s", err)
            raise

    async def get_devices(self, project_id: str) -> list[dict[str, Any]]:
        """Get devices for a project."""
        _LOGGER.debug("Getting devices for project: %s", project_id)
        
        # Build payload
        payload = self.payload_builder.build_device_list_payload(self.session_data, project_id)
        _LOGGER.debug("Payload prepared: %s", payload)
        
        try:
            # Make request
            xml_response = await self.http_client.post(
                API_DEVICE_LIST_URL,
                {'xml': payload}
            )
            _LOGGER.debug("Device list XML response: %s", xml_response)
            
            # Parse response
            devices = self.response_parser.parse_device_list_response(xml_response)
            
            # Add project_id to each device
            for device in devices:
                device['id'] = device['serial_number']  # Use SN as ID
                device['project_id'] = project_id
                _LOGGER.debug(
                    "Device found: %s (ID: %s, DCLG: %s)", 
                    device['name'], device['id'], device['dclg']
                )
            
            _LOGGER.debug("Found %d device(s) in project %s", len(devices), project_id)
            return devices
            
        except Exception as err:
            _LOGGER.error("Failed to get devices: %s", err)
            raise

    async def get_device_status(self, device_id: str) -> dict[str, Any]:
        """Get status of a device."""
        _LOGGER.debug("Getting status for device: %s", device_id)
        
        # Build payload
        payload = self.payload_builder.build_device_status_payload(self.session_data, device_id)
        _LOGGER.debug("Status request payload: %s", payload)
        
        try:
            # Make request
            xml_response = await self.http_client.post(
                API_DEVICE_STATUS_URL,
                {'xml': payload}
            )
            _LOGGER.debug("Status XML response: %s", xml_response)
            
            # Parse response
            status_data = self.response_parser.parse_device_status_response(xml_response)
            _LOGGER.debug("Status data parsed: %d attributes", len(status_data))
            return status_data
            
        except Exception as err:
            _LOGGER.error("Failed to get device status: %s", err)
            raise

    async def set_device_status(self, device_id: str, command: str, value: Any) -> bool:
        """Set device status/command."""
        _LOGGER.debug("Setting device %s command %s to %s", device_id, command, value)
        
        # Convert boolean to int
        if isinstance(value, bool):
            original_value = value
            value = 1 if value else 0
            _LOGGER.debug("Converted boolean %s to int %s", original_value, value)
        
        # Build payload
        payload = self.payload_builder.build_set_status_payload(
            self.session_data, device_id, command, value
        )
        _LOGGER.debug("Set status payload: %s", payload)
        
        try:
            # Make request
            xml_response = await self.http_client.post(
                API_SET_STATUS_URL,
                {'xml': payload}
            )
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
        
        # Build payload
        payload = self.payload_builder.build_statistics_payload(
            self.session_data, device_id, statistic_type
        )
        _LOGGER.debug("Statistics payload: %s", payload)
        
        try:
            # Make request
            xml_response = await self.http_client.post(
                API_STATISTICS_URL,
                {'xml': payload}
            )
            _LOGGER.debug("Statistics XML response: %s", xml_response)
            
            # Parse response
            stats_data = self.response_parser.parse_statistics_response(xml_response)
            _LOGGER.debug("Statistics data parsed: %d attributes", len(stats_data))
            return stats_data
            
        except Exception as err:
            _LOGGER.error("Failed to get %s statistics: %s", statistic_type, err)
            raise
