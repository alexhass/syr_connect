"""Alarm, notification and warning codes of the SYR devices (getALA, getALM, getNOT, getWRN).

The devices report "no code" in several ways, see "Resetting alarms, notifications and
warnings" in docs/syrconnect-protocol.md. `is_code_active()` tells an active code from
these values.

The tables map the codes of a device family to the key of their meaning (for example
"alarm_salt_supply_low"); the caller translates the key. A family without a table of a
kind has unknown codes, and the caller shows the raw code. A signature names the tables
of its family (`ala_codes`, `not_codes`, `wrn_codes` of `SyrConnectModelSignature`).
"""

from collections.abc import Mapping

# Values that mean "no code", compared after strip().upper(). The device reports "FF"
# after a reset; 255 is the decimal reset value of the JSON API (`clear_value`).
NO_CODE_VALUES: frozenset[str] = frozenset({"", "0", "00", "FF", "A0X0000", "255"})


def is_code_active(value: object) -> bool:
    """Return True if an alarm, notification or warning code is active.

    Args:
        value: Value of getALA, getALM, getNOT or getWRN, None if the device does not
            report it

    Returns:
        False for None and the values of `NO_CODE_VALUES`, True otherwise
    """
    return value is not None and str(value).strip().upper() not in NO_CODE_VALUES


# Alarm codes (getALA) of the All-in-One+: raw code -> key of the meaning
ALA_CODES_ALLINONEPLUS: Mapping[str, str] = {
    "A1": "alarm_end_switch",
    "A2": "alarm_pressure_sensor_faulty",
    "A3": "alarm_pressure_sensor_2_faulty",
    "A4": "alarm_flow_sensor_fault",
    "A5": "fault_conductance_sensor",
    "A6": "alarm_conductivity_sensor_2_faulty",
    "A7": "alarm_temperature_sensor_faulty",
    "A8": "alarm_fill_cycles_exceeded",
    "A9": "alarm_heating_fill_volume_leak",
    "AA": "alarm_heating_fill_time_leak",
    "AB": "alarm_cartridge_almost_exhausted",
    "AC": "alarm_cartridge_exhausted",
    "AD": "alarm_battery_low",
    "AE": "alarm_sl_module_communication",
    "AF": "alarm_pressure_too_low",
    "B0": "alarm_target_pressure_unreachable",
    "B1": "alarm_no_power_supply",
    "FF": "no_alarm",
}

