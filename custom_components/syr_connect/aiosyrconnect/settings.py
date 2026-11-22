"""Allowed values of the settings of the SYR devices.

A device takes only certain raw values for a setting, documented in
docs/syrconnect-protocol.md. `SETTING_VALUES` lists them per status key in ascending
order, and `SETTING_OFF_VALUES` the raw value that switches a setting off. A model whose
values differ names them in its signature (`setting_values`, `setting_off_values`,
`hardness_ranges`); `SyrConnectModelSignature.allowed_values()` and `off_value()` give
the values of a model. The limits that depend on the model alone (`maximum_salt_volume`,
`maximum_regeneration_interval`) are fields of the signature.
"""

from collections.abc import Mapping, Sequence

# Flushing volume of the stagnation and the periodic flushing (getSTV, getF3V, HygBox) and
# the flushing volume after which a hygiene module stops (getCSL, getWSL) in liters: 1-100
# in steps of 1
_FLUSHING_VOLUMES = range(1, 101)

# Periodic flushing of a hygiene module line (getCCF, getCWF) in days: 1-30 in steps of 1;
# "off" (0) comes from the signature
_HYGIENE_PERIODIC_DAYS = range(1, 31)

# Stagnation flushing of a hygiene module line (getSCF, getSWF) in days: 1-7 in steps of 1
_HYGIENE_STAGNATION_DAYS = range(1, 8)

# Flushing time after which a hygiene module line stops (getCSS, getWSS): raw 1-99 in steps
# of 1, in 10 s (10-990 s)
_HYGIENE_STOP_TIMES = range(1, 100)

# Maximum filling charges (getRVT) and maximum volume of the initial filling (getFVT) in
# liters: 0=off, 10-100 in steps of 10, 100-1000 in steps of 50, 1000-9900 in steps of 100
_FILLING_VOLUMES = sorted(
    {
        0,
        *range(10, 101, 10),
        *range(100, 1001, 50),
        *range(1000, 9901, 100),
    }
)

