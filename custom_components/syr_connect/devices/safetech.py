"""Entity allowlist overrides shared by the SafeTech model family.

Derived from the SafeTech, SafeTech V3/V4, SafeTech+, and SafeTech+ Connect
JSON/XML fixtures. Keys are included when observed in at least one family
fixture and supported by the integration's global entity metadata; optional
keys only create entities when the device actually reports them.

The self-learning phase (getSLE) and its remaining time (getSLP) are included:
the SafeTech shows them in its status. The self-learning results
(getSLF/getSLT/getSLV) are omitted, no SafeTech fixture reports them. The
self-learning settings (getSLO/getSOF/getSMF) and the leakage warning threshold
(getLWT) are included: SYR's SafeTech command table lists them, and every fixture
reports their defaults (10 %, 20 %, 3500 l/h, 90 %).

The battery level (getBAP) is omitted: of the SafeTech family only the SafeTech+
with dk 1112 (dkv 112) reports it; the SafeTech reports the battery voltage
(getBAT) only.
"""

from . import SyrConnectDeviceProfile

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve, flow, and volume ---
    "getAB",
    "getAVO",
    "getFLO",
    "getLTV",
    "getVLV",
    "getVOL",
    # --- Alarm, notification, and warning ---
    "getALA",
    "getALD",
    "getALM",
    "getNOT",
    "getWRN",
    # --- Pressure, voltage, and battery ---
    "getBAR",
    "getBAT",
    "getNET",
    # --- Water quality ---
    "getCEL",
    "getCND",
    "getCND_class",
    "getCNF",
    "getCNL",
    # --- Microleakage test ---
    "getDBD",
    "getDBT",
    "getDCM",
    "getDMA",
    "getDOM",
    "getDPL",
    "getDRP",
    "getDST",
    "getDSV",
    "getDTC",
    "getDTT",
    "getNPS",
    "getTTM",
    # --- Leak protection and self-learning ---
    "getLWT",
    "getSLE",
    "getSLO",
    "getSLP",
    "getSMF",
    "getSOF",
    # --- Leak-protection profiles ---
    "getPA1",
    "getPA2",
    "getPA3",
    "getPA4",
    "getPA5",
    "getPA6",
    "getPA7",
    "getPA8",
    "getPB1",
    "getPB2",
    "getPB3",
    "getPB4",
    "getPB5",
    "getPB6",
    "getPB7",
    "getPB8",
    "getPF1",
    "getPF2",
    "getPF3",
    "getPF4",
    "getPF5",
    "getPF6",
    "getPF7",
    "getPF8",
    "getPM1",
    "getPM2",
    "getPM3",
    "getPM4",
    "getPM5",
    "getPM6",
    "getPM7",
    "getPM8",
    "getPN1",
    "getPN2",
    "getPN3",
    "getPN4",
    "getPN5",
    "getPN6",
    "getPN7",
    "getPN8",
    "getPR1",
    "getPR2",
    "getPR3",
    "getPR4",
    "getPR5",
    "getPR6",
    "getPR7",
    "getPR8",
    "getPRF",
    "getPRN",
    "getPT1",
    "getPT2",
    "getPT3",
    "getPT4",
    "getPT5",
    "getPT6",
    "getPT7",
    "getPT8",
    "getPV1",
    "getPV2",
    "getPV3",
    "getPV4",
    "getPV5",
    "getPV6",
    "getPV7",
    "getPV8",
    "getPW1",
    "getPW2",
    "getPW3",
    "getPW4",
    "getPW5",
    "getPW6",
    "getPW7",
    "getPW8",
    # --- Device information and diagnostics ---
    "getAPT",
    "getEGW",
    "getEIP",
    "getFFM",
    "getLNG",
    "getMAC",
    "getMAC1",
    "getMAC2",
    "getSRN",
    "getSRO",
    "getSRV",
    "getT2",
    "getTMP",
    "getTMZ",
    "getTYP",
    "getVER",
    # --- Wi-Fi ---
    "getWFC",
    "getWFR",
    "getWFS",
    "getWGW",
    "getWIP",
}

SELECT_SUPPORTED_KEYS = {
    "getPRF",
    "getSRO",
}

SWITCH_SUPPORTED_KEYS = {
    "getBPB",
    "getBUZ",
}

BINARY_SENSOR_SUPPORTED_KEYS = {
    "get71",
    "getBSA",
    "getBUZ",
    "getCSD",
    "getIDS",
    "getPSD",
    "getSFV",
    "getTSD",
    "getVTO",
}

BUTTON_SUPPORTED_KEYS = {
    "setALA",
    "setDEX",
    "setNOT",
    "setWRN",
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
