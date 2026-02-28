"""Minimal SYR Connect JSON API client for local device API (port 5333).

This module implements a lightweight client for devices that expose a
local JSON API at the URL pattern:

    BASE_URL = "http://{ip}:5333/{device_url}/"

The expected endpoints used here are:
- GET {BASE_URL}set/ADM/(2)f    -> login (side-effect required before get/all)
- GET {BASE_URL}get/all         -> returns a flat JSON object with getXXX keys

The client is intentionally small and mirrors the interface used by the
XML API client so it can be integrated into the coordinator later.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from .const import _SYR_CONNECT_JSON_API_PORT

_LOGGER = logging.getLogger(__name__)

# Session timeout (minutes) - mirror XML client behaviour
_SESSION_TIMEOUT_MINUTES = 30


class SyrConnectJsonAPI:
    """Client for the local JSON API served by some SYR devices.

    Args:
        session: aiohttp ClientSession provided by Home Assistant
        ip: IP address of the device (optional if base_url provided)
        device_url: path component for the device (optional)
        base_url: explicit base URL (overrides ip/device_url)
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        ip: str | None = None,
        device_url: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._session = session
        self._ip = ip
        self._device_url = device_url
        self._base_url = base_url
        self._last_login: datetime | None = None
        self.projects: list[dict[str, Any]] = []

    def _build_base_url(self) -> str | None:
        if self._base_url:
            return self._base_url.rstrip("/") + "/"
        if not self._ip or not self._device_url:
            return None
        return f"http://{self._ip}:{_SYR_CONNECT_JSON_API_PORT}/{self._device_url.strip('/')}/"

    def is_session_valid(self) -> bool:
        if self._last_login is None:
            return False
        return datetime.now() < (self._last_login + timedelta(minutes=_SESSION_TIMEOUT_MINUTES))

    async def login(self) -> bool:
        """Call the login endpoint required by the device JSON API.

        This performs a GET on the known login URL. Many devices require this
        call before `get/all` returns values.
        """
        base = self._build_base_url()
        if not base:
            raise ValueError("Base URL not configured for JSON API client")

        login_url = f"{base}set/ADM/(2)f"
        try:
            timeout_obj = aiohttp.ClientTimeout(total=10)
            async with self._session.get(login_url, timeout=timeout_obj) as resp:
                _LOGGER.debug("JSON API login status: %s", resp.status)
                # We accept any 2xx as success; some devices return an empty body
                resp.raise_for_status()
        except Exception as err:
            _LOGGER.error("JSON API login failed: %s", err)
            raise

        self._last_login = datetime.now()
        # Single-project placeholder to keep coordinator logic compatible
        self.projects = [{"id": "local", "name": "Local JSON API"}]
        _LOGGER.info("Logged into local JSON API at %s", base)
        return True

    async def _fetch_json(self, path: str, timeout: int = 10) -> dict[str, Any]:
        base = self._build_base_url()
        if not base:
            raise ValueError("Base URL not configured for JSON API client")
        url = f"{base}{path.lstrip('/') }"
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with self._session.get(url, timeout=timeout_obj) as resp:
                resp.raise_for_status()
                data = await resp.json()
                if not isinstance(data, dict):
                    raise ValueError("JSON API returned unexpected payload")
                return data
        except Exception as err:
            _LOGGER.error("Failed to fetch JSON from %s: %s", url, err)
            raise

    async def get_devices(self, project_id: str) -> list[dict[str, Any]]:
        """Return a single-device list constructed from the JSON `get/all` result.

        The local JSON API targets a single device; we expose it as one device
        so the coordinator code can continue to reuse the same flow as the
        XML API (projects -> devices -> device status).
        """
        # Ensure session/login
        if not self.is_session_valid():
            await self.login()

        status = await self._fetch_json("get/all")

        # Derive id and name from common fields if available
        device_id = status.get("getSRN") or status.get("getFRN") or "local_device"
        name = status.get("getCNA") or status.get("getVER") or device_id

        return [{"id": str(device_id), "dclg": str(device_id), "name": str(name)}]

    async def get_device_status(self, device_id: str) -> dict[str, Any] | None:
        """Return the device status dictionary parsed from JSON.

        Returns None on unexpected payload to allow the coordinator to keep
        previous state (same behaviour as the XML client parser).
        """
        if not self.is_session_valid():
            await self.login()

        try:
            status = await self._fetch_json("get/all")
            # The JSON API returns a flat dict with getXXX keys already; return
            # as-is so the rest of the integration can operate on the same
            # status shape as the XML parser.
            return {k: v for k, v in status.items()}
        except Exception:
            _LOGGER.exception("Failed to parse JSON device status for %s", device_id)
            return None

    async def set_device_status(self, device_id: str, command: str, value: Any) -> bool:
        """Attempt to set a device value using the JSON API.

        The exact set URL pattern differs between devices. The implementation
        below attempts a conservative GET to `set/{command}/{value}` and
        returns True if the request succeeds. This can be adapted later to
        match exact device behaviour.
        """
        base = self._build_base_url()
        if not base:
            raise ValueError("Base URL not configured for JSON API client")

        # Strip leading "set" if caller sends full command like "setAB"
        cmd = command[3:] if command.lower().startswith("set") else command
        url = f"{base}set/{cmd}/{value}"
        try:
            timeout_obj = aiohttp.ClientTimeout(total=10)
            async with self._session.get(url, timeout=timeout_obj) as resp:
                resp.raise_for_status()
                _LOGGER.info("Set %s=%s via JSON API for device %s", cmd, value, device_id)
                return True
        except Exception as err:
            _LOGGER.error("Failed to set %s via JSON API: %s", cmd, err)
            raise
