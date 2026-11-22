"""Select platform for SYR Connect (regeneration time wrapper)."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import logging
from typing import Any, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aiosyrconnect import (
    CAS_VALUE_MAP,
    CRS_VALUE_MAP,
    FLUSHING_TEMPERATURE_GAP,
    FLUSHING_TEMPERATURE_RANGES,
    SyrConnectError,
    SyrConnectStatus,
    build_rtm_commands,
    get_active_leak_protection_profiles,
    get_current_leak_protection_profile,
    get_rtm_value,
    parse_hygiene_module_value,
    round_hardness,
    set_command,
    to_float,
)
from .const import DOMAIN
from .coordinator import SyrConnectConfigEntry, SyrConnectDataUpdateCoordinator
from .data import SyrConnectDevice
from .entity import SyrConnectEntity, async_add_device_entities
from .helpers.device import get_device_model
from .helpers.profile import get_cartridge_entity_keys, get_model_supported_keys
from .helpers.registry import find_entity_id, registry_cleanup
from .models import SyrConnectModel
from .sensor import _SYR_CONNECT_SENSOR_DESCRIPTIONS

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the API
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SyrConnectSelectEntityDescription(SelectEntityDescription):
    """Describes a SYR Connect select; `key` is the status key (e.g. "getRMN")."""


# Descriptions of all selects. Which ones a device gets is decided in select.py
# (allowlist of the model and a valid value); options and units are built there.
# The active leak-protection profile (getPRF) is no configuration entity.
_SYR_CONNECT_SELECT_TYPES: tuple[SyrConnectSelectEntityDescription, ...] = (
    # --- Softener ---
    SyrConnectSelectEntityDescription(
        key="getRTM",  # Regeneration time (combined HH:MM string)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getPRF",  # Currently active leak protection profile index
    ),
    SyrConnectSelectEntityDescription(
        key="getSRO",  # Display rotation / orientation (0 / 90 / 180 / 270 degrees)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getSV1",  # Salt amount - container 1 (kg)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getSV2",  # Salt amount - container 2 (kg)
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSelectEntityDescription(
        key="getSV3",  # Salt amount - container 3 (kg)
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSelectEntityDescription(
        key="getRPD",  # Regeneration interval (days)
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    SyrConnectSelectEntityDescription(
        key="getIWH",  # Incoming (raw) water hardness
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getOWH",  # Outgoing (softened) water hardness
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getRMO",  # Regeneration mode (Standard / ECO / Power / Automatic)
        entity_category=EntityCategory.CONFIG,
    ),
    # --- Water treatment / Filling (Conel Clear Pro Fill) ---
    SyrConnectSelectEntityDescription(
        key="getCRS",  # Cartridge size (raw 1-5, mapped to liters)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getCRT",  # Cartridge type (0=HWE, 1=HVE, 2=HVE+)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getCWL",  # Remaining capacity warning threshold (%)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getFCS",  # Custom cartridge size (L), used for getCRS 0
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getFMT",  # Maximum duration of the initial filling (min)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getFVT",  # Maximum volume of the initial filling (L)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getRCD",  # Filling processes period (0=hour, 1=day, 2=week, 3=month)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getRMN",  # Filling processes count
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getRMT",  # Maximum filling duration (min)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getRVT",  # Maximum filling charges
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getTPR",  # Target pressure (1/10 bar)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getLOT",  # Maximum output conductivity (raw x10 µS/cm)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getOHW",  # Soft water hardness (°dH)
        entity_category=EntityCategory.CONFIG,
    ),
    # --- SafeFloor ---
    SyrConnectSelectEntityDescription(
        key="getMIH",  # Minimum humidity threshold (%)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getMXH",  # Maximum humidity threshold (%)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getMIT",  # Minimum temperature threshold (1/10 °C)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getMXT",  # Maximum temperature threshold (1/10 °C)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getALD",  # Duration of alarm (s)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getWMP",  # Measurement interval (s)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getRCP",  # Synchronization interval (s)
        entity_category=EntityCategory.CONFIG,
    ),
    # --- Hygiene flushing (HygBox) ---
    SyrConnectSelectEntityDescription(
        key="getF2T",  # Maximum flushing duration of the temperature flushing (s)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getF2W",  # Stop temperature of the temperature flushing (°C)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getF3P",  # Interval of the periodic flushing (min)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getF3V",  # Flushing volume of the periodic flushing (l)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getMTF",  # Maximum number of temperature flushings per day
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getSTP",  # Stagnation time of the stagnation flushing (min)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getSTV",  # Flushing volume of the stagnation flushing (l)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getTTT",  # Start temperature of the temperature flushing (°C)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getWTY",  # Water type (1=cold water, 2=hot water)
        entity_category=EntityCategory.CONFIG,
    ),
    # --- Hygiene flushing (hygiene module, cold and hot water line) ---
    SyrConnectSelectEntityDescription(
        key="getCCF",  # Periodic flushing of the cold water line (days, 0=off)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getCCL",  # Maximum temperature of the cold water line (°C)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getCSL",  # Flushing volume after which the cold water line stops (l)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getCSS",  # Flushing time after which the cold water line stops (10 s)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getCWF",  # Periodic flushing of the hot water line (days, 0=off)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getSCF",  # Stagnation time of the cold water line (days)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getSWF",  # Stagnation time of the hot water line (days)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getWCL",  # Minimum temperature of the hot water line (°C)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getWSL",  # Flushing volume after which the hot water line stops (l)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getWSS",  # Flushing time after which the hot water line stops (10 s)
        entity_category=EntityCategory.CONFIG,
    ),
    # --- Dosing (Dosing Pump) ---
    SyrConnectSelectEntityDescription(
        key="getCAS",  # Canister size (raw 1-2, mapped to liters)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getDMO",  # Operating mode (0=automatic, 1=running-in, 2=disinfection, 3=low)
        entity_category=EntityCategory.CONFIG,
    ),
    SyrConnectSelectEntityDescription(
        key="getDSL",  # Dosing liquid (1, 2)
        entity_category=EntityCategory.CONFIG,
    ),
)

_SYR_CONNECT_SELECT_DESCRIPTIONS: dict[str, SyrConnectSelectEntityDescription] = {
    description.key: description for description in _SYR_CONNECT_SELECT_TYPES
}


def _option_unit(key: str) -> str:
    """Return the unit of a key for select option labels, from its sensor description.

    Args:
        key: Status key, e.g. "getRMT"

    Returns:
        The unit, e.g. "min"

    Raises:
        ValueError: If the sensor description has no unit; the labels would read "30 None"
    """
    unit = _SYR_CONNECT_SENSOR_DESCRIPTIONS[key].native_unit_of_measurement
    if unit is None:
        raise ValueError(f"No unit for the select options of {key}")
    return unit


# Cartridge size (getCRS): 1=2.5L, 2=4L, 3=7L, 4=14L, 5=30L. Reuses the same
# CRS_VALUE_MAP as the getCRS sensor so raw <-> display stays in one place.
_SYR_CONNECT_SELECT_CRS_MAP = {
    f"{v:g} {_option_unit('getCRS')}": k for k, v in CRS_VALUE_MAP.items()
}
# Canister size of the dosing pump (getCAS): 1=5 L, 2=10 L, from the same value map as the
# getCAS sensor
_SYR_CONNECT_SELECT_CAS_MAP = {
    f"{v:g} {_option_unit('getCAS')}": k for k, v in CAS_VALUE_MAP.items()
}
# All-in-One+: also "custom" (raw 0), whose size in liters is getFCS
_SYR_CONNECT_SELECT_CRS_CUSTOM_MAP = {
    **_SYR_CONNECT_SELECT_CRS_MAP,
    "custom": 0,
}

# Option key of the empty value of the selects whose device reports an empty value:
# status key -> option key (translated by the frontend)
_SYR_CONNECT_SELECT_EMPTY_OPTIONS = {
    "getCRT": "none",
    "getRCD": "undefined",
}


def _setting_values(model: SyrConnectModel, key: str) -> Sequence[int]:
    """Return the raw values of a setting of the model (see `allowed_values()`).

    Raises:
        ValueError: If the library knows no values for the setting
    """
    values = model.allowed_values(key)
    if values is None:
        raise ValueError(f"No values for the setting {key}")
    return values


def _code_options(model: SyrConnectModel, key: str) -> dict[str, int | None]:
    """Return the option map of a select whose options are the raw values.

    The option key is the raw value as text, which the frontend translates (e.g. "2" ->
    "ECO" for getRMO). The value that switches the setting off gets the key "off", a
    negative value the key "minus_<value>": option keys must match hassfest's
    [a-z0-9-_]+ without a leading hyphen. An empty value has an option of its own
    (`_SYR_CONNECT_SELECT_EMPTY_OPTIONS`). The options are in ascending order of the raw
    value, after the option of the empty value.
    """
    options: dict[str, int | None] = {}
    empty_option = _SYR_CONNECT_SELECT_EMPTY_OPTIONS.get(key)
    if empty_option is not None:
        options[empty_option] = None
    off_value = model.off_value(key)
    raw_values = set(_setting_values(model, key))
    if off_value is not None:
        raw_values.add(off_value)
    for raw in sorted(raw_values):
        if raw == off_value:
            options["off"] = raw
        elif raw < 0:
            options[f"minus_{-raw}"] = raw
        else:
            options[str(raw)] = raw
    return options


def _build_time_options(step_minutes: int = 15) -> list[str]:
    """Build list of time strings (HH:MM) for a 24h day with given step."""
    options: list[str] = []
    for h in range(24):
        m = 0
        while m < 60:
            options.append(f"{h:02d}:{m:02d}")
            m += step_minutes
    return options


def _format_scaled(value: int, scale: int) -> str:
    """Format a raw device value for display, dividing by `scale` when != 1."""
    if scale == 1:
        return str(int(value))
    return f"{value / scale:.1f}"


def _is_number(value: Any) -> bool:
    """Return True if a raw device value is present and numeric (e.g. "5" or "5.0").

    The default check before a select is created: a missing, empty or non-numeric
    value could not be shown as the select's current option, so no select is created.

    Args:
        value: Raw value from the device status

    Returns:
        True for a value float() accepts, False for None, "" and anything else
    """
    if value is None or value == "":
        return False
    try:
        float(value)
    except ValueError, TypeError:
        return False
    return True


def _is_integer(value: Any) -> bool:
    """Return True if a raw device value is present and converts to an integer (e.g. "90" or "90.0").

    Used instead of `_is_number` for selects whose current option is looked up by the
    integer value (getSRO, getCRS, getRMO).

    Args:
        value: Raw value from the device status

    Returns:
        True for a value int(float()) accepts, False for None, "" and anything else
    """
    return _to_int(value) is not None


def _to_int(value: Any) -> int | None:
    """Return a raw device value as an integer (e.g. "90" or "90.0" -> 90).

    Args:
        value: Raw value from the device status

    Returns:
        The integer, or None for None, "" and anything int(float()) does not accept
    """
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError, TypeError, OverflowError:
        return None


def _is_hygiene_module_value(value: Any) -> bool:
    """Return True if a raw hygiene module setting holds a number (e.g. "3" or "3 [1-7]").

    Args:
        value: Raw value from the device status

    Returns:
        True if `parse_hygiene_module_value` finds a number, False otherwise
    """
    return parse_hygiene_module_value(value) is not None


def _unit_options(key: str, values: Sequence[int]) -> list[str]:
    """Return option labels with the key's unit suffix, e.g. "30 min".

    Args:
        key: Status key whose unit is used (from its sensor description)
        values: Raw option values

    Returns:
        One label per value, in the same order
    """
    unit = _option_unit(key)
    return [f"{v} {unit}" for v in values]


class _SyrConnectSelectBuilder:
    """Collect the select entities of one device.

    Holds the device's coordinator, id, name and status, so each block in the
    `_add_*_selects` functions only names what differs (key, range or option map).
    """

    def __init__(
        self, coordinator: SyrConnectDataUpdateCoordinator, device: SyrConnectDevice
    ) -> None:
        """Initialize the builder for one device from the coordinator data."""
        self.coordinator = coordinator
        self.device_id = device["id"]
        self.device_name = device["name"]
        self.status: SyrConnectStatus = device.get("status", {})
        # Only the selects of the device file of the detected model; a model without
        # one has no selects.
        self.model_info = get_device_model(device)
        self.supported_select_keys = get_model_supported_keys(
            self.model_info, "select", set()
        )
        self.entities: list[SelectEntity] = []

    def allowed(self, key: str, is_valid: Callable[[Any], bool] = _is_number) -> bool:
        """Return True if the model lists `key` and the device reports a valid value for it.

        Args:
            key: Status key, e.g. "getRMN"
            is_valid: Check for the raw value; default `_is_number`
        """
        return key in self.supported_select_keys and is_valid(self.status.get(key))

    def add_discrete(self, key: str, options_map: Mapping[str, int | None]) -> None:
        """Add a select with a fixed option map (option key -> raw value).

        Args:
            key: Status key, e.g. "getCRT"
            options_map: Option keys as shown (or translated) mapped to raw device values
        """
        self.entities.append(
            SyrConnectDiscreteSelect(
                self.coordinator, self.device_id, self.device_name, key, options_map
            )
        )

    def add_numeric(
        self, key: str, min_value: int, max_value: int, **kwargs: Any
    ) -> None:
        """Add a select with the raw values min_value..max_value in steps of 1.

        Args:
            key: Status key, e.g. "getRMN"
            min_value: Lowest raw value
            max_value: Highest raw value
            **kwargs: Passed to SyrConnectNumericSelect (`scale`, `options`)
        """
        self.entities.append(
            SyrConnectNumericSelect(
                self.coordinator,
                self.device_id,
                self.device_name,
                key,
                min_value,
                max_value,
                1,
                **kwargs,
            )
        )

    def add_numeric_steps(self, key: str, values: Sequence[int]) -> None:
        """Add a numeric select with a non-uniform list of steps, labeled with the unit.

        Args:
            key: Status key, e.g. "getRMT"
            values: Raw values in ascending order (e.g. `allowed_values("getRMT")`)
        """
        self.add_numeric(key, values[0], values[-1], options=_unit_options(key, values))

    def offer_discrete(
        self,
        key: str,
        options_map: Mapping[str, int | None],
        is_valid: Callable[[Any], bool] = _is_number,
    ) -> None:
        """Add a select with a fixed option map if `allowed` (see add_discrete).

        Args:
            key: Status key, e.g. "getCRT"
            options_map: Option keys as shown (or translated) mapped to raw device values
            is_valid: Check for the raw value; default `_is_number`
        """
        if self.allowed(key, is_valid):
            self.add_discrete(key, options_map)

    def offer_numeric(
        self, key: str, min_value: int, max_value: int, **kwargs: Any
    ) -> None:
        """Add a select with the raw values min_value..max_value if `allowed` (see add_numeric).

        Args:
            key: Status key, e.g. "getRMN"
            min_value: Lowest raw value
            max_value: Highest raw value
            **kwargs: Passed to SyrConnectNumericSelect (`scale`, `options`)
        """
        if self.allowed(key):
            self.add_numeric(key, min_value, max_value, **kwargs)

    def offer_numeric_steps(self, key: str) -> None:
        """Add a numeric select with the steps of the setting if `allowed`.

        The steps are the raw values of the model (`allowed_values()`), labeled with the
        unit of the key (see add_numeric_steps).

        Args:
            key: Status key, e.g. "getRMT"
        """
        if self.allowed(key):
            self.add_numeric_steps(key, _setting_values(self.model_info, key))

    def offer_numeric_range(self, key: str, **kwargs: Any) -> None:
        """Add a select from the lowest to the highest raw value of the setting if `allowed`.

        For the settings whose raw values have steps of 1 (see add_numeric).

        Args:
            key: Status key, e.g. "getRMN"
            **kwargs: Passed to SyrConnectNumericSelect (`scale`, `options`)
        """
        values = _setting_values(self.model_info, key)
        self.offer_numeric(key, values[0], values[-1], **kwargs)

    def offer_codes(
        self, key: str, is_valid: Callable[[Any], bool] = _is_number
    ) -> None:
        """Add a select whose options are the raw values of the setting if `allowed`.

        Args:
            key: Status key, e.g. "getRMO"
            is_valid: Check for the raw value; default `_is_number`
        """
        if self.allowed(key, is_valid):
            self.add_discrete(key, _code_options(self.model_info, key))


def _build_device_selects(
    coordinator: SyrConnectDataUpdateCoordinator, device: SyrConnectDevice
) -> list[SelectEntity]:
    """Return the selects of one device (except the conditional cartridge keys).

    A select is only created when the detected model lists its key and the device
    reports a valid value for it. The `_add_*_selects` functions add them by topic, in a
    fixed order.

    Args:
        coordinator: Data update coordinator
        device: Device entry from the coordinator data (id, name, status)

    Returns:
        The select entities to add for this device
    """
    builder = _SyrConnectSelectBuilder(coordinator, device)
    _add_device_setting_selects(builder)
    _add_regeneration_selects(builder)
    _add_salt_selects(builder)
    _add_hardness_selects(builder)
    _add_muco_selects(builder)
    _add_safefloor_selects(builder)
    _add_hygbox_selects(builder)
    _add_hygiene_module_selects(builder)
    _add_dosing_pump_selects(builder)
    return builder.entities


def _add_device_setting_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the selects for the active leak protection profile and the display rotation."""
    # Active leak-protection profile (getPRF), if any profile getPAx is active (e.g. "true" or "1")
    if "getPRF" in b.supported_select_keys and get_active_leak_protection_profiles(
        b.status
    ):
        b.entities.append(
            SyrConnectPrfSelect(b.coordinator, b.device_id, b.device_name)
        )

    # Display rotation (getSRO): 0, 90, 180, 270; accepts numeric-like values ("90" or "90.0")
    if b.allowed("getSRO", _is_integer):
        b.entities.append(
            SyrConnectRotationSelect(b.coordinator, b.device_id, b.device_name)
        )


