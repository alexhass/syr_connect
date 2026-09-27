"""Entity allowlists for SafeTech+ (dkv=39 and dkv=112).

Based on the SafeTech+ JSON and XML fixtures and checked against the
Per-model validity matrix. The matrix marks BAR unavailable for SafeTech+,
so getBAR is intentionally absent here even though it appears in the captures.
The base SafeTech family keeps its separate devices/safetech.py allowlist.
"""

SENSOR_KNOWN_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Valve, flow, and volume ---
    "getAB", "getAVO", "getFLO", "getLTV", "getVLV", "getVOL",
    # --- Alarm, notification, and warning ---
    "getALA", "getALD", "getALM", "getNOT", "getWRN",
    # --- Pressure, voltage, and battery ---
    "getBAP", "getBAR2", "getBAT", "getNET",
    # --- Water quality ---
    "getCEL", "getCND",
    # --- Microleakage test ---
    "getDBD", "getDMA", "getDRP", "getDSV", "getDTT", "getNPS",
    # --- Leak-protection profiles ---
    "getPA1", "getPA2", "getPA3", "getPA4", "getPA5", "getPA6", "getPA7", "getPA8",
    "getPB1", "getPB2", "getPB3", "getPB4", "getPB5", "getPB6", "getPB7", "getPB8",
    "getPF1", "getPF2", "getPF3", "getPF4", "getPF5", "getPF6", "getPF7", "getPF8",
    "getPM1", "getPM2", "getPM3", "getPM4", "getPM5", "getPM6", "getPM7", "getPM8",
    "getPN1", "getPN2", "getPN3", "getPN4", "getPN5", "getPN6", "getPN7", "getPN8",
    "getPR1", "getPR2", "getPR3", "getPR4", "getPR5", "getPR6", "getPR7", "getPR8",
    "getPRF",
    "getPT1", "getPT2", "getPT3", "getPT4", "getPT5", "getPT6", "getPT7", "getPT8",
    "getPV1", "getPV2", "getPV3", "getPV4", "getPV5", "getPV6", "getPV7", "getPV8",
    "getPW1", "getPW2", "getPW3", "getPW4", "getPW5", "getPW6", "getPW7", "getPW8",
    # --- Device information and diagnostics ---
    "getAPT", "getCNO", "getEGW", "getEIP", "getFFM", "getLNG",
    "getMAC", "getMAC1", "getMAC2", "getSRN", "getSRO", "getSRV", "getT2",
    "getTMP", "getTYP", "getVER",
    # --- Wi-Fi ---
    "getWFC", "getWFL", "getWFR", "getWFS", "getWGW", "getWIP",
}

SELECT_KNOWN_KEYS = {
    "getFFM", "getPRF", "getSRO",
}

SWITCH_KNOWN_KEYS = {
    "getBUZ",
}

BINARY_SENSOR_KNOWN_KEYS = {
    "getBUZ",
}

BUTTON_KNOWN_KEYS = {
    "setALA", "setDEX", "setNOT", "setWRN",
}

VALVE_KNOWN_KEYS = {
    "getAB",
}
