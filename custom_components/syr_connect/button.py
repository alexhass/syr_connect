"""Button platform for SYR Connect.

This module implements ButtonEntity objects for SYR Connect devices.

Reset buttons (setALA, setNOT, setWRN) only trigger when the device
reports an active code. The following values are treated as "no alarm"
and will suppress the reset command (case-insensitive):

    "", "0", "00", "ff", "a0x0000", "255"

For setALA, both the alarm field and the reset command come from the model
signature of the library (`alarm_status_key`, `alarm_reset_command`):

    alarm_style_alm: True  → field = ALM  (getALM / setALM / clrALM)
    alarm_style_alm: False → field = ALA  (getALA / setALA / clrALA)

    alarm_clear_via_set: True  → send setALA/setALM with value "FF"
    alarm_clear_via_set: False → send clrALA/clrALM (the JSON API via /clr/)

setNOT and setWRN send "FF" (XML API) or 255 (JSON API) via the standard set
command.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any, override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aiosyrconnect import SyrConnectError, SyrConnectJsonAPI, SyrConnectStatus
from .const import _SYR_CONNECT_SENSOR_ALA_CODES_NO_ALARM, DOMAIN
from .coordinator import SyrConnectConfigEntry, SyrConnectDataUpdateCoordinator
from .data import SyrConnectDevice
from .entity import SyrConnectEntity, async_add_device_entities
from .helpers.device import get_device_model
from .helpers.profile import get_model_supported_keys
from .helpers.registry import find_entity_id, registry_cleanup
from .models import SyrConnectModel

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the API
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class _SyrConnectButtonPress:
    """The pressed button and the device it belongs to, for a press handler."""

    command: str
    coordinator: SyrConnectDataUpdateCoordinator
    device_id: str
    device_name: str
    model: SyrConnectModel
    status: SyrConnectStatus


@dataclass(frozen=True, kw_only=True)
class SyrConnectButtonEntityDescription(ButtonEntityDescription):
    """Describes a SYR Connect button; `key` is the command (e.g. "setSIR")."""

    # Sends the command of the button; raises ServiceValidationError if the device
    # state does not allow it
    press_fn: Callable[[_SyrConnectButtonPress], Awaitable[None]]


# --- Press handlers -------------------------------------------------------------
# The `press_fn` of a button description. Each handler gets the pressed button with
# the status of its device and sends the command.


async def _async_press_sir(press: _SyrConnectButtonPress) -> None:
    """Manual regeneration (setSIR): the value follows the format of getSIR.

    Values:
    - getSIR False or "false": "true"
    - Any other getSIR (e.g. "1", 1): 0
    """
    raw_sir = press.status.get("getSIR")
    value_sir: int | str
    if raw_sir is False or str(raw_sir).strip().lower() == "false":
        value_sir = "true"
    else:
        value_sir = 0
    await press.coordinator.async_set_device_value(
        press.device_id, press.command, value_sir
    )


def _dex_value(typ: Any) -> int | str:
    """Return the value that starts the microleakage test (setDEX), by device type (getTYP).

    Values:
    - getTYP below 100: 1
    - getTYP 100 or more, absent or not numeric: "true"
    """
    try:
        return 1 if int(typ) < 100 else "true"
    except ValueError, TypeError:
        return "true"


async def _async_press_dex(press: _SyrConnectButtonPress) -> None:
    """Microleakage test (setDEX): start it unless one is running (getDSV 1)."""
    if str(press.status.get("getDSV")).strip() == "1":
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="microleakage_test_running",
            translation_placeholders={"device": press.device_name},
        )
    await press.coordinator.async_set_device_value(
        press.device_id, press.command, _dex_value(press.status.get("getTYP"))
    )


async def _async_press_flush(press: _SyrConnectButtonPress) -> None:
    """Manual flushing of a hygiene module line (setMFC, setMFW): the command has no value."""
    await press.coordinator.async_set_device_value(press.device_id, press.command, "")


def _has_active_code(press: _SyrConnectButtonPress) -> bool:
    """Return True if a reset button (setALA, setNOT, setWRN) has an active code to reset."""
    return _is_active_code(press.status.get(_reset_get_key(press.command, press.model)))


async def _async_press_ala(press: _SyrConnectButtonPress) -> None:
    """Alarm reset (setALA): field and method follow the model, see the module docstring."""
    if not _has_active_code(press):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_alarm_to_reset",
            translation_placeholders={"device": press.device_name},
        )
    command, value = press.model.alarm_reset_command
    await press.coordinator.async_set_device_value(press.device_id, command, value)


async def _async_press_not_wrn(press: _SyrConnectButtonPress) -> None:
    """Notification or warning reset (setNOT, setWRN): send the "nothing active" code.

    Values:
    - JSON API: 255, sent as /set/not/255 or /set/wrn/255
    - XML API: "FF"
    """
    if not _has_active_code(press):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=(
                "no_notification_to_reset"
                if press.command == "setNOT"
                else "no_warning_to_reset"
            ),
            translation_placeholders={"device": press.device_name},
        )
    reset_value: int | str = (
        255 if isinstance(press.coordinator.api, SyrConnectJsonAPI) else "FF"
    )
    await press.coordinator.async_set_device_value(
        press.device_id, press.command, reset_value
    )


# Descriptions of all buttons, in the order they are created
_SYR_CONNECT_BUTTON_TYPES: tuple[SyrConnectButtonEntityDescription, ...] = (
    SyrConnectButtonEntityDescription(
        key="setSIR",  # Trigger manual regeneration
        press_fn=_async_press_sir,
    ),
    SyrConnectButtonEntityDescription(
        key="setALA",  # Reset alarm
        press_fn=_async_press_ala,
    ),
    SyrConnectButtonEntityDescription(
        key="setNOT",  # Reset notification
        press_fn=_async_press_not_wrn,
    ),
    SyrConnectButtonEntityDescription(
        key="setWRN",  # Reset warning
        press_fn=_async_press_not_wrn,
    ),
    SyrConnectButtonEntityDescription(
        key="setDEX",  # Start microleakage test
        press_fn=_async_press_dex,
    ),
    SyrConnectButtonEntityDescription(
        key="setMFC",  # Start a manual flushing of the cold water line (hygiene module)
        press_fn=_async_press_flush,
    ),
    SyrConnectButtonEntityDescription(
        key="setMFW",  # Start a manual flushing of the hot water line (hygiene module)
        press_fn=_async_press_flush,
    ),
)

# Commands without a read key of their own: command -> status key that tells the device
# has the function. A hygiene module reports no getMFC/getMFW; the stagnation time of the
# line (getSCF, getSWF) shows that the line exists.
_SYR_CONNECT_BUTTON_PRESENCE_KEYS = {
    "setMFC": "getSCF",
    "setMFW": "getSWF",
}

_SYR_CONNECT_BUTTON_DESCRIPTIONS: dict[str, SyrConnectButtonEntityDescription] = {
    description.key: description for description in _SYR_CONNECT_BUTTON_TYPES
}

# Icons of the reset buttons while there is something to reset; otherwise the
# icons.json default is shown
_SYR_CONNECT_BUTTON_ACTIVE_ICONS = {
    "setALA": "mdi:alarm-light",
    "setNOT": "mdi:bell-ring",
    "setWRN": "mdi:alert",
}


def _is_active_code(raw: object) -> bool:
    """Return True if an alarm, notification or warning code is active.

    See the module docstring for the values that mean "nothing active".
    """
    return (
        raw is not None
        and str(raw).strip().upper() not in _SYR_CONNECT_SENSOR_ALA_CODES_NO_ALARM
    )


def _reset_get_key(command: str, model: SyrConnectModel) -> str:
    """Return the status key read by a reset button (setALA, setNOT, setWRN).

    For setALA the key depends on the model: getALM with alarm_style_alm, otherwise getALA.
    """
    if command == "setALA":
        return model.alarm_status_key
    return "get" + command[3:]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SyrConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SYR Connect buttons.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up SYR Connect buttons")
    coordinator = entry.runtime_data

    registry_cleanup(
        hass,
        coordinator.data,
        "button",
        allowed_keys=set(),
        entry_id=coordinator.entry_id,
    )

    async_add_device_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda device: _build_device_buttons(hass, coordinator, device),
    )


def _build_device_buttons(
    hass: HomeAssistant,
    coordinator: SyrConnectDataUpdateCoordinator,
    device: SyrConnectDevice,
) -> list[SyrConnectButton]:
    """Return the buttons of one device and remove the ones it no longer has."""
    entities: list[SyrConnectButton] = []
    device_id = device["id"]
    device_name = device["name"]
    status = device.get("status", {})

    created_commands: set[str] = set()

    model_info = get_device_model(device)

    # Only the buttons of the device file of the detected model; a model without
    # one has no buttons.
    supported_button_keys = get_model_supported_keys(model_info, "button", set())

    for description in _SYR_CONNECT_BUTTON_TYPES:
        command = description.key
        if command not in supported_button_keys:
            continue

        # Derive the corresponding "getXYZ" key from the command name
        # (e.g. 'setNOT' -> 'getNOT') and skip if it's not present
        # in the device status.
        # For setALA, the actual get-key depends on the model: devices with
        # alarm_style_alm use getALM; all others use getALA.
        if command == "setALA":
            get_key = _reset_get_key(command, model_info)
        elif command == "setDEX":
            # No getDEX read key exists; presence is indicated by getDSV
            # (microleakage test status), which exists on devices that support
            # microleakage tests (Trio DFR/LS, SafeTech+).
            # setDEX is JSON-only: skip on XML API.
            if not isinstance(coordinator.api, SyrConnectJsonAPI):
                continue
            get_key = "getDSV"
        else:
            get_key = _SYR_CONNECT_BUTTON_PRESENCE_KEYS.get(
                command, "get" + command[3:]
            )
        if get_key not in status:
            continue

        entities.append(
            SyrConnectButton(
                coordinator,
                device_id,
                device_name,
                command,
            )
        )
        created_commands.add(command)
        _LOGGER.debug("Adding button: %s (%s)", device_name, command)

    # Remove any previously-registered button that is no longer being created
    # for this device (e.g. a command whose get-key disappeared from the status).
    # These buttons are in the allowlist of the device file and therefore survive
    # the registry_cleanup; they must be removed individually here. A device
    # without a status (not fetched yet) is not passed here (async_add_device_entities).
    try:
        registry = er.async_get(hass)
        for description in _SYR_CONNECT_BUTTON_TYPES:
            command = description.key
            if command in created_commands:
                continue
            # Found by unique_id, so a renamed or "_2"-suffixed button is removed as well
            stale_entity_id = find_entity_id(
                registry, "button", coordinator.entry_id, device_id, command
            )
            if stale_entity_id is not None:
                _LOGGER.debug(
                    "Removing conditionally-skipped button from registry: %s",
                    stale_entity_id,
                )
                registry.async_remove(stale_entity_id)
    except Exception:
        _LOGGER.exception(
            "Failed to remove conditionally-skipped buttons for device %s",
            device_id,
        )
    return entities


class SyrConnectButton(SyrConnectEntity, ButtonEntity):
    """Representation of a SYR Connect button."""

    entity_description: SyrConnectButtonEntityDescription

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        command: str,
    ) -> None:
        """Initialize the button.

        Args:
            coordinator: Data update coordinator
            device_id: Device ID (serial number)
            device_name: Device display name
            command: Command to execute (e.g., 'setSIR')
        """
        super().__init__(coordinator, device_id, device_name, "button", command)

        self._command = command
        self.entity_description = _SYR_CONNECT_BUTTON_DESCRIPTIONS[command]

    @property
    @override
    def icon(self) -> str | None:
        """Return the icon of a reset button while there is something to reset.

        Otherwise the icon comes from icons.json.
        """
        active_icon = _SYR_CONNECT_BUTTON_ACTIVE_ICONS.get(self._command)
        if active_icon is None or self._device is None:
            return None
        status = self._status
        if _is_active_code(
            status.get(_reset_get_key(self._command, self.device_model))
        ):
            return active_icon
        return None

    @override
    async def async_press(self) -> None:
        """Press the button: send the command with the press handler of its description.

        Raises:
            ServiceValidationError: If the device state does not allow the command, e.g.
                no active code to reset or a microleakage test already running
            HomeAssistantError: If sending the command fails
        """
        _LOGGER.debug("Button pressed: %s (device: %s)", self._command, self._device_id)
        press = _SyrConnectButtonPress(
            command=self._command,
            coordinator=self.coordinator,
            device_id=self._device_id,
            device_name=self._device_name,
            model=self.device_model,
            status=self._status,
        )
        try:
            await self.entity_description.press_fn(press)
        except SyrConnectError as err:
            _LOGGER.error(
                "Failed to press %s on %s: %s", self._command, self._device_id, err
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="button_press_failed",
                translation_placeholders={
                    "device": self._device_name,
                    "entity": self._entity_name,
                },
            ) from err
