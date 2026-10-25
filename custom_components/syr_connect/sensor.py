"""Sensor platform for SYR Connect."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
import re
from typing import Any, Literal, override

from babel.dates import format_datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfConductivity,
    UnitOfElectricPotential,
    UnitOfMass,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .binary_sensor import _SYR_CONNECT_BINARY_SENSOR_SUPPORTED_KEYS
from .const import (
    _SYR_CONNECT_SENSOR_ALM_VALUE_MAP,
    _SYR_CONNECT_SENSOR_BAT_VALUE_PERCENTAGE,
    _SYR_CONNECT_SENSOR_CRS_VALUE_MAP,
    _SYR_CONNECT_SENSOR_LE_VALUE_MAP,
    _SYR_CONNECT_SENSOR_STA_VALUE_MAP,
    _SYR_CONNECT_SENSOR_T1_VALUE_MAP,
    _SYR_CONNECT_SENSOR_UL_VALUE_MAP,
    _SYR_CONNECT_SENSOR_WHU_VALUE_MAP,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .data import SyrConnectDevice
from .entity import SyrConnectEntity, async_add_device_entities
from .helpers import (
    find_entity_id,
    get_device_model,
    get_model_supported_keys,
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
    is_empty_ip,
    is_value_true,
    registry_cleanup,
)
from .models import SyrConnectModel

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the API
PARALLEL_UPDATES = 1


# --- Value handlers -------------------------------------------------------------
# The `value_fn` of a sensor description. Each handler gets the sensor, the device status
# and the raw value of the sensor key and returns the native value.


def _map_code(model: SyrConnectModel, raw: Any, mapper: Any) -> str | None:
    """Map an alarm/notification/warning code to its translation key, else the raw code."""
    if raw is None:
        return None
    try:
        mapped, raw_code = mapper(model, raw)
        if mapped:
            return str(mapped)
        # Model unknown or no mapping found: return the raw value 1:1
        sval = str(raw_code)
        return sval if sval.strip() != "" else None
    except ValueError, KeyError, AttributeError, TypeError:
        return None


def _value_ab(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Valve shut-off (getAB): lowercase "true"/"false" for translations."""
    ab = get_sensor_ab_value(status)
    if ab is None:
        return None
    return "true" if ab else "false"


