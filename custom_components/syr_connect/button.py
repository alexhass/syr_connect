"""Button platform for SYR Connect.

This module implements ButtonEntity objects for SYR Connect devices.

Reset buttons (setALA, setNOT, setWRN) only trigger when the device
reports an active code. The following values are treated as "no alarm"
and will suppress the reset command (case-insensitive):

    "", "0", "00", "0000", "ff", "a0x0000", "255"

For setALA, both the alarm field and the reset method depend on the
model signature:

    alarm_style_alm: True  → field = ALM  (getALM / setALM / clrALM)
    alarm_style_alm: False → field = ALA  (getALA / setALA / clrALA)

    alarm_clear_via_set: True  → send setALA/setALM with value "FF"
    alarm_clear_via_set: False → call dedicated clrALA/clrALM endpoint

setNOT and setWRN always send "FF" via the standard set command.
"""
from __future__ import annotations

import logging
from typing import cast

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api_json import SyrConnectJsonAPI
from .const import (
    _SYR_CONNECT_BUTTON_KNOWN_KEYS,
    _SYR_CONNECT_SENSOR_ALA_CODES_NO_ALARM,
    _SYR_CONNECT_SENSOR_EXCLUDED,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .exceptions import SyrConnectError
from .helpers import build_device_info, build_entity_id, registry_cleanup
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

    registry_cleanup(
        hass, coordinator.data, "button",
        allowed_keys=_SYR_CONNECT_BUTTON_KNOWN_KEYS - _SYR_CONNECT_SENSOR_EXCLUDED,
    )

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

        created_commands: set[str] = set()

        model_info = detect_model(status)

        for command, _name in action_buttons:
            # Derive the corresponding "getXYZ" key from the command name
            # (e.g. 'setNOT' -> 'getNOT') and skip if it's not present
            # in the device status.
            # For setALA, the actual get-key depends on the model: devices with
            # alarm_style_alm use getALM; all others use getALA.
            if command == "setALA":
                alarm_field = "alm" if model_info.get("alarm_style_alm") else "ala"
                get_key = f"get{alarm_field.upper()}"
            else:
                get_key = "get" + command[3:]
            if get_key not in status:
                continue

            # setSIR (manual regeneration trigger) is only meaningful for
            # softener models that actually support scheduled regeneration.
            # Workaround for https://github.com/alexhass/syr_connect/issues/24
            if command == "setSIR" and model_info.get("maximum_regeneration_interval") is None:
                continue

            entities.append(
                SyrConnectButton(
                    coordinator,
                    device_id,
                    device_name,
                    project_id,
                    command,
                )
            )
            created_commands.add(command)
            _LOGGER.debug("Adding button: %s (%s)", device_name, command)

        # Remove any previously-registered button that is no longer being created
        # for this device (e.g. a command whose get-key disappeared from the status).
        # These buttons are in _SYR_CONNECT_BUTTON_KNOWN_KEYS and therefore survive
        # the global registry_cleanup above; they must be removed individually here.
        try:
            registry = er.async_get(hass)
            prefix = f"button.syr_connect_{device_id.lower()}_"
            for reg_entry in list(registry.entities.values()):
                if not reg_entry.entity_id.startswith(prefix):
                    continue
                key = reg_entry.entity_id[len(prefix):]
                # Reconstruct the original command (e.g. "setsir" -> "setSIR")
                # by checking against all known commands case-insensitively.
                for known_cmd in action_buttons:
                    if known_cmd[0].lower() == key and known_cmd[0] not in created_commands:
                        _LOGGER.debug(
                            "Removing conditionally-skipped button from registry: %s",
                            reg_entry.entity_id,
                        )
                        registry.async_remove(reg_entry.entity_id)
                        break
        except Exception:
            _LOGGER.exception(
                "Failed to remove conditionally-skipped buttons for device %s", device_id
            )

    if entities:
        _LOGGER.debug("Adding %d button(s) total", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No button entities to add")


class SyrConnectButton(CoordinatorEntity, ButtonEntity):
    """Representation of a SYR Connect button."""

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        project_id: str,
        command: str,
    ) -> None:
        """Initialize the button.

        Args:
            coordinator: Data update coordinator
            device_id: Device ID (serial number)
            device_name: Device display name
            project_id: Project ID
            command: Command to execute (e.g., 'setSIR')
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

        Sends the command to the device to trigger the action.

        Reset buttons (setALA, setNOT, setWRN) perform additional validation
        before triggering a reset: they read the device's current getXYZ value
        and only proceed when an active code is present. See module docstring
        for the full list of "no alarm" sentinel values.

        For setALA, the alarm field (ALA vs ALM) and the reset method
        (set command vs dedicated clr endpoint) are determined from the
        model signature flags alarm_style_alm and alarm_clear_via_set.

        Raises:
            HomeAssistantError: If the button press fails or no reset is required
        """
        # Avoid accessing possibly unset internal name attribute; use translation key or unique id
        button_id = getattr(self, "_attr_translation_key", None) or getattr(self, "_attr_unique_id", None)
        _LOGGER.debug("Button pressed: %s (device: %s)", button_id, self._device_id)

        coordinator = cast(SyrConnectDataUpdateCoordinator, self.coordinator)
        try:
            # Handle setSIR: initiate regeneration with the appropriate value.
            # getSIR = 1 (integer/string) → send setSIR = 0 (integer).
            # getSIR = False / "false" → send setSIR = "true" (string, lowercase).
            if self._command == "setSIR":
                status = None
                for device in coordinator.data.get("devices", []):
                    if device["id"] == self._device_id:
                        status = device.get("status", {})
                        break
                raw_sir = None if status is None else status.get("getSIR")
                # Map the reported getSIR value to the correct setSIR payload.
                # - Boolean False (or the string "false") → send "true" (lowercase string).
                # - Anything else (e.g. "1", 1) → send 0.
                value_sir: int | str
                if raw_sir is False or str(raw_sir).strip().lower() == "false":
                    value_sir = "true"
                else:
                    value_sir = 0
                await coordinator.async_set_device_value(self._device_id, self._command, value_sir)
                return

            # Reset buttons (setALA, setNOT, setWRN): read the current alarm/notification/
            # warning value from the device status and only send a reset if an active code
            # is present. This avoids unnecessary API calls when nothing needs clearing.
            if self._command in ("setALA", "setNOT", "setWRN"):
                # Locate the device's status dictionary in the coordinator payload.
                # coordinator.data['devices'] is a list; find the entry by device id.
                status = None
                for device in coordinator.data.get("devices", []):
                    if device["id"] == self._device_id:
                        status = device.get("status", {})
                        break

                if self._command == "setALA":
                    # Resolve alarm field (ALA vs ALM) and clear method (set vs clr)
                    # from model signature flags:
                    #   alarm_style_alm: True  → field = ALM (uses getALM / setALM / clrALM)
                    #   alarm_style_alm: False → field = ALA (uses getALA / setALA / clrALA)
                    #   alarm_clear_via_set: True  → reset via setALA/setALM "FF"
                    #   alarm_clear_via_set: False → reset via dedicated clrALA/clrALM endpoint
                    try:
                        model_info = detect_model(status or {})
                    except (ValueError, KeyError, AttributeError, TypeError) as err:
                        _LOGGER.debug("Failed to detect model for alarm reset: %s", err)
                        model_info = {}

                    alarm_style_alm: bool = bool(model_info.get("alarm_style_alm"))
                    alarm_clear_via_set: bool = bool(model_info.get("alarm_clear_via_set"))
                    field = "alm" if alarm_style_alm else "ala"
                    get_key = f"get{field.upper()}"

                    # Read the current alarm value. raw may be None, a string, or a number
                    # depending on the device firmware.
                    raw = status.get(get_key) if status is not None else None
                    # Sentinel values that indicate no active alarm (see module docstring).
                    if raw is None or str(raw).strip().lower() in _SYR_CONNECT_SENSOR_ALA_CODES_NO_ALARM:
                        raise HomeAssistantError(
                            f"No reset required for {get_key} on {self._device_id}"
                        )

                    if alarm_clear_via_set:
                        # Device resets the alarm via a standard set command with value "FF".
                        set_cmd = f"set{field.upper()}"
                        await coordinator.async_set_device_value(self._device_id, set_cmd, "FF")
                    else:
                        # Active alarm confirmed above via getALA / getALM;
                        # send dedicated clear command (clrALA / clrALM).
                        await coordinator.async_clear_device_alarm(self._device_id, field)
                    return

                # setNOT / setWRN: determine the corresponding get key, check for an
                # active code, then send the appropriate reset value via the standard
                # set command.
                # - JSON API: integer 255 → URL path /set/not/255 or /set/wrn/255
                # - XML API: string "FF" → payload value
                if self._command == "setNOT":
                    get_key = "getNOT"
                else:
                    get_key = "getWRN"

                # raw may be None, a string, or a number depending on the device firmware.
                raw = None
                if status is not None:
                    raw = status.get(get_key)

                # Sentinel values that indicate no active notification / warning.
                if raw is None or str(raw).strip().lower() in _SYR_CONNECT_SENSOR_ALA_CODES_NO_ALARM:
                    raise HomeAssistantError(
                        f"No reset required for {get_key} on {self._device_id}"
                    )

                reset_value: int | str = 255 if isinstance(coordinator.api, SyrConnectJsonAPI) else "FF"
                await coordinator.async_set_device_value(self._device_id, self._command, reset_value)
                return

            # Default: no action for commands not explicitly handled above.
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
