"""Constants for the SYR Connect integration."""

from dataclasses import dataclass

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

_SYR_CONNECT_SCAN_INTERVAL_CONF = "scan_interval"
_SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT = 60  # seconds
_SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT = 60  # seconds
_SYR_CONNECT_API_XML_SCAN_INTERVAL_MINIMUM = 60  # seconds
_SYR_CONNECT_API_JSON_SCAN_INTERVAL_MINIMUM = 10  # seconds
_SYR_CONNECT_API_SCAN_INTERVAL_MAXIMUM = 600  # seconds

# Client-side re-login interval of the local JSON API (ADM login, minutes). Assumed; the device
# itself is not known to time out the login. The XML (cloud) API has no client-side timeout; it
# logs in again when the server rejects the token.
_SYR_CONNECT_SESSION_TIMEOUT_MINUTES = 30

# API URLs (internal)
_SYR_CONNECT_API_XML_BASE_URL = "https://syrconnect.de/"
_SYR_CONNECT_API_XML_LOGIN_URL = "WebServices/Api/SyrApiService.svc/REST/GetProjects"
_SYR_CONNECT_API_XML_DEVICE_GET_LIST_URL = (
    "WebServices/SyrControlWebServiceTest2.asmx/GetProjectDeviceCollections"
)
_SYR_CONNECT_API_XML_DEVICE_GET_STATUS_URL = (
    "WebServices/SyrControlWebServiceTest2.asmx/GetDeviceCollectionStatus"
)
_SYR_CONNECT_API_XML_DEVICE_SET_STATUS_URL = (
    "WebServices/SyrControlWebServiceTest2.asmx/SetDeviceCollectionStatus"
)
_SYR_CONNECT_API_XML_DEVICE_GET_STATISTICS_URL = (
    "WebServices/SyrControlWebServiceTest2.asmx/GetLexPlusStatistics"
)

# Encryption keys (from original adapter) - internal
_SYR_CONNECT_CLIENT_ENCRYPTION_KEY = (
    "d805a5c409dc354b6ccf03a2c29a5825851cf31979abf526ede72570c52cf954"
)
_SYR_CONNECT_CLIENT_ENCRYPTION_IV = "408a42beb8a1cefad990098584ed51a5"

# Checksum keys - internal
_SYR_CONNECT_CLIENT_CHECKSUM_KEY1 = "L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP"
_SYR_CONNECT_CLIENT_CHECKSUM_KEY2 = "KHGK5X29LVNZU56T"

# Device info - internal
# CF = Core Foundation (iOS/macOS framework)
# Example: "App-3.9.7-de-DE-iOS-iPhone-27.0.0-de.consoft.syr.connect"
_SYR_CONNECT_CLIENT_OS_LANGUAGE = (
    "en-US"  # Default; the integration passes the HA locale instead
)
_SYR_CONNECT_CLIENT_OS_NAME = "iOS"
_SYR_CONNECT_CLIENT_OS_VERSION = "27.0.0"
_SYR_CONNECT_CLIENT_OS_MODEL = "iPhone"
_SYR_CONNECT_CLIENT_CF_BUNDLE_VERSION = "3.9.7"
_SYR_CONNECT_CLIENT_CF_BUNDLE_IDENTIFIER = "de.consoft.syr.connect"
_SYR_CONNECT_CLIENT_APP_NAME = "SYR Connect"
_SYR_CONNECT_CLIENT_APP_VERSION = f"App-{_SYR_CONNECT_CLIENT_CF_BUNDLE_VERSION}-{_SYR_CONNECT_CLIENT_OS_LANGUAGE}-{_SYR_CONNECT_CLIENT_OS_NAME}-{_SYR_CONNECT_CLIENT_OS_MODEL}-{_SYR_CONNECT_CLIENT_OS_VERSION}-{_SYR_CONNECT_CLIENT_CF_BUNDLE_IDENTIFIER}"

# Example: "SYR/485 CFNetwork/3896.100.1.2.1 Darwin/27.0.0"
_SYR_CONNECT_CLIENT_SYR_BUNDLE_NAME = "SYR"
# Example: 3.9.7-485 -> 485 (build number is incremented for each release, but not directly related to bundle version)
_SYR_CONNECT_CLIENT_SYR_BUNDLE_BUILDNUMBER = "485"
_SYR_CONNECT_CLIENT_OS_FRAMEWORK = "CFNetwork/3896.100.1.2.1"
_SYR_CONNECT_CLIENT_OS_KERNEL = "Darwin/27.0.0"
_SYR_CONNECT_CLIENT_USER_AGENT = f"{_SYR_CONNECT_CLIENT_SYR_BUNDLE_NAME}/{_SYR_CONNECT_CLIENT_SYR_BUNDLE_BUILDNUMBER} {_SYR_CONNECT_CLIENT_OS_FRAMEWORK} {_SYR_CONNECT_CLIENT_OS_KERNEL}"


