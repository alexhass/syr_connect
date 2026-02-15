"""Sensor platform for SYR Connect."""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta

from babel.dates import format_datetime
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    _SYR_CONNECT_SENSOR_DEVICE_CLASS,
    _SYR_CONNECT_SENSOR_DIAGNOSTIC,
    _SYR_CONNECT_SENSOR_DISABLED_BY_DEFAULT,
    _SYR_CONNECT_SENSOR_EXCLUDED,
    _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_ZERO,
    _SYR_CONNECT_SENSOR_GETALM_VALUE_MAP,
    _SYR_CONNECT_SENSOR_GETLE_VALUE_MAP,
    _SYR_CONNECT_SENSOR_GETSTA_VALUE_MAP,
    _SYR_CONNECT_SENSOR_GETT1_VALUE_MAP,
    _SYR_CONNECT_SENSOR_GETUL_VALUE_MAP,
    _SYR_CONNECT_SENSOR_GETWHU_VALUE_MAP,
    _SYR_CONNECT_SENSOR_ICON,
    _SYR_CONNECT_SENSOR_STATE_CLASS,
    _SYR_CONNECT_SENSOR_STRING,
    _SYR_CONNECT_SENSOR_UNIT,
    _SYR_CONNECT_SENSOR_UNIT_PRECISION,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import (
    build_device_info,
    build_entity_id,
    clean_sensor_value,
    extract_flow_value,
)

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the API
PARALLEL_UPDATES = 1


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
            for excluded_key in _SYR_CONNECT_SENSOR_EXCLUDED:
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
            if key in _SYR_CONNECT_SENSOR_EXCLUDED:
                continue

            # Special logic for getCS1/2/3:
            # These sensors represent the remaining resin capacity in percent (getCSx),
            # while getSVx represents the salt amount in kg for the same compartment.
            # By default, sensors in _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_ZERO are hidden if their value is 0.
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
            elif key in _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_ZERO:
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
        if sensor_key in _SYR_CONNECT_SENSOR_DIAGNOSTIC:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        # Set unit of measurement for water hardness sensors dynamically
        if sensor_key in ("getIWH", "getOWH"):
            # Try to get WHU value from device status
            whu_value = None
            for device in coordinator.data.get('devices', []):
                if device['id'] == device_id:
                    whu_value = device.get('status', {}).get('getWHU')
                    break
            if whu_value is not None:
                try:
                    self._attr_native_unit_of_measurement = _SYR_CONNECT_SENSOR_GETWHU_VALUE_MAP.get(int(whu_value), None)
                except (ValueError, TypeError):
                    self._attr_native_unit_of_measurement = None
            else:
                self._attr_native_unit_of_measurement = None
        elif sensor_key in _SYR_CONNECT_SENSOR_UNIT:
            self._attr_native_unit_of_measurement = _SYR_CONNECT_SENSOR_UNIT[sensor_key]

        # Set suggested display precision if available
        if sensor_key in _SYR_CONNECT_SENSOR_UNIT_PRECISION:
            self._attr_suggested_display_precision = _SYR_CONNECT_SENSOR_UNIT_PRECISION[sensor_key]

        # Set device class if available
        if sensor_key in _SYR_CONNECT_SENSOR_DEVICE_CLASS:
            self._attr_device_class = _SYR_CONNECT_SENSOR_DEVICE_CLASS[sensor_key]

        # Set state class if available
        if sensor_key in _SYR_CONNECT_SENSOR_STATE_CLASS:
            self._attr_state_class = _SYR_CONNECT_SENSOR_STATE_CLASS[sensor_key]

        # Set icon if available
        if sensor_key in _SYR_CONNECT_SENSOR_ICON:
            self._attr_icon = _SYR_CONNECT_SENSOR_ICON[sensor_key]

        # Store base icon for state-based icon changes
        self._base_icon = getattr(self, '_attr_icon', None)

        # Disable sensors by default based on configuration
        # Also disable sensors that are represented by control entities so they
        # are available if users explicitly enable them, but do not clutter the UI.
        if sensor_key in ("getIPA", "getDGW", "getMAC") or sensor_key in _SYR_CONNECT_SENSOR_DISABLED_BY_DEFAULT:
            self._attr_entity_registry_enabled_default = False

        # Build device info from coordinator data
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

    def _apply_numeric_conversion(self, value: float) -> float | int:
        """Apply sensor-specific unit conversion and precision.

        Args:
            value: The raw numeric value

        Returns:
            The converted value with appropriate precision
        """
        # Apply sensor-specific conversions
        if self._sensor_key == 'getPRS':
            # Divide pressure by 10 to convert from "dbar" to "bar"
            value = value / 10
        elif self._sensor_key == 'getCEL':
            # getCEL values are provided as 1/10 °C (e.g. 110 -> 11.0°C)
            value = value / 10

        # Apply configured precision if available
        precision = _SYR_CONNECT_SENSOR_UNIT_PRECISION.get(self._sensor_key)
        if precision is not None:
            try:
                value = round(value, precision)
                if precision == 0:
                    return int(value)
            except (TypeError, ValueError):
                pass

        return value

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
            mapped = _SYR_CONNECT_SENSOR_GETALM_VALUE_MAP.get(str(raw_value))
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
                    if isinstance(val, datetime):
                        ival = int(val.timestamp())
                    else:
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

        # Dynamic icon for valve shut-off (getAB)
        if self._sensor_key == "getAB":
            val = self.native_value
            if val is None:
                return self._base_icon
            # Values: 1=open, 2=closed
            if str(val) == "1":
                return "mdi:valve-open"
            elif str(val) == "2":
                return "mdi:valve-closed"
            return self._base_icon

        # Dynamic icon for valve status (getVLV)
        if self._sensor_key == "getVLV":
            val = self.native_value
            if val is None:
                return self._base_icon
            # Values: 10=closed, 11=closing, 20=open, 21=opening
            if str(val) == "10":
                return "mdi:valve-closed"
            elif str(val) == "11":
                return "mdi:valve"  # closing in progress
            elif str(val) == "20":
                return "mdi:valve-open"
            elif str(val) == "21":
                return "mdi:valve"  # opening in progress
            return self._base_icon

        # Dynamic icon for pressure sensor availability (getPST)
        if self._sensor_key == "getPST":
            try:
                val = self.native_value
                # native_value may be numeric or string; normalize to int when possible
                if val is None:
                    return self._base_icon
                try:
                    if isinstance(val, datetime):
                        ival = int(val.timestamp())
                    else:
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

        # Dynamic icon for battery voltage (getBAT)
        if self._sensor_key == "getBAT":
            val = self.native_value
            if val is None:
                return self._base_icon
            # Normalize to string and try converting to float once.
            sval = str(val).strip()
            try:
                if float(sval) == 0:
                    return "mdi:battery-alert-variant-outline"
            except (TypeError, ValueError):
                pass

        # Return base icon for all other sensors
        return self._base_icon

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state of the sensor."""
        for device in self.coordinator.data.get('devices', []):
            if device['id'] == self._device_id:
                status = device.get('status', {})

                # Defensive: always set value before use in string sensors
                value = status.get(self._sensor_key) if self._sensor_key in status else None

                # Special handling for getVOL: clean prefix like 'Vol[L]6530' -> '6530'
                if self._sensor_key == 'getVOL' and value is not None:
                    value = clean_sensor_value(value)

                # Special handling for current flow rate (getAVO)
                # Format: "1655mL" - extract numeric value
                if self._sensor_key == 'getAVO':
                    if value is None or value == "":
                        return None
                    return extract_flow_value(value)

                # Special handling for pressure sensor (getBAR) - Safe-T+ device
                # Format: "4077 mbar" - extract numeric value and convert to bar
                if self._sensor_key == 'getBAR':
                    if value is None or value == "":
                        return None
                    try:
                        # Extract integer value from string like "4077 mbar"
                        match = re.search(r'\d+', str(value))
                        if not match:
                            return None
                        pressure_mbar = float(match.group())
                        # Convert mbar to bar (divide by 1000)
                        pressure_bar = pressure_mbar / 1000
                        # Apply configured precision
                        precision = _SYR_CONNECT_SENSOR_UNIT_PRECISION.get(self._sensor_key, 3)
                        return round(pressure_bar, precision)
                    except (ValueError, TypeError):
                        return None

                # TEST: Override getSTA value for manual testing
                #if self._sensor_key == 'getSTA':
                    #status['getSTA'] = "Płukanie regenerantem (587mA)"
                    #status['getSTA'] = "Płukanie szybkie 1"
                    #status['getSTA'] = "Płukanie wsteczne"

                # Special handling for battery voltage (getBAT) - Safe-T+ device
                # Format: "6,12 4,38 3,90" where first value is battery voltage in V
                if self._sensor_key == 'getBAT':
                    if value is None or value == "":
                        return None
                    try:
                        # Extract first value from space-separated string
                        first_value = str(value).split()[0]
                        # Replace comma with dot for proper float conversion
                        voltage = float(first_value.replace(',', '.'))
                        # Apply configured precision
                        precision = _SYR_CONNECT_SENSOR_UNIT_PRECISION.get(self._sensor_key, 2)
                        return round(voltage, precision)
                    except (ValueError, TypeError, IndexError):
                        return None

                # Special handling for leakage protection absent level (getUL)
                # Format: "5" -> multiply by 10 to get liters (5 -> 50L)
                if self._sensor_key == 'getUL':
                    if value is None or value == "":
                        return None
                    try:
                        volume_value = float(value) * 10
                        return int(volume_value)
                    except (ValueError, TypeError):
                        return None

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
                    if isinstance(value, int | float):
                        return _SYR_CONNECT_SENSOR_GETWHU_VALUE_MAP.get(int(value), None)
                    elif isinstance(value, str):
                        try:
                            return _SYR_CONNECT_SENSOR_GETWHU_VALUE_MAP.get(int(value), None)
                        except (ValueError, TypeError):
                            return None
                    return None

                # Special handling for last regeneration timestamp (getLAR): convert unix seconds to datetime object
                if self._sensor_key == 'getLAR':
                    if value is None or value == "":
                        # Return default datetime: 1970-01-01 00:00:00+00:00
                        return None
                    try:
                        ts = int(float(value))
                        # Return an aware datetime object (UTC). Home Assistant
                        # will format this according to the user's timezone/locale.
                        return datetime.fromtimestamp(ts, UTC)
                    except (ValueError, TypeError, OverflowError):
                        return None

                # Special handling for regeneration permitted weekdays (getRPW):
                # The device returns a bitmask where bit 1 = Monday, bit 2 = Tuesday, ... bit 7 = Sunday.
                # - mask == 0 -> "Anytime"
                # - other masks -> comma-separated short weekday names using strftime('%a')
                if self._sensor_key == 'getRPW':
                    raw_mask = status.get('getRPW')
                    if raw_mask is None or raw_mask == "":
                        return None
                    try:
                        mask = int(float(raw_mask))
                    except (ValueError, TypeError):
                        try:
                            mask = int(str(raw_mask).strip())
                        except Exception:
                            return None

                    if mask == 0:
                        return None

                    parts: list[str] = []
                    # Localize short weekday names using the Home Assistant language setting.
                    # Use a reference Monday date so weekday offsets map correctly.
                    ref_monday = datetime(2024, 1, 1)
                    locale = None
                    try:
                        locale = getattr(self.hass.config, "language", None)
                    except Exception:
                        locale = None

                    for idx in range(7):
                        if mask & (1 << idx):
                            try:
                                name = format_datetime(ref_monday + timedelta(days=idx), "EEE", locale=locale)
                            except Exception:
                                # Fallback to system short name if Babel/localization fails
                                name = (ref_monday + timedelta(days=idx)).strftime("%a")
                            parts.append(name)

                    return ",".join(parts)

                # Special handling for status sensor (getSTA): map Polish strings to internal keys and set translation key.
                # NOTE: Translation placeholders are not supported for entity state strings in the frontend (they are only
                # available for entity names / labels). See: https://github.com/home-assistant/frontend/issues/29064
                if self._sensor_key == 'getSTA':
                    raw = str(status.get('getSTA') or "")
                    _LOGGER.debug("getSTA entity=%s device_id=%s raw=%s", self.entity_id, self._device_id, raw)

                    # Try known patterns and map to internal translation keys.
                    # Keep placeholder values local for debugging only (frontend
                    # states do not support placeholders).
                    m = re.match(r"Płukanie regenerantem \((.*?)\)", raw)
                    if m:
                        resistance_value = str(m.group(1) or "")
                        normalized = "Płukanie regenerantem"
                        mapped = str(_SYR_CONNECT_SENSOR_GETSTA_VALUE_MAP.get(normalized, "status_regenerant_rinse"))
                        self._attr_translation_key = mapped
                        _LOGGER.debug("getSTA mapped=%s placeholders=%s", mapped, {"resistance_value": resistance_value})
                        return mapped

                    m2 = re.match(r"Płukanie szybkie\s*(\d+)", raw)
                    if m2:
                        rinse_round = str(m2.group(1) or "")
                        normalized = "Płukanie rapide"
                        mapped = str(_SYR_CONNECT_SENSOR_GETSTA_VALUE_MAP.get(normalized, "status_fast_rinse"))
                        self._attr_translation_key = mapped
                        _LOGGER.debug("getSTA mapped=%s placeholders=%s", mapped, {"rinse_round": rinse_round})
                        return mapped

                    # Fallback: use raw string as normalized mapping key
                    normalized = raw
                    mapped = str(_SYR_CONNECT_SENSOR_GETSTA_VALUE_MAP.get(normalized, normalized))
                    self._attr_translation_key = mapped
                    _LOGGER.debug("getSTA mapped=%s", mapped)
                    return mapped

                # Special handling for alarm sensor: map raw API values to internal keys
                if self._sensor_key == 'getALM':
                    raw = str(status.get('getALM') or "")
                    mapped = str(_SYR_CONNECT_SENSOR_GETALM_VALUE_MAP.get(raw))
                    self._attr_translation_key = mapped if mapped is not None else value
                    # Return mapped key (e.g. 'no_salt', 'low_salt', 'no_alarm') or raw value as fallback
                    return mapped if mapped is not None else (value if value is not None else None)

                # Special handling for getLE sensor: map raw API values to display values
                if self._sensor_key == 'getLE':
                    raw = str(status.get('getLE') or "")
                    mapped = str(_SYR_CONNECT_SENSOR_GETLE_VALUE_MAP.get(raw))
                    # Return mapped display value (e.g. '100', '150', etc.) or raw value as fallback
                    return mapped if mapped is not None else (raw if raw else None)

                # Special handling for getUL sensor: map raw API values to display values
                if self._sensor_key == 'getUL':
                    raw = str(status.get('getUL') or "")
                    mapped = str(_SYR_CONNECT_SENSOR_GETUL_VALUE_MAP.get(raw))
                    # Return mapped display value (e.g. '10', '20', etc.) or raw value as fallback
                    return mapped if mapped is not None else (raw if raw else None)

                # Special handling for getT1 and getT2 sensors: map raw API values to display values
                if self._sensor_key in ('getT1', 'getT2'):
                    raw = str(status.get(self._sensor_key) or "")
                    mapped = _SYR_CONNECT_SENSOR_GETT1_VALUE_MAP.get(raw)
                    # Return mapped display value (e.g. '0.5', '1.0', etc.) or raw value as fallback
                    return str(mapped) if mapped is not None else (raw if raw else None)

                # Keep certain sensors as strings (version, serial, MAC, etc.)
                if self._sensor_key in _SYR_CONNECT_SENSOR_STRING:
                    _LOGGER.debug("String sensor key: %s, value: %s", self._sensor_key, value)
                    return str(value) if value is not None else None

                # Try to convert to number if possible for other sensors
                if isinstance(value, str):
                    try:
                        numeric_value = float(value)
                        return self._apply_numeric_conversion(numeric_value)
                    except (ValueError, TypeError):
                        return value

                # Handle numeric values directly
                if isinstance(value, int | float):
                    return self._apply_numeric_conversion(float(value))

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
