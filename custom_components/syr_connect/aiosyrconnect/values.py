"""Status values of the SYR devices: parsing, value tables and commands.

The devices report many values in formats of their own, which differ per model and
API (comma decimals, unit prefixes, codes for liters or hours). The functions here turn
them into numbers and build the set commands in the format the device expects. The
value tables map a raw code to its value, or to the key of its meaning that the caller
translates (`STA_VALUE_MAP`).
"""

from collections.abc import Mapping
from datetime import UTC, datetime, time, timedelta, tzinfo
import ipaddress
import logging
import re
from typing import Any, Final

from .models import SyrConnectModelSignature, SyrConnectStatus, SyrConnectStatusValue

_LOGGER = logging.getLogger(__name__)

# Canister size of the dosing pump (getCAS): raw code -> liters
CAS_VALUE_MAP: Mapping[int, int] = {
    1: 5,
    2: 10,
}

# Conductivity (getCND) in µS/cm per °dH of water hardness, the factor SYR uses to estimate
# the hardness from the conductivity
CND_PER_DH: Final = 35

# Cartridge size (getCRS): raw code -> liters
CRS_VALUE_MAP: Mapping[int, float] = {
    1: 2.5,
    2: 4,
    3: 7,
    4: 14,
    5: 30,
}

# Leak protection level while present (getLE): raw code -> liters
LE_VALUE_MAP: Mapping[int, int] = {
    2: 100,
    3: 150,
    4: 200,
    5: 250,
    6: 300,
    7: 350,
    8: 400,
    9: 450,
    10: 500,
    11: 550,
    12: 600,
    13: 650,
    14: 700,
    15: 750,
    16: 800,
    17: 850,
    18: 900,
    19: 950,
    20: 1000,
    21: 1050,
    22: 1100,
    23: 1150,
    24: 1200,
    25: 1250,
    26: 1300,
    27: 1350,
    28: 1400,
    29: 1450,
    30: 1500,
}

# Status of the regeneration (getSTA): reported text or code -> key of the meaning. The
# devices report the status as a Polish or German text; two Polish texts carry a detail
# that `parse_sta_value()` strips ("Płukanie regenerantem (5mA)", "Płukanie szybkie 1").
# Newer models (AC 3200, AC 3228, MultiController) report a number.
STA_VALUE_MAP: Mapping[str, str] = {
    "Płukanie wsteczne": "status_backwash",
    "Płukanie regenerantem": "status_regenerant_rinse",
    "Płukanie wolne": "status_slow_rinse",
    "Płukanie szybkie": "status_fast_rinse",
    "Napełnianie": "status_filling",
    "Bitte Salz nachfüllen": "status_refill_salt",
    "": "status_inactive",
    "0": "status_standby",
    "1": "status_initial_filling",
    "2": "status_automatic_filling",
    "3": "status_manual_filling",
}

# Leakage time (getT1): raw code -> hours
T1_VALUE_MAP: Mapping[int, float] = {
    1: 0.5,
    2: 1.0,
    3: 1.5,
    4: 2.0,
    5: 2.5,
    6: 3.0,
    7: 3.5,
    8: 4.0,
    9: 4.5,
    10: 5.0,
    11: 5.5,
    12: 6.0,
    13: 6.5,
    14: 7.0,
    15: 7.5,
    16: 8.0,
    17: 8.5,
    18: 9.0,
    19: 9.5,
    20: 10.0,
    21: 10.5,
    22: 11.0,
    23: 11.5,
    24: 12.0,
    25: 12.5,
    26: 13.0,
    27: 13.5,
    28: 14.0,
    29: 14.5,
    30: 15.0,
    31: 15.5,
    32: 16.0,
    33: 16.5,
    34: 17.0,
    35: 17.5,
    36: 18.0,
    37: 18.5,
    38: 19.0,
    39: 19.5,
    40: 20.0,
    41: 20.5,
    42: 21.0,
    43: 21.5,
    44: 22.0,
    45: 22.5,
    46: 23.0,
    47: 23.5,
    48: 24.0,
    49: 24.5,
    50: 25.0,
}

# Leak protection level while absent (getUL): raw code -> liters
UL_VALUE_MAP: Mapping[int, int] = {
    1: 10,
    2: 20,
    3: 30,
    4: 40,
    5: 50,
    6: 60,
    7: 70,
    8: 80,
    9: 90,
    10: 100,
}


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


