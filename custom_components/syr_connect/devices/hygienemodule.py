"""Entity allowlist override for the hygiene module with two lines (dk=62/63).

Models: Hygiene Module (hot and cold, dk=62/dkv=23), Hygiene Module (cold and hot,
dk=63/dkv=24).

Model type: Hygiene flushing

Provisional: no fixture of this device exists yet. The allowlists hold the keys of the
hygiene module described in docs/syrconnect-protocol.md, and must be checked against a
capture of a real device.

The hygiene module flushes a cold and a hot water line. Each line has five settings;
the keys of the cold line have a "C", the keys of the hot line a "W":
- Stagnation flushing (getSCF, getSWF): flushes after 1-7 days without water use.
- Periodic flushing (getCCF, getCWF): flushes every 1-30 days, 0 = off.
- Temperature limit (getCCL, getWCL): maximum temperature of the cold line, minimum
  temperature of the hot line; a value below the range = off.
- Flushing stop after a time (getCSS, getWSS) and after a volume (getCSL, getWSL).
setMFC and setMFW start a manual flushing of the line.

The alarm (getALA) is reset with clrALA (alarm_clear_via_set is not set).

Deliberately NOT included:
- getVOL: holds the number of flushings in the attributes tcf/twf, which the response
  parser does not read.
- getCNO: code number of the device label; it registers the device to an account.

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.
"""

from . import SyrConnectDeviceProfile

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
    "setMFC",
    "setMFW",
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
