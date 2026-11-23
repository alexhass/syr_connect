"""Entity allowlist override for the neosoft_duo model family.

Dual-tank NeoSoft platform rebrands: NeoSoft 5000 and every "*duo"/"twin" sibling
signature in dk=1200-1222 via device_profile=neosoft_duo.PROFILE. Single-tank rebrands
use the sibling neosoft_single.py instead.

Derived from the real capture tests/fixtures/json/OptimaT2Dual_get_all.json
(Optima T2 Dual, firmware NSR.1.82): every getXXX key below is reported there.
getBAR/getCEL/getCND/getVPS2 are also confirmed ✓ (available) for NeoSoft 5000
by the "Per-model validity" matrix in docs/syrconnect-protocol.md.

The capture reports the reserve capacity of both resin tanks (getRE1/getRE2),
but not the regeneration-running flag of the second one (getRG2). The device
has only one salt tank, so the second set of salt keys (getSS2/getSV2) is not
included.

Deliberately NOT included:
- getNPS: 260 in the capture, but confirmed X (not available) for NeoSoft
  5000 by the "Per-model validity" matrix.
"""

from . import SyrConnectDeviceProfile

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Flow ---
    "getAVO",
    "getFLO",
    # --- Alarm / Notification / Warning ---
    "getALA",
    "getALM",
    "getALN",
    "getALW",
    "getNOT",
    "getWRN",
    # --- Pressure ---
    "getBAR",
    # --- Voltage ---
    "getNET",
    # --- Water Quality ---
    "getCEL",
    "getCND",
    "getIWH",
    "getOWH",
    "getWHU",
    # --- Water Consumption & Volume ---
    "getLTV",
    "getVOL",
    # --- Salt / Reserve Capacity ---
    "getRE1",
    "getRE2",
    "getSS1",
    "getSV1",
    # --- Regeneration ---
    "getCYN",
    "getCYT",
    "getLAR",
    "getRG1",
    "getRMO",
    "getRPD",
    "getRPW",
    "getRTI",
    # --- Turbine / Pulse Monitoring ---
    "getVPS1",
    "getVPS2",
    # --- Device Info & Diagnostics ---
    "getMAC1",
    "getMAC2",
    "getSRN",
    "getTMZ",
    "getTYP",
    "getVER",
    # --- Wi-Fi ---
    "getAPT",
    "getEGW",
    "getEIP",
    "getWFC",
    "getWFR",
    "getWFS",
    "getWGW",
    "getWIP",
}

# getSV1 excluded - built-in salt level sensor, not a manual setting (see neosoft_single.py docstring).
SELECT_SUPPORTED_KEYS = {
    "getRPD",
    "getRMO",
}

# getDFI (Conel Clear Pro Fill filling mode) deliberately excluded - no filling
# feature on this model.
SWITCH_SUPPORTED_KEYS = {
    "getBUZ",
}

BINARY_SENSOR_SUPPORTED_KEYS = {
    "getBUZ",
    "getIDS",
    "getSFV",
}

# setDEX excluded - no microleakage-test hardware on this model.
BUTTON_SUPPORTED_KEYS = {
    "setSIR",
    "setALA",
    "setNOT",
    "setWRN",
}

# No shutoff valve on this model (a conventional softener).
VALVE_SUPPORTED_KEYS: set[str] = set()


PROFILE = SyrConnectDeviceProfile(
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    sensor=SENSOR_SUPPORTED_KEYS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
