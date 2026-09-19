"""Entity allowlist override for the muco_connectioncentre model (SYR AC 3200
Connect, dkv=506, getDFM=2, "Connection centre"/"Anschlusscenter" role).

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists in const.py which have to
cover every supported model at once.

No real-device or fixture capture exists for this variant yet - the keys
below are taken from the official validity matrix in
docs/syrconnect-protocol.md, which confirms getBAR2/getBAT/getBUZ/getCND/
getFLO/getSRN/getVER are available, plus the same baseline
connectivity/alarm/device-info/Wi-Fi keys shared by the other muco_*.py
device files. Verify against a real device before relying on this.

Deliberately NOT included, pending confirmation on a real device:
- getAVO, getBAR, getCEL, getLTV, getVOL, getVPS1, getVPS2: marked X (not
  available) for this model in the validity matrix.
- getCFT, getCFV: marked ✓ in the validity matrix, but their meaning is
  still undocumented (see the "Unknown" sections in
  docs/syrconnect-protocol.md) - left out until confirmed.
- Leak-protection-profile family (getPA-PW1-8, getPRF) and valve control
  (getAB/getVLV): this is a "Connection centre" role (getDFM=2 =
  "Anschlusscenter"/"Connection centre"), not a leak-protection variant.

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below.
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Flow ---
    "getFLO",
    # --- Alarm / Notification / Warning ---
    "getALA", "getALM", "getALN", "getALW", "getNOT", "getWRN",
    # --- Pressure ---
    "getBAR2",
    # --- Voltage / Battery ---
    "getBAT",
    # --- Water Quality ---
    "getCND",
    # --- Device Status ---
    "getDFM",
    # --- Device Info & Diagnostics ---
    "getEGW", "getEIP", "getLNG", "getMAC1", "getMAC2", "getSRN", "getVER",
    # --- Wi-Fi ---
    "getAPT", "getWFC", "getWFR", "getWFS", "getWGW", "getWIP",
    # --- Lock / Connection Centre ---
    "getLFT", "getLFV", "getNRT", "getTRT", "getTRV",
}

SELECT_KNOWN_KEYS: set[str] = set()

SWITCH_KNOWN_KEYS = {
    "getBUZ",
}

BUTTON_KNOWN_KEYS = {
    "setALA", "setNOT", "setWRN",
}

# No shutoff valve confirmed for this "Connection centre" role.
VALVE_KNOWN_KEYS: set[str] = set()