def _add_regeneration_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the selects for the regeneration time, interval and mode."""
    # Regeneration time (getRTM): may contain a combined HH:MM string when `getRTH` is
    # not provided, or act as minutes when `getRTH` is present.
    if b.allowed("getRTM", lambda v: v is not None and v != ""):
        b.entities.append(
            SyrConnectRegenerationSelect(b.coordinator, b.device_id, b.device_name)
        )

    # Regeneration interval in days (getRPD): the maximum depends on the model; models without
    # regeneration have none. 0 means no interval regeneration, so no select is created.
    max_rpd = b.model_info.maximum_regeneration_interval
    if (
        max_rpd is not None
        and b.allowed("getRPD")
        and to_float(b.status["getRPD"]) != 0
    ):
        b.add_numeric("getRPD", 1, max_rpd)

    # Regeneration mode (getRMO), only for a value >= 1
    if b.allowed("getRMO", _is_integer) and int(to_float(b.status["getRMO"])) >= 1:
        b.add_discrete("getRMO", _code_options(b.model_info, "getRMO"))


def _add_salt_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the selects for the salt amounts (getSV1-3).

    The maximum depends on the model; models without salt containers have none.
    """
    max_capacity = b.model_info.maximum_salt_volume
    if max_capacity is None:
        return
    for sv_key in ("getSV1", "getSV2", "getSV3"):
        b.offer_numeric(sv_key, 0, max_capacity)


