"""Data update coordinator for SYR Connect."""
from __future__ import annotations

import asyncio
import copy
import logging
import time
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api_json import SyrConnectJsonAPI
from .api_xml import SyrConnectXmlAPI
from .const import (
    _SYR_CONNECT_DEVICE_SETTINGS,
    _SYR_CONNECT_DEVICE_USE_JSON_API,
    _SYR_CONNECT_SCAN_INTERVAL_DEFAULT,
    DOMAIN,
)
from .exceptions import SyrConnectAuthError, SyrConnectConnectionError
from .models import detect_model
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

        self.api = SyrConnectXmlAPI(session, username, password)
        # Keep aiohttp session for optional JSON API usage per-device
        self._session = session
        self._username = username
        # Map of ((device_id, get_key) -> expire_timestamp) to ignore API
        # provided values for a short period after we apply an optimistic
        # update. This is used to avoid immediately overwriting an
        # optimistic `getAB` change with stale API data.
        self._ignore_until: dict[tuple[str, str], float] = {}

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
            if not self.api.is_session_valid():
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

            # DCLG remains the device identifier for XML API calls
            dclg = device.get('dclg', device['id'])

            # Determine whether to use local JSON API for this device.
            # Priority: persistent per-device option in config entry -> in-memory device flag -> False
            use_json = False
            try:
                entry = getattr(self, "config_entry", None)
                if entry and entry.options:
                    device_settings = entry.options.get(_SYR_CONNECT_DEVICE_SETTINGS, {})
                    dev_opts = device_settings.get(str(device.get('id')), {}) if isinstance(device.get('id'), (str | int)) else {}
                    if dev_opts and _SYR_CONNECT_DEVICE_USE_JSON_API in dev_opts:
                        use_json = bool(dev_opts.get(_SYR_CONNECT_DEVICE_USE_JSON_API, False))
                    elif device.get(_SYR_CONNECT_DEVICE_USE_JSON_API) is not None:
                        use_json = bool(device.get(_SYR_CONNECT_DEVICE_USE_JSON_API))
                else:
                    if device.get(_SYR_CONNECT_DEVICE_USE_JSON_API) is not None:
                        use_json = bool(device.get(_SYR_CONNECT_DEVICE_USE_JSON_API))
            except Exception:
                use_json = False
            if use_json:
                # Only attempt JSON API when a `base_path` is known for the device
                ip = device.get('ip') or device.get('getWIP') or device.get('getEIP')
                base_path = device.get('base_path')
                if ip and base_path:
                    json_api = SyrConnectJsonAPI(self._session, ip=ip, base_path=base_path)
                    status = await json_api.get_device_status(dclg)
                else:
                    # Fallback to XML API when JSON API cannot be constructed
                    status = await self.api.get_device_status(dclg)
            else:
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

            # Attempt to detect model from the flattened status and set
            # `device['base_path']` if not already present and the
            # signature provides a base_path mapping. This allows future
            # runs to opt into the local JSON API without using DCLG as
            # a fallback for the base_path.
            try:
                if isinstance(status, dict):
                    if not device.get('base_path'):
                        model = detect_model(status)
                        det_url = model.get('base_path')
                        if det_url:
                            # Set detected base_path and expose a per-device
                            # toggle defaulting to False so the UI can show
                            # an option for devices that actually support it.
                            device['base_path'] = det_url
                            try:
                                # Only add the device-level toggle when supported
                                if _SYR_CONNECT_DEVICE_USE_JSON_API not in device:
                                    device[_SYR_CONNECT_DEVICE_USE_JSON_API] = False
                            except Exception:
                                pass
                            _LOGGER.debug("Set base_path for %s to detected value %s", device.get('id'), det_url)
                        else:
                            # Ensure per-device JSON API flag is not present for devices
                            # that do not support a base_path (explicit None).
                            try:
                                if _SYR_CONNECT_DEVICE_USE_JSON_API in device:
                                    device.pop(_SYR_CONNECT_DEVICE_USE_JSON_API, None)
                            except Exception:
                                pass
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("Model detection failed for device %s", device.get('id'))

            # Delete offline issue if device is back online
            delete_issue(self.hass, f"device_offline_{device['id']}")

            # If we have any ignore rules for this device, preserve the
            # optimistic values for keys that are still within their ignore
            # window (e.g. `getAB`). Replace the API-provided value with the
            # previously-stored value in coordinator.data so entities retain
            # the optimistic state until the ignore window expires.
            try:
                if getattr(self, 'data', None) and isinstance(self.data, dict):
                    prev_devices = {d.get('id'): d for d in self.data.get('devices', []) if isinstance(d, dict)}
                else:
                    prev_devices = {}

                now = time.time()
                for key in list(status.keys()):
                    dev_id_str = str(device.get('id') or "")
                    ignore_key = (dev_id_str, key)
                    expire = self._ignore_until.get(ignore_key)
                    if expire is None:
                        continue
                    if now < expire:
                        prev = prev_devices.get(device.get('id'))
                        if prev and isinstance(prev.get('status'), dict) and key in prev['status']:
                            status[key] = prev['status'][key]
                        else:
                            # Remove the key so we don't overwrite with possibly stale API value
                            status.pop(key, None)
                    else:
                        # Clean up expired entry
                        self._ignore_until.pop(ignore_key, None)
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("Failed to apply ignore rules to device status for %s", device.get('id'))

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

        # Optimistically update the in-memory coordinator data so entities show
        # the new value immediately, then attempt to set it via the API and
        # schedule a background refresh to retrieve authoritative data.
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
                # async_set_updated_data is not awaitable; call directly to update data
                self.async_set_updated_data(new_data)

                # If this was a valve control change (`getAB`), ignore API
                # responses for that key for the next 60 seconds so we don't
                # immediately overwrite the optimistic state with stale data.
                try:
                    if get_key.lower() == 'getab':
                        self._ignore_until[(device_id, get_key)] = time.time() + 60
                except Exception:
                    pass
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to apply optimistic update to coordinator data")

        try:
            await self.api.set_device_status(dclg, command, value)
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to set device %s via API", device_id)
            raise
        finally:
            # Schedule a delayed refresh in the background to give the API
            # time to apply changes server-side before we request authoritative
            # status. Some SYR devices take up to ~60 seconds to reflect
            # configuration changes.
            try:
                self.hass.async_create_task(self._delayed_refresh())
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("Failed to schedule delayed coordinator refresh after setting device value")

    async def _delayed_refresh(self, delay: int = 60) -> None:
        """Wait `delay` seconds then refresh coordinator data.

        This gives the SYR API time to process changes so the subsequent
        refresh will return the authoritative, updated device status.
        """
        try:
            await asyncio.sleep(delay)
            await self.async_refresh()
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Delayed refresh failed")
