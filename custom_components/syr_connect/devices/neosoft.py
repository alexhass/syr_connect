"""Entity allowlist override for the neosoft model family (NeoSoft platform,
dk=1200-1222 - shared by "neosoft"/"neosoft2500"/"neosoft5000" and every
rebrand-only sibling signature in this dk range via "device_file": "neosoft").

Derived from BOTH tests/fixtures/json/NeoSoft2500_get_all.json (JSON API) and
tests/fixtures/xml/NeoSoft2500_GetDeviceCollectionStatus.xml (XML API) - the
two agree on every key below, and several differ in value between the two
captures (e.g. getLAR, getLTV, getRE1, getRPD, getSS1, getSV1, getVOL,
getVPS1), confirming they are genuinely live rather than stubs.
(NeoSoft5000_GetDeviceCollectionStatus.xml is explicitly marked in its own
XML comment as "Just for model tests. We need a test machine to verify" - a
synthetic capture for model-detection unit tests only, NOT used here.)

Unlike the "lex" family, this platform uses a "reserve capacity" salt/tank
schema (getRE1/getRE2) instead of the "resin capacity %" schema (getCS1-3),
and it does have Wi-Fi (getWFC/getWFL/getWFR/getWFS/getWGW/getWIP) instead of
the LAN-only getDGW/getIPA/getMAC used by the lex family. It has NO shutoff
valve (no getAB/getVLV) and NO battery (no getBAT/getBAP).

Deliberately NOT included:
- getALD: 600 in JSON but empty ("") in XML - inconsistent, and 600 is the
  same generic value seen across several unrelated device families.
- getBAR, getCEL, getCND, getNPS: empty ("") in the XML fixture.
- getRE2, getSS2, getSV2, getVPS2 (second-tank keys): not present in this
  single-tank fixture - only relevant for genuinely dual-tank rebrands
  (e.g. the "*duo" signatures); not confirmed here, pending a real fixture.

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below.
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Flow ---
    "getAVO", "getFLO",
    # --- Alarm / Notification / Warning ---
    "getALA", "getALM", "getALN", "getALW", "getNOT", "getWRN",
    # --- Water Quality ---
    "getIWH", "getOWH", "getWHU",
    # --- Water Consumption & Volume ---
    "getLTV", "getVOL",
    # --- Salt / Reserve Capacity ---
    "getRE1", "getSS1", "getSV1",
    # --- Regeneration ---
    "getCYN", "getCYT", "getLAR", "getRG1", "getRMO", "getRPD", "getRPW", "getRTI",
    "getRTM",
    # --- Maintenance ---
    "getSRH", "getSRV",
    # --- Turbine / Pulse Monitoring ---
    "getVPS1",
    # --- Device Info & Diagnostics ---
    "getMAC1", "getMAC2", "getSRN", "getTYP", "getVER",
    # --- Wi-Fi ---
    "getAPT", "getEGW", "getEIP", "getWFC", "getWFL", "getWFR", "getWFS", "getWGW",
    "getWIP",
}

SELECT_KNOWN_KEYS = {
    "getRPD", "getRMO", "getRTM", "getSV1",
}

# getDFI (Conel Clear Pro Fill filling mode) deliberately excluded - no filling
# feature on this model.
SWITCH_KNOWN_KEYS = {
    "getBUZ",
}

# setDEX excluded - no microleakage-test hardware on this model.
BUTTON_KNOWN_KEYS = {
    "setSIR", "setALA", "setNOT", "setWRN",
}

# No shutoff valve on this model (a conventional softener).
VALVE_KNOWN_KEYS: set[str] = set()
