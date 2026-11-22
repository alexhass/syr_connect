"""Constants for the SYR Connect integration."""

DOMAIN = "syr_connect"

# Configuration keys
CONF_API_TYPE = "api_type"
CONF_HOST = "host"
CONF_MODEL = "model"
CONF_LOGIN_REQUIRED = "login_required"
CONF_SERVICE = "service"

# API type values
API_TYPE_XML = "xml"
API_TYPE_JSON = "json"

# Service of the SYR Connect app itself: preselected for a new account, and the service
# of the entries made before the service could be chosen
_SYR_CONNECT_SERVICE_DEFAULT = "de.consoft.syr.connect"

_SYR_CONNECT_SCAN_INTERVAL_CONF = "scan_interval"
_SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT = 60  # seconds
_SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT = 60  # seconds
_SYR_CONNECT_API_XML_SCAN_INTERVAL_MINIMUM = 60  # seconds
_SYR_CONNECT_API_JSON_SCAN_INTERVAL_MINIMUM = 10  # seconds
_SYR_CONNECT_API_SCAN_INTERVAL_MAXIMUM = 600  # seconds


# Numbers of the leak protection profiles. Every profile has the same settings, keyed
# by the setting with the number appended: getPA1-getPA8, getPN1-getPN8, ...
_SYR_CONNECT_LEAK_PROTECTION_PROFILES = range(1, 9)

# Select options, sorted by name:
# - `*_MAP`: option maps of the discrete selects: option key (translated by the frontend,
#   or a label with unit) -> raw device value. None marks the option for an empty raw value.
# - `*_OPTIONS`: step lists of the numeric selects with non-uniform steps: raw values in
#   ascending order, shown with the key's unit (see docs/syrconnect-protocol.md).

# Alarm duration (getALD) in seconds, the documented GUI step list: 1, 5, 10, 20, 30,
# then 1-10 minutes (60-600) in steps of 60
_SYR_CONNECT_SELECT_ALD_OPTIONS = [
    1,
    5,
    10,
    20,
    30,
    *range(60, 601, 60),
]

# Cartridge type (getCRT): 0=HWE, 1=HVE, 2=HVE+ (empty value = no cartridge installed)
_SYR_CONNECT_SELECT_CRT_MAP = {
    "none": None,
    "0": 0,
    "1": 1,
    "2": 2,
}

# Operating mode of the dosing pump (getDMO): 0=automatic, 1=running-in, 2=disinfection,
# 3=low
_SYR_CONNECT_SELECT_DMO_MAP = {
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
}

# Dosing liquid of the dosing pump (getDSL): 1 and 2 (0 = not set is not selectable)
_SYR_CONNECT_SELECT_DSL_MAP = {
    "1": 1,
    "2": 2,
}

# Maximum flushing duration of the temperature flushing (getF2T, HygBox) in seconds: 30-600
# in steps of 30
_SYR_CONNECT_SELECT_F2T_OPTIONS = list(range(30, 601, 30))

# Interval of the periodic flushing (getF3P, HygBox) in minutes: 1-23 hours in steps of
# 1 hour, then 1-12 days in steps of 1 day
_SYR_CONNECT_SELECT_F3P_OPTIONS = sorted(
    {
        *range(60, 1381, 60),
        *range(1440, 17281, 1440),
    }
)

# Smallest distance between the start and the stop temperature of the temperature
# flushing (getTTT, getF2W, HygBox) in °C
_SYR_CONNECT_SELECT_FLUSHING_TEMPERATURE_GAP = 2

# Range of the start and the stop temperature of the temperature flushing (getTTT,
# getF2W, HygBox) in °C per water type (getWTY): 1=cold water, 2=hot water
_SYR_CONNECT_SELECT_FLUSHING_TEMPERATURE_RANGES = {
    1: (10, 25),
    2: (50, 60),
}

# Flushing volume of the stagnation and the periodic flushing (getSTV, getF3V, HygBox) and
# the flushing volume after which a hygiene module stops (getCSL, getWSL) in liters: 1-100
# in steps of 1
_SYR_CONNECT_SELECT_FLUSHING_VOLUME_OPTIONS = list(range(1, 101))

# Maximum duration of the initial filling (getFMT, All-in-One+) in minutes: 5-20 in steps
# of 5, 30-50 in steps of 10, 60-1500 in steps of 30
_SYR_CONNECT_SELECT_FMT_OPTIONS = sorted(
    {
        *range(5, 21, 5),
        *range(30, 51, 10),
        *range(60, 1501, 30),
    }
)

# Periodic flushing of a hygiene module line (getCCF, getCWF) in days: 1-30 in steps of 1;
# "off" (0) comes from the device profile
_SYR_CONNECT_SELECT_HYGIENE_PERIODIC_OPTIONS = list(range(1, 31))

# Stagnation flushing of a hygiene module line (getSCF, getSWF) in days: 1-7 in steps of 1
_SYR_CONNECT_SELECT_HYGIENE_STAGNATION_OPTIONS = list(range(1, 8))

