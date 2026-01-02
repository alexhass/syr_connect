"""Sensor platform for SYR Connect."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfMass,
    UnitOfPressure,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    SENSOR_DEVICE_CLASS,
    SENSOR_STATE_CLASS,
    SENSOR_ICONS,
    STRING_SENSORS,
)
from .coordinator import SyrConnectDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Sensor units mapping (units are standardized and not translated)
_SENSOR_UNITS = {
    "getIWH": "°dH",
    "getOWH": "°dH",
    "getRES": UnitOfVolume.LITERS,
    "getTOR": UnitOfVolume.LITERS,
    "getRPD": UnitOfTime.DAYS,
    "getRTH": UnitOfTime.HOURS,
    "getSV1": UnitOfMass.KILOGRAMS,
    "getSV2": UnitOfMass.KILOGRAMS,
    "getSV3": UnitOfMass.KILOGRAMS,
    "getSS1": UnitOfTime.WEEKS,
    "getSS2": UnitOfTime.WEEKS,
    "getSS3": UnitOfTime.WEEKS,
    "getPRS": UnitOfPressure.BAR,
    "getFLO": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
    "getFCO": UnitOfVolume.LITERS,
    "getDWF": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
    "getRDO": PERCENTAGE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SYR Connect sensors.
    
    Args:
        hass: Home Assistant instance
        entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up SYR Connect sensors")
    coordinator: SyrConnectDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for sensors")
        return
    
    # Sensors to always exclude (parameters from XML that should not be exposed)
    EXCLUDED_SENSORS = {
        'p1883', 'p1883rd', 'p8883', 'p8883rd',
        'sbt', 'sta', 'dst', 'ast', 'so',
        'dclg', 'clb', 'nrs',  # Device collection metadata
        'nrdt', 'dg',  # Additional device metadata attributes
        'dt',  # Timestamp attributes (getSRN_dt, getALM_dt, etc.)
        'getDEN',  # Boolean sensor - device enabled/disabled
        'getRTH', 'getRTM',  # Regeneration time - combined into getRTI
        'getCDE',  # Configuration code - not useful for users
        'getNOT',  # Notes field not useful as sensor
        'getSIR',  # Immediate regeneration control
        'getSTA',  # Status - redundant with other status sensors
        'getTYP',  # Type - not helpful for users
        'getINR',  # Internal reference - not useful
        'getLAR',  # Last action - not useful as sensor
        'getSRN_dt',
        'getALM_dt',
        # Boolean sensors - now handled as binary_sensor platform
        'getSRE',  # Regeneration active
        'getPST',  # Operating state
        'getSCR',  # Screen lock
        'getALM',  # Alarm
    }
    
    # Sensors to exclude only when value is 0
    EXCLUDE_WHEN_ZERO = {
        'getSV1', 'getSV2', 'getSV3',  # Salt amount containers
        'getSS1', 'getSS2', 'getSS3',  # Salt supply containers
        'getCS1', 'getCS2', 'getCS3',  # Configuration stages
        'getRG1', 'getRG2', 'getRG3',  # Regeneration groups
        'getVS1', 'getVS2', 'getVS3',  # Volume thresholds
    }
    
    entities = []
    
    for device in coordinator.data.get('devices', []):
        device_id = device['id']
        device_name = device['name']
        project_id = device['project_id']
        status = device.get('status', {})
        
        # Create sensors for all status values
        sensor_count = 0
        for key, value in status.items():
            # Skip sensors that are always excluded
            if key in EXCLUDED_SENSORS or key.startswith('_'):
                continue
            
            # Skip specific sensors only when value is 0
            if key in EXCLUDE_WHEN_ZERO:
                if isinstance(value, (int, float)) and value == 0:
                    continue
                elif isinstance(value, str) and value == "0":
                    continue
            
            # Create sensor if value is valid
            if isinstance(value, (int, float, str)):
                entities.append(
                    SyrConnectSensor(
                        coordinator,
                        device_id,
                        device_name,
                        project_id,
                        key,
                    )
                )
                sensor_count += 1
        
        # Create combined regeneration time sensor from getRTH and getRTM
        if 'getRTH' in status and 'getRTM' in status:
            entities.append(
                SyrConnectSensor(
                    coordinator,
                    device_id,
                    device_name,
                    project_id,
                    'getRTI',  # Combined regeneration time
                )
            )
            sensor_count += 1
        
        _LOGGER.debug("Created %d sensor(s) for device %s", sensor_count, device_name)
    
    _LOGGER.debug("Adding %d sensor(s) total", len(entities))
    async_add_entities(entities)


class SyrConnectSensor(CoordinatorEntity, SensorEntity):
    """Representation of a SYR Connect sensor."""

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        project_id: str,
        sensor_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._device_id = device_id
        self._device_name = device_name
        self._project_id = project_id
        self._sensor_key = sensor_key
        
        # Set unique ID and translation platform
        # device_id is the serial number - use it for technical entity IDs
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_key
        
        # Override the entity_id to use technical name (serial number) with domain prefix
        # This prevents entity IDs from using aliases like "weichwasser"
        self.entity_id = f"sensor.{DOMAIN}_{device_id.lower()}_{sensor_key.lower()}"
        
        # Set unit of measurement if available
        if sensor_key in _SENSOR_UNITS:
            self._attr_native_unit_of_measurement = _SENSOR_UNITS[sensor_key]
        
        # Set device class if available
        if sensor_key in SENSOR_DEVICE_CLASS:
            self._attr_device_class = SENSOR_DEVICE_CLASS[sensor_key]
        
        # Set state class if available
        if sensor_key in SENSOR_STATE_CLASS:
            self._attr_state_class = SENSOR_STATE_CLASS[sensor_key]
        
        # Set icon if available
        if sensor_key in SENSOR_ICONS:
            self._attr_icon = SENSOR_ICONS[sensor_key]
        
        # Disable IP address, Gateway and MAC address sensors by default
        if sensor_key in ("getIPA", "getDGW", "getMAC"):
            self._attr_entity_registry_enabled_default = False
        
        # Build device info with data from coordinator
        model = None
        sw_version = None
        hw_version = None
        
        # Add additional device information from status if available
        for device in coordinator.data.get('devices', []):
            if device['id'] == device_id:
                status = device.get('status', {})
                
                # Add model from getCNA
                if 'getCNA' in status and status['getCNA']:
                    model = str(status['getCNA'])
                else:
                    _LOGGER.warning("getCNA not found in status or is empty for device %s", device_id)
                
                # Add firmware version from getVER
                if 'getVER' in status and status['getVER']:
                    sw_version = str(status['getVER'])
                
                # Add hardware version/type from getFIR
                if 'getFIR' in status and status['getFIR']:
                    hw_version = str(status['getFIR'])
                
                break
        
        # Fallback if no model found
        if model is None:
            model = "SYR Connect"
            _LOGGER.warning("No model found, using fallback 'SYR Connect'")
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="SYR",
            model=model,
            sw_version=sw_version,
            hw_version=hw_version,
            serial_number=device_id,
        )

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                status = device.get('status', {})
                
                # Special handling for combined regeneration time sensor
                if self._sensor_key == 'getRTI':
                    hour = status.get('getRTH', 0)
                    minute = status.get('getRTM', 0)
                    try:
                        return f"{int(hour):02d}:{int(minute):02d}"
                    except (ValueError, TypeError):
                        return "00:00"
                
                # Special handling for water hardness unit sensor (mapping)
                if self._sensor_key == 'getWHU':
                    value = status.get(self._sensor_key)
                    unit_map = {
                        0: "°dH",
                        1: "°fH",
                        2: "ppm",
                        3: "mmol/l"
                    }
                    if isinstance(value, (int, float)):
                        return unit_map.get(int(value), "°dH")
                    elif isinstance(value, str):
                        try:
                            return unit_map.get(int(value), "°dH")
                        except (ValueError, TypeError):
                            return "°dH"
                    return "°dH"
                
                value = status.get(self._sensor_key)
                
                # Keep certain sensors as strings (version, serial, MAC, etc.)
                if self._sensor_key in STRING_SENSORS:
                    return str(value) if value is not None else None
                
                # Try to convert to number if possible for other sensors
                if isinstance(value, str):
                    try:
                        numeric_value = float(value)
                        # Divide pressure by 10 to convert to correct unit
                        if self._sensor_key == 'getPRS':
                            numeric_value = numeric_value / 10
                        return numeric_value
                    except (ValueError, TypeError):
                        return value
                
                # Handle numeric values directly
                if isinstance(value, (int, float)):
                    # Divide pressure by 10 to convert to correct unit
                    if self._sensor_key == 'getPRS':
                        return value / 10
                    return value
                
                return value
        
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
