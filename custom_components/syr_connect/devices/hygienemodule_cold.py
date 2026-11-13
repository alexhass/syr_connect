"""Entity allowlist override for the hygiene module with the cold water line only.

Model: Hygiene Module (cold, dk=60/dkv=21).

Model type: Hygiene flushing

Provisional: no fixture of this device exists yet. The keys, ranges and alarm codes are
those of the hygiene module with two lines (hygienemodule.py), limited to the cold
water line (getSCF, getCCF, getCCL, getCSS, getCSL, setMFC).

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.
"""

from . import SyrConnectDeviceProfile
from .hygienemodule import ALA_CODES, SELECT_CCL_OPTIONS

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Alarm ---
    "getALA",
    # --- Voltage / Battery ---
    "getBAT",
    # --- Hygiene flushing (cold water line) ---
    "getCCF",
    "getCCL",
    "getCSL",
    "getCSS",
    "getSCF",
    # --- Device Info & Diagnostics ---
    "getMAC",
    "getSRN",
    "getVER",
}

SELECT_SUPPORTED_KEYS = {
    "getCCF",
    "getCCL",
    "getCSL",
    "getCSS",
    "getSCF",
}

SWITCH_SUPPORTED_KEYS: set[str] = set()

BINARY_SENSOR_SUPPORTED_KEYS: set[str] = set()

BUTTON_SUPPORTED_KEYS = {
    "setALA",
    "setMFC",
}

VALVE_SUPPORTED_KEYS: set[str] = set()

# Raw values written for "off", see hygienemodule.py
SELECT_OFF_VALUES = {
    "getCCF": 0,
    "getCCL": 14,
}


PROFILE = SyrConnectDeviceProfile(
    ala_codes=ALA_CODES,
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    select_off_values=SELECT_OFF_VALUES,
    select_options={
        "getCCL": SELECT_CCL_OPTIONS,
    },
    sensor=SENSOR_SUPPORTED_KEYS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
