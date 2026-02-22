"""Constants for the SYR Connect integration."""
# Configuration URL for device info

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfConductivity,
    UnitOfElectricPotential,
    UnitOfMass,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)

DOMAIN = "syr_connect"

_SYR_CONNECT_SCAN_INTERVAL_CONF = "scan_interval"
_SYR_CONNECT_SCAN_INTERVAL_DEFAULT = 60  # seconds

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

# Device model mapping for salt capacity per salt container (kg).
# Keys are normalized to uppercase when looked up.
#
# Known models:
# - LEXplus10, LEXplus10S, LEXplus10SL -> 25 kg per container
#
# Unknown models with similar names can have up to 300 kg per container.
# Fallback to 25 kg when unknown.
_SYR_CONNECT_MODEL_SALT_CAPACITY = {
    "lexplus10": 25,
    "lexplus10s": 25,
    "lexplus10sl": 25,
    "neosoft2500": 40,
    "neosoft5000": 35,
    # TODO: Below names are not confirmed models.
    # Names are guessed from data sheets with similar pattern, values are documented in data sheets.
    "unknown_lex10": 25,
    "unknown_lex20": 70,
    "unknown_lex30": 70,
    "unknown_lex40": 75,
    "unknown_lex60": 110,
    "unknown_lex80": 200,
    "unknown_lex100": 300,
}

# Alarm code mappings per device model (raw API getALA -> internal translation key)
# These are used to map device-specific alarm codes to internal translation keys.
_SYR_CONNECT_SENSOR_ALA_CODES_LEX10 = {
    "0": "no_alarm",
}

_SYR_CONNECT_SENSOR_ALA_CODES_NEOSOFT = {
    "FF": "no_alarm",
    "A1": "alarm_end_switch",
    "A2": "alarm_turbine_blocked",
    "A3": "alarm_leakage_volume_reached",
    "A4": "alarm_leakage_time_reached",
    "A5": "alarm_max_flow_rate_reached",
    "A6": "alarm_microleakage_detected",
    "A7": "alarm_external_sensor_leakage_radio",
    "A8": "alarm_external_sensor_leakage_cable",
    "A9": "alarm_pressure_sensor_faulty",
    "AA": "alarm_temperature_sensor_faulty",
    "AB": "fault_conductance_sensor",
    "AC": "fault_conductance_sensor",
    "AE": "error_no_information",
    "AD": "alarm_increased_water_hardness",
    "0D": "alarm_salt_supply_empty",
    "0E": "alarm_valve_position",
}

_SYR_CONNECT_SENSOR_ALA_CODES_SAFET = {
    "FF": "no_alarm",
    "A1": "alarm_end_switch",
    "A2": "alarm_turbine_blocked",
    "A3": "alarm_leakage_volume_reached",
    "A4": "alarm_leakage_time_reached",
    "A5": "alarm_max_flow_rate_reached",
    "A6": "alarm_microleakage_detected",
    "A7": "alarm_external_sensor_leakage_radio",
    "A8": "alarm_external_sensor_leakage_cable",
    "A9": "alarm_pressure_sensor_faulty",
    "AA": "alarm_temperature_sensor_faulty",
    "AB": "alarm_weak_battery",
    "AE": "error_no_information",
    "WeakBat": "alarm_weak_battery",
}

_SYR_CONNECT_SENSOR_NOT_CODES = {
    "01": "new_software_available",
    "02": "bi_annual_maintenance",
    "03": "annual_maintenance",
    "04": "new_software_installed",
    "FF": "no_notification",
}

_SYR_CONNECT_SENSOR_WRN_CODES = {
    "01": "power_outage",
    "02": "salt_supply_low",
    "07": "leak_warning",
    "08": "battery_low",
    "09": "initial_filling",
    "10": "leak_warning_volume",
    "11": "leak_warning_time",
    "FF": "no_warning",
}

# Binary sensors mapping with their device classes - internal
_SYR_CONNECT_SENSOR_BINARY = {
    "getSRE": BinarySensorDeviceClass.RUNNING,  # Regeneration active
}

# Sensors that are represented by control entities (select/text/buttons)
# These sensors should be hidden from the regular sensor platform.
_SYR_CONNECT_SENSOR_CONTROLLED = {
    "getAB",    # Valve shut-off (false=open, true=closed) - also represented as select entity
    "getSV1",   # Salt container amount 1 - also represented as select entity
    "getSV2",   # Salt container amount 2 - also represented as select entity
    "getSV3",   # Salt container amount 3 - also represented as select entity
    "getPRF",   # Active leak protection profile
    "getRPD",   # Regeneration interval - also represented as select entity
    "getRTM",   # Regeneration time (minutes or combined) - represented as select entity
}

# Diagnostic sensors (configuration, technical info, firmware) - internal
_SYR_CONNECT_SENSOR_DIAGNOSTIC = {
    'getCNA',  # Device name
    'getDGW',  # Gateway
    'getEGW',  # Ethernet gateway
    'getEIP',  # Ethernet IP address
    'getFIR',  # Firmware model
    'getIPA',  # IP address
    'getMAC',  # MAC address
    'getMAC1', # Wi-Fi MAC address
    'getMAC2', # LAN MAC address
    'getMAN',  # Manufacturer
    'getSRN',  # Serial number
    'getTYP',  # Type
    'getVER',  # Firmware version
    'getWGW',  # Wi-Fi gateway
    'getWIP',  # Wi-Fi IP address
}

