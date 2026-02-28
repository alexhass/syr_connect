"""Helper functions for SYR Connect integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    _SYR_CONNECT_CONFIGURATION_URL,
    _SYR_CONNECT_SENSOR_ALA_CODES_LEX10,
    _SYR_CONNECT_SENSOR_ALA_CODES_NEOSOFT,
    _SYR_CONNECT_SENSOR_ALA_CODES_SAFET,
    _SYR_CONNECT_SENSOR_NOT_CODES,
    _SYR_CONNECT_SENSOR_WRN_CODES,
    DOMAIN,
)
from .models import detect_model

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

            # Get human-friendly model display name
            detected = detect_model(status)
            display_name = detected.get("display_name") if isinstance(detected, dict) else None
            if display_name:
                model = str(display_name)

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
        model = "Unknown model"
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
    - Safe-Tech+ format: "9,36" -> take as is and parse comma as decimal
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

    # If space-separated Safe-T+ format, take firstech token
    if " " in s:
        first = s.split()[0]
        try:
            return round(float(first.replace(',', '.')), 2)
        except (ValueError, TypeError):
            return None

    # Single-token Safe-Tech+ format with comma decimal, e.g. "9,36"
    if ',' in s:
        try:
            return round(float(s.replace(',', '.')), 2)
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


def get_sensor_rtm_value(status: dict[str, Any]) -> str | None:
    """Return regeneration time as HH:MM string or None.

    Handles two device representations:
    - Separate hour (`getRTH`) and minutes (`getRTM`) numeric values.
    - Combined string in `getRTM` containing an HH:MM value.

    Returns a zero-padded "HH:MM" string when valid, otherwise None.
    """
    if not status:
        return None

    rth = status.get("getRTH")
    rtm = status.get("getRTM")

    if rtm is None or rtm == "":
        return None

    # Case A:Combined representation: getRTH missing/empty and getRTM contains HH:MM
    if rth is None or rth == "":
        if isinstance(rtm, str):
            m_match = re.match(r"\s*(\d{2}):(\d{2})\s*$", rtm)
            if not m_match:
                return None
            try:
                hh = int(m_match.group(1))
                mm = int(m_match.group(2))
                # Strict validation: hours 0-23, minutes 0-59
                if 0 <= hh <= 23 and 0 <= mm <= 59:
                    return f"{hh:02d}:{mm:02d}"
            except Exception:
                return None
        return None

    # Case B: Separate numeric values
    try:
        h = int(float(rth))
        m = int(float(rtm))
        # Strict validation: hours 0-23, minutes 0-59
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    except Exception:
        return None

    return None


def set_sensor_rtm_value(status: dict[str, Any], option: str) -> list[tuple[str, Any]]:
    """Build set commands for regeneration time selection.

    Given the current `status` and a chosen `option` string in "HH:MM" format,
    return a list of (set_key, value) tuples that should be called on the API.

    If the device uses the combined representation (no `getRTH` and `getRTM` is
    a HH:MM string), a single `setRTM` with the HH:MM string is returned.
    Otherwise, returns two commands: `setRTH` (hour int) and `setRTM` (minute int).
    """
    commands: list[tuple[str, Any]] = []
    if not option or not isinstance(option, str):
        return commands

    # Determine combined-mode
    combined_mode = False
    if status is not None:
        raw_rth = status.get("getRTH")
        raw_rtm = status.get("getRTM")
        if (raw_rth is None or raw_rth == "") and isinstance(raw_rtm, str) and ":" in raw_rtm:
            combined_mode = True

    if combined_mode:
        commands.append(("setRTM", option))
        return commands

    # Parse HH:MM into integers
    try:
        parts = option.split(":")
        h = int(parts[0])
        m = int(parts[1])
    except Exception:
        return commands

    commands.append(("setRTH", h))
    commands.append(("setRTM", m))
    return commands


def get_sensor_ab_value(status: dict[str, Any]) -> bool | None:
    """Parse `getAB` value from device status and return closed state as bool.

    Returns:
        - True if valve is closed
        - False if valve is open
        - None if unknown/unparseable

    Devices may report `getAB` as numeric (1=open, 2=closed) or boolean-like
    strings (`"true"`/`"false"`). Map both to a unified boolean.
    """
    if not status:
        return None

    val = status.get("getAB")
    if val is None or val == "":
        return None

    # Numeric values (int/float or digit strings)
    try:
        if isinstance(val, (int | float)):
            # Safe-T: Syr seems to use 1 for open and 2 for closed, but we want True=closed, False=open
            ival = int(float(val))
            if ival == 2:
                return True
            if ival == 1:
                return False
            return None
        if isinstance(val, str):
            # Trio DFR/LS and other new devices: Normalize string and check for boolean-like values
            s = val.strip().lower()
            # Boolean-like strings
            if s in ("true", "false"):
                return s == "true"
            # Numeric string fallback
            if s.isdigit():
                ival = int(s)
                if ival == 2:
                    return True
                if ival == 1:
                    return False
    except Exception:
        return None

    return None


def get_sensor_ala_map(status: dict[str, Any], raw_code: Any) -> tuple[str | None, str]:
    """Map raw getALA alarm code to internal translation key.

    Args:
        status: Flattened device status dict (used to detect model).
        raw_code: Raw code value from the API (e.g. "FF", "A5", "0").

    Returns:
        Internal translation key (e.g. "no_alarm", "alarm_low_salt") or None if unknown.
    """
    if raw_code is None:
        return (None, "")

    # Normalize code and prepare uppercase form for mapping lookups
    code = str(raw_code)
    code_upper = code.strip().upper()

    # Detect model from status (expect flattened attributes)
    try:
        model = detect_model(status or {}).get("name")
    except Exception:
        model = None

    # If model is unknown or not detected, do NOT attempt any matching.
    # Return the raw code unchanged so the caller can present it 1:1.
    if not model or (isinstance(model, str) and str(model).strip().lower().startswith("unknown")):
        return (None, code)

    # Select mapping based on detected model. Only attempt mapping for the
    # explicitly-detected model family; do NOT attempt cross-family fallbacks.
    if model in ("lexplus10", "lexplus10s", "lexplus10sl"):
        mapped = _SYR_CONNECT_SENSOR_ALA_CODES_LEX10.get(code_upper)
        return (mapped, code) if mapped is not None else (None, code)

    if model in ("neosoft2500", "neosoft5000", "trio"):
        mapped = _SYR_CONNECT_SENSOR_ALA_CODES_NEOSOFT.get(code_upper)
        return (mapped, code) if mapped is not None else (None, code)

    if model == "safetplus":
        mapped = _SYR_CONNECT_SENSOR_ALA_CODES_SAFET.get(code_upper)
        return (mapped, code) if mapped is not None else (None, code)

    # If we reach here, model was something else (not recognized). Do not
    # attempt any mapping — return raw code unchanged.
    return (None, code)


def get_sensor_not_map(status: dict[str, Any], raw_code: Any) -> tuple[str | None, str]:
    """Map raw getNOT notification code to internal translation key.

    Args:
        status: Device status dict (unused but kept for signature parity)
        raw_code: Raw code value from the API (e.g. "01", "FF")

    Returns:
        (mapped_key, raw_code) where mapped_key is internal translation key or None
    """
    # Accept None
    if raw_code is None:
        return (None, "")

    code = str(raw_code)
    code_upper = code.strip().upper()
    mapped = _SYR_CONNECT_SENSOR_NOT_CODES.get(code_upper)
    return (mapped, code) if mapped is not None else (None, code)


def get_sensor_wrn_map(status: dict[str, Any], raw_code: Any) -> tuple[str | None, str]:
    """Map raw getWRN warning code to internal translation key.

    Args:
        status: Device status dict (unused but kept for signature parity)
        raw_code: Raw code value from the API (e.g. "01", "FF")

    Returns:
        (mapped_key, raw_code) where mapped_key is internal translation key or None
    """
    # Accept None
    if raw_code is None:
        return (None, "")

    code = str(raw_code)
    code_upper = code.strip().upper()
    mapped = _SYR_CONNECT_SENSOR_WRN_CODES.get(code_upper)
    return (mapped, code) if mapped is not None else (None, code)


def build_set_ab_command(status: dict[str, Any], closed: bool) -> tuple[str, Any]:
    """Build the appropriate (`setAB`, value) command for desired closed state.

    - If device reports `getAB` as boolean-like strings, use "true"/"false".
    - Otherwise prefer numeric `1` (open) / `2` (closed).

    Returns a tuple (set_key, value).
    """
    raw = None
    if status:
        raw = status.get("getAB")

    # Prefer boolean-string representation if current value looks boolean
    if isinstance(raw, str) and raw.strip().lower() in ("true", "false"):
        return ("setAB", "true" if closed else "false")

    # If raw is explicitly boolean type (unlikely), use string representation
    if isinstance(raw, bool):
        return ("setAB", "true" if closed else "false")

    # Fallback to numeric representation
    return ("setAB", 2 if closed else 1)
