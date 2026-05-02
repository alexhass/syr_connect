"""Helper functions for SYR Connect integration."""
from __future__ import annotations

import ipaddress
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    _SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT,
    _SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT,
    _SYR_CONNECT_CONFIGURATION_URL,
    _SYR_CONNECT_SCAN_INTERVAL_CONF,
    _SYR_CONNECT_SENSOR_ALA_CODES_LEX10,
    _SYR_CONNECT_SENSOR_ALA_CODES_NEOSOFT,
    _SYR_CONNECT_SENSOR_ALA_CODES_SAFET,
    _SYR_CONNECT_SENSOR_EXCLUDED,
    _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_IPADDRESS,
    _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_STRING,
    _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_VALUE,
    _SYR_CONNECT_SENSOR_NOT_CODES,
    _SYR_CONNECT_SENSOR_WRN_CODES,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    DOMAIN,
)
from .models import detect_model

_LOGGER = logging.getLogger(__name__)


def is_value_true(val: object) -> bool:
    """Normalize a heterogeneous API flag value to a Python bool.

    SYR devices report binary activation flags (e.g. ``getPAx``) in varying
    formats depending on firmware version: native ``bool``, ``int``/``float``,
    or strings such as ``"1"`` or ``"true"``. This function provides a single,
    consistent conversion so callers do not need to handle each format separately.

    Args:
        val: Raw value received from the device API.

    Returns:
        ``True`` if *val* represents a truthy/active state, ``False`` otherwise.
        Unknown or unconvertible values always return ``False``.
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, (int | float)):
        try:
            return int(float(val)) != 0
        except (ValueError, TypeError):
            return False
    if isinstance(val, str):
        sval = val.strip().lower()
        if sval in ("1", "true"):
            return True
        if sval in ("0", "false"):
            return False
        try:
            return int(float(sval)) != 0
        except (ValueError, TypeError):
            return False
    return False


def get_default_scan_interval_for_entry(entry: ConfigEntry | dict | None) -> int:
    """Return the default scan interval for a config entry.

    Logic:
    - If `entry` is None -> return XML default
    - If the entry has an explicit `scan_interval` option -> return it
    - Otherwise, return the per-API default: JSON -> JSON default, else XML default
    """
    # If no entry provided, preserve legacy XML default
    if entry is None:
        return _SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT

    # Accept either a ConfigEntry or a plain dict (used internally by the coordinator)
    if isinstance(entry, dict):
        options = entry.get("options") or {}
        data = entry.get("data") or {}
    else:
        options = getattr(entry, "options", None) or {}
        data = getattr(entry, "data", None) or {}

    # If user explicitly set a scan interval option, use it
    if _SYR_CONNECT_SCAN_INTERVAL_CONF in options:
        try:
            return int(options[_SYR_CONNECT_SCAN_INTERVAL_CONF])
        except (TypeError, ValueError):
            pass

    # Otherwise use per-API default (default to XML for legacy)
    api_type = data.get(CONF_API_TYPE, API_TYPE_XML)
    return (
        _SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT
        if api_type == API_TYPE_JSON
        else _SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT
    )


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
    manufacturer = None
    sw_version = None
    hw_version = None
    mac = None
    connections = set()

    # Extract device information from coordinator data
    for device in coordinator_data.get('devices', []):
        if device['id'] == device_id:
            status = device.get('status', {})

            # Get human-friendly model display name and manufacturer
            detected = detect_model(status)
            display_name = detected.get("display_name")
            if display_name:
                model = str(display_name)
            manufacturer = detected.get("manufacturer") or None

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


def registry_cleanup(
    hass: HomeAssistant,
    coordinator_data: dict[str, Any],
    domain: str,
    allowed_keys: set[str] | None = None,
) -> None:
    """Remove previously-registered entities from the entity registry.

    Scans all registered entities for the given domain/devices and removes
    any whose key is NOT in ``allowed_keys``. If ``allowed_keys`` is None,
    nothing is removed.

    For sensor entities, also removes entries for keys that are conditionally
    hidden (i.e. listed in ``_SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_*``) when
    ``is_sensor_visible`` returns ``False`` for the current device status. This
    covers keys that are absent from the device status entirely as well as keys
    that are present with an empty or zero value.

    Args:
        hass: Home Assistant instance.
        coordinator_data: Coordinator ``.data`` mapping containing ``devices``.
        domain: Entity domain string (e.g. ``"sensor"``).
        allowed_keys: Set of permitted sensor keys. Entities whose key is not
            in this set will be removed from the entity registry.
    """
    if allowed_keys is None:
        return
    try:
        registry = er.async_get(hass)
        allowed_lower = {k.lower() for k in allowed_keys}

        # Build the set of conditionally visible sensor keys once, outside the device loop.
        _conditional_keys = (
            _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_VALUE
            | _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_STRING
            | _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_IPADDRESS
        ) - _SYR_CONNECT_SENSOR_EXCLUDED

        for device in (coordinator_data or {}).get("devices", []):
            device_id = device.get("id")
            if not device_id:
                continue
            prefix = f"{domain}.{DOMAIN}_{device_id.lower()}_"

            # Remove entities whose key is no longer in the allowed set.
            for entry in list(registry.entities.values()):
                if not entry.entity_id.startswith(prefix):
                    continue
                key_lower = entry.entity_id[len(prefix):]
                if key_lower not in allowed_lower:
                    _LOGGER.debug(
                        "Removing unlisted %s from registry: %s",
                        domain,
                        entry.entity_id,
                    )
                    try:
                        registry.async_remove(entry.entity_id)
                    except Exception:
                        _LOGGER.exception("Failed to remove entity %s", entry.entity_id)

            # Remove conditionally hidden sensor entities based on current device status.
            if domain == "sensor":
                status = device.get("status", {})
                for key in _conditional_keys:
                    value = status.get(key)
                    if not is_sensor_visible(status, key, value):
                        entity_id = f"{prefix}{key.lower()}"
                        if registry.async_get(entity_id) is not None:
                            _LOGGER.debug(
                                "Removing conditionally hidden sensor from registry: %s",
                                entity_id,
                            )
                            try:
                                registry.async_remove(entity_id)
                            except Exception:
                                _LOGGER.exception("Failed to remove entity %s", entity_id)
    except Exception:
        _LOGGER.exception("Failed to cleanup excluded %s entities from registry", domain)


def get_current_mac(status: dict[str, Any]) -> str | None:
    """Return the current MAC address following priority rules.

    Priority:
    1. If `getIPA` not empty -> use `getMAC`
    2. If `getWIP` not empty and getWFS = 2 (Wi-Fi is connected) -> use `getMAC1`
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
        #   1 = Wi-Fi not connected
        #   0 = unknown or not available
        if wfs_val is not None:
            try:
                wfs_int = int(wfs_val)
            except (ValueError, TypeError):
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


