"""Entity allowlist override for the hva model (HVA, dk=20).

Model type: Filling the Heating System

Provisional: no fixture of this device exists yet. The allowlists hold the keys known
for the HVA that have an entity description, and must be checked against a capture of
a real device.

Deliberately NOT included:
- getRCP: on the HVA the remaining capacity in the format "<n> (<m>L)", not the
  settings synchronization interval of the sensor and select descriptions (see
  docs/syrconnect-protocol.md).
- getBAT: reported, but without a known meaning on the HVA.

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.
"""

from . import NOT_CODES_NONE, WRN_CODES_NONE, SyrConnectDeviceProfile

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve ---
    "getVLV",
    # --- Alarm / Notification / Warning ---
    "getALA",
    "getALM",
    "getNOT",
    "getWRN",
    # --- Pressure ---
    "getBAR",
    # --- Device Info & Diagnostics ---
    "getSRN",
    "getVER",
}

SELECT_SUPPORTED_KEYS: set[str] = set()

SWITCH_SUPPORTED_KEYS: set[str] = set()

BINARY_SENSOR_SUPPORTED_KEYS = {
    "getSFV",
}

BUTTON_SUPPORTED_KEYS = {
    "setALA",
    "setNOT",
    "setWRN",
}

VALVE_SUPPORTED_KEYS: set[str] = set()

# Alarm codes of the HVA (raw API getALA -> internal translation key)
ALA_CODES = {
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


PROFILE = SyrConnectDeviceProfile(
    ala_codes=ALA_CODES,
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    not_codes=NOT_CODES_NONE,
    select=SELECT_SUPPORTED_KEYS,
    sensor=SENSOR_SUPPORTED_KEYS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
    wrn_codes=WRN_CODES_NONE,
)
