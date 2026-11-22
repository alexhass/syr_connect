"""Entity allowlist override for the Safe-T Hygiene module with two lines (dk=4).

Models: Safe-T Hygiene module (in-wall installation, dk=4/dkv=11), Safe-T Hygiene
module (dk=4/dkv=15).

Model type: Hygiene flushing with shut-off valve

Provisional: no fixture of this device exists yet. The allowlists hold the keys of the
Safe-T Hygiene module described in docs/syrconnect-protocol.md, and must be checked
against a capture of a real device.

The Safe-T Hygiene module has the five settings per line of the hygiene module
(hygienemodule.py), with other temperature ranges and without "off" for the
temperature limit, and no manual flushing. Like the Safe-T, it has a shut-off valve
(getVLV, setAB), reports the time without turbine pulses (getNPS) and can deactivate
the protection for a time (getTMP).

The alarm (getALA) has the alarm codes of the Safe-T and is reset with clrALA
(alarm_clear_via_set is not set).

Deliberately NOT included:
- getVOL: holds the number of flushings in the attributes tcf/twf, which the response
  parser does not read, and a current flow per line of an unknown unit.
- getCNO: code number of the device label; it registers the device to an account.

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.
"""

from . import SyrConnectDeviceProfile

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
    # --- Hygiene flushing (hot water line) ---
    "getCWF",
    "getSWF",
    "getWCL",
    "getWSL",
    "getWSS",
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
    "getCWF",
    "getSCF",
    "getSWF",
    "getWCL",
    "getWSL",
    "getWSS",
}

SWITCH_SUPPORTED_KEYS: set[str] = set()

BINARY_SENSOR_SUPPORTED_KEYS: set[str] = set()

BUTTON_SUPPORTED_KEYS = {
    "setALA",
}

VALVE_SUPPORTED_KEYS = {
    "getAB",
}


PROFILE = SyrConnectDeviceProfile(
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    sensor=SENSOR_SUPPORTED_KEYS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
