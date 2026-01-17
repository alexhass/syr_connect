"""Binary sensor platform for SYR Connect."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    _SYR_CONNECT_BINARY_SENSORS,
    _SYR_CONNECT_EXCLUDED_SENSORS,
    _SYR_CONNECT_SENSOR_ICONS,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import build_device_info, build_entity_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SYR Connect binary sensors.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up SYR Connect binary sensors")
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data

    entities = []

    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for binary sensors")
        return

    # Remove previously-registered entities that are now excluded
    try:
        registry = er.async_get(hass)
        for device in coordinator.data.get('devices', []):
            device_id = device['id']
            for excluded_key in _SYR_CONNECT_EXCLUDED_SENSORS:
                entity_id = build_entity_id("binary_sensor", device_id, excluded_key)
                registry_entry = registry.async_get(entity_id)
                if registry_entry is not None and hasattr(registry_entry, "entity_id"):
                    _LOGGER.debug("Removing excluded binary sensor from registry: %s", entity_id)
                    registry.async_remove(registry_entry.entity_id)
    except Exception:  # pragma: no cover - defensive
        _LOGGER.exception("Failed to cleanup excluded binary sensors from entity registry")

    for device in coordinator.data.get('devices', []):
        device_id = device['id']
        device_name = device['name']
        project_id = device['project_id']
        status = device.get('status', {})

        # Create binary sensors for boolean status values
        for sensor_key, device_class in _SYR_CONNECT_BINARY_SENSORS.items():
            # Skip sensors excluded globally
            if sensor_key in _SYR_CONNECT_EXCLUDED_SENSORS:
                continue

            if sensor_key in status:
                entities.append(
                    SyrConnectBinarySensor(
                        coordinator,
                        device_id,
                        device_name,
                        project_id,
                        sensor_key,
                        device_class,
                    )
                )

    _LOGGER.debug("Adding %d binary sensor(s) total", len(entities))
    async_add_entities(entities)


class SyrConnectBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a SYR Connect binary sensor."""

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        project_id: str,
        sensor_key: str,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        """Initialize the binary sensor.

        Args:
            coordinator: Data update coordinator
            device_id: Device ID (serial number)
            device_name: Device display name
            project_id: Project ID
            sensor_key: Sensor key (e.g., 'getSRE')
            device_class: Binary sensor device class
        """
        super().__init__(coordinator)

        self._device_id = device_id
        self._device_name = device_name
        self._project_id = project_id
        self._sensor_key = sensor_key

        # Set unique ID and translation platform
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_key.lower()
        self._attr_device_class = device_class

        # Override the entity_id to use technical name (serial number) with domain prefix
        self.entity_id = build_entity_id("binary_sensor", device_id, sensor_key)

        # Set icon if available
        if sensor_key in _SYR_CONNECT_SENSOR_ICONS:
            self._attr_icon = _SYR_CONNECT_SENSOR_ICONS[sensor_key]

        # Build device info from coordinator data
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on.

        Returns:
            True if sensor is on, False if off, None if unavailable
        """
        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                status = device.get('status', {})
                value = status.get(self._sensor_key)

                # Convert value to boolean
                if isinstance(value, int | float):
                    return value != 0
                elif isinstance(value, str):
                    return value not in ("0", "false", "False", "")

                return False

        return None

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