# Raw values of the settings: status key -> allowed raw values in ascending order. The
# values of a model can differ (`setting_values` of the signature).
SETTING_VALUES: Mapping[str, Sequence[int]] = {
    # Alarm duration (getALD) in seconds, the documented GUI step list: 1, 5, 10, 20, 30,
    # then 1-10 minutes (60-600) in steps of 60
    "getALD": [
        1,
        5,
        10,
        20,
        30,
        *range(60, 601, 60),
    ],
    "getCCF": _HYGIENE_PERIODIC_DAYS,
    # Cartridge type (getCRT): 0=HWE, 1=HVE, 2=HVE+ (empty value = no cartridge installed)
    "getCRT": [
        0,
        1,
        2,
    ],
    "getCSL": _FLUSHING_VOLUMES,
    "getCSS": _HYGIENE_STOP_TIMES,
    # Remaining capacity warning threshold (getCWL) in %: 1-10 in steps of 1
    "getCWL": range(1, 11),
    "getCWF": _HYGIENE_PERIODIC_DAYS,
    # Operating mode of the dosing pump (getDMO): 0=automatic, 1=running-in,
    # 2=disinfection, 3=low
    "getDMO": [
        0,
        1,
        2,
        3,
    ],
    # Dosing liquid of the dosing pump (getDSL): 1 and 2 (0 = not set is not selectable)
    "getDSL": [
        1,
        2,
    ],
    # Maximum flushing duration of the temperature flushing (getF2T, HygBox) in seconds:
    # 30-600 in steps of 30
    "getF2T": range(30, 601, 30),
    # Interval of the periodic flushing (getF3P, HygBox) in minutes: 1-23 hours in steps of
    # 1 hour, then 1-12 days in steps of 1 day
    "getF3P": sorted(
        {
            *range(60, 1381, 60),
            *range(1440, 17281, 1440),
        }
    ),
    "getF3V": _FLUSHING_VOLUMES,
    # Custom cartridge size (getFCS, All-in-One+) in liters: 1-100 in steps of 1
    "getFCS": range(1, 101),
    # Maximum duration of the initial filling (getFMT, All-in-One+) in minutes: 5-20 in
    # steps of 5, 30-50 in steps of 10, 60-1500 in steps of 30
    "getFMT": sorted(
        {
            *range(5, 21, 5),
            *range(30, 51, 10),
            *range(60, 1501, 30),
        }
    ),
    "getFVT": _FILLING_VOLUMES,
    # Raw water hardness (getIWH): 1-100 in steps of 1, in the unit of getWHU
    "getIWH": range(1, 101),
    # Maximum output conductivity (getLOT, HVE/HVE+ cartridge): raw 0-20, in 10 µS/cm
    # (0-200 µS/cm, 0 = off)
    "getLOT": range(21),
    # Minimum humidity threshold (getMIH): 0-95 % in steps of 5. The lower boundary 0
    # doubles as "Off" (per docs/syrconnect-protocol.md), so it has no off value.
    "getMIH": range(0, 96, 5),
    # Minimum temperature threshold (getMIT): raw 1/10 °C, -30 to 50 °C in steps of 1 °C,
    # below the maximum temperature unless that is off (`SETTING_UPPER_LIMITS`); off is a
    # value of its own (`SETTING_OFF_VALUES`)
    "getMIT": range(-300, 501, 10),
    # Flushings per day of the temperature flushing (getMTF, HygBox): 1-50
    "getMTF": range(1, 51),
    # Maximum humidity threshold (getMXH): 5-100 % in steps of 5. The upper boundary 100
    # doubles as "Off" (per docs/syrconnect-protocol.md), so it has no off value.
    "getMXH": range(5, 101, 5),
    # Maximum temperature threshold (getMXT): raw 1/10 °C, 1-50 °C in steps of 1 °C; off
    # is a value of its own (`SETTING_OFF_VALUES`)
    "getMXT": range(10, 501, 10),
    # Soft water hardness (getOWH): 0-100 in steps of 1, in the unit of getWHU
    "getOWH": range(101),
    # Filling processes period (getRCD): 0=hour, 1=day, 2=week, 3=month (empty value =
    # undefined)
    "getRCD": [
        0,
        1,
        2,
        3,
    ],
    # Settings synchronization interval (getRCP) in seconds: non-uniform duration steps as
    # documented in docs/syrconnect-protocol.md
    "getRCP": [
        3600,
        7200,
        10800,
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
        777600,
        864000,
        950400,
        1036800,
        1123200,
        1209600,
    ],
    # Filling processes count (getRMN): 1-10
    "getRMN": range(1, 11),
    # Regeneration mode (getRMO): 1=Standard, 2=ECO, 3=Power, 4=Automatic
    "getRMO": [
        1,
        2,
        3,
        4,
    ],
    # Maximum filling duration (getRMT) in minutes: 1-5 (step 1), 10, 15-60 (step 15),
    # 60-720 (step 30)
    "getRMT": sorted(
        {
            *range(1, 6),
            10,
            *range(15, 61, 15),
            *range(60, 721, 30),
        }
    ),
    "getRVT": _FILLING_VOLUMES,
    "getSCF": _HYGIENE_STAGNATION_DAYS,
    # Stagnation time of the stagnation flushing (getSTP, HygBox) in minutes: 1-23 hours in
    # steps of 1 hour, then 1-30 days in steps of 1 day
    "getSTP": sorted(
        {
            *range(60, 1381, 60),
            *range(1440, 43201, 1440),
        }
    ),
    "getSTV": _FLUSHING_VOLUMES,
    "getSWF": _HYGIENE_STAGNATION_DAYS,
    # Target pressure (getTPR): raw 1/10 bar, 0.5-5.0 bar in steps of 0.1 bar
    "getTPR": range(5, 51),
    # Measurement interval (getWMP) in seconds: non-uniform duration steps as documented
    # in docs/syrconnect-protocol.md; at most the synchronization interval (getRCP, see
    # `SETTING_UPPER_LIMITS`)
    "getWMP": [
        60,
        600,
        900,
        1800,
        3600,
        7200,
        10800,
        21600,
        32400,
        43200,
        57600,
        72000,
        86400,
    ],
    "getWSL": _FLUSHING_VOLUMES,
    "getWSS": _HYGIENE_STOP_TIMES,
    # Water type of the HygBox (getWTY): 1=cold water, 2=hot water (0 = undefined is not
    # selectable)
    "getWTY": [
        1,
        2,
    ],
}

# Raw values that switch a setting off, outside of its range: status key -> raw value.
# The values of a model can differ (`setting_off_values` of the signature).
SETTING_OFF_VALUES: Mapping[str, int] = {
    # Minimum temperature threshold (getMIT): below the range
    "getMIT": -400,
    # Maximum temperature threshold (getMXT): above the range
    "getMXT": 700,
}

# Settings that are limited by another setting of the device: key -> (key of the upper
# limit, smallest distance to it). The minimum humidity (getMIH) stays below the maximum
# humidity (getMXH), the minimum temperature (getMIT) below the maximum temperature
# (getMXT), and the measurement interval (getWMP) at most the synchronization interval
# (getRCP). The upper key is in turn limited by the lower one. A limit that is switched
# off (`SETTING_OFF_VALUES`) limits nothing.
SETTING_UPPER_LIMITS: Mapping[str, tuple[str, int]] = {
    "getMIH": ("getMXH", 5),
    "getMIT": ("getMXT", 10),
    "getWMP": ("getRCP", 0),
}

# Smallest distance between the start and the stop temperature of the temperature
# flushing (getTTT, getF2W, HygBox) in °C
FLUSHING_TEMPERATURE_GAP = 2

# Range of the start and the stop temperature of the temperature flushing (getTTT,
# getF2W, HygBox) in °C per water type (getWTY): 1=cold water, 2=hot water
FLUSHING_TEMPERATURE_RANGES: Mapping[int, tuple[int, int]] = {
    1: (10, 25),
    2: (50, 60),
}
