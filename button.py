"""Button platform for SYR Connect."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SyrConnectDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SYR Connect buttons.
    
    Args:
        hass: Home Assistant instance
        entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up SYR Connect buttons")
    coordinator: SyrConnectDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    
    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for buttons")
        return
    
    for device in coordinator.data.get('devices', []):
        device_id = device['id']
        device_name = device['name']
        project_id = device['project_id']
        
        # Add action buttons based on the ioBroker adapter
        action_buttons = [
            ("setSIR", "Regenerate Now"),
            ("setSMR", "Multi Regenerate"),
            ("setRST", "Reset Device"),
        ]
        
        for command, name in action_buttons:
            entities.append(
                SyrConnectButton(
                    coordinator,
                    device_id,
                    device_name,
                    project_id,
                    command,
                    name,
                )
            )

    
    _LOGGER.debug("Adding %d button(s) total", len(entities))
    async_add_entities(entities)


class SyrConnectButton(CoordinatorEntity, ButtonEntity):
    """Representation of a SYR Connect button."""

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        project_id: str,
        command: str,
        button_name: str,
    ) -> None:
        """Initialize the button.
        
        Args:
            coordinator: Data update coordinator
            device_id: Device ID (serial number)
            device_name: Device display name
            project_id: Project ID
            command: Command to execute (e.g., 'setSIR')
            button_name: Display name for the button
        """
        super().__init__(coordinator)
        
        self._device_id = device_id
        self._device_name = device_name
        self._project_id = project_id
        self._command = command
        
        self._attr_name = f"{device_name} {button_name}"
        self._attr_unique_id = f"{device_id}_{command}"
        
        # Override the entity_id to use technical name (serial number) with domain prefix
        # This matches the sensor entity ID structure
        self.entity_id = f"button.{DOMAIN}_{device_id.lower()}_{command.lower()}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "SYR",
            "model": "Connect",
        }

    async def async_press(self) -> None:
        """Press the button.
        
        Sends the command to the device with value 1 to trigger the action.
        """
        _LOGGER.debug("Button pressed: %s (device: %s)", self._attr_name, self._device_id)
        # Send command with value 1 (trigger action)
        await self.coordinator.async_set_device_value(
            self._device_id, self._command, 1
        )

    @property
    def available(self) -> bool:
        """Return if entity is available.
        
        Returns:
            True if last coordinator update was successful
        """
        return self.coordinator.last_update_success