def _add_hardness_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the selects for the raw (getIWH, 1-100) and the soft water hardness (getOWH, 0-100).

    Plain LEX family, MuCo filling and All-in-One+ (see docs/syrconnect-protocol.md). The
    unit suffix follows the device's getWHU setting. On the MuCo filling and the
    All-in-One+, the ranges depend on the unit, and the soft water hardness (getOHW,
    getOWH) is that of the HWE cartridge, added by _async_setup_muco_conditional_selects.
    """
    cartridge_keys = b.model_info.cartridge_dependent_keys
    for hardness_key in ("getIWH", "getOWH"):
        if not b.allowed(hardness_key) or hardness_key in cartridge_keys:
            continue
        if hardness_key in b.model_info.hardness_ranges:
            b.entities.append(
                SyrConnectRangedHardnessSelect(
                    b.coordinator, b.device_id, b.device_name, hardness_key
                )
            )
        else:
            values = _setting_values(b.model_info, hardness_key)
            b.entities.append(
                SyrConnectHardnessSelect(
                    b.coordinator,
                    b.device_id,
                    b.device_name,
                    hardness_key,
                    values[0],
                    values[-1],
                    1,
                )
            )


def _add_muco_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the MuCo selects for the water treatment / filling mode configuration.

    getLOT and getOHW are mutually exclusive depending on cartridge type, and the custom
    cartridge size (getFCS) only applies to getCRS "custom". They are handled separately
    (_async_setup_muco_conditional_selects), which adds/removes whichever one currently
    applies instead of creating it and showing it as unavailable.
    """
    # Cartridge size (getCRS); a model with a custom size (getFCS) also offers "custom"
    b.offer_discrete(
        "getCRS",
        _SYR_CONNECT_SELECT_CRS_CUSTOM_MAP
        if "getFCS" in b.supported_select_keys
        else _SYR_CONNECT_SELECT_CRS_MAP,
        _is_integer,
    )
    # getCRT and getRCD have an option for the empty value, so any reported value counts
    for key in ("getCRT", "getRCD"):
        if key in b.supported_select_keys and key in b.status:
            b.add_discrete(key, _code_options(b.model_info, key))
    # Remaining capacity warning threshold (getCWL) in %
    b.offer_numeric_steps("getCWL")
    # Filling processes count (getRMN)
    b.offer_numeric_range("getRMN")
    # Maximum filling duration (getRMT) and charges (getRVT): non-uniform minute/liter steps
    # (see docs/syrconnect-protocol.md); the All-in-One+ has other getRMT steps
    b.offer_numeric_steps("getRMT")
    b.offer_numeric_steps("getRVT")
    # Initial filling (All-in-One+): maximum volume (getFVT, same steps as getRVT) and
    # maximum duration (getFMT)
    b.offer_numeric_steps("getFVT")
    b.offer_numeric_steps("getFMT")
    # Target pressure (getTPR): the raw value is stored as 1/10 bar
    b.offer_numeric_range("getTPR", scale=10)


