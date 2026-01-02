"""Helper functions for SYR Connect integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def build_device_info(
    device_id: str,
    device_name: str,
    coordinator_data: dict[str, Any],
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
    sw_version = None
    hw_version = None

    # Extract device information from coordinator data
    for device in coordinator_data.get('devices', []):
        if device['id'] == device_id:
            status = device.get('status', {})

            # Get model from getCNA
            if 'getCNA' in status and status['getCNA']:
                model = str(status['getCNA'])

            # Get software version from getVER
            if 'getVER' in status and status['getVER']:
                sw_version = str(status['getVER'])

            # Get hardware version from getFIR
            if 'getFIR' in status and status['getFIR']:
                hw_version = str(status['getFIR'])

            break

    # Use fallback if no model found
    if model is None:
        model = "SYR Connect"
        _LOGGER.debug("No model found for device %s, using fallback", device_id)

    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=device_name,
        manufacturer="SYR",
        model=model,
        sw_version=sw_version,
        hw_version=hw_version,
        serial_number=device_id,
    )


def build_entity_id(platform: str, device_id: str, key: str) -> str:
    """Build consistent entity ID.

    Args:
        platform: Platform name (sensor, binary_sensor, button)
        device_id: Device ID (serial number)
        key: Entity key (sensor_key, command, etc.)

    Returns:
        Formatted entity ID
    """
    return f"{platform}.{DOMAIN}_{device_id.lower()}_{key.lower()}"