@dataclass(frozen=True, kw_only=True)
class SyrConnectService:
    """Cloud API service (app brand) of the SYR Connect XML API."""

    # App name sent in the login request. It is bound to api_base_url: the login
    # fails unless both belong to the same service.
    api_app_name: str
    # Base URL of the API endpoints (login, device status), ends with "/"
    api_base_url: str
    # Bundle identifier of the official app. The server does not check it, it is
    # sent to emulate the app. Also the key of the service in the registry.
    cf_bundle_identifier: str
    # User-facing URL in the HA device info card, may differ from api_base_url
    configuration_url: str
    # Name of the service in the config flow
    display_name: str


# Cloud API service registry: one entry per backend service, keyed by
# cf_bundle_identifier.
_SYR_CONNECT_API_SERVICES: dict[str, SyrConnectService] = {
    "de.consoft.syr.connect": SyrConnectService(
        api_app_name="SYR Connect",
        api_base_url="https://syrconnect.de/",
        cf_bundle_identifier="de.consoft.syr.connect",
        configuration_url="https://syrconnect.de/",
        display_name="SYR Connect",
    ),
    "de.consoft.gc.conel.connect": SyrConnectService(
        api_app_name="CLEAR PRO",
        api_base_url="https://api.conelclearpro.de/",
        cf_bundle_identifier="de.consoft.gc.conel.connect",
        configuration_url="https://conelclearpro.de/",
        display_name="CONEL CLEAR PRO",
    ),
    "de.consoft.gsh.comfort.connect": SyrConnectService(
        api_app_name="comfort CONNECT",
        api_base_url="https://syrconnect.de/",
        cf_bundle_identifier="de.consoft.gsh.comfort.connect",
        configuration_url="https://syrconnect.de/",
        display_name="Sanibel comfort CONNECT",
    ),
    "de.consoft.isg.concept.connect": SyrConnectService(
        api_app_name="concept CONNECT",
        api_base_url="https://syrconnect.de/",
        cf_bundle_identifier="de.consoft.isg.concept.connect",
        configuration_url="https://syrconnect.de/",
        display_name="concept CONNECT",
    ),
    "de.consoft.sanitaerunion.ditech.connect": SyrConnectService(
        api_app_name="DITECH Geräte",
        api_base_url="https://syrconnect.de/",
        cf_bundle_identifier="de.consoft.sanitaerunion.ditech.connect",
        configuration_url="https://syrconnect.de/",
        display_name="DITECH Haustechnik",
    ),
    "de.consoft.isg.optima.connect": SyrConnectService(
        api_app_name="optima CONNECT",
        api_base_url="https://syrconnect.de/",
        cf_bundle_identifier="de.consoft.isg.optima.connect",
        configuration_url="https://syrconnect.de/",
        display_name="Optima CONNECT",
    ),
    "de.consoft.rwc.connect": SyrConnectService(
        api_app_name="RwcMultisafe",
        api_base_url="https://rwcmultisafe.com/",
        cf_bundle_identifier="de.consoft.rwc.connect",
        configuration_url="https://rwcmultisafe.com/",
        display_name="RWC MultiSafe",
    ),
    "de.consoft.polygonvatro.connect": SyrConnectService(
        api_app_name="POLYGONVATRO Connect",
        api_base_url="https://polygonvatro-connect.de/",
        cf_bundle_identifier="de.consoft.polygonvatro.connect",
        configuration_url="https://polygonvatro-connect.de/",
        display_name="POLYGONVATRO Connect",
    ),
}

# Default CF bundle identifier used as the default selection in the UI
# Keep as a separate named constant to avoid hard-coded strings scattered across the codebase.
_SYR_CONNECT_DEFAULT_CF_BUNDLE_IDENTIFIER = "de.consoft.syr.connect"

# Values that mean "no alarm present" (compared after strip().upper()).
_SYR_CONNECT_SENSOR_ALA_CODES_NO_ALARM = {
    "",
    "0",
    "00",
    "FF",
    "A0X0000",
    "255",
}

