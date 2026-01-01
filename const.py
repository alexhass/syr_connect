"""Constants for the SYR Connect integration."""

DOMAIN = "syr_connect"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60  # seconds

# API URLs
API_BASE_URL = "https://syrconnect.de/WebServices"
API_LOGIN_URL = f"{API_BASE_URL}/Api/SyrApiService.svc/REST/GetProjects"
API_DEVICE_LIST_URL = f"{API_BASE_URL}/SyrControlWebServiceTest2.asmx/GetProjectDeviceCollections"
API_DEVICE_STATUS_URL = f"{API_BASE_URL}/SyrControlWebServiceTest2.asmx/GetDeviceCollectionStatus"
API_SET_STATUS_URL = f"{API_BASE_URL}/SyrControlWebServiceTest2.asmx/SetDeviceCollectionStatus"
API_STATISTICS_URL = f"{API_BASE_URL}/SyrControlWebServiceTest2.asmx/GetLexPlusStatistics"

# Encryption keys (from original adapter)
ENCRYPTION_KEY = "d805a5c409dc354b6ccf03a2c29a5825851cf31979abf526ede72570c52cf954"
ENCRYPTION_IV = "408a42beb8a1cefad990098584ed51a5"

# Checksum keys
CHECKSUM_KEY1 = "L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP"
CHECKSUM_KEY2 = "KHGK5X29LVNZU56T"

# Device info
APP_VERSION = "App-3.7.10-de-DE-iOS-iPhone-15.8.3-de.consoft.syr.connect"
USER_AGENT = "SYR/400 CFNetwork/1335.0.3.4 Darwin/21.6.0"

# Sensor device classes (for Home Assistant)
SENSOR_DEVICE_CLASS = {
    "getPRS": "pressure",
    "getFLO": "volume_flow_rate",
}

# Sensor state classes (for Home Assistant)
SENSOR_STATE_CLASS = {
    "getRES": "measurement",
    "getTOR": "measurement",
    "getPRS": "measurement",
    "getFLO": "measurement",
    "getFCO": "total_increasing",
    "getNOR": "total_increasing",
}

# Sensors that should remain as strings (not converted to numbers)
STRING_SENSORS = {
    "getVER",  # Version
    "getFIR",  # Firmware
    "getSRN",  # Serial number
    "getCNA",  # Device name
    "getMAN",  # Manufacturer
    "getMAC",  # MAC Address
    "getIPA",  # IP Address
    "getDGW",  # Gateway
    "getRTI",  # Regeneration time (combined from getRTH and getRTM)
    "getSRE",  # Regeneration active (boolean displayed as Ein/Aus)
    "getPST",  # Operating state (boolean displayed as Ein/Aus)
    "getSCR",  # Screen lock (boolean displayed as Ein/Aus)
    "getALM",  # Alarm (boolean displayed as Ein/Aus)
    "getWHU",  # Water hardness unit (mapped to unit names)
}

# Sensor icons (Material Design Icons)
SENSOR_ICONS = {
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
