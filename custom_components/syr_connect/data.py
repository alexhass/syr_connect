"""Typed data structures of the SYR Connect coordinator."""

from typing import Any, NotRequired, TypedDict

from .models import SyrConnectModel


class SyrConnectDevice(TypedDict):
    """A device as returned by the API clients and stored in the coordinator data.

    `status`, `model` and `available` are added by the coordinator once the status of
    the device has been fetched.
    """

    id: str
    dclg: str
    name: str
    # Added by `SyrConnectXmlAPI.get_devices`, the response parser does not know it
    project_id: NotRequired[str]
    # Only reported by the XML API
    serial_number: NotRequired[str]
    dk: NotRequired[int]
    dkv: NotRequired[int]
    sbt: NotRequired[int]
    # Current UTC offset of the project's time zone in seconds, from `tzo` of the device
    # list ("02:00:00" in summer time). Only reported by the XML API
    utc_offset: NotRequired[int]
    # Set by the coordinator
    status: NotRequired[dict[str, Any]]
    # Detected from `status` whenever the coordinator changes it
    model: NotRequired[SyrConnectModel]
    available: NotRequired[bool]


class SyrConnectCoordinatorData(TypedDict):
    """The data of the SYR Connect coordinator."""

    configuration_url: str | None
    devices: list[SyrConnectDevice]
    projects: list[dict[str, Any]]
