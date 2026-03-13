"""Button platform for SYR Connect.

This module implements `ButtonEntity` objects for SYR Connect devices.

Reset buttons (`setALA`, `setNOT`, `setWRN`) have special behavior: a
reset is only performed when the device reports an active code. Values
that represent "no code" include an empty string (`""`), the hex code
`"FF"` (case-insensitive), or the numeric value `255`. When no code is
present, the integration will not send a reset command.

Some device families require a model-specific reset payload: for
Safe-T+ / LEXplus10 variants the reset payload is an empty string;
other models expect the string `"FF"`.
"""
from __future__ import annotations

import logging
from typing import cast

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SyrConnectDataUpdateCoordinator
from .exceptions import SyrConnectError
from .helpers import build_device_info, build_entity_id
from .models import detect_model

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the API
PARALLEL_UPDATES = 1


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
    coordinator = cast(SyrConnectDataUpdateCoordinator, entry.runtime_data)

    entities = []

    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for buttons")
        return

    for device in coordinator.data.get('devices', []):
        device_id = device['id']
        device_name = device['name']
        project_id = device['project_id']
        status = device.get('status', {})

        # Add action buttons
        action_buttons = [
            ("setSIR", "Regenerate Now"),
            ("setALA", "Reset alarm"),
            ("setNOT", "Reset notification"),
            ("setWRN", "Reset warning"),
        ]

        for command, name in action_buttons:
            # Derive the corresponding "getXXX" key from the command name
            # (e.g. 'setALA' -> 'getALA') and skip if it's not present
            # in the device status.
            get_key = "get" + command[3:]
            if get_key not in status:
                continue

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
            _LOGGER.debug("Added button: %s (%s)", device_name, command)

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

        Reset buttons (`setALA`, `setNOT`, `setWRN`) perform additional
        validation before triggering a reset: they check the device's
        reported `getXXX` value and only send a model-appropriate reset
        payload when a code is present.

        Raises:
            HomeAssistantError: If the button press fails
        """
        # Avoid accessing possibly unset internal name attribute; use translation key or unique id
        button_id = getattr(self, "_attr_translation_key", None) or getattr(self, "_attr_unique_id", None)
        _LOGGER.debug("Button pressed: %s (device: %s)", button_id, self._device_id)

        coordinator = cast(SyrConnectDataUpdateCoordinator, self.coordinator)
        try:
            # Handle setSIR explicitly: only send when the setSIR button is pressed.
            if self._command == "setSIR":
                await coordinator.async_set_device_value(self._device_id, self._command, 0)
                return

            # Reset buttons (setALA, setNOT, setWRN) should send 255 when the
            # corresponding getXXX value is neither "FF" nor empty.
            if self._command in ("setALA", "setNOT", "setWRN"):
                # Determine corresponding get key
                if self._command == "setALA":
                    get_key = "getALA"
                elif self._command == "setNOT":
                    get_key = "getNOT"
                else:
                    get_key = "getWRN"

                # Find the device's status dictionary in the coordinator
                # payload. `coordinator.data['devices']` is expected to be
                # a list of device dictionaries; locate the entry with the
                # matching `id` and read its `status` sub-dictionary.
                status = None
                for device in coordinator.data.get("devices", []):
                    if device["id"] == self._device_id:
                        status = device.get("status", {})
                        break

                # Read the raw reported value for the corresponding get key
                # (e.g. `getALA`, `getNOT`, `getWRN`). `raw` may be `None`, a
                # string, or a numeric type depending on the backend.
                raw = None
                if status is not None:
                    raw = status.get(get_key)

                # Explicit rules for "no code" (no reset required):
                # - raw is None (no reported value)
                # - raw is an empty string ("")
                # - raw equals "FF" (case-insensitive)
                # - raw equals numeric 255
                #
                # Use an explicit None check so that other falsy values like
                # 0 are not treated as empty.
                if raw is None or str(raw).strip().lower() in ("", "ff", "255"):
                    raise HomeAssistantError(
                        f"No reset required for {get_key} on {self._device_id}"
                    )

                # For safetplus and all lex10 models we reset by sending
                # an empty string; for other models send "FF" (255).
                try:
                    model = detect_model(status or {}).get("name")
                except (ValueError, KeyError, AttributeError, TypeError) as err:
                    _LOGGER.debug("Failed to detect model for alarm reset: %s", err)
                    model = None

                send_value: str
                if isinstance(model, str) and model.lower() in (
                    "safetplus",
                    "lexplus10",
                    "lexplus10s",
                    "lexplus10sl",
                ):
                    send_value = ""
                else:
                    send_value = "FF"

                await coordinator.async_set_device_value(self._device_id, self._command, send_value)
                return

            # Default: do nothing for commands we don't explicitly handle.
            return
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            raise HomeAssistantError(f"Failed to press button: {err}") from err

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
