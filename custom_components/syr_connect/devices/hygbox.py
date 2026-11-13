"""Entity allowlist override for the hygbox model (HygBox, dk=180/dkv=37).

Model type: Hygiene flushing

Provisional: no fixture of this device exists yet. The allowlists hold the keys of the
HygBox described in docs/syrconnect-protocol.md, and must be checked against a capture
of a real device.

The HygBox flushes the water pipe in three ways, each with its own settings:
- Stagnation flushing (getFD1): after the stagnation time (getSTP) without water use,
  with the flushing volume getSTV.
- Temperature flushing (getFD2): when the water temperature leaves the range of the
  water type (getWTY), between the start and the stop temperature (getTTT, getF2W), at
  most getF2T seconds and getMTF times per day.
- Periodic flushing (getFD3): every getF3P minutes, with the flushing volume getF3V.
getFD1-3 report the function as disabled, so their switches are inverted.

The alarm (getALA) is reset with clrALA (alarm_clear_via_set is not set). The
HygBox reports no warnings (getWRN) and no notifications (getNOT).

Deliberately NOT included:
- getMQT: reported, but without a known meaning (probably an MQTT flag).

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.
"""

from . import SyrConnectDeviceProfile

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve & Flow ---
    "getFLO",
    # --- Alarm ---
    "getALA",
    # --- Pressure ---
    "getBAR",
    # --- Voltage / Battery ---
    "getBAP",
    # --- Water Quality ---
    "getCEL",
    # --- Hygiene flushing ---
    "getF2T",
    "getF2W",
    "getF3P",
    "getF3V",
    "getMTF",
    "getSTP",
    "getSTV",
    "getTTT",
    "getWTY",
    # --- Intervals ---
    "getRCP",
    # --- Device Info & Diagnostics ---
    "getMAC",
    "getSRN",
    "getVER",
    # --- Wi-Fi ---
    "getWFC",
    "getWGW",
    "getWIP",
    # "getMQT",  # Unknown meaning, probably an MQTT flag
}

SELECT_SUPPORTED_KEYS = {
    "getF2T",
    "getF2W",
    "getF3P",
    "getF3V",
    "getMTF",
    "getRCP",
    "getSTP",
    "getSTV",
    "getTTT",
    "getWTY",
}

SWITCH_SUPPORTED_KEYS = {
    "getBUZ",
    "getFD1",
    "getFD2",
    "getFD3",
}

BINARY_SENSOR_SUPPORTED_KEYS = {
    "getBUZ",
}

BUTTON_SUPPORTED_KEYS = {
    "setALA",
}

VALVE_SUPPORTED_KEYS: set[str] = set()

# Synchronization interval (getRCP) in seconds: 6 hours to 8 days, the steps of the
# global option map within this range
SELECT_RCP_OPTIONS = [
    21600,
    43200,
    86400,
    172800,
    259200,
    345600,
    432000,
    518400,
    604800,
    691200,
]

# Alarm codes of the HygBox (raw API getALA -> internal translation key). "FF" = no alarm
# is assumed like on the other devices with the alarm codes A1-AF.
ALA_CODES = {
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


PROFILE = SyrConnectDeviceProfile(
    ala_codes=ALA_CODES,
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    select_options={
        "getRCP": SELECT_RCP_OPTIONS,
    },
    sensor=SENSOR_SUPPORTED_KEYS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