# Sensors that are disabled by default (less frequently used) - internal
_SYR_CONNECT_SENSOR_DISABLED_BY_DEFAULT = {
    # Sensors exits in devices:
    # - LEXplus10S
    # - LEXplus10SL

    'getCYN',  # Regeneration cycle counter - technical metric - Shows remaining time during regeneration runs
    'getCYT',  # Regeneration cycle time - technical metric - Shows remaining process cycles during regeneration runs
    'getDWF',  # Flow Warning Value - advanced setting
    'getLAN',  # Language of the UI (0=English, 1=German, 3=Spanish)
    'getNOT',  # Retrieving the current notification
    'getSRE',  # Regeneration active
    'getRG2', 'getRG3',  # Regeneration running for tank
    'getRPD',  # Regeneration interval (days)
    'getRPW',  # Regeneration permitted weekdays as bit mask
    'getPST',  # Pressure sensor installed: 1 = not available, 2 = available
    'getVS1', 'getVS2', 'getVS3',  # Volume thresholds - advanced config
    'getWHU',  # Water hardness unit

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

    # Sensors exits in devices:
    # - NeoSoft 2500 / 5000

    'getVPS1',  # No turbine pulses on control head 1 since (timestamp) - technical metric for flow measurement, not useful for most users
    'getVPS2',  # No turbine pulses on control head 2 since (timestamp) - technical metric for flow measurement, not useful for most users

    # Sensors exits in devices:
    # - NeoSoft 2500 / 5000 / Trio DFR/LS

    'getWFC',   # Wi-Fi SSID
    'getWFR',   # Wifi signal strength (%)
    'getWFS',   # Wi-Fi connection status (connected / not connected)
}

# Sensor device classes (for Home Assistant) - internal
_SYR_CONNECT_SENSOR_DEVICE_CLASS = {
    "getBAR": SensorDeviceClass.PRESSURE,
    "getBAT": SensorDeviceClass.VOLTAGE,
    "getCOF": SensorDeviceClass.WATER,
    "getFLO": SensorDeviceClass.VOLUME_FLOW_RATE,
    "getLAR": SensorDeviceClass.TIMESTAMP,
    "getPRS": SensorDeviceClass.PRESSURE,
    "getVOL": SensorDeviceClass.WATER,
}

