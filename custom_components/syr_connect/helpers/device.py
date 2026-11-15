"""Device data of the coordinator: lookup, model, availability and device info."""

import logging
from typing import Any

from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.data import (
    SyrConnectCoordinatorData,
    SyrConnectDevice,
)
from custom_components.syr_connect.models import (
    UNKNOWN_MODEL,
    SyrConnectModel,
    detect_model,
)
from homeassistant.helpers.device_registry import DeviceInfo

from .values import is_empty_ip

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


def is_device_available(coordinator: Any, device_id: str) -> bool:
    """Return whether the entities of a device are available.

    Shared by the `available` property of all entities of a device:
    - False if the last coordinator update failed.
    - The device's own `available` flag otherwise (False while the cloud reports it offline).
    - False if the device is not in the data: temporary failures keep the devices of the
      last update, so a missing device was removed from the account (it is removed from
      Home Assistant at the next setup).
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


def get_current_mac(status: dict[str, Any]) -> str | None:
    """Return the MAC address of the active network connection.

    The connections are checked in this order; the first one with an address and a
    non-empty MAC address is used:
    1. If `getIPA` not empty -> use `getMAC`
    2. If `getWIP` not empty and getWFS = 2 (Wi-Fi is connected) -> use `getMAC1`
    3. If `getEIP` not empty -> use `getMAC2`

    Returns None if no connection has both.
    """
    if not status:
        return None

    def is_not_empty_ip(key: str) -> bool:
        return not is_empty_ip(status.get(key))

    # Priority selection for MAC address:
    # 1. If getIPA (primary IP) is set and not empty, use getMAC (primary MAC)
    if is_not_empty_ip("getIPA"):
        mac_val = status.get("getMAC")
        if mac_val is not None and str(mac_val).strip() != "":
            return str(mac_val)

    # 2. If getWIP (Wi-Fi IP) is set and not empty, only use getMAC1 (Wi-Fi MAC)
    #    if and only if getWFS == 2 (Wi-Fi is connected).
    #    This prevents returning a Wi-Fi MAC address when the device is not actually
    #    connected to a Wi-Fi network, which avoids confusion and ensures that only
    #    active/connected MAC addresses are reported.
    if is_not_empty_ip("getWIP"):
        wfs_val = status.get("getWFS")
        # getWFS meaning:
        #   2 = Wi-Fi connected
        #   1 = Wi-Fi connecting
        #   0 = Wi-Fi not connected
        if wfs_val is not None:
            try:
                wfs_int = int(wfs_val)
            except ValueError, TypeError:
                wfs_int = None
        else:
            wfs_int = None
        if wfs_int == 2:
            # Only return the Wi-Fi MAC if Wi-Fi is confirmed to be connected
            mac_val = status.get("getMAC1")
            if mac_val is not None and str(mac_val).strip() != "":
                return str(mac_val)
        # If Wi-Fi is not connected, skip getMAC1 and continue to next fallback

    # 3. If getEIP (Ethernet IP) is set and not empty, use getMAC2 (Ethernet MAC)
    if is_not_empty_ip("getEIP"):
        mac_val = status.get("getMAC2")
        if mac_val is not None and str(mac_val).strip() != "":
            return str(mac_val)

    # No fallback: only return a MAC if it matches the priority rules above
    return None


def is_device_offline(dst: Any) -> bool:
    """Return True if the cloud device state means offline.

    dst="0" never online, dst="1" offline (2 = online, 3 = standby).

    Args:
        dst: The ``dst`` value of a status response

    Returns:
        True if the device is not reachable via the cloud
    """
    return str(dst if dst is not None else "").strip() in ("0", "1")
