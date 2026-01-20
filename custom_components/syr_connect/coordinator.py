"""Data update coordinator for SYR Connect."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
import copy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import SyrConnectAPI
from .const import _SYR_CONNECT_SCAN_INTERVAL_DEFAULT, DOMAIN
from .exceptions import SyrConnectAuthError, SyrConnectConnectionError
from .repairs import create_issue, delete_issue

_LOGGER = logging.getLogger(__name__)


class SyrConnectDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching SYR Connect data."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        scan_interval: int = _SYR_CONNECT_SCAN_INTERVAL_DEFAULT,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            session: aiohttp client session
            username: SYR Connect username
            password: SYR Connect password
            scan_interval: Update interval in seconds
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

        self.api = SyrConnectAPI(session, username, password)
        self._username = username

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API.

        Returns:
            Dictionary containing devices and projects data

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            UpdateFailed: If API communication fails
        """
        try:
            # Login if not already logged in or session expired
            if not self.api._is_session_valid():
                _LOGGER.debug("No valid session, logging in...")
                try:
                    await self.api.login()
                except SyrConnectAuthError as err:
                    _LOGGER.error("Authentication failed: %s", err)
                    raise ConfigEntryAuthFailed(
                        "Authentication failed. Please reconfigure the integration."
                    ) from err
                except SyrConnectConnectionError as err:
                    _LOGGER.error("Connection failed: %s", err)
                    raise UpdateFailed(f"Connection error: {err}") from err

            all_devices = []

            # Get devices from all projects in parallel
            device_tasks = [
                self.api.get_devices(project['id'])
                for project in self.api.projects
            ]

            try:
                projects_devices = await asyncio.gather(*device_tasks, return_exceptions=True)
            except Exception as err:
                _LOGGER.error("Failed to fetch devices: %s", err)
                raise UpdateFailed(f"Error fetching devices: {err}") from err

            # Process each project's devices
            for project_idx, result in enumerate(projects_devices):
                if isinstance(result, Exception):
                    _LOGGER.warning(
                        "Failed to get devices for project %s: %s",
                        self.api.projects[project_idx]['name'],
                        result
                    )
                    continue

                project = self.api.projects[project_idx]
                project_id = project['id']
                devices_result = result
                if not isinstance(devices_result, list):
                    _LOGGER.warning("Device list result is not a list: %s", devices_result)
                    continue
                devices: list[dict[str, Any]] = devices_result

                _LOGGER.debug(
                    "Found %d device(s) in project %s",
                    len(devices),
                    project['name']
                )

                # Get status for all devices in parallel
                status_tasks = [
                    self._fetch_device_status(device, project_id)
                    for device in devices
                ]

                device_results = await asyncio.gather(*status_tasks, return_exceptions=True)

                for device_result in device_results:
                    if isinstance(device_result, Exception):
                        _LOGGER.warning("Device status fetch failed: %s", device_result)
                        continue
                    if device_result:
                        all_devices.append(device_result)

            _LOGGER.debug("Update cycle completed: %d device(s) total", len(all_devices))
            return {
                'devices': all_devices,
                'projects': self.api.projects,
            }

        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            _LOGGER.error("Update failed: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _fetch_device_status(
        self, device: dict[str, Any], project_id: str
    ) -> dict[str, Any] | None:
        """Fetch status for a single device.

        Args:
            device: Device dictionary
            project_id: Project ID

        Returns:
            Device dictionary with status or None if failed
        """
        try:
            # Add project_id to device
            device['project_id'] = project_id

            # Use DCLG for API calls
            dclg = device.get('dclg', device['id'])
            status = await self.api.get_device_status(dclg)

            # If parser signalled that the response did not contain the
            # expected sc>dvs>d structure, it returns None. In this case we
            # SHOULD NOT overwrite the existing sensor values. Try to reuse
            # the previous device entry from coordinator data if available
            # (keep existing status). Otherwise mark device unavailable.
            if status is None:
                _LOGGER.warning(
                    "Device %s returned unexpected status structure; preserving previous status if present",
                    device.get('id'),
                )
                # Try to find previous device data and return it unchanged
                if getattr(self, 'data', None) and isinstance(self.data.get('devices', None), list):
                    for prev in self.data.get('devices', []):
                        if prev.get('id') == device.get('id'):
                            _LOGGER.debug("Reusing previous status for device %s", device.get('id'))
                            return prev
                # No previous data available: keep empty status but do NOT mark
                # the device as unavailable to avoid clearing sensors in HA.
                device['status'] = {}
                device['available'] = True
                _LOGGER.debug(
                    "No previous status for device %s; keeping device available with empty status",
                    device.get('id'),
                )
                return device

            device['status'] = status
            device['available'] = True

            # Delete offline issue if device is back online
            delete_issue(self.hass, f"device_offline_{device['id']}")

            return device

        except Exception as err:
            _LOGGER.warning(
                "Failed to get status for device %s: %s",
                device['id'],
                err
            )
            # Add project_id even on error
            device['project_id'] = project_id
            # Mark device as unavailable but still add it
            device['status'] = {}
            device['available'] = False

            # Create repair issue for offline device
            create_issue(
                self.hass,
                f"device_offline_{device['id']}",
                "device_offline",
                translation_placeholders={
                    "device_name": device.get('cna', device['id']),
                },
            )

            return device

    async def async_set_device_value(
        self, device_id: str, command: str, value: Any
    ) -> None:
        """Set a device value.

        Args:
            device_id: The device ID (serial number)
            command: The command to execute
            value: The value to set

        Raises:
            ValueError: If coordinator data is not available or device not found
            HomeAssistantError: If setting the value fails
        """
        _LOGGER.debug("Setting device %s command %s to %s", device_id, command, value)

        if not self.data:
            raise ValueError("Coordinator data not available")

        # Find the DCLG for this device_id (which is now SN)
        dclg = None
        for device in self.data.get('devices', []):
            if device['id'] == device_id:
                dclg = device.get('dclg', device_id)
                break

        if not dclg:
            raise ValueError(f"Device {device_id} not found")

        await self.api.set_device_status(dclg, command, value)

        # Optimistically update the in-memory coordinator data so entities show
        # the new value immediately, then schedule a background refresh to
        # retrieve authoritative data from the API.
        try:
            if isinstance(self.data, dict):
                new_data = copy.deepcopy(self.data)
                get_key = f"get{command[3:]}"
                for dev in new_data.get('devices', []):
                    if dev.get('id') == device_id:
                        status = dev.setdefault('status', {})
                        # Store as string to match API-parsed values
                        status[get_key] = str(value)
                        dev['available'] = True
                        break
                await self.async_set_updated_data(new_data)
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to apply optimistic update to coordinator data")

        # Schedule an immediate refresh in the background to reconcile with API
        try:
            self.hass.async_create_task(self.async_refresh())
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to schedule coordinator refresh after setting device value")
