"""Entity allowlist override for the neosoft_duo model family (dual-tank
NeoSoft platform rebrands: NeoSoft 5000 and every "*duo"/"twin" sibling
signature in dk=1200-1222 via "device_file": "neosoft_duo"). Single-tank
rebrands use the sibling neosoft_single.py instead.

Currently IDENTICAL to neosoft_single.py's confirmed keys - no genuine
real-device evidence exists yet for any second-tank key. The only available
capture with dual-tank data, tests/fixtures/xml/NeoSoft5000_GetDeviceCollectionStatus.xml,
is explicitly marked in its own XML comment as "Just for model tests. We
need a test machine to verify" (used only to satisfy the getRE1+getRE2
v_keys fingerprint required for model detection), so it is NOT treated as
proof of any key's real-world behavior:
- getRE2: has a real-looking, distinct non-zero value (999 vs getRE1=773)
  in that synthetic fixture, but since the fixture itself is unverified,
  this alone isn't sufficient evidence per the stricter standard applied
  elsewhere in this codebase (see neosoft_single.py's getBAR/getCEL/getCND
  history) - pending a real dual-tank capture.
- getSS2, getSV2: not present at all, even in the synthetic fixture.
- getVPS2: present but empty ("") in the synthetic fixture - no evidence.

If a real dual-tank device capture confirms any of getRE2/getSS2/getSV2/
getVPS2 (or getRG2, the tank-2 regeneration-running flag already in
const.py's global allowlist) with a genuine non-empty value, move it into
SENSOR_KNOWN_KEYS below.
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
