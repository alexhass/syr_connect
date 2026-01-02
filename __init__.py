"""The SYR Connect integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .coordinator import SyrConnectDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SYR Connect from a config entry."""
    _LOGGER.info("Setting up SYR Connect integration for user: %s", entry.data[CONF_USERNAME])
    hass.data.setdefault(DOMAIN, {})
    
    session = async_get_clientsession(hass)
    
    # Get scan interval from options, fall back to default
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    
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
    
    _LOGGER.info("SYR Connect integration setup completed")
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("SYR Connect integration setup completed")
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading SYR Connect integration")
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("SYR Connect integration unloaded successfully")
    else:
        _LOGGER.warning("Failed to unload SYR Connect integration")
    
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.info("Options updated, reloading integration")
    await hass.config_entries.async_reload(entry.entry_id)
