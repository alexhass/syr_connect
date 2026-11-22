"""Asynchronous client library for SYR Connect water treatment and leak protection devices.

It talks to the SYR Connect cloud (XML API) and to the local API of the devices (JSON
API). The caller passes an aiohttp.ClientSession, the User-Agent and, for the cloud, the
locale and the time zone.

Modules:
- xml_api: client of the cloud (SyrConnectXmlAPI)
- xml_parser, xml_payload, xml_checksum, xml_encryption: answers, requests, checksums and
  login encryption of the cloud
- json_api: client of the local device API (SyrConnectJsonAPI)
- http_client: HTTP requests and size-limited reading of the answers
- commands: set commands of the keys and the values the device takes
- codes: values that mean "no code" and the meaning of the alarm, notification and
  warning codes of each device family
- models: devices, status values, cloud services, statistics series and model signatures
- model_detection: signatures of the known models and their detection
- settings: allowed raw values of the settings and the values that switch them off
- units: water hardness units of the device families and their conversion
- values: parsing of the status values, value tables and set commands of single keys
- exceptions: errors raised by the clients
- const: URLs, keys, client identity and the cloud services

It imports only its own modules, the standard library and the requirements listed in
README.md (tests/aiosyrconnect/test_package.py checks this).
"""

from .codes import NO_CODE_VALUES, is_code_active
from .commands import (
    JSON_ONLY_COMMANDS,
    build_cartridge_type_commands,
    build_dex_command,
    build_flag_command,
    build_reset_command,
    build_sir_command,
    build_trigger_command,
    command_status_key,
    filling_refusal,
    is_flag_enabled,
    is_microleakage_test_running,
    is_regeneration_running,
    set_command,
)
from .const import API_SERVICES
from .exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectDeviceNotFoundError,
    SyrConnectError,
    SyrConnectHTTPError,
    SyrConnectInvalidResponseError,
    SyrConnectLoginFailedError,
    SyrConnectSessionExpiredError,
    is_network_error,
)
from .http_client import mask_ug_value
from .json_api import SyrConnectJsonAPI
from .model_detection import (
    MODEL_SIGNATURES,
    UNKNOWN_MODEL_SIGNATURE,
    detect_model_signature,
)
from .models import (
    SyrConnectApiDevice,
    SyrConnectModelSignature,
    SyrConnectService,
    SyrConnectStatistic,
    SyrConnectStatus,
    SyrConnectStatusValue,
)
from .settings import FLUSHING_TEMPERATURE_GAP, FLUSHING_TEMPERATURE_RANGES
from .units import round_hardness
from .values import (
    CAS_VALUE_MAP,
    CRS_VALUE_MAP,
    LEAK_PROTECTION_PROFILES,
    T1_VALUE_MAP,
    UL_VALUE_MAP,
    build_rtm_commands,
    build_set_ab_command,
    get_ab_value,
    get_active_leak_protection_profiles,
    get_battery_level,
    get_crs_value,
    get_current_leak_protection_profile,
    get_current_mac,
    get_hardness_class,
    get_iwh_value,
    get_le_raw_values,
    get_le_step,
    get_rtm_value,
    get_serial_number,
    is_empty_ip,
    is_measuring_sensor_active,
    is_spurious_bap,
    is_value_true,
    is_valve_closing,
    is_valve_opening,
    parse_alarm_memory,
    parse_avo_value,
    parse_bat_value,
    parse_code_value,
    parse_cyt_value,
    parse_dbd_value,
    parse_dom_value,
    parse_float,
    parse_hygiene_module_value,
    parse_int,
    parse_lar_value,
    parse_le_value,
    parse_lng_value,
    parse_mbar_value,
    parse_net_value,
    parse_sta_value,
    parse_tmz_value,
    parse_utc_time,
    parse_vol_value,
    parse_weekday_mask,
    to_float,
    to_int,
)
from .xml_api import SyrConnectXmlAPI
from .xml_parser import is_device_offline

__all__ = [
    "API_SERVICES",
    "CAS_VALUE_MAP",
    "CRS_VALUE_MAP",
    "FLUSHING_TEMPERATURE_GAP",
    "FLUSHING_TEMPERATURE_RANGES",
    "JSON_ONLY_COMMANDS",
    "LEAK_PROTECTION_PROFILES",
    "MODEL_SIGNATURES",
    "NO_CODE_VALUES",
    "T1_VALUE_MAP",
    "UL_VALUE_MAP",
    "UNKNOWN_MODEL_SIGNATURE",
    "SyrConnectApiDevice",
    "SyrConnectAuthError",
    "SyrConnectConnectionError",
    "SyrConnectDeviceNotFoundError",
    "SyrConnectError",
    "SyrConnectHTTPError",
    "SyrConnectInvalidResponseError",
    "SyrConnectJsonAPI",
    "SyrConnectLoginFailedError",
    "SyrConnectModelSignature",
    "SyrConnectService",
    "SyrConnectSessionExpiredError",
    "SyrConnectStatistic",
    "SyrConnectStatus",
    "SyrConnectStatusValue",
    "SyrConnectXmlAPI",
    "build_cartridge_type_commands",
    "build_dex_command",
    "build_flag_command",
    "build_reset_command",
    "build_rtm_commands",
    "build_set_ab_command",
    "build_sir_command",
    "build_trigger_command",
    "command_status_key",
    "detect_model_signature",
    "filling_refusal",
    "get_ab_value",
    "get_active_leak_protection_profiles",
    "get_battery_level",
    "get_crs_value",
    "get_current_leak_protection_profile",
    "get_current_mac",
    "get_hardness_class",
    "get_iwh_value",
    "get_le_raw_values",
    "get_le_step",
    "get_rtm_value",
    "get_serial_number",
    "is_code_active",
    "is_device_offline",
    "is_empty_ip",
    "is_flag_enabled",
    "is_measuring_sensor_active",
    "is_microleakage_test_running",
    "is_network_error",
    "is_regeneration_running",
    "is_spurious_bap",
    "is_value_true",
    "is_valve_closing",
    "is_valve_opening",
    "mask_ug_value",
    "parse_alarm_memory",
    "parse_avo_value",
    "parse_bat_value",
    "parse_code_value",
    "parse_cyt_value",
    "parse_dbd_value",
    "parse_dom_value",
    "parse_float",
    "parse_hygiene_module_value",
    "parse_int",
    "parse_lar_value",
    "parse_le_value",
    "parse_lng_value",
    "parse_mbar_value",
    "parse_net_value",
    "parse_sta_value",
    "parse_tmz_value",
    "parse_utc_time",
    "parse_vol_value",
    "parse_weekday_mask",
    "round_hardness",
    "set_command",
    "to_float",
    "to_int",
]
