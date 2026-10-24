"""Data update coordinator for SYR Connect."""

import asyncio
import copy
from datetime import timedelta
import logging
from typing import Any, override

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_json import SyrConnectJsonAPI
from .api_xml import SyrConnectXmlAPI
from .const import (
    _SYR_CONNECT_API_SERVICES,
    _SYR_CONNECT_SENSOR_ALA_CODES_NO_ALARM,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_LOGIN_REQUIRED,
    CONF_MODEL,
    CONF_SERVICE,
    DOMAIN,
)
from .data import SyrConnectCoordinatorData, SyrConnectDevice
from .exceptions import SyrConnectAuthError, SyrConnectConnectionError
from .helpers import (
    get_api_locale,
    get_default_scan_interval_for_entry,
    get_device,
    get_sensor_iwh_value,
    is_device_offline,
)
from .models import MODEL_SIGNATURES, detect_model
from .repairs import delete_issue

_LOGGER = logging.getLogger(__name__)


class SyrConnectDataUpdateCoordinator(
    DataUpdateCoordinator[SyrConnectCoordinatorData | None]
):
    """Class to manage fetching SYR Connect data."""

    api: SyrConnectXmlAPI | SyrConnectJsonAPI
    # Owning config entry ID; used to scope entity unique_ids across hubs.
    entry_id: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        config_data: dict[str, Any],
        scan_interval: int | None = None,
        *,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            session: aiohttp client session
            config_data: Configuration data containing API type and credentials
            scan_interval: Update interval in seconds
            config_entry: Owning config entry; its entry_id scopes the entity unique_ids
                so the same device reachable from several hubs does not collide
                (see build_unique_id)
        """
        # If caller didn't provide a scan_interval, compute per-API default
        if scan_interval is None:
            # Pass a mapping-like object to the helper so it can inspect
            # `data` (config_data) and `options` consistently.
            scan_interval = get_default_scan_interval_for_entry(
                {"data": config_data, "options": {}}
            )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        if config_entry is not None:
            self.entry_id = config_entry.entry_id

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
                if sig.name == model:
                    base_path = sig.base_path
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
            self._configuration_url: str | None = (
                None  # No cloud service URL for local JSON API
            )
            _LOGGER.info(
                "Coordinator initialized with JSON API (host=%s, model=%s)", host, model
            )
        else:
            # Cloud XML API (default)
            username = config_data[CONF_USERNAME]
            password = config_data[CONF_PASSWORD]

            # Look up service parameters from CONF_SERVICE (cf_bundle_identifier)
            conf_service = config_data.get(CONF_SERVICE)
            svc = _SYR_CONNECT_API_SERVICES.get(conf_service) if conf_service else None
            api_app_name = svc["api_app_name"] if svc else None
            api_base_url = svc["api_base_url"] if svc else None
            cf_bundle_identifier = svc["cf_bundle_identifier"] if svc else None

            self.api = SyrConnectXmlAPI(
                session,
                username,
                password,
                api_app_name=api_app_name,
                api_base_url=api_base_url,
                cf_bundle_identifier=cf_bundle_identifier,
                language=get_api_locale(hass.config.language, hass.config.country),
            )
            self._username = username
            self._configuration_url = svc["configuration_url"] if svc else None
            _LOGGER.debug(
                "Coordinator initialized with XML API (username=%s)", username
            )

        # Keep aiohttp session for optional JSON API usage per-device
        self._session = session

        # False if the device list of at least one project could not be fetched in the
        # last update; devices missing from the data are then not known to be deleted.
        self.device_list_complete = False

    @override
    async def _async_update_data(self) -> SyrConnectCoordinatorData:
        """Fetch data from API.

        Returns:
            Dictionary containing devices and projects data

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            UpdateFailed: If API communication fails
        """
        try:
            all_devices = await self._async_fetch_all_devices()
        except ConfigEntryAuthFailed:
            raise
        except SyrConnectAuthError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except SyrConnectConnectionError as err:
            # Temporary failures happen (cloud outage, maintenance page, device reboot), e.g. when
            # the re-login after a rejected session token fails. Keep the data of the last update
            # instead of raising UpdateFailed, which would make every entity unavailable.
            # The coordinator data is None until the first successful refresh
            previous: SyrConnectCoordinatorData | None = self.data
            if previous is not None:
                _LOGGER.warning(
                    "Connection failed, keeping the data of the last update: %s", err
                )
                self.device_list_complete = False
                return previous
            # First refresh: nothing to keep, setup is retried (ConfigEntryNotReady)
            _LOGGER.error("Connection failed: %s", err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_connection_error",
            ) from err
        except Exception as err:
            _LOGGER.exception("Update failed")
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        else:
            return {
                "configuration_url": self._configuration_url,
                "devices": all_devices,
                "projects": self.api.projects,
            }

    async def _async_fetch_all_devices(self) -> list[SyrConnectDevice]:
        """Log in if needed and fetch the status of all devices of all projects.

        Returns:
            List of device status dictionaries

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            SyrConnectConnectionError: If no device list could be fetched on the first refresh
        """
        # Login if not already logged in or session expired.
        # For the XML API this also (re-)populates api.projects, which is
        # required before device tasks can be dispatched.
        if not self.api.is_session_valid():
            _LOGGER.debug("No valid session, logging in...")
            await self.api.login()

        all_devices: list[SyrConnectDevice] = []

        # Get devices from all projects in parallel
        device_tasks = [
            self.api.get_devices(project["id"]) for project in self.api.projects
        ]

        # Gather device lists for all projects. We use `return_exceptions=True`
        # so asyncio.gather will never raise; any per-project failures are
        # returned as Exception instances and handled below.
        projects_devices = await asyncio.gather(*device_tasks, return_exceptions=True)

        # Process each project's devices
        failed_projects = 0
        for project_idx, result in enumerate(projects_devices):
            if isinstance(result, SyrConnectAuthError):
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed",
                ) from result

            project = self.api.projects[project_idx]
            if not isinstance(result, list):
                # Temporary failures happen (routing, timeouts, maintenance). Keep the
                # project's devices from the last update with their old values instead
                # of dropping them or marking them unavailable; the next poll updates them.
                previous = self._previous_project_devices(project["id"])
                _LOGGER.warning(
                    "Failed to get devices for project %s, keeping %d device(s) from the last update: %s",
                    project["name"],
                    len(previous),
                    result,
                )
                all_devices.extend(previous)
                failed_projects += 1
                continue
            devices: list[SyrConnectDevice] = result

            _LOGGER.debug(
                "Found %d device(s) in project %s", len(devices), project["name"]
            )

            # Get status for all devices in parallel
            status_tasks = [self._fetch_device_status(device) for device in devices]

            device_results = await asyncio.gather(*status_tasks, return_exceptions=True)

            for device_result in device_results:
                if isinstance(device_result, SyrConnectAuthError):
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN,
                        translation_key="auth_failed",
                    ) from device_result
                if isinstance(device_result, Exception):
                    _LOGGER.warning("Device status fetch failed: %s", device_result)
                    continue
                if isinstance(device_result, dict) and device_result:
                    all_devices.append(device_result)

        # On the first refresh there is nothing to keep: without any device list,
        # setup is retried (ConfigEntryNotReady) instead of showing an empty account.
        if (
            failed_projects
            and failed_projects == len(projects_devices)
            and self.data is None
        ):
            raise SyrConnectConnectionError(
                f"Failed to get the device list of all {failed_projects} project(s)"
            )
        self.device_list_complete = failed_projects == 0

        _LOGGER.debug("Update cycle completed: %d device(s) total", len(all_devices))
        return all_devices

    def _previous_project_devices(self, project_id: str) -> list[SyrConnectDevice]:
        """Return the devices of a project from the last successful update."""
        if not self.data:
            return []
        return [
            d for d in self.data.get("devices", []) if d.get("project_id") == project_id
        ]

    async def _fetch_device_status(
        self, device: SyrConnectDevice
    ) -> SyrConnectDevice | None:
        """Fetch status for a single device.

        Args:
            device: Device dictionary

        Returns:
            Device dictionary with status or None if failed
        """
        try:
            # DCLG remains the device identifier for XML API calls
            dclg = device.get("dclg", device["id"])

            _LOGGER.debug(
                "Device %s: Fetching status via %s API",
                device.get("id"),
                self._api_type.upper(),
            )
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
                return self._previous_device_or_empty(device)

            device["status"] = status

            # Emergency action.
            #
            # SYR returns broken data values; if a device is offline. Setting values are still returned properly,
            # others real data values may change its data type and return empty strings.
            #
            # dst=0 (never online) or dst=1 (offline) means the device is not reachable via the cloud.
            # Mark it unavailable so all entities show as "Unavailable" in HA.
            if is_device_offline(status.get("dst")):
                _LOGGER.debug(
                    "Device %s is offline (dst=%s); marking unavailable",
                    device.get("id"),
                    status.get("dst"),
                )
                device["available"] = False
            else:
                device["available"] = True

            # Compute derived sensor values (e.g. getIWH from getCND) so they
            # are available to all platforms without mutating coordinator data
            # from within platform setup code.
            try:
                get_sensor_iwh_value(status)
            except (ValueError, TypeError) as err:
                _LOGGER.warning(
                    "Failed to compute derived sensor values for device %s: %s",
                    device.get("id"),
                    err,
                )

            # Remove "device offline" repair issues left over from older versions,
            # which created one on every failed status poll
            delete_issue(self.hass, f"device_offline_{device['id']}")

        except SyrConnectAuthError:
            # Propagate — caught by _async_update_data's outer handler
            raise
        except Exception as err:  # noqa: BLE001
            # Temporary failures happen (routing, timeouts). Only log them and keep the
            # previous values; no unavailable state and no repair issue.
            _LOGGER.warning(
                "Failed to get status for device %s, keeping previous status: %s",
                device["id"],
                err,
            )
            return self._previous_device_or_empty(device)
        else:
            return device

    def _previous_device_or_empty(self, device: SyrConnectDevice) -> SyrConnectDevice:
        """Return the device from the last update unchanged, or the device with an empty status.

        Used when the status could not be fetched, so the sensors keep their old values
        instead of being cleared. Without previous data the device stays available with
        an empty status.
        """
        prev = get_device(self.data, device["id"])
        if prev is not None:
            _LOGGER.debug("Reusing previous status for device %s", device.get("id"))
            return prev
        _LOGGER.debug(
            "No previous status for device %s; keeping device available with empty status",
            device.get("id"),
        )
        device["status"] = {}
        device["available"] = True
        return device

    def _get_device_dclg_from_srn(self, device_id: str) -> str | None:
        """Return the DCLG (Device Collection Group UUID) for the given device serial number.

        The coordinator stores devices keyed by serial number (`device["id"]`),
        but XML API calls require the DCLG — the cloud-side UUID assigned to the
        device collection. This helper performs that mapping.

        Args:
            device_id: Serial number of the device to look up.

        Returns:
            The DCLG string when found, or `None` when no device with the given
            serial number is present in coordinator data (including when coordinator
            data is not yet available).
        """
        device = get_device(self.data, device_id)
        if device is None:
            return None
        return device.get("dclg", device_id)

    async def async_set_device_value(
        self, device_id: str, command: str, value: Any
    ) -> None:
        """Set a device value.

        Args:
            device_id: The device ID (serial number)
            command: The command to execute
            value: The value to set

        Raises:
            HomeAssistantError: If coordinator data is not available, device not found, or setting the value fails
        """
        await self.async_set_device_values(device_id, [(command, value)])

    async def async_set_device_values(
        self, device_id: str, commands: list[tuple[str, Any]]
    ) -> None:
        """Set several device values together.

        The XML API sends all commands in a single request, so they are applied
        together or not at all (e.g. setRTH + setRTM of a regeneration time). The
        JSON API has no multi-command endpoint and sends them one after another.

        Args:
            device_id: The device ID (serial number)
            commands: Sequence of (command, value) pairs, executed in order

        Raises:
            HomeAssistantError: If coordinator data is not available, device not found, or setting the values fails
        """
        _LOGGER.debug("Setting device %s commands %s", device_id, commands)

        if not self.data:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="coordinator_data_unavailable",
            )

        dclg = self._get_device_dclg_from_srn(device_id)
        if dclg is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
            )

        # Optimistically update the in-memory coordinator data so entities show
        # the new values immediately, then attempt to set them via the API.
        previous_data = self.data
        optimistic_data: SyrConnectCoordinatorData | None = None

        try:
            if isinstance(self.data, dict):
                new_data = copy.deepcopy(self.data)
                device = get_device(new_data, device_id)
                applied = False
                for command, value in commands:
                    # "clrXYZ" clears an alarm; it has no value to show optimistically
                    if command.startswith("clr"):
                        continue
                    # Derive the read key from the write command.
                    # Convention: all writable SYR commands are named "setXYZ";
                    # the corresponding readable key is "getXYZ".
                    # Guard explicitly so we never write a garbage key to the status dict.
                    if not command.startswith("set"):
                        _LOGGER.warning(
                            "Command '%s' does not follow the 'setXYZ' convention; "
                            "skipping optimistic status update for device %s",
                            command,
                            device_id,
                        )
                        continue
                    if device is not None:
                        device.setdefault("status", {})[f"get{command[3:]}"] = str(
                            value
                        )
                        device["available"] = True
                    applied = True
                if applied:
                    self.async_set_updated_data(new_data)
                    optimistic_data = new_data

        except (KeyError, AttributeError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Failed to apply optimistic update to coordinator data: %s", err
            )

        try:
            await self.api.set_device_status(dclg, commands)
        except Exception:
            # Log at debug level since the exception will be caught and logged
            # properly by the calling entity (select, button, etc.)
            _LOGGER.debug(
                "Failed to set device %s via API, re-raising to caller", device_id
            )
            self._rollback_optimistic_update(previous_data, optimistic_data)
            raise

    def _rollback_optimistic_update(
        self,
        previous_data: SyrConnectCoordinatorData | None,
        optimistic_data: SyrConnectCoordinatorData | None,
    ) -> None:
        """Restore the data from before an optimistic update whose command failed.

        Without this, the entity keeps showing a value the device never received
        (e.g. a valve shown closed while water still flows) until the next poll.
        Skipped if a poll has replaced the optimistic data in the meantime, so
        newer data is not overwritten with older one.
        """
        if optimistic_data is not None and self.data is optimistic_data:
            self.async_set_updated_data(previous_data)

    async def async_clear_device_alarm(
        self, device_id: str, field: str = "ala"
    ) -> None:
        """Clear active alarm via the /clr/{field} endpoint (JSON API) or clr command (XML API).

        Args:
            device_id: The device ID (serial number)
            field: Alarm field to clear — "ala" (default) or "alm"

        Raises:
            HomeAssistantError: If the request fails
        """
        if isinstance(self.api, SyrConnectJsonAPI):
            await self.api.request_json_data(f"clr/{field}")
            _LOGGER.info(
                "Coordinator: Cleared alarm via /clr/%s for device %s", field, device_id
            )
        else:
            dclg = self._get_device_dclg_from_srn(device_id) or device_id
            await self.api.set_device_status(dclg, [(f"clr{field.upper()}", "")])
            _LOGGER.info(
                "Coordinator: Cleared alarm via clr%s for device %s",
                field.upper(),
                device_id,
            )

    async def async_open_valve(
        self, device_id: str, set_key: str, set_val: Any
    ) -> None:
        """Open the valve, prepending an alarm-clear command when an alarm is active.

        When an active alarm is detected in the device status the clear command
        is sent atomically with the open command:

        - **XML API**: both commands travel in a single XML request so the
          device processes them in order without an intermediate state where
          the alarm is cleared but the valve has not yet been commanded open.
        - **JSON API**: the clear request is sent first, then the open request
          as two sequential HTTP calls (the JSON API has no multi-command
          endpoint).

        If no alarm is detected, or alarm detection fails for any reason, the
        open command is issued without any clear prefix — identical behaviour
        to a direct "async_set_device_value" call.

        Args:
            device_id: The device ID (serial number)
            set_key: Valve set command (e.g. "setAB")
            set_val: Value to send (e.g. "1")

        Raises:
            HomeAssistantError: If the API call fails
        """
        if not self.data:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="coordinator_data_unavailable",
            )

        dclg = self._get_device_dclg_from_srn(device_id)
        if dclg is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
            )

        device = get_device(self.data, device_id)
        status: dict = (device.get("status") or {}) if device is not None else {}

        # --- Detect active alarm and compute clear command ---
        # Returns (command, value) when an alarm must be cleared first, or None.
        clear_prefix: tuple[str, Any] | None = None
        try:
            model_info = detect_model(status)
            alarm_style_alm = model_info.alarm_style_alm
            alarm_clear_via_set = model_info.alarm_clear_via_set
            field = "alm" if alarm_style_alm else "ala"
            get_key = f"get{field.upper()}"
            raw = status.get(get_key)
            if (
                raw is not None
                and str(raw).strip().upper()
                not in _SYR_CONNECT_SENSOR_ALA_CODES_NO_ALARM
            ):
                if alarm_clear_via_set:
                    clear_prefix = (f"set{field.upper()}", "FF")
                else:
                    clear_prefix = (f"clr{field.upper()}", "")
                _LOGGER.info(
                    "Valve open: active alarm %s=%r on device %s; prepending %s",
                    get_key,
                    raw,
                    device_id,
                    clear_prefix[0],
                )
        except Exception as err:
            _LOGGER.debug(
                "Valve open: alarm detection failed for %s (will open without clear): %s",
                device_id,
                err,
                exc_info=True,
            )
            clear_prefix = None

        if clear_prefix is None:
            # No active alarm (or detection failed) — normal open path
            await self.async_set_device_value(device_id, set_key, set_val)
            return

        # --- Active alarm: send clear + open together (optimistic update and rollback included) ---
        if isinstance(self.api, SyrConnectJsonAPI) and clear_prefix[0].startswith(
            "clr"
        ):
            # The JSON API clears alarms via its own /clr/<field> endpoint, not via set
            await self.api.request_json_data(f"clr/{clear_prefix[0][3:].lower()}")
            await self.async_set_device_values(device_id, [(set_key, set_val)])
        else:
            # XML API: clear + open in a single request. JSON API (setALA=FF): sent one after another.
            await self.async_set_device_values(
                device_id, [clear_prefix, (set_key, set_val)]
            )
        _LOGGER.info(
            "Valve open with alarm clear: sent %s and %s=%s for device %s",
            clear_prefix[0],
            set_key,
            set_val,
            device_id,
        )