_SYR_CONNECT_SENSOR_ALA_CODES_GENERIC = {
    "0D": "alarm_salt_supply_empty",
    "0E": "alarm_valve_position",
    "15": "alarm_heating_fill_volume_leak",
    "16": "alarm_heating_fill_time_leak",
    "17": "alarm_fill_cycles_exceeded",
    "18": "alarm_cartridge_exhausted_capacity",
    "19": "alarm_cartridge_exhausted_conductivity",
    "1A": "alarm_target_pressure_unreachable",
    "A1": "alarm_end_switch",
    "A2": "alarm_motor_current_exceeded",
    "A3": "alarm_leakage_volume_reached",
    "A4": "alarm_leakage_time_reached",
    "A5": "alarm_max_flow_rate_reached",
    "A6": "alarm_microleakage_detected",
    "A7": "alarm_external_sensor_leakage_radio",
    "A8": "alarm_flow_sensor_fault",
    "A9": "alarm_pressure_sensor_faulty",
    "AA": "alarm_temperature_sensor_faulty",
    "AB": "fault_conductance_sensor",
    "AC": "fault_conductance_sensor",
    "AD": "alarm_increased_water_hardness",
    "AE": "error_no_information",
    "FF": "no_alarm",
}

# Notification code mappings
_SYR_CONNECT_SENSOR_NOT_CODES_GENERIC = {
    "01": "new_software_available",
    "02": "bi_annual_maintenance",
    "03": "annual_maintenance",
    "04": "new_software_installed",
    "07": "filter_maintenance_reminder",
    "08": "filter_service_reminder",
    "09": "backwash_reminder_pressure",
    "FF": "no_notification",
    "": "no_notification",
}

# Warning code mappings
_SYR_CONNECT_SENSOR_WRN_CODES_GENERIC = {
    "01": "power_outage",
    "02": "salt_supply_low",
    "07": "leak_warning",
    "08": "battery_low",
    "09": "initial_filling",
    "0A": "leak_warning_volume",
    "0B": "leak_warning_time",
    "10": "cartridge_almost_exhausted",
    "11": "leak_warning_time",
    "13": "no_batteries_detected",
    "14": "outlet_pressure_too_high",
    "A6": "microleakage_suspected",
    "FF": "no_warning",
    "": "no_warning",
}

# Mapping for getALM sensor values
# Maps raw API value (compared after strip().upper()) -> internal key
# API values observed:
# - "NoSalt"  -> device reports salt empty <= 2kg
# - "LowSalt" -> device reports low salt <= 4kg
# - ""        -> no alarm >= 5kg
_SYR_CONNECT_SENSOR_ALM_VALUE_MAP = {
    "NOSALT": "no_salt",
    "LOWSALT": "low_salt",
    "": "no_alarm",
}

# Device type codes (getTYP) that report getBAT as battery percentage (%) rather than voltage (V).
# To add support for a new device, append its getTYP value as a string.
_SYR_CONNECT_SENSOR_BAT_VALUE_PERCENTAGE = {
    "120",  # SafeFloor - reports e.g. "40" = 40%
    "122",  # SafeFloor - reports e.g. "40" = 40%
}

# Mapping for getLE sensor values (Leakage protection - Present level)
# Maps raw API value (integer) -> display value in liters
_SYR_CONNECT_SENSOR_LE_VALUE_MAP = {
    2: 100,
    3: 150,
    4: 200,
    5: 250,
    6: 300,
    7: 350,
    8: 400,
    9: 450,
    10: 500,
    11: 550,
    12: 600,
    13: 650,
    14: 700,
    15: 750,
    16: 800,
    17: 850,
    18: 900,
    19: 950,
    20: 1000,
    21: 1050,
    22: 1100,
    23: 1150,
    24: 1200,
    25: 1250,
    26: 1300,
    27: 1350,
    28: 1400,
    29: 1450,
    30: 1500,
}

# getRPW: Days on which regeneration is allowed, stored as a bit mask.
#
# This maps a single-bit mask value to the corresponding weekday index
# (0 = Monday .. 6 = Sunday). A mask value of 0 indicates "no days configured"
# Example: mask 5 (0b0000101) means Monday (1<<0) and Wednesday (1<<2).
#
# Use this mapping to decode device `getRPW` bitmasks where each bit
# represents a weekday. Documentation only.
_SYR_CONNECT_SENSOR_RPW_VALUE_MAP = {
    0: None,  # No days configured
    1: 0,  # Monday
    2: 1,  # Tuesday
    4: 2,  # Wednesday
    8: 3,  # Thursday
    16: 4,  # Friday
    32: 5,  # Saturday
    64: 6,  # Sunday
}

