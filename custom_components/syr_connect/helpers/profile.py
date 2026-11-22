"""Device profile lookups: allowlists, alarm codes, water hardness and cartridges."""

from collections.abc import Mapping, Set as AbstractSet
import logging
import math
from typing import Any

from ..aiosyrconnect import SyrConnectStatus
from ..devices import WHU_FACTORS_FROM_DH
from ..models import SyrConnectModel

_LOGGER = logging.getLogger(__name__)


def get_model_supported_keys(
    model_info: SyrConnectModel, platform: str, global_supported_keys: set[str]
) -> set[str]:
    """Return the supported-keys allowlist for a platform, scoped to the detected model.

    If the detected model has a `device_profile` (from a `devices/<name>.py` file,
    see `models.MODELS`), its allowlist for the platform is used as a
    POSITIVE, device-specific allowlist instead of `global_supported_keys`.
    Rebranded variants of the same hardware share one profile.
    This is deliberately an allowlist, not an exclusion list — the global
    allowlists of the platform modules cover ~90 different models, and new/unexpected keys can
    show up in any device's API response at any time, so only explicitly
    confirmed keys are trusted per device. Falls back to `global_supported_keys`
    unchanged when the model has no profile, or its profile has no allowlist for
    this platform (an explicit empty set is honored as "no entities of this
    platform for this model", not a fallback trigger).

    Args:
        model_info: Result of `models.detect_model()`.
        platform: Entity domain string (e.g. "sensor", "select", "switch"); the name
            of a `SyrConnectDeviceProfile` allowlist field.
        global_supported_keys: The platform's full/default allowlist.

    Returns:
        The effective allowlist to use for this device.
    """
    profile = model_info.device_profile
    if profile is None:
        return global_supported_keys
    # No default: a platform without a profile field is a programming error.
    device_keys: AbstractSet[str] | None = getattr(profile, platform)
    # None means "not defined" -> fall back. An explicit empty set is a valid
    # override meaning "this model has none of this platform's entities".
    if device_keys is None:
        return global_supported_keys
    return set(device_keys)


def _map_family_code(
    codes: Mapping[str, str] | None, raw_code: Any
) -> tuple[str | None, str]:
    """Map a raw alarm, notification or warning code with the codes of the family.

    Each device family numbers its codes differently; without the codes of the
    family (unknown models) the raw code is kept.

    Args:
        codes: Codes of the device family (raw code -> translation key), or None.
        raw_code: Raw code value from the API (e.g. "FF", "A5", "0").

    Returns:
        (mapped_key, raw_code) where mapped_key is the translation key or None.
    """
    if raw_code is None:
        return (None, "")
    code = str(raw_code)
    if codes is None:
        return (None, code)
    mapped = codes.get(code.strip().upper())
    return (mapped, code) if mapped is not None else (None, code)


def get_sensor_ala_map(model: SyrConnectModel, raw_code: Any) -> tuple[str | None, str]:
    """Map raw getALA alarm code to internal translation key.

    Args:
        model: Detected model of the device (selects the alarm code family).
        raw_code: Raw code value from the API (e.g. "FF", "A5", "0").

    Returns:
        Internal translation key (e.g. "no_alarm", "alarm_salt_supply_low") or None if unknown.
    """
    return _map_family_code(model.ala_codes, raw_code)


def get_whu_unit(model: SyrConnectModel, raw_code: Any) -> str | None:
    """Water hardness unit (getWHU): raw code -> unit of the model's code family.

    Args:
        model: Detected model of the device (selects the code family).
        raw_code: Raw code value from the API (e.g. 0, "1", "2.0").

    Returns:
        The unit (e.g. "°dH"), or None for a missing or unknown code and for a model
        without water hardness unit codes.
    """
    profile = model.device_profile
    code = _whu_code(raw_code)
    if code is None or profile is None or profile.whu_units is None:
        return None
    return profile.whu_units.get(code)


def get_hardness_divisor(model: SyrConnectModel, raw_code: Any) -> int:
    """Divisor of the water hardness values (getIWH, getOWH) for a getWHU code.

    Formats:
    - NeoSoft, mmol/l (getWHU 1): "15" -> 1.5 mmol/l
    - Other units and models: "15" -> 15

    Args:
        model: Detected model of the device (selects the code family).
        raw_code: Raw getWHU value from the API (e.g. 0, "1", "2.0").

    Returns:
        The divisor, 1 if the device reports the values unscaled.
    """
    profile = model.device_profile
    code = _whu_code(raw_code)
    if code is None or profile is None:
        return 1
    return profile.hardness_divisors.get(code, 1)


