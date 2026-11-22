"""Data models of the SYR Connect APIs: devices, status values, services, statistics and models."""

from collections.abc import Mapping
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
    """Signature of a device model: how it is detected, addressed and named.

    `dk`, `dkv`, `sbt` and `dfm` identify the model in `detect_model_signature()`; the
    `cna_equals`, `srn_*` and `ver_*` fields are its status checks. `base_path`,
    `alarm_style_alm` and `alarm_clear_via_set` describe how the model is addressed.
    `display_name`, `manufacturer` and `service_branding` name it, and the
    `maximum_*` fields are limits of its settings. `ala_codes`, `not_codes` and
    `wrn_codes` are the code tables of its family (`codes.py`).
    """

    # Alarm codes (getALA or getALM, see `alarm_style_alm`) of the device family: raw
    # code -> key of the meaning; None means the codes are unknown
    ala_codes: Mapping[str, str] | None = None
    # If True, the alarm/error state is cleared by sending a setter command (setALM)
    # rather than by a clrALM command. It only chooses the command: the value of the
    # set command comes from the client (`clear_value`), a clr command has none.
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
    # Human-readable model name, e.g. for the device info and the local model selector
    display_name: str
    # Cloud API deviceKind: the integer `dk` attribute in GetProjectDeviceCollections XML
    dk: int | None
    # Cloud API deviceKindVersion: the integer `dkv` attribute in
    # GetProjectDeviceCollections XML; for Azure-connected devices this also equals the
    # numeric SRN prefix of newer production units
    dkv: int | None
    # Human-readable name of the device manufacturer
    manufacturer: str
    # Maximum number of days between regenerations; None means no regeneration interval
    maximum_regeneration_interval: int | None = None
    # Maximum salt tank volume that can be set; only set for models whose salt amount
    # can be set
    maximum_salt_volume: int | None = None
    # Stable machine-readable model identifier (e.g. "lexplus10s")
    name: str
    # Notification codes (getNOT) of the device family: raw code -> key of the meaning;
    # None means the codes are unknown
    not_codes: Mapping[str, str] | None = None
    # Cloud API device subtype: the integer `sbt` attribute in GetProjectDeviceCollections
    # XML; only set when the subtype uniquely identifies this model within its dk/dkv family
    sbt: int | None = None
    # Per-service branding: cf_bundle_identifier of `API_SERVICES` -> (manufacturer,
    # display name). Used when the same dk/dkv hardware is sold under different names
    # by different vendors; detection and addressing stay the same.
    service_branding: Mapping[str, tuple[str, str]] | None = None
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
    # Warning codes (getWRN) of the device family: raw code -> key of the meaning; None
    # means the codes are unknown
    wrn_codes: Mapping[str, str] | None = None

    def branded(self, service: str | None) -> tuple[str, str]:
        """Return the manufacturer and display name of the model for a cloud service.

        Args:
            service: The cf_bundle_identifier of the cloud service, or None for the
                local JSON API

        Returns:
            The (manufacturer, display_name) pair from `service_branding`, or the
            default one if the service has no branding of its own
        """
        if service is not None and self.service_branding is not None:
            branding = self.service_branding.get(service)
            if branding is not None:
                return branding
        return self.manufacturer, self.display_name

    @property
    def alarm_status_key(self) -> str:
        """Status key of the current alarm (getALM or getALA, see `alarm_style_alm`)."""
        return "getALM" if self.alarm_style_alm else "getALA"

    def alarm_reset_command(self, clear_value: str | int) -> tuple[str, str | int]:
        """Return the command and value that reset an active alarm of the model.

        The signature decides between a set and a clr command; the value of a set
        command is the clear value of the client, which encodes it:

        Formats:
        - alarm_clear_via_set, cloud: ("setALA", "FF") or ("setALM", "FF")
        - alarm_clear_via_set, device: ("setALA", 255) or ("setALM", 255)
        - otherwise: ("clrALA", "") or ("clrALM", "")

        Both clients send it with `set_device_status`; the JSON API sends a clr
        command to its /clr/ endpoint.

        Args:
            clear_value: `clear_value` of the client that sends it

        Returns:
            The command and its value
        """
        field = self.alarm_status_key[3:]
        if self.alarm_clear_via_set:
            return f"set{field}", clear_value
        return f"clr{field}", ""
