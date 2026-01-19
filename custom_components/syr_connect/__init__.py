"""The SYR Connect integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import _SYR_CONNECT_SCAN_INTERVAL_CONF, _SYR_CONNECT_SCAN_INTERVAL_DEFAULT
from .coordinator import SyrConnectDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.BUTTON, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SYR Connect from a config entry."""
    _LOGGER.info("Setting up SYR Connect integration for user: %s", entry.data[CONF_USERNAME])

    session = async_get_clientsession(hass)

    # Get scan interval from options, fall back to default
    scan_interval = entry.options.get(_SYR_CONNECT_SCAN_INTERVAL_CONF, _SYR_CONNECT_SCAN_INTERVAL_DEFAULT)

    coordinator = SyrConnectDataUpdateCoordinator(
        hass,
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        scan_interval,
    )

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
    new_scan_interval = entry.options.get(_SYR_CONNECT_SCAN_INTERVAL_CONF, _SYR_CONNECT_SCAN_INTERVAL_DEFAULT)

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
