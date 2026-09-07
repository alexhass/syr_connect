"""Entity allowlist override for the lexplus10s model (LEX Plus 10 S Connect,
dk=80/dkv=25, sbt=2). Also used for the "lexplus10" (sbt=1) sibling signature
via "device_file": "lexplus10s" - no distinct fixture exists for the plain
"LEX Plus 10" (non-S) variant, and both share the same dk/dkv/hardware family,
differing only in maximum_salt_volume-style metadata already handled
elsewhere - pending confirmation if a real "LEX Plus 10" fixture ever exists.

Derived from tests/fixtures/xml/LEXplus10S_GetDeviceCollectionStatus.xml (no
JSON fixture exists for this model). Unlike the LEXplus10SL sibling, this
model has NO shutoff valve (no getAB/getVLV) and NO buzzer (no getBUZ), and
NO leak-protection-profile/microleakage-test family - it is a conventional
column softener, same shape as the plain "lex" family but with a few extra
regeneration-history diagnostics (getINR/getLAR/getNOR). It connects via LAN
by default, but - like LEX10 - may have an optional Wi-Fi module; the Wi-Fi
keys are included below even though the fixture doesn't have them, since
they are only ever created when actually present in a device's status.

Deliberately NOT included:
- getSTA: empty ("") in the fixture.
- getWRN: not present in the fixture (getNOT/getALM are present and used
  instead, via alarm_style_alm).

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below.
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
    "getCYN", "getCYT", "getINR", "getLAR", "getNOR", "getRG1", "getRG2", "getRG3",
    "getRPD", "getRPW", "getRTH", "getRTI", "getRTM", "getSCR", "getTOR",
    # --- Maintenance ---
    "getDWF", "getVS1", "getVS2", "getVS3",
    # --- Filter ---
    "getFCO", "getPST",
    # --- Device Info & Diagnostics ---
    "getCDE", "getCNA", "getDGW", "getFIR", "getIPA", "getMAC", "getMAN", "getSRN",
    "getTYP", "getVER",
    # --- Wi-Fi (optional module, same as the plain "lex" family) ---
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

# setWRN excluded - no getWRN in the fixture. setDEX excluded - no
# microleakage-test hardware on this model.
BUTTON_KNOWN_KEYS = {
    "setSIR", "setALA", "setNOT",
}

# No shutoff valve on this model (a conventional column softener).
VALVE_KNOWN_KEYS: set[str] = set()
