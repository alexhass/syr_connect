"""Minimal SYR Connect JSON API client for local device API (port 5333).

This module implements a lightweight client for devices that expose a
local JSON API at the URL pattern:

    BASE_URL = "{scheme}://{host}:5333{base_path}"

The expected endpoints used here are:
- GET {BASE_URL}/set/ADM/(2)f    -> login (side-effect required before /get/all)
- GET {BASE_URL}/get/all         -> returns a flat JSON object with getXXX keys

Known API error codes in responses:
- "NSC": Command does not exist (No Such Command)
- "MIMA": Value outside valid range (Min/Max exceeded)

The client is intentionally small and mirrors the interface used by the
XML API client so it can be integrated into the coordinator later.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

import aiohttp
from yarl import URL

from .exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectInvalidResponseError,
)

_LOGGER = logging.getLogger(__name__)

# Local JSON API defaults
_SYR_CONNECT_JSON_API_SCHEME = "http"
_SYR_CONNECT_JSON_API_PORT = 5333

# Session timeout (minutes) - mirror XML client behaviour
_SESSION_TIMEOUT_MINUTES = 30

# Default timeout for local JSON API requests (seconds)
_SYR_CONNECT_DEFAULT_API_TIMEOUT = 10


class SyrConnectJsonAPI:
    """Client for the local JSON API served by some SYR devices.

    Args:
        session: aiohttp ClientSession provided by Home Assistant
        host: IP address or hostname of the device (optional if base_url provided)
        base_path: path component for the device (optional)
        base_url: explicit base URL (overrides host/base_path)
        device_name: optional custom device name to use instead of serial number
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str | None = None,
        base_path: str | None = None,
        base_url: str | None = None,
        device_name: str | None = None,
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

        # Optional custom device name (otherwise uses serial number)
        self._device_name = device_name

        # Session tracking (devices require login before /get/all returns data)
        self._last_login: datetime | None = None

        # Project list (single-item placeholder for coordinator compatibility)
        self.projects: list[dict[str, Any]] = []

        # Cache /get/all response to avoid duplicate API calls when get_devices()
        # is followed immediately by get_device_status()
        self._cached_get_all: dict[str, Any] | None = None

    def _build_base_url(self) -> str | None:
        """Build the base URL for API requests.

        Priority order:
        1. Explicit base_url (if provided) - used for tests or custom configurations
        2. Constructed from host + base_path - standard production use

        Returns:
            Base URL with trailing slash, or None if neither option is available
        """
        # Option 1: Use explicit base_url if provided (e.g., for tests)
        if self._base_url:
            result = f"{self._base_url.rstrip('/')}/"
            _LOGGER.debug("JSON API: Built base URL from explicit base_url: %s", result)
            return result

        # Option 2: Construct from host + base_path (standard production use)
        if not self._host or not self._base_path:
            _LOGGER.debug("JSON API: Cannot build base URL - host=%s, base_path=%s", self._host, self._base_path)
            return None

        result = f"{_SYR_CONNECT_JSON_API_SCHEME}://{self._host}:{_SYR_CONNECT_JSON_API_PORT}{self._base_path}"
        _LOGGER.debug(
            "JSON API: Built base URL from host and base_path: %s (host=%s, port=%s, base_path=%s)",
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
            and datetime.now() < self._last_login + timedelta(minutes=_SESSION_TIMEOUT_MINUTES)
        )

    def _construct_encoded_url(self, *path_parts: str, encode: bool = True) -> URL:
        """Build a URL from path components with optional encoding.

        This method handles URL construction with proper encoding for special characters.

        Why manual encoding?
        - The yarl.URL('/') operator doesn't encode colons in path segments
        - Colons are valid in URLs (for ports), but our API needs them encoded
        - We use quote() to encode, then yarl.URL(encoded=True) to prevent re-decoding

        Examples:
            _construct_encoded_url("set", "RTM", "02:30", encode=True)
            -> URL("http://device:5333/neosoft/set/RTM/02%3A30", encoded=True)

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

    async def _execute_http_get(
        self,
        url: URL | str,
        *,
        timeout: int = _SYR_CONNECT_DEFAULT_API_TIMEOUT,
        expect_json: bool = True,
        operation: str = "request",
    ) -> dict[str, Any] | None:
        """Central method for all HTTP requests with unified error handling.

        Args:
            url: Target URL (yarl.URL or string)
            timeout: Request timeout in seconds
            expect_json: If True, parse and return JSON response
            operation: Description of operation for error messages

        Returns:
            Parsed JSON dict if expect_json=True, None otherwise

        Raises:
            SyrConnectAuthError: On 401/403 errors
            SyrConnectConnectionError: On connection/HTTP errors
            SyrConnectInvalidResponseError: On invalid JSON response
        """
        _LOGGER.debug("JSON API %s - URL: %s", operation, url)
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with self._session.get(url, timeout=timeout_obj) as resp:
                _LOGGER.debug("JSON API %s - Response status: %s", operation, resp.status)

                # --- Error Response Debugging ---
                # Read response body BEFORE raise_for_status() so we can log it
                # This helps debug 400/500 errors where the body contains error details
                if resp.status >= 400:
                    try:
                        response_text = await resp.text()
                        _LOGGER.debug("JSON API %s - Error response: %r", operation, response_text)
                    except Exception as err:
                        _LOGGER.debug("JSON API %s - Could not read error response: %s", operation, err)

                # Raise exception on HTTP errors (4xx, 5xx)
                resp.raise_for_status()

                # --- Handle Non-JSON Responses ---
                # Some endpoints (like login) don't return JSON, just success/failure via HTTP status
                if not expect_json:
                    return None

                # --- Parse and Validate JSON Response ---
                data = await resp.json()
                if not isinstance(data, dict):
                    _LOGGER.error("JSON API %s - Non-dict payload from %s", operation, url)
                    raise SyrConnectInvalidResponseError("API returned unexpected payload type")

                # --- Check for API-Level Error Codes ---
                # Even with HTTP 200, the API may return error codes like "NSC" or "MIMA"
                self._validate_response_errors(data, str(url))

                _LOGGER.debug("JSON API %s - Success", operation)
                return data

        # --- HTTP Error Handling ---
        except aiohttp.ClientResponseError as err:
            # 404: Endpoint doesn't exist (wrong base_path or device model?)
            if err.status == 404:
                _LOGGER.error("JSON API %s - Endpoint not found: %s (HTTP %s)", operation, url, err.status)
                raise SyrConnectConnectionError(
                    f"{operation.capitalize()} failed: Endpoint not found (HTTP 404)"
                ) from err
            # 401/403: Authentication failed (login required or invalid credentials)
            if err.status in (401, 403):
                _LOGGER.error("JSON API %s - Authentication failed: %s (HTTP %s)", operation, url, err.status)
                raise SyrConnectAuthError(f"Authentication failed: {err.message}") from err
            # Other HTTP errors (400, 500, etc.)
            _LOGGER.error("JSON API %s - HTTP error: %s (HTTP %s - %s)", operation, url, err.status, err.message)
            raise SyrConnectConnectionError(f"HTTP {err.status}: {err.message}") from err

        # --- Network/Connection Errors ---
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("JSON API %s - Connection error: %s", operation, err)
            raise SyrConnectConnectionError(f"Connection failed: {err}") from err

        # --- API Validation Errors ---
        # Re-raise our own validation errors without wrapping
        except SyrConnectInvalidResponseError:
            raise

        # --- Unexpected Errors ---
        # Catch-all for any other exceptions
        except Exception as err:
            _LOGGER.error("JSON API %s - Unexpected error: %s", operation, err)
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
            SyrConnectAuthError: On authentication failure
            SyrConnectConnectionError: On network/HTTP errors
        """
        # Build login URL: /set/ADM/(2)f with literal parentheses (encode=False)
        url = self._construct_encoded_url("set", "ADM", "(2)f", encode=False)

        # Make request (no JSON response expected, just HTTP 2xx = success)
        await self._execute_http_get(url, expect_json=False, operation="login")

        # Update session tracking
        self._last_login = datetime.now()

        # Clear any cached data from previous session
        self._cached_get_all = None

        # Create single-project placeholder (coordinator expects projects list)
        self.projects = [{"id": "local", "name": "Local JSON API"}]

        _LOGGER.info("Logged into local JSON API at %s", self._build_base_url())
        return True

    async def _request_json_data(self, path: str, timeout: int = _SYR_CONNECT_DEFAULT_API_TIMEOUT) -> dict[str, Any]:
        """Fetch JSON data from a relative path.

        This is a convenience wrapper around _execute_http_get() for GET requests
        that return JSON data. Used primarily for the /get/all endpoint.

        Args:
            path: Relative path (e.g., "/get/all" or "get/all")
                 Leading slash is optional and will be stripped
            timeout: Request timeout in seconds (default: 10)

        Returns:
            Parsed JSON response as dictionary

        Raises:
            SyrConnectAuthError: On authentication errors (401/403)
            SyrConnectConnectionError: On connection/HTTP errors
            SyrConnectInvalidResponseError: If response is not valid JSON dict
        """
        # Build URL without encoding (paths like "get/all" are already clean)
        url = self._construct_encoded_url(path.lstrip("/"), encode=False)

        # Make request with JSON parsing enabled
        data = await self._execute_http_get(url, timeout=timeout, expect_json=True, operation=f"fetch {path}")

        # Sanity check: _execute_http_get with expect_json=True should never return None
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
        # Skip login if base_url is set (test mode) or session is still valid
        if not self._base_url and not self.is_session_valid():
            await self.login()

        # Fetch device status from /get/all endpoint
        # Note: Support tests that patch _request_json_data with a synchronous callable
        # (hasattr check handles both async and sync for test compatibility)
        maybe: Any = self._request_json_data("/get/all")
        status = await maybe if hasattr(maybe, "__await__") else maybe

        # Cache the response so get_device_status() can reuse it without another API call
        # This is an optimization: coordinator calls get_devices() then get_device_status()
        # back-to-back for each device, but we only need one /get/all request
        self._cached_get_all = status

        # Extract device identifier from response fields (priority order):
        # 1. getSRN: Serial number (most common)
        # 2. getFRN: Factory reference number (fallback for some devices)
        # 3. "local_device": Last resort if neither is present
        device_id = status.get("getSRN") or status.get("getFRN") or "local_device"

        # Use custom device name if configured, otherwise use extracted device_id
        name = self._device_name or device_id

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
                if not self._base_url and not self.is_session_valid():
                    _LOGGER.debug("JSON API: Session invalid, calling login for device_id=%s", device_id)
                    await self.login()

                # Fetch fresh data (with test support for sync callables)
                maybe: Any = self._request_json_data("/get/all")
                status = await maybe if hasattr(maybe, "__await__") else maybe

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
        """
        # --- Normalize Command Name ---
        # Some callers send "setAB", others send "AB" - we need just "AB" for the URL
        # Example: "setRTM" -> "RTM", "RTM" -> "RTM"
        cmd = command[3:] if command.lower().startswith("set") else command

        # --- Build URL with Path Encoding ---
        # Format: {base}/set/{cmd}/{value}
        # Example: http://192.168.1.100:5333/neosoft/set/RTM/02%3A30
        # Note: encode=True to handle special characters (colons in times, slashes, etc.)
        url = self._construct_encoded_url("set", cmd, str(value), encode=True)

        _LOGGER.debug("JSON API: Setting %s=%s for device %s", cmd, value, device_id)

        # --- Make Request ---
        # Response may be:
        # - Success: {"status":"ok", "key":"getRTM", "old_value":"02:00", "new_value":"02:30"}
        # - Error: {"getRTM": "NSC"} or {"getRTM": "MIMA"}
        # The _execute_http_get() method will check for error codes and log warnings
        await self._execute_http_get(url, expect_json=True, operation=f"set {cmd}")

        _LOGGER.info("Set %s=%s via JSON API for device %s", cmd, value, device_id)
        return True

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

        # Scan response values for error codes
        for key, val in data.items():
            # Check if value is a string matching a known error code
            if isinstance(val, str) and (msg := error_messages.get(val.upper())):
                _LOGGER.warning("JSON API: '%s' %s - URL: %s", key, msg, url)
