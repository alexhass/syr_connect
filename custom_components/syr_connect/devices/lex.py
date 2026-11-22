"""Entity allowlist override for the lex model family.

Covers i-LEX / LEX conventional softeners (dk=40/dkv=16), shared by all l10-l100
and lex10-lex100 signatures via device_profile=lex.PROFILE.

Derived from tests/fixtures/xml/SyrL20_GetDeviceCollectionStatus.xml and
tests/fixtures/xml/SyrLEX30_GetDeviceCollectionStatus.xml (no JSON fixture exists
for this family). Both fixtures agree on every key below; where a value
differs between the two (e.g. getMAN="Oceanic"/"Syr", getIWH=36/20), that is
treated as strong evidence the key is genuinely live, not a stub.

This is a conventional column softener with NO shutoff valve (no getAB/getVLV)
and NO buzzer (no getBUZ). It connects via LAN (getDGW/getIPA/getMAC). It has NO
leak-protection-profile family or microleakage test.

Deliberately NOT included:
- getPA1, getPA2, getPA3: constant 0 in both fixtures, and only 3 slots instead
  of an 8-slot leak-protection-profile family - no confirmed meaning for this
  device.
- getWRN: not present in either fixture (no warning-code feature on this
  family; getNOT/getALM are present and used instead).
- getHED, getHEM, getHEY, getHSD, getHSM, getHSY, getVAC: present in the
  fixtures but not in the global sensor.py allowlist at all (undocumented
  keys).

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_SUPPORTED_KEYS below (after adding them to the
global sensor.py allowlist first).
"""

from . import WHU_UNITS_LEX, SyrConnectDeviceProfile

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Flow ---
    "getFLO",
    # --- Alarm / Notification (alarm_style_alm: getALM/getNOT, no getALA/getWRN) ---
    "getALM",
    "getNOT",
    # --- Pressure ---
    "getPRS",
    # --- Water Quality ---
    "getIWH",
    "getOWH",
    "getWHU",
    # --- Device Status ---
    # --- Resin Capacity ---
    "getCS1",
    "getCS2",
    "getCS3",
    # --- Salt ---
    "getRDO",
    "getRES",
    "getSS1",
    "getSS2",
    "getSS3",
    "getSV1",
    "getSV2",
    "getSV3",
    # --- Regeneration ---
    "getCYN",
    "getCYT",
    "getRG1",
    "getRG2",
    "getRG3",
    "getRPD",
    "getRPW",
    "getRTI",
    "getRTM",
    "getSCR",
    "getTOR",
    # --- Maintenance ---
    "getDWF",
    # --- Filter ---
    "getFCO",
    "getPST",
    # --- Device Info & Diagnostics ---
    "getCNA",
    "getDGW",
    "getFIR",
    "getIPA",
    "getMAC",
    "getMAN",
    "getSRN",
    "getTYP",
    "getVER",
}

SELECT_SUPPORTED_KEYS = {
    "getIWH",
    "getOWH",
    "getRPD",
    "getRTM",
    "getSV1",
    "getSV2",
    "getSV3",
}

# No buzzer on this model.
SWITCH_SUPPORTED_KEYS: set[str] = set()

# No buzzer on this model.
BINARY_SENSOR_SUPPORTED_KEYS: set[str] = set()

# setWRN excluded - no getWRN in either fixture. setDEX excluded - no
# microleakage-test hardware on this model.
BUTTON_SUPPORTED_KEYS = {
    "setSIR",
    "setALA",
    "setNOT",
}

# No shutoff valve on this model (a conventional column softener).
VALVE_SUPPORTED_KEYS: set[str] = set()


PROFILE = SyrConnectDeviceProfile(
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    sensor=SENSOR_SUPPORTED_KEYS,
    sensor_factors={
        "getFLO": 60,
    },
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
    whu_units=WHU_UNITS_LEX,
)