def get_sensor_vol_value(value: str | int | float) -> str | int | float | None:
    """Clean sensor value by removing prefixes like 'Vol[L]6530' -> '6530'.

    Some devices send values with prefixes that include the parameter name
    and unit in brackets, e.g., 'Vol[L]6530', 'Temp[C]25', etc.
    This function extracts the numeric value from such strings.

    Examples:
        >>> get_sensor_vol_value("")
        None
        >>> get_sensor_vol_value(6530)
        6530
        >>> get_sensor_vol_value("Vol[L]6530")
        '6530'

    Args:
        value: The raw sensor value

    Returns:
        Cleaned value with prefix removed if applicable, or None for empty string
    """
    # Only process string values
    if not isinstance(value, str):
        return value

    # Return None for empty string
    if value.strip() == "":
        return None

    # Pattern to match values like 'Vol[L]6530', 'Temp[C]25', etc.
    # Format: word characters, optional brackets with content, then the actual value
    match = re.match(r'^[A-Za-z]+\[[^\]]+\](.+)$', value)
    if match:
        cleaned = match.group(1).strip()
        _LOGGER.debug("Cleaned sensor value from '%s' to '%s'", value, cleaned)
        return cleaned

    return value


def get_sensor_lng_value(value: str | int | float) -> str | int | float | None:
    """Extract the leading integer from a getLNG value.

    Some devices append a human-readable annotation to the numeric value,
    e.g. ``"0 (0=Deutsch 1=English)"`` instead of plain ``"0"``.
    This function returns only the leading integer token so it can be matched
    against the translation state map.

    Examples:
        >>> get_sensor_lng_value("0 (0=Deutsch 1=English)")
        '0'
        >>> get_sensor_lng_value("1")
        '1'
        >>> get_sensor_lng_value(0)
        0

    Args:
        value: The raw getLNG sensor value

    Returns:
        Leading integer token as string, original value if no annotation present,
        or None for empty string.
    """
    if not isinstance(value, str):
        return value

    if value.strip() == "":
        return None

    token = value.split(maxsplit=1)[0]
    try:
        int(token)
        return token
    except ValueError:
        return value


