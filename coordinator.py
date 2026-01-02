"""Data update coordinator for SYR Connect."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
import aiohttp

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, CONF_SCAN_INTERVAL
from .api import SyrConnectAPI

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
            UpdateFailed: If API communication fails
        """
        try:
            # Login if not already logged in
            if not self.api.session_data:
                _LOGGER.debug("No active session, logging in...")
                await self.api.login()
            
            all_devices = []
            
            # Get devices from all projects
            for project in self.api.projects:
                project_id = project['id']
                
                # Get devices for this project
                devices = await self.api.get_devices(project_id)
                
                # Get status for each device
                for device in devices:
                    try:
                        # Use DCLG for API calls
                        dclg = device.get('dclg', device['id'])
                        status = await self.api.get_device_status(dclg)
                        device['status'] = status
                        all_devices.append(device)
                    except Exception as err:
                        _LOGGER.warning(
                            "Failed to get status for device %s: %s",
                            device['id'],
                            err
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
            ValueError: If coordinator data is not available
        """
        _LOGGER.debug("Setting device %s command %s to %s", device_id, command, value)
        try:
            if not self.data:
                _LOGGER.error("No coordinator data available")
                raise ValueError("Coordinator data not available")
            
            # Find the DCLG for this device_id (which is now SN)
            dclg = None
            for device in self.data.get('devices', []):
                if device['id'] == device_id:
                    dclg = device.get('dclg', device_id)
                    break
            
            if not dclg:
                _LOGGER.error("Could not find DCLG for device %s", device_id)
                return
            
            await self.api.set_device_status(dclg, command, value)
            await self.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set device value: %s", err, exc_info=True)
            raise