def parse_avo_value(value: Any) -> float | None:
    """Extract numeric flow value from strings like '1655mL' -> 1.655 (L).

    The device reports getAVO in the format '1655mL', '0mL', etc.
    This function extracts the numeric value, converts from mL to L, and returns it as a float.

    Args:
        value: The raw value (e.g., '1655mL', '0mL')

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


def parse_float(value: SyrConnectStatusValue) -> float | None:
    """Status value as float, or None if it is no number.

    Formats:
    - Text or number: "5.5", 5.5 -> 5.5
    - Missing or no number: None, "", "x", [1] -> None
    """
    try:
        return to_float(value)
    except ValueError, TypeError:
        return None


def parse_int(value: SyrConnectStatusValue) -> int | None:
    """Status value as integer, cut off like int(float()), or None if it is no number.

    Formats:
    - Integer: "90", "90.0", 90 -> 90
    - Fraction: "90.5" -> 90
    - Missing or no number: None, "", "x", "inf", [1] -> None
    """
    try:
        return int(to_float(value))
    except ValueError, TypeError, OverflowError:
        return None


def parse_code_value[V](
    value_map: Mapping[int, V], value: SyrConnectStatusValue
) -> V | None:
    """Value of a raw code in a value table (`CAS_VALUE_MAP`, `LE_VALUE_MAP`, ...).

    Formats:
    - Known code: "2", "2.0", 2 -> value of code 2
    - Unknown code or no integer: "0", "1.5", "", None -> None
    """
    number = parse_float(value)
    if number is None or not number.is_integer():
        return None
    return value_map.get(int(number))


def get_crs_value(status: SyrConnectStatus) -> float | None:
    """Cartridge size (getCRS): raw code -> liters.

    Formats:
    - Fixed size: "3" -> 7
    - Custom size (All-in-One+): "0" -> the liters of getFCS
    """
    if parse_float(status.get("getCRS")) == 0:
        return parse_float(status.get("getFCS"))
    return parse_code_value(CRS_VALUE_MAP, status.get("getCRS"))


def parse_vol_value(value: SyrConnectStatusValue) -> SyrConnectStatusValue:
    """Clean a value by removing prefixes like 'Vol[L]6530' -> '6530'.

    Some devices send values with prefixes that include the parameter name
    and unit in brackets, e.g., 'Vol[L]6530', 'Temp[C]25', etc.
    This function extracts the numeric value from such strings.

    Examples:
        >>> parse_vol_value("")
        None
        >>> parse_vol_value(6530)
        6530
        >>> parse_vol_value("Vol[L]6530")
        '6530'

    Args:
        value: The raw value

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
        _LOGGER.debug("Cleaned value from '%s' to '%s'", value, cleaned)
        return cleaned

    return value