def get_sensor_net_value(value: str | int | float) -> float | None:
    """Parse mains voltage (getNET) supporting three formats.

    Formats supported:
    - Safe-T+ format:   "ADC:950 6,16V" -> extract "6,16" and parse comma as decimal -> 6.16
    - Safe-Tech+ format: "11,86"         -> parse comma as decimal -> 11.86
    - Trio DFR/LS format: "363"          -> value in 1/100 V, divide by 100 -> 3.63

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

    # Safe-T+ format: "ADC:950 6,16V" — extract the token that ends with 'V'
    if "ADC:" in s:
        for token in s.split():
            if token.upper().endswith("V"):
                raw = token[:-1]  # strip trailing 'V'
                try:
                    return round(float(raw.replace(',', '.')), 2)
                except (ValueError, TypeError):
                    return None
        return None

    # Safe-Tech+ format with comma decimal, e.g. "11,86"
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

    return None


def is_valid_host(host: str) -> bool:
    """Return True if *host* is a valid IPv4, IPv6 or hostname (no port).

    - Accepts IPv4 and IPv6 addresses using the stdlib ``ipaddress`` module
    - Rejects explicit ``host:port`` strings
    - Allows DNS hostnames that meet length and label rules

    This function intentionally returns a boolean so callers can handle
    error reporting / translation to Home Assistant errors as appropriate.
    """
    if not isinstance(host, str) or not host.strip():
        return False

    # Reject surrounding whitespace
    if re.search(r"\s", host):
        return False

    # Reject explicit host:port
    if re.match(r"^.+:\d+$", host):
        return False

    # Try IP address (IPv4/IPv6)
    try:
        ipaddress.ip_address(host)
        return True
    except Exception:
        pass

    # Hostname validation: length and label rules
    hostname_pattern = r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
    return bool(re.match(hostname_pattern, host))


def get_sensor_bat_value(value: str | int | float) -> float | None:
    """Parse battery voltage supporting two formats.

    Formats supported:
    - Safe-T+ format: "6,11 4,38 3,90" -> take first token and parse comma as decimal
    - Safe-Tech+ format: "9,36" -> take as is and parse comma as decimal
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
            except (ValueError, IndexError, AttributeError) as err:
                _LOGGER.debug("Failed to parse time from match: %s", err)
                return None
        return None

    # Case B: Separate numeric values
    try:
        h = int(float(rth))
        m = int(float(rtm))
        # Strict validation: hours 0-23, minutes 0-59
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    except (ValueError, TypeError) as err:
        _LOGGER.debug("Failed to parse regeneration time from separate values: %s", err)
        return None

    return None


