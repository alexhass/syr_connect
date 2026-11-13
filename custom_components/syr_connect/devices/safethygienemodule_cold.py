"""Entity allowlist override for the Safe-T Hygiene module with the cold water line only.

Model: Safe-T Hygiene module (front-wall installation, dk=4/dkv=5).

Model type: Hygiene flushing with shut-off valve

Provisional: no fixture of this device exists yet. The keys, ranges and alarm codes are
those of the Safe-T Hygiene module with two lines (safethygienemodule.py), limited to
the cold water line (getSCF, getCCF, getCCL, getCSS, getCSL).

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.
"""

from . import SyrConnectDeviceProfile
from .safethygienemodule import ALA_CODES, SELECT_CCL_OPTIONS

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve & Flow ---
    "getAB",
    "getVLV",
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
    # --- Leak Protection ---
    "getNPS",
    "getTMP",
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
}

VALVE_SUPPORTED_KEYS = {
    "getAB",
}

# Raw values written for "off": 0 days for the periodic flushing
SELECT_OFF_VALUES = {
    "getCCF": 0,
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
