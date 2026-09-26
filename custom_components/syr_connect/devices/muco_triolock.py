"""Entity allowlist override for the muco_triolock model (SYR TRIO Lock Connect, dkv=506, getDFM=5).

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists in const.py which have to
cover every supported model at once.

Derived from tests/fixtures/xml/SyrTrioLock_GetDeviceCollectionStatus.xml,
the first real-device capture for this model. Like muco_leakprotect (the
other dkv=506 role that genuinely controls a valve), this "Lock Connect"
role DOES report a shutoff valve (getAB=False/getVLV=20) and the full
8-slot leak-protection-profile family populated with real distinct values
(getPA1/getPA2=True, getPN1="Anwesend"/getPN2="Abwesend", getPRF=1).
Unlike muco_leakprotect's all-stub-zero microleakage-test config, this
fixture also has genuinely populated values (getDBD=10, getDMA=1, getDRP=2,
getDTT="04:00" - a real formatted duration, not a zero stub), so those are
included here too, along with setDEX (gated on getDSV presence, matching
the getDSV-gating in muco_leakprotect).

Deliberately NOT included:
- getCEL, getBAR, getCND: 0 in the fixture, and the official "Per-model
  validity" matrix (docs/syrconnect-protocol.md) explicitly marks CEL/BAR/
  CND as X (not available) for TRIO Lock specifically - the matrix takes
  precedence over the muco_leakprotect sibling's inclusion of getCND, since
  that file's fixture is actually the unrelated A25 Leak Protection Module
  (dkv=501), a product not covered by this TRIO-Lock-specific matrix.
- getTYP: 0 in the fixture; no other muco_*.py sibling includes it either.
- getT2: appears alone without its usual getT1/getLE/getUL siblings (the
  single-profile leak keys) - too little evidence to include alone, same
  reasoning as lexplus10sl.py.
- Self-learning phase (getSLE/getSLF/getSLP/getSLT/getSLV): all reported as
  constant 0 in the fixture - same stub pattern muco_leakprotect excluded
  (even a genuinely non-zero getSLF was left out there pending confirmation).
- getVPS1, getVPS2, getIWH, getOWH, getWHU, getSTA, getTMP: not present in
  the fixture at all.

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
    # --- Water Consumption & Volume ---
    "getLTV", "getVOL",
    # --- Alarm Duration ---
    "getALD",
    # --- Microleakage Test ---
    "getDBD", "getDMA", "getDRP", "getDSV", "getDTT", "getNPS",
    # --- Leak Protection Profiles 1-8 ---
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
    # --- Lock / Connection Centre ---
    "getNMS", "getNMT", "getNPT",
    # --- Device Status ---
    "getDFM",
    # --- Device Info & Diagnostics ---
    "getEGW", "getEIP", "getLNG", "getMAC1", "getMAC2", "getSRN", "getVER",
    # --- Wi-Fi ---
    "getAPT", "getWFC", "getWFR", "getWFS", "getWGW", "getWIP",
}

SELECT_KNOWN_KEYS = {
    "getPRF", "getSRO", "getFFM",
}

SWITCH_KNOWN_KEYS = {
    "getBUZ",
}

# setDEX (microleakage test) gated on getDSV presence, matching muco_leakprotect.
BUTTON_KNOWN_KEYS = {
    "setALA", "setNOT", "setWRN", "setDEX",
}

# getAB (valve shutoff control) kept - this model genuinely controls a valve.
VALVE_KNOWN_KEYS = {
    "getAB",
}
