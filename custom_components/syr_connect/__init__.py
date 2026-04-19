"""The SYR Connect integration."""
from __future__ import annotations

import copy
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .config_flow import ConfigFlow
from .const import (
    _SYR_CONNECT_API_JSON_SCAN_INTERVAL_MINIMUM,
    _SYR_CONNECT_API_XML_SCAN_INTERVAL_MINIMUM,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import get_default_scan_interval_for_entry
from .migrations import v1_to_v2_update_kwargs

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SWITCH,
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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to the current version.

    Version history:
      1 → 2: Added CONF_API_TYPE field and updated unique_id to include
             API type prefix (legacy entries always used the XML API).
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

    _LOGGER.debug("Migrating config entry '%s' from version %d", entry.title, entry.version)

    # Delegate migration steps to helpers in migrations.py
    # Migrate v1 -> v2
    if entry.version == 1:
        update_kwargs = v1_to_v2_update_kwargs(entry)
        if update_kwargs:
            # Mask sensitive fields for logging only;
            safe_update = _mask_sensitive_data(update_kwargs)
            _LOGGER.debug("Applying v1->v2 migration for entry %s: %s", entry.entry_id, safe_update)
            hass.config_entries.async_update_entry(entry, **update_kwargs)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SYR Connect from a config entry."""
    api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML)
    api_identifier = (
        entry.data.get(CONF_HOST) if api_type == API_TYPE_JSON else entry.data.get(CONF_USERNAME, "unknown")
    )
    _LOGGER.info("Setting up SYR Connect integration (%s API) for: %s", api_type.upper(), api_identifier)

    session = async_get_clientsession(hass)

    # Get scan interval from options. If not set, use per-API default (JSON uses
    # a faster default). This ensures new JSON/local entries default to
    # `_SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT`.
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
    )

    # Attach config entry to coordinator for options access
    coordinator.config_entry = entry

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        # Propagate authentication failures so Home Assistant triggers re-auth flows
        raise
    except Exception as err:
        _LOGGER.error("Failed to connect to SYR Connect API: %s", err)
        raise ConfigEntryNotReady(f"Unable to connect to SYR Connect: {err}") from err

    entry.runtime_data = coordinator

    # Register listener for options changes (scan_interval updates)
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("SYR Connect integration setup completed")

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading SYR Connect integration")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = getattr(entry, "runtime_data", None)
        try:
            if coordinator and getattr(coordinator, "_pending_refresh_task", None):
                coordinator._pending_refresh_task.cancel()
        except Exception:
            _LOGGER.debug("Failed to cancel pending coordinator refresh task during unload", exc_info=True)

        _LOGGER.info("SYR Connect integration unloaded successfully")
    else:
        _LOGGER.warning("Failed to unload SYR Connect integration")

    return unload_ok


async def async_options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update (scan_interval changes)."""
    old_scan_interval = entry.runtime_data.update_interval.total_seconds()
    new_scan_interval = get_default_scan_interval_for_entry(entry)

    # Enforce the same minimum as async_setup_entry so no code path can
    # bypass the per-API floor, even if the config flow schema changes.
    api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML)
    min_allowed = (
        _SYR_CONNECT_API_JSON_SCAN_INTERVAL_MINIMUM
        if api_type == API_TYPE_JSON
        else _SYR_CONNECT_API_XML_SCAN_INTERVAL_MINIMUM
    )
    if new_scan_interval < min_allowed:
        _LOGGER.warning(
            "Options scan interval %d is below minimum for %s API; clamping to %d seconds",
            new_scan_interval,
            api_type,
            min_allowed,
        )
        new_scan_interval = min_allowed

    if old_scan_interval != new_scan_interval:
        _LOGGER.info(
            "Scan interval updated from %d to %d seconds, reloading coordinator",
            int(old_scan_interval),
            new_scan_interval,
        )
        entry.runtime_data.update_interval = timedelta(seconds=new_scan_interval)
        await entry.runtime_data.async_request_refresh()
    else:
        _LOGGER.debug("Options updated but scan interval unchanged")
