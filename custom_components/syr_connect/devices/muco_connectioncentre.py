"""Entity allowlist override for the muco_connectioncentre model.

SYR AC 3200 Connect (dkv=506, getDFM=2), "Connection centre"/"Anschlusscenter" role,
and its rebrands of the other MultiController brands.

Model type: Connection Centre / "Anschlusscenter": fills the heating system, with water
treatment (cartridge) and filling limits.

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.

No real-device or fixture capture exists for this variant yet. The keys are taken
from docs/syrconnect-protocol.md: the official validity matrix (getBAR2, getBAT,
getBUZ, getCND, getFLO, getSRN, getVER and the filling values getCFT, getCFV, getLFT,
getLFV, getNRT, getTRT, getTRV), the filling cycles (getRCC, getRCD, getRCN, getRMN)
and the water treatment and filling settings of the "Filling the Heating System"
section, plus the baseline connectivity/alarm/device-info/Wi-Fi keys of the other
muco_*.py device files. Verify against a real device before relying on this.

Deliberately NOT included, pending confirmation on a real device:
- getAVO, getBAR, getCEL, getLTV, getVOL, getVPS1, getVPS2: marked X (not
  available) for this model in the validity matrix.
- Leak-protection-profile family (getPA-PW1-8, getPRF) and valve control
  (getAB): this is a "Connection centre" role, not a leak-protection variant.

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_SUPPORTED_KEYS below.
"""

from . import SyrConnectDeviceProfile

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve & Flow ---
    "getFLO",
    "getVLV",
    # --- Alarm / Notification / Warning ---
    "getALA",
    "getALM",
    "getALN",
    "getALW",
    "getNOT",
    "getWRN",
    # --- Pressure ---
    "getBAR2",
    # --- Voltage / Battery ---
    "getBAP",
    "getBAT",
    # --- Water Quality ---
    "getCND",
    "getIWH",
    "getOHW",
    "getWHU",
    # --- Device Status ---
    "getDFM",
    # --- Display ---
    "getSRO",
    # --- Device Info & Diagnostics ---
    "getEGW",
    "getEIP",
    "getLNG",
    "getMAC1",
    "getMAC2",
    "getSRN",
    "getTMZ",
    "getVER",
    # --- Wi-Fi ---
    "getAPT",
    "getWFC",
    "getWFR",
    "getWFS",
    "getWGW",
    "getWIP",
    # --- Water treatment / Filling ---
    "getCRS",
    "getCRT",
    "getCWL",
    "getFMT",
    "getFVT",
    "getLOT",
    "getLRC",
    "getPRC",
    "getRCC",
    "getRCD",
    "getRCN",
    "getRMN",
    "getRMT",
    "getRVT",
    "getTPR",
    # --- Lock / Connection Centre ---
    "getCFT",
    "getCFV",
    "getLFT",
    "getLFV",
    "getNRT",
    "getTRT",
    "getTRV",
}

SELECT_SUPPORTED_KEYS = {
    "getSRO",
    "getCRS",
    "getCRT",
    "getCWL",
    "getFMT",
    "getFVT",
    "getIWH",
    "getLOT",
    "getOHW",
    "getRCD",
    "getRMN",
    "getRMT",
    "getRVT",
    "getTPR",
}

SWITCH_SUPPORTED_KEYS = {
    "getBUZ",
    "getDFI",
    "getIFL",
}

BINARY_SENSOR_SUPPORTED_KEYS = {
    "getBUZ",
    "getIDS",
    "getSFV",
}

BUTTON_SUPPORTED_KEYS = {
    "setALA",
    "setNOT",
    "setWRN",
}

# No shutoff valve confirmed for this "Connection centre" role.
VALVE_SUPPORTED_KEYS: set[str] = set()


PROFILE = SyrConnectDeviceProfile(
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    sensor=SENSOR_SUPPORTED_KEYS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
