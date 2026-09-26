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

Unlike models where getSV1 is a manually-configured salt refill amount, this
platform has a built-in salt level sensor - getSV1 is read-only telemetry
here, so it stays sensor-only (SENSOR_KNOWN_KEYS) and is deliberately left
out of SELECT_KNOWN_KEYS to avoid exposing a control nobody should use.

Deliberately NOT included:
- getALD: 600 in JSON but empty ("") in XML - inconsistent, and 600 is the
  same generic value seen across several unrelated device families.
- getNPS: empty ("") in the XML fixture.
- getBAR, getCEL, getCND: empty ("") in the XML fixture and absent from the
  JSON fixture entirely - no real value in either capture. A prior version
  of this docstring cited "the official validity matrix" marking these ✓
  for NeoSoft 5000, but docs/syrconnect-protocol.md has no such matrix for
  NeoSoft models (its only "Per-model validity" matrix covers the unrelated
  TRIO Lock/SafeTech Lock/AC 3200/AC 3228/RSA family) - that citation was
  unverifiable, so these stay excluded until a real, non-empty capture
  confirms them.
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

# getSV1 excluded - built-in salt level sensor, not a manual setting (see module docstring).
SELECT_KNOWN_KEYS = {
    "getRPD", "getRMO", "getRTM",
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
