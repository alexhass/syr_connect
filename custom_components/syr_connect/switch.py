"""Switch platform for SYR Connect integration."""

import logging
from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    _SYR_CONNECT_SENSOR_CONFIG,
    _SYR_CONNECT_SENSOR_EXCLUDED,
    _SYR_CONNECT_SWITCH_KNOWN_KEYS,
    DOMAIN,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .entity import SyrConnectEntity
from .exceptions import SyrConnectError
from .helpers import (
    build_unique_id,
    get_model_known_keys,
    is_value_true,
    registry_cleanup,
)
from .models import detect_model

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up boolean switch entities (e.g. getBUZ, getDFI)."""
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data

    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for switch platform")
        return

    registry_cleanup(
        hass, coordinator.data, "switch",
        allowed_keys=_SYR_CONNECT_SWITCH_KNOWN_KEYS - _SYR_CONNECT_SENSOR_EXCLUDED,
        entry_id=coordinator.entry_id,
    )

    entities = []
    devices = coordinator.data.get("devices", [])
    _LOGGER.debug("Found %d devices in coordinator data.", len(devices))
    for device in devices:
        device_id = device.get("id")
        device_name = device.get("name", device_id)
        status = device.get("status", {})
        _LOGGER.debug("Checking device: id=%s, name=%s, status_keys=%s", device_id, device_name, list(status.keys()))

        # Scope to the detected model (falls back to the global allowlist for
        # models that haven't opted into per-model key lists).
        known_switch_keys = get_model_known_keys(detect_model(status), "switch", _SYR_CONNECT_SWITCH_KNOWN_KEYS)

        for sensor_key in sorted(known_switch_keys):
            if sensor_key not in status:
                _LOGGER.debug("%s not found in status for device %s.", sensor_key, device_id)
                continue
            _LOGGER.debug("%s found in status for device %s. Creating SyrConnectBooleanSwitch.", sensor_key, device_id)
            try:
                entity = SyrConnectBooleanSwitch(
                    coordinator,
                    device_id,
                    device_name,
                    sensor_key,
                )
                # If a registry entry already exists for this unique_id,
                # prefer the registry's entity_id to avoid creating a new
                # entity with a "_2" suffix.
                try:
                    registry = er.async_get(hass)
                    uid = getattr(entity, "_attr_unique_id", None)
                    if uid:
                        existing_entity_id = registry.async_get_entity_id("switch", DOMAIN, uid)
                        if existing_entity_id:
                            entity.entity_id = existing_entity_id
                            _LOGGER.debug(
                                "Using existing registry entity_id %s for unique_id %s",
                                existing_entity_id,
                                uid,
                            )
                except Exception:
                    _LOGGER.exception("Failed to check entity registry for existing switch entity")

                entities.append(entity)
                _LOGGER.debug(
                    "Appended SyrConnectBooleanSwitch for device %s (entity_id=%s, unique_id=%s)",
                    device_id,
                    getattr(entity, "entity_id", None),
                    getattr(entity, "_attr_unique_id", None),
                )
            except Exception:
                _LOGGER.exception("Failed to instantiate SyrConnectBooleanSwitch for device %s", device_id)
    if entities:
        async_add_entities(entities)
        try:
            registry = er.async_get(hass)
            missing = []
            for ent in entities:
                entity_id = getattr(ent, "entity_id", None)
                unique_id = getattr(ent, "_attr_unique_id", None)
                # Prefer lookup by entity_id; fall back to unique_id lookup
                if entity_id and registry.async_get(entity_id) is None:
                    # Try lookup by unique_id
                    if unique_id:
                        found = registry.async_get_entity_id("switch", DOMAIN, unique_id)
                        if found is None:
                            missing.append((entity_id, unique_id))
                    else:
                        missing.append((entity_id, unique_id))
            if missing:
                _LOGGER.warning(
                    "Some switch entities were created but are missing from the entity registry: %s",
                    missing,
                )
        except Exception:
            _LOGGER.exception("Failed to verify entity registry for created switch entities")
    else:
        _LOGGER.debug("No boolean switch entities found for any device.")


class SyrConnectBooleanSwitch(SyrConnectEntity, SwitchEntity):
    """Generic switch entity for boolean get<KEY>/set<KEY> settings (e.g. getBUZ, getDFI)."""

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
    ) -> None:
        """Initialize the switch."""
        _LOGGER.debug("Initializing SyrConnectBooleanSwitch: device_id=%s, name=%s, sensor_key=%s", device_id, device_name, sensor_key)
        super().__init__(coordinator, device_id, device_name, "switch", sensor_key)

        self._sensor_key = sensor_key

        # Use a platform-specific suffix to avoid unique_id collision with the
        # binary_sensor that represents the same underlying key (getBUZ).
        # Only lowercase device_id/key, not entry_id (a case-sensitive ULID) -
        # otherwise this would never match the entry_id casing written by the
        # v6->v7 registry migration.
        self._attr_unique_id = build_unique_id(coordinator.entry_id, device_id.lower(), f"{sensor_key}_switch".lower())

        # Set entity category if this key is a config entity
        if sensor_key in _SYR_CONNECT_SENSOR_CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the setting is enabled."""
        if self._device is None:
            return None
        value = self._status.get(self._sensor_key)
        if value is None:
            return None
        # A reported but unknown value (e.g. empty) is shown as off
        return is_value_true(value)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self._set_value(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self._set_value(False)

    async def _set_value(self, state: bool) -> None:
        """Set the boolean value via API."""
        # Mirror the exact type of the current getter value so the setter
        # uses the same format the device expects.
        current = self._status.get(self._sensor_key)
        value: bool | int | str
        if isinstance(current, bool):
            value = state
        elif isinstance(current, int):
            value = 1 if state else 0
        elif isinstance(current, str) and current.strip() in ("0", "1"):
            value = "1" if state else "0"
        else:
            value = "True" if state else "False"
        # key for setting: remove leading 'get' and prefix with 'set'
        set_key = f"set{self._sensor_key[3:]}"
        try:
            # Use coordinator.async_set_device_value so the DCLG is resolved correctly
            await self.coordinator.async_set_device_value(self._device_id, set_key, value)
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            # Report the failure to the caller (UI, automation) like valve/select/button do;
            # swallowing it would make the service call look successful. The coordinator has
            # already restored the previous value.
            _LOGGER.error("Failed to set %s for device %s: %s", set_key, self._device_id, err)
            raise HomeAssistantError(f"Failed to set {self._sensor_key}: {err}") from err
        await self.coordinator.async_request_refresh()