def get_hardness_range(
    model: SyrConnectModel, key: str, raw_code: Any
) -> tuple[int, int, int] | None:
    """Return the range of a water hardness select for the unit (getWHU), or None.

    Args:
        model: Detected model of the device (its profile holds the ranges).
        key: The water hardness key, e.g. "getIWH".
        raw_code: Raw getWHU value from the API (e.g. 0, "1", "2.0").

    Returns:
        (lowest, highest, step) in the unit of the code, or None if the model has no
        range for the key and unit.
    """
    profile = model.device_profile
    code = _whu_code(raw_code)
    if profile is None or code is None:
        return None
    return profile.hardness_ranges.get(key, {}).get(code)


def get_hardness_factor(model: SyrConnectModel, raw_code: Any) -> float:
    """Factor from the water hardness the device keeps to the unit of the display (getWHU).

    Formats:
    - MuCo filling, °fH (getWHU 2): 1.78480457 (the device keeps °dH)
    - Other models, and a missing or unknown unit: 1.0 (the device keeps the unit)

    Args:
        model: Detected model of the device (its profile tells the unit of the values).
        raw_code: Raw getWHU value from the API (e.g. 0, "1", "2.0").

    Returns:
        The number of display units per unit of the device value.
    """
    profile = model.device_profile
    if profile is None or not profile.hardness_in_dh:
        return 1.0
    unit = get_whu_unit(model, raw_code)
    if unit is None:
        return 1.0
    return WHU_FACTORS_FROM_DH.get(unit, 1.0)


def round_hardness(value: float) -> int:
    """Round a converted water hardness to a whole number, halves up."""
    return math.floor(value + 0.5)


def _whu_code(raw_code: Any) -> int | None:
    """Return the getWHU code as integer, or None for a missing or invalid value."""
    if raw_code is None:
        return None
    try:
        return int(float(raw_code))
    except ValueError, TypeError, OverflowError:
        return None


def get_cartridge_keys(model: SyrConnectModel) -> set[str]:
    """Return the keys that only apply to one cartridge type or size of the model.

    The device profile maps each cartridge type (getCRT) to its key (`cartridge_keys`)
    and each cartridge size (getCRS) to its key (`cartridge_size_keys`):
    - MuCo filling: HWE -> getOHW, HVE/HVE+ -> getLOT
    - All-in-One+: HWE -> getOWH, custom size -> getFCS

    Args:
        model: Detected model of the device.

    Returns:
        The keys, empty for a model without cartridge types or sizes.
    """
    profile = model.device_profile
    if profile is None:
        return set()
    return set(profile.cartridge_keys.values()) | set(
        profile.cartridge_size_keys.values()
    )


def get_reported_cartridge_keys(
    model: SyrConnectModel, status: SyrConnectStatus
) -> set[str]:
    """Return the keys of the reported cartridge type (getCRT) and size (getCRS).

    Args:
        model: Detected model of the device.
        status: The flattened device status.

    Returns:
        The keys the device profile maps the reported cartridge type and size to, empty
        if the model has no key for them.
    """
    profile = model.device_profile
    if profile is None:
        return set()
    keys = set()
    for status_key, key_map in (
        ("getCRT", profile.cartridge_keys),
        ("getCRS", profile.cartridge_size_keys),
    ):
        value = status.get(status_key)
        if value is not None and (key := key_map.get(str(value).strip())) is not None:
            keys.add(key)
    return keys


def get_cartridge_entity_keys(
    model: SyrConnectModel, status: SyrConnectStatus, supported_keys: AbstractSet[str]
) -> set[str]:
    """Return the cartridge keys that become entities for the device.

    Args:
        model: Detected model of the device.
        status: The flattened device status.
        supported_keys: The keys the model lists for the platform.

    Returns:
        The keys of the reported cartridge type and size (see
        `get_reported_cartridge_keys`) that the model lists and that have a value.
    """
    return {
        key
        for key in get_reported_cartridge_keys(model, status)
        if key in supported_keys and status.get(key) not in (None, "")
    }


def get_sensor_not_map(model: SyrConnectModel, raw_code: Any) -> tuple[str | None, str]:
    """Map raw getNOT notification code to internal translation key.

    Args:
        model: Detected model of the device (selects the code family).
        raw_code: Raw code value from the API (e.g. "01", "FF")

    Returns:
        (mapped_key, raw_code) where mapped_key is internal translation key or None
    """
    return _map_family_code(model.not_codes, raw_code)


def get_sensor_wrn_map(model: SyrConnectModel, raw_code: Any) -> tuple[str | None, str]:
    """Map raw getWRN warning code to internal translation key.

    Args:
        model: Detected model of the device (selects the code family).
        raw_code: Raw code value from the API (e.g. "01", "FF")

    Returns:
        (mapped_key, raw_code) where mapped_key is internal translation key or None
    """
    return _map_family_code(model.wrn_codes, raw_code)
