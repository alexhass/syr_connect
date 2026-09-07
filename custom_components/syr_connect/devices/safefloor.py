"""Entity allowlist override for the safefloor model (SafeFloor Connect, dk=120/dkv=34).

Derived from tests/fixtures/xml/SafeFloor_GetDeviceCollectionStatus.xml (this
model has no JSON API fixture - it is only reachable via the XML API).
This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists in const.py which have to
cover every supported model at once.

Unlike every other device file so far, this model IS the genuine home of the
"(SafeFloor)"-tagged const.py keys (getALD, getHMD, getMIH, getMXH, getMIT,
getMXT) that muco_dfm1/muco_dfm3 excluded as "a different product" - it is a
standalone humidity/temperature/leak sensor with no valve, no flow, no
buzzer, and no leak-protection-profile family.

Deliberately NOT included:
- getALI, getAOA, getBDE, getBMP, getDEF, getECP, getEMR, getISN, getRTC,
  getSFV, getWAR, getWTD: present in the fixture but not in the global
  const.py allowlist at all (undocumented/unclear keys).

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below (after adding them to the
global const.py allowlist first).
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Alarm ---
    "getALA", "getALD",
    # --- Voltage / Battery ---
    "getBAT",
    # --- Water Quality / Ambient ---
    "getCEL", "getHMD",
    # --- Alarm Thresholds (SafeFloor) ---
    "getMIH", "getMXH", "getMIT", "getMXT",
    # --- Intervals ---
    "getRCP", "getWMP",
    # --- Device Info & Diagnostics ---
    "getCNO", "getMAC", "getSRN", "getTYP", "getVER",
    # --- Wi-Fi ---
    "getAPT", "getWFC", "getWFR", "getWFS", "getWGW", "getWIP",
}

# No select-worthy keys for this model (no display rotation, no
# regeneration/filling/salt configuration, no leak-protection profiles).
SELECT_KNOWN_KEYS: set[str] = set()

# No buzzer/switch on this model.
SWITCH_KNOWN_KEYS: set[str] = set()

# setSIR (regeneration) and setDEX (microleakage test) excluded - not applicable
# to a standalone sensor. setNOT/setWRN excluded - no getNOT/getWRN in the
# fixture for this model.
BUTTON_KNOWN_KEYS = {
    "setALA",
}

# No shutoff valve on this model (a standalone sensor, not a valve controller).
VALVE_KNOWN_KEYS: set[str] = set()