# Flushing time after which a hygiene module line stops (getCSS, getWSS): raw 1-99 in steps
# of 1, in 10 s (10-990 s)
_SYR_CONNECT_SELECT_HYGIENE_STOP_TIME_OPTIONS = list(range(1, 100))

# Minimum humidity threshold (getMIH): 0-95 % in steps of 5. The lower boundary 0 doubles
# as "Off" (per docs/syrconnect-protocol.md), so no separate raw sentinel value is needed,
# unlike getMIT. Options are raw values; display labels (including the "Off" text) come
# from the select.getmih translation "state" map.
_SYR_CONNECT_SELECT_MIH_MAP = {str(v): v for v in range(0, 96, 5)}

# Minimum temperature threshold (getMIT): raw 1/10 °C, -30 to 49 °C in steps of 1 °C, with a
# dedicated "Off" sentinel (-400) outside the normal stepped range (see docs/syrconnect-protocol.md).
# Display labels come from the select.getmit translation "state" map.
# Option keys must match hassfest's [a-z0-9-_]+ (no leading hyphen), so negatives use "minus_".
_SYR_CONNECT_SELECT_MIT_MAP = {"off": -400} | {
    (f"minus_{-d * 10}" if d < 0 else str(d * 10)): d * 10 for d in range(-30, 50)
}

# Maximum humidity threshold (getMXH): 5-100 % in steps of 5. The upper boundary 100 doubles
# as "Off" (per docs/syrconnect-protocol.md), so no separate raw sentinel value is needed,
# unlike getMXT. Display labels come from the select.getmxh translation "state" map.
_SYR_CONNECT_SELECT_MXH_MAP = {str(v): v for v in range(5, 101, 5)}

# Maximum temperature threshold (getMXT): raw 1/10 °C, 1-50 °C in steps of 1 °C, with a dedicated "Off"
# sentinel (700). It is numerically above the range, so it sorts last.
# Display labels come from the select.getmxt translation "state" map.
_SYR_CONNECT_SELECT_MXT_MAP = {str(d * 10): d * 10 for d in range(1, 51)} | {"off": 700}

# Filling processes period (getRCD): 0=hour, 1=day, 2=week, 3=month (empty value = undefined)
_SYR_CONNECT_SELECT_RCD_MAP = {
    "undefined": None,
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
}

# Settings synchronization interval (getRCP) in seconds: non-uniform duration steps as
# documented in docs/syrconnect-protocol.md. Display labels come from the select.getrcp
# translation "state" map.
_SYR_CONNECT_SELECT_RCP_MAP = {
    "3600": 3600,
    "7200": 7200,
    "10800": 10800,
    "21600": 21600,
    "43200": 43200,
    "86400": 86400,
    "172800": 172800,
    "259200": 259200,
    "345600": 345600,
    "432000": 432000,
    "518400": 518400,
    "604800": 604800,
    "691200": 691200,
    "777600": 777600,
    "1209600": 1209600,
}

# Regeneration mode (getRMO): 1=Standard, 2=ECO, 3=Power, 4=Automatic
_SYR_CONNECT_SELECT_RMO_MAP = {
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
}

# Maximum filling duration (getRMT) in minutes: 1-5 (step 1), 10, 15-60 (step 15), 60-720 (step 30)
_SYR_CONNECT_SELECT_RMT_OPTIONS = sorted(
    {
        *range(1, 6),
        10,
        *range(15, 61, 15),
        *range(60, 721, 30),
    }
)

# Maximum filling charges (getRVT) in liters: 0=off, 10-100 in steps of 10,
# 100-1000 in steps of 50, 1000-9900 in steps of 100
_SYR_CONNECT_SELECT_RVT_OPTIONS = sorted(
    {
        0,
        *range(10, 101, 10),
        *range(100, 1001, 50),
        *range(1000, 9901, 100),
    }
)

# Stagnation time of the stagnation flushing (getSTP, HygBox) in minutes: 1-23 hours in
# steps of 1 hour, then 1-30 days in steps of 1 day
_SYR_CONNECT_SELECT_STP_OPTIONS = sorted(
    {
        *range(60, 1381, 60),
        *range(1440, 43201, 1440),
    }
)

# Measurement interval (getWMP) in seconds: non-uniform duration steps as documented in
# docs/syrconnect-protocol.md. Display labels come from the select.getwmp translation "state" map.
_SYR_CONNECT_SELECT_WMP_MAP = {
    "60": 60,
    "600": 600,
    "900": 900,
    "1800": 1800,
    "3600": 3600,
    "7200": 7200,
    "10800": 10800,
    "21600": 21600,
    "43200": 43200,
}

# Water type of the HygBox (getWTY): 1=cold water, 2=hot water (0 = undefined is not
# selectable)
_SYR_CONNECT_SELECT_WTY_MAP = {
    "1": 1,
    "2": 2,
}
