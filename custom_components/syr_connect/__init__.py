"""The SYR Connect integration."""

from collections.abc import Awaitable, Callable
import copy
from dataclasses import dataclass
import inspect
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .aiosyrconnect import SyrConnectConnectionError, SyrConnectError
from .config_flow import ConfigFlow
from .const import (
    _SYR_CONNECT_API_JSON_SCAN_INTERVAL_MINIMUM,
    _SYR_CONNECT_API_XML_SCAN_INTERVAL_MINIMUM,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    DOMAIN,
)
from .coordinator import (
    SyrConnectConfigEntry,
    SyrConnectDataUpdateCoordinator,
    SyrConnectStatisticsCoordinator,
)
from .helpers.integration import get_default_scan_interval_for_entry
from .helpers.registry import cleanup_removed_devices, clear_device_statistics
from .migrations import (
    v1_to_v2_update_kwargs,
    v2_to_v3_fix_flo_unit,
    v3_to_v4_add_service,
    v4_to_v5_remove_sta_binary_sensor,
    v5_to_v6_fix_nps_unit,
    v6_to_v7_scope_unique_id_by_entry,
    v7_to_v8_rename_local_model,
    v8_to_v9_detect_local_model,
    v9_to_v10_entry_unique_id_by_service,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.VALVE,
]


def _mask_sensitive_data(update_kwargs: dict) -> dict:
    """Return a deep-copied update_kwargs with sensitive fields masked.

    Currently masks `password` in the `data` section. Used to produce a
    safe-to-log representation without modifying the original dict.
    """
    safe_update = copy.deepcopy(update_kwargs)
    data_section = safe_update.get("data")
    if isinstance(data_section, dict) and "password" in data_section:
        data_section["password"] = "***"
    return safe_update


async def _async_v8_to_v9_detect_local_model(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict | None:
    """Detect the model of a local device whose generic model was removed (v8 -> v9).

    Raises:
        ConfigEntryNotReady: If the device cannot be reached to detect its model;
            Home Assistant retries the migration later.
        ConfigEntryError: If the model of the device cannot be detected.
    """
    try:
        return await v8_to_v9_detect_local_model(hass, entry)
    except SyrConnectConnectionError as err:
        # Leaves the entry at version 8; Home Assistant retries the migration
        _LOGGER.error(
            "Cannot migrate %s: the device is not reachable to detect its model, "
            "the migration is retried: %s",
            entry.title,
            err,
        )
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="migration_cannot_connect",
            translation_placeholders={"device": entry.title},
        ) from err
    except SyrConnectError as err:
        _LOGGER.error(
            "Cannot migrate %s: the model of the device cannot be detected, remove "
            "the entry and set up the device again: %s",
            entry.title,
            err,
        )
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="migration_model_not_detected",
            translation_placeholders={"device": entry.title},
        ) from err


@dataclass(frozen=True, kw_only=True)
class _SyrConnectMigrationStep:
    """A migration step of a config entry, from `from_version` to the next version.

    A step either fixes the registry (`fix_registry`), and the entry only gets the
    next version, or returns the update kwargs of the entry (`update_kwargs`: data,
    unique_id, version), or None to only raise the version.
    """

    from_version: int
    # What the step does, for the log
    description: str
    fix_registry: Callable[[HomeAssistant, ConfigEntry], None] | None = None
    update_kwargs: (
        Callable[[HomeAssistant, ConfigEntry], dict | Awaitable[dict | None] | None]
        | None
    ) = None


