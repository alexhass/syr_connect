# Configuration URL for device info
"""Constants for the SYR Connect integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfMass,
    UnitOfPressure,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)

DOMAIN = "syr_connect"

_SYR_CONNECT_SCAN_INTERVAL_CONF = "scan_interval"
_SYR_CONNECT_SCAN_INTERVAL_DEFAULT = 60  # seconds

# Platform update limits
PARALLEL_UPDATES = 1  # Limit parallel updates to avoid overwhelming the API

# API URLs (internal)
_SYR_CONNECT_CONFIGURATION_URL = "https://syrconnect.de/"
_SYR_CONNECT_API_BASE_URL = "https://syrconnect.de/WebServices"
_SYR_CONNECT_API_LOGIN_URL = f"{_SYR_CONNECT_API_BASE_URL}/Api/SyrApiService.svc/REST/GetProjects"
_SYR_CONNECT_API_DEVICE_LIST_URL = f"{_SYR_CONNECT_API_BASE_URL}/SyrControlWebServiceTest2.asmx/GetProjectDeviceCollections"
_SYR_CONNECT_API_DEVICE_STATUS_URL = f"{_SYR_CONNECT_API_BASE_URL}/SyrControlWebServiceTest2.asmx/GetDeviceCollectionStatus"
_SYR_CONNECT_API_SET_STATUS_URL = f"{_SYR_CONNECT_API_BASE_URL}/SyrControlWebServiceTest2.asmx/SetDeviceCollectionStatus"
_SYR_CONNECT_API_STATISTICS_URL = f"{_SYR_CONNECT_API_BASE_URL}/SyrControlWebServiceTest2.asmx/GetLexPlusStatistics"

# Encryption keys (from original adapter) - internal
_SYR_CONNECT_CLIENT_ENCRYPTION_KEY = "d805a5c409dc354b6ccf03a2c29a5825851cf31979abf526ede72570c52cf954"
_SYR_CONNECT_CLIENT_ENCRYPTION_IV = "408a42beb8a1cefad990098584ed51a5"

# Checksum keys - internal
_SYR_CONNECT_CLIENT_CHECKSUM_KEY1 = "L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP"
_SYR_CONNECT_CLIENT_CHECKSUM_KEY2 = "KHGK5X29LVNZU56T"

# Device info - internal
_SYR_CONNECT_CLIENT_APP_VERSION = "App-3.7.10-de-DE-iOS-iPhone-15.8.3-de.consoft.syr.connect"
_SYR_CONNECT_CLIENT_USER_AGENT = "SYR/400 CFNetwork/1335.0.3.4 Darwin/21.6.0"

# Binary sensors mapping with their device classes - internal
_SYR_CONNECT_BINARY_SENSORS = {
    "getSRE": BinarySensorDeviceClass.RUNNING,  # Regeneration active
    "getPST": BinarySensorDeviceClass.RUNNING,  # Operating state
    "getSCR": BinarySensorDeviceClass.LOCK,     # Screen lock
    "getALM": BinarySensorDeviceClass.PROBLEM,  # Alarm
}

# Sensor device classes (for Home Assistant) - internal
_SYR_CONNECT_SENSOR_DEVICE_CLASS = {
    "getPRS": SensorDeviceClass.PRESSURE,
    "getFLO": SensorDeviceClass.VOLUME_FLOW_RATE,
}

# Sensor state classes (for Home Assistant) - internal
_SYR_CONNECT_SENSOR_STATE_CLASS = {
    "getRES": "measurement",
    "getTOR": "measurement",
    "getPRS": "measurement",
    "getFLO": "measurement",
    "getFCO": "total_increasing",
    "getNOR": "total_increasing",
}

# Sensors that should remain as strings (not converted to numbers) - internal
_SYR_CONNECT_STRING_SENSORS = {
    "getVER",  # Version
    "getFIR",  # Firmware
    "getSRN",  # Serial number
    "getCNA",  # Device name
    "getMAN",  # Manufacturer
    "getMAC",  # MAC Address
    "getIPA",  # IP Address
    "getDGW",  # Gateway
    "getRTI",  # Regeneration time (combined from getRTH and getRTM)
    "getWHU",  # Water hardness unit (mapped to unit names)
}

# Water hardness unit mapping (for getWHU)
# According to the SYR GUI, there are water hardness units "°dH" and "°fH" only.
_SYR_CONNECT_WATER_HARDNESS_UNIT_MAP = {
    0: "°dH",
    1: "°fH",
    2: "ppm",
    3: "mmol/l"
}

# Sensor icons (Material Design Icons) - internal
_SYR_CONNECT_SENSOR_ICONS = {
    # Water & Hardness
    "getIWH": "mdi:water-percent",
    "getOWH": "mdi:water-percent",
    "getWHU": "mdi:water-opacity",
    # Pressure & Flow
    "getPRS": "mdi:gauge",
    "getFLO": "mdi:waves-arrow-right",
    "getFCO": "mdi:counter",
    "getDWF": "mdi:water-alert",
    # Capacity & Supply
    "getRES": "mdi:gauge-empty",
    "getTOR": "mdi:gauge-full",
    "getSV1": "mdi:shaker",
    "getSV2": "mdi:shaker",
    "getSV3": "mdi:shaker",
    "getSS1": "mdi:cup-water",
    "getSS2": "mdi:cup-water",
    "getSS3": "mdi:cup-water",
    # Regeneration
    "getSRE": "mdi:autorenew",
    "getNOR": "mdi:counter",
    "getRTI": "mdi:clock-outline",
    "getRPD": "mdi:calendar-clock",
    "getRPW": "mdi:calendar-week",
    "nrdt": "mdi:calendar-clock",
    # System & Status
    "getALM": "mdi:bell-alert",
    "getPST": "mdi:power",
    "getSCR": "mdi:lock",
    "getRDO": "mdi:timer-sand",
    # Device Info
    "getSRN": "mdi:identifier",
    "getVER": "mdi:chip",
    "getFIR": "mdi:chip",
    "getCNA": "mdi:tag",
    "getMAN": "mdi:factory",
    "getMAC": "mdi:ethernet",
    "getIPA": "mdi:ip-network",
    "getDGW": "mdi:router-network",
    # Configuration
    "getCS1": "mdi:cog",
    "getCS2": "mdi:cog",
    "getCS3": "mdi:cog",
    "getRG1": "mdi:group",
    "getRG2": "mdi:group",
    "getRG3": "mdi:group",
    "getVS1": "mdi:gauge",
    "getVS2": "mdi:gauge",
    "getVS3": "mdi:gauge",
    # Regeneration Cycles
    "getCYN": "mdi:numeric",
    "getCYT": "mdi:clock-time-four",
}

# Diagnostic sensors (configuration, technical info, firmware) - internal
_SYR_CONNECT_DIAGNOSTIC_SENSORS = {
    'getSRN',  # Serial Number
    'getVER',  # Firmware Version
    'getFIR',  # Firmware Model
    'getTYP',  # Type
    'getCNA',  # Device Name
    'getMAN',  # Manufacturer
    'getMAC',  # MAC Address
    'getIPA',  # IP Address
    'getDGW',  # Gateway
    'getCDE',  # Configuration Code
    'getCS1', 'getCS2', 'getCS3',  # Configuration Levels
    'getINR',  # Internal Reference
    'getNOT',  # Notes
}

# Sensor units mapping (units are standardized and not translated) - internal
_SYR_CONNECT_SENSOR_UNITS = {
    # getIWH and getOWH units are set dynamically from getWHU
    "getRES": UnitOfVolume.LITERS,
    "getTOR": UnitOfVolume.LITERS,
    "getRPD": UnitOfTime.DAYS,
    "getRTH": UnitOfTime.HOURS,
    "getSV1": UnitOfMass.KILOGRAMS,
    "getSV2": UnitOfMass.KILOGRAMS,
    "getSV3": UnitOfMass.KILOGRAMS,
    "getSS1": UnitOfTime.WEEKS,
    "getSS2": UnitOfTime.WEEKS,
    "getSS3": UnitOfTime.WEEKS,
    "getPRS": UnitOfPressure.BAR,
    "getFLO": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
    "getFCO": UnitOfVolume.LITERS,
    "getDWF": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
    "getRDO": PERCENTAGE,
}

# Sensors to always exclude (parameters from XML that should not be exposed) - internal
_SYR_CONNECT_EXCLUDED_SENSORS = {
    'p1883', 'p1883rd', 'p8883', 'p8883rd',
    'sbt', 'sta', 'dst', 'ast', 'so',
    'dclg', 'clb', 'nrs',  # Device collection metadata
    'nrdt', 'dg',  # Additional device metadata attributes
    'dt',  # Timestamp attributes (getSRN_dt, getALM_dt, etc.)
    'getDEN',  # Boolean sensor - device enabled/disabled
    'getRTH', 'getRTM',  # Regeneration time - combined into getRTI
    'getCDE',  # Configuration code - not useful for users
    'getNOT',  # Notes field not useful as sensor
    'getSIR',  # Immediate regeneration control
    'getSTA',  # Status - redundant with other status sensors
    'getTYP',  # Type - not helpful for users
    'getINR',  # Internal reference - not useful
    'getLAR',  # Last action - not useful as sensor
    'getSRN_dt',
    'getALM_dt',
    # Boolean sensors - now handled as binary_sensor platform
    'getSRE',  # Regeneration active
    'getPST',  # Operating state
    'getSCR',  # Screen lock
    'getALM',  # Alarm
}

# Sensors to exclude only when value is 0 - internal
_SYR_CONNECT_EXCLUDE_WHEN_ZERO = {
    'getSV1', 'getSV2', 'getSV3',  # Salt amount containers
    'getSS1', 'getSS2', 'getSS3',  # Salt supply containers
    'getCS1', 'getCS2', 'getCS3',  # Configuration stages
    'getRG1', 'getRG2', 'getRG3',  # Regeneration groups
    'getVS1', 'getVS2', 'getVS3',  # Volume thresholds
}

# Sensors that are disabled by default (less frequently used) - internal
_SYR_CONNECT_DISABLED_BY_DEFAULT_SENSORS = {
    'getCYN',  # Cycle Counter - technical metric
    'getCYT',  # Cycle Time - technical metric
    'getNOT',  # Notes - rarely used
    'getINR',  # Internal Reference - technical
    'getLAR',  # Last Action - technical log
    'getRG1', 'getRG2', 'getRG3',  # Regeneration Groups - advanced config
    'getVS1', 'getVS2', 'getVS3',  # Volume Thresholds - advanced config
    'getCS1', 'getCS2', 'getCS3',  # Configuration Levels - advanced config
    'getRPW',  # Regenerations per Week - less useful than count
    'getDWF',  # Flow Warning Value - advanced setting
}
