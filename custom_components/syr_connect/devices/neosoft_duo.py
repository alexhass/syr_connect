"""Entity allowlist override for the neosoft_duo model family (dual-tank
NeoSoft platform rebrands: NeoSoft 5000 and every "*duo"/"twin" sibling
signature in dk=1200-1222 via "device_file": "neosoft_duo"). Single-tank
rebrands use the sibling neosoft_single.py instead.

getBAR/getCEL/getCND/getVPS2 are confirmed ✓ (available) for NeoSoft 5000
specifically by the now-complete "Per-model validity" matrix in
docs/syrconnect-protocol.md (X for NeoSoft 2500, hence neosoft_single.py
correctly excludes them) - included below on that authority, overriding the
earlier decision to exclude them pending fixture confirmation.

No genuine real-device evidence exists yet for the remaining second-tank
keys (getRE2/getSS2/getSV2), which aren't covered by the matrix at all. The
only available capture with dual-tank data,
tests/fixtures/xml/SyrNeoSoft5000_GetDeviceCollectionStatus.xml, is explicitly
marked in its own XML comment as "Just for model tests. We need a test
machine to verify" (used only to satisfy the getRE1+getRE2 v_keys
fingerprint required for model detection), so it is NOT treated as proof:
- getRE2: has a real-looking, distinct non-zero value (999 vs getRE1=773)
  in that synthetic fixture, but the fixture itself is unverified - pending
  a real dual-tank capture.
- getSS2, getSV2: not present at all, even in the synthetic fixture.

If a real dual-tank device capture confirms getRE2/getSS2/getSV2 (or getRG2,
the tank-2 regeneration-running flag already in const.py's global
allowlist) with a genuine non-empty value, move it into SENSOR_KNOWN_KEYS
below.
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Flow ---
    "getAVO", "getFLO",
    # --- Alarm / Notification / Warning ---
    "getALA", "getALM", "getALN", "getALW", "getNOT", "getWRN",
    # --- Pressure ---
    "getBAR",
    # --- Water Quality ---
    "getCEL", "getCND", "getIWH", "getOWH", "getWHU",
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
    "getVPS1", "getVPS2",
    # --- Device Info & Diagnostics ---
    "getMAC1", "getMAC2", "getSRN", "getTYP", "getVER",
    # --- Wi-Fi ---
    "getAPT", "getEGW", "getEIP", "getWFC", "getWFL", "getWFR", "getWFS", "getWGW",
    "getWIP",
}

# getSV1 excluded - built-in salt level sensor, not a manual setting (see neosoft_single.py docstring).
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
