"""Select platform for SYR Connect (regeneration time wrapper)."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from typing import Any, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    _SYR_CONNECT_SELECT_ALD_OPTIONS,
    _SYR_CONNECT_SELECT_CRT_MAP,
    _SYR_CONNECT_SELECT_MIH_MAP,
    _SYR_CONNECT_SELECT_MIT_MAP,
    _SYR_CONNECT_SELECT_MXH_MAP,
    _SYR_CONNECT_SELECT_MXT_MAP,
    _SYR_CONNECT_SELECT_RCD_MAP,
    _SYR_CONNECT_SELECT_RCP_MAP,
    _SYR_CONNECT_SELECT_RMO_MAP,
    _SYR_CONNECT_SELECT_RMT_OPTIONS,
    _SYR_CONNECT_SELECT_RVT_OPTIONS,
    _SYR_CONNECT_SELECT_WMP_MAP,
    _SYR_CONNECT_SENSOR_CRS_VALUE_MAP,
    _SYR_CONNECT_SENSOR_WHU_VALUE_MAP,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .data import SyrConnectDevice
from .entity import SyrConnectEntity
from .exceptions import SyrConnectError
from .helpers import (
    find_entity_id,
    get_model_supported_keys,
    get_sensor_rtm_value,
    is_value_true,
    registry_cleanup,
    set_sensor_rtm_value,
)
from .models import detect_model
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
        entity_registry_enabled_default=False,
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
        key="getFFM",  # Filter type (backwash / replaceable / none)
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
        key="getRCP",  # Synchronisation interval (s)
        entity_category=EntityCategory.CONFIG,
    ),
)

_SYR_CONNECT_SELECT_DESCRIPTIONS: dict[str, SyrConnectSelectEntityDescription] = {
    description.key: description for description in _SYR_CONNECT_SELECT_TYPES
}

# Supported keys for the select platform — used by registry_cleanup to remove stale entries.
# The global fallback for models without a device file; some selects (SafeFloor thresholds,
# LEX water hardness) are only enabled by the SELECT_SUPPORTED_KEYS of their device file.
_SYR_CONNECT_SELECT_SUPPORTED_KEYS = {
    "getRTM",  # Regeneration time (HH:MM combined or minutes)
    "getPRF",  # Active leak-protection profile
    "getSRO",  # Display rotation (0 / 90 / 180 / 270 °)
    # "getFCD",   # Filter backwash interval
    "getSV1",  # Salt amount container 1
    "getSV2",  # Salt amount container 2
    "getSV3",  # Salt amount container 3
    "getRPD",  # Regeneration interval (days)
    "getFFM",  # Filter type (1..3)
    "getRMO",  # Regeneration mode (Standard / ECO / Power / Automatic)
    # --- Water treatment / Filling (Conel Clear Pro Fill) ---
    "getCRS",  # Cartridge size (raw 1-5, mapped to liters)
    "getCRT",  # Cartridge type (0=HWE, 1=HVE, 2=HVE+)
    "getLOT",  # Maximum output conductivity (raw x10 µS/cm) - only when getCRT is HVE/HVE+
    "getOHW",  # Soft water hardness (°dH) - only when getCRT is HWE
    "getRCD",  # Filling processes period (0=hour, 1=day, 2=week, 3=month)
    "getRMN",  # Filling processes count
    "getRMT",  # Maximum filling duration (min)
    "getRVT",  # Maximum filling charges
    "getTPR",  # Target pressure (1/10 bar)
}

# Cartridge size (getCRS): 1=2.5L, 2=4L, 3=7L, 4=14L, 5=30L. Reuses the same
# _SYR_CONNECT_SENSOR_CRS_VALUE_MAP as the getCRS sensor so raw <-> display stays in one place.
_SYR_CONNECT_SELECT_CRS_MAP = {
    f"{v:g} {_SYR_CONNECT_SENSOR_DESCRIPTIONS['getCRS'].native_unit_of_measurement}": k
    for k, v in _SYR_CONNECT_SENSOR_CRS_VALUE_MAP.items()
}


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
    if value is None or value == "":
        return False
    try:
        int(float(value))
    except ValueError, TypeError:
        return False
    return True


def _unit_options(key: str, values: list[int]) -> list[str]:
    """Return option labels with the key's unit suffix, e.g. "30 min".

    Args:
        key: Status key whose unit is used (from its sensor description)
        values: Raw option values

    Returns:
        One label per value, in the same order
    """
    unit = _SYR_CONNECT_SENSOR_DESCRIPTIONS[key].native_unit_of_measurement
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
        self.status: dict[str, Any] = device.get("status", {})
        # Scope to the detected model (falls back to the global allowlist for
        # models that haven't opted into per-model key lists).
        self.model_info = detect_model(self.status)
        self.supported_select_keys = get_model_supported_keys(
            self.model_info, "select", _SYR_CONNECT_SELECT_SUPPORTED_KEYS
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

    def add_numeric_steps(self, key: str, values: list[int]) -> None:
        """Add a numeric select with a non-uniform list of steps, labelled with the unit.

        Args:
            key: Status key, e.g. "getRMT"
            values: Raw values in ascending order (e.g. `_SYR_CONNECT_SELECT_RMT_OPTIONS`)
        """
        self.add_numeric(key, values[0], values[-1], options=_unit_options(key, values))


def _build_device_selects(
    coordinator: SyrConnectDataUpdateCoordinator, device: SyrConnectDevice
) -> list[SelectEntity]:
    """Return the selects of one device (except the conditional getLOT/getOHW).

    A select is only created when the detected model lists its key and the device
    reports a valid value for it; a few keys are not limited to the allowlist (marked
    below). The selects are created in a fixed order, one block per key.

    Args:
        coordinator: Data update coordinator
        device: Device entry from the coordinator data (id, name, status)

    Returns:
        The select entities to add for this device
    """
    builder = _SyrConnectSelectBuilder(coordinator, device)
    _add_softener_selects(builder)
    _add_muco_selects(builder)
    _add_safefloor_selects(builder)
    return builder.entities


def _add_softener_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the selects for regeneration, salt, hardness and the general device settings."""
    status = b.status
    supported_select_keys = b.supported_select_keys

    # Regeneration time (getRTM): may contain a combined HH:MM string when `getRTH` is
    # not provided, or act as minutes when `getRTH` is present.
    if b.allowed("getRTM", lambda v: v is not None and v != ""):
        b.entities.append(
            SyrConnectRegenerationSelect(b.coordinator, b.device_id, b.device_name)
        )

    # Active leak-protection profile (getPRF), if any profile getPAx is active (e.g. "true" or "1")
    if "getPRF" in supported_select_keys and any(
        is_value_true(status.get(f"getPA{i}")) for i in range(1, 9)
    ):
        b.entities.append(
            SyrConnectPrfSelect(b.coordinator, b.device_id, b.device_name)
        )

    # Display rotation (getSRO): 0, 90, 180, 270; accepts numeric-like values ("90" or "90.0")
    if b.allowed("getSRO", _is_integer):
        b.entities.append(
            SyrConnectRotationSelect(b.coordinator, b.device_id, b.device_name)
        )

    # Salt amounts (getSV1-3): the maximum depends on the model; models without salt containers have none
    max_capacity = b.model_info.get("maximum_salt_volume")
    if max_capacity is not None:
        for sv_key in ("getSV1", "getSV2", "getSV3"):
            if b.allowed(sv_key):
                b.add_numeric(sv_key, 0, int(max_capacity))

    # Regeneration interval in days (getRPD): the maximum depends on the model; models without
    # regeneration have none. 0 means no interval regeneration, so no select is created.
    # Not limited to the allowlist.
    max_rpd = b.model_info.get("maximum_regeneration_interval")
    if (
        max_rpd is not None
        and _is_number(status.get("getRPD"))
        and float(status["getRPD"]) != 0
    ):
        b.add_numeric("getRPD", 1, max_rpd)

    # Raw water hardness (getIWH, 1-100) and outlet/soft water hardness (getOWH, 0-100), plain LEX
    # family only (see docs/syrconnect-protocol.md). The unit suffix follows the device's getWHU setting.
    for hardness_key, hardness_min in (("getIWH", 1), ("getOWH", 0)):
        if b.allowed(hardness_key):
            b.entities.append(
                SyrConnectHardnessSelect(
                    b.coordinator,
                    b.device_id,
                    b.device_name,
                    hardness_key,
                    hardness_min,
                    100,
                    1,
                )
            )

    # Filter type (getFFM): types 1-3, only for a value >= 1. Raw numeric options so the frontend
    # translates the state. Not limited to the allowlist.
    if _is_number(status.get("getFFM")) and float(status["getFFM"]) >= 1:
        b.add_numeric("getFFM", 1, 3, options=["1", "2", "3"])

    # Regeneration mode (getRMO), only for a value >= 1. Not limited to the allowlist.
    if _is_integer(status.get("getRMO")) and int(float(status["getRMO"])) >= 1:
        b.add_discrete("getRMO", _SYR_CONNECT_SELECT_RMO_MAP)


