"""Button platform for SYR Connect."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import build_device_info, build_entity_id

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
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data

    entities = []

    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for buttons")
        return

    for device in coordinator.data.get('devices', []):
        device_id = device['id']
        device_name = device['name']
        project_id = device['project_id']

        # Add action buttons
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

        self._attr_unique_id = f"{device_id}_{command}"
        # Use translation key for localized button names; let HA build the name
        self._attr_has_entity_name = True
        self._attr_translation_key = command.lower()

        # Override the entity_id to use technical name (serial number) with domain prefix
        # This matches the sensor entity ID structure
        self.entity_id = build_entity_id("button", device_id, command)

        # Build device info from coordinator data
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

    async def async_press(self) -> None:
        """Press the button.

        Sends the command to the device with value 0 to trigger the action.

        Raises:
            HomeAssistantError: If the button press fails
        """
        # Avoid accessing possibly unset internal name attribute; use translation key or unique id
        button_id = getattr(self, "_attr_translation_key", None) or getattr(self, "_attr_unique_id", None)
        _LOGGER.debug("Button pressed: %s (device: %s)", button_id, self._device_id)

        try:
            # Send value: 0 for `setSIR` (documentation: 0 = immediate), otherwise 1
            value = 0 if self._command == "setSIR" else 1
            await self.coordinator.async_set_device_value(
                self._device_id, self._command, value
            )
        except ValueError as err:
            raise HomeAssistantError(f"Failed to press button: {err}") from err
        except Exception as err:
            raise HomeAssistantError(f"Unexpected error pressing button: {err}") from err

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Returns:
            True if last coordinator update was successful and device is available
        """
        if not self.coordinator.last_update_success:
            return False

        # Check if the specific device is available
        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                return device.get('available', True)

        return True
