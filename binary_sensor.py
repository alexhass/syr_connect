"""Binary sensor platform for SYR Connect."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, SENSOR_ICONS
from .coordinator import SyrConnectDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Binary sensors mapping with their device classes
BINARY_SENSORS = {
    "getSRE": BinarySensorDeviceClass.RUNNING,  # Regeneration active
    "getPST": BinarySensorDeviceClass.RUNNING,  # Operating state
    "getSCR": BinarySensorDeviceClass.LOCK,     # Screen lock
    "getALM": BinarySensorDeviceClass.PROBLEM,  # Alarm
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SYR Connect binary sensors."""
    _LOGGER.info("Setting up SYR Connect binary sensors")
    coordinator: SyrConnectDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    
    for device in coordinator.data.get('devices', []):
        device_id = device['id']
        device_name = device['name']
        project_id = device['project_id']
        status = device.get('status', {})
        
        # Create binary sensors for boolean status values
        for sensor_key, device_class in BINARY_SENSORS.items():
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
    
    _LOGGER.info("Adding %d binary sensor(s) total", len(entities))
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
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        
        self._device_id = device_id
        self._device_name = device_name
        self._project_id = project_id
        self._sensor_key = sensor_key
        
        # Set unique ID and translation platform
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_key
        self._attr_device_class = device_class
        
        # Override the entity_id to use technical name (serial number) with domain prefix
        self.entity_id = f"binary_sensor.{DOMAIN}_{device_id.lower()}_{sensor_key.lower()}"
        
        # Set icon if available
        if sensor_key in SENSOR_ICONS:
            self._attr_icon = SENSOR_ICONS[sensor_key]
        
        # Build device info with data from coordinator
        model = None
        sw_version = None
        hw_version = None
        
        for device in coordinator.data.get('devices', []):
            if device['id'] == device_id:
                status = device.get('status', {})
                model = str(status.get('getCNA', 'SYR Connect'))
                sw_version = str(status['getVER']) if 'getVER' in status and status['getVER'] else None
                hw_version = str(status['getFIR']) if 'getFIR' in status and status['getFIR'] else None
                break
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="SYR",
            model=model or "SYR Connect",
            sw_version=sw_version,
            hw_version=hw_version,
            serial_number=device_id,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                status = device.get('status', {})
                value = status.get(self._sensor_key)
                
                # Convert value to boolean
                if isinstance(value, (int, float)):
                    return value != 0
                elif isinstance(value, str):
                    return value not in ("0", "false", "False", "")
                
                return False
        
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
