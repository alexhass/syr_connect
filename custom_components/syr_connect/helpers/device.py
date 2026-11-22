"""Device data of the coordinator: lookup, model, availability and device info."""

import logging

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..aiosyrconnect import get_current_mac
from ..const import DOMAIN
from ..data import SyrConnectCoordinatorData, SyrConnectDevice
from ..models import UNKNOWN_MODEL, SyrConnectModel, detect_model

_LOGGER = logging.getLogger(__name__)


def get_device(
    coordinator_data: SyrConnectCoordinatorData | None, device_id: str
) -> SyrConnectDevice | None:
    """Return the device with the given id from the coordinator data.

    Args:
        coordinator_data: Coordinator data, None before the first refresh
        device_id: Device ID (serial number)

    Returns:
        The device, or None if it is not in the data
    """
    if not coordinator_data:
        return None
    for device in coordinator_data.get("devices", []):
        if device.get("id") == device_id:
            return device
    return None


def detect_device_model(
    device: SyrConnectDevice, service: str | None = None, model: str | None = None
) -> SyrConnectModel:
    """Detect the model of a device from its cloud device kind and its status.

    Only the cloud API (XML) reports `dk`, `dkv` and `sbt`; without them the model is
    detected from the status alone. A model chosen at setup (local JSON API) is used
    without detection (see `models.detect_model()`).

    Args:
        device: The device from the coordinator data
        service: The cf_bundle_identifier of the config entry, None for the local
            JSON API; the log names the model as this service brands it
        model: The name of the model chosen at setup (CONF_MODEL), None to detect it

    Returns:
        The chosen or detected model, or `UNKNOWN_MODEL`
    """
    return detect_model(
        device.get("status"),
        dk=device.get("dk"),
        dkv=device.get("dkv"),
        sbt=device.get("sbt"),
        service=service,
        model=model,
    )


def get_device_model(device: SyrConnectDevice | None) -> SyrConnectModel:
    """Return the model of a device, as detected by the coordinator.

    Device data that was not built by the coordinator has no stored model; it is
    detected instead.

    Args:
        device: The device from the coordinator data, or None if it is missing

    Returns:
        The detected model, or `UNKNOWN_MODEL` without a device
    """
    if device is None:
        return UNKNOWN_MODEL
    model = device.get("model")
    if model is not None:
        return model
    return detect_device_model(device)


def is_device_available(
    coordinator: DataUpdateCoordinator[SyrConnectCoordinatorData | None],
    device_id: str,
) -> bool:
    """Return whether the entities of a device are available.

    Shared by the `available` property of all entities of a device:
    - False if the last coordinator update failed.
    - The device's own `available` flag otherwise (False while the cloud reports it offline).
    - False if the device is not in the data: temporary failures keep the devices of the
      last update, so a missing device was removed from the account (it is removed from
      Home Assistant once the device list is complete).
    """
    if not coordinator.last_update_success:
        return False
    device = get_device(coordinator.data, device_id)
    if device is None:
        return False
    return bool(device.get("available", True))


def build_device_info(
    device_id: str,
    device_name: str,
    coordinator_data: SyrConnectCoordinatorData | None,
) -> DeviceInfo:
    """Build DeviceInfo object from coordinator data.

    Args:
        device_id: Device ID (serial number)
        device_name: Device display name
        coordinator_data: Coordinator data containing device information

    Returns:
        DeviceInfo object with device metadata
    """

    model = None
    manufacturer = None
    sw_version = None
    hw_version = None
    mac = None
    connections = set()
    configuration_url: str | None = None

    # Extract device information from coordinator data
    device = get_device(coordinator_data, device_id)
    if coordinator_data is not None and device is not None:
        status = device.get("status", {})

        # Get human-friendly model display name and manufacturer of the cloud service
        detected = get_device_model(device)
        manufacturer, model = detected.branded(coordinator_data.get("service"))
        configuration_url = coordinator_data.get("configuration_url")

        # Get software version from getVER
        if status.get("getVER"):
            sw_version = str(status["getVER"])

        # Get hardware version from getFIR
        if status.get("getFIR"):
            hw_version = str(status["getFIR"])

        # Get MAC address using prioritized helper
        detected_mac = get_current_mac(status)
        if detected_mac:
            mac = str(detected_mac)
            connections.add(("mac", mac))

    # Use fallback if no model found
    if model is None:
        model = "Unknown model"
        _LOGGER.debug("No model found for device %s, using fallback", device_id)
    if manufacturer is None:
        manufacturer = "Unknown"

    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=device_name,
        manufacturer=manufacturer,
        model=model,
        sw_version=sw_version,
        hw_version=hw_version,
        serial_number=device_id,
        connections=connections,
        configuration_url=configuration_url,
    )