def _add_safefloor_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the SafeFloor selects: alarm/humidity/temperature thresholds and sync/measurement intervals."""
    # Thresholds; the labels (including the "Off" text) come from the translation "state"
    # map of each select
    b.offer_codes("getMIH")
    b.offer_codes("getMXH")
    b.offer_codes("getMIT")
    b.offer_codes("getMXT")
    # Alarm duration (getALD): documented GUI Settings step list (see docs/syrconnect-protocol.md)
    b.offer_numeric_steps("getALD")
    b.offer_codes("getWMP")
    # Synchronization interval (getRCP); the HygBox offers a part of the steps
    b.offer_codes("getRCP")


def _add_hygbox_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the HygBox selects: water type and the stagnation, temperature and periodic flushing."""
    b.offer_codes("getWTY", _is_integer)
    # Stagnation flushing: stagnation time (getSTP) and flushing volume (getSTV)
    b.offer_numeric_steps("getSTP")
    b.offer_numeric_steps("getSTV")
    # Temperature flushing: start and stop temperature (getTTT, getF2W), whose range follows
    # the water type, maximum duration (getF2T) and flushings per day (getMTF)
    for temperature_key in ("getTTT", "getF2W"):
        if b.allowed(temperature_key):
            b.entities.append(
                SyrConnectFlushingTemperatureSelect(
                    b.coordinator, b.device_id, b.device_name, temperature_key
                )
            )
    b.offer_numeric_steps("getF2T")
    b.offer_numeric_range("getMTF")
    # Periodic flushing: interval (getF3P) and flushing volume (getF3V)
    b.offer_numeric_steps("getF3P")
    b.offer_numeric_steps("getF3V")


