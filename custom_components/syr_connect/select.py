"""Select platform for SYR Connect (regeneration time wrapper)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    _SYR_CONNECT_MODEL_SALT_CAPACITY,
    _SYR_CONNECT_SENSOR_ICONS,
    _SYR_CONNECT_SENSOR_UNITS,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import build_device_info, build_entity_id

_LOGGER = logging.getLogger(__name__)


def _build_time_options(step_minutes: int = 15) -> list[str]:
    """Build list of time strings (HH:MM) for a 24h day with given step."""
    opts: list[str] = []
    for h in range(24):
        m = 0
        while m < 60:
            opts.append(f"{h:02d}:{m:02d}")
            m += step_minutes
    return opts


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for SYR Connect."""
    _LOGGER.debug("Setting up SYR Connect select entities")
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data

    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for select platform")
        return

    entities: list[Any] = []
    for device in coordinator.data.get("devices", []):
        device_id = device.get("id")
        device_name = device.get("name", device_id)
        status = device.get("status", {})
        if "getRTH" not in status and "getRTM" not in status:
            continue
        entities.append(SyrConnectRegenerationSelect(coordinator, device_id, device_name))

    # Add numeric-controlled selects for salt amounts and regeneration interval
    for device in coordinator.data.get("devices", []):
        device_id = device.get("id")
        device_name = device.get("name", device_id)
        status = device.get("status", {})
        # Salt amount selects (max depends on device model)
        model = status.get("getCNA") or device.get("type") or ""
        max_capacity = int(_SYR_CONNECT_MODEL_SALT_CAPACITY.get(str(model).upper(), 25))
        for sv_key in ("getSV1", "getSV2", "getSV3"):
            sv_value = status.get(sv_key)
            if sv_value is None or sv_value == "":
                continue
            try:
                if float(sv_value) == 0:
                    # Skip creating when zero reported (keeps parity with previous logic)
                    continue
            except (ValueError, TypeError):
                continue
            entities.append(
                SyrConnectNumericSelect(
                    coordinator, device_id, device_name, sv_key, 0, max_capacity, 1
                )
            )

        # Regeneration interval select (1..4 days)
        rpd_value = status.get("getRPD")
        if rpd_value is not None and rpd_value != "":
            try:
                if float(rpd_value) != 0:
                    entities.append(SyrConnectNumericSelect(coordinator, device_id, device_name, "getRPD", 1, 4, 1))
            except (ValueError, TypeError):
                pass

    if entities:
        _LOGGER.debug("Adding %d select(s) total", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No select entities to add")


class SyrConnectRegenerationSelect(CoordinatorEntity, SelectEntity):
    """Select entity exposing regeneration time as a choice list.

    This provides a Control-friendly domain for users who prefer the
    Controls/Steuerelemente view. Selecting an option sends the
    corresponding `setRTH`/`setRTM` commands via the coordinator.
    """

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name

        self._attr_has_entity_name = True
        self._attr_translation_key = "getrtime"
        self.entity_id = build_entity_id("select", device_id, "getrtime")
        self._attr_unique_id = f"{device_id}_getrtime_select"
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

        # Use same icon as the combined regeneration time sensor if available
        self._attr_icon = _SYR_CONNECT_SENSOR_ICONS.get("getRTIME")

        # Options: 15 minute steps by default
        self._options = _build_time_options(15)

        _LOGGER.debug(
            "Created SyrConnectRegenerationSelect object: device=%s name=%s unique_id=%s",
            self._device_id,
            self._device_name,
            self._attr_unique_id,
        )

    @property
    def options(self) -> list[str]:
        return self._options

    @property
    def current_option(self) -> str | None:
        """Return the currently configured regeneration time as HH:MM."""
        for dev in self.coordinator.data.get("devices", []):
            if dev.get("id") != self._device_id:
                continue
            status = dev.get("status", {})
            rth = status.get("getRTH")
            rtm = status.get("getRTM")
            if rth is None or rth == "" or rtm is None or rtm == "":
                return None
            try:
                h = int(float(rth)) % 24
                m = int(float(rtm)) % 60
            except Exception:
                return None
            return f"{h:02d}:{m:02d}"
        return None

    async def async_select_option(self, option: str) -> None:
        """Called when user selects a time option from the UI."""
        try:
            parts = option.split(":")
            h = int(parts[0])
            m = int(parts[1])
        except Exception as err:
            _LOGGER.error("Invalid time option selected for device %s: %s", self._device_id, err)
            return

        _LOGGER.debug("Setting regeneration time for device %s to %02d:%02d via select", self._device_id, h, m)

        coordinator: SyrConnectDataUpdateCoordinator = self.coordinator  # type: ignore[assignment]
        try:
            await coordinator.async_set_device_value(self._device_id, "setRTH", h)
            await coordinator.async_set_device_value(self._device_id, "setRTM", m)
            _LOGGER.debug("Requested setRTH/setRTM for device %s (h=%s m=%s)", self._device_id, h, m)
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to set regeneration time for device %s", self._device_id)

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device.get("available", True)
        return True


class SyrConnectNumericSelect(CoordinatorEntity, SelectEntity):
    """Select entity representing a numeric control.

    Options are stringified integers between min_value and max_value
    with the given step. Selecting an option sends `set<KEY>` via the coordinator.
    """

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
        min_value: int,
        max_value: int,
        step: int = 1,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name
        self._sensor_key = sensor_key

        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_key.lower()
        self.entity_id = build_entity_id("select", device_id, sensor_key)
        self._attr_unique_id = f"{device_id}_{sensor_key}_select"
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)
        # Icon mapping if present
        self._attr_icon = _SYR_CONNECT_SENSOR_ICONS.get(sensor_key)

        # Determine unit label (if available) and build options (append unit for readability)
        unit_label = None
        unit = _SYR_CONNECT_SENSOR_UNITS.get(self._sensor_key)
        if unit is not None:
            try:
                unit_label = str(unit)
            except Exception:
                unit_label = None

        opts: list[str] = []
        v = min_value
        while v <= max_value:
            if unit_label:
                opts.append(f"{int(v)} {unit_label}")
            else:
                opts.append(str(int(v)))
            v += step
        self._options = opts

        _LOGGER.debug(
            "Created SyrConnectNumericSelect object: device=%s key=%s unique_id=%s",
            self._device_id,
            self._sensor_key,
            self._attr_unique_id,
        )

    @property
    def options(self) -> list[str]:
        return self._options

    @property
    def current_option(self) -> str | None:
        for dev in self.coordinator.data.get("devices", []):
            if dev.get("id") != self._device_id:
                continue
            status = dev.get("status", {})
            val = status.get(self._sensor_key)
            if val is None or val == "":
                return None
            try:
                num = int(float(val))
                # Return the option that starts with the numeric value (preserves unit if present)
                for opt in self._options:
                    if opt.startswith(f"{num}"):
                        return opt
                return str(num)
            except Exception:
                return None
        return None

    async def async_select_option(self, option: str) -> None:
        try:
            # Option may include a unit suffix (e.g., '2 days'), so parse first token
            token = str(option).split()[0]
            val = int(token)
        except Exception as err:
            _LOGGER.error("Invalid option for %s: %s", self._sensor_key, err)
            return

        coordinator: SyrConnectDataUpdateCoordinator = self.coordinator  # type: ignore[assignment]
        # key for setting: remove leading 'get' and prefix with 'set'
        set_key = f"set{self._sensor_key[3:]}"
        try:
            await coordinator.async_set_device_value(self._device_id, set_key, val)
            _LOGGER.debug("Requested %s for device %s (value=%s)", set_key, self._device_id, val)
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to set %s for device %s", set_key, self._device_id)

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device.get("available", True)
        return True
