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
from datetime import datetime
import logging
from typing import Any

import aiohttp

from .const import (
    CLIENT_CF_BUNDLE_VERSION,
    CLIENT_OS_LANGUAGE,
    CLIENT_OS_MODEL,
    CLIENT_OS_NAME,
    CLIENT_OS_VERSION,
    XML_CHECKSUM_KEY1,
    XML_CHECKSUM_KEY2,
    XML_DEVICE_GET_LIST_URL,
    XML_DEVICE_GET_STATUS_URL,
    XML_DEVICE_SERVICE_PATH,
    XML_DEVICE_SET_STATUS_URL,
    XML_LOGIN_URL,
)
from .exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectInvalidResponseError,
    SyrConnectLoginFailedError,
    SyrConnectSessionExpiredError,
)
from .http_client import HTTPClient, mask_ug_value
from .models import (
    SyrConnectApiDevice,
    SyrConnectService,
    SyrConnectStatistic,
    SyrConnectStatus,
)
from .xml_checksum import SyrChecksum
from .xml_encryption import SyrEncryption
from .xml_parser import ResponseParser
from .xml_payload import PayloadBuilder

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
        service: SyrConnectService,
        user_agent: str | None = None,
        language: str = CLIENT_OS_LANGUAGE,
        local_now: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize the cloud API client.

        Args:
            session: aiohttp ClientSession of the caller
            username: SYR Connect cloud account email address
            password: SYR Connect cloud account password
            service: Cloud API service of the account (from API_SERVICES):
                app name, base URL, bundle identifier and the key of the login response
            user_agent: HTTP User-Agent of the requests; names the caller
            language: Locale like "de-DE" sent in the app version string
                "<si v=...>", as lng/reg at login, lg/rg in statistics requests and in the
                Accept-Language header. Defaults to CLIENT_OS_LANGUAGE ("en-US").
            local_now: Returns the current time in the time zone of the caller, for the
                UTC offset (tzo) of the login; default the local time of the process

        Raises:
            ValueError: If user_agent is missing, empty or no valid User-Agent (RFC 9110)
        """
        # --- Authentication credentials ---
        self.username = username
        self.password = password

        # --- Session management ---
        # Session data is a token string returned by login, used for all subsequent requests
        self.session_data: str = ""
        # Serializes (re-)logins from parallel requests (see _ensure_session/_relogin)
        self._login_lock = asyncio.Lock()
        # Number of logins finished by _login_shared and the error of the last one, so
        # requests waiting for that login share its failure instead of repeating it
        self._logins_finished = 0
        self._login_error: Exception | None = None

        # --- Project structure ---
        # Cloud API organizes devices into projects (locations/buildings)
        # Each login returns a list of projects the user has access to
        self.projects: list[dict[str, Any]] = []

        # --- Service endpoints (of the service of the account) ---
        _app_name = service.api_app_name
        _base = service.api_base_url
        _bundle_id = service.cf_bundle_identifier
        self._login_url = _base + XML_LOGIN_URL
        self._device_list_url = _base + XML_DEVICE_GET_LIST_URL
        self._device_get_status_url = _base + XML_DEVICE_GET_STATUS_URL
        self._device_set_status_url = _base + XML_DEVICE_SET_STATUS_URL
        # The statistics method of the device family is appended (get_statistics)
        self._device_service_url = _base + XML_DEVICE_SERVICE_PATH

        # Example: "App-3.9.7-de-DE-iOS-iPhone-27.0.0-de.consoft.syr.connect"
        # The app sends the phone's language here; use the locale of the caller.
        _app_version = (
            f"App-{CLIENT_CF_BUNDLE_VERSION}"
            f"-{language}"
            f"-{CLIENT_OS_NAME}"
            f"-{CLIENT_OS_MODEL}"
            f"-{CLIENT_OS_VERSION}"
            f"-{_bundle_id}"
        )

        # --- Helper components ---
        # These handle the low-level details of the SYR protocol

        # AES encryption for login response decryption
        self.encryption = SyrEncryption(service.crypt_key, service.crypt_vector)

        # Request checksum required by the webservice (proprietary, two keys; not an HMAC)
        self.checksum = SyrChecksum(XML_CHECKSUM_KEY1, XML_CHECKSUM_KEY2)

        # XML payload construction with embedded checksums
        self.payload_builder = PayloadBuilder(
            _app_version, self.checksum, _app_name, language, local_now
        )

        # XML response parsing (handles various response formats)
        self.response_parser = ResponseParser()

        # HTTP client; the User-Agent identifies the caller
        self.http_client = HTTPClient(session, user_agent, language=language)

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
        attempt = self._logins_finished
        # Requests run in parallel (projects, devices): only the first one logs in
        async with self._login_lock:
            if self.is_session_valid():
                return
            await self._login_shared(attempt)

    async def _relogin(self, rejected_token: str) -> None:
        """Log in again after the webservice rejected `rejected_token`.

        Parallel requests usually get the rejection at the same time; only the first one
        logs in, the others find a new token already and reuse it.
        """
        attempt = self._logins_finished
        async with self._login_lock:
            if self.session_data and self.session_data != rejected_token:
                return
            await self._login_shared(attempt)

    async def _login_shared(self, attempt: int) -> None:
        """Log in, unless a login has failed while the request waited for the lock.

        Must be called with the login lock held. A request that waited for the lock while
        another one logged in gets the error of that login: during a cloud outage the
        webservice rejects every login (docs/known_issues_xml_api.md, issues 3 and 4), and
        after a password change each attempt would send the wrong password again. The next
        request tries again.

        Args:
            attempt: Value of `_logins_finished` when the request found it needs a login
        """
        if attempt != self._logins_finished and self._login_error is not None:
            raise self._login_error
        try:
            await self.login()
        except Exception as err:
            self._login_error = err
            raise
        else:
            self._login_error = None
        finally:
            self._logins_finished += 1

    async def _post_with_session[T](
        self,
        url: str,
        build_payload: Callable[[str], str],
        parse: Callable[[str], T],
        name: str,
    ) -> T:
        """Post a request built with the current session token; re-login once if it is rejected.

        The webservice answers a rejected (invalid or expired) token with HTTP 200 and
        `<sc><msg mtid="1" .../></sc>` (docs/known_issues_xml_api.md, issue 4). The parser
        raises SyrConnectSessionExpiredError for it; the request is then sent once more with
        a new token, and a second rejection is raised (a SyrConnectConnectionError).

        Args:
            url: Endpoint URL
            build_payload: Builds the XML payload for a given session token
            parse: Parses the XML response; raises SyrConnectSessionExpiredError for a
                rejected token
            name: Request name for log messages

        Returns:
            The parsed response
        """
        token = self.session_data
        payload = build_payload(token)
        _LOGGER.debug("%s payload: %s", name, mask_ug_value(payload))
        xml_response = await self.http_client.post(url, {"xml": payload})
        _LOGGER.debug("%s XML response: %s", name, xml_response)
        try:
            return parse(xml_response)
        except SyrConnectSessionExpiredError as err:
            _LOGGER.info("%s: %s; logging in again", name, err)
        await self._relogin(token)
        payload = build_payload(self.session_data)
        _LOGGER.debug("%s payload (after re-login): %s", name, mask_ug_value(payload))
        xml_response = await self.http_client.post(url, {"xml": payload})
        _LOGGER.debug("%s XML response: %s", name, xml_response)
        return parse(xml_response)

    async def login(self) -> bool:
        """Authenticate with the SYR Connect cloud service.

        Login workflow:
        1. Build the XML payload with username and password (no checksum)
        2. POST to login endpoint
        3. Parse response to extract encrypted session data
        4. Decrypt session data using AES to get session token + project list
        5. Store the session token (it has no client-side expiry)

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
        # The login is the only request without checksum
        xml_data = self.payload_builder.build_login_payload(
            self.username, self.password
        )
        _LOGGER.debug("Login payload prepared (%d bytes)", len(xml_data))

        try:
            # --- Make HTTP Request ---
            # Login uses direct XML POST (not form-encoded like other endpoints)
            xml_response = await self.http_client.post(
                self._login_url, xml_data, content_type="text/xml"
            )
            _LOGGER.debug("Login XML response received")

            # --- Parse and Decrypt Response ---
            # The session token and the projects are AES encrypted in <api>
            encrypted_text, parsed = self.response_parser.parse_login_response(
                xml_response
            )
            decrypted = self.encryption.decrypt(encrypted_text)
            _LOGGER.debug("Login response decrypted")

            # Success is reported by <suc v="true"/> only, as in the SYR app
            if not self.response_parser.is_login_successful(parsed):
                self.response_parser.raise_login_rejected(decrypted)

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
        # Errors are logged at debug level only: the caller decides what the user sees,
        # e.g. a failed update once instead of at every poll
        except SyrConnectAuthError as err:
            # The server rejected the password (see raise_login_rejected): re-authentication needed
            _LOGGER.debug("Authentication failed: %s", err)
            raise
        except SyrConnectLoginFailedError as err:
            # Unknown username or cloud failure (see raise_login_rejected): no re-authentication
            _LOGGER.debug("Login failed: %s", err)
            raise
        except ValueError as err:
            # Malformed or unexpected answer (e.g. a maintenance page instead of XML). The
            # credentials are not known to be wrong, so this must not trigger a re-authentication.
            _LOGGER.debug("Invalid login response: %s", err)
            raise SyrConnectConnectionError(f"Invalid login response: {err}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            # Network errors (DNS, connection timeout, etc.)
            error_representation = repr(err)
            _LOGGER.debug("Connection failed: %s", error_representation)
            raise SyrConnectConnectionError(
                f"Connection failed: {error_representation}"
            ) from err
        except Exception as err:
            # Catch-all for unexpected errors (encryption failures, etc.)
            error_representation = repr(err)
            _LOGGER.debug(
                "Login failed with unexpected error: %s", error_representation
            )
            raise SyrConnectConnectionError(
                f"Login failed: {error_representation}"
            ) from err
        else:
            return True

    async def get_devices(self, project_id: str) -> list[SyrConnectApiDevice]:
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
            devices = await self._post_with_session(
                self._device_list_url,
                lambda token: self.payload_builder.build_device_get_list_payload(
                    token, project_id
                ),
                self.response_parser.parse_device_list_response,
                "Device list",
            )

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
        except ValueError as err:
            # No XML or no project, e.g. a maintenance page
            raise SyrConnectInvalidResponseError(
                f"Invalid device list response: {err}"
            ) from err
        else:
            return devices

    async def get_device_status(self, device_id: str) -> SyrConnectStatus | None:
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
            or None if the response format is unexpected (allows the caller to
            keep the previous state instead of failing)

        Raises:
            SyrConnectAuthError: If session expired and re-login fails
            SyrConnectConnectionError: If network/HTTP errors occur
        """
        # --- Ensure Valid Session ---
        await self._ensure_session()

        _LOGGER.debug("Getting status for device: %s", device_id)

        try:
            # --- Make HTTP Request ---
            # Parser returns None if response doesn't have expected structure
            # This is intentional: allows the caller to keep the previous state
            # rather than failing completely on malformed responses
            status_data = await self._post_with_session(
                self._device_get_status_url,
                lambda token: self.payload_builder.build_device_get_status_payload(
                    token, device_id
                ),
                self.response_parser.parse_device_status_response,
                "Status request",
            )
            if status_data is None:
                _LOGGER.debug("Status parser returned None for device %s", device_id)
                return None

            _LOGGER.debug("Status data parsed: %d attributes", len(status_data))

        except (aiohttp.ClientError, TimeoutError) as err:
            # Network errors: wrap them like login()/get_devices() so callers
            # only need to handle SyrConnectError
            raise SyrConnectConnectionError(
                f"Failed to get device status: {err}"
            ) from err
        except ValueError as err:
            # No XML, e.g. a maintenance page
            raise SyrConnectInvalidResponseError(
                f"Invalid device status response: {err}"
            ) from err
        else:
            return status_data

    async def get_raw_device_list(self, project_id: str) -> str:
        """Return the device list of a project as the cloud sends it, for diagnostics.

        The answer is neither parsed nor checked, and a rejected session token is not
        renewed, so it shows exactly what the cloud sends. `parse_device_list` reads the
        devices from it.

        Args:
            project_id: Project ID (obtained from login response)

        Returns:
            The raw XML answer

        Raises:
            SyrConnectAuthError: If the login fails
            SyrConnectConnectionError: If network/HTTP errors occur
        """
        await self._ensure_session()
        payload = self.payload_builder.build_device_get_list_payload(
            self.session_data, project_id
        )
        return await self._post_raw(self._device_list_url, payload, "Raw device list")

    async def get_raw_device_status(self, device_id: str) -> str:
        """Return the status of a device as the cloud sends it, for diagnostics.

        The answer is neither parsed nor checked, and a rejected session token is not
        renewed, so it shows exactly what the cloud sends.

        Args:
            device_id: Device collection group ID (DCLG) from get_devices()

        Returns:
            The raw XML answer

        Raises:
            SyrConnectAuthError: If the login fails
            SyrConnectConnectionError: If network/HTTP errors occur
        """
        await self._ensure_session()
        payload = self.payload_builder.build_device_get_status_payload(
            self.session_data, device_id
        )
        return await self._post_raw(
            self._device_get_status_url, payload, "Raw status request"
        )

    def parse_device_list(self, xml_response: str) -> list[SyrConnectApiDevice]:
        """Return the devices of a raw device list answer (see get_raw_device_list).

        Args:
            xml_response: Raw XML answer of the device list

        Returns:
            The devices, without project_id

        Raises:
            SyrConnectSessionExpiredError: If the answer rejects the session token
            ValueError: If the answer is no XML or contains no project
        """
        return self.response_parser.parse_device_list_response(xml_response)

    async def _post_raw(self, url: str, payload: str, name: str) -> str:
        """Post an XML payload and return the raw answer.

        Raises:
            SyrConnectConnectionError: If network/HTTP errors occur
        """
        _LOGGER.debug("%s payload: %s", name, mask_ug_value(payload))
        try:
            return await self.http_client.post(url, {"xml": payload})
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SyrConnectConnectionError(f"{name} failed: {err}") from err

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
            # The cloud sends no confirmation; only a rejected token is detected
            await self._post_with_session(
                self._device_set_status_url,
                lambda token: self.payload_builder.build_device_set_status_payload(
                    token, device_id, normalized
                ),
                self.response_parser.raise_if_session_expired,
                "Set status",
            )
            _LOGGER.info(
                "Successfully executed %d command(s) for device %s",
                len(commands),
                device_id,
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            # Network errors: wrapped, so the caller gets an error of the library
            # instead of an aiohttp exception
            raise SyrConnectConnectionError(
                f"Failed to set device status: {err}"
            ) from err
        else:
            return True

    async def get_statistics(
        self, device_id: str, statistic: SyrConnectStatistic
    ) -> list[tuple[datetime, float]]:
        """Fetch the measurement history of one series of a device.

        The cloud keeps measurements a device does not report in its status, for
        example the measurements of a SafeFloor sensor between two uploads. The caller
        passes the series of the device family.

        Args:
            device_id: Device collection group ID (DCLG)
            statistic: Series to fetch (web service method and request attributes)

        Returns:
            (timestamp, value) of every measurement, sorted by timestamp (UTC)

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
            stats_data = await self._post_with_session(
                self._device_service_url + statistic.method,
                lambda token: self.payload_builder.build_device_get_statistics_payload(
                    token, device_id, statistic
                ),
                self.response_parser.parse_statistics_response,
                "Statistics",
            )
            _LOGGER.debug("Statistics parsed: %d measurement(s)", len(stats_data))

        except (aiohttp.ClientError, TimeoutError) as err:
            raise SyrConnectConnectionError(
                f"Failed to get {statistic.key} statistics: {err}"
            ) from err
        except ValueError as err:
            # No XML, e.g. a maintenance page
            raise SyrConnectInvalidResponseError(
                f"Invalid {statistic.key} statistics response: {err}"
            ) from err
        else:
            return stats_data