def _add_hygiene_module_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the hygiene module selects: the five settings of the cold and the hot water line.

    The temperature limits (getCCL, getWCL) differ between the hygiene module and the
    Safe-T Hygiene module and come from the signature of the model only.
    """
    for key in (
        "getSCF",
        "getSWF",
        "getCCF",
        "getCWF",
        "getCCL",
        "getWCL",
        "getCSS",
        "getWSS",
        "getCSL",
        "getWSL",
    ):
        values = b.model_info.allowed_values(key)
        if values is None or not b.allowed(key, _is_hygiene_module_value):
            continue
        # Option labels in the unit of the sensor, e.g. "60 s" for the raw value 6 of getCSS
        unit = _option_unit(key)
        factor = _SYR_CONNECT_SENSOR_DESCRIPTIONS[key].multiply_by
        options_map: dict[str, int | None] = {
            f"{value * factor} {unit}": value for value in values
        }
        off_value = b.model_info.off_value(key)
        if off_value is not None:
            options_map = {"off": off_value, **options_map}
        b.entities.append(
            SyrConnectHygieneModuleSelect(
                b.coordinator,
                b.device_id,
                b.device_name,
                key,
                options_map,
                off_value,
            )
        )


def _add_dosing_pump_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the dosing pump selects: canister size, dosing liquid and operating mode."""
    b.offer_discrete("getCAS", _SYR_CONNECT_SELECT_CAS_MAP, _is_integer)
    b.offer_codes("getDSL", _is_integer)
    b.offer_codes("getDMO", _is_integer)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SyrConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for SYR Connect."""
    _LOGGER.debug("Setting up SYR Connect select entities")
    coordinator = entry.runtime_data

    registry_cleanup(
        hass,
        coordinator.data,
        "select",
        allowed_keys=set(),
        entry_id=coordinator.entry_id,
        # The selects of the other cartridge types; their unique_id has the "_select" suffix
        hidden_keys=lambda status, model: {
            f"{key}_select"
            for key in model.cartridge_dependent_keys
            - model.reported_cartridge_keys(status)
        },
    )

    async_add_device_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda device: _build_device_selects(coordinator, device),
    )

    _async_setup_muco_conditional_selects(hass, entry, coordinator, async_add_entities)


def _async_setup_muco_conditional_selects(
    hass: HomeAssistant,
    entry: SyrConnectConfigEntry,
    coordinator: SyrConnectDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Dynamically add/remove the cartridge selects depending on the cartridge type and size.

    getLOT (HVE/HVE+) and the soft water hardness (HWE; getOHW, getOWH on the All-in-One+)
    are mutually exclusive: only one ever applies for a given cartridge type (getCRT). The
    custom cartridge size (getFCS) only applies to getCRS "custom". Instead of creating both and showing the inapplicable one
    as permanently grayed-out "unavailable", only the currently-relevant entity is added; the
    other is removed from the entity registry. Re-evaluated on every coordinator update, so
    switching getCRT (which optimistically updates coordinator.data immediately) swaps the
    visible entity right away, without requiring an integration reload.
    """
    # Per-device set of currently added keys ("getLOT" / "getOHW")
    live_keys: dict[str, set[str]] = {}

    def _wanted_keys(status: SyrConnectStatus, model: SyrConnectModel) -> set[str]:
        # Only for models whose profile maps the cartridge types or sizes to keys (MuCo
        # filling, All in One +). Leak-protection and TrioLock devices also report
        # getCRT/getLOT/getOHW but deliberately do not expose them; a select there would
        # even write setOHW/setLOT.
        supported_select_keys = get_model_supported_keys(model, "select", set())
        return get_cartridge_entity_keys(model, status, supported_select_keys)

    def _build_entity(
        device_id: str, device_name: str, model: SyrConnectModel, key: str
    ) -> SyrConnectDiscreteSelect | SyrConnectNumericSelect:
        if key == "getLOT":
            lot_unit = _option_unit("getLOT")
            lot_map: dict[str, int | None] = {
                f"{raw * 10} {lot_unit}": raw
                for raw in _setting_values(model, "getLOT")
            }
            return SyrConnectDiscreteSelect(
                coordinator, device_id, device_name, "getLOT", lot_map
            )
        if key == "getFCS":
            # Custom cartridge size in liters
            fcs_values = _setting_values(model, "getFCS")
            return SyrConnectNumericSelect(
                coordinator,
                device_id,
                device_name,
                "getFCS",
                fcs_values[0],
                fcs_values[-1],
                1,
                options=_unit_options("getFCS", fcs_values),
            )
        return SyrConnectRangedHardnessSelect(coordinator, device_id, device_name, key)

    @callback
    def _sync() -> None:
        new_entities: list[SyrConnectDiscreteSelect | SyrConnectNumericSelect] = []
        try:
            registry = er.async_get(hass)
            for device in (
                coordinator.data.get("devices", []) if coordinator.data else []
            ):
                device_id = device["id"]
                device_name = device["name"]
                status = device.get("status", {})
                current = live_keys.setdefault(device_id, set())
                model = get_device_model(device)
                wanted_set = _wanted_keys(status, model)

                for key in current - wanted_set:
                    # Selects use the "<key>_select" unique_id suffix (see SyrConnectDiscreteSelect/NumericSelect)
                    stale_entity_id = find_entity_id(
                        registry,
                        "select",
                        coordinator.entry_id,
                        device_id,
                        f"{key}_select",
                    )
                    if stale_entity_id is not None:
                        _LOGGER.debug(
                            "Removing conditionally hidden select from registry: %s",
                            stale_entity_id,
                        )
                        registry.async_remove(stale_entity_id)
                    current.discard(key)

                for key in sorted(wanted_set - current):
                    new_entities.append(
                        _build_entity(device_id, device_name, model, key)
                    )
                    current.add(key)
        except Exception:
            _LOGGER.exception("Failed to sync conditional MuCo select(s)")
            return

        if new_entities:
            _LOGGER.debug("Adding %d conditional MuCo select(s)", len(new_entities))
            async_add_entities(new_entities)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))


