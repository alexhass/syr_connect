"""Helper functions for SYR Connect integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import _SYR_CONNECT_CONFIGURATION_URL, DOMAIN

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
    mac = None
    connections = set()

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

            # Get MAC address from getMAC
            if 'getMAC' in status and status['getMAC']:
                mac = str(status['getMAC'])
                connections.add(("mac", mac))

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
        connections=connections if connections else set(),
        configuration_url=_SYR_CONNECT_CONFIGURATION_URL,
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


def clean_sensor_value(value: str | int | float) -> str | int | float:
    """Clean sensor value by removing prefixes like 'Vol[L]6530' -> '6530'.

    Some devices send values with prefixes that include the parameter name
    and unit in brackets, e.g., 'Vol[L]6530', 'Temp[C]25', etc.
    This function extracts the numeric value from such strings.

    Args:
        value: The raw sensor value

    Returns:
        Cleaned value with prefix removed if applicable
    """
    # Only process string values
    if not isinstance(value, str):
        return value

    # Pattern to match values like 'Vol[L]6530', 'Temp[C]25', etc.
    # Format: word characters, optional brackets with content, then the actual value
    match = re.match(r'^[A-Za-z]+\[[^\]]+\](.+)$', value)
    if match:
        cleaned = match.group(1).strip()
        _LOGGER.debug("Cleaned sensor value from '%s' to '%s'", value, cleaned)
        return cleaned

    return value
