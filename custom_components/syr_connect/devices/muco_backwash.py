"""Entity allowlist override for the muco_backwash model (SYR RSA Connect,
dkv=506, getDFM=4, automatic-backwash "Rückspülautomatik" role).

Model type: Automatic Backwash System

This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists in const.py which have to
cover every supported model at once.

No real-device or fixture capture exists for this variant yet - the keys
below are taken from the official command table and validity matrix in
docs/syrconnect-protocol.md, which confirm getBAT/getBUZ/getSRN/getVER plus
the automatic-backwash feature (getCOA/getCOM/getRSA/getRSD/getRSE/getSSA/
getSSE), and the same baseline connectivity/alarm/device-info/Wi-Fi keys
shared by the other muco_*.py device files. Verify against a real device
before relying on this.

Deliberately NOT included, pending confirmation on a real device:
- Leak-protection-profile family (getPA-PW1-8, getPRF), water treatment /
  filling family (getCRS/getCRT/getRCD/getRMN/etc.), and valve control
  (getAB/getVLV): none of these are part of the automatic-backwash feature
  set and belong to the other muco_leakprotect/muco_filling variants instead.

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below.
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Alarm / Notification / Warning ---
    "getALA", "getALM", "getALN", "getALW", "getNOT", "getWRN",
    # --- Device Status ---
    "getDFM",
    # --- Voltage / Battery ---
    "getBAT",
    # --- Automatic Backwash (RSA) ---
    "getCOA", "getCOM", "getRSA", "getRSD", "getRSE",
    # --- Device Info & Diagnostics ---
    "getEGW", "getEIP", "getLNG", "getMAC1", "getMAC2", "getSRN", "getVER",
    # --- Wi-Fi ---
    "getAPT", "getWFC", "getWFR", "getWFS", "getWGW", "getWIP",
}

# getRSA/getRSD/getRSE deliberately excluded from SELECT_KNOWN_KEYS: their
# value ranges (1-365 days, 1-100 s) are too large for a usable select
# dropdown, same reasoning as getIWH/getMPR/getDWF in const.py.
SELECT_KNOWN_KEYS: set[str] = set()

SWITCH_KNOWN_KEYS = {
    "getBUZ", "getSSA", "getSSE",
}

BUTTON_KNOWN_KEYS = {
    "setALA", "setNOT", "setWRN",
}

# No shutoff valve on this model - it only automates backwash scheduling.
VALVE_KNOWN_KEYS: set[str] = set()