class SyrConnectRegenerationSelect(SyrConnectEntity, SelectEntity):
    """Select entity exposing regeneration time as a choice list.

    This provides a Control-friendly domain for users who prefer the
    Controls/Steuerelemente view. Selecting an option sends the
    corresponding `setRTH`/`setRTM` commands via the coordinator.
    """

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the select entity."""
        # Translation key "getrtm" for the human-friendly name; the select is backed by `getRTM`
        super().__init__(
            coordinator,
            device_id,
            device_name,
            "select",
            "getRTM",
            unique_key="getRTM_select",
        )

        # Options: 15 minute steps by default
        self._options = _build_time_options(15)

        self.entity_description = _SYR_CONNECT_SELECT_DESCRIPTIONS["getRTM"]

        _LOGGER.debug(
            "Created SyrConnectRegenerationSelect object: device=%s name=%s unique_id=%s",
            self._device_id,
            self._device_name,
            self._attr_unique_id,
        )

    @property
    @override
    def options(self) -> list[str]:
        """Return the selectable options."""
        return self._options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently configured regeneration time as HH:MM."""
        if self._device is None:
            return None
        return get_rtm_value(self._status)

    @override
    async def async_select_option(self, option: str) -> None:
        """Called when user selects a time option from the UI."""
        coordinator = self.coordinator
        commands = build_rtm_commands(self._status, option)
        if not commands:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_option",
                translation_placeholders={
                    "entity": self._entity_name,
                    "option": option,
                },
            )

        try:
            # setRTH + setRTM in one call: with the XML API a single request, so the time
            # is never left half-changed (new hour, old minute) when the request fails
            await coordinator.async_set_device_values(self._device_id, commands)
            _LOGGER.debug(
                "Requested regeneration time set commands for device %s: %s",
                self._device_id,
                commands,
            )
            _LOGGER.debug(
                "Regeneration time select changed for %s to %s", self._device_id, option
            )
        except SyrConnectError as err:
            _LOGGER.error(
                "Failed to set regeneration time for device %s: %s",
                self._device_id,
                err,
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_value_failed",
                translation_placeholders={
                    "device": self._device_name,
                    "entity": self._entity_name,
                },
            ) from err