def get_sensor_iwh_value(status: dict[str, Any]) -> int | float | None:
    """Compute or return incoming water hardness (getIWH).

    Rules:
    1. If `getIWH` exists and is numeric, return it (int if whole).
    2. If `getIWH` missing/empty but `getCND` exists and is numeric,
       default `getWHU` to 0 when missing and compute `getIWH = getCND / 33`.
    3. Return ``None`` when values are missing or unparseable.
    """
    if not status:
        return None

    raw_iwh = status.get("getIWH")
    raw_whu = status.get("getWHU")
    # Only accept an explicit getIWH when WHU is also present (unit known)
    if raw_iwh is not None and raw_iwh != "" and raw_whu is not None and raw_whu != "":
        try:
            val = float(raw_iwh)
            # Persist normalized numeric getiwh back into status
            try:
                status["getIWH"] = int(val) if val.is_integer() else val
            except Exception:
                pass
            # Return int when it's an exact whole number
            return int(val) if val.is_integer() else val
        except (ValueError, TypeError):
            # Fall through to fallback derivation
            pass

    # Fallback: derive from getCND when available
    raw_cnd = status.get("getCND")
    if raw_cnd is None or raw_cnd == "":
        return None
    try:
        cnd = float(raw_cnd)
    except (ValueError, TypeError):
        return None

    # Normalize/ensure getWHU exists; default to 0 when missing or invalid
    raw_whu = status.get("getWHU")
    try:
        whu = int(float(raw_whu)) if (raw_whu is not None and raw_whu != "") else 0
    except (ValueError, TypeError):
        whu = 0
    try:
        status["getWHU"] = whu
    except Exception:
        pass

    # Compute and persist getIWH
    # Calculation notes:
    # - 1 °dH is equivalent to approximately 30-35 µS/cm per scientific articles.
    # - However, the more precise standard value for clean, unpolluted fresh water appears to be 1 °dH = 33 µS/cm.
    iwh = cnd / 33.0
    iwh_out = int(iwh) if iwh.is_integer() else iwh
    try:
        status["getIWH"] = iwh_out
    except Exception:
        pass
    return iwh_out


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
    except (ValueError, IndexError, AttributeError) as err:
        _LOGGER.debug("Failed to parse time option '%s': %s", option, err)
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

    Devices may report `getAB` in multiple formats:
    - Numeric: 1 (open), 2 (closed) - Used by older Safe-T devices
    - Boolean strings: "true" (closed), "false" (open) - Used by newer Trio devices

    The numeric mapping (1=open, 2=closed) appears counterintuitive but
    matches the SYR device firmware convention.
    """
    if not status:
        return None

    val = status.get("getAB")
    if val is None or val == "":
        return None

    # Boolean values (native JSON booleans)
    if isinstance(val, bool):
        # In JSON API boolean True means closed, False means open
        return bool(val)

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
    except (ValueError, TypeError, AttributeError) as err:
        _LOGGER.debug("Failed to parse getAB value: %s", err)
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
    except (ValueError, KeyError, AttributeError, TypeError) as err:
        _LOGGER.debug("Failed to detect model for ALA mapping: %s", err)
        model = None

    # If model is unknown or not detected, do NOT attempt any matching.
    # Return the raw code unchanged so the caller can present it 1:1.
    if not model or (isinstance(model, str) and str(model).strip().lower().startswith("unknown")):
        return (None, code)

    # Select mapping based on detected model. Only attempt mapping for the
    # explicitly-detected model family; do NOT attempt cross-family fallbacks.
    if model in (
        "lex10",
        "lex20",
        "lex30",
        "lex40",
        "lex60",
        "lex80",
        "lex100",
        "lexplus10",
        "lexplus10s",
        "lexplus10sl",
    ):
        mapped = _SYR_CONNECT_SENSOR_ALA_CODES_LEX10.get(code_upper)
        return (mapped, code) if mapped is not None else (None, code)

    if model in (
        "safetplus",
    ):
        mapped = _SYR_CONNECT_SENSOR_ALA_CODES_SAFET.get(code_upper)
        return (mapped, code) if mapped is not None else (None, code)

    if model in (
        "pontosbase",
        "neosoft2500",
        "neosoft5000",
        "safetech",
        "safetechplus",
        "sanibelleakprotect",
        "sanibelsoftwateruno",
        "trio",
    ):
        mapped = _SYR_CONNECT_SENSOR_ALA_CODES_NEOSOFT.get(code_upper)
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


def build_set_ab_command(status: dict[str, Any], closed: bool) -> tuple[str, Any] | None:
    """Build the appropriate (`setAB`, value) command for desired closed state.

    This function mirrors the device's own format for `getAB` when sending `setAB`:
    - Native bool (`True`/`False`) or boolean strings ("true"/"false") → "true" (closed) / "false" (open)
    - Native integer or numeric string ("1"/"2") → numeric `1` (open) / `2` (closed)
    - Unknown or absent → `None` (error is logged; caller must not send the command)

    Using the device's native format prevents potential parsing errors or
    firmware issues when the device receives commands in an unexpected format.

    Returns a tuple (set_key, value), or None when the format is unrecognised.
    """
    raw = None
    if status:
        raw = status.get("getAB")

    # Native bool (JSON API devices like SafeTech/Trio) → boolean string
    # Must be checked before int because bool is a subclass of int in Python.
    if isinstance(raw, bool):
        return ("setAB", "true" if closed else "false")

    # Boolean-like strings ("true"/"false") → boolean string
    if isinstance(raw, str) and raw.strip().lower() in ("true", "false"):
        return ("setAB", "true" if closed else "false")

    # Native integer (JSON API devices that report getAB as int 1/2) → numeric
    if isinstance(raw, int | float):
        return ("setAB", 2 if closed else 1)

    # Numeric string ("1"/"2") → numeric (XML API and some JSON API devices)
    if isinstance(raw, str) and raw.strip().isdigit():
        return ("setAB", 2 if closed else 1)

    # Unknown format — this should not happen with known device firmware.
    # Log an error and return None so the caller knows not to send a command.
    _LOGGER.error(
        "build_set_ab_command: unexpected getAB format %r (type %s); "
        "command will not be sent. Please report this issue.",
        raw,
        type(raw).__name__,
    )
    return None


def is_sensor_visible(status: dict[str, Any], key: str, value: Any) -> bool:
    """Decide whether a reported status key/value should produce a sensor.

    This function centralizes all visibility/exclusion rules so both the
    entity-creation code and diagnostics produce the same set of visible
    sensors. It is intentionally defensive about input types and accepts
    values that may be strings, numbers, booleans or None.

    Rules (applied in order):
    - Group-controlled keys: keys matching ``getPVx,getPTx,getPFx,getPNx,``
        ``getPMx,getPWx,getPBx,getPRx`` are only visible when the device's
        corresponding ``getPAx`` flag is truthy (``1``, ``true``, "on", etc.).
    - Special-case salt counters (``getCS1/2/3``): shown if the associated
        ``getSVx`` value is non-zero; otherwise they follow the normal empty
        value rules (hide when 0, "0", empty or None).
    - Empty-string exclusions: keys listed in
        ``_SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_STRING`` are hidden when the
        reported value is None or a whitespace-only string.
    - Empty-value exclusions: keys listed in
        ``_SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_VALUE`` are hidden when the
        reported value is numeric zero (0), the string "0", an empty string,
        or None.
    - Empty-IP exclusions: keys listed in
        ``_SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_IP`` are hidden when the
        reported value is None, an empty/whitespace string, or the placeholder
        IP ``"0.0.0.0"``.

    Args:
            status: The full flattened device status mapping (used for cross-key
                    checks such as ``getPAx`` and ``getSVx``).
            key: The status key being considered (e.g. ``getWIP``, ``getPV1``).
            value: The raw value reported by the device for this key.

    Returns:
            True when the key/value should result in a sensor entity; False when
            the key should be suppressed according to the rules above.

    Examples:
            >>> is_sensor_visible(status, 'getWIP', '0.0.0.0')
            False

            >>> # If getSV1 == 5 then getCS1 is visible even if its own value is '0'
            >>> is_sensor_visible({'getSV1': 5}, 'getCS1', '0')
            True
    """
    # Group keys controlled by getPAx should be hidden when getPAx is false
    m = re.match(r"get(PV|PT|PF|PN|PM|PW|PB|PR)([1-8])$", key)
    if m:
        idx = m.group(2)
        pa_key = f"getPA{idx}"
        if not is_value_true(status.get(pa_key)):
            return False

    # Special logic for getCS1/2/3: show if corresponding getSVx is non-zero
    if key in ("getCS1", "getCS2", "getCS3"):
        sv_key = "getSV" + key[-1]
        sv_val = status.get(sv_key)
        if sv_val is not None:
            try:
                if float(sv_val) != 0:
                    return True
            except (ValueError, TypeError):
                pass
        if value is None:
            return False
        if isinstance(value, int | float) and float(value) == 0:
            return False
        if isinstance(value, str) and (value.strip() == "" or value == "0"):
            return False

    # Exclude when empty string
    if key in _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_STRING:
        if value is None:
            return False
        if isinstance(value, str) and value.strip() == "":
            return False

    # Exclude when empty value (0 or "")
    if key in _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_VALUE:
        if value is None:
            return False
        if isinstance(value, int | float) and float(value) == 0:
            return False
        if isinstance(value, str) and (value.strip() == "" or value == "0"):
            return False

    # Exclude empty IPs
    if key in _SYR_CONNECT_SENSOR_EXCLUDED_WHEN_EMPTY_IPADDRESS:
        if value is None:
            return False
        if isinstance(value, str) and (value.strip() == "" or value == "0.0.0.0"):
            return False

    return True


def mask_ug_value(payload: str) -> str:
    """Redact `ug` attribute values in an XML payload.

    Replaces values like `ug="..."` with `ug="***"` (case-insensitive)
    so session tokens are not leaked in logs or diagnostics.
    """
    if not isinstance(payload, str) or payload == "":
        return payload
    try:
        # Use case-insensitive lookbehind to replace the attribute value only
        return re.sub(r'(?i)(?<=ug=")[^"]*', "***", payload)
    except re.error:
        return payload
