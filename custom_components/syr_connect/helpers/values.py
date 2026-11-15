"""Parsing and formatting of device status values."""

import ipaddress
import logging
import re
from typing import Any

from ..aiosyrconnect import SyrConnectStatus, SyrConnectStatusValue
from ..const import _SYR_CONNECT_SENSOR_CND_PER_DH

_LOGGER = logging.getLogger(__name__)


def is_value_true(val: object) -> bool:
    """Normalize a heterogeneous API flag value to a Python bool.

    SYR devices report binary activation flags (e.g. getPAx, getBUZ) in varying
    formats depending on API and firmware version: the XML API always sends strings
    ("1", "0", "True", "false"), the local JSON API native bool or int/float. This
    function is the single conversion for all boolean keys, so callers do not need
    to handle each format separately.

    Args:
        val: Raw value received from the device API.

    Returns:
        True if val represents a truthy/active state, False otherwise.
        Unknown or unconvertible values always return False.
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, (int | float)):
        try:
            return int(float(val)) != 0
        except ValueError, TypeError, OverflowError:
            return False
    if isinstance(val, str):
        sval = val.strip().lower()
        if sval in ("1", "true"):
            return True
        if sval in ("0", "false"):
            return False
        try:
            return int(float(sval)) != 0
        except ValueError, TypeError, OverflowError:
            return False
    return False


def is_empty_ip(value: Any) -> bool:
    """Return True if an IP address value is missing, blank or the unspecified address.

    Formats:
    - Missing or blank: None, "" -> True
    - Unspecified address (Trio DFR/LS without an address): "0.0.0.0", "::" -> True
    - Any other value, also a hostname: "192.168.1.10" -> False
    """
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    text = value.strip()
    if text == "":
        return True
    try:
        return ipaddress.ip_address(text).is_unspecified
    except ValueError:
        return False


def get_sensor_avo_value(value: Any) -> float | None:
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
    match = re.match(r"^(\d+)mL$", value)
    if match:
        flow_ml = int(match.group(1))
        flow_l = flow_ml / 1000  # Convert mL to L
        _LOGGER.debug("Extracted flow value from '%s' to %.3f L", value, flow_l)
        return flow_l

    # If pattern doesn't match, try to extract any number at the start and convert
    match = re.match(r"^(\d+)", value)
    if match:
        flow_ml = int(match.group(1))
        return flow_ml / 1000  # Convert mL to L

    return None


def to_float(value: SyrConnectStatusValue) -> float:
    """Return a status value as float, like float().

    Raises:
        TypeError: If the value is no text or number: None, or a list or object of
            the local JSON API
        ValueError: If the text is no number
    """
    if isinstance(value, str | int | float):
        return float(value)
    raise TypeError(f"Not a number: {value!r}")


def to_int(value: SyrConnectStatusValue) -> int:
    """Return a status value as int, like int().

    Raises:
        TypeError: If the value is no text or number: None, or a list or object of
            the local JSON API
        ValueError: If the text is no whole number
    """
    if isinstance(value, str | int | float):
        return int(value)
    raise TypeError(f"Not a number: {value!r}")


def get_sensor_vol_value(value: SyrConnectStatusValue) -> SyrConnectStatusValue:
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
    # Format: letters, brackets with content, then the actual value
    match = re.match(r"^[A-Za-z]+\[[^\]]+\](.+)$", value)
    if match:
        cleaned = match.group(1).strip()
        _LOGGER.debug("Cleaned sensor value from '%s' to '%s'", value, cleaned)
        return cleaned

    return value


def get_sensor_lng_value(value: SyrConnectStatusValue) -> SyrConnectStatusValue:
    """Extract the leading integer from a getLNG value.

    Some devices append a human-readable annotation to the numeric value,
    e.g. "0 (0=Deutsch 1=English)" instead of plain "0".
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
    except ValueError:
        return value
    else:
        return token


def get_sensor_net_value(value: Any) -> float | None:
    """Parse mains voltage (getNET) supporting three formats.

    Formats supported:
    - Safe-T+ format:   "ADC:950 6,16V" -> extract "6,16" and parse comma as decimal -> 6.16
    - Safe-Tech+ format: "11,86"         -> parse comma as decimal -> 11.86
    - Trio DFR/LS format: "363"          -> value in 1/100 V, divide by 100 -> 3.63

    Returns the voltage as float rounded to 2 decimals, or None on failure.
    """
    # If already numeric, assume it's in 1/100 V (int) and divide
    if isinstance(value, int | float):
        return round(value / 100, 2)
    if not isinstance(value, str):
        return None
    text = value.strip()

    # Safe-T+ format: "ADC:950 6,16V" — extract the token that ends with 'V'
    if "ADC:" in text:
        for token in text.split():
            if token.upper().endswith("V"):
                return _parse_comma_decimal(token[:-1])  # strip trailing 'V'
        return None

    # Safe-Tech+ format with comma decimal, e.g. "11,86"
    if "," in text:
        return _parse_comma_decimal(text)

    # Digits-only Trio DFR/LS format "363" -> divide by 100
    if text.isdigit():
        return _parse_centivolts(text)

    return None