class SyrConnectNumericSelect(SyrConnectEntity, SelectEntity):
    """Select entity representing a numeric control.

    Options are stringified integers between min_value and max_value
    with the given step. Selecting an option sends `set<KEY>` via the coordinator.

    Args:
        coordinator: Data update coordinator
        device_id: Device ID (serial number)
        device_name: Device display name
        sensor_key: Status key, e.g. "getRMN"
        min_value: Lowest raw value of the generated options
        max_value: Highest raw value of the generated options
        step: Step between the generated options
        scale: Divisor for display (raw 18 with scale 10 is shown as "1.8")
        options: Explicit option labels instead of the generated range, e.g. for
            non-uniform steps. Each label must start with the number, optionally
            followed by a unit ("30 min"); the number is what is written to the device.
    """

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
        min_value: int,
        max_value: int,
        step: int = 1,
        scale: int = 1,
        options: list[str] | None = None,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(
            coordinator,
            device_id,
            device_name,
            "select",
            sensor_key,
            unique_key=f"{sensor_key}_select",
        )
        self._sensor_key = sensor_key
        # Raw device values are divided by `scale` for display and multiplied back when writing
        # (e.g. getTPR is stored as 1/10 bar, so scale=10 shows "1.8 bar" for the raw value 18).
        self._scale = scale

        self.entity_description = _SYR_CONNECT_SELECT_DESCRIPTIONS[sensor_key]

        # Determine unit label (if available) and build options (append unit for readability)
        unit_label = _SYR_CONNECT_SENSOR_DESCRIPTIONS[
            self._sensor_key
        ].native_unit_of_measurement

        opts: list[str] = []
        v = min_value
        while v <= max_value:
            label = _format_scaled(v, self._scale)
            if unit_label:
                opts.append(f"{label} {unit_label}")
            else:
                opts.append(label)
            v += step
        # Explicit option labels replace the generated range (e.g. non-uniform steps)
        self._options = options if options is not None else opts

        _LOGGER.debug(
            "Created SyrConnectNumericSelect object: device=%s key=%s unique_id=%s",
            self._device_id,
            self._sensor_key,
            self._attr_unique_id,
        )

    @property
    @override
    def options(self) -> list[str]:
        """Return the selectable options."""
        return self._options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if self._device is None:
            return None
        val = self._status.get(self._sensor_key)
        if val is None or val == "":
            return None
        try:
            num = int(to_float(val))
            # Return the option whose number (first token; options may carry a unit suffix,
            # e.g. "20 s") equals the scaled display value. Same parsing as async_select_option.
            # A prefix match would wrongly pick "20 s" for the value 2.
            label = _format_scaled(num, self._scale)
            for opt in self._options:
                if opt.split(" ", 1)[0] == label:
                    return opt
        except ValueError, TypeError, AttributeError, OverflowError:
            return None
        else:
            return label

    def _raw_value(self, value: float) -> int:
        """Return the raw device value of the number of an option."""
        return round(value * self._scale)

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the device."""
        try:
            # Option may include a unit suffix (e.g., '2 days'), so parse first token
            token = str(option).split()[0]
            val = self._raw_value(float(token))
        except (IndexError, OverflowError, ValueError) as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_option",
                translation_placeholders={
                    "entity": self._entity_name,
                    "option": option,
                },
            ) from err

        coordinator = self.coordinator
        # key for setting: remove leading 'get' and prefix with 'set'
        set_key = set_command(self._sensor_key)
        try:
            await coordinator.async_set_device_value(self._device_id, set_key, val)
            _LOGGER.debug(
                "Requested %s for device %s (value=%s)", set_key, self._device_id, val
            )
            _LOGGER.debug(
                "Select %s changed for device %s to %s",
                self._sensor_key,
                self._device_id,
                option,
            )
        except SyrConnectError as err:
            _LOGGER.error(
                "Failed to set %s for device %s: %s", set_key, self._device_id, err
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_value_failed",
                translation_placeholders={
                    "device": self._device_name,
                    "entity": self._entity_name,
                },
            ) from err


class SyrConnectFlushingTemperatureSelect(SyrConnectNumericSelect):
    """Start or stop temperature of the temperature flushing (getTTT, getF2W, HygBox).

    The range depends on the water type (getWTY): 10-25 °C for cold water, 50-60 °C for hot
    water. Cold water is flushed when it gets warmer than the start temperature, until it
    is cooled down to the stop temperature; hot water when it gets colder, until it is
    heated up again. The start and the stop temperature keep a distance of 2 °C, so the
    options of one key follow the current value of the other.
    """

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
    ) -> None:
        """Initialize the select entity."""
        low = min(low for low, _high in FLUSHING_TEMPERATURE_RANGES.values())
        high = max(high for _low, high in FLUSHING_TEMPERATURE_RANGES.values())
        super().__init__(coordinator, device_id, device_name, sensor_key, low, high)
        self._unit = _option_unit(sensor_key)

    def _range(self) -> tuple[int, int] | None:
        """Return the lowest and highest temperature that can be selected now."""
        water_type = _to_int(self._status.get("getWTY"))
        temperature_range = (
            FLUSHING_TEMPERATURE_RANGES.get(water_type)
            if water_type is not None
            else None
        )
        if temperature_range is None:
            return None
        low, high = temperature_range
        is_start = self._sensor_key == "getTTT"
        other = _to_int(self._status.get("getF2W" if is_start else "getTTT"))
        if other is not None:
            # Cold water: the start temperature is above the stop temperature; hot water:
            # below it
            if is_start == (water_type == 1):
                low = max(low, other + FLUSHING_TEMPERATURE_GAP)
            else:
                high = min(high, other - FLUSHING_TEMPERATURE_GAP)
        return (low, high) if low <= high else None

    @property
    @override
    def options(self) -> list[str]:
        """Return the selectable options."""
        temperature_range = self._range()
        if temperature_range is None:
            return []
        low, high = temperature_range
        return [f"{value} {self._unit}" for value in range(low, high + 1)]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        value = _to_int(self._status.get(self._sensor_key)) if self._device else None
        if value is None:
            return None
        option = f"{value} {self._unit}"
        return option if option in self.options else None


class SyrConnectHardnessSelect(SyrConnectNumericSelect):
    """Water hardness select (`getIWH`/`getOWH`) with the unit taken from the live `getWHU` setting."""

    def _unit_label(self) -> str:
        return self.device_model.whu_unit(self._status.get("getWHU")) or ""

    @property
    @override
    def options(self) -> list[str]:
        """Return the selectable options."""
        unit = self._unit_label()
        return [f"{opt} {unit}" if unit else opt for opt in self._options]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        value = super().current_option
        if value is None:
            return None
        unit = self._unit_label()
        return f"{value} {unit}" if unit else value


class SyrConnectRangedHardnessSelect(SyrConnectHardnessSelect):
    """Water hardness select whose range follows the live `getWHU` unit.

    The ranges come from the signature of the model (`hardness_ranges`). The soft water hardness
    (getOWH, getOHW on the MuCo) can be at most the raw water hardness (getIWH) and is
    lowered with it. The MuCo keeps the values in °dH (`hardness_in_dh`); they are
    converted to the unit and back.
    """

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(
            coordinator, device_id, device_name, sensor_key, 0, 0, options=[]
        )

    @property
    @override
    def options(self) -> list[str]:
        """Return the selectable options for the current unit."""
        hardness_range = self.device_model.hardness_range(
            self._sensor_key, self._status.get("getWHU")
        )
        if hardness_range is None:
            return []
        lowest, highest, step = hardness_range
        if self._sensor_key != "getIWH" and _is_integer(self._status.get("getIWH")):
            raw_water = int(to_float(self._status["getIWH"]))
            highest = min(highest, round_hardness(raw_water * self._factor()))
        unit = self._unit_label()
        return [
            f"{value} {unit}" if unit else str(value)
            for value in range(lowest, highest + 1, step)
        ]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        factor = self._factor()
        hardness_range = self.device_model.hardness_range(
            self._sensor_key, self._status.get("getWHU")
        )
        raw = self._status.get(self._sensor_key)
        if factor == 1 or hardness_range is None or raw is None or not _is_number(raw):
            return super().current_option
        lowest, _, step = hardness_range
        value = round_hardness(to_float(raw) * factor)
        # A converted value can lie between two steps of the unit (ppm): the step below
        value = lowest + max(value - lowest, 0) // step * step
        return f"{value} {self._unit_label()}"

    def _factor(self) -> float:
        return self.device_model.hardness_factor(self._status.get("getWHU"))

    @override
    def _raw_value(self, value: float) -> int:
        """Return the raw device value of the number of an option."""
        return round_hardness(value / self._factor())

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the device.

        A raw water hardness (getIWH) below the soft water hardness lowers the soft
        water hardness to the same value.
        """
        await super().async_select_option(option)
        if self._sensor_key != "getIWH":
            return
        raw_water = self._raw_value(float(option.split(maxsplit=1)[0]))
        for soft_key in ("getOHW", "getOWH"):
            soft = self._status.get(soft_key)
            if (
                self.device_model.hardness_range(soft_key, self._status.get("getWHU"))
                is None
                or soft is None
                or not _is_integer(soft)
                or int(to_float(soft)) <= raw_water
            ):
                continue
            set_key = set_command(soft_key)
            try:
                await self.coordinator.async_set_device_value(
                    self._device_id, set_key, raw_water
                )
            except SyrConnectError as err:
                _LOGGER.error(
                    "Failed to set %s for device %s: %s", set_key, self._device_id, err
                )
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="set_value_failed",
                    translation_placeholders={
                        "device": self._device_name,
                        "entity": self._entity_name,
                    },
                ) from err


