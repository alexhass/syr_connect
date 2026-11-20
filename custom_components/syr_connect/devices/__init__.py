"""Per-device-model entity allowlist overrides.

Each module here describes one device family and defines one POSITIVE allowlist
constant per platform: `SENSOR_SUPPORTED_KEYS`, `SELECT_SUPPORTED_KEYS`,
`SWITCH_SUPPORTED_KEYS`, `BINARY_SENSOR_SUPPORTED_KEYS`, `BUTTON_SUPPORTED_KEYS`,
`VALVE_SUPPORTED_KEYS`. They are collected in the module's `PROFILE`, which the
signatures of the family reference as `device_profile` in `models.MODEL_SIGNATURES`.
A profile also lists the measurement history series the cloud keeps for the family
(`statistics`), see "Statistics web services" in docs/syrconnect-protocol.md.

`helpers.profile.get_model_supported_keys()` uses these allowlists instead of the global
ones, so the entities created for a device are limited to keys explicitly
confirmed for that model rather than the union of every model's keys. Models
without a profile keep using the global allowlists unchanged.

The global fallback allowlists these override are `_SYR_CONNECT_<PLATFORM>_SUPPORTED_KEYS`
in the platform modules (sensor.py, select.py, ...).
"""

from collections.abc import Mapping, Set as AbstractSet
from dataclasses import dataclass, field

from ..aiosyrconnect import SyrConnectStatistic

# Common alarm codes (getALA) of NeoSoft, Trio, SafeTech+ (dk 1112) and the
# MultiController: raw code -> internal translation key, see "Alarm codes (getALA) —
# common table" in docs/syrconnect-protocol.md
ALA_CODES_COMMON = {
    "01": "alarm_pressure_too_low",
    "02": "alarm_pressure_too_high",
    "03": "alarm_mixing_valve_position",
    "04": "alarm_changeover_valve_position",
    "05": "alarm_column_1_position",
    "06": "alarm_column_2_position",
    "07": "alarm_brine_level_low",
    "08": "alarm_brine_suction_too_low",
    "09": "alarm_electrolysis_cell_column_1",
    "0A": "alarm_electrolysis_cell_column_2",
    "0B": "alarm_no_usb_drive",
    "0C": "alarm_electrolysis_cell",
    "0D": "alarm_salt_supply_empty",
    "0E": "alarm_valve_position",
    "15": "alarm_heating_fill_volume_leak",
    "16": "alarm_heating_fill_time_leak",
    "17": "alarm_fill_cycles_exceeded",
    "18": "alarm_cartridge_exhausted_capacity",
    "19": "alarm_cartridge_exhausted_conductivity",
    "1A": "alarm_target_pressure_unreachable",
    "96": "alarm_leakage_volume_no_shutoff",
    "97": "alarm_leakage_time_no_shutoff",
    "9F": "alarm_end_switch",
    "A0": "alarm_leak_protection_connection",
    "A1": "alarm_end_switch",
    "A2": "alarm_motor_current_exceeded",
    "A3": "alarm_leakage_volume_reached",
    "A4": "alarm_leakage_time_reached",
    "A5": "alarm_max_flow_rate_reached",
    "A6": "alarm_microleakage_detected",
    "A7": "alarm_external_sensor_leakage_radio",
    "A8": "alarm_flow_sensor_fault",
    "A9": "alarm_pressure_sensor_faulty",
    "AA": "alarm_temperature_sensor_faulty",
    "AB": "fault_conductance_sensor",
    "AC": "alarm_increased_water_hardness",
    "AD": "alarm_conductivity_sensor_2_faulty",
    "AE": "alarm_valve_no_movement",
    "AF": "alarm_pressure_sensor_2_faulty",
    "FF": "no_alarm",
}

# Common notification codes (getNOT) of the same device families: raw code ->
# internal translation key
NOT_CODES_COMMON = {
    "01": "new_software_available",
    "02": "bi_annual_maintenance",
    "03": "annual_maintenance",
    "04": "new_software_installed",
    "07": "filter_maintenance_reminder",
    "08": "filter_service_reminder",
    "09": "backwash_reminder_pressure",
    "FF": "no_notification",
    "": "no_notification",
}

# Notification codes of device families whose notifications are unknown: only "no
# notification" is mapped
NOT_CODES_NONE = {
    "FF": "no_notification",
    "": "no_notification",
}

# Common warning codes (getWRN) of the same device families: raw code -> internal
# translation key
WRN_CODES_COMMON = {
    "01": "power_outage",
    "02": "salt_supply_low",
    "03": "water_temperature_too_low",
    "04": "water_temperature_too_high",
    "05": "salt_refill_timeout",
    "06": "water_hardness_change",
    "07": "leak_warning",
    "08": "battery_low",
    "09": "initial_filling",
    "0A": "leak_warning_volume",
    "0B": "leak_warning_time",
    "10": "cartridge_almost_exhausted",
    "11": "regeneration_required",
    "12": "batteries_running_low",
    "13": "no_batteries_detected",
    "14": "outlet_pressure_too_high",
    "1A": "system_time_lost",
    "1B": "start_condition_missing",
    "A6": "microleakage_suspected",
    "FF": "no_warning",
    "": "no_warning",
}

