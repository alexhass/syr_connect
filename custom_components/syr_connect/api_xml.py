"""SYR Connect XML API client for cloud-based device management.

This module implements the client for the SYR Connect cloud API, which uses
XML-based SOAP-like communication with encryption and checksums.

Cloud API workflow:
1. Login with username/password -> returns encrypted session + project list
2. Get device list for a project -> returns devices with DCLG IDs
3. Get/Set device status using DCLG ID -> returns/updates device parameters
4. Get statistics (water/salt consumption) -> returns historical data

Security features:
- Request checksums with a proprietary two-key algorithm (required by the webservice; not an HMAC)
- Response encryption using AES (protects sensitive data)
- Session-based authentication; a token rejected by the webservice triggers one new login (no client-side expiry)

The API client coordinates several helper components:
- SyrEncryption: AES encryption/decryption
- SyrChecksum: Request checksums
- PayloadBuilder: XML request construction
- ResponseParser: XML response parsing
- HTTPClient: HTTP POST with custom headers
"""

import asyncio
from collections.abc import Callable
import logging
from typing import Any

import aiohttp

from .checksum import SyrChecksum
from .const import (
    _SYR_CONNECT_API_XML_BASE_URL,
    _SYR_CONNECT_API_XML_DEVICE_GET_LIST_URL,
    _SYR_CONNECT_API_XML_DEVICE_GET_STATUS_URL,
    _SYR_CONNECT_API_XML_DEVICE_SERVICE_PATH,
    _SYR_CONNECT_API_XML_DEVICE_SET_STATUS_URL,
    _SYR_CONNECT_API_XML_LOGIN_URL,
    _SYR_CONNECT_CLIENT_APP_NAME,
    _SYR_CONNECT_CLIENT_CF_BUNDLE_IDENTIFIER,
    _SYR_CONNECT_CLIENT_CF_BUNDLE_VERSION,
    _SYR_CONNECT_CLIENT_CHECKSUM_KEY1,
    _SYR_CONNECT_CLIENT_CHECKSUM_KEY2,
    _SYR_CONNECT_CLIENT_ENCRYPTION_IV,
    _SYR_CONNECT_CLIENT_ENCRYPTION_KEY,
    _SYR_CONNECT_CLIENT_OS_LANGUAGE,
    _SYR_CONNECT_CLIENT_OS_MODEL,
    _SYR_CONNECT_CLIENT_OS_NAME,
    _SYR_CONNECT_CLIENT_OS_VERSION,
    _SYR_CONNECT_CLIENT_USER_AGENT,
)
from .data import SyrConnectDevice
from .devices import SyrConnectStatistic
from .encryption import SyrEncryption
from .exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectSessionExpiredError,
)
from .helpers import mask_login_password, mask_ug_value
from .http_client import HTTPClient
from .payload_builder import PayloadBuilder
from .response_parser import ResponseParser

_LOGGER = logging.getLogger(__name__)


