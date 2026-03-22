"""The SYR Connect integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import get_default_scan_interval_for_entry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str | Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.VALVE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SYR Connect from a config entry."""
    # Get API type for logging
    from .const import API_TYPE_XML, CONF_HOST

    # Migrate legacy entries without API type
    if CONF_API_TYPE not in entry.data:
        _LOGGER.info(
            "Migrating legacy config entry '%s' to new format with API type",
            entry.title
        )
        await _async_migrate_legacy_entry(hass, entry)

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

    # Enforce minimum scan interval depending on API type
    api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML)
    min_allowed = 10 if api_type == API_TYPE_JSON else 60
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
    except Exception as err:
        _LOGGER.error("Failed to connect to SYR Connect API: %s", err)
        raise ConfigEntryNotReady(f"Unable to connect to SYR Connect: {err}") from err

    entry.runtime_data = coordinator

    # Register listener for options changes (scan_interval updates)
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("SYR Connect integration setup completed")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading SYR Connect integration")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        _LOGGER.info("SYR Connect integration unloaded successfully")
    else:
        _LOGGER.warning("Failed to unload SYR Connect integration")

    return unload_ok


async def async_options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update (scan_interval changes).

    This listener is triggered when the user changes integration options
    through the Options Flow (e.g., updates the scan interval).
    """
    old_scan_interval = entry.runtime_data.update_interval.total_seconds()
    # When checking for option updates, fall back to the per-API default
    # so that JSON entries without explicit options use the JSON default.
    new_scan_interval = get_default_scan_interval_for_entry(entry)

    if old_scan_interval != new_scan_interval:
        _LOGGER.info(
            "Scan interval updated from %d to %d seconds, reloading coordinator",
            int(old_scan_interval),
            new_scan_interval,
        )
        # Update coordinator update interval
        entry.runtime_data.update_interval = timedelta(seconds=new_scan_interval)
        # Request refresh with new interval
        await entry.runtime_data.async_request_refresh()
    else:
        _LOGGER.debug("Options updated but scan interval unchanged")


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when critical settings change (credentials via reauth).

    This is called when the user reconfigures or reauthenticates the integration.
    """
    _LOGGER.info("Reloading SYR Connect integration due to configuration change")
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_migrate_legacy_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate a legacy config entry to the new format.

    Legacy entries (created before menu-based flow) don't have:
    - CONF_API_TYPE field
    - API type prefix in unique_id

    This function:
    1. Adds CONF_API_TYPE (defaults to XML for backward compatibility)
    2. Updates unique_id to include API type prefix
    """
    from .const import CONF_API_TYPE

    username = entry.data.get(CONF_USERNAME)
    if not username:
        _LOGGER.warning(
            "Cannot migrate entry '%s': Missing username",
            entry.title
        )
        return

    # Update data with API_TYPE_XML (legacy entries always used XML API)
    new_data = {**entry.data, CONF_API_TYPE: API_TYPE_XML}

    # Update unique_id to include API type prefix
    new_unique_id = f"{API_TYPE_XML}_{username}"

    _LOGGER.info(
        "Migrating entry '%s': Adding API type '%s', updating unique_id from '%s' to '%s'",
        entry.title,
        API_TYPE_XML,
        entry.unique_id,
        new_unique_id
    )

    # Update config entry with new data and unique_id
    hass.config_entries.async_update_entry(
        entry,
        data=new_data,
        unique_id=new_unique_id
    )
