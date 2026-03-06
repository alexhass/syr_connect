"""SYR Connect XML API client for cloud-based device management.

This module implements the client for the SYR Connect cloud API, which uses
XML-based SOAP-like communication with encryption and checksums.

Cloud API workflow:
1. Login with username/password -> returns encrypted session + project list
2. Get device list for a project -> returns devices with DCLG IDs
3. Get/Set device status using DCLG ID -> returns/updates device parameters
4. Get statistics (water/salt consumption) -> returns historical data

Security features:
- Request checksums using dual-key HMAC (prevents tampering)
- Response encryption using AES (protects sensitive data)
- Session-based authentication with 30-minute timeout

The API client coordinates several helper components:
- SyrEncryption: AES encryption/decryption
- SyrChecksum: Dual-key HMAC checksums
- PayloadBuilder: XML request construction
- ResponseParser: XML response parsing
- HTTPClient: HTTP POST with custom headers
"""
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


class SyrConnectXmlAPI:
    """API client for the SYR Connect cloud service.

    This client handles authentication, session management, and all device
    operations through the cloud API. It automatically re-authenticates
    when sessions expire and coordinates multiple helper components for
    encryption, checksums, and XML processing.
    """

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        """Initialize the cloud API client.

        Args:
            session: aiohttp ClientSession provided by Home Assistant
            username: SYR Connect cloud account email address
            password: SYR Connect cloud account password
        """
        # --- Authentication credentials ---
        self.username = username
        self.password = password

        # --- Session management ---
        # Session data is a token string returned by login, used for all subsequent requests
        self.session_data: str = ""
        # Sessions expire after 30 minutes of inactivity
        self.session_expires_at: datetime | None = None

        # --- Project structure ---
        # Cloud API organizes devices into projects (locations/buildings)
        # Each login returns a list of projects the user has access to
        self.projects: list[dict[str, Any]] = []

        # --- Helper components ---
        # These handle the low-level details of the SYR protocol

        # AES encryption for login response decryption
        self.encryption = SyrEncryption(_SYR_CONNECT_CLIENT_ENCRYPTION_KEY, _SYR_CONNECT_CLIENT_ENCRYPTION_IV)

        # Dual-key HMAC checksums to prevent request tampering
        self.checksum = SyrChecksum(_SYR_CONNECT_CLIENT_CHECKSUM_KEY1, _SYR_CONNECT_CLIENT_CHECKSUM_KEY2)

        # XML payload construction with embedded checksums
        self.payload_builder = PayloadBuilder(_SYR_CONNECT_CLIENT_APP_VERSION, self.checksum)

        # XML response parsing (handles various response formats)
        self.response_parser = ResponseParser()

        # HTTP client with SYR-specific User-Agent
        self.http_client = HTTPClient(session, _SYR_CONNECT_CLIENT_USER_AGENT)

    def is_session_valid(self) -> bool:
        """Check if the current session is still valid.

        Sessions are valid if:
        1. We have a session token (self.session_data is not empty)
        2. We have an expiry time set (self.session_expires_at is not None)
        3. The current time is before the expiry time (not timed out)

        Returns:
            True if session is valid and can be used for API calls, False otherwise
        """
        # Check if we have a session token at all
        if not self.session_data:
            return False

        # Check if we have an expiry time (should always be set with session_data)
        if self.session_expires_at is None:
            return False

        # Check if session hasn't timed out yet
        return datetime.now() < self.session_expires_at

    def _update_session_expiry(self) -> None:
        """Update session expiration time.

        Called after successful login to set the session timeout.
        Sessions expire after 30 minutes of inactivity, matching the
        server-side timeout to avoid unnecessary re-authentication attempts.
        """
        self.session_expires_at = datetime.now() + timedelta(minutes=_SESSION_TIMEOUT_MINUTES)

    async def login(self) -> bool:
        """Authenticate with the SYR Connect cloud service.

        Login workflow:
        1. Build XML payload with username/password and checksum
        2. POST to login endpoint
        3. Parse response to extract encrypted session data
        4. Decrypt session data using AES to get session token + project list
        5. Store session token and update expiry time

        The login response contains:
        - Session token: Used for all subsequent API calls
        - Project list: Buildings/locations the user has access to

        Returns:
            True if login successful

        Raises:
            SyrConnectAuthError: If credentials are invalid or authentication fails
            SyrConnectConnectionError: If network/HTTP errors occur
        """
        _LOGGER.debug("Attempting login for user: %s", self.username)

        # --- Build Login Request ---
        # Payload includes username, password, and checksum for integrity
        xml_data = self.payload_builder.build_login_payload(self.username, self.password)
        _LOGGER.debug("Login payload prepared")

        try:
            # --- Make HTTP Request ---
            # Login uses direct XML POST (not form-encoded like other endpoints)
            xml_response = await self.http_client.post(
                _SYR_CONNECT_API_XML_LOGIN_URL,
                xml_data,
                content_type='text/xml'
            )
            _LOGGER.debug("Login XML response received")

            # --- Parse and Decrypt Response ---
            # Response contains encrypted session data to protect credentials in transit
            encrypted_text, _ = self.response_parser.parse_login_response(xml_response)
            decrypted = self.encryption.decrypt(encrypted_text)
            _LOGGER.info("Login response decrypted successfully")

            # --- Extract Session and Projects ---
            # Decrypted data contains session token and list of accessible projects
            self.session_data, self.projects = self.response_parser.parse_decrypted_login(decrypted)

            # --- Update Session Tracking ---
            # Set expiry time to 30 minutes from now
            self._update_session_expiry()
            _LOGGER.info("Login successful, found %d project(s)", len(self.projects))

            # Log available projects for debugging
            for project in self.projects:
                _LOGGER.debug("Project: %s (ID: %s)", project['name'], project['id'])

            return True

        # --- Error Handling ---
        except ValueError as err:
            # Parser errors usually mean invalid credentials or malformed response
            _LOGGER.error("Authentication failed: %s", err)
            raise SyrConnectAuthError(f"Authentication failed: {err}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            # Network errors (DNS, connection timeout, etc.)
            error_representation = repr(err)
            _LOGGER.error("Connection failed: %s", error_representation)
            raise SyrConnectConnectionError(f"Connection failed: {error_representation}") from err
        except Exception as err:
            # Catch-all for unexpected errors (encryption failures, etc.)
            error_representation = repr(err)
            _LOGGER.error("Login failed with unexpected error: %s", error_representation)
            raise SyrConnectConnectionError(f"Login failed: {error_representation}") from err

    async def get_devices(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch all devices in a project.

        Each project (building/location) can contain multiple devices.
        This method returns the device list with metadata needed for
        subsequent status queries.

        Device information includes:
        - id: Unique device identifier (serial number)
        - name: User-assigned device name
        - dclg: Device collection group ID (used for status queries)
        - serial_number: Factory serial number
        - project_id: Parent project ID (added by this method)

        Args:
            project_id: Project ID to query (obtained from login response)

        Returns:
            List of device dictionaries with metadata

        Raises:
            SyrConnectAuthError: If session expired and re-login fails
            SyrConnectConnectionError: If network/HTTP errors occur
        """
        # --- Ensure Valid Session ---
        # Check if session is still valid, re-authenticate if needed
        if not self.is_session_valid():
            _LOGGER.warning("Session expired, re-authenticating...")
            await self.login()

        _LOGGER.debug("Getting devices for project: %s", project_id)

        # --- Build Request Payload ---
        # Payload includes session token and project ID
        payload = self.payload_builder.build_device_list_payload(self.session_data, project_id)
        _LOGGER.debug("Payload prepared: %s", payload)

        try:
            # --- Make HTTP Request ---
            # Device list endpoint uses form-encoded XML
            xml_response = await self.http_client.post(
                _SYR_CONNECT_API_XML_DEVICE_LIST_URL,
                {'xml': payload}
            )
            _LOGGER.debug("Device list XML response: %s", xml_response)

            # --- Parse Response ---
            # Extract device metadata from XML structure
            devices = self.response_parser.parse_device_list_response(xml_response)

            # --- Enrich Device Data ---
            # Add project context and normalize ID fields
            for device in devices:
                # Associate device with its parent project
                device['project_id'] = project_id

                # Ensure 'id' field exists (parser may use 'serial_number')
                # This normalizes the interface for the coordinator
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
        """Fetch current status and parameters of a device.

        Device status includes all readable parameters:
        - Current readings (flow, pressure, temperature, etc.)
        - Configuration values (regeneration times, alarm thresholds, etc.)
        - State information (valve positions, alarm flags, etc.)

        The response format varies by device model:
        - LEXplus: Has detailed status with many parameters
        - SafeTech: Has basic flow/pressure/alarm data
        - NeoSoft: Has softener-specific regeneration data

        Args:
            device_id: Device collection group ID (DCLG) from get_devices()

        Returns:
            Dictionary mapping parameter names (e.g., 'getFLO', 'getPRS') to values,
            or None if the response format is unexpected (allows coordinator to
            preserve previous state instead of failing)

        Raises:
            SyrConnectAuthError: If session expired and re-login fails
            SyrConnectConnectionError: If network/HTTP errors occur
        """
        # --- Ensure Valid Session ---
        if not self.is_session_valid():
            _LOGGER.warning("Session expired, re-authenticating...")
            await self.login()

        _LOGGER.debug("Getting status for device: %s", device_id)

        # --- Build Request Payload ---
        # Payload includes session token and device DCLG ID
        payload = self.payload_builder.build_device_status_payload(self.session_data, device_id)
        _LOGGER.debug("Status request payload: %s", payload)

        try:
            # --- Make HTTP Request ---
            xml_response = await self.http_client.post(
                _SYR_CONNECT_API_XML_DEVICE_GET_STATUS_URL,
                {'xml': payload}
            )
            _LOGGER.debug("Status XML response: %s", xml_response)

            # --- Parse Response ---
            # Parser returns None if response doesn't have expected structure
            # This is intentional: allows coordinator to keep previous state
            # rather than failing completely on malformed responses
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
        """Set a device parameter or execute a command.

        This method can:
        - Change configuration values (regeneration times, thresholds, etc.)
        - Execute commands (manual regeneration, alarm reset, etc.)
        - Control outputs (valve positions, etc.)

        Common commands:
        - setRTM: Set regeneration time (format: "HH:MM")
        - setAB: Trigger manual regeneration (value: 2)
        - setVLV: Set valve position (value: 0-100)

        Args:
            device_id: Device collection group ID (DCLG)
            command: Command name (e.g., 'setRTM', 'setAB', 'setVLV')
            value: Command value (type depends on command - int, str, bool)

        Returns:
            True if the command was accepted (does not guarantee completion)

        Raises:
            SyrConnectAuthError: If session expired and re-login fails
            SyrConnectConnectionError: If network/HTTP errors occur
        """
        # --- Ensure Valid Session ---
        if not self.is_session_valid():
            _LOGGER.warning("Session expired, re-authenticating...")
            await self.login()

        _LOGGER.debug("Setting device %s command %s to %s", device_id, command, value)

        # --- Normalize Boolean Values ---
        # API expects integers (0/1) for boolean commands, not true/false
        if isinstance(value, bool):
            original_value = value
            value = 1 if value else 0
            _LOGGER.debug("Converted boolean %s to int %s", original_value, value)

        # --- Build Request Payload ---
        payload = self.payload_builder.build_set_status_payload(
            self.session_data, device_id, command, value
        )
        _LOGGER.debug("Set status payload: %s", payload)

        try:
            # --- Make HTTP Request ---
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
        """Fetch historical consumption statistics for a device.

        This endpoint is primarily used by LEXplus devices that track:
        - Water consumption (daily/weekly/monthly totals)
        - Salt consumption (regeneration counts, salt usage)

        Statistics are useful for:
        - Monitoring usage patterns
        - Detecting leaks (abnormal consumption)
        - Planning maintenance (salt refills)
        - Energy/cost analysis

        Note: Not all device models support statistics. SafeTech and older
        NeoSoft models may not provide this data.

        Args:
            device_id: Device collection group ID (DCLG)
            statistic_type: Type of statistic to fetch:
                - "water": Water consumption in liters/gallons
                - "salt": Salt consumption in kg and regeneration counts

        Returns:
            Dictionary with time-series data (format varies by statistic_type)

        Raises:
            SyrConnectAuthError: If session expired and re-login fails
            SyrConnectConnectionError: If network/HTTP errors occur
        """
        _LOGGER.debug("Getting %s statistics for device: %s", statistic_type, device_id)

        # --- Build Request Payload ---
        payload = self.payload_builder.build_statistics_payload(
            self.session_data, device_id, statistic_type
        )
        _LOGGER.debug("Statistics payload: %s", payload)

        try:
            # --- Make HTTP Request ---
            xml_response = await self.http_client.post(
                _SYR_CONNECT_API_XML_DEVICE_GET_STATISTICS_URL,
                {'xml': payload}
            )
            _LOGGER.debug("Statistics XML response: %s", xml_response)

            # --- Parse Response ---
            # Statistics format depends on device model and statistic type
            stats_data = self.response_parser.parse_statistics_response(xml_response)
            _LOGGER.debug("Statistics data parsed: %d attributes", len(stats_data))
            return stats_data

        except Exception as err:
            _LOGGER.error("Failed to get %s statistics: %s", statistic_type, err)
            raise
