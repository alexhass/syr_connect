"""Entity allowlist override for the hygiene module with two lines (dk=62/63).

Models: Hygiene Module (hot and cold, dk=62/dkv=23), Hygiene Module (cold and hot,
dk=63/dkv=24).

Model type: Hygiene flushing

Provisional: no fixture of this device exists yet. The allowlists hold the keys of the
hygiene module described in docs/syrconnect-protocol.md, and must be checked against a
capture of a real device.

The hygiene module flushes a cold and a hot water line. Each line has five settings;
the keys of the cold line have a "C", the keys of the hot line a "W":
- Stagnation flushing (getSCF, getSWF): flushes after 1-7 days without water use.
- Periodic flushing (getCCF, getCWF): flushes every 1-30 days, 0 = off.
- Temperature limit (getCCL, getWCL): maximum temperature of the cold line, minimum
  temperature of the hot line; a value below the range = off.
- Flushing stop after a time (getCSS, getWSS) and after a volume (getCSL, getWSL).
setMFC and setMFW start a manual flushing of the line.

The alarm (getALA) is reset with clrALA (alarm_clear_via_set is not set).

Deliberately NOT included:
- getVOL: holds the number of flushings in the attributes tcf/twf, which the response
  parser does not read.
- getCNO: code number of the device label; it registers the device to an account.

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.
"""

from . import SyrConnectDeviceProfile

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Alarm ---
    "getALA",
    # --- Voltage / Battery ---
    "getBAT",
    # --- Hygiene flushing (cold water line) ---
    "getCCF",
    "getCCL",
    "getCSL",
    "getCSS",
    "getSCF",
    # --- Hygiene flushing (hot water line) ---
    "getCWF",
    "getSWF",
    "getWCL",
    "getWSL",
    "getWSS",
    # --- Device Info & Diagnostics ---
    "getMAC",
    "getSRN",
    "getVER",
}

SELECT_SUPPORTED_KEYS = {
    "getCCF",
    "getCCL",
    "getCSL",
    "getCSS",
    "getCWF",
    "getSCF",
    "getSWF",
    "getWCL",
    "getWSL",
    "getWSS",
}

SWITCH_SUPPORTED_KEYS: set[str] = set()

BINARY_SENSOR_SUPPORTED_KEYS: set[str] = set()

BUTTON_SUPPORTED_KEYS = {
    "setALA",
    "setMFC",
    "setMFW",
}

VALVE_SUPPORTED_KEYS: set[str] = set()

# Maximum temperature of the cold water line (getCCL) in °C: 15-25
SELECT_CCL_OPTIONS = list(range(15, 26))

# Minimum temperature of the hot water line (getWCL) in °C: 55-65
SELECT_WCL_OPTIONS = list(range(55, 66))

# Raw values written for "off": 0 days for the periodic flushing, one degree below the
# range for the temperature limit
SELECT_OFF_VALUES = {
    "getCCF": 0,
    "getCCL": 14,
    "getCWF": 0,
    "getWCL": 54,
}

# Alarm codes of the hygiene module (raw API getALA -> internal translation key). "FF" =
# no alarm is assumed like on the other devices with the alarm codes A0-AF.
ALA_CODES = {
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


PROFILE = SyrConnectDeviceProfile(
    ala_codes=ALA_CODES,
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    select_off_values=SELECT_OFF_VALUES,
    select_options={
        "getCCL": SELECT_CCL_OPTIONS,
        "getWCL": SELECT_WCL_OPTIONS,
    },
    sensor=SENSOR_SUPPORTED_KEYS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
