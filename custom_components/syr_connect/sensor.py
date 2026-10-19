"""Sensor platform for SYR Connect."""

from collections.abc import Callable
import contextlib
from datetime import UTC, datetime, timedelta
import logging
import re
from typing import Any, override

from babel.dates import format_datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    _SYR_CONNECT_SENSOR_ALM_VALUE_MAP,
    _SYR_CONNECT_SENSOR_BAT_VALUE_PERCENTAGE,
    _SYR_CONNECT_SENSOR_BINARY,
    _SYR_CONNECT_SENSOR_CRS_VALUE_MAP,
    _SYR_CONNECT_SENSOR_DEVICE_CLASS,
    _SYR_CONNECT_SENSOR_DIAGNOSTIC,
    _SYR_CONNECT_SENSOR_DISABLED_BY_DEFAULT,
    _SYR_CONNECT_SENSOR_EXCLUDED,
    _SYR_CONNECT_SENSOR_KNOWN_KEYS,
    _SYR_CONNECT_SENSOR_LE_VALUE_MAP,
    _SYR_CONNECT_SENSOR_STA_VALUE_MAP,
    _SYR_CONNECT_SENSOR_STATE_CLASS,
    _SYR_CONNECT_SENSOR_STRING,
    _SYR_CONNECT_SENSOR_T1_VALUE_MAP,
    _SYR_CONNECT_SENSOR_UL_VALUE_MAP,
    _SYR_CONNECT_SENSOR_UNIT,
    _SYR_CONNECT_SENSOR_UNIT_PRECISION,
    _SYR_CONNECT_SENSOR_WHU_VALUE_MAP,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .entity import SyrConnectEntity
from .helpers import (
    find_entity_id,
    get_model_known_keys,
    get_sensor_ab_value,
    get_sensor_ala_map,
    get_sensor_avo_value,
    get_sensor_bat_value,
    get_sensor_iwh_value,
    get_sensor_lng_value,
    get_sensor_net_value,
    get_sensor_not_map,
    get_sensor_rtm_value,
    get_sensor_vol_value,
    get_sensor_wrn_map,
    is_sensor_visible,
    is_value_true,
    registry_cleanup,
)
from .models import detect_model

_LOGGER = logging.getLogger(__name__)

# Leak-protection boolean flags getPAx, getPBx, getPMx, getPWx (not getPRx: numeric return times)
_SYR_CONNECT_SENSOR_LEAK_PROTECTION_FLAG = re.compile(r"^getP(?:A|B|M|W)\d$")

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

    # Remove previously-registered entities that are no longer valid.
    # registry_cleanup also handles conditionally hidden sensors internally.
    registry_cleanup(
        hass,
        coordinator.data,
        "sensor",
        allowed_keys=_SYR_CONNECT_SENSOR_KNOWN_KEYS - _SYR_CONNECT_SENSOR_EXCLUDED,
        entry_id=coordinator.entry_id,
    )

    # Registry handle used for per-group removals below
    registry = er.async_get(hass)

    entities: list[SensorEntity] = []

    _LOGGER.debug(
        "Setting up sensors for %d device(s)", len(coordinator.data.get("devices", []))
    )

    for device in coordinator.data.get("devices", []):
        device_id = device["id"]
        device_name = device["name"]
        status = device.get("status", {})

        # Scope the sensor allowlist to the detected model (falls back to the
        # global allowlist for models that haven't opted into per-model key lists).
        model_info = detect_model(status)
        known_sensor_keys = get_model_known_keys(
            model_info, "sensor", _SYR_CONNECT_SENSOR_KNOWN_KEYS
        )

        _LOGGER.debug(
            "Device %s (%s) has %d status values", device_name, device_id, len(status)
        )

        # Only create the connection state sensor when the API provides a "dst" value
        if status.get("dst") is not None:
            entities.append(
                SyrConnectConnectionStateSensor(
                    coordinator,
                    device_id,
                    device_name,
                )
            )

        # Handle leak-protection groups controlled by getPA1..getPA8
        group_entities, handled_keys = _build_pa_group_sensors(
            coordinator, registry, device_id, device_name, status, known_sensor_keys
        )
        entities.extend(group_entities)
        sensor_count = len(group_entities)

        # Create sensors for all status values
        for key, value in status.items():
            if not _is_sensor_wanted(
                status, key, value, known_sensor_keys, handled_keys
            ):
                continue
            _LOGGER.debug(
                "Creating sensor: device=%s key=%s value=%r", device_id, key, value
            )
            entities.append(
                SyrConnectSensor(
                    coordinator,
                    device_id,
                    device_name,
                    key,
                )
            )
            sensor_count += 1

        _LOGGER.debug("Created %d sensor(s) for device %s", sensor_count, device_name)

    _LOGGER.debug("Adding %d sensor(s) total", len(entities))
    async_add_entities(entities)

    _async_setup_muco_conditional_sensors(hass, entry, coordinator, async_add_entities)


