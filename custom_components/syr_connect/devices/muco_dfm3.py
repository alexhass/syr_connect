"""Entity allowlist override for the muco_dfm3 model (e.g. Conel Clear Pro Fill).

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists in const.py which have to
cover every supported model at once.

Deliberately NOT included, pending confirmation on a real device:
- getALD, getMIH, getMXH, getMIT, getMXT: labeled "(SafeFloor)" in const.py -
  a different product (humidity/flood sensor), unrelated to a filling
  controller.
- getDBD, getDRP, getDSV, getDTT: labeled "(Trio DFR/LS)" microleakage-test
  feature in const.py - a different product family.
- getSLE, getSLF, getSLP, getSLT, getSLV: labeled "(Trio DFR/LS)"
  self-learning-phase feature in const.py; also reported as constant 0 stub
  values in the fixture.
- getSRV: labeled "(Trio DFR/LS)" in const.py and empty ("") in the fixture.
- getPA1-8, getPB1-8, getPF1-8, getPM1-8, getPN1-8, getPR1-8, getPT1-8,
  getPV1-8, getPW1-8, getPRF: leak-protection profiles (LEXplus10SL feature),
  not applicable to this filling controller.

Deliberately removed on request despite being present in the fixture and the
global allowlist (confirmed not applicable to this device):
- getAB, getBAR, getCEL, getNPS, getRCP, getSTA, getTMP.

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below.
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve & Flow ---
    "getAVO", "getFLO", "getVLV",
    # --- Alarm / Notification / Warning ---
    "getALA", "getALM", "getALN", "getALW", "getNOT", "getWRN",
    # --- Pressure ---
    "getBAR2",
    # --- Voltage / Battery ---
    "getBAP", "getBAT", "getNET",
    # --- Water Quality ---
    "getCND", "getIWH", "getOHW", "getWHU",
    # --- Water Consumption & Volume ---
    "getLTV", "getVOL",
    # --- Device Status ---
    "getDFM",
    # --- Filter ---
    "getFFM",
    # --- Display ---
    "getSRO",
    # --- Device Info & Diagnostics ---
    "getEGW", "getEIP", "getLNG", "getMAC1", "getMAC2", "getSRN", "getVER",
    # --- Wi-Fi ---
    "getAPT", "getWFC", "getWFR", "getWFS", "getWGW", "getWIP",
    # --- Water treatment / Filling ---
    "getCRS", "getCRT", "getLOT", "getLRC", "getPRC", "getRCD", "getRMN", "getRMT",
    "getRVT", "getTPR",
}

# getRTM, getPRF, getSV1-3, getRPD, getRMO deliberately excluded: this is a filling
# controller with no regeneration/resin/salt containers and no leak-protection profiles.
SELECT_KNOWN_KEYS = {
    "getSRO", "getFFM",
    "getCRS", "getCRT", "getLOT", "getOHW", "getRCD", "getRMN", "getRMT", "getRVT", "getTPR",
}

SWITCH_KNOWN_KEYS = {
    "getBUZ", "getDFI",
}

# setSIR (no regeneration) and setDEX (Trio DFR/LS microleakage test, not applicable
# despite getDSV being present in the fixture) deliberately excluded.
BUTTON_KNOWN_KEYS = {
    "setALA", "setNOT", "setWRN",
}

# getAB (valve shutoff control) deliberately excluded on request; getVLV (read-only
# valve position, handled by the sensor platform) is unaffected.
VALVE_KNOWN_KEYS: set[str] = set()


