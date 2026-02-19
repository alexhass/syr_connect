"""Valve platform for SYR Connect (water shut-off valve)."""
from __future__ import annotations

import logging
import time

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import _SYR_CONNECT_SENSOR_ICON
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import (
    build_device_info,
    build_entity_id,
    build_set_ab_command,
    get_sensor_ab_value,
)

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the API
PARALLEL_UPDATES = 1


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

    entities: list[SyrConnectValve] = []
    for device in coordinator.data.get("devices", []):
        device_id = device.get("id")
        device_name = device.get("name", device_id)
        # Per-device status dictionary from the coordinator payload
        status = device.get("status", {})
        # Create valve entity when device exposes either getAB (control)
        # or getVLV (status)
        ab_value = status.get("getAB")
        vlv_value = status.get("getVLV")
        create = False
        # If `getAB` looks numeric and in the expected domain (1/2),
        # treat the device as a valve that can be controlled.
        try:
            if ab_value is not None and ab_value != "":
                if int(float(ab_value)) in (1, 2):
                    create = True
        except (ValueError, TypeError):
            create = False

        # If `getVLV` looks numeric and matches our known status codes
        # (10/11/20/21), also create a valve entity. We only create one
        # entity per device regardless of whether both sensors are
        # present; the entity will prefer `getVLV` for its reported
        # state and use `getAB` for control.
        try:
            if not create and vlv_value is not None and vlv_value != "":
                if int(float(vlv_value)) in (10, 11, 20, 21):
                    create = True
        except (ValueError, TypeError):
            create = False

        if create:
            entities.append(SyrConnectValve(coordinator, device_id, device_name))

    if entities:
        _LOGGER.debug("Adding %d valve(s) total", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No valve entities to add")


class SyrConnectValve(CoordinatorEntity, ValveEntity):
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
        sensor_key: str | None = None,
    ) -> None:
        """Initialize the valve entity.

        Args:
            coordinator: Data update coordinator
            device_id: Device ID (serial number)
            device_name: Device display name
            project_id: Project ID
            sensor_key: Sensor key (e.g., 'getSRE')
            device_class: Valve device class
        """
        super().__init__(coordinator)

        self._device_id = device_id
        self._device_name = device_name
        # support legacy callers that omit sensor_key
        self._sensor_key = sensor_key or "getAB"

        # Set unique ID and translation key
        self._attr_has_entity_name = True
        self._attr_translation_key = self._sensor_key.lower()
        self._attr_unique_id = f"{device_id}_{self._sensor_key}"

        # Keep a typed reference to the coordinator to access integration-specific helpers
        self._sc_coordinator: SyrConnectDataUpdateCoordinator = coordinator

        # Override the entity_id to use technical name (serial number) with domain prefix
        self.entity_id = build_entity_id("valve", device_id, self._sensor_key)

        # Build device info from coordinator data
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

        # Set icon if available
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get("getAB")
        self._base_icon = getattr(self, "_attr_icon", None)

        # Enable valve entities by default
        self._attr_entity_registry_enabled_default = True

        # Keep last seen low-level values for change detection/logging
        self._last_values: dict | None = None

        # Cache recent `setAB` requests because devices may take time
        # (approx. 60s) to reflect the change in the `getAB` field.
        # We use this cached value to update the GUI immediately when
        # `getVLV` is not present; `getVLV` remains authoritative.
        self._ab_cache_seconds = 60
        self._cached_ab: dict | None = None  # {'value': True|False, 'expires': float}

        # This integration does not report a continuous position value
        # (we expose opening/closing via discrete `getVLV` codes). Set
        # `reports_position` to False so Home Assistant will not expect
        # a numeric position attribute.
        self._attr_reports_position = False

        # Advertise supported actions (open and close) as a bitmask
        # using the ValveEntityFeature IntFlag. Home Assistant expects
        # an int/IntFlag here — not a list — so use the bitwise OR.
        self._attr_supported_features = (
            ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
        )

        # Device class: represent this entity as a water valve in the
        # Home Assistant UI.
        self._attr_device_class = ValveDeviceClass.WATER

    def _get_device(self) -> dict | None:
        """Return the device dict for this entity, or None if not present."""
        for dev in self.coordinator.data.get("devices", []):
            if dev.get("id") == self._device_id:
                return dev
        return None

    def _get_status(self) -> dict | None:
        """Return the status dict for this entity's device, or None.

        The coordinator stores a list of devices; this helper locates
        the current device by id and returns its `status` mapping.
        """
        dev = self._get_device()
        if not dev:
            return None
        return dev.get("status", {})

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes including raw API values.

        We expose the raw `getVLV` and `getAB` values as attributes so
        users and automations can inspect the low-level API payload.
        """
        status = self._get_status()
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
    def is_closed(self) -> bool | None:
        """Return True if valve is closed, False if open, None if unknown.

        Preference order:
        1. Use `getVLV` if it is reported (authoritative discrete state).
        2. Fall back to `getAB` control value (1=open, 2=closed).
        """
        status = self._get_status()
        if status is None:
            return None

        # If we've recently sent a `setAB` command, prefer the cached
        # value for a short window so the UI reflects the requested
        # state immediately. This intentionally overrides `getVLV`
        # during the cache window because some devices update `getVLV`
        # slowly even though the control command was accepted.
        now = time.time()
        if self._cached_ab is not None:
            if now < self._cached_ab.get("expires", 0):
                val = self._cached_ab.get("value")
                _LOGGER.debug(
                    "Valve %s using cached getAB=%s for UI (expires in %.fs)",
                    self._device_id,
                    val,
                    self._cached_ab.get("expires", 0) - now,
                )
                if val is True:
                    return True
                if val is False:
                    return False
            else:
                # Cache expired
                self._cached_ab = None

        # Prefer authoritative valve state from `getVLV` when available
        vlv = status.get("getVLV")
        if vlv is not None and vlv != "":
            try:
                ival = int(float(vlv))
                # Mapping:
                # 10 = closed, 11 = closing, 20 = open, 21 = opening
                if ival == 10:
                    return True
                else:
                    return False
            except (ValueError, TypeError):
                pass

        # Fallback to getAB control value (use helper to normalize)
        ab = get_sensor_ab_value(status)
        return ab

    @property
    def is_opening(self) -> bool | None:
        """Return True if valve is currently opening.

        This maps `getVLV == 21` to an opening state.
        """
        status = self._get_status()
        if status is None:
            return None
        vlv = status.get("getVLV")
        if vlv is None or vlv == "":
            return None
        try:
            return int(float(vlv)) == 21
        except (ValueError, TypeError):
            return None

    @property
    def is_closing(self) -> bool | None:
        """Return True if valve is currently closing.

        This maps `getVLV == 11` to a closing state.
        """
        status = self._get_status()
        if status is None:
            return None
        vlv = status.get("getVLV")
        if vlv is None or vlv == "":
            return None
        try:
            return int(float(vlv)) == 11
        except (ValueError, TypeError):
            return None

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device.get("available", True)
        return True

    async def async_open(self) -> None:
        """Open the valve (send `setAB` -> 1).

        The coordinator provides `async_set_device_value` which sends the
        command to the backend; any exceptions are wrapped as
        `HomeAssistantError` so callers receive a clear failure.
        """
        # Build the correct setAB command based on device representation
        set_key, set_val = build_set_ab_command(self._get_status() or {}, False)

        # Optimistically cache the requested boolean value (False = opened)
        self._cached_ab = {"value": False, "expires": time.time() + self._ab_cache_seconds}
        _LOGGER.debug(
            "Optimistically cached getAB=%s for %s seconds for %s",
            set_val,
            self._ab_cache_seconds,
            self._device_id,
        )
        try:
            # Immediately write state so the UI reflects the requested change
            try:
                self.async_write_ha_state()
            except Exception:
                pass

            # Send command to backend; await result but do not block UI update
            await self._sc_coordinator.async_set_device_value(self._device_id, set_key, set_val)
        except Exception as err:  # pragma: no cover - defensive
            # On failure, clear optimistic cache and restore state
            _LOGGER.exception("Failed to open valve %s", self._device_id)
            self._cached_ab = None
            try:
                self.async_write_ha_state()
            except Exception:
                pass
            raise HomeAssistantError(f"Failed to open valve {self._device_id}: {err}") from err

    async def async_close(self) -> None:
        """Close the valve (send `setAB` -> 2).

        See `async_open` for behavior and error handling.
        """
        # Build the correct setAB command based on device representation
        set_key, set_val = build_set_ab_command(self._get_status() or {}, True)

        # Optimistically cache the requested boolean value (True = closed)
        self._cached_ab = {"value": True, "expires": time.time() + self._ab_cache_seconds}
        _LOGGER.debug(
            "Optimistically cached getAB=%s for %s seconds for %s",
            set_val,
            self._ab_cache_seconds,
            self._device_id,
        )
        try:
            # Immediately write state so the UI reflects the requested change
            try:
                self.async_write_ha_state()
            except Exception:
                pass

            # Send command to backend; await result but do not block UI update
            await self._sc_coordinator.async_set_device_value(self._device_id, set_key, set_val)
        except Exception as err:  # pragma: no cover - defensive
            # On failure, clear optimistic cache and restore state
            _LOGGER.exception("Failed to close valve %s", self._device_id)
            self._cached_ab = None
            try:
                self.async_write_ha_state()
            except Exception:
                pass
            raise HomeAssistantError(f"Failed to close valve {self._device_id}: {err}") from err

    async def async_open_valve(self) -> None:
        """Async service entrypoint to open the valve."""
        await self.async_open()

    def open_valve(self) -> None:
        """Sync service entrypoint to open the valve (schedules async task)."""
        if self.hass is not None:
            self.hass.async_create_task(self.async_open())

    async def async_close_valve(self) -> None:
        """Async service entrypoint to close the valve."""
        await self.async_close()

    def close_valve(self) -> None:
        """Sync service entrypoint to close the valve (schedules async task)."""
        if self.hass is not None:
            self.hass.async_create_task(self.async_close())

    @property
    def icon(self) -> str | None:
        """Return a dynamic icon based on the valve state.

        If the valve is currently moving (opening/closing) show a
        generic valve icon; otherwise show open/closed icons.
        """
        opening = self.is_opening
        if opening is True:
            return "mdi:valve"
        closing = self.is_closing
        if closing is True:
            return "mdi:valve"

        # Prefer getAB/getVLV derived closed state for final display
        closed = self.is_closed
        if closed is None:
            return self._base_icon
        return "mdi:valve-closed" if closed else "mdi:valve-open"