# Sensors to always exclude (parameters from XML that should not be exposed) - internal
_SYR_CONNECT_SENSOR_EXCLUDED = {
    # Uninstall - This will delete the sensors from the entity registry if they were created before.
    "getRTIME",  # Uninstall custom regeneration time control

    # Sensors exits in devices:
    # - LEXplus10S
    # - LEXplus10SL

    'p1883', 'p1883rd', 'p8883', 'p8883rd',
    'sbt', 'sta', 'dst', 'ast', 'so',
    'dclg', 'clb', 'nrs',  # Device collection metadata
    'nrdt', 'dg',  # Additional device metadata attributes

    # Other attributes than "n" = "name" / "v" = "value" in XML response
    'getSRN_dt',    # Serial number timestamp
    'getALM_acd',   # Active alarm since timestamp
    'getALM_dt',    # Alarm timestamp
    'getALM_ih',    # Alarm inhibit flag (unlcear purpose)
    'getALM_m',     # Alarm message e.g. LowSalt

    'getDEN',  # Boolean sensor - device enabled/disabled
    'getRTH',  # Regeneration hour - minutes/combined handled by getRTM
    'getCDE',  # Unknown constant (some kind of device identifier?) - not useful for users
    'getNOT',  # Notifications
    'getSIR',  # Immediate regeneration control
    'getSMR',  # Manual regeneration control - per documentation unknown what values do
    'getRST',  # Reset device control - per documentation unknown what values do
    'getTYP',  # Type of device (Known values: 1 = Safe-T+, 80 = Lex water softeners) - not helpful for users
    'getRTI',  # Value is always 00:00. Not clear what it represents.
    'getFCO',  # Iron content (always 0) - not useful
    'getSCR',  # Unknown, likely number of service regeneration

    # BUG: Exclude until the bug is found why these are not shown as translated strings.
    # They also seem to exists as sensor and binary_sensor.
    'getSRE',  # Regeneration active - now handled as binary_sensor platform

    # Sensors exits in devices:
    # - LEXplus10SL

    # Technical values without context
    'get71', 'getBSA', 'getBUZ',
    'getCDF',
    'getCES', 'getCND',
    'getCNO', # Code number - not useful for users
    'getCNS',
    'getDAT', 'getDBD', 'getDBT', 'getDCM', 'getDMA', 'getDOM', 'getDPL',
    'getDST', 'getDTC',
    'getDWF', # Expected daily water consumption. If at the regeneration time getRES() < getDWF() a regeneration will start
    'getFSL', 'getIDS', 'getLDF', 'getLWT', 'getMTF',
    'getOHF', 'getYHF',
    'getSLO', 'getSLP',
    'getT2', 'getTN',

    # Sensors exits in devices:
    # - Safe-T+

    # Unknown Safe-T+ specific sensors
    'f', 'b', 'm',  # CI values from API response, unclear purpose, (m = MAC address)
    'getALA_acd',   # Last alarm - timestamp - acknowledged?
    'getALA_dt',    # Last alarm - timestamp - occurence?
    'getALA_ih',    # Last alarm - e.g. 0 - Unknown
    'getALA_m',     # Last alarm - alarm codes e.g. A5, A6
    'getAWY',       # Unknown
    'getBLT',       # Unknown
    'getBSI',       # Unknown
    'getCEO',       # Unknown
    #'getCNO',      # Code number - not useful for users (duplicate of getCNO from LEXplus10SL)
    'getEXI',       # Unknown
    'getEXT',       # Unknown
    'getGLE',       # Unknown
    'getGUL',       # Unknown
    'getINT',       # Unknown
    'getREL',       # Unknown
    #'getT2',       # Leakage time? unclear (duplicate of getT2 from LEXplus10SL)
    'getTBS',       # Unknown
    'getTC',        # Unknown
    'getTO',        # Unknown
    'getTPA',       # Unknown
    'getUNI',       # Unknown

    # Sensors exits in devices:
    # - NeoSoft 2500 / 5000

    'getALN',       # Value: "", unclear meaning
    'getALW',       # Value: "", unclear meaning
    'getBMX',       # Value: "", unclear meaning
    'getERE',       # Value: "", unclear meaning
    #'getLDF',      # Value: "", unclear meaning
    'getLMS',       # Value: "", unclear meaning
    'getNRE',       # Value: "", unclear meaning
    #'getOHF',      # Value: "", unclear meaning
    'getPRE',       # Value: "", unclear meaning
    'getVRE1',      # Value: "", unclear meaning
    'getVRE2',      # Value: "", unclear meaning
    #'getYHF',      # Value: "", unclear meaning
    'getHWV',       # Value: e.g. "V1", "0000000001", unclear meaning
    'getAPT',       # Value: e.g. "600", unclear meaning
    'getCNF',       # Value: "", unclear meaning
    'getCSD',       # Value: "", unclear meaning
    'getEVL',       # Value: "0", unclear meaning
    #'getIDS',      # Value: "False", unclear meaning
    'getLNG',       # Value: "0", unclear meaning
    'getPSD',       # Value: "", unclear meaning
    'getRTC',       # Value: "", unclear meaning
    'getRURL',      # Value: "", unclear meaning
    'getTMZ',       # Value: "4", unclear meaning
    'getTURL',      # Value: "", unclear meaning
    'getWAD',       # Value: "False", unclear meaning
    'getWTI',       # Value: e.g. "1720", unclear meaning
    #'getNOT',      # Value: e.g. "FF", unclear meaning
    'getALD',       # Value: "", unclear meaning
    'getCNL',       # Value: "", unclear meaning
    'getWAH',       # Value: "", unclear meaning
    'getNET',       # Value: "", unclear meaning
    'getTSD',       # Value: "", unclear meaning

    # Sensors exits in devices:
    # - Trio DFR/LS

    "getAFW",
    #"getALD",
    #"getAPT",
    "getBAP",
    "getBAR2",
    "getBFT",
    "getBPT",
    #"getBSA",
    "getCCK",
    "getCFW",
    #"getCND",  # Conductivity in µS/cm
    "getCND2",
    #"getCNF",
    #"getCNL",
    #"getCSD",
    "getCSE",
    "getCURL",
    #"getDBT",
    #"getDCM",
    #"getDMA",
    #"getDOM",
    #"getDPL",
    #"getDST",
    #"getDTC",
    "getENV",
    #"getEVL",
    "getDTR",
    #"getFSL",
    #"getHWV",
    #"getIDS",
    "getLED",
    "getLOCK",
    #"getLNG",
    #"getLWT",
    "getSMF",
    #"getPSD",
    "getPSE",
    "getPRN",
    "getRCE",
    #"getRTC",
    #"getRURL",
    "getSFV",
    "getSLP_m",
    "getSLP_sd",
    "getSLP_ed",
    #"getSLO",
    "getSOF",
    "getSRO",
    "getSRV",
    #"getTN",
    #"getTMZ",
    #"getTSD",
    "getTSE",
    #"getTURL",
    "getVER2",
    "getVTO",
    #"getWAD",
    #"getWAH",
    "getWFL",
    "getWNS",
    #"getWTI",
    #"getNET",
}