def _build_pa_group_sensors(
    coordinator: SyrConnectDataUpdateCoordinator,
    registry: er.EntityRegistry,
    device_id: str,
    device_name: str,
    status: dict[str, Any],
    known_sensor_keys: set[str],
) -> tuple[list[SensorEntity], set[str]]:
    """Create or remove the leak-protection profile sensors controlled by getPA1..getPA8.

    If getPAx evaluates to true, the sensors getPVx, getPTx, getPFx, getPMx, getPWx, getPBx
    and getPRx are created. If getPAx evaluates to false, they are removed from the registry
    if present.

    Returns:
        The created sensors and the group keys handled here, which are skipped afterwards.
    """
    entities: list[SensorEntity] = []
    handled_keys: set[str] = set()

    for idx in range(1, 9):
        pa_key = f"getPA{idx}"
        pa_val = status.get(pa_key)
        group_keys = [
            f"getPA{idx}",
            f"getPV{idx}",
            f"getPT{idx}",
            f"getPF{idx}",
            f"getPN{idx}",
            f"getPM{idx}",
            f"getPW{idx}",
            f"getPB{idx}",
            f"getPR{idx}",
        ]

        try:
            if is_value_true(pa_val):
                # Create entities for group keys — only if the key is actually present in
                # status AND allowed for this model (per-model allowlist takes precedence).
                for gk in group_keys:
                    # Avoid duplicates when iterating over status later
                    handled_keys.add(gk)
                    if gk not in known_sensor_keys:
                        _LOGGER.debug(
                            "Skipping PA group sensor (not in allowlist): device=%s key=%s",
                            device_id,
                            gk,
                        )
                        continue
                    if gk not in status:
                        _LOGGER.debug(
                            "Skipping PA group sensor (not in status): device=%s key=%s",
                            device_id,
                            gk,
                        )
                        continue
                    _LOGGER.debug(
                        "Creating sensor (PA group): device=%s key=%s", device_id, gk
                    )
                    entities.append(
                        SyrConnectSensor(
                            coordinator,
                            device_id,
                            device_name,
                            gk,
                        )
                    )
            elif status:
                # Remove group sensors from entity registry when the PA flag is false or missing
                # (Pontos Base reports the profile keys without any getPAx; they are not shown).
                # Skipped for an empty status: it was not fetched yet (temporary failure at
                # startup), which says nothing about the profiles, like in registry_cleanup.
                for gk in group_keys:
                    try:
                        # Found by unique_id, so a renamed or "_2"-suffixed sensor is removed as well
                        stale_entity_id = find_entity_id(
                            registry, "sensor", coordinator.entry_id, device_id, gk
                        )
                        if stale_entity_id is not None:
                            _LOGGER.debug(
                                "Removing sensor due to getPA=false: %s",
                                stale_entity_id,
                            )
                            registry.async_remove(stale_entity_id)
                    except RuntimeError:
                        _LOGGER.exception(
                            "Failed to remove sensor %s for device %s", gk, device_id
                        )
                    # Ensure group keys are marked as handled so they are not recreated
                    # later when iterating over status.items().
                    handled_keys.add(gk)
        except ValueError, KeyError, AttributeError, TypeError:
            _LOGGER.exception(
                "Error handling getPA group %s for device %s", pa_key, device_id
            )

    return entities, handled_keys


