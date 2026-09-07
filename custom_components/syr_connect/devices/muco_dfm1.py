"""Entity allowlist override for the muco_dfm1 model (e.g. Leak Protection Module A25).

Derived from tests/fixtures/json/SanibelLeakProtectionModuleA25_get_all.json.
This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists in const.py which have to
cover every supported model at once.

Unlike the muco_dfm3 (filling controller) variant, the leak-protection-profile
keys ARE the core feature here (populated with real distinct values in the
fixture, e.g. getPN1="Anwesend"/getPN2="Abwesend") and getAB/getVLV are kept
since this model genuinely controls a shutoff valve.

Deliberately NOT included, pending confirmation on a real device:
- getMIH, getMXH, getMIT, getMXT: labeled "(SafeFloor)" in const.py -
  a different product (humidity/flood sensor), unrelated to this model.
  getALD is the one exception (see SENSOR_KNOWN_KEYS below).
- getCRS, getCRT, getLOT, getLRC, getOHW, getPRC, getRCD, getRMN, getRMT,
  getRVT, getTPR: labeled "(Conel Clear Pro Fill)" water treatment / filling
  feature in const.py - belongs to the muco_dfm3 filling-controller variant, not
  this leak-protection variant, despite being present (shared firmware).
- getSRV: labeled "(Trio DFR/LS)" in const.py and empty ("") in the fixture.
- getBAR: labeled "(Safe-T+)" in const.py, unrelated product; 0 in fixture.
- getCEL: temperature reading with no clear tie to leak protection; 0 in fixture.
- getRCP: generic cloud sync interval, not tied to any specific feature here.
- getDBD, getDRP, getDTT, getNPS: labeled "(Trio DFR/LS)" microleakage-test
  feature in const.py - a different product family. getDSV is the one
  exception (see BUTTON_KNOWN_KEYS below).
- getSLE, getSLP, getSLT, getSLV: labeled "(Trio DFR/LS)" self-learning-phase
  feature in const.py; reported as constant 0 in the fixture. getSLF is the
  one exception (reported as a real non-zero value, 3500) but left out here
  too pending confirmation since its siblings are all stub zeros.

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below.
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve & Flow ---
    "getAB", "getAVO", "getFLO", "getVLV",
    # --- Alarm / Notification / Warning ---
    "getALA", "getALM", "getALN", "getALW", "getNOT", "getWRN",
    # --- Pressure ---
    "getBAR2",
    # --- Voltage / Battery ---
    "getBAP", "getBAT", "getNET",
    # --- Water Quality ---
    "getCND", "getIWH", "getWHU",
    # --- Water Consumption & Volume ---
    "getLTV", "getVOL",
    # --- Device Status ---
    "getDFM", "getSTA",
    # --- Alarm Duration ---
    "getALD",
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
    "getFFM",
    # --- Display ---
    "getSRO",
    # --- Device Info & Diagnostics ---
    "getEGW", "getEIP", "getLNG", "getMAC1", "getMAC2", "getSRN", "getVER",
    # --- Wi-Fi ---
    "getAPT", "getWFC", "getWFR", "getWFS", "getWGW", "getWIP",
}

SELECT_KNOWN_KEYS = {
    "getPRF", "getSRO", "getFFM",
}

# getDFI (Conel Clear Pro Fill filling mode) deliberately excluded - belongs to the
# muco_dfm3 variant, not this leak-protection variant.
SWITCH_KNOWN_KEYS = {
    "getBUZ",
}

# setSIR (no regeneration) deliberately excluded. setDEX (microleakage test) is
# tentatively included: unlike the muco_dfm3 fixture, getDSV is non-zero (3) here and
# a microleakage test is thematically consistent with a leak-protection module -
# verify against a real device before relying on this.
BUTTON_KNOWN_KEYS = {
    "setALA", "setNOT", "setWRN", "setDEX",
}

# getAB (valve shutoff control) kept - this model genuinely controls a valve.
VALVE_KNOWN_KEYS = {
    "getAB",
}
