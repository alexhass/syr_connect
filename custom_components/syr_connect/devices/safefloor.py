"""Entity allowlist override for the safefloor model (SafeFloor Connect, dk=120/dkv=34).

Derived from tests/fixtures/xml/SyrSafeFloor_GetDeviceCollectionStatus.xml (this
model has no JSON API fixture - it is only reachable via the XML API).
This is a POSITIVE list: only keys confirmed to be meaningful for this model
are listed, unlike the shared global allowlists of the platforms which have to
cover every supported model at once.

Unlike every other device file so far, this model IS the genuine home of the
"(SafeFloor)"-tagged sensor.py keys (getALD, getHMD, getMIH, getMXH, getMIT,
getMXT) that muco_leakprotect/muco_filling excluded as "a different product" - it is a
standalone humidity/temperature/leak sensor with no valve, no flow, no
buzzer, and no leak-protection-profile family.

Deliberately NOT included:
- getALI, getAOA, getBDE, getBMP, getDEF, getECP, getEMR, getISN, getRTC,
  getSFV, getWAR, getWTD: present in the fixture but not in the global
  sensor.py allowlist at all (undocumented/unclear keys).

If real-device testing shows any of the above (or other) keys are actually
used, move them into SENSOR_SUPPORTED_KEYS below (after adding them to the
global sensor.py allowlist first).
"""

from . import SyrConnectDeviceProfile, SyrConnectStatistic

SENSOR_SUPPORTED_KEYS = {
    # --- Connectivity ---
    "dst",
    # --- Alarm ---
    "getALA",
    "getALD",
    # --- Voltage / Battery ---
    "getBAT",
    # --- Water Quality / Ambient ---
    "getCEL",
    "getHMD",
    # --- Alarm Thresholds (SafeFloor) ---
    "getMIH",
    "getMXH",
    "getMIT",
    "getMXT",
    # --- Intervals ---
    "getRCP",
    "getWMP",
    # --- Device Info & Diagnostics ---
    "getMAC",
    "getSRN",
    "getTYP",
    "getVER",
    # --- Wi-Fi ---
    "getAPT",
    "getWFC",
    "getWFR",
    "getWFS",
    "getWGW",
    "getWIP",
}

# No display rotation, no regeneration/filling/salt configuration, no
# leak-protection profiles - but the alarm/humidity/temperature thresholds and
# sync/measurement intervals are user-adjustable settings on this model.
SELECT_SUPPORTED_KEYS = {
    "getALD",
    "getMIH",
    "getMXH",
    "getMIT",
    "getMXT",
    "getRCP",
    "getWMP",
}

# No buzzer/switch on this model.
SWITCH_SUPPORTED_KEYS: set[str] = set()
BINARY_SENSOR_SUPPORTED_KEYS = {
    "getSFV",
}

# setSIR (regeneration) and setDEX (microleakage test) excluded - not applicable
# to a standalone sensor. setNOT/setWRN excluded - no getNOT/getWRN in the
# fixture for this model.
BUTTON_SUPPORTED_KEYS = {
    "setALA",
}

# No shutoff valve on this model (a standalone sensor, not a valve controller).
VALVE_SUPPORTED_KEYS: set[str] = set()

# Alarm codes for SafeFloor devices (raw API getALA -> internal translation key)
# Original casing in API is "A0x0000", but we normalize it for get_sensor_ala_map() lookups.
# Codes are hexadecimal bitmask values (0x0002, 0x0004, ..., 0x0100).
ALA_CODES = {
    "A0X0000": "no_alarm",
    "A0X0002": "alarm_safefloor_communication",
    "A0X0004": "alarm_safefloor_flood",
    "A0X0008": "alarm_safefloor_weather",
    "A0X0010": "alarm_safefloor_low_temperature",
    "A0X0020": "alarm_safefloor_high_temperature",
    "A0X0040": "alarm_safefloor_low_humidity",
    "A0X0080": "alarm_safefloor_high_humidity",
    "A0X0100": "alarm_battery_weak",
}

# The sensor measures every getWMP seconds but uploads only every getRCP seconds, so
# the status holds only the latest measurement. The cloud keeps the raw measurements
# of the last 6 days (see "SafeFloor measurement history" in docs/syrconnect-protocol.md).
STATISTICS = (
    SyrConnectStatistic(
        key="getCEL",
        method="GetSafeFloorStatistics",
        rtyp=4,
        t=1,
        unit="°C",
    ),
    SyrConnectStatistic(
        key="getHMD",
        method="GetSafeFloorStatistics",
        rtyp=4,
        t=2,
        unit="%",
    ),
)


PROFILE = SyrConnectDeviceProfile(
    ala_codes=ALA_CODES,
    binary_sensor=BINARY_SENSOR_SUPPORTED_KEYS,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    sensor=SENSOR_SUPPORTED_KEYS,
    statistics=STATISTICS,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
