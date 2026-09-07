"""Entity allowlist override for the safetplus model (Safe-T+ Connect, dk=1/dkv=6).

Derived from tests/fixtures/xml/SafeTPlus_GetDeviceCollectionStatus.xml (this
model has no JSON API fixture - it is only reachable via the XML API).
This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists in const.py which have to
cover every supported model at once.

Unlike the LEXplus10SL / SafeTech(+) leak-protection variants, this model has
only a SINGLE leak-protection profile (no getPA1-8/getPRF numbered-profile
family) - it uses the plain getLE/getT1/getT2/getUL/getTMP keys instead.
It also has no Wi-Fi module (no getWFC/getWFR/getWFS/getEGW/getEIP/getMAC1/
getMAC2/getAPT in the fixture) and no getFLO/getNOT/getWRN/getDSV/getDTT.

Deliberately NOT included, pending confirmation on a real device:
- getDST, getDTC, getDBT, getDCM, getDOM, getDPL: present in the fixture but
  not in the global const.py allowlist at all (undocumented/unclear keys).
- getBSA, getBSI, getBLT, getUNI, getTC, getTO, getTPA, getTBS, getREL,
  getEXI, getEXT, getFLL, getINT, get71: same as above - not in the global
  allowlist, meaning not confirmed for use across the integration.

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_KNOWN_KEYS below (after adding them to the
global const.py allowlist first).
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve & Flow ---
    "getAB", "getAVO", "getVLV",
    # --- Alarm / Notification / Warning ---
    "getALA", "getALM",
    # --- Pressure ---
    "getBAR",
    # --- Voltage / Battery ---
    "getBAT", "getNET",
    # --- Water Quality ---
    "getCEL",
    # --- Water Consumption & Volume ---
    "getVOL",
    # --- Microleakage Test ---
    "getDBD", "getDRP", "getNPS",
    # --- Leak Protection (single profile only, no numbered profile family) ---
    "getLE", "getT1", "getT2", "getTMP", "getUL",
    # --- Device Info & Diagnostics ---
    "getCNO", "getLNG", "getSRN", "getTYP", "getVER",
}

# No select-worthy keys present for this model (no display rotation, no
# regeneration/filling/salt configuration, no numbered leak-protection profiles).
SELECT_KNOWN_KEYS: set[str] = set()

SWITCH_KNOWN_KEYS = {
    "getBUZ",
}

# setSIR (regeneration) and setDEX (microleakage test, no getDSV present)
# deliberately excluded. setNOT/setWRN excluded - no getNOT/getWRN in the
# fixture for this model.
BUTTON_KNOWN_KEYS = {
    "setALA",
}

# getAB (valve shutoff control) kept - this model genuinely controls a valve.
VALVE_KNOWN_KEYS = {
    "getAB",
}