def _to_float(value: Any) -> float | None:
    """Return the value as float, or None if it is missing or not a number."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError, TypeError:
        return None


def _is_sensor_wanted(
    status: dict[str, Any],
    key: str,
    value: Any,
    known_sensor_keys: set[str],
    handled_keys: set[str],
) -> bool:
    """Return True if the status value gets a regular sensor entity."""
    # Allowlist check: the definitive list of keys this integration handles.
    # Anything not listed here is ignored unconditionally, regardless of
    # what other checks follow. This takes precedence over all other logic.
    if key not in known_sensor_keys:
        _LOGGER.debug("Skipping unknown sensor key %s (not in allowlist)", key)
        return False

    # Exclusion check: skip keys that are explicitly excluded.
    if key in _SYR_CONNECT_SENSOR_EXCLUDED:
        _LOGGER.debug("Skipping excluded sensor key %s", key)
        return False

    # Skip keys that are handled as binary sensors, dst (a dedicated
    # SyrConnectConnectionStateSensor) and keys already handled by the getPA group logic.
    # getLOT/getOHW are mutually exclusive depending on getCRT and are handled
    # dynamically (_async_setup_muco_conditional_sensors) so the applicable
    # one can be added/removed live without an integration reload.
    if (
        key in _SYR_CONNECT_SENSOR_BINARY
        or key == "dst"
        or key in handled_keys
        or key in ("getLOT", "getOHW")
    ):
        return False

    # Centralized visibility check
    if not is_sensor_visible(status, key, value):
        return False

    # Special: only create getSRO sensor when the reported value is an integer
    if key == "getSRO":
        number = _to_float(value)
        if number is None or not number.is_integer():
            return False

    # Special: only create getFFM sensor when the reported value is >= 1
    if key == "getFFM":
        number = _to_float(value)
        if number is None or number < 1:
            return False

    return isinstance(value, int | float | str)


def _async_setup_muco_conditional_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: SyrConnectDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Dynamically add/remove the getLOT/getOHW sensor depending on the cartridge type.

    Mirrors _async_setup_muco_conditional_selects in select.py: getLOT (HVE/HVE+) and
    getOHW (HWE) are mutually exclusive based on getCRT. registry_cleanup() only runs
    once at setup, so without this listener the inapplicable diagnostic sensor would
    stay registered and show as permanently greyed-out "unavailable" after the user
    changes the cartridge type live (e.g. via the getCRT select), instead of being
    removed. Re-evaluated on every coordinator update.
    """
    live_keys: dict[str, set[str]] = {}

    def _wanted_key(status: dict[str, Any]) -> str | None:
        crt = str(status.get("getCRT") or "").strip()
        if crt in ("1", "2") and status.get("getLOT") not in (None, ""):
            key = "getLOT"
        elif crt == "0" and status.get("getOHW") not in (None, ""):
            key = "getOHW"
        else:
            return None
        # Only for models that list the key (MuCo filling). Leak-protection and TrioLock devices
        # also report getCRT/getLOT/getOHW but deliberately do not expose them.
        known_sensor_keys = get_model_known_keys(
            detect_model(status), "sensor", _SYR_CONNECT_SENSOR_KNOWN_KEYS
        )
        return key if key in known_sensor_keys else None

    @callback
    def _sync() -> None:
        new_entities: list[SyrConnectSensor] = []
        try:
            registry = er.async_get(hass)
            for device in coordinator.data.get("devices", []):
                device_id = device.get("id")
                if not device_id:
                    continue
                device_name = device.get("name", device_id)
                status = device.get("status", {})
                current = live_keys.setdefault(device_id, set())
                wanted = _wanted_key(status)
                wanted_set = {wanted} if wanted else set()

                for key in current - wanted_set:
                    stale_entity_id = find_entity_id(
                        registry, "sensor", coordinator.entry_id, device_id, key
                    )
                    if stale_entity_id is not None:
                        _LOGGER.debug(
                            "Removing conditionally hidden sensor from registry: %s",
                            stale_entity_id,
                        )
                        registry.async_remove(stale_entity_id)
                    current.discard(key)

                for key in wanted_set - current:
                    new_entities.append(
                        SyrConnectSensor(coordinator, device_id, device_name, key)
                    )
                    current.add(key)
        except Exception:
            _LOGGER.exception("Failed to sync conditional MuCo sensor(s)")
            return

        if new_entities:
            _LOGGER.debug("Adding %d conditional MuCo sensor(s)", len(new_entities))
            async_add_entities(new_entities)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))


