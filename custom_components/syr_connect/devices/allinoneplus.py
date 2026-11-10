"""Entity allowlist override for the allinoneplus model (All in One +, dk=160).

Model type: Filling the Heating System

Provisional: no fixture of this device exists yet. The allowlists are taken from
the muco_filling profile (Conel Clear Pro Fill, AC 3228 Connect), the closest
filling controller, and must be checked against a capture of a real device.

Differences to muco_filling:
- getDFM: not included, it is the role of a MultiController (dk 1500-1506).
- getCFV, getLFV, getTRV: reported in milliliters instead of liters (see issue 10
  in docs/known_issues_json_api.md).
- getOWH instead of getOHW: the soft water hardness of the HWE cartridge.
- getFFM, getLOT, getSRO: not included, the device has no filter type, no
  conductivity limit and no display rotation.

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.
"""

from . import WHU_UNITS_MUCO, SyrConnectDeviceProfile

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
    "getBAR",
    "getBAR2",
    # --- Voltage / Battery ---
    "getBAP",
    "getBAT",
    "getNET",
    # --- Alarm Duration ---
    "getALD",
    # --- Water Quality ---
    "getCND",
    "getCNF",
    "getIWH",
    "getOWH",
    "getWHU",
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
    "getLRC",
    "getPRC",
    "getRCC",
    "getRCD",
    "getRCN",
    "getRMN",
    "getRMT",
    "getRVT",
    "getTPR",
    # --- Filling ---
    "getCFT",
    "getCFV",
    "getLFT",
    "getLFV",
    "getNRT",
    "getTRT",
    "getTRV",
}

SELECT_SUPPORTED_KEYS = {
    "getCRS",
    "getCRT",
    "getOWH",
    "getRCD",
    "getRMN",
    "getRMT",
    "getRVT",
    "getTPR",
}

SWITCH_SUPPORTED_KEYS = {
    "getBUZ",
    "getDFI",
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

VALVE_SUPPORTED_KEYS: set[str] = set()


PROFILE = SyrConnectDeviceProfile(
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    sensor=SENSOR_SUPPORTED_KEYS,
    sensor_divide_by={
        "getCFV": 1000,
        "getLFV": 1000,
        "getTRV": 1000,
    },
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
    whu_units=WHU_UNITS_MUCO,
)