# Sensors to exclude only when value is empty (0 or "") - internal
_SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY = {
    'getCS1', 'getCS2', 'getCS3',  # Remaining resin capacity (percent)
    'getSS1', 'getSS2', 'getSS3',  # Salt storage (weeks)
    'getSV1', 'getSV2', 'getSV3',  # Salt amount (kg)
    'getVS1', 'getVS2', 'getVS3',  # Volume thresholds

    # Sensors exits in devices only:
    # - LEXplus10SL
    # - Safe-T+
    'getCEL',  # Water temperature - value "" means sensor does not exists or not measured.
    'getNPS',  # Microleakage count - value "" means sensor does not exists.

    # Sensors exits in devices only:
    # - NeoSoft 2500 / 5000
    'getBAR',  # Pressure at inlet - value "" means sensor does not exists or not measured
    'getCYT',  # Regeneration cycle time - value "0" means no active regeneration, should be "00:00" to show a time.
    'getLAR',  # Last regeneration (timestamp) - if 0 means no regeneration has happened yet, so not useful to show.
    'getVPS1', # No turbine pulses on control head 1 since (timestamp). Value "" means sensor does not exists.
    'getVPS2', # No turbine pulses on control head 2 since (timestamp). Value "" means sensor does not exists.
    'getEGW',  # Ethernet gateway
    'getEIP',  # Ethernet IP address
    'getWGW',  # Wi-Fi gateway
    'getWIP',  # Wi-Fi IP address

    # Sensors exits in devices only:
    # - NeoSoft 5000

    # NOT TESTED
    # RPD and RTM have no influence on the NeoSoft 5000, as this system initiates regeneration automatically as soon
    # as a pillar is exhausted. Softened water is available at all times.
    #'getRPD',   # Regeneration interval (days) - value "0" means no interval configured.
    #'getRTM',   # Regeneration time (minutes) - value "0" means no active regeneration, should be "00:00" to show a time.

    # Sensors exits in devices only:
    # - Trio DFR/LS
    "getSRV",  # Next annual maintenance (timestamp) - if "" means no maintenance required, so not useful to show.
    "getCND",  # Conductivity in µS/cm - value "" means sensor does not exists or not measured.
}

# Sensor icons (Material Design Icons) - internal
_SYR_CONNECT_SENSOR_ICON = {
    # Sensors exits in devices:
    # - LEXplus10S
    # - LEXplus10SL
    # - Safe-T+

    # Safe-T+ specific
    "getBAR": "mdi:gauge",
    "getBAT": "mdi:battery",
    "getVLV": "mdi:valve",

    # - LEXplus10SL
    # - Safe-T+
    "getAB": "mdi:valve",
    "getAVO": "mdi:waves-arrow-right",

    # Water & Hardness
    "getIWH": "mdi:water-percent",
    "getOWH": "mdi:water-percent",
    "getWHU": "mdi:water-opacity",
    # Pressure & Flow
    "getCOF": "mdi:counter",
    "getDWF": "mdi:water-alert",
    "getFCO": "mdi:counter",
    "getFLO": "mdi:waves-arrow-right",
    "getPRS": "mdi:gauge",
    # Capacity & Supply
    "getRES": "mdi:gauge",
    "getSS1": "mdi:calendar-week",
    "getSS2": "mdi:calendar-week",
    "getSS3": "mdi:calendar-week",
    "getSV1": "mdi:delete-variant",
    "getSV2": "mdi:delete-variant",
    "getSV3": "mdi:delete-variant",
    "getVOL": "mdi:gauge-full",
    # Regeneration
    "getINR": "mdi:counter",
    "getLAR": "mdi:calendar-clock",
    "getNOR": "mdi:counter",
    "getRTI": "mdi:clock-outline",
    "getRPD": "mdi:calendar-clock",
    "getRPW": "mdi:calendar-filter-outline",
    "getSRE": "mdi:autorenew",
    "getTOR": "mdi:counter",
    "nrdt": "mdi:calendar-clock",
    # System & Status
    "getALM": "mdi:bell-alert",
    "getALA": "mdi:bell-alert",
    "getNOT": "mdi:bell",
    "getWRN": "mdi:alert",
    "getSTA": "mdi:list-status",
    "getPST": "mdi:check-circle",
    "getRDO": "mdi:shaker",
    # Device Info
    "getCNA": "mdi:tag",
    "getDGW": "mdi:router-network",
    "getFIR": "mdi:chip",
    "getIPA": "mdi:ip-network",
    "getLAN": "mdi:translate",
    "getMAN": "mdi:factory",
    "getMAC": "mdi:ethernet",
    "getSRN": "mdi:identifier",
    "getVER": "mdi:chip",
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
    "getRTM": "mdi:clock-outline", # Regeneration time (minutes or combined HH:MM)

    # Sensors exits in devices:
    # - LEXplus10SL

    # Leak protection profile sensors
    "getCEL": "mdi:thermometer",
    "getLE": "mdi:water-alert",
    "getNPS": "mdi:pipe-leak",
    "getT1": "mdi:timer-outline",
    "getT2": "mdi:timer-outline",
    "getTMP": "mdi:timer-off-outline",
    "getUL": "mdi:water-alert",
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
    # Leak protection profile icons (active/name/week/mode/return time)
    "getPA1": "mdi:shield-check",
    "getPA2": "mdi:shield-check",
    "getPA3": "mdi:shield-check",
    "getPA4": "mdi:shield-check",
    "getPA5": "mdi:shield-check",
    "getPA6": "mdi:shield-check",
    "getPA7": "mdi:shield-check",
    "getPA8": "mdi:shield-check",

    "getPN1": "mdi:account",
    "getPN2": "mdi:account",
    "getPN3": "mdi:account",
    "getPN4": "mdi:account",
    "getPN5": "mdi:account",
    "getPN6": "mdi:account",
    "getPN7": "mdi:account",
    "getPN8": "mdi:account",

    "getPB1": "mdi:bell-alert",
    "getPB2": "mdi:bell-alert",
    "getPB3": "mdi:bell-alert",
    "getPB4": "mdi:bell-alert",
    "getPB5": "mdi:bell-alert",
    "getPB6": "mdi:bell-alert",
    "getPB7": "mdi:bell-alert",
    "getPB8": "mdi:bell-alert",

    "getPW1": "mdi:alert",
    "getPW2": "mdi:alert",
    "getPW3": "mdi:alert",
    "getPW4": "mdi:alert",
    "getPW5": "mdi:alert",
    "getPW6": "mdi:alert",
    "getPW7": "mdi:alert",
    "getPW8": "mdi:alert",

    "getPM1": "mdi:pipe-leak",
    "getPM2": "mdi:pipe-leak",
    "getPM3": "mdi:pipe-leak",
    "getPM4": "mdi:pipe-leak",
    "getPM5": "mdi:pipe-leak",
    "getPM6": "mdi:pipe-leak",
    "getPM7": "mdi:pipe-leak",
    "getPM8": "mdi:pipe-leak",

    "getPR1": "mdi:clock-outline",
    "getPR2": "mdi:clock-outline",
    "getPR3": "mdi:clock-outline",
    "getPR4": "mdi:clock-outline",
    "getPR5": "mdi:clock-outline",
    "getPR6": "mdi:clock-outline",
    "getPR7": "mdi:clock-outline",
    "getPR8": "mdi:clock-outline",

    # Sensors exits in devices:
    # - NeoSoft 2500 / 5000
    "getEGW": "mdi:router-network",
    "getEIP": "mdi:ip-network",
    "getMAC1": "mdi:ethernet",          # Wi-Fi MAC address
    "getMAC2": "mdi:ethernet",          # LAN MAC address
    "getLTV": "mdi:faucet",             # Last dispensed volume
    "getRMO": "mdi:autorenew",
    "getSRH": "mdi:calendar-clock",     # Next semi-annual maintenance
    "getSRV": "mdi:calendar-clock",     # Next annual maintenance
    "getVPS1": "mdi:turbine",           # No turbine pulses on control head 1 since
    "getVPS2": "mdi:turbine",           # No turbine pulses on control head 2 since
    "getWGW": "mdi:router-wireless",
    "getWIP": "mdi:ip-network",
    "getWFC": "mdi:wifi",
    "getWFS": "mdi:wifi-check",
    "getWFR": "mdi:wifi-strength-1",

    # Sensors exits in devices:
    # - Trio DFR/LS

    "getDRP": "mdi:calendar-clock",
    "getDSV": "mdi:water-check",
    "getDTT": "mdi:clock-outline",
    "getPRF": "mdi:account",
    "getSLV": "mdi:water",
    "getSLF": "mdi:waves-arrow-right",
    "getSLT": "mdi:timer-outline",
    "getSLE": "mdi:timer-sand",
}