class SyrConnectSensor(SyrConnectEntity, SensorEntity):
    """Representation of a SYR Connect sensor."""

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
    ) -> None:
        """Initialize the sensor."""
        # The translation_key (set by the base class from sensor_key) is fixed for the entity's
        # lifetime: it names the entity ("entity.sensor.<key>.name") and its state values are
        # translated under "entity.sensor.<key>.state.<value>". native_value only returns the
        # state key (e.g. "no_alarm"); it must not change the translation_key.
        super().__init__(coordinator, device_id, device_name, "sensor", sensor_key)

        self._sensor_key = sensor_key

        # Set entity category for diagnostic sensors
        if sensor_key in _SYR_CONNECT_SENSOR_DIAGNOSTIC:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        # Set unit of measurement for water hardness sensors dynamically
        if sensor_key in ("getIWH", "getOWH"):
            # Try to get WHU value from device status
            whu_value = self._status.get("getWHU")
            if whu_value is not None:
                try:
                    self._attr_native_unit_of_measurement = (
                        _SYR_CONNECT_SENSOR_WHU_VALUE_MAP.get(int(whu_value), None)
                    )
                except ValueError, TypeError:
                    self._attr_native_unit_of_measurement = None
            else:
                self._attr_native_unit_of_measurement = None
        elif sensor_key in _SYR_CONNECT_SENSOR_UNIT:
            self._attr_native_unit_of_measurement = _SYR_CONNECT_SENSOR_UNIT[sensor_key]

        # Set suggested display precision if available
        if sensor_key in _SYR_CONNECT_SENSOR_UNIT_PRECISION:
            self._attr_suggested_display_precision = _SYR_CONNECT_SENSOR_UNIT_PRECISION[
                sensor_key
            ]

        # Set device class if available
        if sensor_key in _SYR_CONNECT_SENSOR_DEVICE_CLASS:
            self._attr_device_class = _SYR_CONNECT_SENSOR_DEVICE_CLASS[sensor_key]

        # Set state class if available
        if sensor_key in _SYR_CONNECT_SENSOR_STATE_CLASS:
            self._attr_state_class = _SYR_CONNECT_SENSOR_STATE_CLASS[sensor_key]

        # Disable sensors by default based on configuration
        # Also disable sensors that are represented by control entities so they
        # are available if users explicitly enable them, but do not clutter the UI.
        if (
            sensor_key in ("getIPA", "getDGW", "getMAC")
            or sensor_key in _SYR_CONNECT_SENSOR_DISABLED_BY_DEFAULT
        ):
            self._attr_entity_registry_enabled_default = False

        # Override getBAT attributes for devices that report battery as percentage (e.g. SafeFloor TYP=120)
        if sensor_key == "getBAT":
            typ = str(self._status.get("getTYP", "") or "").strip()
            if typ in _SYR_CONNECT_SENSOR_BAT_VALUE_PERCENTAGE:
                self._attr_native_unit_of_measurement = PERCENTAGE
                self._attr_device_class = SensorDeviceClass.BATTERY
                self._attr_suggested_display_precision = 0

        # Cache last non-None native value to avoid writing None when API omits values
        self._last_native_value: str | int | float | datetime | None = None

    def _apply_numeric_conversion(self, value: float) -> float | int:
        """Apply sensor-specific unit conversion and precision.

        Args:
            value: The raw numeric value

        Returns:
            The converted value with appropriate precision
        """
        # Apply sensor-specific conversions
        if self._sensor_key in ("getCEL", "getMIT", "getMXT"):
            # Values are provided as 1/10 °C (e.g. 110 -> 11.0°C, -40 -> -4.0°C)
            value = value / 10
        elif self._sensor_key in ("getPRS", "getTPR"):
            # Values are provided in 1/10 units (e.g. dbar to bar)
            value = value / 10
        elif self._sensor_key == "getLOT":
            # Value is in steps of 10 µS/cm (e.g. 7 -> 70 µS/cm)
            value = value * 10
        elif self._sensor_key == "getVOL":
            # API provides total volume in liters; convert to cubic meters (m³)
            with contextlib.suppress(ZeroDivisionError, TypeError):
                value = value / 1000

        # Apply configured precision if available
        precision = _SYR_CONNECT_SENSOR_UNIT_PRECISION.get(self._sensor_key)
        if precision is not None:
            try:
                value = round(value, precision)
                if precision == 0:
                    return int(value)
            except TypeError, ValueError:
                pass

        return value

    @property
    @override
    def icon(self) -> str | None:
        """Return the getBAT icon; all other icons and state icons come from icons.json.

        In percentage mode the BATTERY device class provides the icon, in voltage mode a
        dead battery (0 V) is flagged.
        """
        if (
            self._sensor_key != "getBAT"
            or self._attr_device_class == SensorDeviceClass.BATTERY
        ):
            return None

        val = self.native_value
        if val is not None:
            try:
                if float(str(val).strip()) == 0:
                    return "mdi:battery-alert-variant-outline"
            except TypeError, ValueError:
                pass
        return "mdi:battery"

    @property
    @override
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state of the sensor.

        Wrapper around `_compute_native_value()` that caches the last
        non-None value. If the API omits the `getXYZ` field (i.e. returns
        `None`), the last known non-None value is returned to avoid
        storing `None` in the entity state.
        """
        computed = self._compute_native_value()
        if computed is not None:
            self._last_native_value = computed
            return computed
        return getattr(self, "_last_native_value", None)

    def _compute_native_value(self) -> str | int | float | datetime | None:
        """Compute the native value from the device status.

        Keys with a special format or a value map have a handler in `_SYR_CONNECT_SENSOR_VALUE_HANDLERS`
        (or are leak-protection flags, see `_SYR_CONNECT_SENSOR_LEAK_PROTECTION_FLAG`). All other keys are
        returned as string (`_SYR_CONNECT_SENSOR_STRING`) or as converted number.
        """
        device = self._device
        if device is None:
            return None
        status = device.get("status", {})
        value = status.get(self._sensor_key)

        # Log missing sensor data (API omitted field or returned None/empty)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            _LOGGER.debug(
                "Missing sensor data for device=%s (%s) sensor=%s value=%r",
                self._device_name,
                self._device_id,
                self._sensor_key,
                value,
            )

        handler = self._SYR_CONNECT_SENSOR_VALUE_HANDLERS.get(self._sensor_key)
        if handler is None and _SYR_CONNECT_SENSOR_LEAK_PROTECTION_FLAG.match(
            self._sensor_key
        ):
            handler = SyrConnectSensor._value_leak_protection_flag
        if handler is not None:
            return handler(self, status, value)

        # Clean prefix like 'Vol[L]6530' -> '6530', then continue as a number
        if self._sensor_key == "getVOL" and value is not None:
            value = get_sensor_vol_value(value)

        # Keep certain sensors as strings (version, serial, MAC, etc.)
        if self._sensor_key in _SYR_CONNECT_SENSOR_STRING:
            _LOGGER.debug("String sensor key: %s, value: %s", self._sensor_key, value)
            return str(value) if value is not None else None

        # Try to convert to number if possible for other sensors
        if isinstance(value, str):
            try:
                numeric_value = float(value)
                return self._apply_numeric_conversion(numeric_value)
            except ValueError, TypeError:
                return value

        # Handle numeric values directly
        if isinstance(value, int | float):
            return self._apply_numeric_conversion(float(value))

        # None, or a type a sensor cannot show (e.g. a list)
        return None

    # --- Value handlers -------------------------------------------------------------
    # Each handler gets the device status and the raw value of the sensor key and returns
    # the native value.

    @staticmethod
    def _map_code(status: dict[str, Any], raw: Any, mapper: Any) -> str | None:
        """Map an alarm/notification/warning code to its translation key, else the raw code."""
        if raw is None:
            return None
        try:
            mapped, raw_code = mapper(status, raw)
            if mapped:
                return str(mapped)
            # Model unknown or no mapping found: return the raw value 1:1
            sval = str(raw_code)
            return sval if sval.strip() != "" else None
        except ValueError, KeyError, AttributeError, TypeError:
            return None

    def _value_ab(self, status: dict[str, Any], value: Any) -> Any:
        """Valve shut-off (getAB): lowercase "true"/"false" for translations."""
        ab = get_sensor_ab_value(status)
        if ab is None:
            return None
        return "true" if ab else "false"

    def _value_ala(self, status: dict[str, Any], value: Any) -> Any:
        """Alarm code (getALA): translation key based on the device model."""
        return self._map_code(status, value, get_sensor_ala_map)

    def _value_not(self, status: dict[str, Any], value: Any) -> Any:
        """Notification code (getNOT): translation key."""
        return self._map_code(status, value, get_sensor_not_map)

    def _value_wrn(self, status: dict[str, Any], value: Any) -> Any:
        """Warning code (getWRN): translation key."""
        return self._map_code(status, value, get_sensor_wrn_map)

    def _value_alm(self, status: dict[str, Any], value: Any) -> Any:
        """Alarm (getALM): model-aware mapping like getALA, then the static getALM value map."""
        raw_str = str(value) if value is not None else ""
        try:
            ala_mapped, _ = get_sensor_ala_map(status or {}, value)
        except ValueError, KeyError, AttributeError, TypeError:
            ala_mapped = None
        std_mapped = _SYR_CONNECT_SENSOR_ALM_VALUE_MAP.get(raw_str.strip().upper())
        mapped = ala_mapped or std_mapped
        # Mapped key (e.g. 'no_salt', 'low_salt', 'no_alarm') or the raw value as fallback
        return mapped if mapped is not None else value

    def _value_avo(self, status: dict[str, Any], value: Any) -> Any:
        """Current flow rate (getAVO): "1655mL" -> numeric value."""
        if value is None or value == "":
            return None
        return get_sensor_avo_value(value)

    def _value_bar(self, status: dict[str, Any], value: Any) -> Any:
        """Pressure (getBAR / getBAR2, Safe-T+ / TRIO Lock): "4077 mbar" -> bar."""
        if value is None or value == "":
            return None
        try:
            match = re.search(r"\d+", str(value))
            if not match:
                return None
            pressure_bar = float(match.group()) / 1000
            precision = _SYR_CONNECT_SENSOR_UNIT_PRECISION.get(self._sensor_key, 3)
            return round(pressure_bar, precision)
        except ValueError, TypeError:
            return None

    def _value_bat(self, status: dict[str, Any], value: Any) -> Any:
        """Battery (getBAT).

        Formats: Safe-T+ ("6,11 4,38 3,90" -> 6.11 V), Trio DFR/LS ("363" -> 3.63 V),
        SafeFloor TYP=120 ("85" -> 85 %).
        """
        if value is None:
            return None
        if not isinstance(value, (str | int | float)):
            return None
        # SafeFloor (and similar) report battery as an integer percentage.
        if self._attr_native_unit_of_measurement == PERCENTAGE:
            try:
                return int(float(str(value).strip()))
            except ValueError, TypeError:
                return None
        return get_sensor_bat_value(value)

    def _value_dbd(self, status: dict[str, Any], value: Any) -> Any:
        """Microleakage pressure drop (getDBD): tenths of a bar ("10" -> 1.0 bar)."""
        if value is None or value == "":
            return None
        try:
            match = re.search(r"-?\d+", str(value))
            if not match:
                return None
            pressure_bar = float(match.group()) / 10.0
            precision = _SYR_CONNECT_SENSOR_UNIT_PRECISION.get(self._sensor_key, 1)
            return round(pressure_bar, precision)
        except ValueError, TypeError:
            return None

    def _value_iwh(self, status: dict[str, Any], value: Any) -> Any:
        """Incoming water hardness (getIWH): explicit getIWH, otherwise derived from getCND."""
        return get_sensor_iwh_value(status or {})

    def _value_net(self, status: dict[str, Any], value: Any) -> Any:
        """Mains voltage (getNET).

        Formats: Safe-T+ ("ADC:950 6,16V" -> 6.16 V), Safe-Tech+ ("11,86" -> 11.86 V),
        Trio DFR/LS ("363" -> 3.63 V).
        """
        if value is None:
            return None
        if not isinstance(value, (str | int | float)):
            return None
        return get_sensor_net_value(value)

    def _value_lar(self, status: dict[str, Any], value: Any) -> Any:
        """Last regeneration (getLAR): unix seconds -> aware UTC datetime."""
        if value is None or value == "":
            return None
        try:
            # Home Assistant formats it according to the user's timezone/locale.
            return datetime.fromtimestamp(int(float(value)), UTC)
        except ValueError, TypeError, OverflowError:
            return None

    @staticmethod
    def _map_int(value_map: dict[int, Any], value: Any, default: int) -> Any:
        """Look up a raw integer value in a value map.

        A missing, empty or 0 value uses `default`. A value that is not an integer
        returns None instead of raising, so a broken device value does not break the
        sensor update (native_value then keeps the last known value).
        """
        try:
            return value_map.get(int(value or default))
        except ValueError, TypeError:
            return None

    def _value_le(self, status: dict[str, Any], value: Any) -> Any:
        """getLE: raw value -> display value."""
        return self._map_int(_SYR_CONNECT_SENSOR_LE_VALUE_MAP, value, 2)

    def _value_lng(self, status: dict[str, Any], value: Any) -> Any:
        """Language (getLNG): strip a trailing annotation, "0 (0=Deutsch 1=English)" -> "0"."""
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        return get_sensor_lng_value(value)

    def _value_leak_protection_flag(self, status: dict[str, Any], value: Any) -> Any:
        """Leak-protection flags (getPAx, getPBx, getPMx, getPWx): "true"/"false" like getAB.

        getPRx are numeric return-time values and are not matched (see _SYR_CONNECT_SENSOR_LEAK_PROTECTION_FLAG).
        """
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        return "true" if is_value_true(value) else "false"

    def _value_rtm(self, status: dict[str, Any], value: Any) -> Any:
        """Regeneration time (getRTM): "HH:MM" from getRTM, or combined from getRTH + getRTM."""
        return get_sensor_rtm_value(status)

    def _value_rpw(self, status: dict[str, Any], value: Any) -> Any:
        """Regeneration permitted weekdays (getRPW): bitmask, bit 1 = Monday ... bit 7 = Sunday.

        0 -> "0" ("Not specified" translation key), otherwise comma-separated localized
        short weekday names.
        """
        if value is None or value == "":
            return None
        try:
            mask = int(float(value))
        except ValueError, TypeError:
            try:
                mask = int(str(value).strip())
            except ValueError, TypeError:
                return None

        if mask == 0:
            return "0"

        # Localize with the Home Assistant language; a reference Monday maps the weekday offsets.
        ref_monday = datetime(2024, 1, 1)
        try:
            locale = getattr(self.hass.config, "language", None)
        except AttributeError:
            locale = None

        parts: list[str] = []
        for idx in range(7):
            if mask & (1 << idx):
                day = ref_monday + timedelta(days=idx)
                try:
                    name = format_datetime(day, "EEE", locale=locale)
                except ValueError, KeyError, AttributeError, TypeError:
                    # Fallback to system short name if Babel/localization fails
                    name = day.strftime("%a")
                parts.append(name)
        return ",".join(parts)

    def _value_sta(self, status: dict[str, Any], value: Any) -> Any:
        """Status (getSTA): map the Polish status strings to translation keys.

        Translation placeholders are not supported for entity states in the frontend (only
        for names/labels), see https://github.com/home-assistant/frontend/issues/29064, so
        the placeholder values are only logged.
        """
        # Newer models (e.g. Syr AC 3200/3228) report getSTA as an integer (0=Standby);
        # check for None explicitly so a genuine 0 is kept.
        raw = str(value) if value is not None else ""
        _LOGGER.debug(
            "getSTA entity=%s device_id=%s raw=%s", self.entity_id, self._device_id, raw
        )

        m_match = re.match(r"Płukanie regenerantem \((.*?)\)", raw)
        if m_match:
            mapped = str(
                _SYR_CONNECT_SENSOR_STA_VALUE_MAP.get(
                    "Płukanie regenerantem", "status_regenerant_rinse"
                )
            )
            _LOGGER.debug(
                "getSTA mapped=%s placeholders=%s",
                mapped,
                {"resistance_value": str(m_match.group(1) or "")},
            )
            return mapped

        m2_match = re.match(r"Płukanie szybkie\s*(\d+)", raw)
        if m2_match:
            mapped = str(
                _SYR_CONNECT_SENSOR_STA_VALUE_MAP.get(
                    "Płukanie rapide", "status_fast_rinse"
                )
            )
            _LOGGER.debug(
                "getSTA mapped=%s placeholders=%s",
                mapped,
                {"rinse_round": str(m2_match.group(1) or "")},
            )
            return mapped

        # Fallback: use the raw string as mapping key
        mapped = str(_SYR_CONNECT_SENSOR_STA_VALUE_MAP.get(raw, raw))
        _LOGGER.debug("getSTA mapped=%s", mapped)
        return mapped

    def _value_t(self, status: dict[str, Any], value: Any) -> Any:
        """getT1 / getT2: raw value -> display value."""
        return self._map_int(_SYR_CONNECT_SENSOR_T1_VALUE_MAP, value, 1)

    def _value_ul(self, status: dict[str, Any], value: Any) -> Any:
        """getUL: raw value -> display value."""
        return self._map_int(_SYR_CONNECT_SENSOR_UL_VALUE_MAP, value, 1)

    def _value_crs(self, status: dict[str, Any], value: Any) -> Any:
        """Cartridge size (getCRS): raw value -> liters."""
        if value is None or value == "":
            return None
        try:
            raw = int(float(value))
        except ValueError, TypeError:
            return None
        return _SYR_CONNECT_SENSOR_CRS_VALUE_MAP.get(raw)

    def _value_crt(self, status: dict[str, Any], value: Any) -> Any:
        """Cartridge type (getCRT): empty means "no cartridge"; translation keys cannot be "", so "none"."""
        if value is None or value == "":
            return "none"
        return str(value)

    def _value_rcd(self, status: dict[str, Any], value: Any) -> Any:
        """Filling period (getRCD): empty means "undefined"; translation keys cannot be ""."""
        if value is None or value == "":
            return "undefined"
        return str(value)

    def _value_whu(self, status: dict[str, Any], value: Any) -> Any:
        """Water hardness unit (getWHU): raw value -> unit."""
        if isinstance(value, int | float):
            return _SYR_CONNECT_SENSOR_WHU_VALUE_MAP.get(int(value), None)
        if isinstance(value, str):
            try:
                return _SYR_CONNECT_SENSOR_WHU_VALUE_MAP.get(int(value), None)
            except ValueError, TypeError:
                return None
        return None

    _SYR_CONNECT_SENSOR_VALUE_HANDLERS: dict[
        str,
        Callable[
            [SyrConnectSensor, dict[str, Any], Any], str | int | float | datetime | None
        ],
    ] = {
        "getAB": _value_ab,
        "getALA": _value_ala,
        "getALM": _value_alm,
        "getAVO": _value_avo,
        "getBAR": _value_bar,
        "getBAR2": _value_bar,
        "getBAT": _value_bat,
        "getCRS": _value_crs,
        "getCRT": _value_crt,
        "getDBD": _value_dbd,
        "getIWH": _value_iwh,
        "getLAR": _value_lar,
        "getLE": _value_le,
        "getLNG": _value_lng,
        "getNET": _value_net,
        "getNOT": _value_not,
        "getRCD": _value_rcd,
        "getRPW": _value_rpw,
        "getRTM": _value_rtm,
        "getSTA": _value_sta,
        "getT1": _value_t,
        "getT2": _value_t,
        "getUL": _value_ul,
        "getWHU": _value_whu,
        "getWRN": _value_wrn,
    }


class SyrConnectConnectionStateSensor(SyrConnectEntity, SensorEntity):
    """Sensor for the device connection state (virtual 'dst' field).

    Always available so Home Assistant can always show the connectivity state,
    even when the coordinator cannot reach the device.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the connection state sensor."""
        super().__init__(coordinator, device_id, device_name, "sensor", "dst")

    @property
    @override
    def native_value(self) -> str | None:
        """Return the raw dst value as a string (translation key)."""
        dst = self._status.get("dst")
        if dst is None:
            return None
        try:
            return str(int(dst))
        except TypeError, ValueError:
            return str(dst)

    @property
    @override
    def available(self) -> bool:
        """Always available so the connection state is always shown."""
        return True
