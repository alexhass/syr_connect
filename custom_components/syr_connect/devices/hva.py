"""Entity allowlist override for the hva model (HVA, dk=20).

Model type: Filling the Heating System

Provisional: no fixture of this device exists yet. The allowlists hold the keys known
for the HVA that have an entity description, and must be checked against a capture of
a real device.

Deliberately NOT included:
- getRCP: on the HVA the remaining capacity in the format "<n> (<m>L)", not the
  settings synchronization interval of the sensor and select descriptions (see
  docs/syrconnect-protocol.md).
- getBAT: reported, but without a known meaning on the HVA.

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.
"""

from . import SyrConnectDeviceProfile

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve ---
    "getVLV",
    # --- Alarm / Notification / Warning ---
    "getALA",
    "getALM",
    "getNOT",
    "getWRN",
    # --- Pressure ---
    "getBAR",
    # --- Device Info & Diagnostics ---
    "getSRN",
    "getVER",
}

SELECT_SUPPORTED_KEYS: set[str] = set()

SWITCH_SUPPORTED_KEYS: set[str] = set()

BINARY_SENSOR_SUPPORTED_KEYS = {
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
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
