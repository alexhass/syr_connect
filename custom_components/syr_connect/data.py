"""Typed data structures of the SYR Connect coordinator."""

from typing import Any, NotRequired, TypedDict


class SyrConnectDevice(TypedDict):
    """A device as returned by the API clients and stored in the coordinator data.

    `status` and `available` are added by the coordinator once the status of the
    device has been fetched.
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
    # Set by the coordinator
    status: NotRequired[dict[str, Any]]
    available: NotRequired[bool]


class SyrConnectCoordinatorData(TypedDict):
    """The data of the SYR Connect coordinator."""

    configuration_url: str | None
    devices: list[SyrConnectDevice]
    projects: list[dict[str, Any]]
