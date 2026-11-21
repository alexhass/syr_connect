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
- models: devices, status values, cloud services, statistics series and model signatures
- model_detection: signatures of the known models and their detection
- exceptions: errors raised by the clients
- const: URLs, keys, client identity and the cloud services

It imports only its own modules, the standard library and the requirements listed in
README.md (tests/aiosyrconnect/test_package.py checks this).
"""

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
from .model_detection import MODEL_SIGNATURES, detect_model_signature
from .models import (
    SyrConnectApiDevice,
    SyrConnectModelSignature,
    SyrConnectService,
    SyrConnectStatistic,
    SyrConnectStatus,
    SyrConnectStatusValue,
)
from .xml_api import SyrConnectXmlAPI
from .xml_parser import is_device_offline

__all__ = [
    "API_SERVICES",
    "MODEL_SIGNATURES",
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
    "detect_model_signature",
    "is_device_offline",
    "is_network_error",
    "mask_ug_value",
]
