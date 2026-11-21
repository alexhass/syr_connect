"""Data models of the SYR Connect APIs: devices, status values, services, statistics and models."""

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

    # Serial number; the clients address the device by it
    id: str
    name: str
    # Added by the `get_devices` of both API clients, the XML response parser does not know it
    project_id: NotRequired[str]
    # Only reported by the XML API
    # Device collection the cloud addresses the device by; the client resolves it
    dclg: NotRequired[str]
    serial_number: NotRequired[str]
    dk: NotRequired[int]
    dkv: NotRequired[int]
    sbt: NotRequired[int]


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
    # XML_SECURE_KEY and XML_SECURE_VECTOR (PKCS7) around the base64 text of
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

    # Status key whose measurement history this series holds, e.g. "getCEL"
    key: str
    # Web service method below the device service path, e.g. "GetSafeFloorStatistics"
    method: str
    # Report type: 1 = week, 2 = month, 3 = year, 4 = raw measurements
    rtyp: int
    # Measurement within the method, e.g. 1 = temperature, 2 = humidity
    t: int
    # Unit of the measurement; the cloud answers with an empty <col /> without it
    unit: str


@dataclass(frozen=True, kw_only=True)
class SyrConnectModelSignature:
    """Signature of a device model: how it is detected and how it is addressed.

    `dk`, `dkv`, `sbt` and `dfm` identify the model in `detect_model_signature()`; the
    `cna_equals`, `srn_*` and `ver_*` fields are its status checks. `base_path`,
    `alarm_style_alm` and `alarm_clear_via_set` describe how the model is addressed.
    """

    # If True, the alarm/error state is cleared by sending a setter command (setALM)
    # rather than by a clrALM command
    alarm_clear_via_set: bool = False
    # If True, alarm commands use ALM variants (getALM/setALM/clrALM) instead of ALA
    # variants (getALA/setALA/clrALA)
    alarm_style_alm: bool = False
    # JSON API local access base path for the model, or None if not applicable
    base_path: str | None
    # Exact match against the `getCNA` value
    cna_equals: str | None = None
    # MultiController role (getDFM), the subtype of dk=1500-1506. Like `sbt`, None
    # matches every device.
    dfm: int | None = None
    # Cloud API deviceKind: the integer `dk` attribute in GetProjectDeviceCollections XML
    dk: int | None
    # Cloud API deviceKindVersion: the integer `dkv` attribute in
    # GetProjectDeviceCollections XML; for Azure-connected devices this also equals the
    # numeric SRN prefix of newer production units
    dkv: int | None
    # Stable machine-readable model identifier (e.g. "lexplus10s")
    name: str
    # Cloud API device subtype: the integer `sbt` attribute in GetProjectDeviceCollections
    # XML; only set when the subtype uniquely identifies this model within its dk/dkv family
    sbt: int | None = None
    # String that must immediately follow `srn_prefix`: "AAA" is the factory batch code
    # used by all current SYR/Hansgrohe/Sanibel devices; override it if a future
    # production run changes the pattern
    srn_infix: str = "AAA"
    # Prefix that `getSRN` must start with
    srn_prefix: str | None = None
    # String that `getVER` must contain
    ver_contains: str | None = None
    # Prefix that `getVER` must start with
    ver_prefix: str | None = None

    @property
    def alarm_status_key(self) -> str:
        """Status key of the current alarm (getALM or getALA, see `alarm_style_alm`)."""
        return "getALM" if self.alarm_style_alm else "getALA"

    @property
    def alarm_reset_command(self) -> tuple[str, str]:
        """Command and value that reset an active alarm of the model.

        Formats:
        - alarm_clear_via_set: ("setALA", "FF") or ("setALM", "FF")
        - otherwise: ("clrALA", "") or ("clrALM", "")

        Both clients send it with `set_device_status`; the JSON API sends a clr
        command to its /clr/ endpoint.
        """
        field = self.alarm_status_key[3:]
        if self.alarm_clear_via_set:
            return f"set{field}", "FF"
        return f"clr{field}", ""