def _value_ala(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Alarm code (getALA): translation key based on the device model."""
    return _map_code(sensor.device_model, value, get_sensor_ala_map)


def _value_not(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Notification code (getNOT): translation key."""
    return _map_code(sensor.device_model, value, get_sensor_not_map)


def _value_wrn(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Warning code (getWRN): translation key."""
    return _map_code(sensor.device_model, value, get_sensor_wrn_map)


def _value_alm(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Alarm (getALM): model-aware mapping like getALA, then the static getALM value map.

    Without a mapping the raw value is shown. The alarm memory loses its "Alarms:"
    prefix; the "->" before the current alarm stays, it marks the newest entry:
    - SafeTech: "Alarms:->A4 A4 AF AF A3 AF A3 AF" -> "->A4 A4 AF AF A3 AF A3 AF"
    - Safe-T+: "Alarms: A5 A5 A6 ->A6 A5 A5 A5 A5" -> "A5 A5 A6 ->A6 A5 A5 A5 A5"
    """
    raw_str = str(value) if value is not None else ""
    try:
        ala_mapped, _ = get_sensor_ala_map(sensor.device_model, value)
    except ValueError, KeyError, AttributeError, TypeError:
        ala_mapped = None
    std_mapped = _SYR_CONNECT_SENSOR_ALM_VALUE_MAP.get(raw_str.strip().upper())
    mapped = ala_mapped or std_mapped
    # Mapped key (e.g. 'no_salt', 'low_salt', 'no_alarm') or the raw value as fallback
    if mapped is not None:
        return mapped
    if isinstance(value, str) and value.startswith("Alarms:"):
        return value.removeprefix("Alarms:").lstrip()
    return value


def _value_avo(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Current flow rate (getAVO): "1655mL" -> numeric value."""
    if value is None or value == "":
        return None
    return get_sensor_avo_value(value)


def _value_bar(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Pressure (getBAR / getBAR2, Safe-T+ / TRIO Lock): "4077 mbar" -> bar."""
    if value is None or value == "":
        return None
    try:
        match = re.search(r"\d+", str(value))
        if not match:
            return None
        pressure_bar = float(match.group()) / 1000
        precision = sensor.entity_description.suggested_display_precision
        return round(pressure_bar, 3 if precision is None else precision)
    except ValueError, TypeError:
        return None


def _value_bat(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Battery (getBAT).

    Formats:
    - Safe-T+: "6,11 4,38 3,90" -> 6.11 V
    - Trio DFR/LS: "363" -> 3.63 V
    - SafeFloor TYP=120: "85" -> 85 %
    """
    if value is None:
        return None
    if not isinstance(value, (str | int | float)):
        return None
    # SafeFloor (and similar) report battery as an integer percentage.
    if sensor.native_unit_of_measurement == PERCENTAGE:
        try:
            return int(float(str(value).strip()))
        except ValueError, TypeError, OverflowError:
            return None
    return get_sensor_bat_value(value)


def _value_cyt(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Remaining regeneration cycle time (getCYT): raw value -> minutes.

    Formats:
    - NeoSoft, Sanibel UNO, Conel Clear Pro Soft: 45 -> 45 min
    - LEX, L20: "12:30" (minutes:seconds) -> 12.5 min
    """
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str) and ":" in value:
            minutes, seconds = value.strip().split(":")
            return int(minutes) + int(seconds) / 60
        return int(float(value))
    except ValueError, TypeError, OverflowError:
        return None


def _value_dbd(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Microleakage pressure drop (getDBD): tenths of a bar ("10" -> 1.0 bar)."""
    if value is None or value == "":
        return None
    try:
        match = re.search(r"-?\d+", str(value))
        if not match:
            return None
        pressure_bar = float(match.group()) / 10.0
        precision = sensor.entity_description.suggested_display_precision
        return round(pressure_bar, 1 if precision is None else precision)
    except ValueError, TypeError:
        return None


def _value_dtt(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Microleakage test time (getDTT): UTC "HH:MM" -> local "HH:MM".

    The device always stores the time in UTC. It is converted with the time zone of
    Home Assistant for today's date, so the shown time follows daylight saving time.

    Formats:
    - Germany, winter (CET): "04:00" -> "05:00"
    - Germany, summer (CEST): "04:00" -> "06:00"
    """
    try:
        hour, minute = (int(part) for part in str(value).strip().split(":"))
        utc_time = dt_util.utcnow().replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
    except ValueError, TypeError:
        return None
    return dt_util.as_local(utc_time).strftime("%H:%M")


def _value_iwh(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Incoming water hardness (getIWH): explicit getIWH, otherwise derived from getCND."""
    return get_sensor_iwh_value(status or {})


def _value_net(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Mains voltage (getNET).

    Formats:
    - Safe-T+: "ADC:950 6,16V" -> 6.16 V
    - Safe-Tech+: "11,86" -> 11.86 V
    - Trio DFR/LS: "363" -> 3.63 V
    """
    if value is None:
        return None
    if not isinstance(value, (str | int | float)):
        return None
    return get_sensor_net_value(value)


def _value_lar(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Last regeneration (getLAR): local time in seconds since 1970 -> aware datetime.

    The device counts its local wall time, not UTC (see docs/known_issues_xml_api.md,
    issue 5): 1792718160 is 23 October 2026 01:16 local time, not 01:16 UTC. The cloud
    reports the current UTC offset of the project (tzo), which is subtracted. The local
    JSON API reports no offset; there the time zone of Home Assistant is used.
    """
    if value is None or value == "":
        return None
    try:
        timestamp = int(float(value))
        # 0 means that no regeneration has happened yet.
        if timestamp == 0:
            return None
        utc_offset = sensor.device_utc_offset
        if utc_offset is not None:
            return datetime.fromtimestamp(timestamp - utc_offset, UTC)
        return datetime.fromtimestamp(timestamp, UTC).replace(
            tzinfo=dt_util.get_default_time_zone()
        )
    except ValueError, TypeError, OverflowError:
        return None


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


def _value_le(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Leak protection volume limit, present profile (getLE): raw value -> liters."""
    return _map_int(_SYR_CONNECT_SENSOR_LE_VALUE_MAP, value, 2)


def _value_lng(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Language (getLNG): strip a trailing annotation, "0 (0=Deutsch 1=English)" -> "0"."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    return get_sensor_lng_value(value)


def _value_leak_protection_flag(
    sensor: SyrConnectSensor, status: dict[str, Any], value: Any
) -> Any:
    """Leak-protection flags (getPAx, getPBx, getPMx, getPWx): "true"/"false" like getAB.

    getPRx are numeric return-time values and have no value_fn.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    return "true" if is_value_true(value) else "false"


def _value_rtm(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Regeneration time (getRTM): "HH:MM" from getRTM, or combined from getRTH + getRTM."""
    return get_sensor_rtm_value(status)


def _value_rpw(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Regeneration permitted weekdays (getRPW): bitmask, bit 1 = Monday ... bit 7 = Sunday.

    0 -> "0" ("Not specified" translation key), otherwise comma-separated localized
    short weekday names.
    """
    if value is None or value == "":
        return None
    try:
        mask = int(float(value))
    except ValueError, TypeError, OverflowError:
        try:
            mask = int(str(value).strip())
        except ValueError, TypeError:
            return None

    if mask == 0:
        return "0"

    # Localize with the Home Assistant language; a reference Monday maps the weekday offsets.
    ref_monday = datetime(2024, 1, 1)
    try:
        locale = getattr(sensor.hass.config, "language", None)
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


def _value_sta(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Status (getSTA): map the Polish status strings to translation keys.

    Translation placeholders are not supported for entity states in the frontend (only
    for names/labels), see https://github.com/home-assistant/frontend/issues/29064, so
    the placeholder values are only logged.
    """
    # Newer models (e.g. Syr AC 3200/3228) report getSTA as an integer (0=Standby);
    # check for None explicitly so a genuine 0 is kept.
    raw = str(value) if value is not None else ""
    _LOGGER.debug("getSTA entity=%s raw=%s", sensor.entity_id, raw)

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


def _value_t(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Maximum flow duration, present / absent profile (getT1 / getT2): raw value -> hours."""
    return _map_int(_SYR_CONNECT_SENSOR_T1_VALUE_MAP, value, 1)


def _value_tmz(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Time zone (getTMZ): offset in quarter hours -> "UTC+hh:mm".

    The device accepts -44..48 (UTC-11:00 to UTC+12:00 in steps of 15 minutes).

    Formats:
    - Germany (CET): "4" -> "UTC+01:00"
    - India: "22" -> "UTC+05:30"
    - Newfoundland: "-14" -> "UTC-03:30"
    """
    try:
        quarters = int(str(value).strip())
    except ValueError:
        return None
    if not -44 <= quarters <= 48:
        return None
    sign = "-" if quarters < 0 else "+"
    hours, minutes = divmod(abs(quarters) * 15, 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def _value_ul(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Leak protection volume limit, absent profile (getUL): raw value -> liters."""
    return _map_int(_SYR_CONNECT_SENSOR_UL_VALUE_MAP, value, 1)


def _value_crs(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Cartridge size (getCRS): raw value -> liters."""
    if value is None or value == "":
        return None
    try:
        raw = int(float(value))
    except ValueError, TypeError, OverflowError:
        return None
    return _SYR_CONNECT_SENSOR_CRS_VALUE_MAP.get(raw)


def _value_crt(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Cartridge type (getCRT): empty means "no cartridge"; translation keys cannot be "", so "none"."""
    if value is None or value == "":
        return "none"
    return str(value)


def _value_rcd(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Filling period (getRCD): empty means "undefined"; translation keys cannot be ""."""
    if value is None or value == "":
        return "undefined"
    return str(value)


def _value_whu(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Water hardness unit (getWHU): raw value -> unit."""
    if isinstance(value, int | float):
        return _SYR_CONNECT_SENSOR_WHU_VALUE_MAP.get(int(value), None)
    if isinstance(value, str):
        try:
            return _SYR_CONNECT_SENSOR_WHU_VALUE_MAP.get(int(value), None)
        except ValueError, TypeError:
            return None
    return None


def _value_vol(sensor: SyrConnectSensor, status: dict[str, Any], value: Any) -> Any:
    """Total volume (getVOL): strip a prefix like 'Vol[L]6530', then convert it as a number."""
    if value is not None:
        value = get_sensor_vol_value(value)
    return sensor.numeric_value(value)


@dataclass(frozen=True, kw_only=True)
class SyrConnectSensorEntityDescription(SensorEntityDescription):
    """Describes a SYR Connect sensor; `key` is the status key (e.g. "getFLO")."""

    # Return the value as string instead of converting it to a number (version, serial, MAC, ...);
    # not combined with value_fn, which computes the value itself
    keep_as_string: bool = False
    # Scale a numeric value before rounding, e.g. 1/10 °C -> °C (divide_by=10)
    divide_by: int = 1
    multiply_by: int = 1
    # Hide the sensor while its value is empty: "empty" (None or blank text) or "empty_ip"
    # (also the unspecified IP "0.0.0.0" or "::"). "always" never creates the entity; remove it in
    # the code once a device reports a useful value.
    hidden_when: Literal["empty", "empty_ip", "always"] | None = None
    # Compute the native value for keys with a special format or a value map
    value_fn: (
        Callable[
            [SyrConnectSensor, dict[str, Any], Any], str | int | float | datetime | None
        ]
        | None
    ) = None


# Descriptions of all known sensor keys.
#
# Only API keys listed here will become sensor entities. Any key returned by
# a firmware update that is not listed here is silently ignored.
_SYR_CONNECT_SENSOR_TYPES: tuple[SyrConnectSensorEntityDescription, ...] = (
    # --- Connectivity (virtual, always created) ---
    SyrConnectSensorEntityDescription(
        key="dst",  # Device connection state (0=never online, 1=offline, 2=online, 3=standby)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Valve & Flow ---
    SyrConnectSensorEntityDescription(
        key="getAB",  # Valve shutoff state (open / closed)
        value_fn=_value_ab,
    ),
    SyrConnectSensorEntityDescription(
        key="getAVO",  # Current instantaneous flow rate
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=1,
        value_fn=_value_avo,
    ),
    SyrConnectSensorEntityDescription(
        key="getFLO",  # Water flow rate (l/h)
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getVLV",  # Valve position (10=closed, 11=closing, 20=open, 21=opening)
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getCFO",  # Cycle flow offset, numeric counter
        suggested_display_precision=0,
        hidden_when="always",
    ),
    # --- Alarm / Notification / Warning ---
    SyrConnectSensorEntityDescription(
        key="getALA",  # Current alarm code
        value_fn=_value_ala,
    ),
    SyrConnectSensorEntityDescription(
        key="getALM",  # List of last alarms (e.g. low salt level)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_alm,
    ),
    SyrConnectSensorEntityDescription(
        key="getALN",  # List of last 8 notifications
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getALW",  # List of last 8 warnings
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getNOT",  # Current notification code
        entity_registry_enabled_default=False,
        value_fn=_value_not,
    ),
    SyrConnectSensorEntityDescription(
        key="getWRN",  # Current warning code
        value_fn=_value_wrn,
    ),
    # --- Pressure ---
    SyrConnectSensorEntityDescription(
        key="getBAR",  # Inlet pressure - mbar sensor (Safe-T+)
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
        value_fn=_value_bar,
        hidden_when="empty",  # value "" means sensor does not exists or not measured
    ),
    SyrConnectSensorEntityDescription(
        key="getBAR2",  # Outlet pressure - mbar sensor (SYR TRIO Lock Connect)
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
        value_fn=_value_bar,
    ),
    SyrConnectSensorEntityDescription(
        key="getPRS",  # Inlet pressure - bar sensor (LEXplus10SL)
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
        divide_by=10,
    ),
    # --- Voltage / Battery ---
    SyrConnectSensorEntityDescription(
        key="getBAP",  # Battery level (%)
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getBAT",  # Battery voltage (V) or battery level (%) - unit depends on device type
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=_value_bat,
    ),
    SyrConnectSensorEntityDescription(
        key="getNET",  # Mains (AC) voltage (V)
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=_value_net,
        hidden_when="empty",  # value "" means no mains voltage sensor present.
    ),
    # --- Water Quality ---
    SyrConnectSensorEntityDescription(
        key="getCEL",  # Temperature (°C)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        divide_by=10,
        hidden_when="empty",  # value "" means sensor does not exists or not measured.
    ),
    SyrConnectSensorEntityDescription(
        key="getCFT",  # Current filling duration (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getCND",  # Water conductivity (µS/cm)
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",  # value "" means sensor does not exists or not measured.
    ),
    SyrConnectSensorEntityDescription(
        key="getCNF",  # Conductivity factor (raw 5-50 -> 0.5-5.0)
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        divide_by=10,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getCFV",  # Current filling volume (l)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getHMD",  # Ambient humidity (%)
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getIWH",  # Incoming (raw) water hardness
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_iwh,
    ),
    SyrConnectSensorEntityDescription(
        key="getOWH",  # Outgoing (softened) water hardness
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWHU",  # Water hardness unit (°dH / °fH / ppm / mmol/l)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_whu,
    ),
    # --- Water Consumption & Volume ---
    SyrConnectSensorEntityDescription(
        key="getCOF",  # Total water consumption counter (l)
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getLTV",  # Last dispensed (tapped) volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getVOL",  # Total volume (m³)
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=3,
        divide_by=1000,
        value_fn=_value_vol,
    ),
    # --- Device Status ---
    SyrConnectSensorEntityDescription(
        key="getDFM",  # Device feature mode (device function type)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getSTA",  # Device operating status
        value_fn=_value_sta,
    ),
    # --- Resin Capacity ---
    SyrConnectSensorEntityDescription(
        key="getCS1",  # Remaining resin capacity - tank 1 (%)
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getCS2",  # Remaining resin capacity - tank 2 (%)
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getCS3",  # Remaining resin capacity - tank 3 (%)
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    # --- Salt ---
    SyrConnectSensorEntityDescription(
        key="getRDO",  # Salt dosing (g/l)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{UnitOfMass.GRAMS}/{UnitOfVolume.LITERS}",
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRE1",  # Reserve capacity - bottle 1 (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getRE2",  # Reserve capacity - bottle 2 (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getRES",  # Remaining softening capacity (l)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getSS1",  # Salt supply - container 1 (weeks)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.WEEKS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getSS2",  # Salt supply - container 2 (weeks)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.WEEKS,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getSS3",  # Salt supply - container 3 (weeks)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.WEEKS,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getSV1",  # Salt amount - container 1 (kg)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getSV2",  # Salt amount - container 2 (kg)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getSV3",  # Salt amount - container 3 (kg)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    # --- Regeneration ---
    SyrConnectSensorEntityDescription(
        key="getCYN",  # Regeneration cycle counter
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getCYT",  # Regeneration cycle time (remaining, min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_cyt,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getINR",  # Incomplete regeneration count
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getLAR",  # Timestamp of last regeneration
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_lar,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getNOR",  # Regeneration count (normal operation)
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRG1",  # Regeneration status (which tank is regenerating)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRG2",  # Regeneration running - tank 2 flag
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getRG3",  # Regeneration running - tank 3 flag
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getRMO",  # Regeneration mode (Standard / ECO / Power / Automatic)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Not tested: getRPD and getRTM have no influence on the NeoSoft 5000, which regenerates as
    # soon as a pillar is exhausted ("0" means no interval configured / no active
    # regeneration).
    SyrConnectSensorEntityDescription(
        key="getRPD",  # Regeneration interval (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getRPW",  # Regeneration permitted weekdays (bitmask)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_rpw,
    ),
    SyrConnectSensorEntityDescription(
        key="getRTI",  # Total regeneration cycle duration
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
        hidden_when="always",
    ),
    SyrConnectSensorEntityDescription(
        key="getRTM",  # Regeneration time (combined HH:MM string)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_rtm,
    ),
    SyrConnectSensorEntityDescription(
        key="getSRE",  # Regeneration active flag (0/1; values 3/5 unclear)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        hidden_when="always",
    ),
    SyrConnectSensorEntityDescription(
        key="getSCR",  # Service regeneration cycle count
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="always",
    ),
    SyrConnectSensorEntityDescription(
        key="getTOR",  # Total regeneration count (all time)
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Self-Learning Phase (Trio DFR/LS) ---
    SyrConnectSensorEntityDescription(
        key="getSLE",  # Remaining time in active self-learning phase (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSLF",  # Flow rate during self-learning phase (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSLO",  # Self-learning offset: volume/time surplus (%, 5-20)
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getSLP",  # Duration of self-learning phase
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="always",
    ),
    SyrConnectSensorEntityDescription(
        key="getSLT",  # Elapsed time in self-learning phase (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSLV",  # Volume accumulated in self-learning phase (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSMF",  # Self-learning minimum flow (l/h, 0-5000)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getSOF",  # Self-learning offset: maximum flow surplus (%, 5-50)
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",
    ),
    # --- Microleakage Test (Trio DFR/LS, SafeTech) ---
    SyrConnectSensorEntityDescription(
        key="getDBD",  # Microleakage test pressure drop
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_dbd,
    ),
    SyrConnectSensorEntityDescription(
        key="getDMA",  # Microleakage alarm mode (1=Warning, 2=Alarm)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getDRP",  # Microleakage test interval (daily / weekly / monthly)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getDSV",  # Microleakage test status (inactive / active / aborted / skipped)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getDTT",  # Microleakage test time (stored as UTC, shown as local time)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_dtt,
    ),
    SyrConnectSensorEntityDescription(
        key="getNPS",  # No turbine pulses since (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",  # value "" means sensor does not exist.
    ),
    # --- Leak Protection (LEXplus10SL / Trio DFR/LS) ---
    SyrConnectSensorEntityDescription(
        key="getLE",  # Leak protection volume limit - present profile (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_le,
    ),
    SyrConnectSensorEntityDescription(
        key="getLWT",  # Leakage warning threshold (%, 80-99)
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getT1",  # Max. flow duration - present profile (h, 0.5 h steps)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_t,
    ),
    SyrConnectSensorEntityDescription(
        key="getT2",  # Max. flow duration - absent profile (h, 0.5 h steps)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_t,
    ),
    SyrConnectSensorEntityDescription(
        key="getTMP",  # Leak protection temporarily deactivated - remaining time (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",  # value "" means sensor does not exists.
    ),
    SyrConnectSensorEntityDescription(
        key="getUL",  # Leak protection volume limit - absent profile (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_ul,
    ),
    # --- Leak Protection Profiles 1-8 (LEXplus10SL) ---
    SyrConnectSensorEntityDescription(
        key="getPA1",  # Profile 1 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA2",  # Profile 2 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA3",  # Profile 3 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA4",  # Profile 4 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA5",  # Profile 5 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA6",  # Profile 6 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA7",  # Profile 7 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA8",  # Profile 8 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB1",  # Profile 1 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB2",  # Profile 2 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB3",  # Profile 3 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB4",  # Profile 4 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB5",  # Profile 5 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB6",  # Profile 6 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB7",  # Profile 7 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB8",  # Profile 8 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF1",  # Profile 1 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF2",  # Profile 2 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF3",  # Profile 3 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF4",  # Profile 4 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF5",  # Profile 5 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF6",  # Profile 6 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF7",  # Profile 7 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF8",  # Profile 8 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM1",  # Profile 1 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM2",  # Profile 2 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM3",  # Profile 3 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM4",  # Profile 4 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM5",  # Profile 5 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM6",  # Profile 6 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM7",  # Profile 7 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM8",  # Profile 8 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN1",  # Profile 1 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN2",  # Profile 2 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN3",  # Profile 3 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN4",  # Profile 4 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN5",  # Profile 5 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN6",  # Profile 6 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN7",  # Profile 7 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN8",  # Profile 8 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR1",  # Profile 1 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR2",  # Profile 2 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR3",  # Profile 3 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR4",  # Profile 4 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR5",  # Profile 5 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR6",  # Profile 6 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR7",  # Profile 7 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR8",  # Profile 8 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT1",  # Profile 1 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT2",  # Profile 2 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT3",  # Profile 3 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT4",  # Profile 4 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT5",  # Profile 5 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT6",  # Profile 6 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT7",  # Profile 7 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT8",  # Profile 8 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV1",  # Profile 1 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV2",  # Profile 2 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV3",  # Profile 3 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV4",  # Profile 4 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV5",  # Profile 5 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV6",  # Profile 6 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV7",  # Profile 7 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV8",  # Profile 8 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW1",  # Profile 1 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW2",  # Profile 2 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW3",  # Profile 3 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW4",  # Profile 4 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW5",  # Profile 5 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW6",  # Profile 6 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW7",  # Profile 7 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW8",  # Profile 8 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_leak_protection_flag,
    ),
    SyrConnectSensorEntityDescription(
        key="getPRF",  # Currently active leak protection profile index
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getPRN",  # Duplicate of getPRF
        entity_registry_enabled_default=False,
        hidden_when="always",
    ),
    SyrConnectSensorEntityDescription(
        key="getPST",  # Pressure sensor installed (1=not available, 2=available)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # --- Filter (NeoSoft) ---
    SyrConnectSensorEntityDescription(
        key="getFCD",  # Filter flush interval (issue #23)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="always",
    ),
    SyrConnectSensorEntityDescription(
        key="getFCO",  # Iron content (ppm)
        native_unit_of_measurement="ppm",
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="always",
    ),
    SyrConnectSensorEntityDescription(
        key="getFFM",  # Filter type (backwash / replaceable / none)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Alarm / Thresholds (SafeFloor) ---
    SyrConnectSensorEntityDescription(
        key="getALD",  # Duration of alarm (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",  # value "" means sensor is broken, should be "0" to show 0s.
    ),
    SyrConnectSensorEntityDescription(
        key="getMIH",  # Minimum humidity threshold (%)
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMXH",  # Maximum humidity threshold (%)
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMIT",  # Minimum temperature threshold (1/10 °C)
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        divide_by=10,
    ),
    SyrConnectSensorEntityDescription(
        key="getMXT",  # Maximum temperature threshold (1/10 °C)
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        divide_by=10,
    ),
    # --- Intervals ---
    SyrConnectSensorEntityDescription(
        key="getRCP",  # Synchronisation interval (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWMP",  # Measurement interval (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Maintenance ---
    SyrConnectSensorEntityDescription(
        key="getDWF",  # Expected daily water consumption (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        hidden_when="always",
    ),
    SyrConnectSensorEntityDescription(
        key="getSRH",  # Next semi-annual maintenance (timestamp)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSRV",  # Next annual maintenance (timestamp)
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",  # if "" means no maintenance required, so not useful to show.
    ),
    SyrConnectSensorEntityDescription(
        key="getVS1",  # Volume threshold 1 (l)
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getVS2",  # Volume threshold 2 (l)
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getVS3",  # Volume threshold 3 (l)
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        hidden_when="empty",
    ),
    # --- Automatic Backwash (RSA) ---
    SyrConnectSensorEntityDescription(
        key="getCOA",  # Counter of automatic backwashes
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getCOM",  # Counter of manual backwashes
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRSA",  # Backwash interval (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRSD",  # Backwash duration (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRSE",  # Backwash reminder interval (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Lock / Connection Centre (TRIO Lock, SafeTech Lock, AC 3200, AC 3228) ---
    SyrConnectSensorEntityDescription(
        key="getLFT",  # Last refill duration (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getLFV",  # Last refilled volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getNMS",  # No valve movement since (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getNMT",  # Time until valve self-test becomes active (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getNPT",  # Time until alarm A8 "flow sensor fault" becomes active (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getNRT",  # No refill since (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getTRT",  # Cumulative refill time (s)
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getTRV",  # Cumulative refilled volume (l)
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Display ---
    SyrConnectSensorEntityDescription(
        key="getSRO",  # Display rotation / orientation (0 / 90 / 180 / 270 degrees)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # --- Device Info & Diagnostics ---
    SyrConnectSensorEntityDescription(
        key="getCNA",  # Device name
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getDGW",  # Gateway IP address
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getEGW",  # Ethernet (LAN) gateway
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty_ip",
    ),
    SyrConnectSensorEntityDescription(
        key="getEIP",  # Ethernet (LAN) IP address
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty_ip",
    ),
    SyrConnectSensorEntityDescription(
        key="getFIR",  # Firmware model identifier
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getIPA",  # IP address
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getLAN",  # Device language (0=English, 1=German, 3=Spanish) - Lex10 models only
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getLNG",  # Device language (0=Deutsch, 1=English) - other models
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_lng,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getMAC",  # MAC address
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getMAC1",  # Wi-Fi MAC address
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMAC2",  # LAN MAC address
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMAN",  # Manufacturer name
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getSRN",  # Device serial number
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getTMZ",  # Time zone (quarter hours, 4 = UTC+01:00)
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_tmz,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getTYP",  # Device type code
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        hidden_when="empty",  # value "" means sensor does not exists.
    ),
    SyrConnectSensorEntityDescription(
        key="getVER",  # Firmware version string
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    # --- Turbine / Pulse Monitoring (NeoSoft) ---
    SyrConnectSensorEntityDescription(
        key="getVPS1",  # No turbine pulses on control head 1 since (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getVPS2",  # No turbine pulses on control head 2 since (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        hidden_when="empty",
    ),
    # --- Wi-Fi ---
    SyrConnectSensorEntityDescription(
        key="getAPT",  # Access point timeout (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWFC",  # Wi-Fi SSID
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getWFR",  # Wi-Fi signal strength (%)
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getWFS",  # Wi-Fi connection status (not connected / connecting / connected)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWGW",  # Wi-Fi gateway
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty_ip",
    ),
    SyrConnectSensorEntityDescription(
        key="getWIP",  # Wi-Fi IP address
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty_ip",
    ),
    # --- Water treatment / Filling (Conel Clear Pro Fill) ---
    SyrConnectSensorEntityDescription(
        key="getCRS",  # Cartridge size (raw 1-5, mapped to liters)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_crs,
    ),
    SyrConnectSensorEntityDescription(
        key="getCRT",  # Cartridge type (0=HWE, 1=HVE, 2=HVE+)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_crt,
    ),
    SyrConnectSensorEntityDescription(
        key="getLOT",  # Maximum output conductivity (raw x10 µS/cm)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        multiply_by=10,
    ),
    SyrConnectSensorEntityDescription(
        key="getLRC",  # Liter(s) remaining softening capacity
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getOHW",  # Soft water hardness (°dH)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°dH",
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPRC",  # Percent remaining softening capacity
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRCC",  # Number of filling cycles in the current period (AC 3200, AC 3228)
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRCD",  # Filling processes period (0=hour, 1=day, 2=week, 3=month)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_rcd,
    ),
    SyrConnectSensorEntityDescription(
        key="getRCN",  # Counter of all refills (AC 3200, AC 3228)
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRMN",  # Filling processes count
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRMT",  # Maximum filling duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRVT",  # Maximum filling charges
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getTPR",  # Target pressure (1/10 bar)
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        divide_by=10,
    ),
)

_SYR_CONNECT_SENSOR_DESCRIPTIONS: dict[str, SyrConnectSensorEntityDescription] = {
    description.key: description for description in _SYR_CONNECT_SENSOR_TYPES
}

# Allowlist of known sensor keys, the global fallback for get_model_supported_keys()
_SYR_CONNECT_SENSOR_SUPPORTED_KEYS = set(_SYR_CONNECT_SENSOR_DESCRIPTIONS)


def is_sensor_visible(status: dict[str, Any], key: str, value: Any) -> bool:
    """Decide whether a reported status key/value should produce a sensor.

    This function centralizes all visibility/exclusion rules so both the
    entity-creation code and diagnostics produce the same set of visible
    sensors. It is intentionally defensive about input types and accepts
    values that may be strings, numbers, booleans or None.

    Rules (applied in order):
    - Group-controlled keys: keys matching getPVx, getPTx, getPFx, getPNx,
        getPMx, getPWx, getPBx, getPRx are only visible when the device's
        corresponding getPAx flag is truthy (1, "1", True, "true"; see `is_value_true`).
    - getLOT (Maximum output conductivity): only shown when getCRT (cartridge
        type) is "1" (HVE) or "2" (HVE+).
    - getOHW (Soft water hardness): only shown when getCRT (cartridge type)
        is "0" (HWE).
    - Empty values: the `hidden_when` of the key's description hides it when the
        reported value is None or a whitespace-only string ("empty"), or also the
        unspecified IP "0.0.0.0" or "::" ("empty_ip"). "always" hides it whatever the value.

    Args:
            status: The full flattened device status mapping (used for cross-key
                    checks such as getPAx and getCRT).
            key: The status key being considered (e.g. getWIP, getPV1).
            value: The raw value reported by the device for this key.

    Returns:
            True when the key/value should result in a sensor entity; False when
            the key should be suppressed according to the rules above.

    Examples:
            >>> is_sensor_visible(status, 'getWIP', '0.0.0.0')
            False
    """
    # Group keys controlled by getPAx should be hidden when getPAx is false
    m = re.match(r"get(PV|PT|PF|PN|PM|PW|PB|PR)([1-8])$", key)
    if m and not is_value_true(status.get(f"getPA{m.group(2)}")):
        return False

    if key == "getBAP" and _is_spurious_bap(status, value):
        return False

    crt_val = status.get("getCRT")
    crt = None if crt_val is None else str(crt_val).strip()
    # getLOT (Maximum output conductivity) only applies to HVE / HVE+ cartridges (getCRT 1 or 2).
    if key == "getLOT" and crt not in ("1", "2"):
        return False
    # getOHW (Soft water hardness) only applies to HWE cartridges (getCRT 0).
    if key == "getOHW" and crt != "0":
        return False

    return not _is_excluded_when_empty(key, value)


def _is_spurious_bap(status: dict[str, Any], value: Any) -> bool:
    """Return True if getBAP is a spurious field next to a real battery voltage.

    Firmware-bug workaround: getBAP is suppressed only when it is exactly 0/empty
    AND getBAT reports a non-zero voltage. In that case the device exposes a
    spurious percentage field alongside the real voltage reading.
    """
    try:
        bap_zero = float(value) == 0
    except ValueError, TypeError:
        bap_zero = value is None or str(value).strip() == ""
    if not bap_zero:
        return False
    bat_val = status.get("getBAT")
    if bat_val is None:
        return False
    try:
        return float(bat_val) > 0
    except ValueError, TypeError:
        return False


def _is_excluded_when_empty(key: str, value: Any) -> bool:
    """Return True if the key is hidden because its value counts as empty for this key."""
    description = _SYR_CONNECT_SENSOR_DESCRIPTIONS.get(key)
    hidden_when = description.hidden_when if description is not None else None
    if hidden_when == "always":
        return True
    if hidden_when == "empty":
        return value is None or (isinstance(value, str) and value.strip() == "")
    if hidden_when == "empty_ip":
        return is_empty_ip(value)
    return False


# Sensors that registry_cleanup removes while they are hidden: keys that never become an
# entity (hidden_when="always") and getLOT/getOHW, which depend on getCRT (cross-key rule
# in is_sensor_visible). A sensor hidden only because its own value is empty is not
# removed: removing it would drop its customizations (name, area, ...) whenever the
# value happens to be empty at startup.
_SYR_CONNECT_SENSOR_CONDITIONAL_KEYS = {
    description.key
    for description in _SYR_CONNECT_SENSOR_TYPES
    if description.hidden_when == "always"
} | {"getLOT", "getOHW"}


def _hidden_sensor_keys(status: dict[str, Any]) -> set[str]:
    """Return the conditional sensor keys that are hidden for the given device status."""
    return {
        key
        for key in _SYR_CONNECT_SENSOR_CONDITIONAL_KEYS
        if not is_sensor_visible(status, key, status.get(key))
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
        allowed_keys=_SYR_CONNECT_SENSOR_SUPPORTED_KEYS,
        entry_id=coordinator.entry_id,
        hidden_keys=_hidden_sensor_keys,
    )

    async_add_device_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda device: _build_device_sensors(hass, coordinator, device),
    )

    _async_setup_muco_conditional_sensors(hass, entry, coordinator, async_add_entities)


def _build_device_sensors(
    hass: HomeAssistant,
    coordinator: SyrConnectDataUpdateCoordinator,
    device: SyrConnectDevice,
) -> list[SensorEntity]:
    """Return the sensors of one device (except the conditional getLOT/getOHW)."""
    # Registry handle used for per-group removals below
    registry = er.async_get(hass)
    entities: list[SensorEntity] = []
    device_id = device["id"]
    device_name = device["name"]
    status = device.get("status", {})

    # Scope the sensor allowlist to the detected model (falls back to the
    # global allowlist for models that haven't opted into per-model key lists).
    model_info = get_device_model(device)
    supported_sensor_keys = get_model_supported_keys(
        model_info, "sensor", _SYR_CONNECT_SENSOR_SUPPORTED_KEYS
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
        coordinator, registry, device_id, device_name, status, supported_sensor_keys
    )
    entities.extend(group_entities)
    sensor_count = len(group_entities)

    # Create sensors for all status values
    for key, value in status.items():
        registered = (
            find_entity_id(registry, "sensor", coordinator.entry_id, device_id, key)
            is not None
        )
        if not _is_sensor_wanted(
            status, key, value, supported_sensor_keys, handled_keys, registered
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
    return entities


def _build_pa_group_sensors(
    coordinator: SyrConnectDataUpdateCoordinator,
    registry: er.EntityRegistry,
    device_id: str,
    device_name: str,
    status: dict[str, Any],
    supported_sensor_keys: set[str],
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
        group_keys = _pa_group_keys(idx)

        try:
            if is_value_true(pa_val):
                # Create entities for group keys — only if the key is actually present in
                # status AND allowed for this model (per-model allowlist takes precedence).
                for gk in group_keys:
                    # Avoid duplicates when iterating over status later
                    handled_keys.add(gk)
                    if gk not in supported_sensor_keys:
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


def _pa_group_keys(idx: int) -> list[str]:
    """Return the keys of leak-protection profile `idx` (1-8), controlled by getPA<idx>."""
    return [
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


def _muco_conditional_key(status: dict[str, Any], model: SyrConnectModel) -> str | None:
    """Return getLOT or getOHW, whichever applies to the cartridge type (getCRT), or None.

    Only for models that list the key (MuCo filling). Leak-protection and TrioLock devices
    also report getCRT/getLOT/getOHW but deliberately do not expose them.
    """
    crt_value = status.get("getCRT")
    crt = str(crt_value).strip() if crt_value is not None else ""
    if crt in ("1", "2") and status.get("getLOT") not in (None, ""):
        key = "getLOT"
    elif crt == "0" and status.get("getOHW") not in (None, ""):
        key = "getOHW"
    else:
        return None
    supported_sensor_keys = get_model_supported_keys(
        model, "sensor", _SYR_CONNECT_SENSOR_SUPPORTED_KEYS
    )
    return key if key in supported_sensor_keys else None


def sensor_keys_for_status(status: dict[str, Any], model: SyrConnectModel) -> list[str]:
    """Return the keys of the sensors the platform creates for a device status.

    Uses the same rules as the setup: the model's allowlist, the connection state (dst),
    the active leak-protection profiles (getPAx), the visibility and value checks of
    `_is_sensor_wanted` and the conditional getLOT/getOHW sensor.

    Args:
        status: The flattened device status
        model: The detected model of the device

    Returns:
        The sensor keys, in the order the setup creates them
    """
    supported_sensor_keys = get_model_supported_keys(
        model, "sensor", _SYR_CONNECT_SENSOR_SUPPORTED_KEYS
    )
    keys = ["dst"] if status.get("dst") is not None else []
    handled_keys: set[str] = set()
    for idx in range(1, 9):
        group_keys = _pa_group_keys(idx)
        handled_keys.update(group_keys)
        if is_value_true(status.get(f"getPA{idx}")):
            keys.extend(
                key
                for key in group_keys
                if key in supported_sensor_keys and key in status
            )
    keys.extend(
        key
        for key, value in status.items()
        if _is_sensor_wanted(status, key, value, supported_sensor_keys, handled_keys)
    )
    if (conditional_key := _muco_conditional_key(status, model)) is not None:
        keys.append(conditional_key)
    return keys


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
    supported_sensor_keys: set[str],
    handled_keys: set[str],
    registered: bool = False,
) -> bool:
    """Return True if the status value gets a regular sensor entity.

    A sensor that is already registered (`registered`) is created whatever its value,
    except for hidden_when="always". Otherwise it would stay registered without an entity
    (greyed out) until a restart with a value that passes the value rules.
    """
    # Allowlist check: the definitive list of keys this integration handles.
    # Anything not listed here is ignored unconditionally, regardless of
    # what other checks follow. This takes precedence over all other logic.
    if key not in supported_sensor_keys:
        _LOGGER.debug("Skipping unknown sensor key %s (not in allowlist)", key)
        return False

    # Skip keys that are handled as binary sensors, dst (a dedicated
    # SyrConnectConnectionStateSensor) and keys already handled by the getPA group logic.
    # getLOT/getOHW are mutually exclusive depending on getCRT and are handled
    # dynamically (_async_setup_muco_conditional_sensors) so the applicable
    # one can be added/removed live without an integration reload.
    if (
        key in _SYR_CONNECT_BINARY_SENSOR_SUPPORTED_KEYS
        or key == "dst"
        or key in handled_keys
        or key in ("getLOT", "getOHW")
    ):
        return False

    if registered:
        description = _SYR_CONNECT_SENSOR_DESCRIPTIONS.get(key)
        if description is not None and description.hidden_when == "always":
            return False
        return value is None or isinstance(value, int | float | str)

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

    @callback
    def _sync() -> None:
        new_entities: list[SyrConnectSensor] = []
        try:
            registry = er.async_get(hass)
            for device in (
                coordinator.data.get("devices", []) if coordinator.data else []
            ):
                device_id = device["id"]
                device_name = device["name"]
                status = device.get("status", {})
                current = live_keys.setdefault(device_id, set())
                wanted = _muco_conditional_key(status, get_device_model(device))
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

    entity_description: SyrConnectSensorEntityDescription

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
        self.entity_description = _SYR_CONNECT_SENSOR_DESCRIPTIONS[sensor_key]

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

        # Override getBAT attributes for devices that report battery as percentage (e.g. SafeFloor TYP=120).
        # The name follows the unit: "Battery level" like getBAP instead of "Battery voltage".
        if sensor_key == "getBAT":
            typ = str(self._status.get("getTYP", "") or "").strip()
            if typ in _SYR_CONNECT_SENSOR_BAT_VALUE_PERCENTAGE:
                self._attr_native_unit_of_measurement = PERCENTAGE
                self._attr_device_class = SensorDeviceClass.BATTERY
                self._attr_suggested_display_precision = 0
                self._attr_translation_key = "getbap"

        # Cache last non-None native value to avoid writing None when API omits values
        self._last_native_value: str | int | float | datetime | None = None

    def _apply_numeric_conversion(self, value: float) -> float | int:
        """Apply sensor-specific unit conversion and precision.

        Args:
            value: The raw numeric value

        Returns:
            The converted value with appropriate precision
        """
        # Apply the sensor-specific scale (e.g. 1/10 °C -> °C, liters -> m³)
        description = self.entity_description
        value = value / description.divide_by * description.multiply_by

        # Apply configured precision if available
        precision = self.entity_description.suggested_display_precision
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
        """Return the icon of a dead battery (getBAT, 0 V); all other icons come from icons.json.

        In percentage mode the BATTERY device class provides the icon.
        """
        if (
            self._sensor_key != "getBAT"
            or self.device_class == SensorDeviceClass.BATTERY
        ):
            return None

        val = self.native_value
        if val is not None:
            try:
                if float(str(val).strip()) == 0:
                    return "mdi:battery-alert-variant-outline"
            except TypeError, ValueError:
                pass
        return None

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

        Keys with a special format or a value map have a `value_fn` in their description. All
        other keys are returned as string (`keep_as_string`) or as converted number.
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

        value_fn = self.entity_description.value_fn
        if value_fn is not None:
            return value_fn(self, status, value)

        # Keep certain sensors as strings (version, serial, MAC, etc.)
        if self.entity_description.keep_as_string:
            _LOGGER.debug("String sensor key: %s, value: %s", self._sensor_key, value)
            return str(value) if value is not None else None

        return self.numeric_value(value)

    def numeric_value(self, value: Any) -> str | int | float | None:
        """Convert a raw value to a number with the sensor's scale and precision.

        Args:
            value: Raw value from the device status

        Returns:
            The converted number, the text itself if it is no number, or None for
            a missing value or a type a sensor cannot show (e.g. a list)
        """
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
