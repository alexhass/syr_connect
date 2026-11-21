"""Data update coordinator for SYR Connect."""

import asyncio
import copy
from datetime import datetime, timedelta
import logging
from typing import Any, cast, override

import aiohttp

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    STATISTIC_UNIT_TO_UNIT_CONVERTER,
    async_add_external_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .aiosyrconnect import (
    API_SERVICES,
    SyrConnectApiDevice,
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectError,
    SyrConnectJsonAPI,
    SyrConnectStatistic,
    SyrConnectStatus,
    SyrConnectXmlAPI,
    is_code_active,
    is_device_offline,
    is_network_error,
)
from .const import (
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
from .helpers.device import detect_device_model, get_device, get_device_model
from .helpers.integration import (
    build_user_agent,
    get_api_locale,
    get_default_scan_interval_for_entry,
    get_integration_version,
)
from .helpers.registry import (
    build_statistic_id,
    build_unreachable_issue_id,
    create_issue,
    delete_issue,
)
from .helpers.values import get_sensor_iwh_value
from .models import detect_model

_LOGGER = logging.getLogger(__name__)

type SyrConnectConfigEntry = ConfigEntry[SyrConnectDataUpdateCoordinator]

# The device list of a cloud project (devices, names, UTC offset) rarely changes. It is
# fetched with the first update after a start or reload and then every 30 minutes, the
# updates in between only fetch the status of the devices.
_SYR_CONNECT_COORDINATOR_DEVICE_LIST_INTERVAL = timedelta(minutes=30)

# While the whole update fails, the update interval doubles after every failed update,
# up to this maximum, so a lasting outage is not polled at the normal interval. The first
# successful update restores the configured interval.
_SYR_CONNECT_COORDINATOR_BACKOFF_MAXIMUM = timedelta(minutes=15)

# Temporary failures keep the data of the last update. When a failure lasts this long,
# it is no longer temporary: the affected devices become unavailable and a repair issue
# tells the user, until data is fetched again.
_SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT = timedelta(hours=1)


def _coordinator_devices(devices: list[SyrConnectApiDevice]) -> list[SyrConnectDevice]:
    """Return the devices of an API client as devices of the coordinator data.

    The coordinator adds `model` and `available` to them, which the API clients do not
    know; the dictionaries are not copied.
    """
    return cast(list[SyrConnectDevice], devices)


def _unavailable_device(device: SyrConnectDevice) -> SyrConnectDevice:
    """Return a copy of a device of the last update that is marked unavailable.

    The device of the last update stays unchanged, it is part of the coordinator data.
    """
    unavailable = device.copy()
    unavailable["available"] = False
    return unavailable


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
        config_entry: SyrConnectConfigEntry | None = None,
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
        # Configured update interval, restored after the backoff of a failed update
        self._scan_interval = timedelta(seconds=scan_interval)

        # Determine API type and create appropriate API client
        api_type = config_data.get(CONF_API_TYPE, API_TYPE_XML)
        self._api_type = api_type

        if api_type == API_TYPE_JSON:
            # Local JSON API
            host = config_data[CONF_HOST]
            model = config_data[CONF_MODEL]

            # The model gives the local path of the JSON API
            model_info = detect_model({}, model=model)
            if model_info.base_path is None:
                raise ValueError(f"Model {model} does not support local JSON API")

            self.api = SyrConnectJsonAPI(
                session,
                host=host,
                model=model_info,
                login_required=config_data.get(CONF_LOGIN_REQUIRED),
                user_agent=build_user_agent(get_integration_version(hass)),
            )
            self._username = None  # Not used for JSON API
            self._configuration_url: str | None = (
                None  # No cloud service URL for local JSON API
            )
            self._service: str | None = None  # No cloud service for local JSON API
            # The local JSON API reports no device kind, and the status does not tell
            # the models apart, so the model chosen at setup is used
            self._model: str | None = model
            _LOGGER.info(
                "Coordinator initialized with JSON API (host=%s, model=%s)", host, model
            )
        else:
            # Cloud XML API (default)
            username = config_data[CONF_USERNAME]
            password = config_data[CONF_PASSWORD]

            # Look up the service from CONF_SERVICE (cf_bundle_identifier)
            conf_service = config_data[CONF_SERVICE]
            svc = API_SERVICES[conf_service]

            self.api = SyrConnectXmlAPI(
                session,
                username,
                password,
                service=svc,
                user_agent=build_user_agent(get_integration_version(hass)),
                language=get_api_locale(hass.config.language, hass.config.country),
                # The tzo of the login is the offset of the Home Assistant time zone
                local_now=dt_util.now,
            )
            self._username = username
            self._configuration_url = svc.configuration_url
            self._service = conf_service
            self._model = None
            _LOGGER.debug(
                "Coordinator initialized with XML API (username=%s)", username
            )

        # Keep aiohttp session for optional JSON API usage per-device
        self._session = session

        # False if the device list of at least one project could not be fetched in the
        # last update; devices missing from the data are then not known to be deleted.
        self.device_list_complete = False

        # Device lists of the cloud projects: project ID -> (time of the fetch, devices)
        self._device_lists: dict[str, tuple[datetime, list[SyrConnectDevice]]] = {}
        # Project list the device lists belong to; a login replaces it
        self._device_lists_projects: list[dict[str, Any]] | None = None

        # Failures (of the whole update, a project or a device) already logged as a
        # warning, with the time of the first failure: repeats are logged at debug
        # level, the recovery once at info level
        self._failures: dict[str, datetime] = {}
        # Whether the current update found a failure that lasts longer than
        # _SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT; None keeps the repair issue
        # as it is
        self._unreachable: bool | None = False
        # Whether one of these failures is a network error (see is_network_error)
        self._unreachable_network = False

    @override
    async def _async_update_data(self) -> SyrConnectCoordinatorData:
        """Fetch data from API.

        Returns:
            Dictionary containing devices and projects data

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            UpdateFailed: If API communication fails, or the connection has failed for
                longer than _SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT
        """
        self._unreachable = False
        self._unreachable_network = False
        try:
            all_devices = await self._async_fetch_all_devices()
        except ConfigEntryAuthFailed:
            raise
        except SyrConnectAuthError as err:
            # Home Assistant logs the failed update and starts the re-authentication
            _LOGGER.debug("Authentication failed: %s", err)
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except SyrConnectConnectionError as err:
            # Temporary failures happen (cloud outage, maintenance page, device reboot), e.g. when
            # the re-login after a rejected session token fails. Keep the data of the last update
            # instead of raising UpdateFailed, which would make every entity unavailable,
            # unless the failure lasts longer than _SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT.
            # The coordinator data is None until the first successful refresh
            previous: SyrConnectCoordinatorData | None = self.data
            if previous is not None:
                self._log_failure(
                    "update",
                    "Connection failed, keeping the data of the last update: %s",
                    err,
                )
                self.device_list_complete = False
                self._back_off()
                if self._is_failing_too_long("update", err):
                    # Not temporary anymore: all entities become unavailable
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="update_connection_error",
                    ) from err
                # The devices of the last update keep their state, and so does the
                # repair issue
                self._unreachable = None
                return previous
            # First refresh: nothing to keep, setup is retried (ConfigEntryNotReady), which
            # Home Assistant logs itself
            _LOGGER.debug("Connection failed: %s", err)
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
            self._log_recovery("update", "Connection restored")
            self.update_interval = self._scan_interval
            return {
                "configuration_url": self._configuration_url,
                "devices": all_devices,
                "projects": self.api.projects,
                "service": self._service,
            }
        finally:
            self._update_unreachable_issue()

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
            self._async_get_project_devices(project) for project in self.api.projects
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
                # After _SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT they become unavailable.
                previous = self._previous_project_devices(project["id"])
                self._log_failure(
                    f"project:{project['id']}",
                    "Failed to get devices for project %s, keeping %d device(s) from the last update: %s",
                    project["name"],
                    len(previous),
                    result,
                )
                if self._is_failing_too_long(f"project:{project['id']}", result):
                    previous = [_unavailable_device(d) for d in previous]
                all_devices.extend(previous)
                failed_projects += 1
                continue
            devices: list[SyrConnectDevice] = result
            self._log_recovery(
                f"project:{project['id']}",
                "Devices of project %s fetched again",
                project["name"],
            )

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
                # _fetch_device_status handles every other error itself
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

    async def _async_get_project_devices(
        self, project: dict[str, Any]
    ) -> list[SyrConnectDevice]:
        """Return the devices of a project, fetching the list from the cloud every 30 minutes.

        A login can change the projects, so the lists are fetched again after it. If the
        fetch fails, the last list stays in use and the next update tries again.

        Args:
            project: Project dictionary of the API client

        Returns:
            Copies of the device dictionaries, as the status is added to them

        Raises:
            SyrConnectAuthError: If the session expired and the re-login fails
            SyrConnectError: If the list can not be fetched and there is no last list
        """
        project_id: str = project["id"]
        if self._api_type == API_TYPE_JSON:
            # The device list of the local API is its status request
            return _coordinator_devices(await self.api.get_devices(project_id))

        if self.api.projects is not self._device_lists_projects:
            self._device_lists.clear()
            self._device_lists_projects = self.api.projects
        cached = self._device_lists.get(project_id)
        now = dt_util.utcnow()
        if (
            cached is not None
            and now - cached[0] < _SYR_CONNECT_COORDINATOR_DEVICE_LIST_INTERVAL
        ):
            devices = cached[1]
        else:
            try:
                devices = _coordinator_devices(await self.api.get_devices(project_id))
            except SyrConnectAuthError:
                raise
            except SyrConnectError as err:
                if cached is None:
                    raise
                self._log_failure(
                    f"device_list:{project_id}",
                    "Failed to get devices for project %s, keeping the last device list: %s",
                    project["name"],
                    err,
                )
                devices = cached[1]
            else:
                self._log_recovery(
                    f"device_list:{project_id}",
                    "Device list of project %s fetched again",
                    project["name"],
                )
                self._device_lists[project_id] = (now, devices)
        return [device.copy() for device in devices]

    def _log_failure(self, key: str, message: str, *args: Any) -> None:
        """Log a failure as warning the first time, then at debug level until it recovers.

        Home Assistant asks for one message when something becomes unreachable and one
        when it is back, instead of a warning at every poll.

        Args:
            key: What failed, e.g. "update", "project:<id>" or "device:<id>"
            message: Log message with %-style placeholders
            *args: Arguments of the message
        """
        if key in self._failures:
            _LOGGER.debug(message, *args)
            return
        self._failures[key] = dt_util.utcnow()
        _LOGGER.warning(message, *args)

    def _log_recovery(self, key: str, message: str, *args: Any) -> None:
        """Log at info level that a failure logged by _log_failure has recovered.

        Args:
            key: What recovered, as passed to _log_failure
            message: Log message with %-style placeholders
            *args: Arguments of the message
        """
        if key in self._failures:
            del self._failures[key]
            _LOGGER.info(message, *args)

    def _back_off(self) -> None:
        """Double the update interval after a failed update, up to the maximum.

        A configured interval above _SYR_CONNECT_COORDINATOR_BACKOFF_MAXIMUM is kept.
        """
        current = self.update_interval or self._scan_interval
        self.update_interval = min(
            current * 2,
            max(_SYR_CONNECT_COORDINATOR_BACKOFF_MAXIMUM, self._scan_interval),
        )

    def _is_failing_too_long(self, key: str, err: BaseException | None = None) -> bool:
        """Return whether a failure logged by _log_failure lasts longer than the timeout.

        A failure that lasts this long is remembered for the repair issue of the
        current update, together with whether its error is a network error.

        Args:
            key: What failed, as passed to _log_failure
            err: Error of the current attempt, or None for an unusable answer

        Returns:
            True if the failure started _SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT
            or longer ago
        """
        since = self._failures.get(key)
        if (
            since is None
            or dt_util.utcnow() - since < _SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT
        ):
            return False
        self._unreachable = True
        if err is not None and is_network_error(err):
            self._unreachable_network = True
        return True

    def _update_unreachable_issue(self) -> None:
        """Create or delete the repair issue about data that can not be fetched.

        The issue exists while a failure of the whole update, a project or a device
        lasts longer than _SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT. It is
        deleted with the first update without such a failure. When one of the
        failures is a network error, the issue says so: the user's own network or
        DNS is a likely cause that can be checked.
        """
        if self.config_entry is None or self._unreachable is None:
            return
        issue_id = build_unreachable_issue_id(self.config_entry.entry_id)
        if not self._unreachable:
            delete_issue(self.hass, issue_id)
            return
        create_issue(
            self.hass,
            issue_id,
            "unreachable_network" if self._unreachable_network else "unreachable",
            {
                "entry": self.config_entry.title,
                "minutes": str(
                    int(_SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT.total_seconds())
                    // 60
                ),
            },
        )

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
            _LOGGER.debug(
                "Device %s: Fetching status via %s API",
                device.get("id"),
                self._api_type.upper(),
            )
            status = await self.api.get_device_status(device["id"])

            # If parser signaled that the response did not contain the
            # expected sc>dvs>d structure, it returns None. In this case we
            # SHOULD NOT overwrite the existing sensor values. Try to reuse
            # the previous device entry from coordinator data if available
            # (keep existing status). Otherwise the device stays available with
            # an empty status.
            if status is None:
                self._log_failure(
                    f"device:{device['id']}",
                    "Device %s returned unexpected status structure; preserving previous status if present",
                    device.get("id"),
                )
                return self._previous_device_or_empty(device)

            device["status"] = status
            device["model"] = detect_device_model(device, self._service, self._model)

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
            get_sensor_iwh_value(status)

            # Remove "device offline" repair issues left over from older versions,
            # which created one on every failed status poll
            delete_issue(self.hass, f"device_offline_{device['id']}")

        except SyrConnectAuthError:
            # Propagate — caught by _async_update_data's outer handler
            raise
        except Exception as err:  # noqa: BLE001
            # Temporary failures happen (routing, timeouts). Only log them and keep the
            # previous values; no unavailable state and no repair issue unless the
            # failure lasts longer than _SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT.
            self._log_failure(
                f"device:{device['id']}",
                "Failed to get status for device %s, keeping previous status: %s",
                device["id"],
                err,
            )
            return self._previous_device_or_empty(device, err)
        else:
            self._log_recovery(
                f"device:{device['id']}",
                "Status of device %s fetched again",
                device["id"],
            )
            return device

    def _previous_device_or_empty(
        self, device: SyrConnectDevice, err: BaseException | None = None
    ) -> SyrConnectDevice:
        """Return the device from the last update unchanged, or the device with an empty status.

        Used when the status could not be fetched, so the sensors keep their old values
        instead of being cleared. Without previous data the device stays available with
        an empty status. When the status could not be fetched for longer than
        _SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT, the device is unavailable.

        Args:
            device: Device whose status could not be fetched
            err: Error of the status request, or None for an unusable answer
        """
        unreachable = self._is_failing_too_long(f"device:{device['id']}", err)
        prev = get_device(self.data, device["id"])
        if prev is not None:
            _LOGGER.debug("Reusing previous status for device %s", device.get("id"))
            return _unavailable_device(prev) if unreachable else prev
        _LOGGER.debug(
            "No previous status for device %s; keeping device available with empty status",
            device.get("id"),
        )
        device["status"] = {}
        device["model"] = detect_device_model(device, self._service, self._model)
        device["available"] = not unreachable
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

        if get_device(self.data, device_id) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
            )

        # Optimistically update the in-memory coordinator data so entities show
        # the new values immediately, then attempt to set them via the API.
        previous_data = self.data
        optimistic_data: SyrConnectCoordinatorData | None = None

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
                device.setdefault("status", {})[f"get{command[3:]}"] = str(value)
                device["available"] = True
            applied = True
        if device is not None and applied:
            device["model"] = detect_device_model(device, self._service, self._model)
        if applied:
            self.async_set_updated_data(new_data)
            optimistic_data = new_data

        try:
            await self.api.set_device_status(device_id, commands)
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

        If no alarm is detected, the
        open command is issued without any clear prefix — identical behavior
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

        device = get_device(self.data, device_id)
        if device is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
            )

        status: SyrConnectStatus = device.get("status") or {}

        # --- Detect active alarm and take the reset command of the model ---
        # (command, value) when an alarm must be cleared first, or None.
        clear_prefix: tuple[str, Any] | None = None
        model_info = get_device_model(device)
        get_key = model_info.alarm_status_key
        raw = status.get(get_key)
        if is_code_active(raw):
            clear_prefix = model_info.alarm_reset_command(self.api.clear_value)
            _LOGGER.info(
                "Valve open: active alarm %s=%r on device %s; prepending %s",
                get_key,
                raw,
                device_id,
                clear_prefix[0],
            )

        if clear_prefix is None:
            # No active alarm — normal open path
            await self.async_set_device_value(device_id, set_key, set_val)
            return

        # --- Active alarm: send clear + open together (optimistic update and rollback included) ---
        # XML API: clear + open in a single request. JSON API: one after another, a
        # clr command via its /clr/ endpoint.
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


