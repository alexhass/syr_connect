"""Entity allowlist override for the allinoneplus model (All-in-One+, dk=160).

Model type: Filling the Heating System

The allowlists hold the keys that a real device (firmware All-in-One+ V4.05) reports
in the fixtures of the local JSON API and the cloud XML API.

The device reports the current and the last filling volume (getCFV, getLFV) in
milliliters, see issue 10 in docs/known_issues_json_api.md. The cumulative refilled
volume (getTRV) is in liters.

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.
"""

from . import SyrConnectDeviceProfile

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
    "getIBA",
    # --- Voltage / Battery ---
    "getBAT",
    "getNET",
    # --- Alarm Duration ---
    "getALD",
    # --- Water Quality ---
    "getCEL",
    "getCNF",
    "getIWH",
    "getLW1",
    "getLW2",
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
    "getMQT",
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


PROFILE = SyrConnectDeviceProfile(
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    sensor=SENSOR_SUPPORTED_KEYS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