# Mapping for getCRS sensor values (Cartridge size)
# Maps raw API value (integer) -> display value in liters
_SYR_CONNECT_SENSOR_CRS_VALUE_MAP = {
    1: 2.5,
    2: 4,
    3: 7,
    4: 14,
    5: 30,
}

# Mapping for getSTA / status values -> Polish values
# This assigns the observed Polish status to the internal translations.
# - "Płukanie regenerantem (5mA)"
# - "Płukanie szybkie 1"
_SYR_CONNECT_SENSOR_STA_VALUE_MAP = {
    "Płukanie wsteczne": "status_backwash",
    "Płukanie regenerantem": "status_regenerant_rinse",
    "Płukanie wolne": "status_slow_rinse",
    "Płukanie szybkie": "status_fast_rinse",
    "Napełnianie": "status_filling",
    "": "status_inactive",
    # Newer models (Syr AC 3200, AC 3228 / SYR MultiController) report getSTA
    # as a plain integer code instead of a status message string.
    "0": "status_standby",
    "1": "status_initial_filling",
    "2": "status_automatic_filling",
    "3": "status_manual_filling",
}

# Mapping for getT1, getT2 sensor values (Time leakage)
# Maps raw API value (integer) -> display value in hours (float)
_SYR_CONNECT_SENSOR_T1_VALUE_MAP = {
    1: 0.5,
    2: 1.0,
    3: 1.5,
    4: 2.0,
    5: 2.5,
    6: 3.0,
    7: 3.5,
    8: 4.0,
    9: 4.5,
    10: 5.0,
    11: 5.5,
    12: 6.0,
    13: 6.5,
    14: 7.0,
    15: 7.5,
    16: 8.0,
    17: 8.5,
    18: 9.0,
    19: 9.5,
    20: 10.0,
    21: 10.5,
    22: 11.0,
    23: 11.5,
    24: 12.0,
    25: 12.5,
    26: 13.0,
    27: 13.5,
    28: 14.0,
    29: 14.5,
    30: 15.0,
    31: 15.5,
    32: 16.0,
    33: 16.5,
    34: 17.0,
    35: 17.5,
    36: 18.0,
    37: 18.5,
    38: 19.0,
    39: 19.5,
    40: 20.0,
    41: 20.5,
    42: 21.0,
    43: 21.5,
    44: 22.0,
    45: 22.5,
    46: 23.0,
    47: 23.5,
    48: 24.0,
    49: 24.5,
    50: 25.0,
}

# Mapping for getUL sensor values (Leakage protection - Absent level)
# Maps raw API value (integer) -> display value in liters
_SYR_CONNECT_SENSOR_UL_VALUE_MAP = {
    1: 10,
    2: 20,
    3: 30,
    4: 40,
    5: 50,
    6: 60,
    7: 70,
    8: 80,
    9: 90,
    10: 100,
}

# Water hardness unit mapping (for getWHU)
# According to the SYR GUI, there are water hardness units "°dH" and "°fH" only.
_SYR_CONNECT_SENSOR_WHU_VALUE_MAP = {
    0: "°dH",  # German degree of water hardness (Grad deutsche Härte)
    1: "°fH",  # French degree of water hardness (degré français de dureté)
    2: "ppm",  # Parts per million (mg/L), common international unit
    3: "mmol/l",  # Millimoles per liter, SI unit for water hardness
}

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

# TODO: Temporarily disabled - getFCD select (filter backwash interval).
# Known bug: After writing a new value, the server resets the setting back to its previous value.
# Root cause is unknown. Re-enable once the write-back issue is resolved, with this option map
# and a getFCD block in _build_device_selects:
# _SYR_CONNECT_SELECT_FCD_MAP = {
#     "2592000": 2592000,
#     "5184000": 5184000,
#     "7776000": 7776000,
#     "10368000": 10368000,
#     "12960000": 12960000,
#     "15552000": 15552000,
#     "18144000": 18144000,
#     "20736000": 20736000,
#     "23328000": 23328000,
#     "25920000": 25920000,
#     "28512000": 28512000,
#     "31104000": 31104000,
# }

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

# Settings synchronisation interval (getRCP) in seconds: non-uniform duration steps as
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
