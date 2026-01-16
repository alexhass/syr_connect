# Configuration URL for device info
"""Constants for the SYR Connect integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    UnitOfMass,
    UnitOfPressure,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
    UnitOfTemperature,
    PERCENTAGE,
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

# Mapping for getSTA / status values -> Polish values
# These map observed Polish status to internal translations
_SYR_CONNECT_SENSOR_STATUS_VALUE_MAP = {
    "Płukanie wsteczne": "status_backwash",
    "Płukanie regenerantem (0mA)": "status_regenerant_rinse",
    "Płukanie wolne": "status_slow_rinse",
    "Płukanie szybkie 1": "status_fast_rinse",
    "Napełnianie": "status_filling",
    "": "status_inactive",
}

# Sensor device classes (for Home Assistant) - internal
_SYR_CONNECT_SENSOR_DEVICE_CLASS = {
    "getCOF": SensorDeviceClass.WATER,
    "getFLO": SensorDeviceClass.VOLUME_FLOW_RATE,
    "getLAR": SensorDeviceClass.TIMESTAMP,
    "getPRS": SensorDeviceClass.PRESSURE,
}

# Sensor state classes (for Home Assistant) - internal
_SYR_CONNECT_SENSOR_STATE_CLASS = {
    "getCEL": SensorStateClass.MEASUREMENT,        # Water temperature
    "getCOF": SensorStateClass.TOTAL_INCREASING,   # Total water consumption counter
    "getCYN": SensorStateClass.MEASUREMENT,        # Regeneration cycle number/time
    "getCYT": SensorStateClass.MEASUREMENT,        # Regeneration cycle time
    "getFLO": SensorStateClass.MEASUREMENT,        # Flow rate
    "getINR": SensorStateClass.TOTAL_INCREASING,   # Incomplete regenerations
    "getIWH": SensorStateClass.MEASUREMENT,        # Incoming water hardness
    "getNOR": SensorStateClass.TOTAL_INCREASING,   # Regenerations (normal operation)
    "getOWH": SensorStateClass.MEASUREMENT,        # Outgoing water hardness
    "getPRS": SensorStateClass.MEASUREMENT,        # Pressure
    "getRDO": SensorStateClass.MEASUREMENT,        # Salt dosing (g/L)
    "getRES": SensorStateClass.MEASUREMENT,        # Remaining capacity
    "getSS1": SensorStateClass.MEASUREMENT,        # Salt container supply 1 (weeks)
    "getSS2": SensorStateClass.MEASUREMENT,        # Salt container supply 2 (weeks)
    "getSS3": SensorStateClass.MEASUREMENT,        # Salt container supply 3 (weeks)
    "getSV1": SensorStateClass.MEASUREMENT,        # Salt container amount 1
    "getSV2": SensorStateClass.MEASUREMENT,        # Salt container amount 2
    "getSV3": SensorStateClass.MEASUREMENT,        # Salt container amount 3
    "getTOR": SensorStateClass.TOTAL_INCREASING,   # Total regenerations
    "getVOL": SensorStateClass.MEASUREMENT,        # Total capacity
    "getVS1": SensorStateClass.MEASUREMENT,        # Volume threshold 1
    "getVS2": SensorStateClass.MEASUREMENT,        # Volume threshold 2
    "getVS3": SensorStateClass.MEASUREMENT,        # Volume threshold 3
}

# Sensors that should remain as strings (not converted to numbers) - internal
_SYR_CONNECT_STRING_SENSORS = {
    "getCNA",  # Device name
    "getDGW",  # Gateway
    "getFIR",  # Firmware
    "getIPA",  # IP address
    "getMAC",  # MAC address
    "getMAN",  # Manufacturer
    "getRTI",  # Regeneration time
    "getRTIME", # CUSTOM Regeneration time (combined from getRTH and getRTM)
    "getSRN",  # Serial number
    "getVER",  # Version
    "getWHU",  # Water hardness unit (mapped to unit names)
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
    "getCOF": "mdi:counter",
    "getPRS": "mdi:gauge",
    "getFLO": "mdi:waves-arrow-right",
    "getFCO": "mdi:counter",
    "getDWF": "mdi:water-alert",
    # Capacity & Supply
    "getRES": "mdi:gauge-empty",
    "getVOL": "mdi:gauge-full",
    "getSV1": "mdi:delete-variant",
    "getSV2": "mdi:delete-variant",
    "getSV3": "mdi:delete-variant",
    "getSS1": "mdi:calendar-week",
    "getSS2": "mdi:calendar-week",
    "getSS3": "mdi:calendar-week",
    # Regeneration
    "getINR": "mdi:counter",
    "getNOR": "mdi:counter",
    "getRTI": "mdi:clock-outline",
    "getRPD": "mdi:calendar-clock",
    "getRPW": "mdi:calendar-week",
    "getSRE": "mdi:autorenew",
    "getTOR": "mdi:counter",
    "nrdt": "mdi:calendar-clock",
    "getLAR": "mdi:calendar-clock",
    # System & Status
    "getALM": "mdi:bell-alert",
    "getPST": "mdi:check-circle",
    "getSTA": "mdi:list-status",
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
    "getCS1": "mdi:beaker",
    "getCS2": "mdi:beaker",
    "getCS3": "mdi:beaker",
    "getRG1": "mdi:valve-closed",
    "getRG2": "mdi:valve-closed",
    "getRG3": "mdi:valve-closed",
    "getVS1": "mdi:gauge",
    "getVS2": "mdi:gauge",
    "getVS3": "mdi:gauge",
    # Regeneration Cycles
    "getCYN": "mdi:numeric",
    "getCYT": "mdi:timer-sync",

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
    'getCNA',  # Device name
    'getDGW',  # Gateway
    'getFIR',  # Firmware model
    'getIPA',  # IP address
    'getMAC',  # MAC address
    'getMAN',  # Manufacturer
    'getSRN',  # Serial number
    'getTYP',  # Type
    'getVER',  # Firmware version
}

# Sensor units mapping (units are standardized and not translated) - internal
_SYR_CONNECT_SENSOR_UNITS = {
    # Sensors exits in devices:
    # - LEXplus10S
    # - LEXplus10SL

    # getIWH and getOWH units are set dynamically from getWHU
    "getRES": UnitOfVolume.LITERS,                          # Remaining capacity
    "getVOL": UnitOfVolume.LITERS,                          # Total capacity
    "getRPD": UnitOfTime.DAYS,                              # Regeneration interval
    "getRTH": UnitOfTime.HOURS,                             # Regeneration time (Hour)
    "getSV1": UnitOfMass.KILOGRAMS,                         # Salt container amount 1
    "getSV2": UnitOfMass.KILOGRAMS,                         # Salt container amount 2
    "getSV3": UnitOfMass.KILOGRAMS,                         # Salt container amount 3
    "getSS1": UnitOfTime.WEEKS,                             # Salt container supply 1
    "getSS2": UnitOfTime.WEEKS,                             # Salt container supply 2
    "getSS3": UnitOfTime.WEEKS,                             # Salt container supply 3
    "getPRS": UnitOfPressure.BAR,                           # Pressure
    "getFLO": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,       # Flow rate
    "getFCO": "ppm",                                        # Iron content (parts per million)
    "getDWF": UnitOfVolume.LITERS,                          # Expected daily water consumption
    "getRDO": f"{UnitOfMass.GRAMS}/{UnitOfVolume.LITERS}",  # Salt dosing (g/L)

    # Configuration/resin capacity sensors are percentage values
    "getCS1": PERCENTAGE,                                 # Remaining resin capacity 1 (percent)
    "getCS2": PERCENTAGE,                                 # Remaining resin capacity 2 (percent)
    "getCS3": PERCENTAGE,                                 # Remaining resin capacity 3 (percent)

    # Sensors exits in devices:
    # - LEXplus10SL

    # Leak protection profile sensors
    "getCEL": UnitOfTemperature.CELSIUS,                # Water temperature
    "getCOF": UnitOfVolume.LITERS,                      # Total water consumption counter
    "getPF1": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak protection flow rate 1
    "getPF2": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak protection flow rate 2
    "getPF3": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak protection flow rate 3
    "getPF4": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak protection flow rate 4
    "getPF5": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak protection flow rate 5
    "getPF6": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak protection flow rate 6
    "getPF7": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak protection flow rate 7
    "getPF8": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Leak protection flow rate 8
    "getPT1": UnitOfTime.MINUTES,                       # Leak protection time 1
    "getPT2": UnitOfTime.MINUTES,                       # Leak protection time 2
    "getPT3": UnitOfTime.MINUTES,                       # Leak protection time 3
    "getPT4": UnitOfTime.MINUTES,                       # Leak protection time 4
    "getPT5": UnitOfTime.MINUTES,                       # Leak protection time 5
    "getPT6": UnitOfTime.MINUTES,                       # Leak protection time 6
    "getPT7": UnitOfTime.MINUTES,                       # Leak protection time 7
    "getPT8": UnitOfTime.MINUTES,                       # Leak protection time 8
    "getPV1": UnitOfVolume.LITERS,                      # Leak protection volume 1
    "getPV2": UnitOfVolume.LITERS,                      # Leak protection volume 2
    "getPV3": UnitOfVolume.LITERS,                      # Leak protection volume 3    
    "getPV4": UnitOfVolume.LITERS,                      # Leak protection volume 4
    "getPV5": UnitOfVolume.LITERS,                      # Leak protection volume 5
    "getPV6": UnitOfVolume.LITERS,                      # Leak protection volume 6
    "getPV7": UnitOfVolume.LITERS,                      # Leak protection volume 7
    "getPV8": UnitOfVolume.LITERS,                      # Leak protection volume 8
}

# Sensor display precision mapping (number of decimals to show)
# Use integers for whole-number display (0), or >0 for decimal places.
# This allows configuring how many decimals Home Assistant should show
# for specific sensors when the integration formats the value.
_SYR_CONNECT_SENSOR_PRECISION = {
    "getCEL": 1,    # Water temperature, e.g. 110 = 11.0°C
    "getCFO": 0,    # Cycle flow offset: show as whole number by default
    "getCOF": 0,    # Total water consumption counter: show as whole number by default
    "getCS1": 0,    # Remaining resin capacity 1: show as whole number by default
    "getCS2": 0,    # Remaining resin capacity 2: show as whole number by default
    "getCS3": 0,    # Remaining resin capacity 3: show as whole number by default
    "getCYN": 0,    # Regeneration cycle counter: show as whole number by default
    "getDWF": 0,    # Expected daily water consumption: show as whole number by default
    "getFCO": 0,    # Iron content: show as whole number by default
    "getFLO": 0,    # Flow rate: show as whole number by default
    "getINR": 0,    # Incomplete regenerations: show as whole number by default
    "getIWH": 0,    # Incoming water hardness: show as whole number by default
    "getNOR": 0,    # Regenerations (normal operation): show as whole number by default
    "getOWH": 0,    # Outgoing water hardness: show as whole number by default
    "getPRS": 1,    # Pressure: show with 1 decimal place by default
    "getPST": 0,    # Pressure sensor installed: show as whole number by default
    "getRDO": 0,    # Salt dosing: show as whole number by default
    "getRPD": 0,    # Regeneration interval: show as whole days by default
    "getRES": 0,    # Remaining capacity: show as whole number by default
    "getRG1": 0,    # Regeneration 1: show as whole number by default
    "getRG2": 0,    # Regeneration 2: show as whole number by default
    "getRG3": 0,    # Regeneration 3: show as whole number by default
    "getSS1": 0,    # Salt container supply 1: show as whole number by default
    "getSS2": 0,    # Salt container supply 2: show as whole number by default
    "getSS3": 0,    # Salt container supply 3: show as whole number by default
    "getSV1": 0,    # Salt container volume 1: show as whole number by default
    "getSV2": 0,    # Salt container volume 2: show as whole number by default
    "getSV3": 0,    # Salt container volume 3: show as whole number by default
    "getTOR": 0,    # Total regenerations: show as whole number by default
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
    'getSRN_dt',
    'getALM_dt',

    'getDEN',  # Boolean sensor - device enabled/disabled
    'getRTH', 'getRTM',  # Regeneration time - combined into getRTIME
    'getCDE',  # Unknown constant (some kind of device identifier?) - not useful for users
    'getNOT',  # Notes field not useful as sensor
    'getSIR',  # Immediate regeneration control
    'getSMR',  # Manual regeneration control - per documentation unknown what values do
    'getRPW',  # Days on which regeneration is allowed, stored as a bit mask
    'getRST',  # Reset device control - per documentation unknown what values do
    'getTYP',  # Type of device (always 80?) - not helpful for users
    'getRTI',  # Value is always 00:00. Not clear what it represents.
    'getFCO',  # Iron content (always 0) - not useful
    'getSCR',  # Unknown, likely number of service regeneration

    # BUG: Exclude until the bug is found why these are not shown as translated strings.
    # They also seem to exists as sensor and binary_sensor.
    'getSRE',  # Regeneration active - now handled as binary_sensor platform

    # Sensors exits in devices:
    # - LEXplus10SL

    # Leak protection - internal flags (unclear meaning)
    'getPM1', 'getPM2', 'getPM3', 'getPM4', 'getPM5', 'getPM6', 'getPM7', 'getPM8',
    'getPB1', 'getPB2', 'getPB3', 'getPB4', 'getPB5', 'getPB6', 'getPB7', 'getPB8',
    'getPR1', 'getPR2', 'getPR3', 'getPR4', 'getPR5', 'getPR6', 'getPR7', 'getPR8',
    # Technical values without context
    'get71', 'getAB', 'getAVO', 'getBSA', 'getBUZ',
    'getCDF', 
    'getCES', 'getCND', 'getCNO', 'getCNS',
    'getDAT', 'getDBD', 'getDBT', 'getDCM', 'getDMA', 'getDOM', 'getDPL',
    'getDRP', 'getDST', 'getDTC', 
    'getDWF', # Expected daily water consumption. If at the regeneration time getRES() < getDWF() a regeneration will start
    'getFSL', 'getIDS', 'getLDF', 'getLWT', 'getMTF',
    'getNPS', 'getOHF', 'getYHF',
    'getSLE', 'getSLF', 'getSLO', 'getSLP', 'getSLT', 'getSLV',
    'getT2', 'getTN', 'getVLV',
}

# Sensors to exclude only when value is 0 - internal
_SYR_CONNECT_EXCLUDE_WHEN_ZERO = {
    'getCS1', 'getCS2', 'getCS3',  # Remaining resin capacity (percent)
    'getSS1', 'getSS2', 'getSS3',  # Salt storage (weeks)
    'getSV1', 'getSV2', 'getSV3',  # Salt amount (kg)
    'getVS1', 'getVS2', 'getVS3',  # Volume thresholds
}

# Sensors that are disabled by default (less frequently used) - internal
_SYR_CONNECT_DISABLED_BY_DEFAULT_SENSORS = {
    # Sensors exits in devices:
    # - LEXplus10S
    # - LEXplus10SL

    'getCYN',  # Regeneration cycle counter - technical metric - Shows remaining time during regeneration runs
    'getCYT',  # Regeneration cycle time - technical metric - Shows remaining process cycles during regeneration runs
    'getNOT',  # Notes - rarely used
    'getLAR',  # Last regeneration as UNIX timestamp (seconds since 1.1.1970)
    'getVS1', 'getVS2', 'getVS3',  # Volume thresholds - advanced config
    'getDWF',  # Flow Warning Value - advanced setting
    'getRG1',  # Regeneration 1 - enabled by default
    'getSRE',  # Regeneration active
    'getRG2', 'getRG3',  # Regeneration running for tank
    "getPST",  # Pressure sensor installed: 1 = not available, 2 = available

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
