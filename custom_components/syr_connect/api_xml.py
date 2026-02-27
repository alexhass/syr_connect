"""SYR Connect API client."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from .checksum import SyrChecksum
from .const import (
    _SYR_CONNECT_API_XML_DEVICE_GET_STATISTICS_URL,
    _SYR_CONNECT_API_XML_DEVICE_GET_STATUS_URL,
    _SYR_CONNECT_API_XML_DEVICE_LIST_URL,
    _SYR_CONNECT_API_XML_DEVICE_SET_STATUS_URL,
    _SYR_CONNECT_API_XML_LOGIN_URL,
    _SYR_CONNECT_CLIENT_APP_VERSION,
    _SYR_CONNECT_CLIENT_CHECKSUM_KEY1,
    _SYR_CONNECT_CLIENT_CHECKSUM_KEY2,
    _SYR_CONNECT_CLIENT_ENCRYPTION_IV,
    _SYR_CONNECT_CLIENT_ENCRYPTION_KEY,
    _SYR_CONNECT_CLIENT_USER_AGENT,
)
from .encryption import SyrEncryption
from .exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
)
from .http_client import HTTPClient
from .payload_builder import PayloadBuilder
from .response_parser import ResponseParser

_LOGGER = logging.getLogger(__name__)

# Session timeout in minutes
_SESSION_TIMEOUT_MINUTES = 30


class SyrConnectAPI:
    """API client for SYR Connect."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        """Initialize the API client.

        Args:
            session: aiohttp client session
            username: SYR Connect username
            password: SYR Connect password
        """
        self.username = username
        self.password = password
        self.session_data: str = ""  # Session ID as string
        self.session_expires_at: datetime | None = None
        self.projects: list[dict[str, Any]] = []

        # Initialize helper components
        self.encryption = SyrEncryption(_SYR_CONNECT_CLIENT_ENCRYPTION_KEY, _SYR_CONNECT_CLIENT_ENCRYPTION_IV)
        self.checksum = SyrChecksum(_SYR_CONNECT_CLIENT_CHECKSUM_KEY1, _SYR_CONNECT_CLIENT_CHECKSUM_KEY2)
        self.payload_builder = PayloadBuilder(_SYR_CONNECT_CLIENT_APP_VERSION, self.checksum)
        self.response_parser = ResponseParser()
        self.http_client = HTTPClient(session, _SYR_CONNECT_CLIENT_USER_AGENT)

    def is_session_valid(self) -> bool:
        """Check if current session is valid.

        Returns:
            True if session exists and not expired, False otherwise
        """
        if not self.session_data:
            return False

        if self.session_expires_at is None:
            return False

        return datetime.now() < self.session_expires_at

    def _update_session_expiry(self) -> None:
        """Update session expiration time."""
        self.session_expires_at = datetime.now() + timedelta(minutes=_SESSION_TIMEOUT_MINUTES)

    async def login(self) -> bool:
        """Login to SYR Connect API.

        Returns:
            True if login successful

        Raises:
            SyrConnectAuthError: If authentication fails
            SyrConnectConnectionError: If connection fails
        """
        _LOGGER.debug("Attempting login for user: %s", self.username)

        # Build login payload
        xml_data = self.payload_builder.build_login_payload(self.username, self.password)
        _LOGGER.debug("Login payload prepared")

        try:
            # Make login request
            xml_response = await self.http_client.post(
                _SYR_CONNECT_API_XML_LOGIN_URL,
                xml_data,
                content_type='text/xml'
            )
            _LOGGER.debug("Login XML response received")

            # Parse and decrypt response
            encrypted_text, _ = self.response_parser.parse_login_response(xml_response)
            decrypted = self.encryption.decrypt(encrypted_text)
            _LOGGER.info("Login response decrypted successfully")

            # Parse decrypted data
            self.session_data, self.projects = self.response_parser.parse_decrypted_login(decrypted)
            self._update_session_expiry()
            _LOGGER.info("Login successful, found %d project(s)", len(self.projects))

            for project in self.projects:
                _LOGGER.debug("Project: %s (ID: %s)", project['name'], project['id'])

            return True

        except ValueError as err:
            # Parser errors indicate auth failure
            _LOGGER.error("Authentication failed: %s", err)
            raise SyrConnectAuthError(f"Authentication failed: {err}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            error_representation = repr(err)
            _LOGGER.error("Connection failed: %s", error_representation)
            raise SyrConnectConnectionError(f"Connection failed: {error_representation}") from err
        except Exception as err:
            error_representation = repr(err)
            _LOGGER.error("Login failed with unexpected error: %s", error_representation)
            raise SyrConnectConnectionError(f"Login failed: {error_representation}") from err

    async def get_devices(self, project_id: str) -> list[dict[str, Any]]:
        """Get devices for a project.

        Args:
            project_id: Project ID

        Returns:
            List of devices

        Raises:
            SyrConnectSessionExpiredError: If session expired
        """
        if not self.is_session_valid():
            _LOGGER.warning("Session expired, re-authenticating...")
            await self.login()

        _LOGGER.debug("Getting devices for project: %s", project_id)

        # Build payload
        payload = self.payload_builder.build_device_list_payload(self.session_data, project_id)
        _LOGGER.debug("Payload prepared: %s", payload)

        try:
            # Make request
            xml_response = await self.http_client.post(
                _SYR_CONNECT_API_XML_DEVICE_LIST_URL,
                {'xml': payload}
            )
            _LOGGER.debug("Device list XML response: %s", xml_response)

            # Parse response
            devices = self.response_parser.parse_device_list_response(xml_response)

            # Add project_id to each device
            for device in devices:
                device['project_id'] = project_id
                # Ensure 'id' field exists (should be set by parser as serial_number)
                if 'id' not in device and 'serial_number' in device:
                    device['id'] = device['serial_number']
                _LOGGER.debug(
                    "Device found: %s (ID: %s, DCLG: %s)",
                    device['name'], device.get('id'), device.get('dclg')
                )

            _LOGGER.debug("Found %d device(s) in project %s", len(devices), project_id)
            return devices

        except Exception as err:
            _LOGGER.error("Failed to get devices: %s", err)
            raise

    async def get_device_status(self, device_id: str) -> dict[str, Any] | None:
        """Get status of a device.

        Args:
            device_id: Device ID (DCLG)

        Returns:
            Dictionary with device status

        Raises:
            SyrConnectSessionExpiredError: If session expired
        """
        if not self.is_session_valid():
            _LOGGER.warning("Session expired, re-authenticating...")
            await self.login()

        _LOGGER.debug("Getting status for device: %s", device_id)

        # Build payload
        payload = self.payload_builder.build_device_status_payload(self.session_data, device_id)
        _LOGGER.debug("Status request payload: %s", payload)

        try:
            # Make request
            xml_response = await self.http_client.post(
                _SYR_CONNECT_API_XML_DEVICE_GET_STATUS_URL,
                {'xml': payload}
            )
            _LOGGER.debug("Status XML response: %s", xml_response)

            # Parse response. The parser may return None to signal that the
            # response did not contain the detailed structure we expect. In
            # that case, propagate None to the caller so the coordinator can
            # preserve previous state instead of raising an exception here.
            status_data = self.response_parser.parse_device_status_response(xml_response)
            if status_data is None:
                _LOGGER.debug("Status parser returned None for device %s", device_id)
                return None

            _LOGGER.debug("Status data parsed: %d attributes", len(status_data))
            return status_data

        except Exception as err:
            _LOGGER.error("Failed to get device status: %s", err)
            raise

    async def set_device_status(self, device_id: str, command: str, value: Any) -> bool:
        """Set device status/command.

        Args:
            device_id: Device ID (DCLG)
            command: Command name
            value: Command value

        Returns:
            True if successful

        Raises:
            SyrConnectSessionExpiredError: If session expired
        """
        if not self.is_session_valid():
            _LOGGER.warning("Session expired, re-authenticating...")
            await self.login()

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
                _SYR_CONNECT_API_XML_DEVICE_SET_STATUS_URL,
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
                _SYR_CONNECT_API_XML_DEVICE_GET_STATISTICS_URL,
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
