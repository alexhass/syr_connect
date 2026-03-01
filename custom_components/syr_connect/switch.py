"""Switch platform for per-device JSON API toggle."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import _SYR_CONNECT_DEVICE_SETTINGS, _SYR_CONNECT_DEVICE_USE_JSON_API
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import build_device_info, build_entity_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up per-device JSON API switches for SYR Connect."""
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data

    entities: list[SyrConnectJsonAPISwitch] = []

    if not coordinator.data:
        _LOGGER.debug("No coordinator data available for switches")
        return

    device_settings = entry.options.get(_SYR_CONNECT_DEVICE_SETTINGS, {}) if entry and entry.options else {}

    for device in coordinator.data.get('devices', []):
        if not isinstance(device, dict):
            continue
        # Only create a switch if device supports local JSON API (has base_path)
        if not device.get('base_path'):
            continue

        device_id = str(device.get('id'))
        # Determine current value: persistent option -> in-memory -> default False
        current = False
        if device_settings and device_settings.get(device_id):
            current = bool(device_settings.get(device_id, {}).get(_SYR_CONNECT_DEVICE_USE_JSON_API, False))
        elif device.get(_SYR_CONNECT_DEVICE_USE_JSON_API) is not None:
            current = bool(device.get(_SYR_CONNECT_DEVICE_USE_JSON_API))

        entities.append(
            SyrConnectJsonAPISwitch(
                coordinator,
                device_id,
                str(device.get('name') or device_id),
                current,
            )
        )

    async_add_entities(entities)


class SyrConnectJsonAPISwitch(CoordinatorEntity, SwitchEntity):
    """Switch to toggle local JSON API usage for a device."""

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        initial: bool = False,
    ) -> None:
        super().__init__(coordinator)

        self._device_id = device_id
        self._device_name = device_name
        self._is_on = initial

        self._attr_unique_id = f"{device_id}_use_local_json_api"
        self._attr_has_entity_name = True
        self._attr_translation_key = _SYR_CONNECT_DEVICE_USE_JSON_API
        # Mark as configuration entity so it appears in the device's config section
        self._attr_entity_category = EntityCategory.CONFIG

        # Override entity id for stable names
        self.entity_id = build_entity_id("switch", device_id, _SYR_CONNECT_DEVICE_USE_JSON_API)

        # attach device info
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

    @property
    def is_on(self) -> bool:
        return bool(self._is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_enabled(False)

    async def _set_enabled(self, value: bool) -> None:
        """Persist the per-device option in the config entry options."""
        try:
            entry = getattr(self.coordinator, "config_entry", None)
            if not entry:
                # fallback to in-memory only
                self._is_on = value
                self.async_write_ha_state()
                return

            options = dict(entry.options) if entry and entry.options else {}
            device_settings = options.get(_SYR_CONNECT_DEVICE_SETTINGS, {})
            dev_opts = device_settings.get(self._device_id, {})
            dev_opts[_SYR_CONNECT_DEVICE_USE_JSON_API] = bool(value)
            device_settings[self._device_id] = dev_opts
            options[_SYR_CONNECT_DEVICE_SETTINGS] = device_settings

            # Persist options
            # Use the entity's `hass` reference; `ConfigEntry` objects don't have `hass`
            self.hass.config_entries.async_update_entry(entry, options=options)

            # Update in-memory and trigger coordinator refresh to pick up change
            self._is_on = bool(value)
            # Also update coordinator device dict for immediate behaviour
            for dev in self.coordinator.data.get('devices', []):
                if dev.get('id') == self._device_id:
                    dev[_SYR_CONNECT_DEVICE_USE_JSON_API] = bool(value)
                    break

            try:
                await self.coordinator.async_request_refresh()
            except Exception:
                _LOGGER.debug("Failed to request coordinator refresh after toggling device JSON API")

            self.async_write_ha_state()
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to persist device JSON API setting for %s", self._device_id)
