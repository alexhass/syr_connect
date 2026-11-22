"""Entity allowlist override for the dosingpump model (Dosing Pump, dk=190/dkv=44).

Model type: Dosing

Provisional: no fixture of this device exists yet. The allowlists hold the keys of the
dosing pump described in docs/syrconnect-protocol.md, and must be checked against a
capture of a real device.

The alarm (getALA) is reset with clrALA (alarm_clear_via_set is not set). The dosing
pump reports no warnings (getWRN) and no notifications (getNOT).

Deliberately NOT included:
- getRMT, getRMR: reported, but without a known meaning. getRMT can also be set
  (setRMT); on the MuCo and the All-in-One+ it is the maximum filling duration, so its
  sensor and select description would show a wrong value here.

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
    # --- Alarm ---
    "getALA",
    # --- Dosing ---
    "getCAS",
    "getDAM",
    "getDMO",
    "getDSL",
    # "getRMR",  # Unknown meaning
    # "getRMT",  # Unknown meaning, not the maximum filling duration of the MuCo
    # --- Device Info & Diagnostics ---
    "getMAC",
    "getSRN",
    "getVER",
    # --- Wi-Fi ---
    "getMQT",
    "getWFC",
    "getWGW",
    "getWIP",
}

SELECT_SUPPORTED_KEYS = {
    "getCAS",
    "getDMO",
    "getDSL",
    # "getRMT",  # Can be set (setRMT), but the meaning is unknown
}

SWITCH_SUPPORTED_KEYS: set[str] = set()

BINARY_SENSOR_SUPPORTED_KEYS: set[str] = set()

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