# Warning codes of device families whose warnings are unknown: only "no warning" is
# mapped
WRN_CODES_NONE = {
    "FF": "no_warning",
    "": "no_warning",
}

# Water hardness unit codes (getWHU) of the device families: code -> unit. Each family
# numbers the units differently, see docs/syrconnect-protocol.md.
WHU_UNITS_LEX = {
    0: "°dH",
    1: "°fH",
    2: "°e",
    3: "mg/l CaCO₃",
    4: "ppm",
    5: "mmol/l",
    6: "mval/l",
}
WHU_UNITS_MUCO = {
    0: "°dH",
    1: "°e",
    2: "°fH",
    3: "ppm",
}
WHU_UNITS_NEOSOFT = {
    0: "°dH",
    1: "mmol/l",
    2: "°fH",
}

# Water hardness units as multiples of 1 °dH, for devices that keep the water hardness
# in °dH and use getWHU only for the display (hardness_in_dh)
WHU_FACTORS_FROM_DH = {
    "°dH": 1.0,
    "°e": 1.25216338,
    "°fH": 1.78480457,
    "ppm": 17.8480457,
}


@dataclass(frozen=True, kw_only=True)
class SyrConnectDeviceProfile:
    """Entity allowlists, alarm codes and statistics of a device family.

    Each allowlist field is named after its platform and replaces the platform's global
    allowlist completely; an empty set means "no entities of this platform", None
    keeps the global allowlist.
    """

    # Alarm codes (getALA) of the device family: raw code -> translation key; None
    # means the codes are unknown and the raw code is shown
    ala_codes: Mapping[str, str] | None = None
    # getBAR is the pressure of the system (heating system) instead of the inlet
    # pressure; the device reports the inlet pressure in getIBA
    bar_is_system_pressure: bool = False
    # The device reports the battery (getBAT) in % instead of a voltage
    bat_in_percent: bool = False
    binary_sensor: AbstractSet[str] | None
    button: AbstractSet[str] | None
    # Keys that only apply to one cartridge type (getCRT): cartridge type code -> key;
    # only the key of the reported cartridge type becomes an entity
    cartridge_keys: Mapping[str, str] = field(default_factory=dict)
    # Keys that only apply to one cartridge size (getCRS): cartridge size code -> key;
    # only the key of the reported cartridge size becomes an entity
    cartridge_size_keys: Mapping[str, str] = field(default_factory=dict)
    # Water hardness values (getIWH, getOWH) the device reports in another scale for a
    # getWHU code: code -> divisor, e.g. 10 for tenths of mmol/l; the display gets one
    # decimal more per factor 10
    hardness_divisors: Mapping[int, int] = field(default_factory=dict)
    # The device reports and takes the water hardness (getIWH, getOHW) in °dH whatever
    # getWHU is set to; getWHU is only the unit of the display, the values are converted
    hardness_in_dh: bool = False
    # Water hardness selects (getIWH, getOWH) whose range depends on the unit: key ->
    # getWHU code -> (lowest, highest, step) in that unit
    hardness_ranges: Mapping[str, Mapping[int, tuple[int, int, int]]] = field(
        default_factory=dict
    )
    # Switch keys the device reports inverted to the other devices: the reported
    # value means the opposite of the switch state
    inverted_switches: AbstractSet[str] = field(default_factory=frozenset)
    # The device reports its timestamps (getLAR) as local wall time encoded as a UNIX
    # timestamp instead of UTC, see docs/known_issues_xml_api.md, issue 5
    local_time_timestamps: bool = False
    select: AbstractSet[str] | None
    # Select keys with an "off" option: key -> raw value written for "off"; a reported
    # value below the lowest other option is shown as "off"
    select_off_values: Mapping[str, int] = field(default_factory=dict)
    # Select keys whose options differ from the global step list of the platform: key ->
    # raw values in ascending order, e.g. other durations for getRMT
    select_options: Mapping[str, list[int]] = field(default_factory=dict)
    sensor: AbstractSet[str] | None
    # Sensor keys the device reports in another scale than the entity description:
    # key -> divisor that replaces the description's divide_by, e.g. 1000 for
    # milliliters instead of liters
    sensor_divisors: Mapping[str, int] = field(default_factory=dict)
    # Sensor keys the device reports in another scale than the entity description:
    # key -> factor that replaces the description's multiply_by, e.g. 60 for a flow
    # in l/min instead of l/h
    sensor_factors: Mapping[str, int] = field(default_factory=dict)
    # Notification codes (getNOT) of the device family: raw code -> translation key;
    # None means the codes are unknown and the raw code is shown
    not_codes: Mapping[str, str] | None = None
    # Measurement history series the cloud keeps for the device; empty means none
    statistics: tuple[SyrConnectStatistic, ...] = ()
    switch: AbstractSet[str] | None
    # None means the global allowlist of the platform
    update: AbstractSet[str] | None = None
    valve: AbstractSet[str] | None
    # Warning codes (getWRN) of the device family: raw code -> translation key; None
    # means the codes are unknown and the raw code is shown
    wrn_codes: Mapping[str, str] | None = None
    # Water hardness unit codes (getWHU) of the device family: code -> unit; None means
    # the device has no water hardness unit
    whu_units: Mapping[int, str] | None = None
