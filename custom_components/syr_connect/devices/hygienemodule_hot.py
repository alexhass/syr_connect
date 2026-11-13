"""Entity allowlist override for the hygiene module with the hot water line only.

Model: Hygiene Module (hot, dk=61/dkv=22).

Model type: Hygiene flushing

Provisional: no fixture of this device exists yet. The keys, ranges and alarm codes are
those of the hygiene module with two lines (hygienemodule.py), limited to the hot water
line (getSWF, getCWF, getWCL, getWSS, getWSL, setMFW).

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.
"""

from . import SyrConnectDeviceProfile
from .hygienemodule import ALA_CODES, SELECT_WCL_OPTIONS

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Alarm ---
    "getALA",
    # --- Voltage / Battery ---
    "getBAT",
    # --- Hygiene flushing (hot water line) ---
    "getCWF",
    "getSWF",
    "getWCL",
    "getWSL",
    "getWSS",
    # --- Device Info & Diagnostics ---
    "getMAC",
    "getSRN",
    "getVER",
}

SELECT_SUPPORTED_KEYS = {
    "getCWF",
    "getSWF",
    "getWCL",
    "getWSL",
    "getWSS",
}

SWITCH_SUPPORTED_KEYS: set[str] = set()

BINARY_SENSOR_SUPPORTED_KEYS: set[str] = set()

BUTTON_SUPPORTED_KEYS = {
    "setALA",
    "setMFW",
}

VALVE_SUPPORTED_KEYS: set[str] = set()

# Raw values written for "off", see hygienemodule.py
SELECT_OFF_VALUES = {
    "getCWF": 0,
    "getWCL": 54,
}


PROFILE = SyrConnectDeviceProfile(
    ala_codes=ALA_CODES,
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    select_off_values=SELECT_OFF_VALUES,
    select_options={
        "getWCL": SELECT_WCL_OPTIONS,
    },
    sensor=SENSOR_SUPPORTED_KEYS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