# Mapping for getALM sensor values
# Maps raw API value -> internal key
# API values observed:
# - "NoSalt"  -> device reports salt empty <= 2kg
# - "LowSalt" -> device reports low salt <= 4kg
# - ""        -> no alarm >= 5kg
_SYR_CONNECT_SENSOR_ALM_VALUE_MAP = {
    "NoSalt": "no_salt",
    "LowSalt": "low_salt",
    "": "no_alarm",
}

# Mapping for getLE sensor values (Leakage protection - Present level)
# Maps raw API value -> display value in liters (as shown in translations)
_SYR_CONNECT_SENSOR_LE_VALUE_MAP = {
    "2": "100", "3": "150", "4": "200", "5": "250", "6": "300",
    "7": "350", "8": "400", "9": "450", "10": "500", "11": "550",
    "12": "600", "13": "650", "14": "700", "15": "750", "16": "800",
    "17": "850", "18": "900", "19": "950", "20": "1000", "21": "1050",
    "22": "1100", "23": "1150", "24": "1200", "25": "1250", "26": "1300",
    "27": "1350", "28": "1400", "29": "1450", "30": "1500",
}

# getRPW: Days on which regeneration is allowed, stored as a bit mask.
#
# This maps a single-bit mask value to the corresponding weekday index
# (0 = Monday .. 6 = Sunday). A mask value of 0 indicates "no days configured"
# Example: mask 5 (0b0000101) means Monday (1<<0) and Wednesday (1<<2).
#
# Use this mapping to decode device `getRPW` bitmasks where each bit
# represents a weekday.
_SYR_CONNECT_SENSOR_RPW_VALUE_MAP = {
    0: None,    # No days configured
    1: 0,       # Monday
    2: 1,       # Tuesday
    4: 2,       # Wednesday
    8: 3,       # Thursday
    16: 4,      # Friday
    32: 5,      # Saturday
    64: 6,      # Sunday
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
}

