"""Data update coordinator for SYR Connect."""

from __future__ import annotations

import asyncio
import copy
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify
from homeassistant.util.unit_conversion import TemperatureConverter, UnitlessRatioConverter

from .api_json import SyrConnectJsonAPI
from .api_xml import SyrConnectXmlAPI
from .const import (
    _SYR_CONNECT_API_SERVICES,
    _SYR_CONNECT_SAFEFLOOR_DEVICE_KINDS,
    _SYR_CONNECT_SAFEFLOOR_HISTORY_RETRY_FIRST_HOURS,
    _SYR_CONNECT_SAFEFLOOR_HISTORY_RETRY_MAX_HOURS,
    _SYR_CONNECT_SAFEFLOOR_HISTORY_SERIES,
    _SYR_CONNECT_SAFEFLOOR_HISTORY_STORE_VERSION,
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
from .exceptions import SyrConnectAuthError, SyrConnectConnectionError
from .helpers import get_default_scan_interval_for_entry, get_sensor_iwh_value
from .models import MODEL_SIGNATURES, detect_model
from .repairs import create_issue, delete_issue

_LOGGER = logging.getLogger(__name__)


class SyrConnectDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching SYR Connect data."""

    api: SyrConnectXmlAPI | SyrConnectJsonAPI
    # Owning config entry ID; used to scope entity unique_ids across hubs (set in __init__.py).
    entry_id: str | None = None

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
            self._configuration_url: str | None = None  # No cloud service URL for local JSON API
            _LOGGER.info("Coordinator initialized with JSON API (host=%s, model=%s)", host, model)
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
            )
            self._username = username
            self._configuration_url = svc["configuration_url"] if svc else None
            _LOGGER.info("Coordinator initialized with XML API (username=%s)", username)

        # Keep aiohttp session for optional JSON API usage per-device
        self._session = session

        # SafeFloor measurement history fetch state, keyed by device ID (serial number). It is
        # kept in a store (loaded on first use), so a restart does not fetch an upload again.
        self._safefloor_history: dict[str, SafeFloorHistoryState] = {}
        self._safefloor_history_store: Store[dict[str, dict[str, Any]]] | None = None
        # Devices without upload timestamp, logged once
        self._safefloor_history_no_marker: set[str] = set()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API.

        Returns:
            Dictionary containing devices and projects data

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            UpdateFailed: If API communication fails
        """
        try:
            # Login if not already logged in or session expired.
            # For the XML API this also (re-)populates api.projects, which is
            # required before device tasks can be dispatched.
            if not self.api.is_session_valid():
                _LOGGER.debug("No valid session, logging in...")
                await self.api.login()

            all_devices = []

            # Get devices from all projects in parallel
            device_tasks = [self.api.get_devices(project["id"]) for project in self.api.projects]

            # Gather device lists for all projects. We use `return_exceptions=True`
            # so asyncio.gather will never raise; any per-project failures are
            # returned as Exception instances and handled below.
            projects_devices = await asyncio.gather(*device_tasks, return_exceptions=True)

            # Process each project's devices
            for project_idx, result in enumerate(projects_devices):
                if isinstance(result, SyrConnectAuthError):
                    raise ConfigEntryAuthFailed(
                        f"Authentication failed during device list poll: {result}"
                    ) from result
                if isinstance(result, Exception):
                    _LOGGER.warning(
                        "Failed to get devices for project %s: %s",
                        self.api.projects[project_idx]["name"], result
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
                    if isinstance(device_result, SyrConnectAuthError):
                        raise ConfigEntryAuthFailed(
                            f"Authentication failed during device status poll: {device_result}"
                        ) from device_result
                    if isinstance(device_result, Exception):
                        _LOGGER.warning("Device status fetch failed: %s", device_result)
                        continue
                    if device_result:
                        all_devices.append(device_result)

            # SafeFloor sensors upload several measurements at once. Their history is fetched once
            # per new upload and stored as external statistics; the sensor entities stay unchanged
            # (see the SafeFloor section at the end of this module). Failures are logged and
            # retried later, they never fail the regular update.
            if self._api_type == API_TYPE_XML:
                for device in all_devices:
                    if (
                        isinstance(device, dict)
                        and device.get("dk") in _SYR_CONNECT_SAFEFLOOR_DEVICE_KINDS
                        and device.get("status")
                    ):
                        await self._async_update_safefloor_history(device)

            _LOGGER.debug("Update cycle completed: %d device(s) total", len(all_devices))
            return {
                "configuration_url": self._configuration_url,
                "devices": all_devices,
                "projects": self.api.projects,
            }

        except ConfigEntryAuthFailed:
            raise
        except SyrConnectAuthError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise ConfigEntryAuthFailed("Authentication failed. Please reconfigure the integration.") from err
        except SyrConnectConnectionError as err:
            _LOGGER.error("Connection failed: %s", err)
            raise UpdateFailed(f"Connection error: {err}") from err
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

            # Emergency action.
            #
            # SYR returns broken data values; if a device is offline. Setting values are still returned properly,
            # others real data values may change its data type and return empty strings.
            #
            # dst=0 (never online) or dst=1 (offline) means the device is not reachable via the cloud.
            # Mark it unavailable so all entities show as "Unavailable" in HA.
            if str(status.get("dst", "")).strip() in ("0", "1"):
                _LOGGER.debug("Device %s is offline (dst=%s); marking unavailable", device.get("id"), status.get("dst"))
                device["available"] = False
            else:
                device["available"] = True

            # Compute derived sensor values (e.g. getIWH from getCND) so they
            # are available to all platforms without mutating coordinator data
            # from within platform setup code.
            try:
                get_sensor_iwh_value(status)
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Failed to compute derived sensor values for device %s: %s", device.get("id"), err)

            # Delete offline issue if device is back online
            delete_issue(self.hass, f"device_offline_{device['id']}")

            return device

        except SyrConnectAuthError:
            # Propagate — caught by _async_update_data's outer handler
            raise
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

    async def _async_update_safefloor_history(self, device: dict[str, Any]) -> None:
        """Import the measurement history of a SafeFloor sensor once per new upload.

        The timestamp of getSRN changes with every upload of the sensor and comes with the
        regular status, so a new upload is detected without an extra request. Nothing is
        fetched on a schedule, after a restart or without a new upload; a failed fetch is
        retried with a growing delay. See the SafeFloor section at the end of this module.

        Args:
            device: Device dictionary including its status
        """
        if isinstance(self.api, SyrConnectJsonAPI) or "recorder" not in self.hass.config.components:
            return

        device_id = device["id"]
        upload_marker = device["status"].get("getSRN_dt")
        if not upload_marker:
            # Without the upload timestamp a new upload can not be detected: do not fetch blindly
            if device_id not in self._safefloor_history_no_marker:
                self._safefloor_history_no_marker.add(device_id)
                _LOGGER.warning(
                    "Device %s: no upload timestamp (getSRN), SafeFloor measurement history is not fetched",
                    device_id,
                )
            return

        store = await self._async_safefloor_history_store()
        state = self._safefloor_history.setdefault(device_id, SafeFloorHistoryState())
        now = dt_util.utcnow()
        if not state.is_due(upload_marker, now):
            return

        dclg = device.get("dclg", device_id)
        try:
            for key, (measurement_type, unit) in _SYR_CONNECT_SAFEFLOOR_HISTORY_SERIES.items():
                measurements = await self.api.get_safefloor_history(dclg, measurement_type, unit)
                rows = async_import_safefloor_history(
                    self.hass, device_id, device.get("name") or device_id, key, unit, measurements
                )
                _LOGGER.debug(
                    "Device %s: %d %s measurement(s) -> %d statistics row(s)",
                    device_id, len(measurements), key, rows,
                )
        except (SyrConnectAuthError, SyrConnectConnectionError, ValueError, HomeAssistantError) as err:
            state.mark_failed(upload_marker, now)
            _LOGGER.warning(
                "Device %s: failed to import SafeFloor measurement history, next attempt at %s: %s",
                device_id, state.retry_at, err,
            )
        else:
            state.mark_imported(upload_marker)

        await store.async_save({dev_id: dev_state.as_dict() for dev_id, dev_state in self._safefloor_history.items()})

    async def _async_safefloor_history_store(self) -> Store[dict[str, dict[str, Any]]]:
        """Return the store of the SafeFloor fetch state, loading the state on first use."""
        if self._safefloor_history_store is None:
            store = safefloor_history_store(self.hass, self.entry_id)
            for device_id, data in (await store.async_load() or {}).items():
                self._safefloor_history[device_id] = SafeFloorHistoryState.from_dict(data)
            self._safefloor_history_store = store
        return self._safefloor_history_store

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
        if not self.data:
            return None
        for device in self.data.get("devices", []):
            if device["id"] == device_id:
                return device.get("dclg", device_id)
        return None

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

        dclg = self._get_device_dclg_from_srn(device_id)
        if dclg is None:
            raise HomeAssistantError(f"Device {device_id} not found")

        # Optimistically update the in-memory coordinator data so entities show
        # the new value immediately, then attempt to set it via the API and
        # schedule a background refresh to retrieve authoritative data.
        # Ensure get_key is always defined to avoid NameError if command
        # does not follow the 'setXYZ' convention and code later checks it.
        get_key: str | None = None

        try:
            if isinstance(self.data, dict):
                new_data = copy.deepcopy(self.data)
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
                else:
                    get_key = f"get{command[3:]}"
                    for dev in new_data.get("devices", []):
                        if dev.get("id") == device_id:
                            status = dev.setdefault("status", {})
                            status[get_key] = str(value)
                            dev["available"] = True
                            break
                    self.async_set_updated_data(new_data)

        except (KeyError, AttributeError, TypeError, ValueError) as err:  # pragma: no cover - defensive
            _LOGGER.warning("Failed to apply optimistic update to coordinator data: %s", err)

        try:
            await self.api.set_device_status(dclg, [(command, value)])
        except Exception:  # pragma: no cover - defensive
            # Log at debug level since the exception will be caught and logged
            # properly by the calling entity (select, button, etc.)
            _LOGGER.debug("Failed to set device %s via API, re-raising to caller", device_id)
            raise

    async def async_clear_device_alarm(self, device_id: str, field: str = "ala") -> None:
        """Clear active alarm via the /clr/{field} endpoint (JSON API) or clr command (XML API).

        Args:
            device_id: The device ID (serial number)
            field: Alarm field to clear — "ala" (default) or "alm"

        Raises:
            HomeAssistantError: If the request fails
        """
        if isinstance(self.api, SyrConnectJsonAPI):
            await self.api.request_json_data(f"clr/{field}")
            _LOGGER.info("Coordinator: Cleared alarm via /clr/%s for device %s", field, device_id)
        else:
            dclg = self._get_device_dclg_from_srn(device_id) or device_id
            await self.api.set_device_status(dclg, [(f"clr{field.upper()}", "")])
            _LOGGER.info("Coordinator: Cleared alarm via clr%s for device %s", field.upper(), device_id)

    async def async_open_valve(self, device_id: str, set_key: str, set_val: Any) -> None:
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
            raise HomeAssistantError("Coordinator data not available")

        dclg = self._get_device_dclg_from_srn(device_id)
        if dclg is None:
            raise HomeAssistantError(f"Device {device_id} not found")

        status: dict = {}
        for device in self.data.get("devices", []):
            if device["id"] == device_id:
                status = device.get("status", {}) or {}
                break

        # --- Detect active alarm and compute clear command ---
        # Returns (command, value) when an alarm must be cleared first, or None.
        clear_prefix: tuple[str, Any] | None = None
        try:
            model_info = detect_model(status)
            alarm_style_alm: bool = bool(model_info.get("alarm_style_alm"))
            alarm_clear_via_set: bool = bool(model_info.get("alarm_clear_via_set"))
            field = "alm" if alarm_style_alm else "ala"
            get_key = f"get{field.upper()}"
            raw = status.get(get_key)
            if raw is not None and str(raw).strip().upper() not in _SYR_CONNECT_SENSOR_ALA_CODES_NO_ALARM:
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
            )
            clear_prefix = None

        if clear_prefix is None:
            # No active alarm (or detection failed) — normal open path
            await self.async_set_device_value(device_id, set_key, set_val)
            return

        # --- Active alarm: apply optimistic update then send clear + open ---
        get_key_ab: str | None = f"get{set_key[3:]}" if set_key.startswith("set") else None
        try:
            if isinstance(self.data, dict) and get_key_ab:
                new_data = copy.deepcopy(self.data)
                for dev in new_data.get("devices", []):
                    if dev.get("id") == device_id:
                        status = dev.setdefault("status", {})
                        status[get_key_ab] = str(set_val)
                        dev["available"] = True
                        break
                self.async_set_updated_data(new_data)
        except (KeyError, AttributeError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Valve open with alarm clear: failed to apply optimistic update for %s: %s",
                device_id,
                err,
            )

        try:
            if isinstance(self.api, SyrConnectJsonAPI):
                # JSON API: two sequential requests (no multi-command endpoint)
                if clear_prefix[0].startswith("clr"):
                    await self.api.request_json_data(f"clr/{clear_prefix[0][3:].lower()}")
                else:
                    await self.api.set_device_status(dclg, [(clear_prefix[0], clear_prefix[1])])
                await self.api.set_device_status(dclg, [(set_key, set_val)])
                _LOGGER.info(
                    "Valve open with alarm clear (JSON): sent %s then %s=%s for device %s",
                    clear_prefix[0],
                    set_key,
                    set_val,
                    device_id,
                )
            else:
                # XML API: clear + open in a single multi-command payload
                await self.api.set_device_status(
                    dclg, [clear_prefix, (set_key, set_val)]
                )
                _LOGGER.info(
                    "Valve open with alarm clear (XML): sent [%s, %s=%s] for device %s",
                    clear_prefix[0],
                    set_key,
                    set_val,
                    device_id,
                )
        except Exception:
            _LOGGER.debug(
                "Valve open with alarm clear failed for device %s, re-raising", device_id
            )
            raise


# --- SafeFloor measurement history -------------------------------------------------------------
#
# SafeFloor Connect sensors are battery powered. They measure every getWMP seconds (e.g. every
# 3 hours) but upload to the cloud only every getRCP seconds (configurable, e.g. every 4 days).
# The regular status only carries the latest measurement, so the temperature and humidity
# sensor entities stay flat for days and then jump. GetSafeFloorStatistics (report type 4)
# returns the raw measurements of the last 6 days with their timestamps.
#
# When the history is fetched
#   The timestamp of getSRN changes with every upload and comes with the regular status, so a new
#   upload is detected without an extra request. The history is fetched once per new upload
#   (one request per series: temperature and humidity), whatever upload interval the user has
#   configured. The last imported upload is kept in a store, so a restart of Home Assistant does
#   not fetch it again. A failed fetch is retried after 3 hours, then the delay doubles up to
#   24 hours; a new upload starts over. There is no fetch on a schedule.
#
# Why external statistics
#   async_add_external_statistics is the supported Home Assistant API for values with a past
#   timestamp (home-assistant/architecture discussion #559); core integrations whose data arrives
#   late from a cloud use it the same way (e.g. opower, tibber, suez_water). The state history of
#   an entity can not be changed. The long-term statistics of the sensor entities belong to the
#   recorder: it compiles every hour exactly once, and a row written there before makes that
#   compile run fail, so the hour is lost for all sensors. External statistics
#   (syr_connect:<serial>_<key>, source syr_connect) are never compiled by the recorder and can
#   be written at any time. They are no entities; the sensor entities stay unchanged.
#
# How the rows are built
#   Long-term statistics have an hourly resolution. Every hour from the first to the last
#   measurement gets a row: an hour with measurements gets their mean, min and max, an hour
#   without a measurement takes over the row of the hour before exactly. Nothing is interpolated;
#   hours after the last measurement follow with the next upload. Importing the same 6-day window
#   again overwrites the same rows.

_HOUR = timedelta(hours=1)

# Unit -> unit class used by the recorder for unit conversion
_SAFEFLOOR_UNIT_CLASSES: dict[str, str | None] = {
    UnitOfTemperature.CELSIUS: TemperatureConverter.UNIT_CLASS,
    PERCENTAGE: UnitlessRatioConverter.UNIT_CLASS,
}


@dataclass
class SafeFloorHistoryState:
    """Fetch state of the measurement history of one SafeFloor device."""

    upload_marker: str | None = None  # getSRN timestamp of the last imported upload
    failed_marker: str | None = None  # getSRN timestamp of the upload whose fetch failed
    failures: int = 0  # failed fetches of that upload in a row
    retry_at: datetime | None = None

    def is_due(self, upload_marker: str, now: datetime) -> bool:
        """Return True if the history of this upload should be fetched now."""
        if upload_marker == self.upload_marker:
            return False
        if upload_marker == self.failed_marker and self.retry_at is not None:
            return now >= self.retry_at
        return True

    def mark_imported(self, upload_marker: str) -> None:
        """Remember a successful import."""
        self.upload_marker = upload_marker
        self.failed_marker = None
        self.failures = 0
        self.retry_at = None

    def mark_failed(self, upload_marker: str, now: datetime) -> None:
        """Delay the next attempt: first delay, then doubled up to the maximum; a new upload starts over."""
        if upload_marker != self.failed_marker:
            self.failed_marker = upload_marker
            self.failures = 0
        self.failures += 1
        hours = min(
            _SYR_CONNECT_SAFEFLOOR_HISTORY_RETRY_FIRST_HOURS * 2 ** min(self.failures - 1, 10),
            _SYR_CONNECT_SAFEFLOOR_HISTORY_RETRY_MAX_HOURS,
        )
        self.retry_at = now + timedelta(hours=hours)

    def as_dict(self) -> dict[str, Any]:
        """Return the state for the store."""
        return {
            "upload_marker": self.upload_marker,
            "failed_marker": self.failed_marker,
            "failures": self.failures,
            "retry_at": self.retry_at.isoformat() if self.retry_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SafeFloorHistoryState:
        """Return the state read from the store."""
        retry_at = data.get("retry_at")
        return cls(
            upload_marker=data.get("upload_marker"),
            failed_marker=data.get("failed_marker"),
            failures=data.get("failures") or 0,
            retry_at=dt_util.parse_datetime(retry_at) if isinstance(retry_at, str) else None,
        )


def safefloor_history_store(hass: HomeAssistant, entry_id: str | None) -> Store[dict[str, dict[str, Any]]]:
    """Return the store with the SafeFloor fetch state of a config entry."""
    return Store(hass, _SYR_CONNECT_SAFEFLOOR_HISTORY_STORE_VERSION, f"{DOMAIN}.safefloor_history.{entry_id}")


def safefloor_statistic_id(serial_number: str, key: str) -> str:
    """Return the external statistic ID of a SafeFloor measurement series."""
    return f"{DOMAIN}:{slugify(serial_number)}_{key}"


def hourly_statistics(measurements: list[tuple[datetime, float]]) -> list[StatisticData]:
    """Return one row per hour from the first to the last measurement.

    An hour that contains measurements gets their mean, min and max (one measurement:
    its value). An hour without a measurement takes over the row of the hour before
    exactly. Every hour needs a row: the statistics graph card draws a gap between rows
    that do not follow each other, so one row per measurement would only show short dashes.
    """
    hours: dict[datetime, list[float]] = defaultdict(list)
    for timestamp, value in measurements:
        hours[timestamp.replace(minute=0, second=0, microsecond=0)].append(value)
    if not hours:
        return []
    result: list[StatisticData] = []
    start, last_hour = min(hours), max(hours)
    mean = low = high = 0.0
    while start <= last_hour:
        if values := hours.get(start):
            mean, low, high = sum(values) / len(values), min(values), max(values)
        # An hour without a measurement takes over the values of the hour before exactly
        result.append(StatisticData(start=start, mean=mean, min=low, max=high))
        start += _HOUR
    return result


@callback
def async_import_safefloor_history(
    hass: HomeAssistant,
    serial_number: str,
    device_name: str,
    key: str,
    unit: str,
    measurements: list[tuple[datetime, float]],
) -> int:
    """Import SafeFloor measurements as external statistics.

    Rows that already exist are overwritten, so importing the same window again is harmless.

    Returns:
        Number of imported hourly rows
    """
    statistics = hourly_statistics(measurements)
    if not statistics:
        return 0
    # mean_type and unit_class are set explicitly: without them Home Assistant logs a
    # warning and refuses the import from 2026.11 on.
    metadata = StatisticMetaData(
        mean_type=StatisticMeanType.ARITHMETIC,
        has_sum=False,
        # "history" marks the series as measurement history, not as a second sensor
        name=f"{device_name} {key} history",
        source=DOMAIN,
        statistic_id=safefloor_statistic_id(serial_number, key),
        unit_class=_SAFEFLOOR_UNIT_CLASSES.get(unit),
        unit_of_measurement=unit,
    )
    async_add_external_statistics(hass, metadata, statistics)
    _LOGGER.debug(
        "Imported %d hourly row(s) into %s (%s to %s)",
        len(statistics),
        metadata["statistic_id"],
        statistics[0]["start"].isoformat(),
        statistics[-1]["start"].isoformat(),
    )
    return len(statistics)


async def async_remove_safefloor_history_store(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the stored SafeFloor fetch state of a removed config entry."""
    await safefloor_history_store(hass, entry_id).async_remove()