class SyrConnectRotationSelect(SyrConnectEntity, SelectEntity):
    """Select entity exposing display rotation (`getSRO`).

    Options: raw state keys 0, 90, 180, 270 — frontend shows translated labels; selecting sends `setSRO`.
    """

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(
            coordinator,
            device_id,
            device_name,
            "select",
            "getSRO",
            unique_key="getSRO_select",
        )

        # Use raw state keys so the frontend will translate them via the translation files
        self._options = ["0", "90", "180", "270"]

        self.entity_description = _SYR_CONNECT_SELECT_DESCRIPTIONS["getSRO"]

        _LOGGER.debug(
            "Created SyrConnectRotationSelect object: device=%s name=%s unique_id=%s",
            self._device_id,
            self._device_name,
            self._attr_unique_id,
        )

    @property
    @override
    def options(self) -> list[str]:
        """Return the selectable options."""
        return self._options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if self._device is None:
            return None
        val = self._status.get("getSRO")
        if val is None or val == "":
            return None
        try:
            num = int(to_float(val))
            # Return matching raw option (string)
            for opt in self._options:
                if opt.startswith(f"{num}"):
                    return opt
            return str(num)
        except ValueError, TypeError, AttributeError, OverflowError:
            return None

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the device."""
        try:
            val = int(option)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_option",
                translation_placeholders={
                    "entity": self._entity_name,
                    "option": option,
                },
            ) from err

        coordinator = self.coordinator
        set_key = "setSRO"
        try:
            await coordinator.async_set_device_value(self._device_id, set_key, val)
            _LOGGER.debug(
                "Requested %s for device %s (value=%s)", set_key, self._device_id, val
            )
            _LOGGER.debug(
                "Select getSRO changed for device %s to %s", self._device_id, option
            )
        except SyrConnectError as err:
            _LOGGER.error(
                "Failed to set %s for device %s: %s", set_key, self._device_id, err
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_value_failed",
                translation_placeholders={
                    "device": self._device_name,
                    "entity": self._entity_name,
                },
            ) from err


class SyrConnectDiscreteSelect(SyrConnectEntity, SelectEntity):
    """Select entity for discrete, non-sequential option maps (e.g., getRMO)."""

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
        options_map: Mapping[str, int | None],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(
            coordinator,
            device_id,
            device_name,
            "select",
            sensor_key,
            unique_key=f"{sensor_key}_select",
        )
        self._sensor_key = sensor_key
        self._options_map = options_map

        # Options are the raw state keys (strings) of the mapping so the frontend
        # can translate the displayed state using the integration translations.
        self._options = list(options_map.keys())

        self.entity_description = _SYR_CONNECT_SELECT_DESCRIPTIONS[sensor_key]

        _LOGGER.debug(
            "Created SyrConnectDiscreteSelect object: device=%s key=%s unique_id=%s",
            self._device_id,
            self._sensor_key,
            self._attr_unique_id,
        )

    @property
    @override
    def options(self) -> list[str]:
        """Return the selectable options."""
        return self._options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if self._device is None:
            return None
        val = self._status.get(self._sensor_key)
        if val is None or val == "":
            # Some option maps include a sentinel entry (value=None, e.g. "undefined")
            # representing this empty raw state instead of falling back to unknown.
            for opt, mapped in self._options_map.items():
                if mapped is None:
                    return opt
            return None
        try:
            num = int(to_float(val))
        except ValueError, TypeError, OverflowError:
            return None
        for opt, mapped in self._options_map.items():
            if mapped == num:
                return opt
        return None

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the device."""
        if option not in self._options_map:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_option",
                translation_placeholders={
                    "entity": self._entity_name,
                    "option": option,
                },
            )
        val = self._options_map[option]
        if val is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="option_not_selectable",
                translation_placeholders={
                    "entity": self._entity_name,
                    "option": option,
                },
            )
        coordinator = self.coordinator
        set_key = set_command(self._sensor_key)
        try:
            await coordinator.async_set_device_value(self._device_id, set_key, val)
            _LOGGER.debug(
                "Requested %s for device %s (value=%s)", set_key, self._device_id, val
            )
            _LOGGER.debug(
                "Select %s changed for device %s to %s",
                self._sensor_key,
                self._device_id,
                option,
            )
        except SyrConnectError as err:
            _LOGGER.error(
                "Failed to set %s for device %s: %s", set_key, self._device_id, err
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_value_failed",
                translation_placeholders={
                    "device": self._device_name,
                    "entity": self._entity_name,
                },
            ) from err


class SyrConnectHygieneModuleSelect(SyrConnectDiscreteSelect):
    """Setting of a hygiene module line (getSCF, getCCF, getCCL, getCSS, getCSL and getW*).

    Only the number before a space or a "[" of the reported value counts, see
    `parse_hygiene_module_value`. With an "off" option, a value below the lowest other
    option is shown as "off".
    """

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
        options_map: Mapping[str, int | None],
        off_value: int | None,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device_id, device_name, sensor_key, options_map)
        self._off_value = off_value

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if self._device is None:
            return None
        value = parse_hygiene_module_value(self._status.get(self._sensor_key))
        if value is None:
            return None
        for option, raw in self._options_map.items():
            if raw == value:
                return option
        if self._off_value is not None and value < min(
            raw
            for option, raw in self._options_map.items()
            if option != "off" and raw is not None
        ):
            return "off"
        return None


class SyrConnectPrfSelect(SyrConnectEntity, SelectEntity):
    """Select entity exposing active leak-protection profile (`getPRF`).

    Options are derived from `getPN1..getPN8` for each `getPAx` that is
    truthy (e.g., "1" or "true"). Selecting an option sends `setPRF` with
    the corresponding profile index `x`.
    """

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(
            coordinator,
            device_id,
            device_name,
            "select",
            "getPRF",
            unique_key="getPRF_select",
        )

        self.entity_description = _SYR_CONNECT_SELECT_DESCRIPTIONS["getPRF"]

    @property
    @override
    def options(self) -> list[str]:
        """Return the selectable options."""
        return list(get_active_leak_protection_profiles(self._status).values())

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if self._device is None:
            return None
        return get_current_leak_protection_profile(self._status)

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the device."""
        # Find index corresponding to selected option
        coordinator = self.coordinator
        selected_idx = next(
            (
                number
                for number, name in get_active_leak_protection_profiles(
                    self._status
                ).items()
                if name == option
            ),
            None,
        )

        if selected_idx is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_option",
                translation_placeholders={
                    "entity": self._entity_name,
                    "option": option,
                },
            )

        try:
            await coordinator.async_set_device_value(
                self._device_id, "setPRF", selected_idx
            )
            _LOGGER.debug(
                "Requested setPRF for device %s (profile=%s)",
                self._device_id,
                selected_idx,
            )
        except SyrConnectError as err:
            _LOGGER.error("Failed to set PRF for device %s: %s", self._device_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_value_failed",
                translation_placeholders={
                    "device": self._device_name,
                    "entity": self._entity_name,
                },
            ) from err
