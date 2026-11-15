"""Asynchronous client library for SYR Connect water treatment and leak protection devices.

It talks to the SYR Connect cloud (XML API) and to the local API of the devices (JSON
API). The library does not depend on Home Assistant: the caller passes an
aiohttp.ClientSession, the User-Agent and, for the cloud, the locale and the time zone.

Modules:
- xml_api: client of the cloud (SyrConnectXmlAPI)
- xml_parser, xml_payload, xml_checksum, xml_encryption: answers, requests, checksums and
  login encryption of the cloud
- json_api: client of the local device API (SyrConnectJsonAPI)
- http_client: HTTP requests and size-limited reading of the answers
- models: devices, status values, cloud services and statistics series
- exceptions: errors raised by the clients
- const: URLs, keys, client identity and the cloud services

It lives inside the integration (see README.md) and must not import Home Assistant or any
module of the integration (tests/aiosyrconnect/test_package.py checks this).
"""

from .const import API_SERVICES, DEFAULT_CF_BUNDLE_IDENTIFIER
from .exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectError,
    SyrConnectHTTPError,
    SyrConnectInvalidResponseError,
    SyrConnectLoginFailedError,
    SyrConnectSessionExpiredError,
)
from .http_client import mask_ug_value
from .json_api import SyrConnectJsonAPI
from .models import (
    SyrConnectApiDevice,
    SyrConnectService,
    SyrConnectStatistic,
    SyrConnectStatus,
    SyrConnectStatusValue,
)
from .xml_api import SyrConnectXmlAPI
from .xml_parser import is_device_offline

__version__ = "1.0.0"

__all__ = [
    "API_SERVICES",
    "DEFAULT_CF_BUNDLE_IDENTIFIER",
    "SyrConnectApiDevice",
    "SyrConnectAuthError",
    "SyrConnectConnectionError",
    "SyrConnectError",
    "SyrConnectHTTPError",
    "SyrConnectInvalidResponseError",
    "SyrConnectJsonAPI",
    "SyrConnectLoginFailedError",
    "SyrConnectService",
    "SyrConnectSessionExpiredError",
    "SyrConnectStatistic",
    "SyrConnectStatus",
    "SyrConnectStatusValue",
    "SyrConnectXmlAPI",
    "is_device_offline",
    "mask_ug_value",
]