def _parse_comma_decimal(text: str) -> float | None:
    """Parse a number with a comma as decimal separator ("6,16" -> 6.16), rounded to 2 decimals.

    Returns None if the text is no number.
    """
    try:
        return round(float(text.replace(",", ".")), 2)
    except ValueError:
        return None


def _parse_centivolts(digits: str) -> float | None:
    """Parse a digits-only value in 1/100 V and divide by 100 ("363" -> 3.63).

    Returns None if the digits are no number.
    """
    try:
        return round(int(digits) / 100, 2)
    except ValueError:
        # isdigit() also accepts digits int() does not, such as "²"
        return None


def get_hygiene_module_value(value: Any) -> int | None:
    """Setting of a hygiene module line (getSCF, getCCF, ...): raw value -> integer.

    Only the number before a space or a "[" counts; the cloud probably adds a suffix of
    an unknown format (see "Hygiene module" in docs/syrconnect-protocol.md).

    Formats:
    - Without a suffix: "3" -> 3
    - With a suffix (assumed): "3 [1-7]" -> 3
    - With a suffix without a space (assumed): "3[1-7]" -> 3
    """
    if value is None or isinstance(value, bool):
        return None
    tokens = str(value).split()
    if not tokens:
        return None
    try:
        return int(float(tokens[0].split("[", 1)[0]))
    except ValueError, OverflowError:
        return None


def get_sensor_bat_value(value: Any) -> float | None:
    """Parse battery voltage supporting two formats.

    Formats supported:
    - Safe-T+ format: "6,11 4,38 3,90" -> take first token and parse comma as decimal
    - Safe-Tech+ format: "9,36" -> take as is and parse comma as decimal
    - Trio DFR/LS format: "363" -> value in 1/100 V, so divide by 100 -> 3.63

    Returns the voltage as float rounded to 2 decimals, or None on failure.
    """
    # If already numeric, assume it's in 1/100 V (int) and divide
    if isinstance(value, int | float):
        return round(value / 100, 2)
    if not isinstance(value, str):
        return None
    text = value.strip()

    # If space-separated Safe-T+ format, take the first token
    if " " in text:
        return _parse_comma_decimal(text.split()[0])

    # Single-token Safe-Tech+ format with comma decimal, e.g. "9,36"
    if "," in text:
        return _parse_comma_decimal(text)

    # Digits-only Trio DFR/LS format "363" -> divide by 100
    if text.isdigit():
        return _parse_centivolts(text)

    # No other variants supported. Return None.
    return None


def get_sensor_rtm_value(status: SyrConnectStatus) -> str | None:
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

    # Case A: Combined representation: getRTH missing/empty and getRTM contains HH:MM
    if rth is None or rth == "":
        if not isinstance(rtm, str):
            return None
        m_match = re.match(r"\s*(\d{2}):(\d{2})\s*$", rtm)
        if not m_match:
            return None
        return _format_hhmm(int(m_match.group(1)), int(m_match.group(2)))

    # Case B: Separate numeric values
    try:
        return _format_hhmm(int(to_float(rth)), int(to_float(rtm)))
    except (ValueError, TypeError, OverflowError) as err:
        _LOGGER.debug("Failed to parse regeneration time from separate values: %s", err)
        return None


def _format_hhmm(hours: int, minutes: int) -> str | None:
    """Return "HH:MM" for hours 0-23 and minutes 0-59, otherwise None."""
    # Strict validation: hours 0-23, minutes 0-59
    if 0 <= hours <= 23 and 0 <= minutes <= 59:
        return f"{hours:02d}:{minutes:02d}"
    return None


def get_sensor_iwh_value(status: SyrConnectStatus) -> int | float | None:
    """Compute or return incoming water hardness (getIWH).

    Rules:
    1. If `getIWH` and `getWHU` (its unit) exist and `getIWH` is numeric, return
       `getIWH` (int if whole).
    2. Otherwise, if `getCND` exists and is numeric, default `getWHU` to 0 when
       missing and compute `getIWH = getCND / 35` (°dH).
    3. Return None when values are missing or unparsable.
    """
    if not status:
        return None
    iwh = _reported_iwh(status)
    if iwh is not None:
        return iwh
    return _iwh_from_cnd(status)


def _reported_iwh(status: SyrConnectStatus) -> int | float | None:
    """Return getIWH (int if whole) if it is a number and its unit getWHU is known.

    The normalized value is written back into the status.
    """
    raw_iwh = status.get("getIWH")
    raw_whu = status.get("getWHU")
    # Only accept an explicit getIWH when WHU is also present (unit known)
    if raw_iwh is None or raw_iwh == "" or raw_whu is None or raw_whu == "":
        return None
    try:
        val = to_float(raw_iwh)
    except ValueError, TypeError:
        # Fall through to fallback derivation
        return None
    # Return int when it's an exact whole number
    iwh = int(val) if val.is_integer() else val
    # Persist normalized numeric getiwh back into status
    status["getIWH"] = iwh
    return iwh


