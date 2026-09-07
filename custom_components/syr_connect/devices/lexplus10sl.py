"""Entity allowlist override for the lexplus10sl model (LEX Plus 10 SL Connect,
dk=80/dkv=25, sbt=7).

Derived from tests/fixtures/xml/LEXplus10SL_GetDeviceCollectionStatus.xml (no
JSON fixture exists for this model). Unlike the plain "lex"/lexplus10s
siblings, this is the flagship hybrid model: a full column softener (resin/
salt/regeneration) PLUS a shutoff valve (getAB/getVLV) PLUS the full 8-slot
leak-protection-profile family (getPA-PW1-8/getPRF, all populated with real
distinct values, e.g. getPN1="Anwesend"/getPN3="Neues Profil") PLUS a
self-learning phase that is genuinely active (getSLF=1818, getSLT=732,
getSLV=169 - all non-zero) PLUS partial microleakage-test config
(getDBD/getDRP/getNPS=3713, all real).

NOTE: unlike its lexplus10/lexplus10s siblings, this fixture reports getALA
(not getALM) for the current alarm code, even though this signature has
"alarm_style_alm": True in models.py (which makes button.py check for getALM
presence to gate the setALA button) - this may be worth revisiting in
models.py separately; not changed here since it's outside this file's scope.

Deliberately NOT included:
- getDSV, getDTT: not present in this fixture, unlike getDBD/getDRP/getNPS
  (present with real values) - the microleakage-test config keys are there,
  but the two status/result keys are missing from this capture.
- getT2, getTMP is kept but getT1/getLE/getUL are absent: only getT2 appears
  without its usual getT1/getLE/getUL siblings (the single-profile leak
  keys used by e.g. safetplus) - too little evidence to include getT2 alone.
- getBUZ: present but empty ("") in the fixture.
- getSIR is present but getWRN/getALM are not present at all in this fixture.
- getCNO: empty ("") in the fixture.
- No Wi-Fi keys in the fixture (LAN-only via getDGW/getIPA/getMAC), but like
  LEX10 an optional Wi-Fi module is possible - the Wi-Fi keys are included
  in SENSOR_KNOWN_KEYS below anyway, since they are only ever created when
  actually present in a device's status.

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below.
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve & Flow ---
    "getAB", "getAVO", "getFLO", "getVLV",
    # --- Alarm / Notification (getALA here, not getALM; no getWRN) ---
    "getALA", "getNOT",
    # --- Pressure ---
    "getPRS",
    # --- Water Quality ---
    "getCEL", "getCND", "getIWH", "getOWH", "getWHU",
    # --- Water Consumption & Volume ---
    "getCOF",
    # --- Device Status ---
    "getDEN",
    # --- Resin Capacity ---
    "getCS1", "getCS2", "getCS3",
    # --- Salt ---
    "getRDO", "getRES", "getSS1", "getSS2", "getSS3", "getSV1", "getSV2", "getSV3",
    # --- Regeneration ---
    "getCYN", "getCYT", "getINR", "getLAR", "getNOR", "getRG1", "getRPD", "getRPW",
    "getRTH", "getRTI", "getRTM", "getSCR", "getTOR",
    # --- Self-Learning Phase (genuinely active in the fixture) ---
    "getSLE", "getSLF", "getSLP", "getSLT", "getSLV",
    # --- Microleakage Test (config keys confirmed, no status/result keys yet) ---
    "getDBD", "getDRP", "getNPS",
    # --- Leak Protection (deactivation timer, tied to the profiles below) ---
    "getTMP",
    # --- Leak Protection Profiles 1-8 (core feature of this model) ---
    "getPA1", "getPA2", "getPA3", "getPA4", "getPA5", "getPA6", "getPA7", "getPA8",
    "getPB1", "getPB2", "getPB3", "getPB4", "getPB5", "getPB6", "getPB7", "getPB8",
    "getPF1", "getPF2", "getPF3", "getPF4", "getPF5", "getPF6", "getPF7", "getPF8",
    "getPM1", "getPM2", "getPM3", "getPM4", "getPM5", "getPM6", "getPM7", "getPM8",
    "getPN1", "getPN2", "getPN3", "getPN4", "getPN5", "getPN6", "getPN7", "getPN8",
    "getPR1", "getPR2", "getPR3", "getPR4", "getPR5", "getPR6", "getPR7", "getPR8",
    "getPT1", "getPT2", "getPT3", "getPT4", "getPT5", "getPT6", "getPT7", "getPT8",
    "getPV1", "getPV2", "getPV3", "getPV4", "getPV5", "getPV6", "getPV7", "getPV8",
    "getPW1", "getPW2", "getPW3", "getPW4", "getPW5", "getPW6", "getPW7", "getPW8",
    "getPRF",
    # --- Filter ---
    "getFCO", "getPST",
    # --- Maintenance ---
    "getDWF",
    # --- Device Info & Diagnostics (Lex10-only language field confirmed here) ---
    "getCDE", "getCNA", "getDGW", "getFIR", "getIPA", "getLAN", "getMAC", "getMAN",
    "getSRN", "getTYP", "getVER",
    # --- Wi-Fi (optional module, same as the plain "lex"/lexplus10s siblings) ---
    "getAPT", "getEGW", "getEIP", "getMAC1", "getMAC2", "getWFC", "getWFR", "getWFS",
    "getWGW", "getWIP",
}

SELECT_KNOWN_KEYS = {
    "getRPD", "getRTM", "getSV1", "getSV2", "getSV3", "getPRF",
}

# getBUZ present but empty in the fixture - no confirmed buzzer on this model.
SWITCH_KNOWN_KEYS: set[str] = set()
BINARY_SENSOR_KNOWN_KEYS: set[str] = set()

# setWRN excluded - no getWRN in the fixture. setDEX excluded - no getDSV in
# the fixture, despite getDBD/getDRP/getNPS being present.
BUTTON_KNOWN_KEYS = {
    "setSIR", "setALA", "setNOT",
}

# getAB (valve shutoff control) kept - this model genuinely controls a valve.
VALVE_KNOWN_KEYS = {
    "getAB",
}