# Migration steps of the config entry, in the order of their versions. The lambdas
# look the step functions up at call time, so tests can patch them on this module.
_SYR_CONNECT_MIGRATION_STEPS: tuple[_SyrConnectMigrationStep, ...] = (
    _SyrConnectMigrationStep(
        from_version=1,
        description="set the API type (legacy entries always used the XML API) and "
        "prefix the unique_id with it",
        update_kwargs=lambda hass, entry: v1_to_v2_update_kwargs(entry),
    ),
    _SyrConnectMigrationStep(
        from_version=2,
        description="reset the getFLO unit override from L/min to L/h",
        fix_registry=lambda hass, entry: v2_to_v3_fix_flo_unit(hass, entry),
    ),
    _SyrConnectMigrationStep(
        from_version=3,
        description="add the SYR Connect service to cloud entries created before "
        "multi-service support",
        update_kwargs=lambda hass, entry: v3_to_v4_add_service(entry),
    ),
    _SyrConnectMigrationStep(
        from_version=4,
        description="remove the stale binary_sensor sta (moved to the sensor platform)",
        fix_registry=lambda hass, entry: v4_to_v5_remove_sta_binary_sensor(hass, entry),
    ),
    _SyrConnectMigrationStep(
        from_version=5,
        description='reset the getNPS unit override from "" to "s"',
        fix_registry=lambda hass, entry: v5_to_v6_fix_nps_unit(hass, entry),
    ),
    _SyrConnectMigrationStep(
        from_version=6,
        description="prefix the entity unique_ids with the config entry, so the same "
        "device of two hubs no longer collides",
        fix_registry=lambda hass, entry: v6_to_v7_scope_unique_id_by_entry(hass, entry),
    ),
    _SyrConnectMigrationStep(
        from_version=7,
        description="rename the Optima T2.3 and the generic NeoSoft local models",
        update_kwargs=lambda hass, entry: v7_to_v8_rename_local_model(entry),
    ),
    _SyrConnectMigrationStep(
        from_version=8,
        description="replace the removed generic MultiController local models with "
        "the model detected from the device",
        update_kwargs=_async_v8_to_v9_detect_local_model,
    ),
    _SyrConnectMigrationStep(
        from_version=9,
        description="add the cloud service to the unique_id of cloud entries, so the "
        "same e-mail address can be set up for two services",
        update_kwargs=lambda hass, entry: v9_to_v10_entry_unique_id_by_service(entry),
    ),
)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to the current version.

    Runs the steps of `_SYR_CONNECT_MIGRATION_STEPS` from the version of the entry on,
    one version at a time.

    Raises:
        ConfigEntryNotReady: If the local device cannot be reached to detect its
            model (v8 -> v9); Home Assistant retries the migration later.
        ConfigEntryError: If the model of the local device cannot be detected
            (v8 -> v9).
    """
    # If the config entry version is from the future, we must not attempt
    # to migrate it — Home Assistant expects us to return False so the
    # entry isn't loaded with potentially incompatible data.
    if entry.version > ConfigFlow.VERSION:
        _LOGGER.warning(
            "Config entry '%s' has future version %d; refusing to migrate",
            entry.entry_id,
            entry.version,
        )
        return False

    _LOGGER.debug(
        "Migrating config entry '%s' from version %d", entry.title, entry.version
    )

    for step in _SYR_CONNECT_MIGRATION_STEPS:
        if entry.version != step.from_version:
            continue
        _LOGGER.debug(
            "Applying v%d->v%d migration for entry %s: %s",
            step.from_version,
            step.from_version + 1,
            entry.entry_id,
            step.description,
        )
        update_kwargs = None
        if step.fix_registry is not None:
            step.fix_registry(hass, entry)
        if step.update_kwargs is not None:
            result = step.update_kwargs(hass, entry)
            update_kwargs = await result if inspect.isawaitable(result) else result
        if update_kwargs:
            _LOGGER.debug(
                "Updating entry %s: %s",
                entry.entry_id,
                _mask_sensitive_data(update_kwargs),
            )
            hass.config_entries.async_update_entry(entry, **update_kwargs)
        else:
            hass.config_entries.async_update_entry(entry, version=step.from_version + 1)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SyrConnectConfigEntry) -> bool:
    """Set up SYR Connect from a config entry."""
    api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML)
    api_identifier = (
        entry.data.get(CONF_HOST)
        if api_type == API_TYPE_JSON
        else entry.data.get(CONF_USERNAME, "unknown")
    )
    _LOGGER.debug(
        "Setting up SYR Connect integration (%s API) for: %s",
        api_type.upper(),
        api_identifier,
    )

    session = async_get_clientsession(hass)

    # Get scan interval from options. If not set, use the per-API default, so new
    # JSON/local entries default to `_SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT`.
    scan_interval = get_default_scan_interval_for_entry(entry)

    # Enforce minimum scan interval depending on API type using named constants
    min_allowed = (
        _SYR_CONNECT_API_JSON_SCAN_INTERVAL_MINIMUM
        if api_type == API_TYPE_JSON
        else _SYR_CONNECT_API_XML_SCAN_INTERVAL_MINIMUM
    )
    if scan_interval < min_allowed:
        _LOGGER.warning(
            "Configured scan interval %s is below minimum for %s API; clamping to %s seconds",
            scan_interval,
            api_type,
            min_allowed,
        )
        scan_interval = min_allowed

    coordinator = SyrConnectDataUpdateCoordinator(
        hass,
        session,
        dict(entry.data),
        scan_interval,
        config_entry=entry,
    )

    # Raises ConfigEntryNotReady if the first update fails (Home Assistant retries the
    # setup and logs it) and ConfigEntryAuthFailed for wrong credentials (re-auth flow)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Remove devices that were removed from the account (e.g. by another user
    # of the same hub) so they don't linger in HA forever alongside their entities.
    # Skipped if a project's device list failed: its devices are missing, not deleted.
    if coordinator.device_list_complete:
        cleanup_removed_devices(hass, coordinator.data, entry.entry_id)
    else:
        _LOGGER.warning("Device list incomplete; skipping removal of stale devices")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Measurement history of battery devices; only the cloud keeps it. It must not
    # delay or fail the setup, so its first run is a background task.
    if api_type == API_TYPE_XML:
        statistics = SyrConnectStatisticsCoordinator(hass, entry, coordinator)
        entry.async_create_background_task(
            hass, statistics.async_refresh(), f"{DOMAIN} statistics"
        )
    _LOGGER.info("SYR Connect integration setup completed")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SyrConnectConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading SYR Connect integration")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        _LOGGER.info("SYR Connect integration unloaded successfully")
    else:
        _LOGGER.warning("Failed to unload SYR Connect integration")

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: SyrConnectConfigEntry) -> None:
    """Delete the measurement history statistics of the devices of a removed entry."""
    device_ids = {
        identifier
        for device_entry in dr.async_entries_for_config_entry(
            dr.async_get(hass), entry.entry_id
        )
        for domain, identifier in device_entry.identifiers
        if domain == DOMAIN
    }
    clear_device_statistics(hass, entry.entry_id, device_ids)
