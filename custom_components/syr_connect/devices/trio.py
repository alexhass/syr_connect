"""Entity allowlist override for the trio model (Trio DFR/LS Connect, dk=1113/dkv=113).

Derived from BOTH tests/fixtures/json/TrioDFRLS_get_all.json (JSON API) and
tests/fixtures/xml/TrioDFRLS_GetDeviceCollectionStatus.xml (XML API) - the two
agree on every key discussed below. (TrioDFRLS_GetDeviceCollectionStatus_Bug1.xml
is a minimal bug-repro capture with only 4 keys and was not used for derivation.)
This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists in const.py which have to
cover every supported model at once.

Unlike every other device file so far, this model IS the genuine home of the
"(Trio DFR/LS)"-tagged const.py keys: the full microleakage-test group
(getDBD/getDRP/getDSV/getDTT/getNPS) and self-learning-phase group
(getSLE/getSLF/getSLP/getSLT/getSLV) are both included outright - getDSV=3 in
both fixtures, and getSLT/getSLV are non-zero (612/116) in both, proving the
self-learning phase was genuinely active, not a constant-0 stub. getNPS also
differs between the two fixtures (612 vs 6466), confirming it's a live value.
getPA1-8/etc. (leak-protection profiles) and getAB/getVLV (valve control) are
kept for the same reason as the muco_dfm1/safetplus leak-protection variants.

Deliberately NOT included:
- getBAR, getBAR2, getCEL, getCND: null/empty in both fixtures.
- getFFM, getSRO, getSRV, getWFL, getLNG: 0/empty/absent in both fixtures (no
  filter, display, maintenance-date, nearby-Wi-Fi-scan, or language feature
  confirmed on this model).
- Salt/resin/regeneration family and water treatment/filling family: not
  present in either fixture - no softener/filling hardware on this model.

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below.
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve & Flow ---
    "getAB", "getAVO", "getFLO", "getVLV",
    # --- Alarm / Notification / Warning ---
    "getALA", "getALM", "getNOT", "getWRN",
    # --- Voltage / Battery ---
    "getBAP", "getBAT", "getNET",
    # --- Alarm Duration ---
    "getALD",
    # --- Water Consumption & Volume ---
    "getLTV", "getVOL",
    # --- Self-Learning Phase (genuinely active in both fixtures) ---
    "getSLE", "getSLF", "getSLP", "getSLT", "getSLV",
    # --- Microleakage Test (genuinely active in both fixtures) ---
    "getDBD", "getDRP", "getDSV", "getDTT", "getNPS",
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
    # --- Device Info & Diagnostics ---
    "getEGW", "getEIP", "getMAC1", "getMAC2", "getSRN", "getVER",
    # --- Wi-Fi ---
    "getAPT", "getWFC", "getWFR", "getWFS", "getWGW", "getWIP",
}

SELECT_KNOWN_KEYS = {
    "getPRF",
}

# getDFI (Conel Clear Pro Fill filling mode) deliberately excluded - no filling
# feature on this model.
SWITCH_KNOWN_KEYS = {
    "getBUZ",
}

# setSIR (regeneration) deliberately excluded - no softener/regeneration hardware
# on this model (getSIR is present in the fixture but no other regeneration/salt
# keys accompany it). setDEX (microleakage test) included - getDSV=3 (non-zero)
# in both fixtures, plus getDBD/getDRP/getDTT all report real values.
BUTTON_KNOWN_KEYS = {
    "setALA", "setNOT", "setWRN", "setDEX",
}

# getAB (valve shutoff control) kept - this model genuinely controls a valve.
VALVE_KNOWN_KEYS = {
    "getAB",
}