class SyrConnectXmlAPI:
    """API client for the SYR Connect cloud service.

    This client handles authentication, session management, and all device
    operations through the cloud API. It automatically re-authenticates
    when sessions expire and coordinates multiple helper components for
    encryption, checksums, and XML processing.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        *,
        api_app_name: str | None = None,
        api_base_url: str | None = None,
        cf_bundle_identifier: str | None = None,
        language: str = _SYR_CONNECT_CLIENT_OS_LANGUAGE,
    ) -> None:
        """Initialize the cloud API client.

        Args:
            session: aiohttp ClientSession provided by Home Assistant
            username: SYR Connect cloud account email address
            password: SYR Connect cloud account password
            api_app_name: Application name sent in the login payload "<nfo v=...>" (from _SYR_CONNECT_API_SERVICES).
                Defaults to _SYR_CONNECT_CLIENT_APP_NAME ("SYR Connect").
            api_base_url: Cloud API base URL override (from _SYR_CONNECT_API_SERVICES), must end with "/".
                Defaults to _SYR_CONNECT_API_XML_BASE_URL ("https://syrconnect.de/").
            cf_bundle_identifier: iOS bundle identifier override (from _SYR_CONNECT_API_SERVICES).
                Defaults to _SYR_CONNECT_CLIENT_CF_BUNDLE_IDENTIFIER ("de.consoft.syr.connect").
            language: Locale like "de-DE" (from helpers.get_api_locale) sent in the app version string
                "<si v=...>", as lng/reg at login, lg/rg in statistics requests and in the
                Accept-Language header. Defaults to _SYR_CONNECT_CLIENT_OS_LANGUAGE ("en-US").
        """
        # --- Authentication credentials ---
        self.username = username
        self.password = password

        # --- Session management ---
        # Session data is a token string returned by login, used for all subsequent requests
        self.session_data: str = ""
        # Serializes (re-)logins from parallel requests (see _ensure_session/_relogin)
        self._login_lock = asyncio.Lock()

        # --- Project structure ---
        # Cloud API organizes devices into projects (locations/buildings)
        # Each login returns a list of projects the user has access to
        self.projects: list[dict[str, Any]] = []

        # --- URL overrides (config entry-specific) ---
        _app_name = api_app_name or _SYR_CONNECT_CLIENT_APP_NAME
        _base = api_base_url or _SYR_CONNECT_API_XML_BASE_URL
        _bundle_id = cf_bundle_identifier or _SYR_CONNECT_CLIENT_CF_BUNDLE_IDENTIFIER
        self._login_url = _base + _SYR_CONNECT_API_XML_LOGIN_URL
        self._device_list_url = _base + _SYR_CONNECT_API_XML_DEVICE_GET_LIST_URL
        self._device_get_status_url = _base + _SYR_CONNECT_API_XML_DEVICE_GET_STATUS_URL
        self._device_set_status_url = _base + _SYR_CONNECT_API_XML_DEVICE_SET_STATUS_URL
        # The statistics method of the device family is appended (get_statistics)
        self._device_service_url = _base + _SYR_CONNECT_API_XML_DEVICE_SERVICE_PATH

        # Example: "App-3.9.7-de-DE-iOS-iPhone-27.0.0-de.consoft.syr.connect"
        # The app sends the phone's language here; use the HA locale.
        _app_version = (
            f"App-{_SYR_CONNECT_CLIENT_CF_BUNDLE_VERSION}"
            f"-{language}"
            f"-{_SYR_CONNECT_CLIENT_OS_NAME}"
            f"-{_SYR_CONNECT_CLIENT_OS_MODEL}"
            f"-{_SYR_CONNECT_CLIENT_OS_VERSION}"
            f"-{_bundle_id}"
        )

        # --- Helper components ---
        # These handle the low-level details of the SYR protocol

        # AES encryption for login response decryption
        self.encryption = SyrEncryption(
            _SYR_CONNECT_CLIENT_ENCRYPTION_KEY, _SYR_CONNECT_CLIENT_ENCRYPTION_IV
        )

        # Request checksum required by the webservice (proprietary, two keys; not an HMAC)
        self.checksum = SyrChecksum(
            _SYR_CONNECT_CLIENT_CHECKSUM_KEY1, _SYR_CONNECT_CLIENT_CHECKSUM_KEY2
        )

        # XML payload construction with embedded checksums
        self.payload_builder = PayloadBuilder(
            _app_version, self.checksum, _app_name, language
        )

        # XML response parsing (handles various response formats)
        self.response_parser = ResponseParser()

        # HTTP client with SYR-specific User-Agent
        self.http_client = HTTPClient(
            session, _SYR_CONNECT_CLIENT_USER_AGENT, language=language
        )

    @property
    def device_get_status_url(self) -> str:
        """Return the URL of the device status request."""
        return self._device_get_status_url

    @property
    def device_list_url(self) -> str:
        """Return the URL of the device list request."""
        return self._device_list_url

    def is_session_valid(self) -> bool:
        """Return True if a session token from a previous login is available.

        There is no client-side expiry: the real session lifetime of the webservice is
        unknown. A rejected token is detected in the response instead (see
        _post_with_session), which then triggers a new login.
        """
        return bool(self.session_data)

    async def _ensure_session(self) -> None:
        """Log in if there is no session token yet (first request)."""
        if self.is_session_valid():
            return
        # Requests run in parallel (projects, devices): only the first one logs in
        async with self._login_lock:
            if self.is_session_valid():
                return
            await self.login()

    async def _relogin(self, rejected_token: str) -> None:
        """Log in again after the webservice rejected `rejected_token`.

        Parallel requests usually get the rejection at the same time; only the first one
        logs in, the others find a new token already and reuse it.
        """
        async with self._login_lock:
            if self.session_data and self.session_data != rejected_token:
                return
            await self.login()

    async def _post_with_session(
        self, url: str, build_payload: Callable[[str], str], name: str
    ) -> str:
        """Post a request built with the current session token; re-login once if it is rejected.

        The webservice answers a rejected (invalid or expired) token with HTTP 200 and
        `<sc><msg mtid="1" .../></sc>` (docs/known_issues_xml_api.md, issue 4). The request is
        then sent once more with a new token; a second rejection is raised as
        SyrConnectSessionExpiredError, a SyrConnectConnectionError.

        Args:
            url: Endpoint URL
            build_payload: Builds the XML payload for a given session token
            name: Request name for log messages

        Returns:
            The raw XML response
        """
        token = self.session_data
        payload = build_payload(token)
        _LOGGER.debug("%s payload: %s", name, mask_ug_value(payload))
        xml_response = await self.http_client.post(url, {"xml": payload})
        try:
            self.response_parser.raise_if_session_expired(xml_response)
        except SyrConnectSessionExpiredError as err:
            _LOGGER.info("%s: %s; logging in again", name, err)
            await self._relogin(token)
            payload = build_payload(self.session_data)
            _LOGGER.debug(
                "%s payload (after re-login): %s", name, mask_ug_value(payload)
            )
            xml_response = await self.http_client.post(url, {"xml": payload})
            self.response_parser.raise_if_session_expired(xml_response)
        return xml_response

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
        xml_data = self.payload_builder.build_login_payload(
            self.username, self.password
        )
        _LOGGER.debug("Login payload prepared: %s", mask_login_password(xml_data))

        try:
            # --- Make HTTP Request ---
            # Login uses direct XML POST (not form-encoded like other endpoints)
            xml_response = await self.http_client.post(
                self._login_url, xml_data, content_type="text/xml"
            )
            _LOGGER.debug("Login XML response received")

            # --- Parse and Decrypt Response ---
            # Response contains encrypted session data to protect credentials in transit
            encrypted_text, _ = self.response_parser.parse_login_response(xml_response)
            decrypted = self.encryption.decrypt(encrypted_text)
            _LOGGER.info("Login response decrypted successfully")

            # --- Extract Session and Projects ---
            # Decrypted data contains session token and list of accessible projects
            self.session_data, self.projects = (
                self.response_parser.parse_decrypted_login(decrypted)
            )

            _LOGGER.info("Login successful, found %d project(s)", len(self.projects))

            # Log available projects for debugging
            for project in self.projects:
                _LOGGER.debug("Project: %s (ID: %s)", project["name"], project["id"])

        # --- Error Handling ---
        except SyrConnectAuthError as err:
            # The server rejected the credentials (see parse_decrypted_login): re-authentication needed
            _LOGGER.error("Authentication failed: %s", err)
            raise
        except ValueError as err:
            # Malformed or unexpected answer (e.g. a maintenance page instead of XML). The
            # credentials are not known to be wrong, so this must not trigger a re-authentication.
            _LOGGER.error("Invalid login response: %s", err)
            raise SyrConnectConnectionError(f"Invalid login response: {err}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            # Network errors (DNS, connection timeout, etc.)
            error_representation = repr(err)
            _LOGGER.error("Connection failed: %s", error_representation)
            raise SyrConnectConnectionError(
                f"Connection failed: {error_representation}"
            ) from err
        except Exception as err:
            # Catch-all for unexpected errors (encryption failures, etc.)
            error_representation = repr(err)
            _LOGGER.error(
                "Login failed with unexpected error: %s", error_representation
            )
            raise SyrConnectConnectionError(
                f"Login failed: {error_representation}"
            ) from err
        else:
            return True

    async def get_devices(self, project_id: str) -> list[SyrConnectDevice]:
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
        await self._ensure_session()

        _LOGGER.debug("Getting devices for project: %s", project_id)

        try:
            # --- Make HTTP Request ---
            # Device list endpoint uses form-encoded XML
            xml_response = await self._post_with_session(
                self._device_list_url,
                lambda token: self.payload_builder.build_device_get_list_payload(
                    token, project_id
                ),
                "Device list",
            )
            _LOGGER.debug("Device list XML response: %s", xml_response)

            # --- Parse Response ---
            # Extract device metadata from XML structure
            devices = self.response_parser.parse_device_list_response(xml_response)

            # --- Enrich Device Data ---
            # Add project context
            for device in devices:
                # Associate device with its parent project
                device["project_id"] = project_id

                _LOGGER.debug(
                    "Device found: %s (ID: %s, DCLG: %s)",
                    device["name"],
                    device.get("id"),
                    device.get("dclg"),
                )

            _LOGGER.debug("Found %d device(s) in project %s", len(devices), project_id)

        except (aiohttp.ClientError, TimeoutError) as err:
            raise SyrConnectConnectionError(f"Failed to get devices: {err}") from err
        else:
            return devices

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
        await self._ensure_session()

        _LOGGER.debug("Getting status for device: %s", device_id)

        try:
            # --- Make HTTP Request ---
            xml_response = await self._post_with_session(
                self._device_get_status_url,
                lambda token: self.payload_builder.build_device_get_status_payload(
                    token, device_id
                ),
                "Status request",
            )
            _LOGGER.debug("Status XML response: %s", xml_response)

            # --- Parse Response ---
            # Parser returns None if response doesn't have expected structure
            # This is intentional: allows coordinator to keep previous state
            # rather than failing completely on malformed responses
            status_data = self.response_parser.parse_device_status_response(
                xml_response
            )
            if status_data is None:
                _LOGGER.debug("Status parser returned None for device %s", device_id)
                return None

            _LOGGER.debug("Status data parsed: %d attributes", len(status_data))

        except (aiohttp.ClientError, TimeoutError) as err:
            # Network errors after all retries: wrap them like login()/get_devices() so callers
            # only need to handle SyrConnectError
            _LOGGER.error("Failed to get device status: %s", err)
            raise SyrConnectConnectionError(
                f"Failed to get device status: {err}"
            ) from err
        except Exception as err:
            _LOGGER.error("Failed to get device status: %s", err)
            raise
        else:
            return status_data

    async def set_device_status(
        self,
        device_id: str,
        commands: list[tuple[str, Any]],
    ) -> bool:
        """Set one or more device parameters in a single XML request.

        Args:
            device_id: Device collection group ID (DCLG)
            commands: Sequence of ``(command, value)`` pairs, executed in order.
                Use a single-element list for single commands.

        Returns:
            True if the request was accepted (does not guarantee completion)

        Raises:
            SyrConnectAuthError: If session expired and re-login fails
            SyrConnectConnectionError: If network/HTTP errors occur
        """
        await self._ensure_session()

        _LOGGER.debug(
            "Setting device %s with %d command(s): %s",
            device_id,
            len(commands),
            commands,
        )

        # Normalize boolean values to 0/1
        normalized: list[tuple[str, Any]] = [
            (cmd, (1 if val is True else (0 if val is False else val)))
            for cmd, val in commands
        ]

        try:
            xml_response = await self._post_with_session(
                self._device_set_status_url,
                lambda token: self.payload_builder.build_device_set_status_payload(
                    token, device_id, normalized
                ),
                "Set status",
            )
            _LOGGER.debug("Set status XML response: %s", xml_response)
            _LOGGER.info(
                "Successfully executed %d command(s) for device %s",
                len(commands),
                device_id,
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            # Network errors after all retries: wrapped so the entity turns them into a
            # HomeAssistantError for the user instead of an unhandled exception
            _LOGGER.error("Failed to set device status for %s: %s", device_id, err)
            raise SyrConnectConnectionError(
                f"Failed to set device status: {err}"
            ) from err
        except Exception as err:
            _LOGGER.error("Failed to set device status for %s: %s", device_id, err)
            raise
        else:
            return True

    async def get_statistics(
        self, device_id: str, statistic: SyrConnectStatistic
    ) -> dict[str, Any]:
        """Fetch the measurement history of one series of a device.

        The cloud keeps measurements a device does not report in its status, for
        example the measurements of a SafeFloor sensor between two uploads. The device
        profile lists the series of a family (``SyrConnectDeviceProfile.statistics``).

        Args:
            device_id: Device collection group ID (DCLG)
            statistic: Series to fetch (web service method and request attributes)

        Returns:
            Flattened attributes of the response

        Raises:
            SyrConnectAuthError: If session expired and re-login fails
            SyrConnectConnectionError: If network/HTTP errors occur
        """
        # --- Ensure Valid Session ---
        await self._ensure_session()

        _LOGGER.debug(
            "Getting %s statistics (%s) for device: %s",
            statistic.key,
            statistic.method,
            device_id,
        )

        try:
            # --- Make HTTP Request ---
            xml_response = await self._post_with_session(
                self._device_service_url + statistic.method,
                lambda token: self.payload_builder.build_device_get_statistics_payload(
                    token, device_id, statistic
                ),
                "Statistics",
            )
            _LOGGER.debug("Statistics XML response: %s", xml_response)

            # --- Parse Response ---
            stats_data = self.response_parser.parse_statistics_response(xml_response)
            _LOGGER.debug("Statistics data parsed: %d attributes", len(stats_data))

        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Failed to get %s statistics: %s", statistic.key, err)
            raise SyrConnectConnectionError(
                f"Failed to get {statistic.key} statistics: {err}"
            ) from err
        except Exception as err:
            _LOGGER.error("Failed to get %s statistics: %s", statistic.key, err)
            raise
        else:
            return stats_data
