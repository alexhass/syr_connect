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

import aiohttp

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
    ) -> None:
        self._session = session
        self._host = host
        self._base_path = base_path
        self._base_url = base_url
        self._last_login: datetime | None = None
        self.projects: list[dict[str, Any]] = []

    def _build_base_url(self) -> str | None:
        if self._base_url:
            result = self._base_url.rstrip("/") + "/"
            _LOGGER.debug("JSON API: Built base URL from explicit base_url: %s", result)
            return result
        if not self._host or not self._base_path:
            _LOGGER.debug(
                "JSON API: Cannot build base URL - host=%s, base_path=%s",
                self._host,
                self._base_path
            )
            return None
        result = f"{_SYR_CONNECT_JSON_API_SCHEME}://{self._host}:{_SYR_CONNECT_JSON_API_PORT}{self._base_path}"
        _LOGGER.debug(
            "JSON API: Built base URL from host and base_path: %s (host=%s, port=%s, base_path=%s)",
            result,
            self._host,
            _SYR_CONNECT_JSON_API_PORT,
            self._base_path
        )
        return result

    def is_session_valid(self) -> bool:
        if self._last_login is None:
            return False
        return datetime.now() < (self._last_login + timedelta(minutes=_SESSION_TIMEOUT_MINUTES))

    async def login(self) -> bool:
        """Call the login endpoint required by the device JSON API.

        This performs a GET on the known login URL. Many devices require this
        call before `/get/all` returns values.
        """
        base = self._build_base_url()
        if not base:
            raise ValueError("Base URL not configured for JSON API client")

        login_url = f"{base}/set/ADM/(2)f"
        _LOGGER.debug("JSON API: Login attempt - URL: %s", login_url)
        try:
            timeout_obj = aiohttp.ClientTimeout(total=10)
            async with self._session.get(login_url, timeout=timeout_obj) as resp:
                _LOGGER.debug("JSON API: Login response status: %s", resp.status)
                # We accept any 2xx as success; some devices return an empty body
                resp.raise_for_status()
        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                _LOGGER.error("JSON API authentication failed: HTTP %s", err.status)
                raise SyrConnectAuthError(f"Authentication failed: {err.message}") from err
            _LOGGER.error("JSON API login failed with HTTP %s: %s", err.status, err.message)
            raise SyrConnectConnectionError(f"Login failed: HTTP {err.status} - {err.message}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("JSON API login failed - connection error: %s", err)
            raise SyrConnectConnectionError(f"Login failed: {err}") from err
        except Exception as err:
            _LOGGER.error("JSON API login failed - unexpected error: %s", err)
            raise SyrConnectConnectionError(f"Login failed: {err}") from err

        self._last_login = datetime.now()
        # Single-project placeholder to keep coordinator logic compatible
        self.projects = [{"id": "local", "name": "Local JSON API"}]
        _LOGGER.info("Logged into local JSON API at %s", base)
        return True

    async def _fetch_json(self, path: str, timeout: int = 10) -> dict[str, Any]:
        base = self._build_base_url()
        if not base:
            raise ValueError("Base URL not configured for JSON API client")
        url = f"{base}/{path.lstrip('/')}"
        _LOGGER.debug("JSON API: Requesting URL: %s", url)
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with self._session.get(url, timeout=timeout_obj) as resp:
                _LOGGER.debug("JSON API: Response status from %s: %s", url, resp.status)
                resp.raise_for_status()
                data = await resp.json()
                if not isinstance(data, dict):
                    _LOGGER.error("JSON API returned non-dict payload from %s", url)
                    raise SyrConnectInvalidResponseError("API returned unexpected payload type")

                # Check for API error codes in response
                self._check_api_error_codes(data, url)

                _LOGGER.debug("JSON API: Successfully fetched JSON from %s", url)
                return data
        except aiohttp.ClientResponseError as err:
            if err.status == 404:
                _LOGGER.error("JSON API endpoint not found: %s (HTTP %s)", url, err.status)
                raise SyrConnectConnectionError(
                    f"Endpoint not found: {path} - Check device model and base_path configuration"
                ) from err
            if err.status in (401, 403):
                _LOGGER.error("JSON API authentication error: %s (HTTP %s)", url, err.status)
                raise SyrConnectAuthError(f"Authentication failed: {err.message}") from err
            _LOGGER.error("JSON API HTTP error from %s: HTTP %s - %s", url, err.status, err.message)
            raise SyrConnectConnectionError(f"HTTP {err.status}: {err.message}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("JSON API connection error from %s: %s", url, err)
            raise SyrConnectConnectionError(f"Connection failed: {err}") from err
        except SyrConnectInvalidResponseError:
            raise
        except Exception as err:
            _LOGGER.error("JSON API unexpected error from %s: %s", url, err)
            raise SyrConnectConnectionError(f"Unexpected error: {err}") from err

    async def get_devices(self, project_id: str) -> list[dict[str, Any]]:
        """Return a single-device list constructed from the JSON `/get/all` result.

        The local JSON API targets a single device; we expose it as one device
        so the coordinator code can continue to reuse the same flow as the
        XML API (projects -> devices -> device status).
        """
        # Ensure session/login. If an explicit `base_url` is provided we
        # assume tests or callers handle authentication and skip login.
        if not self._base_url and not self.is_session_valid():
            await self.login()

        # Support tests that patch `_fetch_json` with a synchronous callable
        maybe: Any = self._fetch_json("/get/all")
        if hasattr(maybe, "__await__"):
            status = await maybe
        else:
            status = maybe

        # Derive id and name from common fields if available
        device_id = status.get("getSRN") or status.get("getFRN") or "local_device"
        name = status.get("getCNA") or status.get("getVER") or device_id

        return [{"id": str(device_id), "dclg": str(device_id), "name": str(name)}]

    async def get_device_status(self, device_id: str) -> dict[str, Any] | None:
        """Return the device status dictionary parsed from JSON.

        Returns None on unexpected payload to allow the coordinator to keep
        previous state (same behaviour as the XML client parser).
        """
        _LOGGER.debug("JSON API: Fetching device status for device_id=%s", device_id)

        if not self._base_url and not self.is_session_valid():
            _LOGGER.debug("JSON API: Session invalid, calling login for device_id=%s", device_id)
            await self.login()

        try:
            maybe: Any = self._fetch_json("/get/all")
            if hasattr(maybe, "__await__"):
                status = await maybe
            else:
                status = maybe
            # The JSON API returns a flat dict with getXXX keys already; return
            # as-is so the rest of the integration can operate on the same
            # status shape as the XML parser.
            _LOGGER.debug(
                "JSON API: Successfully fetched %d keys for device_id=%s",
                len(status),
                device_id
            )
            return {k: v for k, v in status.items()}
        except Exception:
            _LOGGER.exception("Failed to parse JSON device status for %s", device_id)
            return None

    async def set_device_status(self, device_id: str, command: str, value: Any) -> bool:
        """Attempt to set a device value using the JSON API.

        The exact set URL pattern differs between devices. The implementation
        below attempts a conservative GET to `/set/{command}/{value}` and
        returns True if the request succeeds. This can be adapted later to
        match exact device behaviour.
        """
        base = self._build_base_url()
        if not base:
            raise ValueError("Base URL not configured for JSON API client")

        # Strip leading "set" if caller sends full command like "setAB"
        cmd = command[3:] if command.lower().startswith("set") else command
        url = f"{base}/set/{cmd}/{value}"
        _LOGGER.debug("JSON API: Setting value - URL: %s", url)
        try:
            timeout_obj = aiohttp.ClientTimeout(total=10)
            async with self._session.get(url, timeout=timeout_obj) as resp:
                _LOGGER.debug("JSON API: Set response status: %s", resp.status)
                resp.raise_for_status()

                # Parse response to check for error codes
                try:
                    data = await resp.json()
                    if isinstance(data, dict):
                        self._check_api_error_codes(data, url)
                except Exception:
                    # If JSON parsing fails, continue - some devices return empty response
                    pass

                _LOGGER.info("Set %s=%s via JSON API for device %s", cmd, value, device_id)
                return True
        except aiohttp.ClientResponseError as err:
            if err.status == 404:
                _LOGGER.error("JSON API set endpoint not found: %s (HTTP %s)", url, err.status)
                raise SyrConnectConnectionError(f"Set command not found: {cmd}") from err
            if err.status in (401, 403):
                _LOGGER.error("JSON API authentication error: %s (HTTP %s)", url, err.status)
                raise SyrConnectAuthError(f"Authentication failed: {err.message}") from err
            _LOGGER.error("JSON API HTTP error from %s: HTTP %s - %s", url, err.status, err.message)
            raise SyrConnectConnectionError(f"HTTP {err.status}: {err.message}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("JSON API connection error from %s: %s", url, err)
            raise SyrConnectConnectionError(f"Connection failed: {err}") from err
        except Exception as err:
            _LOGGER.error("JSON API unexpected error from %s: %s", url, err)
            raise SyrConnectConnectionError(f"Unexpected error: {err}") from err

    def _check_api_error_codes(self, data: dict[str, Any], url: str) -> None:
        """Check response for API error codes and log warnings.

        Known error codes:
        - "NSC": Command does not exist
        - "MIMA": Value outside valid range
        """
        for key, val in data.items():
            if not isinstance(val, str):
                continue

            val_upper = val.upper()
            if val_upper == "NSC":
                _LOGGER.warning(
                    "JSON API: Command '%s' does not exist (NSC error) - URL: %s",
                    key,
                    url
                )
            elif val_upper == "MIMA":
                _LOGGER.warning(
                    "JSON API: Value for '%s' is outside valid range (MIMA error) - URL: %s",
                    key,
                    url
                )
