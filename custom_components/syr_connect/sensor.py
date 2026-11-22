"""Sensor platform for SYR Connect."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import logging
import math
import re
from typing import Any, Literal, override

from babel.dates import format_datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.sensor.const import NON_NUMERIC_DEVICE_CLASSES
from homeassistant.const import (
    UnitOfConductivity,
    UnitOfElectricPotential,
    UnitOfMass,
    UnitOfPressure,
    UnitOfRatio,
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

from .aiosyrconnect import (
    CAS_VALUE_MAP,
    LEAK_PROTECTION_PROFILES,
    T1_VALUE_MAP,
    UL_VALUE_MAP,
    SyrConnectStatus,
    SyrConnectStatusValue,
    get_ab_value,
    get_battery_level,
    get_crs_value,
    get_hardness_class,
    get_iwh_value,
    get_rtm_value,
    is_code_active,
    is_empty_ip,
    is_spurious_bap,
    is_value_true,
    parse_alarm_memory,
    parse_avo_value,
    parse_bat_value,
    parse_code_value,
    parse_cyt_value,
    parse_dbd_value,
    parse_dom_value,
    parse_float,
    parse_hygiene_module_value,
    parse_int,
    parse_lar_value,
    parse_le_value,
    parse_lng_value,
    parse_mbar_value,
    parse_net_value,
    parse_sta_value,
    parse_tmz_value,
    parse_utc_time,
    parse_vol_value,
    parse_weekday_mask,
    round_hardness,
    to_int,
)
from .binary_sensor import _SYR_CONNECT_BINARY_SENSOR_SUPPORTED_KEYS
from .coordinator import SyrConnectConfigEntry, SyrConnectDataUpdateCoordinator
from .data import SyrConnectDevice
from .entity import SyrConnectEntity, async_add_device_entities
from .helpers.device import get_device_model
from .helpers.profile import get_cartridge_entity_keys, get_model_supported_keys
from .helpers.registry import find_entity_id, registry_cleanup
from .models import SyrConnectModel

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the API
PARALLEL_UPDATES = 1


# --- Value handlers -------------------------------------------------------------
# The `value_fn` of a sensor description. Each handler gets the sensor, the device status
# and the raw value of the sensor key and returns the native value.


def _map_code(raw: Any, mapped: str | None, no_code: str) -> str | None:
    """Map an alarm/notification/warning code to its translation key, else the raw code.

    The meaning of the code for the model (`mapped`, from its code table) comes first. A value they do not know that means
    "no code" (`aiosyrconnect.is_code_active()`) is
    shown as no_code, e.g. the 255 of an acknowledgment over the JSON API, which the
    optimistic update shows until the device reports "FF". A blank value stays None.
    """
    if raw is None:
        return None
    if mapped:
        return mapped
    # A blank value stays a missing value (None), as before
    if str(raw).strip() != "" and not is_code_active(raw):
        return no_code
    # Model unknown or no mapping found: return the raw value 1:1
    sval = str(raw)
    return sval if sval.strip() != "" else None


def _value_ab(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Valve shut-off (getAB): lowercase "true"/"false" for translations."""
    ab = get_ab_value(status)
    if ab is None:
        return None
    return "true" if ab else "false"


