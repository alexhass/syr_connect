"""Entity allowlist override for the hygbox model (HygBox, dk=180/dkv=37).

Model type: Hygiene flushing

Provisional: no fixture of this device exists yet. The allowlists hold the keys of the
HygBox described in docs/syrconnect-protocol.md, and must be checked against a capture
of a real device.

The HygBox flushes the water pipe in three ways, each with its own settings:
- Stagnation flushing (getFD1): after the stagnation time (getSTP) without water use,
  with the flushing volume getSTV.
- Temperature flushing (getFD2): when the water temperature leaves the range of the
  water type (getWTY), between the start and the stop temperature (getTTT, getF2W), at
  most getF2T seconds and getMTF times per day.
- Periodic flushing (getFD3): every getF3P minutes, with the flushing volume getF3V.
getFD1-3 report the function as disabled, so their switches are inverted.

Deliberately NOT included:
- getMQT: reported, but without a known meaning (probably an MQTT flag).

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
    # --- Pressure ---
    "getBAR",
    # --- Voltage / Battery ---
    "getBAP",
    # --- Water Quality ---
    "getCEL",
    # --- Hygiene flushing ---
    "getF2T",
    "getF2W",
    "getF3P",
    "getF3V",
    "getMTF",
    "getSTP",
    "getSTV",
    "getTTT",
    "getWTY",
    # --- Intervals ---
    "getRCP",
    # --- Device Info & Diagnostics ---
    "getMAC",
    "getSRN",
    "getVER",
    # --- Wi-Fi ---
    "getWFC",
    "getWGW",
    "getWIP",
    # "getMQT",  # Unknown meaning, probably an MQTT flag
}

SELECT_SUPPORTED_KEYS = {
    "getF2T",
    "getF2W",
    "getF3P",
    "getF3V",
    "getMTF",
    "getRCP",
    "getSTP",
    "getSTV",
    "getTTT",
    "getWTY",
}

SWITCH_SUPPORTED_KEYS = {
    "getBUZ",
    "getFD1",
    "getFD2",
    "getFD3",
}

BINARY_SENSOR_SUPPORTED_KEYS = {
    "getBUZ",
}

BUTTON_SUPPORTED_KEYS: set[str] = set()

VALVE_SUPPORTED_KEYS: set[str] = set()

# Synchronization interval (getRCP) in seconds: 6 hours to 8 days, the steps of the
# global option map within this range
SELECT_RCP_OPTIONS = [
    21600,
    43200,
    86400,
    172800,
    259200,
    345600,
    432000,
    518400,
    604800,
    691200,
]


PROFILE = SyrConnectDeviceProfile(
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    select_options={
        "getRCP": SELECT_RCP_OPTIONS,
    },
    sensor=SENSOR_SUPPORTED_KEYS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
