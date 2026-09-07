"""Entity allowlist override for the lex model family (i-LEX / LEX conventional
softeners, dk=40/dkv=16 - shared by all l10-l100 and lex10-lex100 signatures
via "device_file": "lex").

Derived from tests/fixtures/xml/L20_GetDeviceCollectionStatus.xml and
tests/fixtures/xml/LEX30_GetDeviceCollectionStatus.xml (no JSON fixture exists
for this family). Both fixtures agree on every key below; where a value
differs between the two (e.g. getMAN="Oceanic"/"Syr", getIWH=36/20), that is
treated as strong evidence the key is genuinely live, not a stub.

Unlike the LEX Plus 10 SL / SafeTech(+) / Trio DFR/LS variants, this is a
conventional column softener with NO shutoff valve (no getAB/getVLV) and NO
buzzer (no getBUZ). It connects via LAN (getDGW/getIPA/getMAC) by default,
but some units (e.g. LEX10) have an optional Wi-Fi module - the Wi-Fi keys
are included below even though neither fixture has them, since they are
only ever created when actually present in a device's status. It has NO
leak-protection-profile family or microleakage test.

Deliberately NOT included:
- getPA1, getPA2, getPA3: constant 0 in both fixtures, and only 3 slots (not
  the 8-slot leak-protection-profile family used elsewhere) - no confirmed
  meaning for this device.
- getWRN: not present in either fixture (no warning-code feature on this
  family; getNOT/getALM are present and used instead).
- getHED, getHEM, getHEY, getHSD, getHSM, getHSY, getVAC: present in the
  fixtures but not in the global const.py allowlist at all (undocumented
  keys).

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below (after adding them to the
global const.py allowlist first).
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Flow ---
    "getFLO",
    # --- Alarm / Notification (alarm_style_alm: getALM/getNOT, no getALA/getWRN) ---
    "getALM", "getNOT",
    # --- Pressure ---
    "getPRS",
    # --- Water Quality ---
    "getIWH", "getOWH", "getWHU",
    # --- Device Status ---
    "getDEN",
    # --- Resin Capacity ---
    "getCS1", "getCS2", "getCS3",
    # --- Salt ---
    "getRDO", "getRES", "getSS1", "getSS2", "getSS3", "getSV1", "getSV2", "getSV3",
    # --- Regeneration ---
    "getCYN", "getCYT", "getRG1", "getRG2", "getRG3", "getRPD", "getRPW", "getRTH",
    "getRTI", "getRTM", "getSCR", "getTOR",
    # --- Maintenance ---
    "getDWF", "getVS1", "getVS2", "getVS3",
    # --- Filter ---
    "getFCO", "getPST",
    # --- Device Info & Diagnostics ---
    "getCDE", "getCNA", "getDGW", "getFIR", "getIPA", "getMAC", "getMAN", "getSRN",
    "getTYP", "getVER",
    # --- Wi-Fi (optional module on some units, e.g. LEX10) ---
    "getAPT", "getEGW", "getEIP", "getMAC1", "getMAC2", "getWFC", "getWFR", "getWFS",
    "getWGW", "getWIP",
}

SELECT_KNOWN_KEYS = {
    "getRPD", "getRTM", "getSV1", "getSV2", "getSV3",
}

# No buzzer on this model.
SWITCH_KNOWN_KEYS: set[str] = set()

# No buzzer on this model.
BINARY_SENSOR_KNOWN_KEYS: set[str] = set()

# setWRN excluded - no getWRN in either fixture. setDEX excluded - no
# microleakage-test hardware on this model.
BUTTON_KNOWN_KEYS = {
    "setSIR", "setALA", "setNOT",
}

# No shutoff valve on this model (a conventional column softener).
VALVE_KNOWN_KEYS: set[str] = set()
