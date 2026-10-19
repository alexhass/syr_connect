"""Constants for the SYR Connect integration."""

# Configuration URL for device info

from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
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
from homeassistant.helpers.entity import EntityCategory

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

# Cloud API service registry
#
# Each entry represents one distinct backend service.
# - api_app_name: Required. The app name sent in the API login request. Must match the expected value for the service,
#   otherwise login will fail.
# - api_base_url: Required. Base URL for API endpoints (e.g. login, device status) - used to construct full API URLs.
# - cf_bundle_identifier: The Core Foundation bundle identifier of the official app - used as unique key for service
#   registry.
# - configuration_url: User-facing URL displayed in the HA device info card (may differ from api_base_url).
# - display_name: Human-friendly name for the service - used in HA integration UI for configuration.
#
# Note: The value of "api_app_name" and "api_base_url" are hard bound to each other. These need to be used together or
# the api login fails. cf_bundle_identifier is not validated on server side, but should be used to emulate the mobile app.
_SYR_CONNECT_API_SERVICES: dict[str, dict] = {
    "de.consoft.syr.connect": {
        "api_app_name": "SYR Connect",
        "api_base_url": "https://syrconnect.de/",
        "cf_bundle_identifier": "de.consoft.syr.connect",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "SYR Connect",
    },
    "de.consoft.gc.conel.connect": {
        "api_app_name": "CLEAR PRO",
        "api_base_url": "https://api.conelclearpro.de/",
        "cf_bundle_identifier": "de.consoft.gc.conel.connect",
        "configuration_url": "https://conelclearpro.de/",
        "display_name": "CONEL CLEAR PRO",
    },
    "de.consoft.gsh.comfort.connect": {
        "api_app_name": "comfort CONNECT",
        "api_base_url": "https://syrconnect.de/",
        "cf_bundle_identifier": "de.consoft.gsh.comfort.connect",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Sanibel comfort CONNECT",
    },
    "de.consoft.isg.concept.connect": {
        "api_app_name": "concept CONNECT",
        "api_base_url": "https://syrconnect.de/",
        "cf_bundle_identifier": "de.consoft.isg.concept.connect",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "concept CONNECT",
    },
    "de.consoft.sanitaerunion.ditech.connect": {
        "api_app_name": "DITECH Geräte",
        "api_base_url": "https://syrconnect.de/",
        "cf_bundle_identifier": "de.consoft.sanitaerunion.ditech.connect",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "DITECH Haustechnik",
    },
    "de.consoft.isg.optima.connect": {
        "api_app_name": "optima CONNECT",
        "api_base_url": "https://syrconnect.de/",
        "cf_bundle_identifier": "de.consoft.isg.optima.connect",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Optima CONNECT",
    },
    "de.consoft.rwc.connect": {
        "api_app_name": "RwcMultisafe",
        "api_base_url": "https://rwcmultisafe.com/",
        "cf_bundle_identifier": "de.consoft.rwc.connect",
        "configuration_url": "https://rwcmultisafe.com/",
        "display_name": "RWC MultiSafe",
    },
    "de.consoft.polygonvatro.connect": {
        "api_app_name": "POLYGONVATRO Connect",
        "api_base_url": "https://polygonvatro-connect.de/",
        "cf_bundle_identifier": "de.consoft.polygonvatro.connect",
        "configuration_url": "https://polygonvatro-connect.de/",
        "display_name": "POLYGONVATRO Connect",
    },
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

# Alarm codes for SafeFloor devices (raw API getALA -> internal translation key)
# Original casing in API is "A0x0000", but we normalize it for get_sensor_ala_map() lookups.
# Codes are hexadecimal bitmask values (0x0002, 0x0004, ..., 0x0100).
_SYR_CONNECT_SENSOR_ALA_CODES_SAFEFLOOR = {
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

# Alarm code mappings per device model (raw API getALA -> internal translation key)
# These are used to map device-specific alarm codes to internal translation keys.
_SYR_CONNECT_SENSOR_ALA_CODES_LEX = {
    "0": "no_alarm",
    "LOWSALT": "alarm_salt_supply_empty",
    "NOSALT": "alarm_salt_supply_empty",
    "1": "alarm_salt_supply_empty",
    "2": "alarm_chlor_generator_fault",
    "3": "alarm_valve_malfunction",
    "4": "alarm_pressure_too_low",
    "5": "alarm_pressure_too_high",
    "6": "alarm_brine_level_low",
    "7": "alarm_brine_level_high",
    "11": "alarm_end_switch",
    "12": "alarm_no_network_connection",
    "13": "alarm_leakage_volume_reached",
    "14": "alarm_leakage_time_reached",
    "15": "alarm_max_flow_rate_reached",
    "16": "alarm_microleakage_detected",
    "17": "alarm_external_sensor_leakage_radio",
    "18": "alarm_turbine_blocked",
    "19": "alarm_pressure_sensor_faulty",
    "20": "alarm_temperature_sensor_faulty",
    "21": "fault_conductance_sensor",
    "23": "alarm_leakage_volume_approaching",
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

_SYR_CONNECT_SENSOR_ALA_CODES_SAFET = {
    "A0": "alarm_safet_microleakage_detected",
    "A1": "alarm_safet_valve_cannot_be_operated",
    "A2": "alarm_safet_turbine_no_signal",
    "A3": "alarm_safet_leakage_volume_reached",
    "A4": "alarm_safet_flow_leakage_detected",
    "A5": "alarm_safet_absence_leakage_detected",
    "A6": "alarm_safefloor_flood",
    "A7": "alarm_external_sensor_leakage_radio",
    "A8": "alarm_external_sensor_leakage_cable",
    "A9": "alarm_safet_flow_time_exceeded",
    "AA": "alarm_temperature_sensor_faulty",
    "AB": "alarm_battery_weak",
    "AE": "error_no_information",
    "FF": "no_alarm",
    "LOWBAT": "alarm_battery_low",
    "WEAKBAT": "alarm_battery_weak",
}

# Model-specific alarm code families, keyed by a signature's `device_file` (see models.py), or by its
# `name` when it has no `device_file`. Every model not listed here uses _SYR_CONNECT_SENSOR_ALA_CODES_GENERIC.
_SYR_CONNECT_SENSOR_ALA_CODES_BY_MODEL = {
    "lex": _SYR_CONNECT_SENSOR_ALA_CODES_LEX,
    "lexplus10s": _SYR_CONNECT_SENSOR_ALA_CODES_LEX,
    "lexplus10sl": _SYR_CONNECT_SENSOR_ALA_CODES_LEX,
    "safefloor": _SYR_CONNECT_SENSOR_ALA_CODES_SAFEFLOOR,
    "safetplus": _SYR_CONNECT_SENSOR_ALA_CODES_SAFET,
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

# Binary sensors mapping with their device classes - internal
_SYR_CONNECT_SENSOR_BINARY = {
    "getBUZ": BinarySensorDeviceClass.POWER,  # Buzzer on/off
}


@dataclass(frozen=True, kw_only=True)
class SyrConnectSensorEntityDescription(SensorEntityDescription):
    """Describes a SYR Connect sensor; `key` is the status key (e.g. "getFLO")."""

    # Return the value as string instead of converting it to a number (version, serial, MAC, ...)
    keep_as_string: bool = False


# Descriptions of all known sensor keys.
#
# Only API keys listed here will become sensor entities. Any key returned by
# a firmware update that is not listed here is silently ignored.
_SYR_CONNECT_SENSOR_TYPES: tuple[SyrConnectSensorEntityDescription, ...] = (
    # --- Connectivity (virtual, always created) ---
    SyrConnectSensorEntityDescription(
        key="dst",  # Device connection state (0=never online, 1=offline, 2=online, 3=standby)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Valve & Flow ---
    SyrConnectSensorEntityDescription(
        key="getAB",  # Valve shutoff state (open / closed)
    ),
    SyrConnectSensorEntityDescription(
        key="getAVO",  # Current instantaneous flow rate
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=1,
    ),
    SyrConnectSensorEntityDescription(
        key="getFLO",  # Water flow rate (l/h)
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getVLV",  # Valve position (10=closed, 11=closing, 20=open, 21=opening)
        suggested_display_precision=0,
    ),
    # getCFO is not listed: Cycle flow offset
    # Its previous settings: suggested_display_precision=0.
    # --- Alarm / Notification / Warning ---
    SyrConnectSensorEntityDescription(
        key="getALA",  # Current alarm code
    ),
    SyrConnectSensorEntityDescription(
        key="getALM",  # List of last alarms (e.g. low salt level)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getALN",  # List of last 8 notifications
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getALW",  # List of last 8 warnings
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getNOT",  # Current notification code
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getWRN",  # Current warning code
    ),
    # --- Pressure ---
    SyrConnectSensorEntityDescription(
        key="getBAR",  # Inlet pressure - mbar sensor (Safe-T+)
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
    ),
    SyrConnectSensorEntityDescription(
        key="getBAR2",  # Outlet pressure - mbar sensor (SYR TRIO Lock Connect)
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
    ),
    SyrConnectSensorEntityDescription(
        key="getPRS",  # Inlet pressure - bar sensor (LEXplus10SL)
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
    ),
    # --- Voltage / Battery ---
    SyrConnectSensorEntityDescription(
        key="getBAP",  # Battery level (%)
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getBAT",  # Battery voltage (V) or battery level (%) - unit depends on device type
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
    ),
    SyrConnectSensorEntityDescription(
        key="getNET",  # Mains (AC) voltage (V)
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
    ),
    # --- Water Quality ---
    SyrConnectSensorEntityDescription(
        key="getCEL",  # Temperature (°C)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    SyrConnectSensorEntityDescription(
        key="getCFT",  # Current filling duration (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getCND",  # Water conductivity (µS/cm)
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getCFV",  # Current filling volume (l)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getHMD",  # Ambient humidity (%)
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getIWH",  # Incoming (raw) water hardness
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getOWH",  # Outgoing (softened) water hardness
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWHU",  # Water hardness unit (°dH / °fH / ppm / mmol/l)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        keep_as_string=True,
    ),
    # --- Water Consumption & Volume ---
    SyrConnectSensorEntityDescription(
        key="getCOF",  # Total water consumption counter (l)
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getLTV",  # Last dispensed (tapped) volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getVOL",  # Total volume (m³)
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=3,
    ),
    # --- Device Status ---
    SyrConnectSensorEntityDescription(
        key="getDEN",  # Device enabled flag
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getDFM",  # Device feature mode (device function type)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getSTA",  # Device operating status
    ),
    # --- Resin Capacity ---
    SyrConnectSensorEntityDescription(
        key="getCS1",  # Remaining resin capacity - tank 1 (%)
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getCS2",  # Remaining resin capacity - tank 2 (%)
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getCS3",  # Remaining resin capacity - tank 3 (%)
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    # --- Salt ---
    SyrConnectSensorEntityDescription(
        key="getRDO",  # Salt dosing (g/l)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{UnitOfMass.GRAMS}/{UnitOfVolume.LITERS}",
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRE1",  # Reserve capacity - bottle 1 (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getRE2",  # Reserve capacity - bottle 2 (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getRES",  # Remaining softening capacity (l)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getSS1",  # Salt supply - container 1 (weeks)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.WEEKS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getSS2",  # Salt supply - container 2 (weeks)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.WEEKS,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getSS3",  # Salt supply - container 3 (weeks)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.WEEKS,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getSV1",  # Salt amount - container 1 (kg)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=0,
    ),
    SyrConnectSensorEntityDescription(
        key="getSV2",  # Salt amount - container 2 (kg)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getSV3",  # Salt amount - container 3 (kg)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    # --- Regeneration ---
    SyrConnectSensorEntityDescription(
        key="getCYN",  # Regeneration cycle counter
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getCYT",  # Regeneration cycle time (remaining)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getINR",  # Incomplete regeneration count
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getLAR",  # Timestamp of last regeneration
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getNOR",  # Regeneration count (normal operation)
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRG1",  # Regeneration status (which tank is regenerating)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRG2",  # Regeneration running - tank 2 flag
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getRG3",  # Regeneration running - tank 3 flag
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getRMO",  # Regeneration mode (Standard / ECO / Power / Automatic)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRPD",  # Regeneration interval (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getRPW",  # Regeneration permitted weekdays (bitmask)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getRTH",  # Regeneration scheduled hour
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRTI",  # Total regeneration cycle duration
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getRTM",  # Regeneration time (combined HH:MM string)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSCR",  # Service regeneration cycle count
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # getSRE is not listed: Regeneration active flag - Disabled - Not clear what value 3/5 means.
    # Its previous settings: suggested_display_precision=0, entity_category=DIAGNOSTIC,
    # entity_registry_enabled_default=False.
    SyrConnectSensorEntityDescription(
        key="getTOR",  # Total regeneration count (all time)
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Self-Learning Phase (Trio DFR/LS) ---
    SyrConnectSensorEntityDescription(
        key="getSLE",  # Remaining time in active self-learning phase (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSLF",  # Flow rate during self-learning phase (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSLP",  # Duration of self-learning phase
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSLT",  # Elapsed time in self-learning phase (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSLV",  # Volume accumulated in self-learning phase (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Microleakage Test (Trio DFR/LS, SafeTech) ---
    SyrConnectSensorEntityDescription(
        key="getDBD",  # Microleakage test pressure drop
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getDMA",  # Microleakage alarm mode (1=Warning, 2=Alarm)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getDRP",  # Microleakage test interval (daily / weekly / monthly)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getDSV",  # Microleakage test status (inactive / active / aborted / skipped)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getDTT",  # Microleakage test duration / time
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getNPS",  # No turbine pulses since (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Leak Protection (LEXplus10SL / Trio DFR/LS) ---
    SyrConnectSensorEntityDescription(
        key="getLE",  # Leak protection volume limit - present profile (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getT1",  # Max. flow duration - present profile (h, 0.5 h steps)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getT2",  # Max. flow duration - absent profile (h, 0.5 h steps)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getTMP",  # Leak protection temporarily deactivated - remaining time (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getUL",  # Leak protection volume limit - absent profile (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Leak Protection Profiles 1-8 (LEXplus10SL) ---
    SyrConnectSensorEntityDescription(
        key="getPA1",  # Profile 1 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA2",  # Profile 2 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA3",  # Profile 3 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA4",  # Profile 4 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA5",  # Profile 5 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA6",  # Profile 6 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA7",  # Profile 7 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPA8",  # Profile 8 active flag (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB1",  # Profile 1 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB2",  # Profile 2 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB3",  # Profile 3 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB4",  # Profile 4 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB5",  # Profile 5 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB6",  # Profile 6 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB7",  # Profile 7 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPB8",  # Profile 8 buzzer alert (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF1",  # Profile 1 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF2",  # Profile 2 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF3",  # Profile 3 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF4",  # Profile 4 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF5",  # Profile 5 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF6",  # Profile 6 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF7",  # Profile 7 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPF8",  # Profile 8 flow leak threshold (l/h)
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM1",  # Profile 1 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM2",  # Profile 2 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM3",  # Profile 3 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM4",  # Profile 4 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM5",  # Profile 5 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM6",  # Profile 6 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM7",  # Profile 7 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPM8",  # Profile 8 microleakage test enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN1",  # Profile 1 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN2",  # Profile 2 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN3",  # Profile 3 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN4",  # Profile 4 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN5",  # Profile 5 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN6",  # Profile 6 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN7",  # Profile 7 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPN8",  # Profile 8 name
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR1",  # Profile 1 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR2",  # Profile 2 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR3",  # Profile 3 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR4",  # Profile 4 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR5",  # Profile 5 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR6",  # Profile 6 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR7",  # Profile 7 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPR8",  # Profile 8 return time to present profile (h)
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT1",  # Profile 1 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT2",  # Profile 2 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT3",  # Profile 3 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT4",  # Profile 4 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT5",  # Profile 5 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT6",  # Profile 6 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT7",  # Profile 7 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPT8",  # Profile 8 max. leak duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV1",  # Profile 1 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV2",  # Profile 2 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV3",  # Profile 3 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV4",  # Profile 4 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV5",  # Profile 5 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV6",  # Profile 6 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV7",  # Profile 7 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPV8",  # Profile 8 max. leak volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW1",  # Profile 1 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW2",  # Profile 2 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW3",  # Profile 3 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW4",  # Profile 4 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW5",  # Profile 5 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW6",  # Profile 6 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW7",  # Profile 7 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPW8",  # Profile 8 leak warning enabled (true/false)
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getPRF",  # Currently active leak protection profile index
        suggested_display_precision=0,
    ),
    # getPRN is not listed: Duplicate of getPRF
    # Its previous settings: entity_registry_enabled_default=False.
    SyrConnectSensorEntityDescription(
        key="getPST",  # Pressure sensor installed (1=not available, 2=available)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # --- Filter (NeoSoft) ---
    # getFCD is not listed: Filter flush interval (Disabled Issue #23)
    # Its previous settings: suggested_display_precision=0, entity_category=DIAGNOSTIC.
    SyrConnectSensorEntityDescription(
        key="getFCO",  # Iron content (ppm)
        native_unit_of_measurement="ppm",
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getFFM",  # Filter type (backwash / replaceable / none)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Alarm / Thresholds (SafeFloor) ---
    SyrConnectSensorEntityDescription(
        key="getALD",  # Duration of alarm (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMIH",  # Minimum humidity threshold (%)
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMXH",  # Maximum humidity threshold (%)
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMIT",  # Minimum temperature threshold (1/10 °C)
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMXT",  # Maximum temperature threshold (1/10 °C)
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Intervals ---
    SyrConnectSensorEntityDescription(
        key="getRCP",  # Synchronisation interval (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWMP",  # Measurement interval (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Maintenance ---
    SyrConnectSensorEntityDescription(
        key="getDWF",  # Expected daily water consumption (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getSRH",  # Next semi-annual maintenance (timestamp)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getSRV",  # Next annual maintenance (timestamp)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getVS1",  # Volume threshold 1 (l)
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getVS2",  # Volume threshold 2 (l)
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getVS3",  # Volume threshold 3 (l)
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # --- Automatic Backwash (RSA) ---
    SyrConnectSensorEntityDescription(
        key="getCOA",  # Counter of automatic backwashes
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getCOM",  # Counter of manual backwashes
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRSA",  # Backwash interval (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRSD",  # Backwash duration (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRSE",  # Backwash reminder interval (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Lock / Connection Centre (TRIO Lock, SafeTech Lock, AC 3200, AC 3228) ---
    SyrConnectSensorEntityDescription(
        key="getLFT",  # Last refill duration (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getLFV",  # Last refilled volume (l)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getNMS",  # No valve movement since (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getNMT",  # Time until valve self-test becomes active (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getNPT",  # Time until alarm A8 "flow sensor fault" becomes active (days)
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getNRT",  # No refill since (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getTRT",  # Cumulative refill time (s)
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getTRV",  # Cumulative refilled volume (l)
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Display ---
    SyrConnectSensorEntityDescription(
        key="getSRO",  # Display rotation / orientation (0 / 90 / 180 / 270 degrees)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # --- Device Info & Diagnostics ---
    SyrConnectSensorEntityDescription(
        key="getCDE",  # Configuration code
    ),
    SyrConnectSensorEntityDescription(
        key="getCNA",  # Device name
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getDGW",  # Gateway IP address
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getEGW",  # Ethernet (LAN) gateway
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getEIP",  # Ethernet (LAN) IP address
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getFIR",  # Firmware model identifier
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getIPA",  # IP address
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getLAN",  # Device language (0=English, 1=German, 3=Spanish) - Lex10 models only
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getLNG",  # Device language (0=Deutsch, 1=English) - other models
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getMAC",  # MAC address
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getMAC1",  # Wi-Fi MAC address
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMAC2",  # LAN MAC address
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getMAN",  # Manufacturer name
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getSRN",  # Device serial number
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getTYP",  # Device type code
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getVER",  # Firmware version string
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    # --- Turbine / Pulse Monitoring (NeoSoft) ---
    SyrConnectSensorEntityDescription(
        key="getVPS1",  # No turbine pulses on control head 1 since (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSensorEntityDescription(
        key="getVPS2",  # No turbine pulses on control head 2 since (s)
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # --- Wi-Fi ---
    SyrConnectSensorEntityDescription(
        key="getAPT",  # Access point timeout (s)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWFC",  # Wi-Fi SSID
        entity_category=EntityCategory.DIAGNOSTIC,
        keep_as_string=True,
    ),
    SyrConnectSensorEntityDescription(
        key="getWFL",  # Nearby Wi-Fi networks with signal strength
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWFR",  # Wi-Fi signal strength (%)
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWFS",  # Wi-Fi connection status (not connected / connecting / connected)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWGW",  # Wi-Fi gateway
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getWIP",  # Wi-Fi IP address
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Water treatment / Filling (Conel Clear Pro Fill) ---
    SyrConnectSensorEntityDescription(
        key="getCRS",  # Cartridge size (raw 1-5, mapped to liters)
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getCRT",  # Cartridge type (0=HWE, 1=HVE, 2=HVE+)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getLOT",  # Maximum output conductivity (raw x10 µS/cm)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getLRC",  # Liter(s) remaining softening capacity
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getOHW",  # Soft water hardness (°dH)
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°dH",
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getPRC",  # Percent remaining softening capacity
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRCC",  # Number of filling cycles in the current period (AC 3200, AC 3228)
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRCD",  # Filling processes period (0=hour, 1=day, 2=week, 3=month)
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRCN",  # Counter of all refills (AC 3200, AC 3228)
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRMN",  # Filling processes count
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRMT",  # Maximum filling duration (min)
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getRVT",  # Maximum filling charges
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectSensorEntityDescription(
        key="getTPR",  # Target pressure (1/10 bar)
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

_SYR_CONNECT_SENSOR_DESCRIPTIONS: dict[str, SyrConnectSensorEntityDescription] = {
    description.key: description for description in _SYR_CONNECT_SENSOR_TYPES
}

# Allowlist of known sensor keys, the global fallback for get_model_known_keys()
_SYR_CONNECT_SENSOR_KNOWN_KEYS = set(_SYR_CONNECT_SENSOR_DESCRIPTIONS)


# Configuration sensors - settings users do not need for daily use
_SYR_CONNECT_SENSOR_CONFIG = {
    "getBUZ",  # Buzzer on/off - also represented as switch entity
    "getRPD",  # Regeneration interval - also represented as select entity
    "getRMO",  # Regeneration mode - also represented as select entity
    "getRTM",  # Regeneration time (minutes or combined) - represented as select entity
    "getSRO",  # Display rotation - also represented as select entity
    "getSV1",
    "getSV2",
    "getSV3",  # Salt amount (kg) - also represented as select entity
    "getFCD",  # Filter change
    "getFFM",  # Filter fouling level
    # --- Water treatment / Filling (Conel Clear Pro Fill) - also represented as select entity ---
    "getCRS",  # Cartridge size (raw 1-5, mapped to liters)
    "getCRT",  # Cartridge type (0=HWE, 1=HVE, 2=HVE+)
    "getLOT",  # Maximum output conductivity (raw x10 µS/cm) - only when getCRT is HVE/HVE+
    "getOHW",  # Soft water hardness (°dH) - only when getCRT is HWE
    "getRCD",  # Filling processes period (0=hour, 1=day, 2=week, 3=month)
    "getRMN",  # Filling processes count
    "getRMT",  # Maximum filling duration (min)
    "getRVT",  # Maximum filling charges
    "getTPR",  # Target pressure (1/10 bar)
    "getDFI",  # Filling mode enabled flag - also represented as switch entity
    # --- Automatic Backwash (RSA) - also represented as switch entity ---
    "getSSA",  # Automatic backwash enabled flag
    "getSSE",  # Backwash reminder enabled flag
    # --- Water hardness (plain LEX family only) - also represented as select entity ---
    "getIWH",  # Raw water hardness (1-100)
    "getOWH",  # Outlet (soft) water hardness (0-100)
    # --- SafeFloor Thresholds / Intervals - also represented as select entity ---
    "getALD",  # Duration of alarm (s)
    "getMIH",  # Minimum humidity threshold (%)
    "getMXH",  # Maximum humidity threshold (%)
    "getMIT",  # Minimum temperature threshold (1/10 °C)
    "getMXT",  # Maximum temperature threshold (1/10 °C)
    "getRCP",  # Synchronisation interval (s)
    "getWMP",  # Measurement interval (s)
}

# Known keys for the select platform — used by registry_cleanup to remove stale entries.
_SYR_CONNECT_SELECT_KNOWN_KEYS = {
    "getRTM",  # Regeneration time (HH:MM combined or minutes)
    "getPRF",  # Active leak-protection profile
    "getSRO",  # Display rotation (0 / 90 / 180 / 270 °)
    # "getFCD",   # Filter backwash interval
    "getSV1",  # Salt amount container 1
    "getSV2",  # Salt amount container 2
    "getSV3",  # Salt amount container 3
    "getRPD",  # Regeneration interval (days)
    "getFFM",  # Filter type (1..3)
    "getRMO",  # Regeneration mode (Standard / ECO / Power / Automatic)
    # --- Water treatment / Filling (Conel Clear Pro Fill) ---
    "getCRS",  # Cartridge size (raw 1-5, mapped to liters)
    "getCRT",  # Cartridge type (0=HWE, 1=HVE, 2=HVE+)
    "getLOT",  # Maximum output conductivity (raw x10 µS/cm) - only when getCRT is HVE/HVE+
    "getOHW",  # Soft water hardness (°dH) - only when getCRT is HWE
    "getRCD",  # Filling processes period (0=hour, 1=day, 2=week, 3=month)
    "getRMN",  # Filling processes count
    "getRMT",  # Maximum filling duration (min)
    "getRVT",  # Maximum filling charges
    "getTPR",  # Target pressure (1/10 bar)
}

# Known keys for the binary_sensor platform — used by registry_cleanup to remove stale entries.
_SYR_CONNECT_BINARY_SENSOR_KNOWN_KEYS = {
    "getBUZ",  # Buzzer on/off
}

# Known keys for the valve platform — used by registry_cleanup to remove stale entries.
_SYR_CONNECT_VALVE_KNOWN_KEYS = {
    "getAB",  # Valve shutoff control / state
}

# Known keys for the switch platform — used by registry_cleanup to remove stale entries.
_SYR_CONNECT_SWITCH_KNOWN_KEYS = {
    "getBUZ",  # Buzzer on/off
    "getDFI",  # Filling mode enabled flag (Conel Clear Pro Fill)
    "getSSA",  # Automatic backwash enabled flag (RSA)
    "getSSE",  # Backwash reminder enabled flag (RSA)
}

# Known keys for the button platform — used by registry_cleanup to remove stale entries.
_SYR_CONNECT_BUTTON_KNOWN_KEYS = {
    "setSIR",  # Trigger manual regeneration
    "setALA",  # Reset alarm
    "setDEX",  # Start microleakage test
    "setNOT",  # Reset notification
    "setWRN",  # Reset warning
}

# Known keys for the update platform — used by registry_cleanup to remove stale entries.
_SYR_CONNECT_UPDATE_KNOWN_KEYS = {
    "getNOT",  # Notification code; "01" == new_software_available
}

# Sensors to always exclude — parameters returned by the API that must not be
# exposed as sensor entities. Only keys that also appear in
# _SYR_CONNECT_SENSOR_KNOWN_KEYS need to be listed here; all others are already
# silently filtered by the KNOWN_KEYS allowlist.
_SYR_CONNECT_SENSOR_EXCLUDED = {
    # Keys that are in KNOWN_KEYS but must not become sensor entities because
    # they are handled by another entity type, superseded by a derived entity,
    # or have no practical value for users.
    # --- Overridden by a different entity type ---
    "getDEN",  # Boolean flag — handled as binary_sensor; no regular sensor needed
    # --- Superseded by a derived / combined entity ---
    "getRTH",  # Regeneration hour — combined HH:MM representation handled by getRTM
    # --- Always zero / constant / no practical user value ---
    "getFCO",  # Iron content — always 0, not useful
    "getRTI",  # Regeneration cycle duration — always "00:00", no useful value
    # --- Deliberately suppressed despite being in KNOWN_KEYS ---
    "getCDE",  # Configuration code — opaque device identifier, not useful for users
    "getSCR",  # Service regeneration cycle count — function unclear
    "getDWF",  # Expected daily water consumption — internal regeneration-trigger threshold
    "getSLP",  # Self-learning phase duration — technical value without context
    "getWFL",  # Nearby Wi-Fi networks — complex formatted string, not suitable as sensor
}

# Sensors to exclude only when value is empty (0 or "") - internal
_SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_VALUE = {
    "getCS1",
    "getCS2",
    "getCS3",  # Remaining resin capacity (percent)
    "getVS1",
    "getVS2",
    "getVS3",  # Volume thresholds
    "getTYP",  # Device type code - value "" means sensor does not exists, type "0" may not exists.
    # Sensors exits in devices only:
    # - NeoSoft 2500 / 5000
    "getCYT",  # Regeneration cycle time - value "0" means no active regeneration, should be "00:00" to show a time.
    "getLAR",  # Last regeneration (timestamp) - if 0 means no regeneration has happened yet, so not useful to show.
    "getWFR",  # Wi-Fi frequency - "0": "Not connected"
    # Sensors exits in devices only:
    # - NeoSoft 5000
    # NOT TESTED
    # RPD and RTM have no influence on the NeoSoft 5000, as this system initiates regeneration automatically as soon
    # as a pillar is exhausted. Softened water is available at all times.
    # "getRPD",   # Regeneration interval (days) - value "0" means no interval configured.
    # "getRTM",   # Regeneration time (minutes) - value "0" means no active regeneration, should be "00:00" to show a time.
    # Sensors exits in devices only:
    # - Trio DFR/LS
    "getCND",  # Conductivity in µS/cm - value "" means sensor does not exists or not measured.
}

# Sensors to exclude only when value is empty string ("") - internal
_SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_STRING = {
    # Sensors exits in devices only:
    # - LEXplus10SL
    # - Safe-T+
    # - NeoSoft 2500 / 5000
    # - SafeFloor
    "getALD",  # Duration of alarm (s) - value "" means sensor is broken, should be "0" to show 0s.
    "getCEL",  # Temperature - value "" means sensor does not exists or not measured.
    "getLAN",  # Device language (0=English, 1=German, 3=Spanish)
    "getLNG",  # Device language (0=Deutsch, 1=English)
    "getNPS",  # No turbine pulses since (s) - value "" means sensor does not exist.
    # Sensors exits in devices only:
    # - NeoSoft 2500 / 5000
    "getBAR",  # Pressure at inlet - value "" means sensor does not exists or not measured
    "getVPS1",  # No turbine pulses on control head 1 since (s). Value "" means sensor does not exist.
    "getVPS2",  # No turbine pulses on control head 2 since (s). Value "" means sensor does not exist.
    "getWFC",  # Wi-Fi channel
    # Sensors exits in devices only:
    # - SafeTech Plus
    "getTMP",  # Leakage protection deactivated - value "" means sensor does not exists.
    # Sensors exits in devices only:
    # - Trio DFR/LS
    "getSRV",  # Next annual maintenance (timestamp) - if "" means no maintenance required, so not useful to show.
    # Sensors exits in devices:
    # - Safe-T+, Safe-Tech+, Trio DFR/LS
    "getNET",  # Mains voltage - value "" means no mains voltage sensor present.
}

# Sensors to exclude only when value is empty ip ("" or "0.0.0.0") - internal
_SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_IPADDRESS = {
    "getEGW",  # Ethernet gateway
    "getEIP",  # Ethernet IP address
    "getWGW",  # Wi-Fi gateway
    "getWIP",  # Wi-Fi IP address
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