# Mapping for getT1, getT2 sensor values (Time leakage)
# Maps raw API value -> display value in hours (as shown in translations)
_SYR_CONNECT_SENSOR_T1_VALUE_MAP = {
    "1": "0.5", "2": "1.0", "3": "1.5", "4": "2.0", "5": "2.5",
    "6": "3.0", "7": "3.5", "8": "4.0", "9": "4.5", "10": "5.0",
    "11": "5.5", "12": "6.0", "13": "6.5", "14": "7.0", "15": "7.5",
    "16": "8.0", "17": "8.5", "18": "9.0", "19": "9.5", "20": "10.0",
    "21": "10.5", "22": "11.0", "23": "11.5", "24": "12.0", "25": "12.5",
    "26": "13.0", "27": "13.5", "28": "14.0", "29": "14.5", "30": "15.0",
    "31": "15.5", "32": "16.0", "33": "16.5", "34": "17.0", "35": "17.5",
    "36": "18.0", "37": "18.5", "38": "19.0", "39": "19.5", "40": "20.0",
    "41": "20.5", "42": "21.0", "43": "21.5", "44": "22.0", "45": "22.5",
    "46": "23.0", "47": "23.5", "48": "24.0", "49": "24.5", "50": "25.0",
}

# Mapping for getUL sensor values (Leakage protection - Absent level)
# Maps raw API value -> display value in liters (as shown in translations)
_SYR_CONNECT_SENSOR_UL_VALUE_MAP = {
    "1": "10", "2": "20", "3": "30", "4": "40", "5": "50",
    "6": "60", "7": "70", "8": "80", "9": "90", "10": "100",
}

# Water hardness unit mapping (for getWHU)
# According to the SYR GUI, there are water hardness units "°dH" and "°fH" only.
_SYR_CONNECT_SENSOR_WHU_VALUE_MAP = {
    0: "°dH",       # German degree of water hardness (Grad deutsche Härte)
    1: "°fH",       # French degree of water hardness (degré français de dureté)
    2: "ppm",       # Parts per million (mg/L), common international unit
    3: "mmol/l",    # Millimoles per liter, SI unit for water hardness
}

# Sensor state classes (for Home Assistant) - internal
_SYR_CONNECT_SENSOR_STATE_CLASS = {
    "getAVO": SensorStateClass.MEASUREMENT,        # Current flow rate
    "getBAR": SensorStateClass.MEASUREMENT,        # Inlet pressure (mbar sensor), reported by Safe-T+
    "getBAT": SensorStateClass.MEASUREMENT,        # Battery voltage
    "getCEL": SensorStateClass.MEASUREMENT,        # Water temperature
    "getCOF": SensorStateClass.TOTAL_INCREASING,   # Total water consumption counter
    "getCYN": SensorStateClass.MEASUREMENT,        # Regeneration cycle number/time
    "getFLO": SensorStateClass.MEASUREMENT,        # Flow rate
    "getINR": SensorStateClass.TOTAL_INCREASING,   # Incomplete regenerations
    "getIWH": SensorStateClass.MEASUREMENT,        # Incoming water hardness
    "getNOR": SensorStateClass.TOTAL_INCREASING,   # Regenerations (normal operation)
    "getNPS": SensorStateClass.MEASUREMENT,        # Microleakage count
    "getOWH": SensorStateClass.MEASUREMENT,        # Outgoing water hardness
    "getPRS": SensorStateClass.MEASUREMENT,        # Inlet pressure, reported by LEXplus10SL
    "getRDO": SensorStateClass.MEASUREMENT,        # Salt dosing (g/L)
    "getRES": SensorStateClass.MEASUREMENT,        # Remaining capacity
    "getSS1": SensorStateClass.MEASUREMENT,        # Salt container supply 1 (weeks)
    "getSS2": SensorStateClass.MEASUREMENT,        # Salt container supply 2 (weeks)
    "getSS3": SensorStateClass.MEASUREMENT,        # Salt container supply 3 (weeks)
    "getSV1": SensorStateClass.MEASUREMENT,        # Salt container amount 1
    "getSV2": SensorStateClass.MEASUREMENT,        # Salt container amount 2
    "getSV3": SensorStateClass.MEASUREMENT,        # Salt container amount 3
    "getTMP": SensorStateClass.MEASUREMENT,        # Deactivate leakage protection for n seconds
    "getTOR": SensorStateClass.TOTAL_INCREASING,   # Total regenerations
    "getVOL": SensorStateClass.TOTAL_INCREASING,  # Total capacity (cumulative)
    "getVS1": SensorStateClass.MEASUREMENT,        # Volume threshold 1
    "getVS2": SensorStateClass.MEASUREMENT,        # Volume threshold 2
    "getVS3": SensorStateClass.MEASUREMENT,        # Volume threshold 3
}

# Sensors that should remain as strings (not converted to numbers) - internal
_SYR_CONNECT_SENSOR_STRING = {
    # Note: getBAT is handled specially - extracts first numeric value from space-separated string
    "getCNA",  # Device name
    "getDGW",  # Gateway
    "getDTT",  # Microleakage test time
    "getFIR",  # Firmware
    "getIPA",  # IP address
    "getMAC",  # MAC address
    "getMAN",  # Manufacturer
    "getRTI",  # Regeneration time
    "getRPW",  # Regeneration permitted weekdays as bit mask (handled specially to decode bitmask)
    "getSRN",  # Serial number
    "getVER",  # Version
    "getWFC",  # Wi-Fi SSID
    "getWHU",  # Water hardness unit
}

