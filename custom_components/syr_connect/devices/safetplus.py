"""Entity allowlist override for the safetplus model (Safe-T+ Connect, dk=1/dkv=6).

Derived from tests/fixtures/xml/SyrSafeTPlus_GetDeviceCollectionStatus.xml (this
model has no JSON API fixture - it is only reachable via the XML API).
This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.

Unlike the LEXplus10SL / SafeTech(+) leak-protection variants, this model has
only a SINGLE leak-protection profile (no getPA1-8/getPRF numbered-profile
family) - it uses the plain getLE/getT1/getT2/getUL/getTMP keys instead.
It also has no Wi-Fi module (no getWFC/getWFR/getWFS/getEGW/getEIP/getMAC1/
getMAC2/getAPT in the fixture) and no getFLO/getNOT/getWRN/getDSV/getDTT.
getDMA (microleakage alarm mode) is present with a real value and included.

Deliberately NOT included, pending confirmation on a real device:
- getDST, getDTC, getDBT, getDCM, getDOM, getDPL: present in the fixture but
  not in the global sensor.py allowlist at all (undocumented/unclear keys).
- getBSA, getBSI, getBLT, getUNI, getTC, getTO, getTPA, getTBS, getREL,
  getEXI, getEXT, getFLL, getINT, get71: same as above - not in the global
  allowlist, meaning not confirmed for use across the integration.

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_SUPPORTED_KEYS below (after adding them to the
global sensor.py allowlist first).
"""

from . import SyrConnectDeviceProfile

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve & Flow ---
    "getAB",
    "getAVO",
    "getVLV",
    # --- Alarm / Notification / Warning ---
    "getALA",
    "getALM",
    # --- Pressure ---
    "getBAR",
    # --- Voltage / Battery ---
    "getBAT",
    "getNET",
    # --- Water Quality ---
    "getCEL",
    # --- Water Consumption & Volume ---
    "getVOL",
    # --- Microleakage Test ---
    "getDBD",
    "getDMA",
    "getDRP",
    "getNPS",
    # --- Leak Protection (single profile only, no numbered profile family) ---
    "getLE",
    "getT1",
    "getT2",
    "getTMP",
    "getUL",
    # --- Device Info & Diagnostics ---
    "getLNG",
    "getSRN",
    "getTYP",
    "getVER",
}

# No select-worthy keys present for this model (no display rotation, no
# regeneration/filling/salt configuration, no numbered leak-protection profiles).
SELECT_SUPPORTED_KEYS: set[str] = set()

SWITCH_SUPPORTED_KEYS = {
    "getBUZ",
}

BINARY_SENSOR_SUPPORTED_KEYS = {
    "get71",
    "getBUZ",
}

# setSIR (regeneration) and setDEX (microleakage test, no getDSV present)
# deliberately excluded. setNOT/setWRN excluded - no getNOT/getWRN in the
# fixture for this model.
BUTTON_SUPPORTED_KEYS = {
    "setALA",
}

# getAB (valve shutoff control) kept - this model genuinely controls a valve.
VALVE_SUPPORTED_KEYS = {
    "getAB",
}

# Alarm codes of the Safe-T family (raw API getALA -> internal translation key)
ALA_CODES = {
    "A0": "alarm_safet_microleakage_detected",
    "A1": "alarm_safet_valve_cannot_be_operated",
    "A2": "alarm_safet_turbine_no_signal",
    "A3": "alarm_safet_leakage_volume_reached",
    "A4": "alarm_safet_flow_leakage_detected",
    "A5": "alarm_safet_absence_leakage_detected",
    "A6": "alarm_safefloor_flood",
    "A7": "alarm_external_sensor_leakage_radio",
    "A8": "alarm_external_sensor_leakage_cable",
    "A9": "alarm_safet_flow_time_exceeded",
    "AA": "alarm_temperature_sensor_faulty",
    "AB": "alarm_battery_weak",
    "AE": "error_no_information",
    "FF": "no_alarm",
    "LOWBAT": "alarm_battery_low",
    "WEAKBAT": "alarm_battery_weak",
}


PROFILE = SyrConnectDeviceProfile(
    ala_codes=ALA_CODES,
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    sensor=SENSOR_SUPPORTED_KEYS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
