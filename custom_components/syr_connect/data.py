"""Typed data structures of the SYR Connect coordinator."""

from typing import Any, NotRequired, TypedDict

from .aiosyrconnect import SyrConnectApiDevice
from .models import SyrConnectModel


class SyrConnectDevice(SyrConnectApiDevice):
    """A device as returned by the API clients and stored in the coordinator data.

    `status`, `model` and `available` are added by the coordinator once the status of
    the device has been fetched.
    """

    # Detected from `status` whenever the coordinator changes it
    model: NotRequired[SyrConnectModel]
    available: NotRequired[bool]


class SyrConnectCoordinatorData(TypedDict):
    """The data of the SYR Connect coordinator."""

    configuration_url: str | None
    devices: list[SyrConnectDevice]
    projects: list[dict[str, Any]]
    # cf_bundle_identifier of the cloud service, None for the local JSON API
    service: str | None
