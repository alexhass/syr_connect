"""Data models of the SYR Connect APIs: devices, status values, services and statistics."""

from dataclasses import dataclass
from typing import Any, NotRequired, TypedDict

# A value of the device status. The XML API reports text only; the local JSON API also
# reports numbers, booleans and null, and lists or objects for a few keys (getCMS,
# getFSL, getLMS, getPAH, getWFL).
type SyrConnectStatusValue = (
    str | int | float | bool | list[Any] | dict[str, Any] | None
)
# The status of a device: status key (e.g. "getFLO") -> value
type SyrConnectStatus = dict[str, SyrConnectStatusValue]


class SyrConnectApiDevice(TypedDict):
    """A device as returned by the API clients."""

    id: str
    dclg: str
    name: str
    # Added by the `get_devices` of both API clients, the XML response parser does not know it
    project_id: NotRequired[str]
    # Only reported by the XML API
    serial_number: NotRequired[str]
    dk: NotRequired[int]
    dkv: NotRequired[int]
    sbt: NotRequired[int]
    # Current UTC offset of the project's time zone in seconds, from `tzo` of the device
    # list ("02:00:00" in summer time). Only reported by the XML API
    utc_offset: NotRequired[int]
    # Status of the device, once it has been fetched
    status: NotRequired[SyrConnectStatus]


@dataclass(frozen=True, kw_only=True)
class SyrConnectService:
    """Cloud API service (app brand) of the SYR Connect XML API."""

    # App name sent in the login request. It is bound to api_base_url: the login
    # fails unless both belong to the same service.
    api_app_name: str
    # Base URL of the API endpoints (login, device status), ends with "/"
    api_base_url: str
    # Bundle identifier of the official app. The server does not check it, it is
    # sent to emulate the app. Also the key of the service in the registry.
    cf_bundle_identifier: str
    # User-facing URL of the service, may differ from api_base_url
    configuration_url: str
    # AES-256 key and IV of the login response, each AES-CBC encrypted with
    # XML_SECURE_KEY/_VECTOR (PKCS7) around the base64 text of
    # the raw bytes, and base64 encoded. They differ per service.
    crypt_key: str
    crypt_vector: str
    # Display name of the service
    display_name: str


@dataclass(frozen=True, kw_only=True)
class SyrConnectStatistic:
    """Measurement history series that the cloud keeps for a device family.

    The fields are the web service method and the attributes of the ``<sh>`` element
    of the request, see "SafeFloor measurement history" in docs/syrconnect-protocol.md.
    """

    # Sensor key whose measurement history this series holds
    key: str
    # Web service method below the device service path, e.g. "GetSafeFloorStatistics"
    method: str
    # Report type: 1 = week, 2 = month, 3 = year, 4 = raw measurements
    rtyp: int
    # Measurement within the method, e.g. 1 = temperature, 2 = humidity
    t: int
    # Unit of the measurement; the cloud answers with an empty <col /> without it
    unit: str