def _add_muco_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the MuCo selects for the water treatment / filling mode configuration.

    getLOT and getOHW are mutually exclusive depending on cartridge type and are handled
    separately (_async_setup_muco_conditional_selects), which adds/removes whichever one
    currently applies instead of creating both and showing the other as unavailable.
    """
    if b.allowed("getCRS", _is_integer):
        b.add_discrete("getCRS", _SYR_CONNECT_SELECT_CRS_MAP)
    # getCRT and getRCD have an option for the empty value, so any reported value counts
    if "getCRT" in b.supported_select_keys and "getCRT" in b.status:
        b.add_discrete("getCRT", _SYR_CONNECT_SELECT_CRT_MAP)
    if "getRCD" in b.supported_select_keys and "getRCD" in b.status:
        b.add_discrete("getRCD", _SYR_CONNECT_SELECT_RCD_MAP)
    # Filling processes count (getRMN): 1-10
    if b.allowed("getRMN"):
        b.add_numeric("getRMN", 1, 10)
    # Maximum filling duration (getRMT) and charges (getRVT): non-uniform minute/liter steps
    # (see docs/syrconnect-protocol.md)
    if b.allowed("getRMT"):
        b.add_numeric_steps("getRMT", _SYR_CONNECT_SELECT_RMT_OPTIONS)
    if b.allowed("getRVT"):
        b.add_numeric_steps("getRVT", _SYR_CONNECT_SELECT_RVT_OPTIONS)
    # Target pressure (getTPR): 0.5-5.0 bar in 0.1 bar steps (raw value is stored as 1/10 bar)
    if b.allowed("getTPR"):
        b.add_numeric("getTPR", 5, 50, scale=10)


def _add_safefloor_selects(b: _SyrConnectSelectBuilder) -> None:
    """Add the SafeFloor selects: alarm/humidity/temperature thresholds and sync/measurement intervals."""
    if b.allowed("getMIH"):
        b.add_discrete("getMIH", _SYR_CONNECT_SELECT_MIH_MAP)
    if b.allowed("getMXH"):
        b.add_discrete("getMXH", _SYR_CONNECT_SELECT_MXH_MAP)
    if b.allowed("getMIT"):
        b.add_discrete("getMIT", _SYR_CONNECT_SELECT_MIT_MAP)
    if b.allowed("getMXT"):
        b.add_discrete("getMXT", _SYR_CONNECT_SELECT_MXT_MAP)
    # Alarm duration (getALD): documented GUI Settings step list (see docs/syrconnect-protocol.md)
    if b.allowed("getALD"):
        b.add_numeric_steps("getALD", _SYR_CONNECT_SELECT_ALD_OPTIONS)
    if b.allowed("getWMP"):
        b.add_discrete("getWMP", _SYR_CONNECT_SELECT_WMP_MAP)
    if b.allowed("getRCP"):
        b.add_discrete("getRCP", _SYR_CONNECT_SELECT_RCP_MAP)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for SYR Connect."""
    _LOGGER.debug("Setting up SYR Connect select entities")
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data

    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for select platform")
        return

    registry_cleanup(
        hass,
        coordinator.data,
        "select",
        allowed_keys=_SYR_CONNECT_SELECT_SUPPORTED_KEYS,
        entry_id=coordinator.entry_id,
    )

    entities: list[SelectEntity] = []
    for device in coordinator.data.get("devices", []):
        entities.extend(_build_device_selects(coordinator, device))

    if entities:
        _LOGGER.debug("Adding %d select(s) total", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No select entities to add")

    _async_setup_muco_conditional_selects(hass, entry, coordinator, async_add_entities)


def _async_setup_muco_conditional_selects(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: SyrConnectDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Dynamically add/remove the getLOT/getOHW select depending on the cartridge type.

    getLOT (HVE/HVE+) and getOHW (HWE) are mutually exclusive: only one ever applies for a
    given cartridge type (getCRT). Instead of creating both and showing the inapplicable one
    as permanently greyed-out "unavailable", only the currently-relevant entity is added; the
    other is removed from the entity registry. Re-evaluated on every coordinator update, so
    switching getCRT (which optimistically updates coordinator.data immediately) swaps the
    visible entity right away, without requiring an integration reload.
    """
    # Per-device set of currently added keys ("getLOT" / "getOHW")
    live_keys: dict[str, set[str]] = {}

    def _wanted_key(status: dict[str, Any]) -> str | None:
        crt = str(status.get("getCRT") or "").strip()
        if crt in ("1", "2") and status.get("getLOT") not in (None, ""):
            key = "getLOT"
        elif crt == "0" and status.get("getOHW") not in (None, ""):
            key = "getOHW"
        else:
            return None
        # Only for models that list the key (MuCo filling). Leak-protection and TrioLock devices
        # also report getCRT/getLOT/getOHW but deliberately do not expose them; a select there
        # would even write setOHW/setLOT.
        supported_select_keys = get_model_supported_keys(
            detect_model(status), "select", _SYR_CONNECT_SELECT_SUPPORTED_KEYS
        )
        return key if key in supported_select_keys else None

    def _build_entity(
        device_id: str, device_name: str, key: str
    ) -> SyrConnectDiscreteSelect | SyrConnectNumericSelect:
        if key == "getLOT":
            lot_unit = _SYR_CONNECT_SENSOR_DESCRIPTIONS[
                "getLOT"
            ].native_unit_of_measurement
            lot_map = {f"{raw * 10} {lot_unit}": raw for raw in range(21)}
            return SyrConnectDiscreteSelect(
                coordinator, device_id, device_name, "getLOT", lot_map
            )
        return SyrConnectNumericSelect(
            coordinator, device_id, device_name, "getOHW", 0, 12, 1
        )

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
                wanted = _wanted_key(status)
                wanted_set = {wanted} if wanted else set()

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

                for key in wanted_set - current:
                    new_entities.append(_build_entity(device_id, device_name, key))
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
        return get_sensor_rtm_value(self._status)

    @override
    async def async_select_option(self, option: str) -> None:
        """Called when user selects a time option from the UI."""
        coordinator = self.coordinator
        commands = set_sensor_rtm_value(self._status, option)
        if not commands:
            _LOGGER.error(
                "Invalid time option selected for device %s: %s",
                self._device_id,
                option,
            )
            return

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
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            _LOGGER.error(
                "Failed to set regeneration time for device %s: %s",
                self._device_id,
                err,
            )
            raise HomeAssistantError(f"Failed to set regeneration time: {err}") from err


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
        unit_label = None
        unit = _SYR_CONNECT_SENSOR_DESCRIPTIONS[
            self._sensor_key
        ].native_unit_of_measurement
        if unit is not None:
            try:
                unit_label = str(unit)
            except (ValueError, TypeError) as err:
                _LOGGER.debug(
                    "Failed to convert unit to string for %s: %s", self._sensor_key, err
                )
                unit_label = None

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
            num = int(float(val))
            # Return the option whose number (first token; options may carry a unit suffix,
            # e.g. "20 s") equals the scaled display value. Same parsing as async_select_option.
            # A prefix match would wrongly pick "20 s" for the value 2.
            label = _format_scaled(num, self._scale)
            for opt in self._options:
                if opt.split(" ", 1)[0] == label:
                    return opt
        except ValueError, TypeError, AttributeError:
            return None
        else:
            return label

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the device."""
        try:
            # Option may include a unit suffix (e.g., '2 days'), so parse first token
            token = str(option).split()[0]
            val = round(float(token) * self._scale)
        except (IndexError, OverflowError, ValueError) as err:
            _LOGGER.error("Invalid option for %s: %s", self._sensor_key, err)
            return

        coordinator = self.coordinator
        # key for setting: remove leading 'get' and prefix with 'set'
        set_key = f"set{self._sensor_key[3:]}"
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
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            _LOGGER.error(
                "Failed to set %s for device %s: %s", set_key, self._device_id, err
            )
            raise HomeAssistantError(
                f"Failed to set {self._sensor_key}: {err}"
            ) from err


class SyrConnectHardnessSelect(SyrConnectNumericSelect):
    """Water hardness select (`getIWH`/`getOWH`) with the unit taken from the live `getWHU` setting."""

    def _unit_label(self) -> str:
        try:
            whu = int(float(self._status.get("getWHU")))  # type: ignore[arg-type]
        except ValueError, TypeError:
            return ""
        return _SYR_CONNECT_SENSOR_WHU_VALUE_MAP.get(whu, "")

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
            num = int(float(val))
            # Return matching raw option (string)
            for opt in self._options:
                if opt.startswith(f"{num}"):
                    return opt
            return str(num)
        except ValueError, TypeError, AttributeError:
            return None

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the device."""
        try:
            token = str(option).rstrip("°").strip()
            val = int(token)
        except ValueError as err:
            _LOGGER.error("Invalid option for getSRO: %s", err)
            return

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
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            _LOGGER.error(
                "Failed to set %s for device %s: %s", set_key, self._device_id, err
            )
            raise HomeAssistantError(f"Failed to set getSRO: {err}") from err


class SyrConnectDiscreteSelect(SyrConnectEntity, SelectEntity):
    """Select entity for discrete, non-sequential option maps (e.g., getFCD)."""

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
            num = int(float(val))
        except ValueError, TypeError:
            return None
        for opt, mapped in self._options_map.items():
            if mapped == num:
                return opt
        return None

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the device."""
        if option not in self._options_map:
            _LOGGER.error("Invalid option for %s: %s", self._sensor_key, option)
            return
        val = self._options_map[option]
        if val is None:
            _LOGGER.error(
                "Option %s for %s has no underlying raw value and cannot be selected",
                option,
                self._sensor_key,
            )
            return
        coordinator = self.coordinator
        set_key = f"set{self._sensor_key[3:]}"
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
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            _LOGGER.error(
                "Failed to set %s for device %s: %s", set_key, self._device_id, err
            )
            raise HomeAssistantError(
                f"Failed to set {self._sensor_key}: {err}"
            ) from err


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
        status = self._status
        opts: list[str] = []
        for i in range(1, 9):
            pa = status.get(f"getPA{i}")
            if not is_value_true(pa):
                continue
            name = status.get(f"getPN{i}") or str(i)
            opts.append(str(name))
        return opts

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if self._device is None:
            return None
        status = self._status
        val = status.get("getPRF")
        if val is None or val == "":
            return None
        try:
            idx = int(float(val))
        except ValueError, TypeError:
            return None
        return status.get(f"getPN{idx}")

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the device."""
        # Find index corresponding to selected option
        coordinator = self.coordinator
        status = self._status
        selected_idx: int | None = None
        for i in range(1, 9):
            pa = status.get(f"getPA{i}")
            if not is_value_true(pa):
                continue
            name = status.get(f"getPN{i}") or str(i)
            if str(name) == option:
                selected_idx = i
                break

        if selected_idx is None:
            _LOGGER.error(
                "Selected profile not found for device %s: %s", self._device_id, option
            )
            return

        try:
            await coordinator.async_set_device_value(
                self._device_id, "setPRF", selected_idx
            )
            _LOGGER.debug(
                "Requested setPRF for device %s (profile=%s)",
                self._device_id,
                selected_idx,
            )
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            _LOGGER.error("Failed to set PRF for device %s: %s", self._device_id, err)
            raise HomeAssistantError(f"Failed to set profile: {err}") from err