def _iwh_from_cnd(status: SyrConnectStatus) -> int | float | None:
    """Compute getIWH in °dH from the conductivity (getCND), with the factor SYR uses.

    getWHU defaults to 0 (°dH) when it is missing or invalid. getWHU and getIWH are
    written back into the status.
    """
    # Fallback: derive from getCND when available
    raw_cnd = status.get("getCND")
    if raw_cnd is None or raw_cnd == "":
        return None
    try:
        cnd = to_float(raw_cnd)
    except ValueError, TypeError:
        return None

    # Normalize/ensure getWHU exists; default to 0 when missing or invalid
    raw_whu = status.get("getWHU")
    try:
        whu = int(to_float(raw_whu)) if (raw_whu is not None and raw_whu != "") else 0
    except ValueError, TypeError, OverflowError:
        whu = 0
    status["getWHU"] = whu

    # Compute and persist getIWH in °dH with the factor SYR uses
    iwh = cnd / _SYR_CONNECT_SENSOR_CND_PER_DH
    iwh_out = int(iwh) if iwh.is_integer() else iwh
    status["getIWH"] = iwh_out
    return iwh_out


def set_sensor_rtm_value(
    status: SyrConnectStatus, option: str
) -> list[tuple[str, Any]]:
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
        if (
            (raw_rth is None or raw_rth == "")
            and isinstance(raw_rtm, str)
            and ":" in raw_rtm
        ):
            combined_mode = True

    if combined_mode:
        commands.append(("setRTM", option))
        return commands

    # Parse HH:MM into integers
    try:
        parts = option.split(":")
        h = int(parts[0])
        m = int(parts[1])
    except (ValueError, IndexError) as err:
        _LOGGER.debug("Failed to parse time option '%s': %s", option, err)
        return commands

    commands.append(("setRTH", h))
    commands.append(("setRTM", m))
    return commands


def get_sensor_ab_value(status: SyrConnectStatus) -> bool | None:
    """Parse `getAB` value from device status and return closed state as bool.

    Returns:
        - True if valve is closed
        - False if valve is open
        - None if unknown/unparsable

    The value stored under getAB may be a plain raw value from the API
    (string, int, bool). The device itself signals a pending change via the
    "s" attribute in the XML response, which the ResponseParser already
    writes as the current value.

    Devices may report the raw value in multiple formats:
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

    return _parse_ab_raw(val)


# Numeric getAB values. Safe-T: Syr seems to use 1 for open and 2 for closed, but we want
# True=closed, False=open
_SYR_CONNECT_VALUES_AB_NUMERIC: dict[int, bool] = {
    1: False,
    2: True,
}


def _parse_ab_raw(val: Any) -> bool | None:
    """Parse a single raw getAB value (string/int/bool) to bool | None.

    Returns True (closed), False (open), or None (unknown).
    """
    # Boolean values (native JSON booleans)
    if isinstance(val, bool):
        # In JSON API boolean True means closed, False means open
        return val

    # Numeric values (int/float or digit strings)
    try:
        if isinstance(val, (int | float)):
            return _SYR_CONNECT_VALUES_AB_NUMERIC.get(int(float(val)))
        if isinstance(val, str):
            # Trio DFR/LS and other new devices: Normalize string and check for boolean-like values
            s = val.strip().lower()
            # Boolean-like strings
            if s in ("true", "false"):
                return s == "true"
            # Numeric string fallback
            if s.isdigit():
                return _SYR_CONNECT_VALUES_AB_NUMERIC.get(int(s))
    except (ValueError, TypeError, AttributeError, OverflowError) as err:
        _LOGGER.debug("Failed to parse getAB value: %s", err)
        return None

    return None


def build_set_ab_command(
    status: SyrConnectStatus, closed: bool
) -> tuple[str, Any] | None:
    """Build the appropriate (`setAB`, value) command for desired closed state.

    This function mirrors the device's own format for `getAB` when sending `setAB`:
    - Native bool (`True`/`False`) or boolean strings ("true"/"false") → "true" (closed) / "false" (open)
    - Native integer or numeric string ("1"/"2") → numeric `1` (open) / `2` (closed)
    - Unknown or absent → `None` (error is logged; caller must not send the command)

    Using the device's native format prevents potential parsing errors or
    firmware issues when the device receives commands in an unexpected format.

    Returns a tuple (set_key, value), or None when the format is unrecognized.
    """
    raw = None
    if status:
        raw = status.get("getAB")

    text = raw.strip().lower() if isinstance(raw, str) else None

    # Native bool (JSON API devices like SafeTech/Trio) → boolean string
    # Must be checked before int because bool is a subclass of int in Python.
    # Boolean-like strings ("true"/"false") → boolean string
    if isinstance(raw, bool) or text in ("true", "false"):
        return ("setAB", "true" if closed else "false")

    # Native integer (JSON API devices that report getAB as int 1/2) → numeric
    # Numeric string ("1"/"2") → numeric (XML API and some JSON API devices)
    if isinstance(raw, int | float) or (text is not None and text.isdigit()):
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
