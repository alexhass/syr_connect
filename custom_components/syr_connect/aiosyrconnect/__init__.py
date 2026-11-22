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
- codes: values that mean "no code" and the meaning of the alarm, notification and
  warning codes of each device family
- models: devices, status values, cloud services, statistics series and model signatures
- model_detection: signatures of the known models and their detection
- values: parsing of the status values, value tables and set commands of single keys
- exceptions: errors raised by the clients
- const: URLs, keys, client identity and the cloud services

It imports only its own modules, the standard library and the requirements listed in
README.md (tests/aiosyrconnect/test_package.py checks this).
"""

from .codes import NO_CODE_VALUES, is_code_active
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
from .values import (
    CAS_VALUE_MAP,
    CND_PER_DH,
    CRS_VALUE_MAP,
    LE_VALUE_MAP,
    T1_VALUE_MAP,
    UL_VALUE_MAP,
    build_rtm_commands,
    build_set_ab_command,
    get_ab_value,
    get_iwh_value,
    get_rtm_value,
    is_empty_ip,
    is_value_true,
    parse_avo_value,
    parse_bat_value,
    parse_hygiene_module_value,
    parse_lng_value,
    parse_net_value,
    parse_sta_value,
    parse_vol_value,
    to_float,
    to_int,
)
from .xml_api import SyrConnectXmlAPI
from .xml_parser import is_device_offline

__all__ = [
    "API_SERVICES",
    "CAS_VALUE_MAP",
    "CND_PER_DH",
    "CRS_VALUE_MAP",
    "LE_VALUE_MAP",
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
    "build_rtm_commands",
    "build_set_ab_command",
    "detect_model_signature",
    "get_ab_value",
    "get_iwh_value",
    "get_rtm_value",
    "is_code_active",
    "is_device_offline",
    "is_empty_ip",
    "is_network_error",
    "is_value_true",
    "mask_ug_value",
    "parse_avo_value",
    "parse_bat_value",
    "parse_hygiene_module_value",
    "parse_lng_value",
    "parse_net_value",
    "parse_sta_value",
    "parse_vol_value",
    "to_float",
    "to_int",
]