def parse_lng_value(value: SyrConnectStatusValue) -> SyrConnectStatusValue:
    """Extract the leading integer from a getLNG value.

    Some devices append a human-readable annotation to the numeric value,
    e.g. "0 (0=Deutsch 1=English)" instead of plain "0".
    This function returns only the leading integer token so it can be matched
    against the known languages.

    Examples:
        >>> parse_lng_value("0 (0=Deutsch 1=English)")
        '0'
        >>> parse_lng_value("1")
        '1'
        >>> parse_lng_value(0)
        0

    Args:
        value: The raw getLNG value

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


def parse_net_value(value: Any) -> float | None:
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


def parse_hygiene_module_value(value: Any) -> int | None:
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


def parse_bat_value(value: Any) -> float | None:
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


def parse_sta_value(value: SyrConnectStatusValue) -> str:
    """Status of the regeneration (getSTA): reported text or code -> key of the meaning.

    The Polish texts of two steps carry a detail (the resistance, the rinse round),
    which is only logged.

    Formats:
    - Text with a detail: "Płukanie regenerantem (5mA)" -> "status_regenerant_rinse"
    - Text with a round: "Płukanie szybkie 1" -> "status_fast_rinse"
    - Text or code of `STA_VALUE_MAP`: "Napełnianie" -> "status_filling", 0 -> "status_standby"
    - Empty or missing: "" -> "status_inactive"
    - Unknown: the reported text unchanged

    Args:
        value: Value of getSTA

    Returns:
        The key of the meaning, or the reported text if it is unknown
    """
    # A genuine 0 (standby) is kept, so None is checked explicitly
    raw = str(value) if value is not None else ""
    m_match = re.match(r"Płukanie regenerantem \((.*?)\)", raw)
    if m_match:
        _LOGGER.debug("getSTA resistance=%s", m_match.group(1))
        return STA_VALUE_MAP["Płukanie regenerantem"]
    m2_match = re.match(r"Płukanie szybkie\s*(\d+)", raw)
    if m2_match:
        _LOGGER.debug("getSTA rinse round=%s", m2_match.group(1))
        return STA_VALUE_MAP["Płukanie szybkie"]
    return STA_VALUE_MAP.get(raw, raw)


def get_rtm_value(status: SyrConnectStatus) -> str | None:
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


def get_iwh_value(status: SyrConnectStatus) -> int | float | None:
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
    cnd = parse_float(status.get("getCND"))
    if cnd is None:
        return None

    # Normalize/ensure getWHU exists; default to 0 when missing or invalid
    whu = parse_int(status.get("getWHU"))
    status["getWHU"] = 0 if whu is None else whu

    # Compute and persist getIWH in °dH with the factor SYR uses
    iwh = cnd / CND_PER_DH
    iwh_out = int(iwh) if iwh.is_integer() else iwh
    status["getIWH"] = iwh_out
    return iwh_out


def build_rtm_commands(status: SyrConnectStatus, option: str) -> list[tuple[str, Any]]:
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


def get_ab_value(status: SyrConnectStatus) -> bool | None:
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


# Numeric getAB values -> closed. The Safe-T reports 1 for open and 2 for closed.
_AB_NUMERIC: dict[int, bool] = {
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
            return _AB_NUMERIC.get(int(float(val)))
        if isinstance(val, str):
            # Trio DFR/LS and other new devices: Normalize string and check for boolean-like values
            s = val.strip().lower()
            # Boolean-like strings
            if s in ("true", "false"):
                return s == "true"
            # Numeric string fallback
            if s.isdigit():
                return _AB_NUMERIC.get(int(s))
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
    - Unknown or absent → `None` (the caller must not send the command)

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

    # Unknown format: the caller must not send a command
    _LOGGER.debug("Unexpected getAB format %r (type %s)", raw, type(raw).__name__)
    return None


def parse_alarm_memory(value: SyrConnectStatusValue) -> SyrConnectStatusValue:
    """Alarm memory (getALM): strip the "Alarms:" prefix.

    The "->" before the current alarm stays, it marks the newest entry.

    Formats:
    - SafeTech: "Alarms:->A4 A4 AF AF A3" -> "->A4 A4 AF AF A3"
    - Safe-T+: "Alarms: A5 A5 A6 ->A6 A5" -> "A5 A5 A6 ->A6 A5"
    - Without prefix or no text: "A5" -> "A5", 3 -> 3
    """
    if isinstance(value, str) and value.startswith("Alarms:"):
        return value.removeprefix("Alarms:").lstrip()
    return value


def get_battery_level(status: SyrConnectStatus) -> int | None:
    """Battery level in % from the voltage (getBAT) between getBMI (0 %) and getBMA (100 %).

    Formats:
    - getBAT >= getBMA: 100
    - getBMI < getBAT < getBMA: (getBAT - getBMI) / (getBMA - getBMI) * 100, rounded
    - getBAT <= getBMI: 0

    Returns:
        The level, or None without a positive getBAT, without getBMA/getBMI or with
        getBMI > getBMA
    """
    bat = parse_bat_value(status.get("getBAT"))
    bma = parse_bat_value(status.get("getBMA"))
    bmi = parse_bat_value(status.get("getBMI"))
    if bat is None or bat <= 0 or bma is None or bmi is None or bmi > bma:
        return None
    if bat >= bma:
        return 100
    if bat > bmi:
        return round((bat - bmi) / (bma - bmi) * 100)
    return 0


def is_spurious_bap(status: SyrConnectStatus, value: Any) -> bool:
    """Return True if the battery level (getBAP) is a spurious field next to a voltage.

    Workaround of a firmware bug: some devices report a getBAP of 0 or empty next to a
    real battery voltage (getBAT > 0). Such a getBAP is no battery level. The voltage
    is read in every format of getBAT (`parse_bat_value()`).

    Formats of getBAT:
    - Safe-T+: "6,11 4,38 3,90" -> voltage
    - Safe-Tech+: "9,36" -> voltage
    - Trio DFR/LS: "363" -> voltage
    """
    try:
        bap_zero = float(value) == 0
    except ValueError, TypeError:
        bap_zero = value is None or str(value).strip() == ""
    if not bap_zero:
        return False
    bat_val = status.get("getBAT")
    if bat_val is None:
        return False
    voltage = parse_bat_value(bat_val)
    return voltage is not None and voltage > 0


def parse_mbar_value(value: SyrConnectStatusValue) -> float | None:
    """Pressure (getBAR, getBAR2, getIBA): millibar -> bar.

    Formats:
    - With unit: "4077 mbar" -> 4.077
    """
    if value is None or value == "":
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    return float(match.group()) / 1000


def parse_dbd_value(value: SyrConnectStatusValue) -> float | None:
    """Microleakage pressure drop (getDBD): tenths of a bar -> bar.

    Formats:
    - Tenths: "10" -> 1.0
    - Negative: "-3" -> -0.3
    """
    if value is None or value == "":
        return None
    match = re.search(r"-?\d+", str(value))
    if not match:
        return None
    return float(match.group()) / 10.0


def get_hardness_class(status: SyrConnectStatus) -> str | None:
    """Water hardness range from the conductivity (getCND): key of the range in °dH.

    The hardness is estimated with `CND_PER_DH`:
    - Up to 8 °dH: getCND "245" (7.0 °dH) -> "soft"
    - Up to 14 °dH: getCND "384" (11.0 °dH) -> "medium"
    - Above: getCND "608" (17.4 °dH) -> "hard"

    Returns:
        The key of the range, None without a numeric conductivity
    """
    raw = status.get("getCND")
    if raw is None or raw == "":
        return None
    try:
        hardness = to_float(raw) / CND_PER_DH
    except ValueError, TypeError:
        return None
    if hardness <= 8:
        return "soft"
    if hardness <= 14:
        return "medium"
    return "hard"


def parse_cyt_value(value: SyrConnectStatusValue) -> int | float | None:
    """Remaining regeneration cycle time (getCYT): raw value -> minutes.

    Formats:
    - NeoSoft, Sanibel UNO, Conel Clear Pro Soft: 45 -> 45
    - LEX, L20: "12:30" (minutes:seconds) -> 12.5
    """
    if isinstance(value, str) and ":" in value:
        try:
            minutes, seconds = value.strip().split(":")
            return int(minutes) + int(seconds) / 60
        except ValueError:
            return None
    return parse_int(value)


def parse_dom_value(value: SyrConnectStatusValue) -> SyrConnectStatusValue:
    """Microleakage test valve open time (getDOM): a value in minutes -> seconds.

    Formats:
    - SafeTech: "60" -> "60" (seconds, unchanged)
    - Safe-T+: "1 min" -> 60.0
    - Not a number: "x min" -> None
    """
    if isinstance(value, str) and value.strip().lower().endswith("min"):
        try:
            return float(value.strip()[:-3].strip()) * 60
        except ValueError:
            return None
    return value


def parse_utc_time(value: SyrConnectStatusValue) -> time | None:
    """Time of day the device stores in UTC (getDTT): "HH:MM" -> time.

    Formats:
    - Valid: "04:00" -> 04:00 UTC
    - Invalid: "25:00", "4", "" -> None
    """
    try:
        hour, minute = (int(part) for part in str(value).strip().split(":"))
        return time(hour, minute, tzinfo=UTC)
    except ValueError, TypeError:
        return None


def parse_lar_value(
    signature: SyrConnectModelSignature,
    value: SyrConnectStatusValue,
    time_zone: tzinfo,
) -> datetime | None:
    """Last regeneration (getLAR): UNIX timestamp -> aware datetime.

    The value is a UNIX timestamp in UTC on most devices. The models that set
    `local_time_timestamps` (LEX Plus) encode their local wall time instead, see
    docs/known_issues_xml_api.md, issue 5. Their value is read in the time zone of the
    caller, which gives the offset that applied on that day.

    Formats:
    - Clear Pro Soft: "1794877201" -> 2026-11-17 01:00:01 UTC
    - LEX Plus 10 S (Europe/Berlin): "1795147162" -> 2026-11-20 03:59:22 CET
    - No regeneration yet: "0" -> None

    Args:
        signature: Signature of the model
        value: Value of getLAR
        time_zone: Time zone of the caller, used for local timestamps

    Returns:
        The time of the last regeneration, None without one
    """
    timestamp = parse_int(value)
    if timestamp is None or timestamp == 0:
        return None
    try:
        utc_time = datetime.fromtimestamp(timestamp, UTC)
    except ValueError, OverflowError:
        return None
    if signature.local_time_timestamps:
        return utc_time.replace(tzinfo=time_zone)
    return utc_time


def parse_weekday_mask(value: SyrConnectStatusValue) -> int | None:
    """Permitted weekdays (getRPW): bitmask, bit 1 = Monday ... bit 7 = Sunday.

    Formats:
    - Monday and Friday: "17" -> 17
    - Not specified: "0" -> 0
    - Not a number: "", "x" -> None
    """
    return parse_int(value)


def parse_tmz_value(value: SyrConnectStatusValue) -> timedelta | None:
    """Time zone (getTMZ): offset in quarter hours -> offset to UTC.

    The device accepts -44..48 (UTC-11:00 to UTC+12:00 in steps of 15 minutes).

    Formats:
    - Germany (CET): "4" -> +01:00
    - India: "22" -> +05:30
    - Newfoundland: "-14" -> -03:30
    - Out of range or not a number: "60", "x" -> None
    """
    try:
        quarters = int(str(value).strip())
    except ValueError:
        return None
    if not -44 <= quarters <= 48:
        return None
    return timedelta(minutes=quarters * 15)


def get_serial_number(status: SyrConnectStatus) -> str | None:
    """Return the serial number (getSRN) of a device.

    The cloud reports the same number as `sn` of the device list, before the status;
    the local API has no device list, so its status is the only source.

    Args:
        status: Status of the device, e.g. /get/all of the local API

    Returns:
        The serial number, or None if the device reports no getSRN
    """
    serial = status.get("getSRN")
    return str(serial) if serial else None


def get_current_mac(status: SyrConnectStatus) -> str | None:
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
                wfs_int = to_int(wfs_val)
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


# Numbers of the leak protection profiles. Every profile has the same settings, keyed
# by the setting with the number appended: getPA1-getPA8, getPN1-getPN8, ...
LEAK_PROTECTION_PROFILES = range(1, 9)


def get_active_leak_protection_profiles(status: SyrConnectStatus) -> dict[int, str]:
    """Return the active leak protection profiles (getPAx) with their names (getPNx).

    Formats:
    - getPA1 "true", getPN1 "Home": {1: "Home"}
    - getPA2 "1" without getPN2: {2: "2"}
    - Profile not active (getPA3 "false" or missing): not in the result

    Args:
        status: Status of the device

    Returns:
        Profile number -> name, in ascending order of the number
    """
    profiles: dict[int, str] = {}
    for number in LEAK_PROTECTION_PROFILES:
        if not is_value_true(status.get(f"getPA{number}")):
            continue
        profiles[number] = str(status.get(f"getPN{number}") or number)
    return profiles


def get_current_leak_protection_profile(status: SyrConnectStatus) -> str | None:
    """Return the name (getPNx) of the active leak protection profile (getPRF).

    Formats:
    - getPRF "1", getPN1 "Home": "Home"
    - A name the local API reports as a number: getPN1 3 -> "3"
    - No getPRF, no number or no name of the profile: None
    """
    value = status.get("getPRF")
    number = parse_int(value)
    if number is None:
        return None
    name = status.get(f"getPN{number}")
    return str(name) if name is not None else None


# Device kind (dk) from which the devices report flags as True/False instead of 0/1.
# With the change, the measuring sensor settings (getTSD, getPSD, getCSD) flipped their
# meaning, see docs/syrconnect-protocol.md.
_BOOLEAN_FLAGS_MINIMUM_DK = 1100


def is_measuring_sensor_active(
    signature: SyrConnectModelSignature, value: SyrConnectStatusValue
) -> bool | None:
    """Return whether a measuring sensor is active (getTSD, getPSD, getCSD).

    Formats:
    - dk < 1100: "0" -> active, "1" -> deactivated
    - dk >= 1100: "True" -> active, "False" -> deactivated

    Args:
        signature: Signature of the model, for its device kind (dk)
        value: Value of the setting

    Returns:
        True if the sensor is active, False if deactivated, None for an empty value
    """
    if value is None or str(value).strip() == "":
        return None
    dk = signature.dk
    if dk is not None and dk >= _BOOLEAN_FLAGS_MINIMUM_DK:
        return is_value_true(value)
    return not is_value_true(value)


# Valve motor states (getVLV) while the valve moves
_VLV_CLOSING = 11
_VLV_OPENING = 21


def _valve_state(status: SyrConnectStatus) -> int | None:
    """Return the valve motor state (getVLV) as number, or None."""
    return parse_int(status.get("getVLV"))


def is_valve_opening(status: SyrConnectStatus) -> bool | None:
    """Return True while the valve opens (getVLV 21), None without a valve state."""
    state = _valve_state(status)
    return None if state is None else state == _VLV_OPENING


def is_valve_closing(status: SyrConnectStatus) -> bool | None:
    """Return True while the valve closes (getVLV 11), None without a valve state."""
    state = _valve_state(status)
    return None if state is None else state == _VLV_CLOSING
