"""Switch platform for SYR Connect integration."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    _SYR_CONNECT_SENSOR_CONFIG,
    _SYR_CONNECT_SENSOR_ICON,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import build_entity_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities for getBUZ."""
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data
    entities = []
    devices = coordinator.data.get("devices", [])
    _LOGGER.debug(f"Found {len(devices)} devices in coordinator data.")
    for device in devices:
        device_id = device.get("id")
        device_name = device.get("name", device_id)
        status = device.get("status", {})
        _LOGGER.debug(f"Checking device: id={device_id}, name={device_name}, status_keys={list(status.keys())}")
        if "getBUZ" in status:
            _LOGGER.debug(f"getBUZ found in status for device {device_id}. Creating SyrConnectBuzSwitch.")
            try:
                entity = SyrConnectBuzSwitch(
                    coordinator,
                    device_id,
                    device_name,
                    "getBUZ",
                )
                entities.append(entity)
            except Exception as e:
                _LOGGER.error(f"Failed to instantiate SyrConnectBuzSwitch for device {device_id}: {e}")
        else:
            _LOGGER.debug(f"getBUZ not found in status for device {device_id}.")
    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No getBUZ switch entities found for any device.")


class SyrConnectBuzSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for getBUZ (buzzer on/off)."""

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
    ) -> None:
        """Initialize the switch."""
        _LOGGER.debug(f"Initializing SyrConnectBuzSwitch: device_id={device_id}, name={device_name}, sensor_key={sensor_key}")
        super().__init__(coordinator)

        self._device_id = device_id
        self._device_name = device_name
        self._sensor_key = sensor_key

        # Set unique ID and translation platform
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_key.lower()

        # Override the entity_id to use technical name (serial number) with domain prefix
        self.entity_id = build_entity_id("switch", device_id, sensor_key)
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get(sensor_key)

        # Set entity category if getBUZ is a config entity
        if sensor_key in _SYR_CONNECT_SENSOR_CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool | None:
        """Return True if buzzer is on."""
        device = next((d for d in self.coordinator.data.get("devices", []) if d["id"] == self._device_id), None)
        if not device:
            return None
        status = device.get("status", {})
        value = status.get("getBUZ")
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "on", "yes")
        if isinstance(value, int | float):
            return int(value) != 0
        return None

    async def async_turn_on(self, **kwargs):
        """Turn the buzzer on."""
        await self._set_buz(True)

    async def async_turn_off(self, **kwargs):
        """Turn the buzzer off."""
        await self._set_buz(False)

    async def _set_buz(self, state: bool):
        """Set the buzzer state via API."""
        value = True if state else False
        try:
            await self.coordinator.api.set_device_status(self._device_id, "BUZ", value)
        except Exception as err:
            _LOGGER.error("Failed to set getBUZ for device %s: %s", self._device_id, err)
        await self.coordinator.async_request_refresh()
