"""Entity allowlist override for the allinoneplus model (All-in-One+, dk=160).

Model type: Filling the Heating System

The allowlists hold the keys that a real device (firmware All-in-One+ V4.05) reports
in the fixtures of the local JSON API and the cloud XML API.

The device reports the filling volumes in milliliters, see issue 10 in
docs/known_issues_json_api.md.

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
    # --- Alarm ---
    "getALA",
    "getALM",
    # --- Pressure ---
    "getBAR",
    # --- Voltage / Battery ---
    "getBAT",
    "getNET",
    # --- Alarm Duration ---
    "getALD",
    # --- Water Quality ---
    "getCEL",
    "getCNF",
    "getIWH",
    "getOWH",
    "getWHU",
    # --- Device Info & Diagnostics ---
    "getLNG",
    "getMAC",
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
    "getFCS",
    "getFMT",
    "getFVT",
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
    "getCWL",
    "getFCS",
    "getFMT",
    "getFVT",
    "getIWH",
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
    "getIFL",
    "getMFL",
}

BINARY_SENSOR_SUPPORTED_KEYS = {
    "getBUZ",
    "getIDS",
    "getSFV",
}

BUTTON_SUPPORTED_KEYS = {
    "setALA",
}

VALVE_SUPPORTED_KEYS: set[str] = set()

# Maximum filling duration (getRMT) in minutes: 5-20 in steps of 5, 30-50 in steps of 10,
# 60-720 in steps of 30
SELECT_RMT_OPTIONS = sorted(
    {
        *range(5, 21, 5),
        *range(30, 51, 10),
        *range(60, 721, 30),
    }
)


# Water hardness ranges per unit: getWHU code -> (lowest, highest, step) in that unit.
# The soft water hardness (getOWH) can be at most the raw water hardness (getIWH).
HARDNESS_RANGES = {
    "getIWH": {
        0: (1, 50, 1),  # °dH
        1: (1, 65, 1),  # °e
        2: (1, 90, 1),  # °fH
        3: (10, 900, 10),  # ppm
    },
    "getOWH": {
        0: (0, 12, 1),  # °dH
        1: (0, 16, 1),  # °e
        2: (0, 22, 1),  # °fH
        3: (0, 220, 10),  # ppm
    },
}


PROFILE = SyrConnectDeviceProfile(
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    cartridge_keys={
        "0": "getOWH",
    },
    hardness_ranges=HARDNESS_RANGES,
    select=SELECT_SUPPORTED_KEYS,
    select_options={
        "getRMT": SELECT_RMT_OPTIONS,
    },
    sensor=SENSOR_SUPPORTED_KEYS,
    sensor_divisors={
        "getCFV": 1000,
        "getLFV": 1000,
        "getTRV": 1000,
    },
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
    whu_units=WHU_UNITS_MUCO,
)