def _value_ala(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Alarm code (getALA): translation key based on the device model."""
    return _map_code(value, sensor.device_model.alarm_meaning(value), "no_alarm")


def _value_not(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Notification code (getNOT): translation key."""
    return _map_code(
        value, sensor.device_model.notification_meaning(value), "no_notification"
    )


def _value_wrn(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Warning code (getWRN): translation key."""
    return _map_code(value, sensor.device_model.warning_meaning(value), "no_warning")


def _value_alm(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Alarm (getALM): model-aware mapping like getALA, else the alarm memory.

    The LEX family reports its current alarm here ("NoSalt", "LowSalt"), the alarm
    codes of the model map it. An empty value means no alarm. Without a mapping the
    raw value is shown, the alarm memory without its prefix (`parse_alarm_memory()`).
    """
    mapped = sensor.device_model.alarm_meaning(value)
    if mapped is not None:
        return mapped
    if value is None or str(value).strip() == "":
        return "no_alarm"
    return parse_alarm_memory(value)


def _value_avo(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Current flow rate (getAVO): "1655mL" -> numeric value."""
    return parse_avo_value(value)


def _value_bap(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Battery level (getBAP): the reported percentage, else computed from the voltages.

    Without getBAP the level follows the battery voltage (`get_battery_level()`).
    """
    if value is not None and not (isinstance(value, str) and value.strip() == ""):
        return sensor.numeric_value(value)
    return get_battery_level(status)


def _value_bar(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Pressure (getBAR / getBAR2 / getIBA): "4077 mbar" -> bar."""
    return parse_mbar_value(value)


def _value_bat(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Battery (getBAT).

    Formats:
    - Safe-T+: "6,11 4,38 3,90" -> 6.11 V
    - Trio DFR/LS: "363" -> 3.63 V
    - SafeFloor: "85" -> 85 %

    The unit is set from the model (`bat_in_percent`) in `SyrConnectSensor.__init__`.
    """
    if sensor.native_unit_of_measurement == UnitOfRatio.PERCENTAGE:
        return parse_int(value)
    return parse_bat_value(value)


def _value_cnd_class(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Water hardness range (getCND_class): range of the conductivity (getCND).

    The library estimates the range (`get_hardness_class()`): "soft", "medium" or
    "hard", the translation keys of the states.
    """
    return get_hardness_class(status)


def _value_cyt(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Remaining regeneration cycle time (getCYT): raw value -> minutes (`parse_cyt_value()`)."""
    return parse_cyt_value(value)


def _value_dbd(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Microleakage pressure drop (getDBD): tenths of a bar ("10" -> 1.0 bar)."""
    return parse_dbd_value(value)


def _value_dom(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Microleakage test valve open time (getDOM): raw value -> seconds (`parse_dom_value()`)."""
    return sensor.numeric_value(parse_dom_value(value))


def _value_dtt(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Microleakage test time (getDTT): UTC "HH:MM" -> local "HH:MM".

    The device always stores the time in UTC (`parse_utc_time()`). It is converted with
    the time zone of Home Assistant for today's date, so the shown time follows
    daylight saving time.

    Formats:
    - Germany, winter (CET): "04:00" -> "05:00"
    - Germany, summer (CEST): "04:00" -> "06:00"
    """
    utc_time = parse_utc_time(value)
    if utc_time is None:
        return None
    today = dt_util.utcnow().replace(
        hour=utc_time.hour, minute=utc_time.minute, second=0, microsecond=0
    )
    return dt_util.as_local(today).strftime("%H:%M")


def _value_iwh(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Incoming water hardness (getIWH): explicit getIWH, otherwise derived from getCND."""
    return sensor.numeric_value(get_iwh_value(status or {}))


def _value_net(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Mains voltage (getNET).

    Formats:
    - Safe-T+: "ADC:950 6,16V" -> 6.16 V
    - Safe-Tech+: "11,86" -> 11.86 V
    - Trio DFR/LS: "363" -> 3.63 V
    """
    return parse_net_value(value)


def _value_lar(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Last regeneration (getLAR): UNIX timestamp -> aware datetime (`parse_lar_value()`).

    The local timestamps of the LEX Plus are read in the time zone of Home Assistant,
    see docs/known_issues_xml_api.md, issue 5.
    """
    return parse_lar_value(sensor.device_model, value, dt_util.get_default_time_zone())


def _value_le(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Leak protection volume limit, present profile (getLE): raw step -> liters.

    The liters per step depend on the firmware (`parse_le_value`).
    """
    return parse_le_value(status, value)


def _value_lng(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Language (getLNG): strip a trailing annotation, "0 (0=Deutsch 1=English)" -> "0"."""
    return parse_lng_value(value)


def _value_leak_protection_flag(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Leak-protection flags (getPAx, getPBx, getPMx, getPWx): "true"/"false" like getAB.

    getPRx are numeric return-time values and have no value_fn.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    return "true" if is_value_true(value) else "false"


def _value_rtm(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Regeneration time (getRTM): "HH:MM" from getRTM, or combined from getRTH + getRTM."""
    return get_rtm_value(status)


def _value_rpw(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Regeneration permitted weekdays (getRPW): bitmask, bit 1 = Monday ... bit 7 = Sunday.

    0 -> "0" ("Not specified" translation key), otherwise comma-separated localized
    short weekday names.
    """
    mask = parse_weekday_mask(value)
    if mask is None:
        return None
    if mask == 0:
        return "0"

    try:
        language = getattr(sensor.hass.config, "language", None)
    except AttributeError:
        language = None
    return _weekday_names(mask, language)


def _weekday_names(mask: int, language: str | None) -> str:
    """Return the comma-separated short weekday names of a bitmask (bit 1 = Monday).

    Localized with the Home Assistant language; a reference Monday maps the weekday
    offsets. Babel takes "pt_BR", not the "pt-BR" of Home Assistant.
    """
    ref_monday = datetime(2024, 1, 1)
    locale = language.replace("-", "_") if language else None

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


def _value_sta(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Status (getSTA): reported text or code -> translation key.

    Translation placeholders are not supported for entity states in the frontend (only
    for names/labels), see https://github.com/home-assistant/frontend/issues/29064, so
    the details of the status are only logged.
    """
    mapped = parse_sta_value(value)
    _LOGGER.debug("getSTA entity=%s raw=%s mapped=%s", sensor.entity_id, value, mapped)
    return mapped


def _value_t(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Maximum flow duration, present / absent profile (getT1): raw code -> hours."""
    return parse_code_value(T1_VALUE_MAP, value)


def _value_tmz(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Time zone (getTMZ): offset in quarter hours -> "UTC+hh:mm" (`parse_tmz_value()`).

    Formats:
    - Germany (CET): "4" -> "UTC+01:00"
    - India: "22" -> "UTC+05:30"
    - Newfoundland: "-14" -> "UTC-03:30"
    """
    offset = parse_tmz_value(value)
    if offset is None:
        return None
    minutes = int(offset.total_seconds()) // 60
    sign = "-" if minutes < 0 else "+"
    hours, minutes = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def _value_ul(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Leak protection volume limit, absent profile (getUL): raw code -> liters."""
    return parse_code_value(UL_VALUE_MAP, value)


def _value_cas(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Canister size (getCAS, dosing pump): raw code -> liters.

    Formats:
    - Known size: "2" -> 10 L
    - Not defined: "0" -> None
    """
    return parse_code_value(CAS_VALUE_MAP, value)


def _value_hygiene_module(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Setting of a hygiene module line (getSCF, getCCF, ...): raw value -> number.

    Formats:
    - Without a suffix: "3" -> 3
    - With a suffix (assumed): "3 [1-7]" -> 3
    """
    number = parse_hygiene_module_value(value)
    return sensor.numeric_value(number) if number is not None else None


def _value_crs(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Cartridge size (getCRS): raw code -> liters (`get_crs_value()`).

    Formats:
    - Fixed size: "3" -> 7 L
    - Custom size (All-in-One+): "0" -> the liters of getFCS
    """
    return get_crs_value(status)


def _value_crt(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Cartridge type (getCRT): "none" for no cartridge (translation keys cannot be "").

    Formats:
    - Empty value: "" -> "none"
    - Water treatment off (getWTR): "2" -> "none"
    - Otherwise: "2" -> "2"
    """
    if (
        value is None
        or value == ""
        or sensor.device_model.is_water_treatment_off(status)
    ):
        return "none"
    return str(value)


def _value_rcd(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Filling period (getRCD): empty means "undefined"; translation keys cannot be ""."""
    if value is None or value == "":
        return "undefined"
    return str(value)


def _value_whu(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Water hardness unit (getWHU): raw value -> unit of the model's code family."""
    return sensor.device_model.whu_unit(value)


def _value_vol(
    sensor: SyrConnectSensor, status: SyrConnectStatus, value: SyrConnectStatusValue
) -> Any:
    """Total volume (getVOL): strip a prefix like 'Vol[L]6530', then convert it as a number."""
    return sensor.numeric_value(parse_vol_value(value))


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
            [SyrConnectSensor, SyrConnectStatus, SyrConnectStatusValue],
            str | int | float | datetime | None,
        ]
        | None
    ) = None


def _profile_descriptions(
    template: SyrConnectSensorEntityDescription,
) -> tuple[SyrConnectSensorEntityDescription, ...]:
    """Return the descriptions of one setting of the leak protection profiles 1-8.

    The eight profiles have the same settings, with the profile number appended to
    the key: getPA1-getPA8, getPV1-getPV8, ...

    Args:
        template: Description of the setting; its key is the key without the number
    """
    return tuple(
        replace(template, key=f"{template.key}{number}")
        for number in LEAK_PROTECTION_PROFILES
    )


# Descriptions of all known sensor keys.
#
# Only API keys listed here will become sensor entities. Any key returned by
# a firmware update that is not listed here is silently ignored.
_SYR_CONNECT_SENSOR_TYPES: tuple[SyrConnectSensorEntityDescription, ...] = (
    # --- Connectivity (virtual, created when the API reports dst) ---
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
        key="getAVO",  # Volume of the current water withdrawal
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=1,
        value_fn=_value_avo,
    ),
    SyrConnectSensorEntityDescription(
        key="getFLO",  # Water flow rate (l/h; LEX family reports l/min)
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
        value_fn=_value_not,
    ),
    SyrConnectSensorEntityDescription(
        key="getWRN",  # Current warning code
        value_fn=_value_wrn,
    ),
    # --- Pressure ---
    SyrConnectSensorEntityDescription(
        key="getBAR",  # Inlet pressure, system pressure on the All-in-One+ (mbar)
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
        value_fn=_value_bar,
        hidden_when="empty",  # value "" means sensor does not exist or is not measured
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
        key="getIBA",  # Inlet pressure - mbar sensor (All-in-One+)
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
        key="getBAP",  # Battery level (%), computed from getBAT/getBMA/getBMI without getBAP
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=0,
        value_fn=_value_bap,
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
        hidden_when="empty",  # value "" means sensor does not exist or is not measured.
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
        hidden_when="empty",  # value "" means sensor does not exist or is not measured.
    ),
    SyrConnectSensorEntityDescription(
        key="getLW1",  # Inlet conductivity (µS/cm, All-in-One+)
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getLW2",  # Outlet conductivity (µS/cm, All-in-One+)
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getCND_class",  # Water hardness range computed from getCND (SafeTech family)
        device_class=SensorDeviceClass.ENUM,
        options=[
            "soft",
            "medium",
            "hard",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_cnd_class,
    ),
    SyrConnectSensorEntityDescription(
        key="getCNF",  # Conductivity factor (raw 5-50 -> 0.5-5.0)
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        divide_by=10,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getCNL",  # Conductivity limit (µS/cm, 0=disabled, exceeding it triggers alarm AC)
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getCFV",  # Current filling volume (l)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=2,
    ),
    SyrConnectSensorEntityDescription(
        key="getHMD",  # Ambient humidity (%)
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
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
        key="getWHU",  # Water hardness unit (codes per device family, see WHU_UNITS_*)
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
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getCS2",  # Remaining resin capacity - tank 2 (%)
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getCS3",  # Remaining resin capacity - tank 3 (%)
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
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
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
        key="getDBT",  # Microleakage test pressure drop time (s, 1-15)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getDCM",  # Microleakage test valve closed time (min, 1-30)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getDMA",  # Microleakage alarm mode (0=Disabled, 1=Warning, 2=Alarm)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getDOM",  # Microleakage test valve open time (s, 1-60)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value_dom,
    ),
    SyrConnectSensorEntityDescription(
        key="getDPL",  # Microleakage test turbine pulses (3-99)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getDRP",  # Microleakage test interval (always / daily / weekly / monthly)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getDST",  # Microleakage test wait time without flow (min, 0=deactivated, 1-480)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getDSV",  # Microleakage test status (inactive / active / aborted / skipped)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getDTC",  # Microleakage test verification cycles (1-20)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
    SyrConnectSensorEntityDescription(
        key="getTTM",  # No turbine pulses max. time until alarm A8 (days, 1-30)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
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
        key="getT2",  # Maximum flow leakage time (min, 0-99)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getTMP",  # Leak protection temporarily deactivated - remaining time (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",  # value "" means sensor does not exist.
    ),
    SyrConnectSensorEntityDescription(
        key="getUL",  # Leak protection volume limit - absent profile (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_ul,
    ),
    # --- Leak Protection Profiles 1-8 (LEXplus10SL) ---
    *_profile_descriptions(
        SyrConnectSensorEntityDescription(
            key="getPA",  # Active flag (true/false)
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            value_fn=_value_leak_protection_flag,
        )
    ),
    *_profile_descriptions(
        SyrConnectSensorEntityDescription(
            key="getPB",  # Buzzer alert (true/false)
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=_value_leak_protection_flag,
        )
    ),
    *_profile_descriptions(
        SyrConnectSensorEntityDescription(
            key="getPF",  # Flow leak threshold (l/h)
            native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
            suggested_display_precision=0,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        )
    ),
    *_profile_descriptions(
        SyrConnectSensorEntityDescription(
            key="getPM",  # Microleakage test enabled (true/false)
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=_value_leak_protection_flag,
        )
    ),
    *_profile_descriptions(
        SyrConnectSensorEntityDescription(
            key="getPN",  # Name
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        )
    ),
    *_profile_descriptions(
        SyrConnectSensorEntityDescription(
            key="getPR",  # Return time to present profile (h)
            native_unit_of_measurement=UnitOfTime.HOURS,
            suggested_display_precision=0,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
    ),
    *_profile_descriptions(
        SyrConnectSensorEntityDescription(
            key="getPT",  # Max. leak duration (min)
            native_unit_of_measurement=UnitOfTime.MINUTES,
            suggested_display_precision=0,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        )
    ),
    *_profile_descriptions(
        SyrConnectSensorEntityDescription(
            key="getPV",  # Max. leak volume (l)
            native_unit_of_measurement=UnitOfVolume.LITERS,
            suggested_display_precision=0,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        )
    ),
    *_profile_descriptions(
        SyrConnectSensorEntityDescription(
            key="getPW",  # Leak warning enabled (true/false)
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            value_fn=_value_leak_protection_flag,
        )
    ),
    SyrConnectSensorEntityDescription(
        key="getPRF",  # Currently active leak protection profile index
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getPRN",  # Number of leak protection profiles available to the user (1-8)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPST",  # Pressure sensor installed (1=not available, 2=available)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # --- Filter (NeoSoft) ---
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
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMXH",  # Maximum humidity threshold (%)
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
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
        key="getRCP",  # Synchronization interval (s)
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
        suggested_display_precision=2,
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
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Hygiene flushing (HygBox) ---
    SyrConnectSensorEntityDescription(
        key="getF2T",  # Maximum flushing duration of the temperature flushing (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getF2W",  # Stop temperature of the temperature flushing (°C)
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getF3P",  # Interval of the periodic flushing (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getF3V",  # Flushing volume of the periodic flushing (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMTF",  # Maximum number of temperature flushings per day
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSTP",  # Stagnation time of the stagnation flushing (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSTV",  # Flushing volume of the stagnation flushing (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getTTT",  # Start temperature of the temperature flushing (°C)
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWTY",  # Water type (0=undefined, 1=cold water, 2=hot water)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Hygiene flushing (hygiene module, cold and hot water line) ---
    SyrConnectSensorEntityDescription(
        key="getCCF",  # Periodic flushing of the cold water line (days, 0=off)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_hygiene_module,
    ),
    SyrConnectSensorEntityDescription(
        key="getCCL",  # Maximum temperature of the cold water line (°C)
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_hygiene_module,
    ),
    SyrConnectSensorEntityDescription(
        key="getCSL",  # Flushing volume after which the cold water line stops (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_hygiene_module,
    ),
    SyrConnectSensorEntityDescription(
        key="getCSS",  # Flushing time after which the cold water line stops (10 s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        multiply_by=10,
        value_fn=_value_hygiene_module,
    ),
    SyrConnectSensorEntityDescription(
        key="getCWF",  # Periodic flushing of the hot water line (days, 0=off)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_hygiene_module,
    ),
    SyrConnectSensorEntityDescription(
        key="getSCF",  # Stagnation time of the cold water line (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_hygiene_module,
    ),
    SyrConnectSensorEntityDescription(
        key="getSWF",  # Stagnation time of the hot water line (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_hygiene_module,
    ),
    SyrConnectSensorEntityDescription(
        key="getWCL",  # Minimum temperature of the hot water line (°C)
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_hygiene_module,
    ),
    SyrConnectSensorEntityDescription(
        key="getWSL",  # Flushing volume after which the hot water line stops (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_hygiene_module,
    ),
    SyrConnectSensorEntityDescription(
        key="getWSS",  # Flushing time after which the hot water line stops (10 s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        multiply_by=10,
        value_fn=_value_hygiene_module,
    ),
    # --- Dosing (Dosing Pump) ---
    SyrConnectSensorEntityDescription(
        key="getCAS",  # Canister size (raw 1-2, mapped to liters)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_cas,
    ),
    SyrConnectSensorEntityDescription(
        key="getDAM",  # Current dosing amount (ml/m³)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mL/m³",
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getDMO",  # Operating mode (0=automatic, 1=running-in, 2=disinfection, 3=low)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getDSL",  # Dosing liquid (0=not set, 1, 2)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Display ---
    SyrConnectSensorEntityDescription(
        key="getSRO",  # Display rotation / orientation (0 / 90 / 180 / 270 degrees)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
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
        key="getLNG",  # Device language (0=German, 1=English, 2=Spanish, 3=Italian, 4=Polish) - other models
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
        entity_registry_enabled_default=False,
        value_fn=_value_tmz,
        hidden_when="empty",
    ),
    SyrConnectSensorEntityDescription(
        key="getTYP",  # Device type code
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        hidden_when="empty",  # value "" means sensor does not exist.
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
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getMQT",  # Protocol (0=HTTPS, 1=MQTT)
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
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
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
        key="getCWL",  # Remaining capacity warning threshold (%)
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getFCS",  # Custom cartridge size (L), used for getCRS 0
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getFMT",  # Maximum duration of the initial filling (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getFVT",  # Maximum volume of the initial filling (L)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
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
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
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

# Sensors that only a device profile enables: computed values that the device does not
# report itself and that apply to one family only, the keys of one cartridge type or size
# (cartridge_keys, cartridge_size_keys of the model), and the keys of the HygBox, the dosing pump and the
# hygiene module, which other devices report with another meaning (getCWF, getDMO, getMTF)
_SYR_CONNECT_SENSOR_PROFILE_ONLY_KEYS = {
    "getCAS",
    "getCCF",
    "getCCL",
    "getCND_class",
    "getCSL",
    "getCSS",
    "getCWF",
    "getDAM",
    "getDMO",
    "getDSL",
    "getF2T",
    "getF2W",
    "getF3P",
    "getF3V",
    "getLOT",
    "getMTF",
    "getOHW",
    "getSCF",
    "getSTP",
    "getSTV",
    "getSWF",
    "getTTT",
    "getWCL",
    "getWSL",
    "getWSS",
    "getWTY",
}

# Allowlist of known sensor keys, the global fallback for get_model_supported_keys()
_SYR_CONNECT_SENSOR_SUPPORTED_KEYS = (
    set(_SYR_CONNECT_SENSOR_DESCRIPTIONS) - _SYR_CONNECT_SENSOR_PROFILE_ONLY_KEYS
)


def is_sensor_visible(status: SyrConnectStatus, key: str, value: Any) -> bool:
    """Decide whether a reported status key/value should produce a sensor.

    This function centralizes all visibility/exclusion rules so both the
    entity-creation code and diagnostics produce the same set of visible
    sensors. It is intentionally defensive about input types and accepts
    values that may be strings, numbers, booleans or None.

    Rules (applied in order):
    - Group-controlled keys: keys matching getPVx, getPTx, getPFx, getPNx,
        getPMx, getPWx, getPBx, getPRx are only visible when the device's
        corresponding getPAx flag is truthy (1, "1", True, "true"; see `is_value_true`).
    - Empty values: the `hidden_when` of the key's description hides it when the
        reported value is None or a whitespace-only string ("empty"), or also the
        unspecified IP "0.0.0.0" or "::" ("empty_ip"). "always" hides it whatever the value.

    Args:
            status: The full flattened device status mapping (used for cross-key
                    checks such as getPAx and getBAT).
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

    if key == "getBAP" and is_spurious_bap(status, value):
        return False

    return not _is_excluded_when_empty(key, value)


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
# entity (hidden_when="always"). The keys of the other cartridge types are removed as well
# (see _hidden_sensor_keys). A sensor hidden only because its own value is empty is not
# removed: removing it would drop its customizations (name, area, ...) whenever the
# value happens to be empty at startup.
_SYR_CONNECT_SENSOR_CONDITIONAL_KEYS = {
    description.key
    for description in _SYR_CONNECT_SENSOR_TYPES
    if description.hidden_when == "always"
}


def _hidden_sensor_keys(status: SyrConnectStatus, model: SyrConnectModel) -> set[str]:
    """Return the conditional sensor keys that are hidden for the given device status."""
    return {
        key
        for key in _SYR_CONNECT_SENSOR_CONDITIONAL_KEYS
        if not is_sensor_visible(status, key, status.get(key))
    } | (model.cartridge_dependent_keys - model.reported_cartridge_keys(status))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SyrConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SYR Connect sensors.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up SYR Connect sensors")
    coordinator = entry.runtime_data

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
    """Return the sensors of one device (except the conditional cartridge keys)."""
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
    handled_keys |= model_info.cartridge_dependent_keys
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

    # Without getBAP the battery level is computed from the battery voltages (_value_bap)
    if (
        "getBAP" not in status
        and "getBAP" in supported_sensor_keys
        and all(status.get(key) is not None for key in ("getBAT", "getBMA", "getBMI"))
    ):
        _LOGGER.debug("Creating sensor: device=%s key=getBAP (computed)", device_id)
        entities.append(
            SyrConnectSensor(
                coordinator,
                device_id,
                device_name,
                "getBAP",
            )
        )
        sensor_count += 1

    # The water hardness range is computed from the conductivity (_value_cnd_class)
    if _is_cnd_class_wanted(status, supported_sensor_keys):
        _LOGGER.debug("Creating sensor: device=%s key=getCND_class", device_id)
        entities.append(
            SyrConnectSensor(
                coordinator,
                device_id,
                device_name,
                "getCND_class",
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
    status: SyrConnectStatus,
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

    for idx in LEAK_PROTECTION_PROFILES:
        pa_key = f"getPA{idx}"
        pa_val = status.get(pa_key)
        group_keys = _pa_group_keys(idx)

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
                # Ensure group keys are marked as handled so they are not recreated
                # later when iterating over status.items().
                handled_keys.add(gk)

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


def _muco_conditional_keys(
    status: SyrConnectStatus, model: SyrConnectModel
) -> set[str]:
    """Return the cartridge keys that apply to the cartridge type and size.

    Only for models whose profile maps the cartridge types (getCRT) or sizes (getCRS) to
    keys (MuCo filling, All in One +). Leak-protection and TrioLock devices also report
    getCRT/getLOT/getOHW but deliberately do not expose them.
    """
    supported_sensor_keys = get_model_supported_keys(
        model, "sensor", _SYR_CONNECT_SENSOR_SUPPORTED_KEYS
    )
    return get_cartridge_entity_keys(model, status, supported_sensor_keys)


def sensor_keys_for_status(
    status: SyrConnectStatus, model: SyrConnectModel
) -> list[str]:
    """Return the keys of the sensors the platform creates for a device status.

    Uses the same rules as the setup: the model's allowlist, the connection state (dst),
    the active leak-protection profiles (getPAx), the visibility and value checks of
    `_is_sensor_wanted` and the conditional cartridge sensors (getLOT, getOHW, getFCS).

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
    handled_keys = model.cartridge_dependent_keys
    for idx in LEAK_PROTECTION_PROFILES:
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
    keys.extend(sorted(_muco_conditional_keys(status, model)))
    if _is_cnd_class_wanted(status, supported_sensor_keys):
        keys.append("getCND_class")
    return keys


def _is_cnd_class_wanted(
    status: SyrConnectStatus, supported_sensor_keys: set[str]
) -> bool:
    """Return True if the device gets the water hardness range computed from getCND."""
    return (
        "getCND_class" in supported_sensor_keys
        and parse_float(status.get("getCND")) is not None
    )


# Value rules of single keys, on the value as number (None if it is no number)
_SYR_CONNECT_SENSOR_VALUE_RULES: dict[str, Callable[[float | None], bool]] = {
    # Display rotation (getSRO): only an integer value
    "getSRO": lambda number: number is not None and number.is_integer(),
    # getFFM: only a value >= 1
    "getFFM": lambda number: number is not None and number >= 1,
}


def _is_sensor_wanted(
    status: SyrConnectStatus,
    key: str,
    value: Any,
    supported_sensor_keys: set[str],
    handled_keys: set[str],
    registered: bool = False,
) -> bool:
    """Return True if the status value gets a regular sensor entity.

    A sensor that is already registered (`registered`) is created whatever its value,
    except for hidden_when="always". Otherwise it would stay registered without an entity
    (grayed out) until a restart with a value that passes the value rules.
    """
    # Allowlist check: the definitive list of keys this integration handles.
    # Anything not listed here is ignored unconditionally, regardless of
    # what other checks follow. This takes precedence over all other logic.
    if key not in supported_sensor_keys:
        _LOGGER.debug("Skipping unknown sensor key %s (not in allowlist)", key)
        return False

    # Skip keys that are handled as binary sensors, dst (a dedicated
    # SyrConnectConnectionStateSensor) and keys already handled elsewhere: the getPA group
    # logic and the keys of the cartridge types, which are mutually exclusive depending on
    # getCRT and handled dynamically (_async_setup_muco_conditional_sensors) so the
    # applicable one can be added/removed live without an integration reload.
    if (
        key in _SYR_CONNECT_BINARY_SENSOR_SUPPORTED_KEYS
        or key == "dst"
        or key in handled_keys
    ):
        return False

    if registered:
        return _is_registered_sensor_wanted(key, value)

    # Centralized visibility check
    if not is_sensor_visible(status, key, value):
        return False

    value_rule = _SYR_CONNECT_SENSOR_VALUE_RULES.get(key)
    if value_rule is not None and not value_rule(parse_float(value)):
        return False

    return isinstance(value, int | float | str)


def _is_registered_sensor_wanted(key: str, value: Any) -> bool:
    """Return True if an already registered sensor keeps its entity.

    Any value counts, except for hidden_when="always".
    """
    description = _SYR_CONNECT_SENSOR_DESCRIPTIONS.get(key)
    if description is not None and description.hidden_when == "always":
        return False
    return value is None or isinstance(value, int | float | str)


def _async_setup_muco_conditional_sensors(
    hass: HomeAssistant,
    entry: SyrConnectConfigEntry,
    coordinator: SyrConnectDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Dynamically add/remove the cartridge sensors depending on the cartridge type and size.

    Mirrors _async_setup_muco_conditional_selects in select.py: getLOT (HVE/HVE+) and
    getOHW (HWE) are mutually exclusive based on getCRT, and the custom cartridge size
    (getFCS) only applies to getCRS "custom". registry_cleanup() only runs
    once at setup, so without this listener the inapplicable diagnostic sensor would
    stay registered and show as permanently grayed-out "unavailable" after the user
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
                wanted_set = _muco_conditional_keys(status, get_device_model(device))

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

                for key in sorted(wanted_set - current):
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

    # A non-numeric value of a numeric sensor is logged as a warning once, until a
    # number arrives again
    _non_numeric_logged = False

    # Factor from the water hardness the device keeps to the unit of getWHU
    _hardness_factor = 1.0

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

        self._apply_hardness_unit()
        self._apply_model_names()
        self._apply_model_scale()

        # Cache last non-None native value to avoid writing None when API omits values
        self._last_native_value: str | int | float | datetime | None = None

    def _apply_hardness_unit(self) -> None:
        """Set the unit and the factor of a water hardness sensor from getWHU."""
        sensor_key = self._sensor_key
        # Set unit of measurement for water hardness sensors dynamically
        if sensor_key in ("getIWH", "getOWH"):
            self._attr_native_unit_of_measurement = self.device_model.whu_unit(
                self._status.get("getWHU")
            )

        # A device that keeps the water hardness in °dH shows it in the unit of getWHU
        if sensor_key in ("getIWH", "getOHW"):
            self._hardness_factor = self.device_model.hardness_factor(
                self._status.get("getWHU")
            )
            if self._hardness_factor != 1:
                self._attr_native_unit_of_measurement = self.device_model.whu_unit(
                    self._status.get("getWHU")
                )

    def _apply_model_names(self) -> None:
        """Rename getBAT and getBAR for the models that give them another meaning."""
        model = self.device_model
        # Override getBAT attributes for devices that report battery as percentage (SafeFloor).
        # The name follows the unit: "Battery level" like getBAP instead of "Battery voltage".
        if self._sensor_key == "getBAT" and model.bat_in_percent:
            self._attr_native_unit_of_measurement = UnitOfRatio.PERCENTAGE
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_suggested_display_precision = 0
            self._attr_translation_key = "getbap"

        # On devices that report the inlet pressure in getIBA, getBAR is the system pressure
        if self._sensor_key == "getBAR" and model.bar_is_system_pressure:
            self._attr_translation_key = "getbar_system"

    def _apply_model_scale(self) -> None:
        """Use the scale the model reports a key in.

        A device may report a key in another scale than its description, e.g. milliliters
        instead of liters or l/min instead of l/h. The value keeps the unit of the
        description, and with it its display precision.
        """
        model = self.device_model
        sensor_key = self._sensor_key
        description = self.entity_description
        hardness_divisor = (
            model.hardness_divisor(self._status.get("getWHU"))
            if sensor_key in ("getIWH", "getOWH")
            else 1
        )
        divide_by = (
            model.value_divisors.get(sensor_key, description.divide_by)
            * hardness_divisor
        )
        multiply_by = model.value_factors.get(sensor_key, description.multiply_by)
        # The water hardness takes the unit of getWHU instead, which can need decimals
        # the description does not have (tenths of mmol/l)
        precision = description.suggested_display_precision
        if precision is not None and hardness_divisor > 1:
            precision += math.ceil(math.log10(hardness_divisor))
        if (divide_by, multiply_by) != (
            description.divide_by,
            description.multiply_by,
        ):
            self.entity_description = replace(
                description,
                divide_by=divide_by,
                multiply_by=multiply_by,
                suggested_display_precision=precision,
            )

    def _apply_numeric_conversion(self, value: float) -> float | int:
        """Apply the sensor-specific scale to a raw number.

        The value keeps all its digits: the display precision only suggests how many
        Home Assistant shows, and the user can choose more of them. A water hardness the
        device keeps in °dH is the exception: converted to the unit of getWHU, it is
        rounded to a whole number like the select and the SYR app show it, since the
        device only knows whole °dH (5 °dH -> 9 °fH, not 8.92402285 °fH).

        Args:
            value: The raw numeric value

        Returns:
            The scaled value; a whole number as int
        """
        # Apply the sensor-specific scale (e.g. 1/10 °C -> °C, liters -> m³)
        description = self.entity_description
        value = value / description.divide_by * description.multiply_by
        if self._hardness_factor != 1:
            return round_hardness(value * self._hardness_factor)
        if value.is_integer():
            return int(value)
        return value

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
        """Convert a raw value to a number with the sensor's scale.

        Args:
            value: Raw value from the device status

        Returns:
            The converted number; for a text that is no number the text itself, or
            None if the sensor needs a number; None for a missing value or a type a
            sensor cannot show (e.g. a list)
        """
        if isinstance(value, str):
            try:
                numeric_value = float(value)
            except ValueError, TypeError:
                return self._non_numeric_value(value)
            self._non_numeric_logged = False
            return self._apply_numeric_conversion(numeric_value)

        # Handle numeric values directly
        if isinstance(value, int | float):
            self._non_numeric_logged = False
            return self._apply_numeric_conversion(float(value))

        # None, or a type a sensor cannot show (e.g. a list)
        return None

    def _non_numeric_value(self, value: str) -> str | None:
        """Return a text that is no number, or None if the sensor needs a number.

        Home Assistant rejects a text as the state of a numeric sensor (ValueError), so
        the entity would not be updated or added. None keeps the last value instead.
        An empty text is a missing value (logged at debug by _compute_native_value).
        """
        if not self._expects_number():
            return value
        if value.strip() == "":
            return None
        log = _LOGGER.debug if self._non_numeric_logged else _LOGGER.warning
        log(
            "Device %s (%s): %s reported the non-numeric value %r; keeping the last value",
            self._device_name,
            self._device_id,
            self._sensor_key,
            value,
        )
        self._non_numeric_logged = True
        return None

    def _expects_number(self) -> bool:
        """Return True if Home Assistant requires a numeric state for this sensor.

        The same rule as Home Assistant's sensor state check: a unit, state class or
        display precision, or a device class that is not a non-numeric one.
        """
        if self.device_class in NON_NUMERIC_DEVICE_CLASSES:
            return False
        return (
            self.state_class is not None
            or self.native_unit_of_measurement is not None
            or self.suggested_display_precision is not None
            or self.device_class is not None
        )


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
            return str(to_int(dst))
        except TypeError, ValueError:
            return str(dst)

    @property
    @override
    def available(self) -> bool:
        """Always available so the connection state is always shown."""
        return True
