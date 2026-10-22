"""Valve platform for SYR Connect (water shut-off valve)."""

import logging
from typing import override

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SyrConnectDataUpdateCoordinator
from .entity import SyrConnectEntity
from .exceptions import SyrConnectError
from .helpers import (
    build_set_ab_command,
    get_model_supported_keys,
    get_sensor_ab_value,
    registry_cleanup,
)
from .models import detect_model

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the API
PARALLEL_UPDATES = 1

# Descriptions of all valves
_SYR_CONNECT_VALVE_TYPES: tuple[ValveEntityDescription, ...] = (
    ValveEntityDescription(
        key="getAB",  # Valve shutoff control / state
        device_class=ValveDeviceClass.WATER,
        # Opening/closing comes from the discrete getVLV codes, there is no position value
        reports_position=False,
    ),
)

_SYR_CONNECT_VALVE_DESCRIPTIONS: dict[str, ValveEntityDescription] = {
    description.key: description for description in _SYR_CONNECT_VALVE_TYPES
}

# Supported keys for the valve platform — used by registry_cleanup to remove stale entries.
_SYR_CONNECT_VALVE_SUPPORTED_KEYS = set(_SYR_CONNECT_VALVE_DESCRIPTIONS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up valve entities for SYR Connect."""
    # Discover and create valve entities for devices that expose
    # either a control sensor (`getAB`) or a status sensor (`getVLV`).
    # We perform light validation of the values to avoid creating
    # entities for non-numeric or unexpected sensor payloads.
    _LOGGER.debug("Setting up SYR Connect valve entities")
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data

    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for valve platform")
        return

    registry_cleanup(
        hass,
        coordinator.data,
        "valve",
        allowed_keys=_SYR_CONNECT_VALVE_SUPPORTED_KEYS,
        entry_id=coordinator.entry_id,
    )

    entities: list[SyrConnectValve] = []
    for device in coordinator.data.get("devices", []):
        device_id = device["id"]
        device_name = device["name"]
        # Per-device status dictionary from the coordinator payload
        status = device.get("status", {})
        # Create a valve entity only when the device exposes `getAB` (the
        # actual valve control key) AND the model's allowlist permits it.
        # `getVLV` is a read-only status sensor and is handled exclusively
        # by the sensor platform.
        supported_valve_keys = get_model_supported_keys(
            detect_model(status), "valve", _SYR_CONNECT_VALVE_SUPPORTED_KEYS
        )
        ab_value = status.get("getAB") if "getAB" in supported_valve_keys else None
        create = False
        # If `getAB` looks like a control value (numeric 1/2 or boolean),
        # treat the device as a valve that can be controlled.
        try:
            if ab_value is not None and ab_value != "":
                if (
                    # Native boolean from JSON
                    isinstance(ab_value, bool)
                    # Boolean-like strings
                    or (
                        isinstance(ab_value, str)
                        and ab_value.strip().lower() in ("true", "false")
                    )
                    # Numeric representation (1=open, 2=closed)
                    or int(float(ab_value)) in (1, 2)
                ):
                    create = True
        except ValueError, TypeError, OverflowError:
            create = False

        if create:
            entities.append(SyrConnectValve(coordinator, device_id, device_name))

    if entities:
        _LOGGER.debug("Adding %d valve(s) total", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No valve entities to add")


class SyrConnectValve(SyrConnectEntity, ValveEntity):
    """Representation of a SYR Connect valve (shut-off).

    The entity exposes `is_closed`, `is_opening` and `is_closing`
    properties that Home Assistant uses to determine the overall
    `state` (open/closed/opening/closing). `getVLV` is treated as the
    authoritative source for these discrete states; `getAB` is only a
    fallback used for cases where `getVLV` is not reported by the
    device.
    """

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the valve entity for the shut-off valve (getAB).

        Args:
            coordinator: Data update coordinator
            device_id: Device ID (serial number)
            device_name: Device display name
        """
        self._sensor_key = "getAB"
        super().__init__(coordinator, device_id, device_name, "valve", self._sensor_key)
        self.entity_description = _SYR_CONNECT_VALVE_DESCRIPTIONS[self._sensor_key]

        # Advertise supported actions (open and close) as a bitmask
        # using the ValveEntityFeature IntFlag. Home Assistant expects
        # an int/IntFlag here — not a list — so use the bitwise OR.
        self._attr_supported_features = (
            ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes including raw API values.

        We expose the raw `getVLV` and `getAB` values as attributes so
        users and automations can inspect the low-level API payload.
        """
        status = self._status
        if not status:
            return None
        attrs: dict[str, str] = {}
        vlv = status.get("getVLV")
        ab = status.get("getAB")
        if vlv is not None:
            attrs["getVLV"] = str(vlv)
        if ab is not None:
            attrs["getAB"] = str(ab)
        return attrs

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return True if valve is closed, False if open, None if unknown."""
        if self._device is None:
            return None
        status = self._status

        return get_sensor_ab_value(status)

    @property
    @override
    def is_opening(self) -> bool | None:
        """Return True if valve is currently opening.

        This maps `getVLV == 21` to an opening state.
        """
        if self._device is None:
            return None
        status = self._status
        vlv = status.get("getVLV")
        if vlv is None or vlv == "":
            return None
        try:
            return int(float(vlv)) == 21
        except ValueError, TypeError, OverflowError:
            return None

    @property
    @override
    def is_closing(self) -> bool | None:
        """Return True if valve is currently closing.

        This maps `getVLV == 11` to a closing state.
        """
        if self._device is None:
            return None
        status = self._status
        vlv = status.get("getVLV")
        if vlv is None or vlv == "":
            return None
        try:
            return int(float(vlv)) == 11
        except ValueError, TypeError, OverflowError:
            return None

    async def async_open(self) -> None:
        """Open the valve (send `setAB` -> open value)."""
        ab_cmd = build_set_ab_command(self._status, False)
        if ab_cmd is None:
            raise HomeAssistantError(
                f"Cannot open valve {self._device_id}: unknown getAB format"
            )
        set_key, set_val = ab_cmd

        try:
            # Send command to backend; prepend alarm-clear when an alarm is active.
            await self.coordinator.async_open_valve(self._device_id, set_key, set_val)
        except (SyrConnectError, ValueError, TypeError, KeyError, RuntimeError) as err:
            _LOGGER.error("Failed to open valve %s: %s", self._device_id, err)
            raise HomeAssistantError(
                f"Failed to open valve {self._device_id}: {err}"
            ) from err

    async def async_close(self) -> None:
        """Close the valve (send `setAB` -> close value).

        See `async_open` for behavior and error handling.
        """
        ab_cmd = build_set_ab_command(self._status, True)
        if ab_cmd is None:
            raise HomeAssistantError(
                f"Cannot close valve {self._device_id}: unknown getAB format"
            )
        set_key, set_val = ab_cmd

        try:
            await self.coordinator.async_set_device_value(
                self._device_id, set_key, set_val
            )
        except (SyrConnectError, ValueError, TypeError, KeyError, RuntimeError) as err:
            _LOGGER.error("Failed to close valve %s: %s", self._device_id, err)
            raise HomeAssistantError(
                f"Failed to close valve {self._device_id}: {err}"
            ) from err

    @override
    async def async_open_valve(self) -> None:
        """Async service entrypoint to open the valve."""
        await self.async_open()

    @override
    def open_valve(self) -> None:
        """Sync service entrypoint to open the valve (schedules async task)."""
        if self.hass is not None:
            self.hass.async_create_task(self.async_open())

    @override
    async def async_close_valve(self) -> None:
        """Async service entrypoint to close the valve."""
        await self.async_close()

    @override
    def close_valve(self) -> None:
        """Sync service entrypoint to close the valve (schedules async task)."""
        if self.hass is not None:
            self.hass.async_create_task(self.async_close())