# The cloud keeps the measurements of the last 6 days. Fetching every 12 hours (as the
# core integrations SolarEdge and Opower do for data that arrives late) keeps the
# history at most 12 hours behind and never loses a measurement.
_SYR_CONNECT_COORDINATOR_STATISTICS_UPDATE_INTERVAL = timedelta(hours=12)


class SyrConnectStatisticsCoordinator(DataUpdateCoordinator[None]):
    """Import the measurement history the cloud keeps for battery devices.

    A SafeFloor measures every getWMP seconds but connects to the cloud only every
    getRCP seconds (e.g. every 4 days), so its status and sensor entities only see
    the latest measurement. The device profile lists the series the cloud keeps
    (`SyrConnectDeviceProfile.statistics`); see "SafeFloor measurement history" in
    docs/syrconnect-protocol.md.

    Home Assistant can not change the past states of an entity, and the recorder
    compiles the long-term statistics of an entity itself. The measurements go into
    external statistics (see build_statistic_id), the API Home Assistant provides for
    values with a past timestamp. The sensor entities stay unchanged. Every run fetches
    the last 6 days again and overwrites the same hourly rows, so a failed run is
    simply repeated by the next one.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SyrConnectConfigEntry,
        coordinator: SyrConnectDataUpdateCoordinator,
    ) -> None:
        """Initialize the statistics coordinator.

        Args:
            hass: Home Assistant instance
            config_entry: Owning config entry
            coordinator: Coordinator of the entry, whose API and devices are used
        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} statistics",
            update_interval=_SYR_CONNECT_COORDINATOR_STATISTICS_UPDATE_INTERVAL,
        )
        self._coordinator = coordinator

        @callback
        def _dummy_listener() -> None:
            pass

        # No entity listens to this coordinator; without a listener it would not
        # refresh on its interval.
        config_entry.async_on_unload(self.async_add_listener(_dummy_listener))

    @override
    async def _async_update_data(self) -> None:
        """Import the measurement history of every device with statistics series.

        Errors are only logged: the next run fetches the same 6 days again.
        """
        api = self._coordinator.api
        data = self._coordinator.data
        if (
            isinstance(api, SyrConnectJsonAPI)
            or data is None
            or "recorder" not in self.hass.config.components
        ):
            return
        translations = await async_get_translations(
            self.hass, self.hass.config.language, "entity", {DOMAIN}
        )
        for device in data["devices"]:
            profile = get_device_model(device).device_profile
            if profile is None or not profile.statistics or not device.get("available"):
                continue
            for statistic in profile.statistics:
                try:
                    measurements = await api.get_statistics(device["id"], statistic)
                except SyrConnectError as err:
                    _LOGGER.warning(
                        "Device %s: failed to import the %s history, retrying with the next run: %s",
                        device["id"],
                        statistic.key,
                        err,
                    )
                    continue
                self._add_statistics(device, statistic, measurements, translations)

    def _add_statistics(
        self,
        device: SyrConnectDevice,
        statistic: SyrConnectStatistic,
        measurements: list[tuple[datetime, float]],
        translations: dict[str, str],
    ) -> None:
        """Write the measurements of one series as hourly external statistics.

        Args:
            device: The device the measurements belong to
            statistic: The series
            measurements: (timestamp, value) of every measurement, sorted by timestamp
            translations: Entity translations of this integration, for the name
        """
        rows = _hourly_statistics(measurements)
        if not rows:
            return
        # Named like the sensor of the series, as SolarEdge names its statistics
        # "<site> <equipment>"
        sensor_name = translations.get(
            f"component.{DOMAIN}.entity.sensor.{statistic.key.lower()}.name",
            statistic.key,
        )
        converter = STATISTIC_UNIT_TO_UNIT_CONVERTER.get(statistic.unit)
        metadata = StatisticMetaData(
            has_sum=False,
            mean_type=StatisticMeanType.ARITHMETIC,
            name=f"{device.get('name') or device['id']} {sensor_name}",
            source=DOMAIN,
            statistic_id=build_statistic_id(device["id"], statistic.key),
            unit_class=converter.UNIT_CLASS if converter is not None else None,
            unit_of_measurement=statistic.unit,
        )
        _LOGGER.debug(
            "Device %s: adding %d hourly row(s) to %s",
            device["id"],
            len(rows),
            metadata["statistic_id"],
        )
        async_add_external_statistics(self.hass, metadata, rows)


def _hourly_statistics(
    measurements: list[tuple[datetime, float]],
) -> list[StatisticData]:
    """Return one statistics row for every hour with measurements.

    Long-term statistics have hourly rows: an hour gets the mean, min and max of its
    measurements. Hours without a measurement get no row; nothing is interpolated.

    Args:
        measurements: (timestamp, value) of every measurement

    Returns:
        The hourly rows sorted by hour, empty without measurements
    """
    hours: dict[datetime, list[float]] = {}
    for timestamp, value in measurements:
        hour = timestamp.replace(minute=0, second=0, microsecond=0)
        hours.setdefault(hour, []).append(value)
    return [
        StatisticData(
            start=hour,
            mean=sum(values) / len(values),
            min=min(values),
            max=max(values),
        )
        for hour, values in sorted(hours.items())
    ]
