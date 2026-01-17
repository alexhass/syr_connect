"""Sensor platform for SYR Connect."""
from __future__ import annotations

import logging
import re
from datetime import UTC

from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    _SYR_CONNECT_DIAGNOSTIC_SENSORS,
    _SYR_CONNECT_DISABLED_BY_DEFAULT_SENSORS,
    _SYR_CONNECT_EXCLUDE_WHEN_ZERO,
    _SYR_CONNECT_EXCLUDED_SENSORS,
    _SYR_CONNECT_SENSOR_ALARM_VALUE_MAP,
    _SYR_CONNECT_SENSOR_DEVICE_CLASS,
    _SYR_CONNECT_SENSOR_ICONS,
    _SYR_CONNECT_SENSOR_PRECISION,
    _SYR_CONNECT_SENSOR_STATE_CLASS,
    _SYR_CONNECT_SENSOR_STATUS_VALUE_MAP,
    _SYR_CONNECT_SENSOR_UNITS,
    _SYR_CONNECT_STRING_SENSORS,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import build_device_info, build_entity_id

_LOGGER = logging.getLogger(__name__)


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

    # Remove previously-registered entities that are now excluded
    try:
        registry = er.async_get(hass)
        for device in coordinator.data.get('devices', []):
            device_id = device['id']
            for excluded_key in _SYR_CONNECT_EXCLUDED_SENSORS:
                entity_id = build_entity_id("sensor", device_id, excluded_key)
                registry_entry = registry.async_get(entity_id)
                if registry_entry is not None and hasattr(registry_entry, "entity_id"):
                    _LOGGER.debug("Removing excluded sensor from registry: %s", entity_id)
                    registry.async_remove(registry_entry.entity_id)
    except Exception:  # pragma: no cover - defensive
        _LOGGER.exception("Failed to cleanup excluded sensors from entity registry")

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

            # Special logic for getCS1/2/3:
            # These sensors represent the remaining resin capacity in percent (getCSx),
            # while getSVx represents the salt amount in kg for the same compartment.
            # By default, sensors in _SYR_CONNECT_EXCLUDE_WHEN_ZERO are hidden if their value is 0.
            # However, for getCS1/2/3, we want to show them if the corresponding getSV1/2/3 is not zero,
            # even if getCSx itself is zero. This ensures that users see the resin capacity as long as
            # there is salt present, which is relevant for maintenance and monitoring.
            #
            # Logic:
            # - If getSVx exists and is not zero: always show getCSx, regardless of its value.
            # - If getSVx is missing or zero: only show getCSx if its value is not zero.
            # - If getSVx cannot be converted to float: fallback to standard logic (hide if getCSx is zero).
            # This prevents hiding getCSx when salt is present, but still hides it if both are zero or missing.
            if key in ("getCS1", "getCS2", "getCS3"):
                getsv_key = "getSV" + key[-1]
                getsv_value = status.get(getsv_key)
                if getsv_value is not None:
                    try:
                        if float(getsv_value) != 0:
                            pass  # show getCSx even if value == 0
                        else:
                            if isinstance(value, int | float) and value == 0:
                                continue
                            elif isinstance(value, str) and value == "0":
                                continue
                    except (ValueError, TypeError):
                        # If getSVx value is not convertible, use standard logic
                        if isinstance(value, int | float) and value == 0:
                            continue
                        elif isinstance(value, str) and value == "0":
                            continue
                else:
                    # If getSVx value is missing, use standard logic
                    if isinstance(value, int | float) and value == 0:
                        continue
                    elif isinstance(value, str) and value == "0":
                        continue
            elif key in _SYR_CONNECT_EXCLUDE_WHEN_ZERO:
                if isinstance(value, int | float) and value == 0:
                    continue
                elif isinstance(value, str) and value == "0":
                    continue

            # Create sensor if value is valid
            if isinstance(value, int | float | str):
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
        # Use translation key (case-insensitive) to cover different casings
        if getattr(self, '_attr_translation_key', '').lower() == "getsta":
            try:
                raw = None
                for device in coordinator.data.get('devices', []):
                    if device['id'] == device_id:
                        raw = device.get('status', {}).get('getSTA', '')
                        break
                # Always provide the required placeholder keys (may be empty strings)
                placeholders: dict = {"resistance_value": "", "rinse_round": ""}
                _LOGGER.debug("Initial raw getSTA for %s: %s", self.entity_id, raw)
                m = re.search(r"Płukanie regenerantem\s*\(([^)]+)\)", str(raw))
                if m:
                    placeholders['resistance_value'] = m.group(1)
                m2 = re.search(r"Płukanie szybkie\s*(\d+)", str(raw))
                if m2:
                    placeholders['rinse_round'] = m2.group(1)
                _LOGGER.debug("Setting initial translation_placeholders for %s: %s", self.entity_id, placeholders)
                self._attr_translation_placeholders = placeholders
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("Failed to initialize translation placeholders for %s", self.entity_id)
                self._attr_translation_placeholders = {"resistance_value": "", "rinse_round": ""}

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
            mapped = _SYR_CONNECT_SENSOR_ALARM_VALUE_MAP.get(str(raw_value))
            if mapped in ("no_salt", "low_salt"):
                return "mdi:bell-alert"
            return "mdi:bell-outline"

        # Dynamic icon for regeneration active sensor
        if self._sensor_key == "getSRE":
            value = self.native_value
            if value and str(value).lower() in ("1", "true", "on", "active"):
                return "mdi:autorenew"
            return "mdi:timer-outline"

        # Dynamic icon for regeneration relay sensors (getRG1/getRG2/getRG3)
        if self._sensor_key in ("getRG1", "getRG2", "getRG3"):
            try:
                val = self.native_value
                if val is None:
                    return self._base_icon
                try:
                    ival = int(float(val))
                except (TypeError, ValueError):
                    sval = str(val).lower()
                    if sval in ("1", "true", "on", "active"):
                        ival = 1
                    else:
                        ival = 0
                # 1 -> open valve icon, 0 -> closed valve icon
                return "mdi:valve" if ival == 1 else "mdi:valve-closed"
            except Exception:
                pass

        # Dynamic icon for pressure sensor availability (getPST)
        if self._sensor_key == "getPST":
            try:
                val = self.native_value
                # native_value may be numeric or string; normalize to int when possible
                if val is None:
                    return self._base_icon
                try:
                    ival = int(float(val))
                except (TypeError, ValueError):
                    ival = 1
                # Values:
                # 1 -> Not available
                # 2 -> Available
                if ival == 2:
                    return "mdi:check-circle"
                if ival == 1:
                    return "mdi:close-circle"
            except Exception:
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
                    if isinstance(value, int | float):
                        return _SYR_CONNECT_WATER_HARDNESS_UNIT_MAP.get(int(value), None)
                    elif isinstance(value, str):
                        try:
                            return _SYR_CONNECT_WATER_HARDNESS_UNIT_MAP.get(int(value), None)
                        except (ValueError, TypeError):
                            return None
                    return None

                # Special handling for last regeneration timestamp (getLAR): convert unix seconds to datetime object
                if self._sensor_key == 'getLAR':
                    raw_value = status.get(self._sensor_key)
                    if raw_value is None or raw_value == "":
                        return None
                    try:
                        from datetime import datetime

                        ts = int(float(raw_value))
                        # Return an aware datetime object (UTC). Home Assistant
                        # will format this according to the user's timezone/locale.
                        return datetime.fromtimestamp(ts, UTC)
                    except (ValueError, TypeError, OverflowError):
                        return None

                # Raw value from device
                value = status.get(self._sensor_key)

                # Special handling for status sensor (getSTA): map Polish strings to internal keys
                if self._sensor_key == 'getSTA':
                    placeholders = self._compute_translation_placeholders()
                    raw = value if value is not None else ""
                    # Priorisiere Mapping anhand der Platzhalter
                    if placeholders['resistance_value']:
                        return _SYR_CONNECT_SENSOR_STATUS_VALUE_MAP.get("Płukanie regenerantem (0mA)", "status_regenerant_rinse")
                    if placeholders['rinse_round']:
                        return _SYR_CONNECT_SENSOR_STATUS_VALUE_MAP.get("Płukanie szybkie 1", "status_fast_rinse")
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
                        # Divide pressure by 10 to convert from "dbar" to "bar" to correct unit
                        if self._sensor_key == 'getPRS':
                            numeric_value = numeric_value / 10
                        # getCEL values are provided as 1/10 °C (e.g. 110 -> 11.0°C)
                        if self._sensor_key == 'getCEL':
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
                if isinstance(value, int | float):
                    # Divide pressure by 10 to convert from "dbar" to "bar" to correct unit
                    if self._sensor_key == 'getPRS':
                        return value / 10
                    # getCEL values are provided as 1/10 °C (e.g. 110 -> 11.0°C)
                    if self._sensor_key == 'getCEL':
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
        is_getsta = (
            getattr(self, '_attr_translation_key', '').lower() == 'getsta' or
            self.entity_id.endswith('_getsta')
        )
        if not is_getsta:
            return None

        # Debug: log every time attributes are computed for getSTA
        _LOGGER.debug("[getSTA debug] Entity: %s, device_id: %s, coordinator.data: %s", self.entity_id, self._device_id, self.coordinator.data)

        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                raw = device.get('status', {}).get('getSTA', '')
                attrs: dict = {"resistance_value": "", "rinse_round": ""}
                _LOGGER.debug("[getSTA debug] Entity: %s, raw getSTA: %s", self.entity_id, raw)
                if raw is None:
                    _LOGGER.debug("[getSTA debug] Entity: %s, raw is None, returning attrs: %s", self.entity_id, attrs)
                    return attrs
                m = re.search(r"Płukanie regenerantem\s*\(([^)]+)\)", str(raw))
                if m:
                    attrs['resistance_value'] = m.group(1)
                    _LOGGER.debug("[getSTA debug] Entity: %s, resistance_value matched: %s", self.entity_id, attrs['resistance_value'])
                m2 = re.search(r"Płukanie szybkie\s*(\d+)", str(raw))
                if m2:
                    attrs['rinse_round'] = m2.group(1)
                    _LOGGER.debug("[getSTA debug] Entity: %s, rinse_round matched: %s", self.entity_id, attrs['rinse_round'])
                _LOGGER.debug("[getSTA debug] Entity: %s, returning attrs: %s", self.entity_id, attrs)
                return attrs
        return None


    def _compute_translation_placeholders(self) -> dict:
        """Compute translation placeholders for getSTA sensors."""
        is_getsta = (
            getattr(self, '_attr_translation_key', '').lower() == 'getsta' or
            self.entity_id.endswith('_getsta')
        )
        if not is_getsta:
            return {"resistance_value": "", "rinse_round": ""}
        placeholders = {"resistance_value": "", "rinse_round": ""}
        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                raw = device.get('status', {}).get('getSTA', '')
                if raw is None:
                    return placeholders
                m = re.search(r"Płukanie regenerantem\s*\(([^)]+)\)", str(raw))
                if m:
                    placeholders['resistance_value'] = m.group(1)
                m2 = re.search(r"Płukanie szybkie\s*(\d+)", str(raw))
                if m2:
                    placeholders['rinse_round'] = m2.group(1)
                return placeholders
        return placeholders

    def _handle_coordinator_update(self) -> None:
        """Update translation placeholders on coordinator update and propagate state."""
        try:
            # Only update translation_placeholders for getSTA entities
            if getattr(self, '_attr_translation_key', '').lower() == 'getsta' or self.entity_id.endswith('_getsta'):
                new_placeholders = self._compute_translation_placeholders()
                if new_placeholders != getattr(self, '_attr_translation_placeholders', {}):
                    _LOGGER.debug("Updating translation_placeholders for %s: %s", self.entity_id, new_placeholders)
                    _LOGGER.debug("extra_state_attributes for %s: %s", self.entity_id, self.extra_state_attributes)
                self._attr_translation_placeholders = new_placeholders or {"resistance_value": "", "rinse_round": ""}
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to update translation_placeholders for %s", self.entity_id)
            self._attr_translation_placeholders = {"resistance_value": "", "rinse_round": ""}
        super()._handle_coordinator_update()