# Sensor units mapping (units are standardized and not translated) - internal
_SYR_CONNECT_SENSOR_UNIT = {
    # Sensors exits in devices:
    # - LEXplus10S
    # - LEXplus10SL

    # getIWH and getOWH units are set dynamically from getWHU
    "getAVO": UnitOfVolume.LITERS,                          # Current flow in Liters (e.g. "1655mL" -> 1.655 L)
    "getDWF": UnitOfVolume.LITERS,                          # Expected daily water consumption
    "getFLO": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,       # Flow rate
    "getFCO": "ppm",                                        # Iron content (parts per million)
    "getRES": UnitOfVolume.LITERS,                          # Remaining capacity
    "getRDO": f"{UnitOfMass.GRAMS}/{UnitOfVolume.LITERS}",  # Salt dosing (g/L)
    "getRPD": UnitOfTime.DAYS,                              # Regeneration interval
    "getRTH": UnitOfTime.HOURS,                             # Regeneration time (Hour)
    "getPRS": UnitOfPressure.BAR,                           # Pressure
    "getSV1": UnitOfMass.KILOGRAMS,                         # Salt container amount 1
    "getSV2": UnitOfMass.KILOGRAMS,                         # Salt container amount 2
    "getSV3": UnitOfMass.KILOGRAMS,                         # Salt container amount 3
    "getSS1": UnitOfTime.WEEKS,                             # Salt container supply 1
    "getSS2": UnitOfTime.WEEKS,                             # Salt container supply 2
    "getSS3": UnitOfTime.WEEKS,                             # Salt container supply 3
    "getVOL": UnitOfVolume.CUBIC_METERS,                    # Total capacity (m³)

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
    "getPR1": UnitOfTime.HOURS,                         # Return time to profile 1
    "getPR2": UnitOfTime.HOURS,                         # Return time to profile 2
    "getPR3": UnitOfTime.HOURS,                         # Return time to profile 3
    "getPR4": UnitOfTime.HOURS,                         # Return time to profile 4
    "getPR5": UnitOfTime.HOURS,                         # Return time to profile 5
    "getPR6": UnitOfTime.HOURS,                         # Return time to profile 6
    "getPR7": UnitOfTime.HOURS,                         # Return time to profile 7
    "getPR8": UnitOfTime.HOURS,                         # Return time to profile 8
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

    # Sensors exits in devices:
    # - Safe-T+

    "getBAR": UnitOfPressure.BAR,                       # Pressure (mbar sensor)
    "getBAT": UnitOfElectricPotential.VOLT,             # Battery voltage
    "getLE": UnitOfVolume.LITERS,                       # Leakage protection - Present level
    "getT1": UnitOfTime.HOURS,                          # Time leakage (mapped from 0.5h steps)
    "getT2": UnitOfTime.HOURS,                          # Time leakage (mapped from 0.5h steps)
    "getTMP": UnitOfTime.SECONDS,                       # Deactivate leakage protection for n seconds
    "getUL": UnitOfVolume.LITERS,                       # Leakage protection - Absent level

    # Sensors exits in devices:
    # - NeoSoft 2500

    "getLTV": UnitOfVolume.LITERS,                      # Last volume tapped
    "getRE1": UnitOfVolume.LITERS,                      # Reserve capacity bottle 1
    "getWFR": PERCENTAGE,                               # Wi-Fi signal strength 0-100%
    "getVPS1": UnitOfTime.SECONDS,                      # No turbine pulses Control head 1 since
    "getVPS2": UnitOfTime.SECONDS,                      # No turbine pulses Control head 2 since

    # Sensors exits in devices:
    # - NeoSoft 5000

    "getRE2": UnitOfVolume.LITERS,                      # Reserve capacity bottle 2^

    # Sensors exits in devices:
    # - Trio DFR/LS

    "getCND": UnitOfConductivity.MICROSIEMENS_PER_CM,   # Water conductivity (µS/cm)
    "getSLE": UnitOfTime.SECONDS,                       # Remaining time in seconds of an active self-learning phase
    "getSLF": UnitOfVolumeFlowRate.LITERS_PER_HOUR,     # Self-learning phase volume (l/h)
    "getSLT": UnitOfTime.SECONDS,                       # Time in self-learning phase (seconds)
    "getSLV": UnitOfVolume.LITERS,                      # Self-learning phase volume (l)
}

