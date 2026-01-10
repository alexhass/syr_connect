# Configuration URL for device info
"""Constants for the SYR Connect integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
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
}

# Mapping for getALM sensor values
# Maps raw API value -> internal key
# API values observed:
# - "NoSalt"  -> device reports salt empty <= 2kg
# - "LowSalt" -> device reports low salt <= 4kg
# - ""        -> no alarm >= 5kg
_SYR_CONNECT_SENSOR_ALARM_VALUE_MAP = {
    "NoSalt": "no_salt",
    "LowSalt": "low_salt",
    "": "no_alarm",
}

# Sensor device classes (for Home Assistant) - internal
_SYR_CONNECT_SENSOR_DEVICE_CLASS = {
    "getPRS": SensorDeviceClass.PRESSURE,
    "getFLO": SensorDeviceClass.VOLUME_FLOW_RATE,
}

# Sensor state classes (for Home Assistant) - internal
_SYR_CONNECT_SENSOR_STATE_CLASS = {
    "getRES": "measurement",        # Remaining Capacity 
    "getVOL": "measurement",        # Total Capacity
    "getPRS": "measurement",        # Pressure
    "getFLO": "measurement",        # Flow Rate
    "getINR": "total_increasing",   # Incomplete Regenerations
    "getFCO": "total_increasing",   # Total Flow Counter
    "getNOR": "total_increasing",   # Regenerations (normal operation)
    "getTOR": "total_increasing",   # Total regenerations
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
    "getRTI",  # Regeneration time
    "getWHU",  # Water hardness unit (mapped to unit names)

    # Custom non-API combined sensor
    "getRTIME", # CUSTOM Regeneration time (combined from getRTH and getRTM)
}

# Water hardness unit mapping (for getWHU)
# According to the SYR GUI, there are water hardness units "°dH" and "°fH" only.
_SYR_CONNECT_WATER_HARDNESS_UNIT_MAP = {
    0: "°dH",       # German degree of water hardness (Grad deutsche Härte)
    1: "°fH",       # French degree of water hardness (degré français de dureté)
    2: "ppm",       # Parts per million (mg/L), common international unit
    3: "mmol/l",    # Millimoles per liter, SI unit for water hardness
}

# Sensor icons (Material Design Icons) - internal
_SYR_CONNECT_SENSOR_ICONS = {
    # Sensors exits in devices:
    # - LEXplus10S
    # - LEXplus10SL

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
    "getVOL": "mdi:gauge-full",
    "getSV1": "mdi:shaker",
    "getSV2": "mdi:shaker",
    "getSV3": "mdi:shaker",
    "getSS1": "mdi:cup-water",
    "getSS2": "mdi:cup-water",
    "getSS3": "mdi:cup-water",
    # Regeneration
    "getINR": "mdi:counter",
    "getNOR": "mdi:counter",
    "getRTI": "mdi:clock-outline",
    "getRPD": "mdi:calendar-clock",
    "getRPW": "mdi:calendar-week",
    "getSRE": "mdi:autorenew",
    "getTOR": "mdi:counter",
    "nrdt": "mdi:calendar-clock",
    # System & Status
    "getALM": "mdi:bell-alert",
    "getPST": "mdi:power",
    "getSCR": "mdi:lock",
    "getRDO": "mdi:shaker",
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

    # Custom non-API combined sensor
    "getRTIME": "mdi:clock-outline", # Regeneration time (combined from getRTH and getRTM)

    # Sensors exits in devices:
    # - LEXplus10SL

    # Leak protection profile sensors
    "getPF1": "mdi:water-alert",
    "getPF2": "mdi:water-alert",
    "getPF3": "mdi:water-alert",
    "getPF4": "mdi:water-alert",
    "getPF5": "mdi:water-alert",
    "getPF6": "mdi:water-alert",
    "getPF7": "mdi:water-alert",
    "getPF8": "mdi:water-alert",
    "getPT1": "mdi:timer-outline",
    "getPT2": "mdi:timer-outline",
    "getPT3": "mdi:timer-outline",
    "getPT4": "mdi:timer-outline",
    "getPT5": "mdi:timer-outline",
    "getPT6": "mdi:timer-outline",
    "getPT7": "mdi:timer-outline",
    "getPT8": "mdi:timer-outline",
    "getPV1": "mdi:gauge",
    "getPV2": "mdi:gauge",
    "getPV3": "mdi:gauge",
    "getPV4": "mdi:gauge",
    "getPV5": "mdi:gauge",
    "getPV6": "mdi:gauge",
    "getPV7": "mdi:gauge",
    "getPV8": "mdi:gauge",
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
    'getINR',  # Incomplete regenerations
    'getNOT',  # Notes
}

# Sensor units mapping (units are standardized and not translated) - internal
_SYR_CONNECT_SENSOR_UNITS = {
    # Sensors exits in devices:
    # - LEXplus10S
    # - LEXplus10SL

    # getIWH and getOWH units are set dynamically from getWHU
    "getRES": UnitOfVolume.LITERS,                          # Remaining Capacity
    "getVOL": UnitOfVolume.LITERS,                          # Total Capacity (older alternative to getTOR)
    "getRPD": UnitOfTime.DAYS,                              # Regeneration Interval
    "getRTH": UnitOfTime.HOURS,                             # Regeneration Time (Hour)
    "getSV1": UnitOfMass.KILOGRAMS,                         # Salt amount container 1
    "getSV2": UnitOfMass.KILOGRAMS,                         # Salt amount container 2
    "getSV3": UnitOfMass.KILOGRAMS,                         # Salt amount container 3
    "getSS1": UnitOfTime.WEEKS,                             # Salt supply container 1
    "getSS2": UnitOfTime.WEEKS,                             # Salt supply container 2
    "getSS3": UnitOfTime.WEEKS,                             # Salt supply container 3
    "getPRS": UnitOfPressure.BAR,                           # Pressure
    "getFLO": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,       # Flow Rate
    "getFCO": UnitOfVolume.LITERS,                          # Total Flow Counter
    "getDWF": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,       # Flow Warning Value
    "getRDO": f"{UnitOfMass.GRAMS}/{UnitOfVolume.LITERS}",  # Salt Dosing (g/L)

    # Sensors exits in devices:
    # - LEXplus10SL

    # Leak protection profile sensors
    "getPF1": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak Protection Flow Rate 1
    "getPF2": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak Protection Flow Rate 2
    "getPF3": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak Protection Flow Rate 3
    "getPF4": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak Protection Flow Rate 4
    "getPF5": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak Protection Flow Rate 5
    "getPF6": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak Protection Flow Rate 6
    "getPF7": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak Protection Flow Rate 7
    "getPF8": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak Protection Flow Rate 8
    "getPT1": UnitOfTime.MINUTES,                       # Leak Protection Time 1
    "getPT2": UnitOfTime.MINUTES,                       # Leak Protection Time 2
    "getPT3": UnitOfTime.MINUTES,                       # Leak Protection Time 3
    "getPT4": UnitOfTime.MINUTES,                       # Leak Protection Time 4
    "getPT5": UnitOfTime.MINUTES,                       # Leak Protection Time 5
    "getPT6": UnitOfTime.MINUTES,                       # Leak Protection Time 6
    "getPT7": UnitOfTime.MINUTES,                       # Leak Protection Time 7
    "getPT8": UnitOfTime.MINUTES,                       # Leak Protection Time 8
    "getPV1": UnitOfVolume.LITERS,                      # Leak Protection Volume 1
    "getPV2": UnitOfVolume.LITERS,                      # Leak Protection Volume 2
    "getPV3": UnitOfVolume.LITERS,                      # Leak Protection Volume 3    
    "getPV4": UnitOfVolume.LITERS,                      # Leak Protection Volume 4
    "getPV5": UnitOfVolume.LITERS,                      # Leak Protection Volume 5
    "getPV6": UnitOfVolume.LITERS,                      # Leak Protection Volume 6
    "getPV7": UnitOfVolume.LITERS,                      # Leak Protection Volume 7
    "getPV8": UnitOfVolume.LITERS,                      # Leak Protection Volume 8
}

# Sensor display precision mapping (number of decimals to show)
# Use integers for whole-number display (0), or >0 for decimal places.
# This allows configuring how many decimals Home Assistant should show
# for specific sensors when the integration formats the value.
_SYR_CONNECT_SENSOR_PRECISION = {
    "getCFO": 0,  # Cycle Flow Offset: show as whole number by default
    "getCYN": 0,  # Cycle Counter: show as whole number by default
    "getINR": 0,  # Incomplete Regenerations: show as whole number by default
    "getIWH": 0,  # Incoming Water Hardness: show as whole number by default
    "getFCO": 0,  # Total Flow Counter: show as whole number by default
    "getFLO": 0,  # Flow Rate: show as whole number by default
    "getNOR": 0,  # Regenerations (normal operation): show as whole number by default
    "getRDO": 0,  # Salt Dosing: show as whole number by default
    "getRPD": 0,  # Regeneration Interval: show as whole days by default
    "getRPW": 0,  # Regenerations per Week: show as whole number by default
    "getPRS": 1,  # Pressure: show with 1 decimal place by default
    "getRES": 0,  # Remaining Capacity: show as whole number by default
    "getSS1": 0,  # Salt Supply Container 1: show as whole number by default
    "getSS2": 0,  # Salt Supply Container 2: show as whole number by default
    "getSS3": 0,  # Salt Supply Container 2: show as whole number by default
    "getSV1": 0,  # Salt Supply Volume 1: show as whole number by default
    "getSV2": 0,  # Salt Supply Volume 2: show as whole number by default
    "getSV3": 0,  # Salt Supply Volume 3: show as whole number by default
    "getTOR": 0,  # Total regenerations: show as whole number by default
    "getOWH": 0,  # Outgoing Water Hardness: show as whole number by default
}

# Sensors to always exclude (parameters from XML that should not be exposed) - internal
_SYR_CONNECT_EXCLUDED_SENSORS = {
    # Sensors exits in devices:
    # - LEXplus10S
    # - LEXplus10SL

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
    'getSTA',  # Status – What the system is currently doing during maintenance, in Polish
    'getTYP',  # Type - not helpful for users
    'getLAR',  # Last action - not useful as sensor
    'getSRN_dt',
    'getALM_dt',
    'getRTI',  # Value is always 00:00. Not clear what it represents.
    # Boolean sensors - now handled as binary_sensor platform
    'getSRE',  # Regeneration active
    'getPST',  # Operating state
    'getSCR',  # Screen lock

    # Sensors exits in devices:
    # - LEXplus10SL

    # Leak protection - internal flags (unclear meaning)
    'getPM1', 'getPM2', 'getPM3', 'getPM4', 'getPM5', 'getPM6', 'getPM7', 'getPM8',
    'getPB1', 'getPB2', 'getPB3', 'getPB4', 'getPB5', 'getPB6', 'getPB7', 'getPB8',
    'getPR1', 'getPR2', 'getPR3', 'getPR4', 'getPR5', 'getPR6', 'getPR7', 'getPR8',
    # Technical values without context
    'get71', 'getAB', 'getAVO', 'getBSA', 'getBUZ',
    'getCDF', 'getCEL', 'getCES', 'getCND', 'getCNO', 'getCNS', 'getCOF',
    'getDAT', 'getDBD', 'getDBT', 'getDCM', 'getDMA', 'getDOM', 'getDPL',
    'getDRP', 'getDST', 'getDTC', 'getDWF',
    'getFSL', 'getIDS', 'getLDF', 'getLWT', 'getMTF',
    'getNPS', 'getOHF', 'getYHF',
    'getSLE', 'getSLF', 'getSLO', 'getSLP', 'getSLT', 'getSLV',
    'getT2', 'getTN', 'getVLV',
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
    # Sensors exits in devices:
    # - LEXplus10S
    # - LEXplus10SL

    'getCYN',  # Cycle Counter - technical metric
    'getCYT',  # Cycle Time - technical metric
    'getNOT',  # Notes - rarely used
    'getLAR',  # Last Action - technical log
    'getRG1', 'getRG2', 'getRG3',  # Regeneration Groups - advanced config
    'getVS1', 'getVS2', 'getVS3',  # Volume Thresholds - advanced config
    'getCS1', 'getCS2', 'getCS3',  # Configuration Levels - advanced config
    'getRPW',  # Regenerations per Week - less useful than count
    'getDWF',  # Flow Warning Value - advanced setting
    'getFCO',  # Total Flow Counter - defined in XML, but does not provide any values (always 0)

    # Sensors exits in devices:
    # - LEXplus10SL

    # Leak protection profiles (expert setting)
    'getPA1', 'getPA2', 'getPA3', 'getPA4', 'getPA5', 'getPA6', 'getPA7', 'getPA8',
    'getPF1', 'getPF2', 'getPF3', 'getPF4', 'getPF5', 'getPF6', 'getPF7', 'getPF8',
    'getPT1', 'getPT2', 'getPT3', 'getPT4', 'getPT5', 'getPT6', 'getPT7', 'getPT8',
    'getPV1', 'getPV2', 'getPV3', 'getPV4', 'getPV5', 'getPV6', 'getPV7', 'getPV8',
    'getPN1', 'getPN2', 'getPN3', 'getPN4', 'getPN5', 'getPN6', 'getPN7', 'getPN8',
    'getPRN',  # Duplicate of getPRF
    'getPW1', 'getPW2', 'getPW3', 'getPW4', 'getPW5', 'getPW6', 'getPW7', 'getPW8',    
}

# All n-keys from <sc><dvs><d><c> in LEXplus10S.xml
_SYR_CONNECT_LEXPLUS10S_KEYS = [
    "getSRN", "getVER", "getFIR", "getTYP", "getCNA", "getALM", "getCDE", "getCS1", "getCS2", "getCS3",
    "getCYN", "getCYT", "getDEN", "getDGW", "getDWF", "getFCO", "getFLO", "getINR", "getIPA", "getIWH",
    "getLAR", "getMAC", "getMAN", "getNOR", "getNOT", "getOWH", "getPRS", "getPST", "getRDO", "getRES",
    "getRG1", "getRG2", "getRG3", "getRPD", "getRPW", "getRTH", "getRTI", "getRTM", "getSCR", "getSIR",
    "getSRE", "getSS1", "getSS2", "getSS3", "getSTA", "getSV1", "getSV2", "getSV3", "getTOR", "getVS1",
    "getVS2", "getVS3", "getWHU"
]

# All n-keys from <sc><dvs><d><c> in LEXplus10SL.xml
_SYR_CONNECT_LEXPLUS10SL_KEYS = [
    "getSRN", "getVER", "getFIR", "getTYP", "getCNA", "get71", "getAB", "getALA", "getAVO", "getBSA", "getBUZ",
    "getCDE", "getCDF", "getCEL", "getCES", "getCND", "getCNO", "getCNS", "getCOF", "getCS1", "getCYN", "getCYT",
    "getDAT", "getDBD", "getDBT", "getDCM", "getDEN", "getDGW", "getDMA", "getDOM", "getDPL", "getDRP", "getDST",
    "getDTC", "getDWF", "getFCO", "getFLO", "getFSL", "getIDS", "getINR", "getIPA", "getIWH", "getLAN", "getLAR",
    "getLDF", "getLWT", "getMAC", "getMAN", "getMTF", "getNOR", "getNOT", "getNPS", "getOHF", "getOWH", "getPA1",
    "getPA2", "getPA3", "getPA4", "getPA5", "getPA6", "getPA7", "getPA8", "getPB1", "getPB2", "getPB3", "getPB4",
    "getPB5", "getPB6", "getPB7", "getPB8", "getPF1", "getPF2", "getPF3", "getPF4", "getPF5", "getPF6", "getPF7",
    "getPF8", "getPM1", "getPM2", "getPM3", "getPM4", "getPM5", "getPM6", "getPM7", "getPM8", "getPN1", "getPN2",
    "getPN3", "getPN4", "getPN5", "getPN6", "getPN7", "getPN8", "getPR1", "getPR2", "getPR3", "getPR4", "getPR5",
    "getPR6", "getPR7", "getPR8", "getPRF", "getPRN", "getPRS", "getPST", "getPT1", "getPT2", "getPT3", "getPT4",
    "getPT5", "getPT6", "getPT7", "getPT8", "getPV1", "getPV2", "getPV3", "getPV4", "getPV5", "getPV6", "getPV7",
    "getPV8", "getPW1", "getPW2", "getPW3", "getPW4", "getPW5", "getPW6", "getPW7", "getPW8", "getRDO", "getRES",
    "getRG1", "getRPD", "getRPW", "getRTH", "getRTI", "getRTM", "getSCR", "getSIR", "getSLE", "getSLF", "getSLO",
    "getSLP", "getSLT", "getSLV", "getSRE", "getSRV", "getSS1", "getSTA", "getSV1", "getT2", "getTMP", "getTMZ",
    "getTN", "getTOR", "getVLV", "getVS1", "getWHU", "getYHF"
]

# All unique n-keys from LEXplus10S and LEXplus10SL XML
_SYR_CONNECT_LEX_KEYS = list(set(_SYR_CONNECT_LEXPLUS10S_KEYS) | set(_SYR_CONNECT_LEXPLUS10SL_KEYS))
_SYR_CONNECT_LEX_KEYS.sort()
