"""Sensor platform for SYR Connect."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    _SYR_CONNECT_DIAGNOSTIC_SENSORS,
    _SYR_CONNECT_DISABLED_BY_DEFAULT_SENSORS,
    _SYR_CONNECT_EXCLUDE_WHEN_ZERO,
    _SYR_CONNECT_EXCLUDED_SENSORS,
    _SYR_CONNECT_SENSOR_DEVICE_CLASS,
    _SYR_CONNECT_SENSOR_ICONS,
    _SYR_CONNECT_SENSOR_STATE_CLASS,
    _SYR_CONNECT_SENSOR_UNITS,
    _SYR_CONNECT_SENSOR_PRECISION,
    _SYR_CONNECT_STRING_SENSORS,
    _SYR_CONNECT_SENSOR_ALARM_VALUE_MAP,
    _SYR_CONNECT_SENSOR_STATUS_VALUE_MAP,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import build_device_info, build_entity_id

_LOGGER = logging.getLogger(__name__)
import re


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
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data

    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for sensors")
        return

    entities = []

    _LOGGER.debug("Setting up sensors for %d device(s)", len(coordinator.data.get('devices', [])))

    for device in coordinator.data.get('devices', []):
        device_id = device['id']
        device_name = device['name']
        project_id = device['project_id']
        status = device.get('status', {})

        _LOGGER.debug("Device %s (%s) has %d status values", device_name, device_id, len(status))

        # Create sensors for all status values
        sensor_count = 0
        for key, value in status.items():
            # Skip sensors excluded globally
            if key in _SYR_CONNECT_EXCLUDED_SENSORS:
                continue

            # Skip specific sensors only when value is 0
            if key in _SYR_CONNECT_EXCLUDE_WHEN_ZERO:
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
                    'getRTIME',  # Combined regeneration time
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
        self._attr_translation_key = sensor_key.lower()

        # Override the entity_id to use technical name (serial number) with domain prefix
        # This prevents entity IDs from using aliases like "weichwasser"
        self.entity_id = build_entity_id("sensor", device_id, sensor_key)

        # Set entity category for diagnostic sensors
        if sensor_key in _SYR_CONNECT_DIAGNOSTIC_SENSORS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        # Set unit of measurement for water hardness sensors dynamically
        if sensor_key in ("getIWH", "getOWH"):
            # Try to get WHU value from device status
            whu_value = None
            for device in coordinator.data.get('devices', []):
                if device['id'] == device_id:
                    whu_value = device.get('status', {}).get('getWHU')
                    break
            from .const import _SYR_CONNECT_WATER_HARDNESS_UNIT_MAP
            if whu_value is not None:
                try:
                    self._attr_native_unit_of_measurement = _SYR_CONNECT_WATER_HARDNESS_UNIT_MAP.get(int(whu_value), None)
                except (ValueError, TypeError):
                    self._attr_native_unit_of_measurement = None
            else:
                self._attr_native_unit_of_measurement = None
        elif sensor_key in _SYR_CONNECT_SENSOR_UNITS:
            self._attr_native_unit_of_measurement = _SYR_CONNECT_SENSOR_UNITS[sensor_key]

        # Set device class if available
        if sensor_key in _SYR_CONNECT_SENSOR_DEVICE_CLASS:
            self._attr_device_class = _SYR_CONNECT_SENSOR_DEVICE_CLASS[sensor_key]

        # Set state class if available
        if sensor_key in _SYR_CONNECT_SENSOR_STATE_CLASS:
            self._attr_state_class = _SYR_CONNECT_SENSOR_STATE_CLASS[sensor_key]

        # Set icon if available
        if sensor_key in _SYR_CONNECT_SENSOR_ICONS:
            self._attr_icon = _SYR_CONNECT_SENSOR_ICONS[sensor_key]

        # Store base icon for state-based icon changes
        self._base_icon = getattr(self, '_attr_icon', None)

        # Disable sensors by default based on configuration
        if sensor_key in ("getIPA", "getDGW", "getMAC") or sensor_key in _SYR_CONNECT_DISABLED_BY_DEFAULT_SENSORS:
            self._attr_entity_registry_enabled_default = False

        # Build device info from coordinator data
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

        # Initialize translation placeholders for getSTA so Home Assistant
        # receives placeholders immediately (per HA entity translations guidance)
        if sensor_key == "getSTA":
            try:
                raw = None
                for device in coordinator.data.get('devices', []):
                    if device['id'] == device_id:
                        raw = device.get('status', {}).get('getSTA', '')
                        break
                placeholders: dict = {}
                m = re.search(r"Płukanie regenerantem\s*\(([^)]+)\)", str(raw))
                if m:
                    placeholders['resistance_value'] = m.group(1)
                m2 = re.search(r"Płukanie szybkie\s*(\d+)", str(raw))
                if m2:
                    placeholders['rinse_round'] = m2.group(1)
                if placeholders:
                    _LOGGER.debug("Setting initial translation_placeholders for %s: %s", self._attr_unique_id, placeholders)
                    self._attr_translation_placeholders = placeholders
                else:
                    # Home Assistant expects a mapping when formatting names; use empty dict
                    self._attr_translation_placeholders = {}
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("Failed to initialize translation placeholders for %s", self._attr_unique_id)
                self._attr_translation_placeholders = None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any.

        Icons change dynamically based on sensor state for certain sensors:
        - Alarm: alert icon when alarm active, bell icon when inactive
        - Regeneration: autorenew icon when active, timer icon when inactive
        - Salt stock: full/half/empty cup based on level
        - Remaining capacity: gauge-empty/low/full based on percentage
        """
        # Dynamic icon for alarm sensor
        if self._sensor_key == "getALM":
            # Read raw status value to decide icon (avoid translated display)
            raw_value = None
            for device in self.coordinator.data.get('devices', []):
                if device['id'] == self._device_id:
                    raw_value = device.get('status', {}).get('getALM')
                    break
            mapped = _SYR_CONNECT_SENSOR_ALARM_VALUE_MAP.get(raw_value)
            if mapped in ("no_salt", "low_salt"):
                return "mdi:bell-alert"
            return "mdi:bell-outline"

        # Dynamic icon for regeneration active sensor
        if self._sensor_key == "getSRE":
            value = self.native_value
            if value and str(value).lower() in ("1", "true", "on", "active"):
                return "mdi:autorenew"
            return "mdi:timer-outline"

        # Dynamic icon for salt stock sensors (percentage based)
        if self._sensor_key in ("getSS1", "getSS2", "getSS3"):
            try:
                value = float(self.native_value) if self.native_value is not None else 0
                if value >= 66:
                    return "mdi:cup-water"
                elif value >= 33:
                    return "mdi:cup"
                else:
                    return "mdi:cup-outline"
            except (ValueError, TypeError):
                pass

        # Dynamic icon for remaining capacity (percentage based)
        if self._sensor_key == "getRES":
            try:
                value = float(self.native_value) if self.native_value is not None else 0
                if value >= 66:
                    return "mdi:gauge-full"
                elif value >= 33:
                    return "mdi:gauge"
                else:
                    return "mdi:gauge-low"
            except (ValueError, TypeError):
                pass

        # Return base icon for all other sensors
        return self._base_icon

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                status = device.get('status', {})

                # Special handling for combined regeneration time sensor
                if self._sensor_key == 'getRTIME':
                    hour = status.get('getRTH', 0)
                    minute = status.get('getRTM', 0)
                    try:
                        return f"{int(hour):02d}:{int(minute):02d}"
                    except (ValueError, TypeError):
                        return "00:00"

                # Special handling for water hardness unit sensor (mapping)
                if self._sensor_key == 'getWHU':
                    value = status.get(self._sensor_key)
                    from .const import _SYR_CONNECT_WATER_HARDNESS_UNIT_MAP
                    if isinstance(value, (int, float)):
                        return _SYR_CONNECT_WATER_HARDNESS_UNIT_MAP.get(int(value), None)
                    elif isinstance(value, str):
                        try:
                            return _SYR_CONNECT_WATER_HARDNESS_UNIT_MAP.get(int(value), None)
                        except (ValueError, TypeError):
                            return None
                    return None

                # Raw value from device
                value = status.get(self._sensor_key)

                # Special handling for status sensor (getSTA): map Polish strings to internal keys
                if self._sensor_key == 'getSTA':
                    raw = value if value is not None else ""
                    # Default attributes
                    # Check for regenerant rinse pattern with value in parentheses, e.g. "Płukanie regenerantem (0mA)"
                    m = re.search(r"Płukanie regenerantem\s*\(([^)]+)\)", str(raw))
                    if m:
                        # set attribute resistance_value and return mapped key
                        return _SYR_CONNECT_SENSOR_STATUS_VALUE_MAP.get("Płukanie regenerantem (0mA)", "status_regenerant_rinse")
                    # Check for fast rinse pattern with a round number, e.g. "Płukanie szybkie 1"
                    m2 = re.search(r"Płukanie szybkie\s*(\d+)", str(raw))
                    if m2:
                        return _SYR_CONNECT_SENSOR_STATUS_VALUE_MAP.get("Płukanie szybkie 1", "status_fast_rinse")
                    # Fallback to exact map lookup
                    mapped = _SYR_CONNECT_SENSOR_STATUS_VALUE_MAP.get(raw)
                    return mapped if mapped is not None else (raw if raw != "" else None)

                # Special handling for alarm sensor: map raw API values to internal keys
                if self._sensor_key == 'getALM':
                    mapped = _SYR_CONNECT_SENSOR_ALARM_VALUE_MAP.get(value)
                    # Return mapped key (e.g. 'no_salt', 'low_salt', 'no_alarm') or raw value as fallback
                    return mapped if mapped is not None else (value if value is not None else None)

                # Keep certain sensors as strings (version, serial, MAC, etc.)
                if self._sensor_key in _SYR_CONNECT_STRING_SENSORS:
                    return str(value) if value is not None else None

                # Try to convert to number if possible for other sensors
                if isinstance(value, str):
                    try:
                        numeric_value = float(value)
                        # Divide pressure by 10 to convert to correct unit
                        if self._sensor_key == 'getPRS':
                            numeric_value = numeric_value / 10
                        # Apply configured precision if available
                        precision = _SYR_CONNECT_SENSOR_PRECISION.get(self._sensor_key) if isinstance(_SYR_CONNECT_SENSOR_PRECISION, dict) else None
                        if precision is not None:
                            try:
                                numeric_value = round(numeric_value, precision)
                                if precision == 0:
                                    numeric_value = int(numeric_value)
                            except (TypeError, ValueError):
                                pass
                        return numeric_value
                    except (ValueError, TypeError):
                        return value

                # Handle numeric values directly
                if isinstance(value, (int, float)):
                    # Divide pressure by 10 to convert to correct unit
                    if self._sensor_key == 'getPRS':
                        return value / 10
                    # Apply configured precision if available
                    precision = _SYR_CONNECT_SENSOR_PRECISION.get(self._sensor_key) if isinstance(_SYR_CONNECT_SENSOR_PRECISION, dict) else None
                    if precision is not None:
                        try:
                            val = float(value)
                            val = round(val, precision)
                            if precision == 0:
                                return int(val)
                            return val
                        except (TypeError, ValueError):
                            return value
                    return value

                return value

        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check if the specific device is available
        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                return device.get('available', True)

        return True

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return additional state attributes used by translations."""
        # Only provide attributes for getSTA to fill translation placeholders
        if self._sensor_key != 'getSTA':
            return None

        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                raw = device.get('status', {}).get('getSTA', '')
                attrs: dict = {}
                if raw is None:
                    return {}
                # resistance_value: inside parentheses for regenerant rinse
                m = re.search(r"Płukanie regenerantem\s*\(([^)]+)\)", str(raw))
                if m:
                    attrs['resistance_value'] = m.group(1)
                # rinse_round: number after "Płukanie szybkie"
                m2 = re.search(r"Płukanie szybkie\s*(\d+)", str(raw))
                if m2:
                    attrs['rinse_round'] = m2.group(1)

                return attrs if attrs else None

    @property
    def translation_placeholders(self) -> dict:
        """Return translation placeholders for the frontend translations.

        Always return a mapping (possibly empty) because Home Assistant will
        call `name.format(**translation_placeholders)` when building entity
        names; passing None causes a TypeError.
        """
        if self._sensor_key != 'getSTA':
            return {}

        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                raw = device.get('status', {}).get('getSTA', '')
                if raw is None:
                    return {}
                placeholders: dict = {}
                m = re.search(r"Płukanie regenerantem\s*\(([^)]+)\)", str(raw))
                if m:
                    placeholders['resistance_value'] = m.group(1)
                m2 = re.search(r"Płukanie szybkie\s*(\d+)", str(raw))
                if m2:
                    placeholders['rinse_round'] = m2.group(1)

                return placeholders if placeholders else {}

    def _handle_coordinator_update(self) -> None:
        """Update translation placeholders on coordinator update and propagate state."""
        try:
            new_placeholders = self.translation_placeholders or {}
            if new_placeholders != getattr(self, '_attr_translation_placeholders', {}):
                _LOGGER.debug("Updating translation_placeholders for %s: %s", self._attr_unique_id, new_placeholders)
            self._attr_translation_placeholders = new_placeholders
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to update translation_placeholders for %s", self._attr_unique_id)
            self._attr_translation_placeholders = {}
        super()._handle_coordinator_update()