# Sensor display precision mapping (number of decimals to show)
# Use integers for whole-number display (0), or >0 for decimal places.
# This allows configuring how many decimals Home Assistant should show
# for specific sensors when the integration formats the value.
_SYR_CONNECT_SENSOR_UNIT_PRECISION = {
    "getAVO": 1,    # Current flow: show with 2 decimal places
    "getBAR": 1,    # Pressure (mbar sensor): show with 1 decimal places (e.g., 4.1 bar)
    "getBAT": 2,    # Battery voltage: show with 2 decimal places
    "getCEL": 1,    # Water temperature, e.g. 110 = 11.0°C
    "getCFO": 0,    # Cycle flow offset: show as whole number by default
    "getCND": 0,    # Conductivity in µS/cm: show as whole number by default
    "getCOF": 0,    # Total water consumption counter: show as whole number by default
    "getCS1": 0,    # Remaining resin capacity 1: show as whole number by default
    "getCS2": 0,    # Remaining resin capacity 2: show as whole number by default
    "getCS3": 0,    # Remaining resin capacity 3: show as whole number by default
    "getCYN": 0,    # Regeneration cycle counter: show as whole number by default
    "getDRP": 0,    # Microleakage test interval: show as whole number by default
    "getDSV": 0,    # Microleakage test: show as whole number by default
    "getDWF": 0,    # Expected daily water consumption: show as whole number by default
    "getFCO": 0,    # Iron content: show as whole number by default
    "getFLO": 0,    # Flow rate: show as whole number by default
    "getINR": 0,    # Incomplete regenerations: show as whole number by default
    "getIWH": 0,    # Incoming water hardness: show as whole number by default
    "getLAN": 0,    # Language of the UI: show as whole number by default (0=English, 1=German, 3=Spanish)
    "getLE": 0,     # Leakage protection - Present level: show as whole number by default
    "getLTV": 0,    # Last dispensed volume: show with 0 decimal place (e.g. 5 L)
    "getNOR": 0,    # Regenerations (normal operation): show as whole number by default
    "getNPS": 0,    # Microleakage count: show as whole number by default
    "getOWH": 0,    # Outgoing water hardness: show as whole number by default
    "getPRF": 0,    # Active leak protection profile
    "getPR1": 0,    # Return time to profile 1
    "getPR2": 0,    # Return time to profile 2
    "getPR3": 0,    # Return time to profile 3
    "getPR4": 0,    # Return time to profile 4
    "getPR5": 0,    # Return time to profile 5
    "getPR6": 0,    # Return time to profile 6
    "getPR7": 0,    # Return time to profile 7
    "getPR8": 0,    # Return time to profile 8
    "getPRS": 1,    # Pressure: show with 1 decimal place by default
    "getPST": 0,    # Pressure sensor installed: show as whole number by default
    "getRDO": 0,    # Salt dosing: show as whole number by default
    "getRMO": 0,    # Regeneration mode (1=Standard, 2=ECO, 3=Power, 4=Automatik)
    "getRPD": 0,    # Regeneration interval: show as whole days by default
    "getRE1": 0,    # Reserve capacity bottle 1: show as whole number by default
    "getRE2": 0,    # Reserve capacity bottle 2: show as whole number by default
    "getRES": 0,    # Remaining capacity: show as whole number by default
    "getRG1": 0,    # Regeneration 1: show as whole number by default
    "getRG2": 0,    # Regeneration 2: show as whole number by default
    "getRG3": 0,    # Regeneration 3: show as whole number by default
    "getSLE": 0,    # Remaining time in seconds of an active self-learning phase: show as whole number by default
    "getSLF": 0,    # Self-learning phase volume (l/h)
    "getSLT": 0,    # Time in self-learning phase (seconds)
    "getSLV": 0,    # Self-learning phase volume (l)
    "getSS1": 0,    # Salt container supply 1: show as whole number by default
    "getSS2": 0,    # Salt container supply 2: show as whole number by default
    "getSS3": 0,    # Salt container supply 3: show as whole number by default
    "getSV1": 0,    # Salt container volume 1: show as whole number by default
    "getSV2": 0,    # Salt container volume 2: show as whole number by default
    "getSV3": 0,    # Salt container volume 3: show as whole number by default
    "getTMP": 0,    # Deactivate leakage protection for n seconds: show as whole number by default
    "getTOR": 0,    # Total regenerations: show as whole number by default
    "getT1": 1,     # Time leakage: show with 1 decimal place (e.g., 1.5 hours) - mapped from 0.5h steps in API
    "getT2": 1,     # Time leakage: show with 1 decimal place (e.g., 1.5 hours) - mapped from 0.5h steps in API
    "getUL": 0,     # Leakage protection - Absent level: show as whole number by default
    "getVLV": 0,    # Valve status (10=closed, 11=closing, 20=open, 21=opening): show as whole number by default
    "getVPS1": 0,   # No turbine pulses on control head 1 since: show as whole number of seconds by default
    "getVPS2": 0,   # No turbine pulses on control head 2 since: show as whole number of seconds by default
    "getVOL": 3,    # Total water volume: show in cubic meters (m³) with 3 decimals by default
    "getWFR": 0,    # Wi-Fi signal strength: show as whole number by default
    "getWFS": 0,    # Wi-Fi connection status

    # Leak protection numeric precisions (integers)
    "getPF1": 0, "getPF2": 0, "getPF3": 0, "getPF4": 0, "getPF5": 0, "getPF6": 0, "getPF7": 0, "getPF8": 0,
    "getPT1": 0, "getPT2": 0, "getPT3": 0, "getPT4": 0, "getPT5": 0, "getPT6": 0, "getPT7": 0, "getPT8": 0,
    "getPV1": 0, "getPV2": 0, "getPV3": 0, "getPV4": 0, "getPV5": 0, "getPV6": 0, "getPV7": 0, "getPV8": 0,
}
