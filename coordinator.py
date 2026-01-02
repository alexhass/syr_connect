"""Data update coordinator for SYR Connect."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
import aiohttp

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, CONF_SCAN_INTERVAL
from .api import SyrConnectAPI
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
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
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
        
        self.api = SyrConnectAPI(session, username, password)
        self._username = username

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API.
        
        Returns:
            Dictionary containing devices and projects data
            
        Raises:
            ConfigEntryAuthFailed: If authentication fails
            UpdateFailed: If API communication fails
        """
        try:
            # Login if not already logged in
            if not self.api.session_data:
                _LOGGER.debug("No active session, logging in...")
                try:
                    await self.api.login()
                except Exception as err:
                    _LOGGER.error("Login failed: %s", err)
                    # Check if it's an authentication error
                    if "login" in str(err).lower() or "auth" in str(err).lower():
                        raise ConfigEntryAuthFailed(
                            "Authentication failed. Please reconfigure the integration."
                        ) from err
                    raise
            
            all_devices = []
            
            # Get devices from all projects
            for project in self.api.projects:
                project_id = project['id']
                _LOGGER.debug("Getting devices for project: %s (%s)", project['name'], project_id)
                
                # Get devices for this project
                devices = await self.api.get_devices(project_id)
                _LOGGER.debug("Found %d device(s) in project %s", len(devices), project['name'])
                
                # Get status for each device
                for device in devices:
                    try:
                        # Use DCLG for API calls
                        dclg = device.get('dclg', device['id'])
                        status = await self.api.get_device_status(dclg)
                        device['status'] = status
                        device['available'] = True
                        all_devices.append(device)
                        
                        # Delete offline issue if device is back online
                        delete_issue(self.hass, f"device_offline_{device['id']}")
                        
                    except Exception as err:
                        _LOGGER.warning(
                            "Failed to get status for device %s: %s",
                            device['id'],
                            err
                        )
                        # Mark device as unavailable but still add it
                        device['status'] = {}
                        device['available'] = False
                        all_devices.append(device)
                        
                        # Create repair issue for offline device
                        create_issue(
                            self.hass,
                            f"device_offline_{device['id']}",
                            "device_offline",
                            translation_placeholders={
                                "device_name": device.get('cna', device['id']),
                            },
                        )
            
            _LOGGER.debug("Update cycle completed: %d device(s) total", len(all_devices))
            return {
                'devices': all_devices,
                'projects': self.api.projects,
            }
            
        except Exception as err:
            _LOGGER.error("Update failed: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

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
        
        await self.api.set_device_status(dclg, command, value)
        await self.async_request_refresh()
