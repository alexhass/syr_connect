"""Number platform for SYR Connect (setSV1)."""
from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import _SYR_CONNECT_SENSOR_ICONS, _SYR_CONNECT_SENSOR_UNITS
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import build_device_info, build_entity_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for SYR Connect.

    Adds a `number` entity for `getSV1` (salt amount) which is writable via `setSV1`.
    """
    _LOGGER.debug("Setting up SYR Connect number entities")
    coordinator: SyrConnectDataUpdateCoordinator = cast(
        SyrConnectDataUpdateCoordinator, entry.runtime_data
    )

    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for numbers")
        return

    # Cleanup function: remove setSVx entities when corresponding getSVx is missing or zero
    def _cleanup_setsv_entities() -> None:
        try:
            registry = er.async_get(hass)
            for device in coordinator.data.get('devices', []):
                device_id = device['id']
                status = device.get('status', {})
                for sv_key in ("getSV1", "getSV2", "getSV3"):
                    # entity is named after the getSV key
                    entity_id = build_entity_id("number", device_id, sv_key)
                    registry_entry = registry.async_get(entity_id)

                    sv_value = status.get(sv_key)
                    # Remove entity when value is missing or explicitly zero
                    remove = False
                    if sv_value is None or sv_value == "":
                        remove = True
                    else:
                        try:
                            if float(sv_value) == 0:
                                remove = True
                        except (ValueError, TypeError):
                            # Non-numeric value: do not remove
                            remove = False

                    if remove and registry_entry is not None and hasattr(registry_entry, "entity_id"):
                        _LOGGER.debug("Removing number entity from registry because getSV is zero/missing: %s", entity_id)
                        registry.async_remove(registry_entry.entity_id)
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to cleanup setSV entities from entity registry")

    # Run initial cleanup and register it to run after each coordinator update
    _cleanup_setsv_entities()
    try:
        coordinator.async_add_listener(_cleanup_setsv_entities)
    except Exception:
        _LOGGER.debug("Failed to add coordinator listener for cleanup; continuing without listener")

    entities: list[NumberEntity] = []

    for device in coordinator.data.get('devices', []):
        device_id = device['id']
        device_name = device['name']
        status = device.get('status', {})

        # Create numbers for getSV1/getSV2/getSV3 only when the device reports a non-zero value
        for sv_key in ("getSV1", "getSV2", "getSV3"):
            sv_value = status.get(sv_key)
            if sv_value is None or sv_value == "":
                continue
            try:
                if float(sv_value) == 0:
                    # Skip creating a number entity when reported salt amount is zero
                    continue
            except (ValueError, TypeError):
                # If value is not convertible, skip creating the number entity
                continue

            entities.append(
                SyrConnectNumber(coordinator, device_id, device_name, sv_key)
            )

    if entities:
        _LOGGER.debug("Adding %d number(s) total", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No number entities to add")


class SyrConnectNumber(CoordinatorEntity, NumberEntity):
    """Representation of a writable salt amount (getSV1 -> setSV1)."""

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)

        self._device_id = device_id
        self._device_name = device_name
        self._sensor_key = sensor_key

        # Unique ID based on device and sensor key (keep distinct from sensor unique_id)
        self._attr_unique_id = f"{device_id}_{sensor_key}_number"
        self._attr_has_entity_name = True
        # Use the getSVx translation key so the number displays the same label
        self._attr_translation_key = sensor_key.lower()

        # Override entity_id to use technical naming based on the getSVx key
        self.entity_id = build_entity_id("number", device_id, sensor_key)

        # Native numeric range: 0..25 kg (integers)
        self._attr_native_min_value = 0
        self._attr_native_max_value = 25
        self._attr_native_step = 1

        # Unit from const mapping if available
        self._attr_native_unit_of_measurement = _SYR_CONNECT_SENSOR_UNITS.get(sensor_key)

        # Icon from sensor icons mapping (use same icon as getSVx)
        icon = _SYR_CONNECT_SENSOR_ICONS.get(sensor_key)
        if icon:
            self._attr_icon = icon

        # Device info
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

        # Show as configuration field in the device UI instead of a control
        #self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> int | float | None:
        """Return current value from coordinator data (getSV1)."""
        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                status = device.get('status', {})
                val = status.get(self._sensor_key)
                if val is None or val == "":
                    return None
                try:
                    return int(float(val))
                except (ValueError, TypeError):
                    return None
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                return device.get('available', True)

        return True

    async def async_set_native_value(self, value: float) -> None:
        """Set the value via the coordinator which calls the API (setSV1).

        The coordinator will refresh data after the API call.
        """
        # Normalize to integer if step is 1
        try:
            if self._attr_native_step == 1:
                set_value: Any = int(round(value))
            else:
                set_value = value
        except Exception as err:
            _LOGGER.error("Invalid value type for setSV1: %s", err)
            raise

        coordinator: SyrConnectDataUpdateCoordinator = cast(
            SyrConnectDataUpdateCoordinator, self.coordinator
        )
        # Send setSVx command to API (e.g., setSV1) while reading comes from getSVx
        await coordinator.async_set_device_value(self._device_id, f"set{self._sensor_key[3:]}", set_value)

    @property
    def mode(self) -> NumberMode:
        """Return display mode for the number entity.

        Use BOX mode to show a text/number input instead of a slider.
        """
        return NumberMode.BOX
