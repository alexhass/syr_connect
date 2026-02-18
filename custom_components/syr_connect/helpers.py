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

            # Get MAC address using prioritized helper
            detected_mac = get_current_mac(status)
            if detected_mac:
                mac = str(detected_mac)
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


def get_current_mac(status: dict[str, Any]) -> str | None:
    """Return the current MAC address following priority rules.

    Priority:
    1. If `getIPA` not empty -> use `getMAC`
    2. If `getWIP` not empty -> use `getMAC1`
    3. If `getEIP` not empty -> use `getMAC2`

    If the selected MAC is missing or empty, fall back to any available
    non-empty `getMAC` / `getMAC1` / `getMAC2`.
    """
    if not status:
        return None

    def is_not_empty_ip(key: str) -> bool:
        val = status.get(key)
        if val is None:
            return False
        if isinstance(val, str):
            s = val.strip()
            # Treat empty string and the unspecified address 0.0.0.0 as empty
            # Syr "Trio DFR/LS" sets IP as "0.0.0.0", where others do not.
            if s == "" or s == "0.0.0.0":
                return False
            return True
        return True

    # Priority selection
    if is_not_empty_ip("getIPA"):
        mac_val = status.get("getMAC")
        if mac_val is not None and str(mac_val).strip() != "":
            return str(mac_val)

    if is_not_empty_ip("getWIP"):
        mac_val = status.get("getMAC1")
        if mac_val is not None and str(mac_val).strip() != "":
            return str(mac_val)

    if is_not_empty_ip("getEIP"):
        mac_val = status.get("getMAC2")
        if mac_val is not None and str(mac_val).strip() != "":
            return str(mac_val)

    # Fallback: first available MAC
    for k in ("getMAC", "getMAC1", "getMAC2"):
        val = status.get(k)
        if val is not None and str(val).strip() != "":
            return str(val)

    return None


def get_sensor_avo_value(value: str | int | float) -> float | None:
    """Extract numeric flow value from strings like '1655mL' -> 1.655 (L).

    The getAVO sensor returns flow values in the format '1655mL', '0mL', etc.
    This function extracts the numeric value, converts from mL to L, and returns it as a float.

    Args:
        value: The raw sensor value (e.g., '1655mL', '0mL')

    Returns:
        Numeric flow value in L (converted from mL), or None if extraction fails
    """
    # Return None for None input
    if value is None:
        return None

    # If already numeric, convert from mL to L
    if isinstance(value, int | float):
        return float(value) / 1000

    # Only process string values
    if not isinstance(value, str):
        return None

    # Pattern to match values like '1655mL', '0mL', etc.
    # Extract the numeric part before 'mL'
    match = re.match(r'^(\d+)mL$', value)
    if match:
        try:
            flow_ml = int(match.group(1))
            flow_l = flow_ml / 1000  # Convert mL to L
            _LOGGER.debug("Extracted flow value from '%s' to %.3f L", value, flow_l)
            return flow_l
        except (ValueError, TypeError):
            return None

    # If pattern doesn't match, try to extract any number at the start and convert
    match = re.match(r'^(\d+)', value)
    if match:
        try:
            flow_ml = int(match.group(1))
            return flow_ml / 1000  # Convert mL to L
        except (ValueError, TypeError):
            return None

    return None


def get_sensor_vol_value(value: str | int | float) -> str | int | float:
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


def get_sensor_bat_value(value: str | int | float) -> float | None:
    """Parse battery voltage supporting two formats.

    Formats supported:
    - Safe-T+ format: "6,11 4,38 3,90" -> take first token and parse comma as decimal
    - Trio DFR/LS format: "363" -> value in 1/100 V, so divide by 100 -> 3.63

    Returns the voltage as float rounded to 2 decimals, or None on failure.
    """
    if value is None:
        return None

    # If already numeric, assume it's in 1/100 V (int) and divide
    if isinstance(value, (int | float)):
        try:
            return round(float(value) / 100.0, 2)
        except (TypeError, ValueError):
            return None

    if not isinstance(value, str):
        return None

    s = value.strip()
    if s == "":
        return None

    # If space-separated Safe-T+ format, take first token
    if " " in s:
        first = s.split()[0]
        try:
            return round(float(first.replace(',', '.')), 2)
        except (ValueError, TypeError):
            return None

    # Digits-only Trio DFR/LS format "363" -> divide by 100
    if s.isdigit():
        try:
            return round(int(s) / 100.0, 2)
        except (ValueError, TypeError):
            return None

    # No other variants supported. Return None.
    return None