# Alarm codes (getALA) of NeoSoft, Trio, SafeTech+ (dk 1112) and the MultiController:
# raw code -> key of the meaning, see "Alarm codes (getALA) — common table" in
# docs/syrconnect-protocol.md
ALA_CODES_COMMON: Mapping[str, str] = {
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

# Alarm codes (getALA) of the dosing pump: raw code -> key of the meaning. "FF" = no
# alarm is assumed like on the other devices with the alarm codes A1-AF.
ALA_CODES_DOSINGPUMP: Mapping[str, str] = {
    "A1": "alarm_dosing_pump_communication",
    "A2": "alarm_dosing_liquid_low",
    "A3": "alarm_dosing_liquid_empty",
    "FF": "no_alarm",
}

# Alarm codes (getALA) of the HVA: raw code -> key of the meaning
ALA_CODES_HVA: Mapping[str, str] = {
    "A1": "alarm_safet_valve_cannot_be_operated",
    "A2": "alarm_flow_sensor_fault",
    "A3": "alarm_heating_fill_volume_leak",
    "A4": "alarm_heating_fill_flow_leak",
    "A5": "alarm_conductivity_sensor_or_cartridge",
    "A6": "alarm_battery_low",
    "A7": "alarm_cartridge_exhausted",
    "A8": "alarm_heating_fill_time_leak",
    "A9": "alarm_fill_cycles_exceeded",
    "AA": "alarm_minimum_fill_volume_not_reached",
    "AB": "alarm_minimum_pressure_rise_not_reached",
    "AC": "alarm_pressure_sensor_faulty",
    "FF": "no_alarm",
}

# Alarm codes (getALA) of the HygBox: raw code -> key of the meaning. "FF" = no alarm
# is assumed like on the other devices with the alarm codes A1-AF.
ALA_CODES_HYGBOX: Mapping[str, str] = {
    "A1": "alarm_pressure_sensor_faulty",
    "A2": "alarm_temperature_sensor_faulty",
    "A3": "alarm_flow_sensor_fault",
    "A4": "alarm_solenoid_valve_fault",
    "A5": "alarm_drain_sensor_fault",
    "A6": "alarm_pressure_too_low",
    "A7": "alarm_battery_low",
    "A8": "alarm_stagnation_flushing_time_exceeded",
    "A9": "alarm_periodic_flushing_time_exceeded",
    "FF": "no_alarm",
}

# Alarm codes (getALA) of the hygiene module: raw code -> key of the meaning. "FF" = no
# alarm is assumed like on the other devices with the alarm codes A0-AF.
ALA_CODES_HYGIENEMODULE: Mapping[str, str] = {
    "A0": "alarm_battery_low",
    "A1": "alarm_safet_valve_cannot_be_operated",
    "A2": "alarm_flow_sensor_cold_fault",
    "A3": "alarm_flow_sensor_hot_fault",
    "A4": "alarm_flushings_cold_exceeded",
    "A5": "alarm_flushings_hot_exceeded",
    "A6": "alarm_temperature_cold_exceeded",
    "A7": "alarm_temperature_hot_exceeded",
    "A8": "alarm_emergency_stop",
    "A9": "alarm_drain_sensor_fault",
    "AA": "alarm_temperature_sensor_cold_faulty",
    "AB": "alarm_temperature_sensor_hot_faulty",
    "AC": "alarm_combination_module_communication",
    "AD": "alarm_turbine_table_invalid",
    "FF": "no_alarm",
}

# Alarm codes (getALM) of i-LEX, LEX Plus 10 and LEX Plus 10 S: raw code -> key of the
# meaning. The LEX Plus 10 SL has its own, longer table (`ALA_CODES_LEXPLUS10SL`).
ALA_CODES_LEX: Mapping[str, str] = {
    "0": "no_alarm",
    "LOWSALT": "alarm_salt_supply_low",
    "NOSALT": "alarm_salt_supply_empty",
    "1": "alarm_salt_supply_empty",
    "2": "alarm_pressure_too_low",
    "3": "alarm_pressure_too_high",
    "4": "alarm_pressure_sensor_faulty",
    "5": "alarm_valve_malfunction",
}

# Alarm codes (getALA) of the LEX Plus 10 SL: raw code -> key of the meaning. Longer
# than the table of the other LEX devices (`ALA_CODES_LEX`), and the codes 2-5 mean
# something else there.
ALA_CODES_LEXPLUS10SL: Mapping[str, str] = {
    "0": "no_alarm",
    "LOWSALT": "alarm_salt_supply_low",
    "NOSALT": "alarm_salt_supply_empty",
    "1": "alarm_salt_supply_empty",
    "2": "alarm_chlor_generator_fault",
    "3": "alarm_valve_malfunction",
    "4": "alarm_pressure_too_low",
    "5": "alarm_pressure_too_high",
    "6": "alarm_brine_level_low",
    "7": "alarm_brine_level_high",
    "11": "alarm_end_switch",
    "12": "alarm_no_network_connection",
    "13": "alarm_leakage_volume_reached",
    "14": "alarm_leakage_time_reached",
    "15": "alarm_max_flow_rate_reached",
    "16": "alarm_microleakage_detected",
    "17": "alarm_external_sensor_leakage_radio",
    "18": "alarm_turbine_blocked",
    "19": "alarm_pressure_sensor_faulty",
    "20": "alarm_temperature_sensor_faulty",
    "21": "fault_conductance_sensor",
    "23": "alarm_leakage_volume_approaching",
}

# Alarm codes (getALA) of the SafeFloor devices: raw code -> key of the meaning. The
# device reports "A0x0000"; the keys are upper case, so the caller compares the code
# in upper case. The codes are hexadecimal bitmask values (0x0002, 0x0004, ..., 0x0100).
ALA_CODES_SAFEFLOOR: Mapping[str, str] = {
    "A0X0000": "no_alarm",
    "A0X0002": "alarm_safefloor_communication",
    "A0X0004": "alarm_safefloor_flood",
    "A0X0008": "alarm_safefloor_weather",
    "A0X0010": "alarm_safefloor_low_temperature",
    "A0X0020": "alarm_safefloor_high_temperature",
    "A0X0040": "alarm_safefloor_low_humidity",
    "A0X0080": "alarm_safefloor_high_humidity",
    "A0X0100": "alarm_battery_low",
}

# Alarm codes (getALA) of the SafeTech family: raw code -> key of the meaning. A2 and
# AC-AF differ from the codes of NeoSoft, MuCo and Trio (`ALA_CODES_COMMON`).
ALA_CODES_SAFETECH: Mapping[str, str] = {
    "A1": "alarm_end_switch",
    "A2": "alarm_no_network_connection",
    "A3": "alarm_leakage_volume_reached",
    "A4": "alarm_leakage_time_reached",
    "A5": "alarm_max_flow_rate_reached",
    "A6": "alarm_microleakage_detected",
    "A7": "alarm_external_sensor_leakage_radio",
    "A8": "alarm_turbine_blocked",
    "A9": "alarm_pressure_sensor_faulty",
    "AA": "alarm_temperature_sensor_faulty",
    "AB": "fault_conductance_sensor",
    "AC": "alarm_conductivity_too_high",
    "AD": "alarm_battery_low",
    "AE": "alarm_leakage_volume_approaching",
    "AF": "alarm_no_power_supply",
    "FF": "no_alarm",
}

# Alarm codes (getALA) of the Safe-T family: raw code -> key of the meaning
ALA_CODES_SAFETPLUS: Mapping[str, str] = {
    "A0": "alarm_safet_microleakage_detected",
    "A1": "alarm_safet_valve_cannot_be_operated",
    "A2": "alarm_safet_turbine_no_signal",
    "A3": "alarm_safet_leakage_volume_reached",
    "A4": "alarm_safet_flow_leakage_detected",
    "A5": "alarm_safet_absence_leakage_detected",
    "A6": "alarm_safefloor_flood",
    "A7": "alarm_external_sensor_leakage_in2",
    "A8": "alarm_safet_48h_leakage",
    "A9": "alarm_safet_flow_time_exceeded",
    "BA": "alarm_battery_low",
    "FF": "no_alarm",
    "LOWBAT": "alarm_battery_low",
    "WEAKBAT": "alarm_battery_weak",
}

# Notification codes (getNOT) of the same device families: raw code -> key of the
# meaning
NOT_CODES_COMMON: Mapping[str, str] = {
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
NOT_CODES_NONE: Mapping[str, str] = {
    "FF": "no_notification",
    "": "no_notification",
}

# Warning codes (getWRN) of the same device families: raw code -> key of the meaning
WRN_CODES_COMMON: Mapping[str, str] = {
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
WRN_CODES_NONE: Mapping[str, str] = {
    "FF": "no_warning",
    "": "no_warning",
}
