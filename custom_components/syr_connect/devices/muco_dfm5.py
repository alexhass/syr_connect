"""Entity allowlist override for the muco_dfm5 model (SYR TRIO Lock Connect, dkv=506, getDFM=5).

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists in const.py which have to
cover every supported model at once.

No real-device or fixture capture exists for this variant yet - the keys
below are taken from the official validity matrix in
docs/syrconnect-protocol.md, which confirms getAVO/getBAR2/getBAT/getBUZ/
getFLO/getLTV/getNMS/getNMT/getNPS/getNPT/getSRN/getVER/getVOL are available,
plus the same baseline connectivity/alarm/device-info/Wi-Fi keys shared by
the other muco_dfm*.py device files. Verify against a real device before
relying on this.

Deliberately NOT included, pending confirmation on a real device:
- getBAR, getCEL, getCND, getVPS1, getVPS2: marked X (not available) for
  this model in the validity matrix.
- Leak-protection-profile family (getPA-PW1-8, getPRF) and valve control
  (getAB/getVLV): not covered by the validity matrix - unconfirmed whether
  this "Lock Connect" role controls a shutoff valve like the leak-protection
  variants (muco_dfm1).

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below.
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Flow ---
    "getAVO", "getFLO",
    # --- Alarm / Notification / Warning ---
    "getALA", "getALM", "getALN", "getALW", "getNOT", "getWRN",
    # --- Pressure ---
    "getBAR2",
    # --- Voltage / Battery ---
    "getBAT",
    # --- Water Consumption & Volume ---
    "getLTV", "getVOL",
    # --- Leak Protection ---
    "getNPS",
    # --- Lock / Connection Centre ---
    "getNMS", "getNMT", "getNPT",
    # --- Device Status ---
    "getDFM",
    # --- Device Info & Diagnostics ---
    "getEGW", "getEIP", "getLNG", "getMAC1", "getMAC2", "getSRN", "getVER",
    # --- Wi-Fi ---
    "getAPT", "getWFC", "getWFR", "getWFS", "getWGW", "getWIP",
}

SELECT_KNOWN_KEYS: set[str] = set()

SWITCH_KNOWN_KEYS = {
    "getBUZ",
}

BUTTON_KNOWN_KEYS = {
    "setALA", "setNOT", "setWRN",
}

# Valve control (getAB/getVLV) not confirmed by the validity matrix for this role.
VALVE_KNOWN_KEYS: set[str] = set()
