"""Data update coordinator for SYR Connect."""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api_json import SyrConnectJsonAPI
from .api_xml import SyrConnectXmlAPI
from .const import (
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_LOGIN_REQUIRED,
    CONF_MODEL,
    DOMAIN,
)
from .exceptions import SyrConnectAuthError, SyrConnectConnectionError
from .helpers import get_default_scan_interval_for_entry
from .models import MODEL_SIGNATURES
from .repairs import create_issue, delete_issue

_LOGGER = logging.getLogger(__name__)

# Optimistic update: ignore API responses for this duration after setting a value (seconds)
_SYR_CONNECT_OPTIMISTIC_UPDATE_IGNORE_SECONDS = 60

# Delay before refreshing coordinator data after setting device values (seconds)
_SYR_CONNECT_DELAYED_REFRESH_SECONDS = 60


class SyrConnectDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching SYR Connect data."""

    api: SyrConnectXmlAPI | SyrConnectJsonAPI

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        config_data: dict[str, Any],
        scan_interval: int | None = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            session: aiohttp client session
            config_data: Configuration data containing API type and credentials
            scan_interval: Update interval in seconds
        """
        # If caller didn't provide a scan_interval, compute per-API default
        if scan_interval is None:
            # Pass a mapping-like object to the helper so it can inspect
            # `data` (config_data) and `options` consistently.
            scan_interval = get_default_scan_interval_for_entry({"data": config_data, "options": {}})

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

        # Determine API type and create appropriate API client
        api_type = config_data.get(CONF_API_TYPE, API_TYPE_XML)
        self._api_type = api_type

        if api_type == API_TYPE_JSON:
            # Local JSON API
            host = config_data[CONF_HOST]
            model = config_data[CONF_MODEL]

            # Get base_path for the selected model
            base_path = None
            for sig in MODEL_SIGNATURES:
                if sig["name"] == model:
                    base_path = sig.get("base_path")
                    break

            if base_path is None:
                raise ValueError(f"Model {model} does not support local JSON API")

            self.api = SyrConnectJsonAPI(
                session,
                host=host,
                base_path=base_path,
                login_required=config_data.get(CONF_LOGIN_REQUIRED),
            )
            self._username = None  # Not used for JSON API
            _LOGGER.info("Coordinator initialized with JSON API (host=%s, model=%s)", host, model)
        else:
            # Cloud XML API (default)
            username = config_data[CONF_USERNAME]
            password = config_data[CONF_PASSWORD]
            self.api = SyrConnectXmlAPI(session, username, password)
            self._username = username
            _LOGGER.info("Coordinator initialized with XML API (username=%s)", username)

        # Keep aiohttp session for optional JSON API usage per-device
        self._session = session
        # Tracks valve state (getAB) ignore windows: {(device_id, "getAB") -> expire_timestamp}.
        # SYR devices can take up to ~60 s to reflect a valve open/close command, so we suppress
        # incoming API values for getAB during that window to avoid immediately reverting the
        # optimistic UI state. All other keys are intentionally NOT protected and will be
        # overwritten by the next regular poll cycle.
        self._ignore_until: dict[tuple[str, str], float] = {}
        # Task reference for the scheduled delayed refresh, so it can be
        # cancelled when the entry is unloaded before the delay expires.
        self._pending_refresh_task: asyncio.Task | None = None

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
                    raise ConfigEntryAuthFailed("Authentication failed. Please reconfigure the integration.") from err
                except SyrConnectConnectionError as err:
                    _LOGGER.error("Connection failed: %s", err)
                    raise UpdateFailed(f"Connection error: {err}") from err

            all_devices = []

            # Get devices from all projects in parallel
            device_tasks = [self.api.get_devices(project["id"]) for project in self.api.projects]

            # Gather device lists for all projects. We use `return_exceptions=True`
            # so asyncio.gather will never raise; any per-project failures are
            # returned as Exception instances and handled below.
            projects_devices = await asyncio.gather(*device_tasks, return_exceptions=True)

            # Process each project's devices
            for project_idx, result in enumerate(projects_devices):
                if isinstance(result, Exception):
                    _LOGGER.warning(
                        "Failed to get devices for project %s: %s", self.api.projects[project_idx]["name"], result
                    )
                    continue

                project = self.api.projects[project_idx]
                devices_result = result
                if not isinstance(devices_result, list):
                    _LOGGER.warning("Device list result is not a list: %s", devices_result)
                    continue
                devices: list[dict[str, Any]] = devices_result

                _LOGGER.debug("Found %d device(s) in project %s", len(devices), project["name"])

                # Get status for all devices in parallel
                status_tasks = [self._fetch_device_status(device) for device in devices]

                device_results = await asyncio.gather(*status_tasks, return_exceptions=True)

                for device_result in device_results:
                    if isinstance(device_result, Exception):
                        _LOGGER.warning("Device status fetch failed: %s", device_result)
                        continue
                    if device_result:
                        all_devices.append(device_result)

            _LOGGER.debug("Update cycle completed: %d device(s) total", len(all_devices))
            return {
                "devices": all_devices,
                "projects": self.api.projects,
            }

        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            _LOGGER.error("Update failed: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _fetch_device_status(self, device: dict[str, Any]) -> dict[str, Any] | None:
        """Fetch status for a single device.

        Args:
            device: Device dictionary

        Returns:
            Device dictionary with status or None if failed
        """
        try:
            # DCLG remains the device identifier for XML API calls
            dclg = device.get("dclg", device["id"])

            _LOGGER.debug("Device %s: Fetching status via %s API", device.get("id"), self._api_type.upper())
            status = await self.api.get_device_status(dclg)

            # If parser signalled that the response did not contain the
            # expected sc>dvs>d structure, it returns None. In this case we
            # SHOULD NOT overwrite the existing sensor values. Try to reuse
            # the previous device entry from coordinator data if available
            # (keep existing status). Otherwise mark device unavailable.
            if status is None:
                _LOGGER.warning(
                    "Device %s returned unexpected status structure; preserving previous status if present",
                    device.get("id"),
                )
                # Try to find previous device data and return it unchanged
                if getattr(self, "data", None) and isinstance(self.data.get("devices", None), list):
                    for prev in self.data.get("devices", []):
                        if prev.get("id") == device.get("id"):
                            _LOGGER.debug("Reusing previous status for device %s", device.get("id"))
                            return prev
                # No previous data available: keep empty status but do NOT mark
                # the device as unavailable to avoid clearing sensors in HA.
                device["status"] = {}
                device["available"] = True
                _LOGGER.debug(
                    "No previous status for device %s; keeping device available with empty status",
                    device.get("id"),
                )
                return device

            device["status"] = status
            device["available"] = True

            # Delete offline issue if device is back online
            delete_issue(self.hass, f"device_offline_{device['id']}")

            # For getAB (valve state): if the ignore window is still active, restore
            # the previously-stored optimistic value so the entity does not revert
            # to the stale API state before the device has processed the command.
            # All other keys are not in _ignore_until and pass through unchanged.
            try:
                if getattr(self, "data", None) and isinstance(self.data, dict):
                    prev_devices = {d.get("id"): d for d in self.data.get("devices", []) if isinstance(d, dict)}
                else:
                    prev_devices = {}

                now = time.time()
                for key in list(status.keys()):
                    dev_id_str = str(device.get("id") or "")
                    ignore_key = (dev_id_str, key)
                    expire = self._ignore_until.get(ignore_key)
                    if expire is None:
                        continue
                    if now < expire:
                        prev = prev_devices.get(device.get("id"))
                        if prev and isinstance(prev.get("status"), dict) and key in prev["status"]:
                            status[key] = prev["status"][key]
                        else:
                            # Remove the key so we don't overwrite with possibly stale API value
                            status.pop(key, None)
                    else:
                        # Clean up expired entry
                        self._ignore_until.pop(ignore_key, None)
            except (KeyError, AttributeError, TypeError) as err:  # pragma: no cover - defensive
                _LOGGER.warning("Failed to apply ignore rules to device status for %s: %s", device.get("id"), err)

            return device

        except Exception as err:
            _LOGGER.warning("Failed to get status for device %s: %s", device["id"], err)
            # Mark device as unavailable but still add it
            device["status"] = {}
            device["available"] = False

            # Create repair issue for offline device
            create_issue(
                self.hass,
                f"device_offline_{device['id']}",
                "device_offline",
                translation_placeholders={
                    "device_name": device.get("cna", device["id"]),
                },
            )

            return device

    async def async_set_device_value(self, device_id: str, command: str, value: Any) -> None:
        """Set a device value.

        Args:
            device_id: The device ID (serial number)
            command: The command to execute
            value: The value to set

        Raises:
            HomeAssistantError: If coordinator data is not available, device not found, or setting the value fails
        """
        _LOGGER.debug("Setting device %s command %s to %s", device_id, command, value)

        if not self.data:
            raise HomeAssistantError("Coordinator data not available")

        # Find the DCLG for this device_id (which is now SN)
        dclg = None
        for device in self.data.get("devices", []):
            if device["id"] == device_id:
                dclg = device.get("dclg", device_id)
                break

        if not dclg:
            raise HomeAssistantError(f"Device {device_id} not found")

        # Optimistically update the in-memory coordinator data so entities show
        # the new value immediately, then attempt to set it via the API and
        # schedule a background refresh to retrieve authoritative data.
        # Ensure get_key is always defined to avoid NameError if command
        # does not follow the 'setXXX' convention and code later checks it.
        get_key: str | None = None

        try:
            if isinstance(self.data, dict):
                new_data = copy.deepcopy(self.data)
                # Derive the read key from the write command.
                # Convention: all writable SYR commands are named "setXXX";
                # the corresponding readable key is "getXXX".
                # Guard explicitly so we never write a garbage key to the status dict.
                if not command.startswith("set"):
                    _LOGGER.warning(
                        "Command '%s' does not follow the 'setXXX' convention; "
                        "skipping optimistic status update for device %s",
                        command,
                        device_id,
                    )
                else:
                    get_key = f"get{command[3:]}"
                    for dev in new_data.get("devices", []):
                        if dev.get("id") == device_id:
                            status = dev.setdefault("status", {})
                            status[get_key] = str(value)
                            dev["available"] = True
                            break
                    self.async_set_updated_data(new_data)

                    # For valve commands (getAB) only: suppress incoming API values for
                    # 60 s because SYR devices take time to reflect the new state.
                    # All other keys are intentionally not protected — they will be
                    # overwritten by the next poll, which is the desired behaviour.
                    try:
                        # Only set ignore window when we have a valid get_key
                        if get_key and get_key.lower() == "getab":
                            self._ignore_until[(device_id, get_key)] = (
                                time.time() + _SYR_CONNECT_OPTIMISTIC_UPDATE_IGNORE_SECONDS
                            )
                    except (KeyError, TypeError) as err:
                        _LOGGER.debug("Failed to set ignore_until for getab: %s", err)

        except (KeyError, AttributeError, TypeError, ValueError) as err:  # pragma: no cover - defensive
            _LOGGER.warning("Failed to apply optimistic update to coordinator data: %s", err)

        try:
            await self.api.set_device_status(dclg, command, value)
        except Exception:  # pragma: no cover - defensive
            # Log at debug level since the exception will be caught and logged
            # properly by the calling entity (select, button, etc.)
            _LOGGER.debug("Failed to set device %s via API, re-raising to caller", device_id)
            raise
        else:
            # Only schedule a delayed refresh if the API call succeeded.
            # This avoids a phantom refresh log/error when the set operation
            # raised an exception and was handled by the caller.
            try:
                if self._pending_refresh_task and not self._pending_refresh_task.done():
                    self._pending_refresh_task.cancel()
                self._pending_refresh_task = self.hass.async_create_task(self._delayed_refresh())
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("Failed to schedule delayed coordinator refresh after setting device value")

    async def _delayed_refresh(self, delay: int = _SYR_CONNECT_DELAYED_REFRESH_SECONDS) -> None:
        """Wait `delay` seconds then refresh coordinator data.

        This gives the SYR API time to process changes so the subsequent
        refresh will return the authoritative, updated device status.

        This delay does not change dynamically based on the API type or command since
        valve motors take time to close the valve. SYR does not provide any feedback
        mechanism or status for in-progress commands, so we have no way to know when
        the device has finished processing the command.

        By waiting a full 60 seconds, we can ensure that even slow-processing
        commands have time to complete before we refresh and fetch the new state
        from the API.
        """
        try:
            await asyncio.sleep(delay)
            await self.async_refresh()
        except asyncio.CancelledError:
            raise  # propagate cleanly; this is an intentional cancellation
        except Exception:
            _LOGGER.exception("Delayed refresh failed")
