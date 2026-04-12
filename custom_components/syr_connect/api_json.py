"""Minimal SYR Connect JSON API client for local device API (port 5333).

This module implements a lightweight client for devices that expose a
local JSON API at the URL pattern:

    BASE_URL = "{scheme}://{host}:5333{base_path}"

The expected endpoints used here are:
- GET {BASE_URL}/set/ADM/(2)f    -> login (side-effect required before /get/all)
- GET {BASE_URL}/get/all         -> returns a flat JSON object with getXXX keys
- GET {BASE_URL}/get/{key}       -> returns single value: {"get{key}": value}

Known API error codes in responses:
- "NSC": Command does not exist (No Such Command)
- "MIMA": Value outside valid range (Min/Max exceeded)

The client is intentionally small and mirrors the interface used by the
XML API client so it can be integrated into the coordinator later.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import aiohttp
from yarl import URL

from .exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectHTTPError,
    SyrConnectInvalidResponseError,
)

_LOGGER = logging.getLogger(__name__)

# Local JSON API defaults
_SYR_CONNECT_JSON_API_SCHEME = "http"
_SYR_CONNECT_JSON_API_PORT = 5333

# Session timeout (minutes) - mirror XML client behaviour
_SYR_CONNECT_SESSION_TIMEOUT_MINUTES = 30

# Default timeout for local JSON API requests (seconds)
_SYR_CONNECT_DEFAULT_API_TIMEOUT = 10

# JSON API endpoint paths
_SYR_CONNECT_JSON_ENDPOINT_GET_ALL = "/get/all"


class SyrConnectJsonAPI:
    """Client for the local JSON API served by some SYR devices.

    Args:
        session: aiohttp ClientSession provided by Home Assistant
        host: IP address or hostname of the device (optional if base_url provided)
        base_path: path component for the device (optional)
        base_url: explicit base URL (overrides host/base_path)
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str | None = None,
        base_path: str | None = None,
        base_url: str | None = None,
        login_required: bool | None = None,
    ) -> None:
        """Initialize the JSON API client.

        The client can be initialized in two ways:
        1. With host + base_path: URL will be constructed as http://host:5333/base_path
        2. With base_url: Use the explicit URL (useful for tests)
        """
        # HTTP session management
        self._session = session

        # URL construction parameters (option 1: host + base_path)
        self._host = host
        self._base_path = base_path

        # URL construction parameters (option 2: explicit base_url, overrides host/base_path)
        self._base_url = base_url

        # Session tracking (devices require login before /get/all returns data)
        self._last_login: datetime | None = None

        # Tracks whether ADM login is required for this device:
        # - None: unknown (not checked yet)
        # - True: login required
        # - False: login not required (skip attempts)
        # Allow pre-seeding this value from persisted config entry
        self._login_required: bool | None = login_required

        # Project list (single-item placeholder for coordinator compatibility)
        self.projects: list[dict[str, Any]] = []

        # Cache /get/all response to avoid duplicate API calls when get_devices()
        # is followed immediately by get_device_status()
        self._cached_get_all: dict[str, Any] | None = None

    @property
    def login_required(self) -> bool | None:
        """Whether ADM login is required for this device.

        Returns:
            True if login is required, False if not required,
            None if not yet determined.
        """
        return self._login_required

    def _build_base_url(self) -> str | None:
        """Build the base URL for API requests.

        Priority order:
        1. Explicit base_url (if provided) - used for tests or custom configurations
        2. Constructed from host + base_path (standard production use)

        Returns:
            Base URL with trailing slash, or None if neither option is available
        """
        # Option 1: Use explicit base_url if provided (e.g., for tests)
        if self._base_url:
            result = f"{self._base_url.rstrip('/')}/"
            _LOGGER.debug("JSON API: Built base URL from explicit base_url: %s", result)
            return result

        # Option 2: Construct from host + base_path (standard production use)
        _LOGGER.debug("JSON API: Attempting to build base URL - host=%r, base_path=%r", self._host, self._base_path)
        if not self._host or not self._base_path:
            _LOGGER.error("JSON API: Cannot build base URL - host=%r, base_path=%r", self._host, self._base_path)
            return None

        result = f"{_SYR_CONNECT_JSON_API_SCHEME}://{self._host}:{_SYR_CONNECT_JSON_API_PORT}{self._base_path}"
        _LOGGER.debug(
            "JSON API: Built base URL from host and base_path: %s (host=%r, port=%s, base_path=%r)",
            result,
            self._host,
            _SYR_CONNECT_JSON_API_PORT,
            self._base_path,
        )
        return result

    def is_session_valid(self) -> bool:
        """Check if the current session is still valid.

        Sessions expire after 30 minutes of inactivity. This method checks if:
        1. A login has occurred (_last_login is set)
        2. The session hasn't exceeded the timeout period

        Returns:
            True if session is valid and doesn't need re-login, False otherwise
        """
        return (
            self._last_login is not None
            and datetime.now(UTC) < self._last_login + timedelta(minutes=_SYR_CONNECT_SESSION_TIMEOUT_MINUTES)
        )

    async def _ensure_session(self) -> None:
        """Ensure a valid session exists before making an API request.

        Skips login when:
        - ``_base_url`` is set (direct/local mode — no authentication needed)
        - The current session is still within its validity window
        - ``_login_required`` is explicitly ``False`` (ADM login not required)

        Calls ``login()`` when the session is expired or login status is unknown.
        """
        if self._base_url or self.is_session_valid():
            return
        if self._login_required is False:
            _LOGGER.debug("JSON API: ADM login not required; skipping login for %s", self._build_base_url())
        else:
            _LOGGER.debug(
                "JSON API: ADM login required or unknown; calling login for %s",
                self._build_base_url(),
            )
            await self.login()

    def _construct_encoded_url(self, *path_parts: str, encode: bool = False) -> URL:
        """Build a URL from path components with optional encoding.

        This method handles URL construction with proper encoding for special characters.

        Why manual encoding?
        - The yarl.URL('/') operator doesn't encode colons in path segments
        - Colons are valid in URLs (for ports), but our API needs them encoded
        - We use quote() to encode, then yarl.URL(encoded=True) to prevent re-decoding

        Examples:
            _construct_encoded_url("set", "RTM", "02:30", encode=False)
            -> URL("http://device:5333/neosoft/set/RTM/02:30", encoded=False)

            _construct_encoded_url("set", "ADM", "(2)f", encode=False)
            -> URL("http://device:5333/neosoft/set/ADM/(2)f")

        Args:
            *path_parts: Path components to append to base URL (e.g., "set", "RTM", "value")
            encode: If True, use quote() to URL-encode special characters (default: True)
                   If False, use path components as-is (needed for login with literal parentheses)

        Returns:
            yarl.URL object with encoded=True to preserve our manual encoding

        Raises:
            ValueError: If base URL is not configured
        """
        base = self._build_base_url()
        if not base:
            raise ValueError("Base URL not configured for JSON API client")

        # Encode each path component if requested (quote() encodes special chars like :, /, etc.)
        # Otherwise use path parts as-is (needed for login URL with literal parentheses)
        parts = [quote(str(part), safe='') for part in path_parts] if encode else [str(part) for part in path_parts]
        url_string = f"{base.rstrip('/')}/{'/'.join(parts)}"

        # Use encoded=True to tell yarl "this URL is already encoded, don't decode it"
        # Without this, yarl would decode our %3A back to : which breaks the API
        return URL(url_string, encoded=encode)

    def _strip_set_prefix(self, command: str) -> str:
        """Strip leading 'set' prefix from a command if present.

        Accepts either 'setRTM' or 'RTM' and returns the base command
        portion (e.g., 'RTM').
        """
        return command[3:] if command.lower().startswith("set") else command

    def _normalize_cmd_for_url(self, cmd: str) -> str:
        """Normalize command for use in URL path.

        - 'ADM' remains uppercase (device login command)
        - other commands are lowercase in the URL
        """
        return "ADM" if str(cmd).upper() == "ADM" else str(cmd).lower()

    def _response_key_for(self, cmd: str, value: Any) -> str:
        """Construct the expected response key for a set-command.

        Devices return set-command keys with the command portion UPPERCASE,
        e.g. 'setSLP7'. This helper centralizes that logic.
        """
        return f"set{str(cmd).upper()}{value}"

    def _build_set_url(self, cmd: str, value: Any) -> URL:
        """Build the URL for a set command using normalized cmd.

        Values are sent without percent-encoding because the device firmware
        does not decode percent-encoded characters (e.g. %3A → :) and rejects
        encoded values. Special characters such as colons in RTM time strings
        (e.g. "02:30") must therefore be sent literally.
        """
        url_cmd = self._normalize_cmd_for_url(cmd)
        return self._construct_encoded_url("set", url_cmd, str(value), encode=False)

    async def _execute_http_get(
        self,
        url: URL | str,
        *,
        timeout: int = _SYR_CONNECT_DEFAULT_API_TIMEOUT,
        operation: str = "request",
    ) -> dict[str, Any]:
        """Central method for all HTTP requests with unified error handling.

        Args:
            url: Target URL (yarl.URL or string)
            timeout: Request timeout in seconds
            operation: Description of operation for error messages

        Returns:
            dict[str, Any]: Parsed JSON response (always expected)

            Note: This method ALWAYS returns a dict or raises
            an exception. Callers don't need to check for None or validate dict type.

        Raises:
            SyrConnectAuthError: On 401/403 errors
            SyrConnectConnectionError: On connection/HTTP errors
            SyrConnectInvalidResponseError: On invalid JSON response or non-dict payload
        """
        _LOGGER.debug("JSON API: %s - URL: %s", operation, url)
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with self._session.get(url, timeout=timeout_obj) as resp:
                _LOGGER.debug("JSON API: %s - Response status: %s", operation, resp.status)

                # --- Error Response Debugging ---
                # Read response body BEFORE raise_for_status() so we can log it
                # This helps debug 400/500 errors where the body contains error details
                if resp.status >= 400:
                    try:
                        response_text = await resp.text()
                        _LOGGER.debug("JSON API: %s - Error response: %r", operation, response_text)
                    except Exception as err:
                        _LOGGER.debug("JSON API: %s - Could not read error response: %s", operation, err)

                # Raise exception on HTTP errors (4xx, 5xx)
                resp.raise_for_status()

                # --- Parse and Validate JSON Response ---
                # Note: SYR devices return JSON without proper Content-Type header (application/json).
                # Use content_type=None to skip Content-Type validation
                data = await resp.json(content_type=None)
                if not isinstance(data, dict):
                    _LOGGER.error("JSON API: %s - Non-dict payload from %s", operation, url)
                    raise SyrConnectInvalidResponseError("API returned unexpected payload type")

                # --- Log Response Data ---
                _LOGGER.debug("JSON API: %s - Response data: %s", operation, data)

                # --- Check for API-Level Error Codes ---
                # Even with HTTP 200, the API may return error codes like "NSC" or "MIMA"
                self._validate_response_errors(data, str(url))

                _LOGGER.debug("JSON API: %s - Success", operation)
                return data

        # --- HTTP Error Handling ---
        except aiohttp.ClientResponseError as err:
            # 404: Endpoint doesn't exist (wrong base_path or device model?)
            if err.status == 404:
                _LOGGER.error("JSON API: %s - Endpoint not found: %s (HTTP %s)", operation, url, err.status)
                # Raise an HTTP-specific exception carrying the numeric status
                raise SyrConnectHTTPError(f"{operation.capitalize()} failed: Endpoint not found (HTTP 404)", status=err.status) from err
            # 401/403: Authentication failed (login required or invalid credentials)
            if err.status in (401, 403):
                _LOGGER.error("JSON API: %s - Authentication failed: %s (HTTP %s)", operation, url, err.status)
                raise SyrConnectAuthError(f"Authentication failed: {err.message}") from err
            # Other HTTP errors (400, 500, etc.)
            _LOGGER.error("JSON API: %s - HTTP error: %s (HTTP %s - %s)", operation, url, err.status, err.message)
            # Raise an HTTP-specific exception carrying the numeric status
            raise SyrConnectHTTPError(f"HTTP {err.status}: {err.message}", status=err.status) from err

        # --- Network/Connection Errors ---
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("JSON API: %s - Connection error: %s", operation, err)
            raise SyrConnectConnectionError(f"Connection failed: {err}") from err

        # --- API Validation Errors ---
        # Re-raise our own validation errors without wrapping
        except SyrConnectInvalidResponseError:
            raise

        # --- Unexpected Errors ---
        # Catch-all for any other exceptions
        except Exception as err:
            _LOGGER.error("JSON API: %s - Unexpected error: %s", operation, err)
            raise SyrConnectConnectionError(f"Unexpected error: {err}") from err

    async def login(self) -> bool:
        """Call the login endpoint required by the device JSON API.

        Most SYR devices require calling this login endpoint before /get/all
        returns actual data (otherwise it returns empty or placeholder values).

        The login URL is: {base}/set/ADM/(2)f
        Note: Uses literal parentheses, not URL-encoded %28 and %29

        Returns:
            True on successful login

        Raises:
            SyrConnectAuthError: On authentication failure or invalid status
            SyrConnectConnectionError: On network/HTTP errors
            SyrConnectInvalidResponseError: On validation errors (NSC, MIMA)
        """
        # Build login URL: /set/ADM/(2)f with literal parentheses (encode=False)
        url = self._construct_encoded_url("set", "ADM", "(2)f", encode=False)

        # If we've already determined login is not required, skip network call
        if self._login_required is False:
            _LOGGER.debug("JSON API: ADM login not required; skipping login for %s", self._build_base_url())
            # Mark session as valid for the timeout period so callers won't retry
            self._last_login = datetime.now(UTC)
            self.projects = [{"id": "local", "name": "Local JSON API"}]
            return True

        # Make request and get JSON response with login confirmation
        # Some newer devices do not implement the ADM login endpoint and
        # will return HTTP 404. Treat 404 as "login not required" so the
        # client can continue to fetch /get/all without failing.
        try:
            response = await self._execute_http_get(url, operation="login")
        except SyrConnectHTTPError as err:
            # HTTP-specific errors: treat 404 as "login not required"
            if err.status == 404:
                _LOGGER.info(
                    "JSON API: Login endpoint not found (404) at %s; skipping ADM login",
                    self._build_base_url(),
                )
                # Mark session as valid to avoid retrying login
                self._last_login = datetime.now(UTC)
                # Remember that this device doesn't require ADM login
                self._login_required = False
                # Clear any cached data and provide projects placeholder
                self._cached_get_all = None
                self.projects = [{"id": "local", "name": "Local JSON API"}]
                return True
            # Re-raise other HTTP errors
            raise
        except SyrConnectConnectionError:
            # Non-HTTP connection errors (network, timeouts) should propagate
            raise
        else:
            # Successful HTTP call to login endpoint - record that login is required
            self._login_required = True

        # Validate set-command response: {"setADM(2)f":"OK"}
        # Use shared validation logic that checks for OK/MIMA/NSC status codes
        try:
            self._validate_set_response(response, "ADM", "(2)f", "login", is_login=True)
        except SyrConnectInvalidResponseError as err:
            # Convert validation errors to auth errors for login context
            raise SyrConnectAuthError(f"Login failed: {err}") from err

        # Update session tracking
        self._last_login = datetime.now(UTC)

        # Clear any cached data from previous session
        self._cached_get_all = None

        # Create single-project placeholder (coordinator expects projects list)
        self.projects = [{"id": "local", "name": "Local JSON API"}]

        _LOGGER.info("JSON API: Logged in at %s", self._build_base_url())
        return True

    async def request_json_data(self, path: str, timeout: int = _SYR_CONNECT_DEFAULT_API_TIMEOUT) -> dict[str, Any]:
        """Fetch JSON data from a relative path.

        Convenience wrapper around _execute_http_get() for GET requests that
        return JSON data. Leading slash in `path` is optional and will be stripped.
        """
        # Build URL without encoding (paths like "get/all" are already clean)
        url = self._construct_encoded_url(path.lstrip("/"), encode=False)

        # Make request with JSON parsing enabled
        data = await self._execute_http_get(url, timeout=timeout, operation=f"fetch {path}")
        if data is None:
            raise SyrConnectInvalidResponseError(f"No data returned from {path}")
        return data

    async def get_devices(self, project_id: str) -> list[dict[str, Any]]:
        """Return a single-device list for the local JSON API.

        The local JSON API is single-device focused (one device per base_path).
        This method:
        1. Fetches /get/all to get device information
        2. Extracts the device serial number (getSRN or getFRN)
        3. Caches the response for immediate reuse by get_device_status()
        4. Returns a single-item list compatible with the coordinator's expectations

        Args:
            project_id: Project identifier (ignored for JSON API, kept for interface compatibility)

        Returns:
            List with single device dict containing:
            - id: Device serial number (from getSRN or getFRN)
            - dclg: Device collection ID (same as id for JSON API)
            - name: Device name (custom name or serial number)

        Raises:
            SyrConnectAuthError: On authentication errors
            SyrConnectConnectionError: On connection errors
        """
        # --- Ensure Valid Session ---
        await self._ensure_session()

        # Fetch device status from /get/all endpoint
        status = await self.request_json_data(_SYR_CONNECT_JSON_ENDPOINT_GET_ALL)

        # Cache the response so get_device_status() can reuse it without another API call
        # This is an optimization: coordinator calls get_devices() then get_device_status()
        # back-to-back for each device, but we only need one /get/all request
        self._cached_get_all = status

        # Extract device identifier from response fields (priority order):
        # 1. getSRN: Serial number (most common)
        # 2. getFRN: Factory reference number (fallback for some devices)
        # 3. "local_device": Last resort if neither is present
        device_id = status.get("getSRN") or status.get("getFRN") or "local_device"

        # Use device_id as name
        name = device_id

        # --- Return Device List ---
        # Format matches XML API client output for coordinator compatibility
        # - id: Unique device identifier (serial number)
        # - dclg: Device collection (same as id for JSON API, no hierarchical structure)
        # - name: Display name for UI
        _LOGGER.debug(
            "JSON API: Returning device (device_id=%s, name=%s), cached response for reuse",
            device_id,
            name,
        )
        return [{"id": str(device_id), "dclg": str(device_id), "name": str(name)}]

    async def get_device_status(self, device_id: str) -> dict[str, Any] | None:
        """Return the device status dictionary parsed from JSON.

        Returns None on unexpected payload to allow the coordinator to keep
        previous state (same behaviour as the XML client parser).

        This method reuses the cached response from get_devices() if available,
        otherwise fetches /get/all directly.
        """
        _LOGGER.debug("JSON API: Fetching device status for device_id=%s", device_id)

        try:
            # --- Optimization: Reuse cached response ---
            # If get_devices() was called just before this, use the cached /get/all response
            # to avoid a duplicate API call (coordinator calls both methods back-to-back)
            if self._cached_get_all is not None:
                _LOGGER.debug(
                    "JSON API: Reusing cached /get/all response with %d keys for device_id=%s",
                    len(self._cached_get_all),
                    device_id,
                )
                status = self._cached_get_all
            else:
                # --- Fallback: Fetch directly ---
                # This path is used when:
                # 1. get_device_status() is called directly without get_devices() first
                # 2. In direct testing scenarios
                _LOGGER.debug("JSON API: No cached response, fetching /get/all for device_id=%s", device_id)

                # Ensure we have a valid session before fetching
                await self._ensure_session()

                # Fetch fresh data
                status = await self.request_json_data(_SYR_CONNECT_JSON_ENDPOINT_GET_ALL)

            # --- Return Status Dictionary ---
            # The JSON API returns a flat dict with getXXX keys (getSRN, getAB, etc.)
            # Return as-is so the rest of the integration can process it like XML parser output
            _LOGGER.debug("JSON API: Returning status with %d keys for device_id=%s", len(status), device_id)
            return dict(status)

        # --- Error Handling ---
        # Return None on parsing errors to let coordinator keep previous state
        # (same behavior as XML client for graceful degradation)
        except (ValueError, KeyError, TypeError, AttributeError):
            _LOGGER.exception("Failed to parse JSON device status for %s", device_id)
            return None

    async def get_value(self, command: str) -> dict[str, Any]:
        """Fetch a single value from the device using /get/{key}.

        The JSON API supports fetching individual values instead of all data:
        - /get/all returns all values: {"getFLO": 0, "getTMP": 25, ...}
        - /get/flo returns single value: {"getFLO": 0}

        This method provides flexible access to individual device values without
        fetching the entire state.

        Args:
            key: Value key to fetch (e.g., "FLO", "TMP", "AB")
                 The "get" prefix is optional and will be stripped if present.

        Returns:
            Dictionary with single key-value pair: {"get{key}": value}

        Raises:
            SyrConnectAuthError: On authentication errors
            SyrConnectConnectionError: On connection errors
            SyrConnectInvalidResponseError: If response is invalid

        Example:
            >>> result = await api.get_value("FLO")
            >>> print(result)
            {"getFLO": 0}
        """
        # --- Normalize Key ---
        # Accept both "FLO" and "getFLO", normalize to just "FLO" for URL
        cmd = command[3:] if command.lower().startswith("get") else command

        # Normalize command casing: ADM must remain uppercase, all other
        # commands should be lowercase when used in the URL and when
        # constructing expected response keys. This mirrors device
        # behaviour where ADM is a special control command.
        cmd = "ADM" if str(cmd).upper() == "ADM" else str(cmd).lower()

        # --- Ensure Valid Session ---
        await self._ensure_session()

        # --- Build URL and Fetch ---
        # Format: /get/{cmd} (e.g., /get/FLO)
        path = f"/get/{cmd}"
        _LOGGER.debug("JSON API: Fetching single value for cmd=%s (path=%s)", command, path)

        # Fetch data using existing request infrastructure
        data = await self.request_json_data(path)

        # --- Validate Response ---
        # Expected format: {"get{cmd}": value}
        expected_key = f"get{str(cmd).upper()}"
        if expected_key not in data:
            _LOGGER.error(
                "JSON API: Response missing expected cmd '%s' for get_value(%s) - got: %s",
                expected_key,
                command,
                data,
            )
            raise SyrConnectInvalidResponseError(f"Response missing expected key '{expected_key}'")

        _LOGGER.debug("JSON API: Retrieved %s=%s", expected_key, data[expected_key])
        return data

    async def set_device_status(self, device_id: str, command: str, value: Any) -> bool:
        """Attempt to set a device value using the JSON API.

        Args:
            device_id: Device identifier
            command: Command name (e.g., "setRTM" or "RTM")
            value: Value to set

        Returns:
            True if the request succeeds

        Raises:
            SyrConnectAuthError: On authentication errors
            SyrConnectConnectionError: On connection errors
            SyrConnectInvalidResponseError: On validation errors (NSC, MIMA)
        """
        # --- Normalize Command Name ---
        # Some callers send "setAB", others send "AB" - normalize to base
        # command and build the correct URL form via helpers.
        base_cmd = self._strip_set_prefix(command)

        # Build URL with Path Encoding using helper (handles ADM exception)
        url = self._build_set_url(base_cmd, value)

        _LOGGER.debug("JSON API: Setting %s=%s for device %s", base_cmd, value, device_id)

        # --- Make Request ---
        # Response format: {"set{cmd}{value}": "OK"} or {"set{cmd}{value}": "MIMA"}
        # Example: {"setSIR0": "OK"} or {"setRTM02:30": "MIMA"}
        response = await self._execute_http_get(url, operation=f"set {base_cmd}")

        # --- Validate Response Status ---
        # Use shared validation logic that checks for OK/MIMA/NSC status codes
        self._validate_set_response(response, base_cmd, value, device_id)

        _LOGGER.info("JSON API: Set %s=%s for device %s (status: OK)", base_cmd, value, device_id)
        return True

    def _validate_set_response(
        self,
        response: dict[str, Any],
        cmd: str,
        value: Any,
        device_id: str,
        is_login: bool = False,
    ) -> None:
        """Validate a set-command response for success or error status codes.

        Set-commands return responses like:
        - Success: {"set{cmd}{value}": "OK"}
        - Errors: {"set{cmd}{value}": "MIMA"} or {"set{cmd}{value}": "NSC"}

        Args:
            response: JSON response from set-command
            cmd: Command name (e.g., "ADM", "SIR", "RTM")
            value: Value that was set
            device_id: Device identifier (for logging)
            is_login: Whether this is a login command (raises on any non-OK status)

        Raises:
            SyrConnectInvalidResponseError: On MIMA/NSC errors or unexpected status
                (always raises for non-OK when is_login=True)
        """
        # Devices return the command portion UPPERCASE in the response key
        # (e.g., "setABtrue": "OK"). Require the exact uppercase response
        # key to be present.
        #
        # Construct expected response key by concatenating set + cmd + value
        # Example: cmd="sir", value="0" -> response_key="setSIR0"
        # Example: cmd="ADM", value="(2)f" -> response_key="setADM(2)f"
        response_key = self._response_key_for(cmd, value)

        # BUG:
        #   - Neosoft firmware causes "cmd" to become lowercase (e.g., "/set/sv1/15" becomes {"setsv15":"OK"}).
        #   - Trio firmware does properly and always returns uppercase (e.g., {"setPRF1":"OK"}).
        # This is inconsistent and seems to be a firmware bug on Neosoft devices.
        #
        # Perform a case-insensitive lookup for the response key so that
        # devices returning e.g. 'setala255' or 'setALA255' are accepted.
        found_key = next((k for k in response.keys() if k.lower() == response_key.lower()), None)
        if not found_key:
            msg = f"Response missing expected key '{response_key}'"
            _LOGGER.warning("JSON API: %s for device %s (response: %s)", msg, device_id, response)
            # For login, missing key is a failure
            if is_login:
                raise SyrConnectInvalidResponseError(msg)
            # For other commands, don't fail hard (graceful degradation)
            return

        status = response[found_key]

        # Check status value
        if status == "OK":
            # Success - no action needed, caller will log
            return
        elif status == "MIMA":
            msg = f"Value {value} is outside valid range for command {cmd}"
            # Log at debug level since the exception will be caught and logged
            # properly by the calling entity (select, button, etc.)
            _LOGGER.debug("JSON API: %s (device: %s)", msg, device_id)
            raise SyrConnectInvalidResponseError(msg)
        elif status == "NSC":
            msg = f"Command {cmd} does not exist for device {device_id}"
            # Log at debug level since the exception will be caught and logged
            # properly by the calling entity (select, button, etc.)
            _LOGGER.debug("JSON API: %s", msg)
            raise SyrConnectInvalidResponseError(msg)
        else:
            # Unknown/unexpected status
            msg = f"Unexpected status '{status}' for command {cmd} (device: {device_id})"
            _LOGGER.warning("JSON API: %s", msg)
            # For login, any non-OK status is a failure
            if is_login:
                raise SyrConnectInvalidResponseError(f"Device returned status '{status}'")
            # For other commands, don't fail hard on unknown status codes
            return

    def _validate_response_errors(self, data: dict[str, Any], url: str) -> None:
        """Check response for API-level error codes and log warnings.

        Even when HTTP status is 200 OK, the SYR API may return error codes
        as values in the response dictionary to indicate issues:

        Known error codes:
        - "NSC" (No Such Command): Command doesn't exist for this device model
        - "MIMA" (Min/Max): Value is outside the valid range for this parameter

        Example error response:
            {"getRTM": "NSC"}  # RTM command not supported on this device
            {"getSV1": "MIMA"} # Value exceeds min/max limits

        Args:
            data: Parsed JSON response dictionary
            url: Request URL (for logging purposes)
        """
        # Map error codes to human-readable warning messages
        error_messages = {
            "NSC": "Command does not exist (NSC error)",
            "MIMA": "Value is outside valid range (MIMA error)",
        }

        # Scan response values for error codes. Only exact uppercase codes
        # are accepted as API error indicators (logged as warnings). Any
        # value that matches a known code in a non-uppercase form is
        # treated as an invalid response and raises an exception.
        for key, val in data.items():
            # Skip set-command keys (e.g., "setRPD4") - these are validated by _validate_set_response()
            # Only log warnings for get-command keys (e.g., "getRTM") with error codes
            if key.lower().startswith("set"):
                continue

            # Check if value is a string
            if not isinstance(val, str):
                continue

            # Exact uppercase match: log a warning
            if (msg := error_messages.get(val)):
                _LOGGER.warning("JSON API: '%s' %s - URL: %s", key, msg, url)
                continue

            # Non-uppercase variant of a known code: treat as invalid
            if val.upper() in error_messages:
                raise SyrConnectInvalidResponseError(
                    f"Invalid error code case for key '{key}': '{val}' - URL: {url}"
                )
