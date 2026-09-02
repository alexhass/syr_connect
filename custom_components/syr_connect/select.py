"""Select platform for SYR Connect (regeneration time wrapper)."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, cast

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    _SYR_CONNECT_SELECT_KNOWN_KEYS,
    _SYR_CONNECT_SENSOR_CONFIG,
    _SYR_CONNECT_SENSOR_CRS_VALUE_MAP,
    _SYR_CONNECT_SENSOR_DISABLED_BY_DEFAULT,
    _SYR_CONNECT_SENSOR_EXCLUDED,
    _SYR_CONNECT_SENSOR_ICON,
    _SYR_CONNECT_SENSOR_UNIT,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .exceptions import SyrConnectError
from .helpers import (
    build_device_info,
    build_entity_id,
    build_unique_id,
    get_sensor_rtm_value,
    is_value_true,
    registry_cleanup,
    set_sensor_rtm_value,
)
from .models import detect_model

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the API
PARALLEL_UPDATES = 1


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


def _build_rmt_minute_options() -> list[int]:
    """Build the documented non-uniform minute steps for getRMT (see docs/syrconnect-protocol.md).

    Steps in minutes: 1-5 (step 1), 10, 15-60 (step 15), 60-720 (step 30).
    """
    values = {1, 2, 3, 4, 5, 10}
    values.update(range(15, 61, 15))
    values.update(range(60, 721, 30))
    return sorted(values)


def _build_rvt_liter_options() -> list[int]:
    """Build the documented non-uniform liter steps for getRVT (see docs/syrconnect-protocol.md).

    0=off, 10-100 in steps of 10, 100-1000 in steps of 50, 1000-9900 in steps of 100.
    """
    values = {0}
    values.update(range(10, 101, 10))
    values.update(range(100, 1001, 50))
    values.update(range(1000, 9901, 100))
    return sorted(values)


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
        hass, coordinator.data, "select",
        allowed_keys=_SYR_CONNECT_SELECT_KNOWN_KEYS - _SYR_CONNECT_SENSOR_EXCLUDED,
        entry_id=coordinator.entry_id,
    )

    entities: list[Any] = []
    for device in coordinator.data.get("devices", []):
        device_id = device.get("id")
        device_name = device.get("name", device_id)
        status = device.get("status", {})
        # Create regeneration time select when `getRTM` is present (it may contain a combined HH:MM
        # string when `getRTH` is not provided, or act as minutes when `getRTH` is present).
        rtm = status.get("getRTM")
        if rtm is None or rtm == "":
            continue
        entities.append(SyrConnectRegenerationSelect(coordinator, device_id, device_name))

    # Add profile select for active leak-protection profiles (getPRF)
    for device in coordinator.data.get("devices", []):
        device_id = device.get("id")
        device_name = device.get("name", device_id)
        status = device.get("status", {})
        # if any getPAx is truthy (e.g. "true" or "1"), create profile select
        has_profile = False
        for i in range(1, 9):
            pa = status.get(f"getPA{i}")
            if is_value_true(pa):
                has_profile = True
                break
        if has_profile:
            entities.append(SyrConnectPrfSelect(coordinator, device_id, device_name))

    # Add select for display rotation (getSRO) - discrete states: 0,90,180,270
    for device in coordinator.data.get("devices", []):
        device_id = device.get("id")
        device_name = device.get("name", device_id)
        status = device.get("status", {})
        sro_value = status.get("getSRO")
        if sro_value is None or sro_value == "":
            continue
        try:
            # accept numeric-like values (e.g., "90" or "90.0")
            int(float(sro_value))
        except (ValueError, TypeError):
            continue
        entities.append(SyrConnectRotationSelect(coordinator, device_id, device_name))

    # TODO: Temporarily disabled - getFCD select (filter backwash interval).
    # Known bug: After writing a new value, the server resets the setting back to its previous value.
    # Root cause is unknown. Re-enable once the write-back issue is resolved.
    # fcd_map = {
    #     "2592000": 2592000,
    #     "5184000": 5184000,
    #     "7776000": 7776000,
    #     "10368000": 10368000,
    #     "12960000": 12960000,
    #     "15552000": 15552000,
    #     "18144000": 18144000,
    #     "20736000": 20736000,
    #     "23328000": 23328000,
    #     "25920000": 25920000,
    #     "28512000": 28512000,
    #     "31104000": 31104000,
    # }
    # for device in coordinator.data.get("devices", []):
    #     device_id = device.get("id")
    #     device_name = device.get("name", device_id)
    #     status = device.get("status", {})
    #     fcd_value = status.get("getFCD")
    #     if fcd_value is None or fcd_value == "":
    #         continue
    #     try:
    #         int(float(fcd_value))
    #     except (ValueError, TypeError):
    #         continue
    #     entities.append(SyrConnectDiscreteSelect(coordinator, device_id, device_name, "getFCD", fcd_map))

    # Add numeric-controlled selects for salt amounts and regeneration interval
    for device in coordinator.data.get("devices", []):
        device_id = device.get("id")
        device_name = device.get("name", device_id)
        status = device.get("status", {})
        # Salt amount selects (max depends on device model; skip for models without salt containers)
        model_info = detect_model(status)
        max_capacity = model_info.get("maximum_salt_volume")
        if max_capacity is not None:
            for sv_key in ("getSV1", "getSV2", "getSV3"):
                sv_value = status.get(sv_key)
                if sv_value is None or sv_value == "":
                    continue
                try:
                    float(sv_value)  # Validate it's a valid number
                except (ValueError, TypeError):
                    continue
                entities.append(
                    SyrConnectNumericSelect(
                        coordinator, device_id, device_name, sv_key, 0, int(max_capacity), 1
                    )
                )

        # Regeneration interval select (max days depends on device model; skip for models without regeneration)
        rpd_value = status.get("getRPD")
        max_rpd = model_info.get("maximum_regeneration_interval")
        if rpd_value is not None and rpd_value != "" and max_rpd is not None:
            try:
                if float(rpd_value) != 0:
                    entities.append(
                        SyrConnectNumericSelect(coordinator, device_id, device_name, "getRPD", 1, max_rpd, 1)
                    )
            except (ValueError, TypeError):
                pass

        # Add getFFM select (filter type) if present: expose raw numeric keys so frontend translates the state
        ffm_value = status.get("getFFM")
        if ffm_value is not None and ffm_value != "":
            try:
                v = float(ffm_value)
            except (ValueError, TypeError):
                continue
            # Only create select when value is >= 1 (filter types 1..3); ignore 0
            if v < 1:
                continue
            # create numeric select and expose raw numeric options (strings) so HA translates the selected state
            sel = SyrConnectNumericSelect(coordinator, device_id, device_name, "getFFM", 1, 3, 1)
            sel._options = [str(x) for x in range(1, 4)]
            entities.append(sel)

        # Add getRMO select (regeneration mode: 1=Standard, 2=ECO, 3=Power, 4=Automatic)
        # Raw string keys are exposed so the frontend can translate the displayed state.
        rmo_value = status.get("getRMO")
        if rmo_value is not None and rmo_value != "":
            try:
                rmo_int = int(float(rmo_value))
            except (ValueError, TypeError):
                rmo_int = 0
            if rmo_int >= 1:
                rmo_map = {"1": 1, "2": 2, "3": 3, "4": 4}
                entities.append(SyrConnectDiscreteSelect(coordinator, device_id, device_name, "getRMO", rmo_map))

    # --- MuCo devices: water treatment / filling mode configuration ---
    # getLOT and getOHW are mutually exclusive depending on cartridge type and are handled
    # separately below (_async_setup_muco_conditional_selects), which adds/removes whichever
    # one currently applies instead of creating both and showing the other as unavailable.
    for device in coordinator.data.get("devices", []):
        device_id = device.get("id")
        device_name = device.get("name", device_id)
        status = device.get("status", {})

        # Cartridge size (getCRS): 1=2.5L, 2=4L, 3=7L, 4=14L, 5=30L. Reuses the same
        # _SYR_CONNECT_SENSOR_CRS_VALUE_MAP as the getCRS sensor so raw <-> display stays in one place.
        crs_value = status.get("getCRS")
        if crs_value is not None and crs_value != "":
            try:
                int(float(crs_value))
            except (ValueError, TypeError):
                pass
            else:
                crs_map = {f"{v:g} L": k for k, v in _SYR_CONNECT_SENSOR_CRS_VALUE_MAP.items()}
                entities.append(SyrConnectDiscreteSelect(coordinator, device_id, device_name, "getCRS", crs_map))

        # Cartridge type (getCRT): 0=HWE, 1=HVE, 2=HVE+ (empty value = no cartridge installed)
        if "getCRT" in status:
            crt_map = {"none": None, "0": 0, "1": 1, "2": 2}
            entities.append(SyrConnectDiscreteSelect(coordinator, device_id, device_name, "getCRT", crt_map))

        # Filling processes period (getRCD): 0=hour, 1=day, 2=week, 3=month (empty value = undefined)
        if "getRCD" in status:
            rcd_map = {"undefined": None, "0": 0, "1": 1, "2": 2, "3": 3}
            entities.append(SyrConnectDiscreteSelect(coordinator, device_id, device_name, "getRCD", rcd_map))

        # Filling processes count (getRMN): 1-10 in steps of 1
        rmn_value = status.get("getRMN")
        if rmn_value is not None and rmn_value != "":
            try:
                float(rmn_value)
            except (ValueError, TypeError):
                pass
            else:
                entities.append(SyrConnectNumericSelect(coordinator, device_id, device_name, "getRMN", 1, 10, 1))

        # Maximum filling duration (getRMT): non-uniform minute steps (see docs/syrconnect-protocol.md)
        rmt_value = status.get("getRMT")
        if rmt_value is not None and rmt_value != "":
            try:
                float(rmt_value)
            except (ValueError, TypeError):
                pass
            else:
                rmt_options = _build_rmt_minute_options()
                rmt_sel = SyrConnectNumericSelect(
                    coordinator, device_id, device_name, "getRMT", rmt_options[0], rmt_options[-1], 1
                )
                rmt_sel._options = [f"{v} min" for v in rmt_options]
                entities.append(rmt_sel)

        # Maximum filling charges (getRVT): non-uniform liter steps (see docs/syrconnect-protocol.md)
        rvt_value = status.get("getRVT")
        if rvt_value is not None and rvt_value != "":
            try:
                float(rvt_value)
            except (ValueError, TypeError):
                pass
            else:
                rvt_options = _build_rvt_liter_options()
                rvt_sel = SyrConnectNumericSelect(
                    coordinator, device_id, device_name, "getRVT", rvt_options[0], rvt_options[-1], 1
                )
                rvt_sel._options = [f"{v} L" for v in rvt_options]
                entities.append(rvt_sel)

        # Target pressure (getTPR): 0.5-5.0 bar in 0.1 bar steps (raw value is stored as 1/10 bar)
        tpr_value = status.get("getTPR")
        if tpr_value is not None and tpr_value != "":
            try:
                float(tpr_value)
            except (ValueError, TypeError):
                pass
            else:
                entities.append(
                    SyrConnectNumericSelect(coordinator, device_id, device_name, "getTPR", 5, 50, 1, scale=10)
                )

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
            return "getLOT"
        if crt == "0" and status.get("getOHW") not in (None, ""):
            return "getOHW"
        return None

    def _build_entity(device_id: str, device_name: str, key: str) -> SyrConnectDiscreteSelect | SyrConnectNumericSelect:
        if key == "getLOT":
            lot_map = {f"{raw * 10} µS/cm": raw for raw in range(0, 21)}
            return SyrConnectDiscreteSelect(coordinator, device_id, device_name, "getLOT", lot_map)
        return SyrConnectNumericSelect(coordinator, device_id, device_name, "getOHW", 0, 12, 1)

    @callback
    def _sync() -> None:
        new_entities: list[SyrConnectDiscreteSelect | SyrConnectNumericSelect] = []
        registry = er.async_get(hass)
        for device in coordinator.data.get("devices", []):
            device_id = device.get("id")
            if not device_id:
                continue
            device_name = device.get("name", device_id)
            status = device.get("status", {})
            current = live_keys.setdefault(device_id, set())
            wanted = _wanted_key(status)
            wanted_set = {wanted} if wanted else set()

            for key in current - wanted_set:
                entity_id = build_entity_id("select", device_id, key)
                existing = registry.async_get(entity_id)
                if existing is not None and (
                    coordinator.entry_id is None or existing.config_entry_id == coordinator.entry_id
                ):
                    _LOGGER.debug("Removing conditionally hidden select from registry: %s", entity_id)
                    registry.async_remove(entity_id)
                current.discard(key)

            for key in wanted_set - current:
                new_entities.append(_build_entity(device_id, device_name, key))
                current.add(key)

        if new_entities:
            _LOGGER.debug("Adding %d conditional MuCo select(s)", len(new_entities))
            async_add_entities(new_entities)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))


class SyrConnectRegenerationSelect(CoordinatorEntity, SelectEntity):
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
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name

        self._attr_has_entity_name = True
        # Keep translation key for human-friendly name, but back the select by `getRTM` key
        self._attr_translation_key = "getrtm"
        self.entity_id = build_entity_id("select", device_id, "getRTM")
        self._attr_unique_id = build_unique_id(coordinator.entry_id, device_id, "getRTM_select")
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

        # Use same icon as the combined regeneration time sensor if available
        # Use the regeneration-time icon mapped to `getRTM`
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get("getRTM")

        # Options: 15 minute steps by default
        self._options = _build_time_options(15)

        # Set entity category according to central sensor mappings
        if "getRTM" in _SYR_CONNECT_SENSOR_CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG

        if "getRTM" in _SYR_CONNECT_SENSOR_DISABLED_BY_DEFAULT:
            self._attr_entity_registry_enabled_default = False

        _LOGGER.debug(
            "Created SyrConnectRegenerationSelect object: device=%s name=%s unique_id=%s",
            self._device_id,
            self._device_name,
            self._attr_unique_id,
        )

    @property
    def options(self) -> list[str]:
        return self._options

    @property
    def current_option(self) -> str | None:
        """Return the currently configured regeneration time as HH:MM."""
        for dev in self.coordinator.data.get("devices", []):
            if dev.get("id") != self._device_id:
                continue
            status = dev.get("status", {})
            return get_sensor_rtm_value(status)
        return None

    async def async_select_option(self, option: str) -> None:
        """Called when user selects a time option from the UI."""
        coordinator = cast(SyrConnectDataUpdateCoordinator, self.coordinator)
        # Find raw status for this device
        raw_status = None
        for dev in coordinator.data.get("devices", []):
            if dev.get("id") == self._device_id:
                raw_status = dev.get("status", {})
                break

        commands = set_sensor_rtm_value(raw_status or {}, option)
        if not commands:
            _LOGGER.error("Invalid time option selected for device %s: %s", self._device_id, option)
            return

        try:
            for key, val in commands:
                await coordinator.async_set_device_value(self._device_id, key, val)
            _LOGGER.debug("Requested regeneration time set commands for device %s: %s", self._device_id, commands)
            _LOGGER.debug("Regeneration time select changed for %s to %s", self._device_id, option)
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            _LOGGER.error("Failed to set regeneration time for device %s: %s", self._device_id, err)
            raise HomeAssistantError(f"Failed to set regeneration time: {err}") from err

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device.get("available", True)
        return True


class SyrConnectNumericSelect(CoordinatorEntity, SelectEntity):
    """Select entity representing a numeric control.

    Options are stringified integers between min_value and max_value
    with the given step. Selecting an option sends `set<KEY>` via the coordinator.
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
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name
        self._sensor_key = sensor_key
        # Raw device values are divided by `scale` for display and multiplied back when writing
        # (e.g. getTPR is stored as 1/10 bar, so scale=10 shows "1.8 bar" for the raw value 18).
        self._scale = scale

        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_key.lower()
        self.entity_id = build_entity_id("select", device_id, sensor_key)
        self._attr_unique_id = build_unique_id(coordinator.entry_id, device_id, f"{sensor_key}_select")
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)
        # Icon mapping if present
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get(sensor_key)

        # Disable by default if key is in the disabled-by-default set
        if sensor_key in _SYR_CONNECT_SENSOR_DISABLED_BY_DEFAULT:
            self._attr_entity_registry_enabled_default = False

        # Determine unit label (if available) and build options (append unit for readability)
        unit_label = None
        unit = _SYR_CONNECT_SENSOR_UNIT.get(self._sensor_key)
        if unit is not None:
            try:
                unit_label = str(unit)
            except (ValueError, TypeError) as err:
                _LOGGER.debug("Failed to convert unit to string for %s: %s", self._sensor_key, err)
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
        self._options = opts

        # Set entity category according to central sensor mappings
        if self._sensor_key in _SYR_CONNECT_SENSOR_CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG

        _LOGGER.debug(
            "Created SyrConnectNumericSelect object: device=%s key=%s unique_id=%s",
            self._device_id,
            self._sensor_key,
            self._attr_unique_id,
        )

    @property
    def options(self) -> list[str]:
        return self._options

    @property
    def current_option(self) -> str | None:
        for dev in self.coordinator.data.get("devices", []):
            if dev.get("id") != self._device_id:
                continue
            status = dev.get("status", {})
            val = status.get(self._sensor_key)
            if val is None or val == "":
                return None
            try:
                num = int(float(val))
                # Return the option that starts with the scaled display value (preserves unit if present)
                label = _format_scaled(num, self._scale)
                for opt in self._options:
                    if opt.startswith(label):
                        return opt
                return label
            except (ValueError, TypeError, AttributeError):
                return None
        return None

    async def async_select_option(self, option: str) -> None:
        try:
            # Option may include a unit suffix (e.g., '2 days'), so parse first token
            token = str(option).split()[0]
            val = int(round(float(token) * self._scale))
        except Exception as err:
            _LOGGER.error("Invalid option for %s: %s", self._sensor_key, err)
            return

        coordinator = cast(SyrConnectDataUpdateCoordinator, self.coordinator)
        # key for setting: remove leading 'get' and prefix with 'set'
        set_key = f"set{self._sensor_key[3:]}"
        try:
            await coordinator.async_set_device_value(self._device_id, set_key, val)
            _LOGGER.debug("Requested %s for device %s (value=%s)", set_key, self._device_id, val)
            _LOGGER.debug(
                "Select %s changed for device %s to %s",
                self._sensor_key,
                self._device_id,
                option,
            )
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            _LOGGER.error("Failed to set %s for device %s: %s", set_key, self._device_id, err)
            raise HomeAssistantError(f"Failed to set {self._sensor_key}: {err}") from err

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device.get("available", True)
        return True


class SyrConnectRotationSelect(CoordinatorEntity, SelectEntity):
    """Select entity exposing display rotation (`getSRO`).

    Options: raw state keys 0, 90, 180, 270 — frontend shows translated labels; selecting sends `setSRO`.
    """

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name

        self._attr_has_entity_name = True
        self._attr_translation_key = "getsro"
        self.entity_id = build_entity_id("select", device_id, "getSRO")
        self._attr_unique_id = build_unique_id(coordinator.entry_id, device_id, "getSRO_select")
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get("getSRO")

        # Use raw state keys so the frontend will translate them via the translation files
        self._options = ["0", "90", "180", "270"]

        if "getSRO" in _SYR_CONNECT_SENSOR_CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG

        if "getSRO" in _SYR_CONNECT_SENSOR_DISABLED_BY_DEFAULT:
            self._attr_entity_registry_enabled_default = False

        _LOGGER.debug(
            "Created SyrConnectRotationSelect object: device=%s name=%s unique_id=%s",
            self._device_id,
            self._device_name,
            self._attr_unique_id,
        )

    @property
    def options(self) -> list[str]:
        return self._options

    @property
    def current_option(self) -> str | None:
        for dev in self.coordinator.data.get("devices", []):
            if dev.get("id") != self._device_id:
                continue
            status = dev.get("status", {})
            val = status.get("getSRO")
            if val is None or val == "":
                return None
            try:
                num = int(float(val))
                # Return matching raw option (string)
                for opt in self._options:
                    if opt.startswith(f"{num}"):
                        return opt
                return str(num)
            except (ValueError, TypeError, AttributeError):
                return None
        return None

    async def async_select_option(self, option: str) -> None:
        try:
            token = str(option).rstrip("°").strip()
            val = int(token)
        except Exception as err:
            _LOGGER.error("Invalid option for getSRO: %s", err)
            return

        coordinator = cast(SyrConnectDataUpdateCoordinator, self.coordinator)
        set_key = "setSRO"
        try:
            await coordinator.async_set_device_value(self._device_id, set_key, val)
            _LOGGER.debug("Requested %s for device %s (value=%s)", set_key, self._device_id, val)
            _LOGGER.debug("Select getSRO changed for device %s to %s", self._device_id, option)
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            _LOGGER.error("Failed to set %s for device %s: %s", set_key, self._device_id, err)
            raise HomeAssistantError(f"Failed to set getSRO: {err}") from err

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device.get("available", True)
        return True


class SyrConnectDiscreteSelect(CoordinatorEntity, SelectEntity):
    """Select entity for discrete, non-sequential option maps (e.g., getFCD)."""

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
        options_map: Mapping[str, int | None],
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name
        self._sensor_key = sensor_key
        self._options_map = options_map

        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_key.lower()
        self.entity_id = build_entity_id("select", device_id, sensor_key)
        self._attr_unique_id = build_unique_id(coordinator.entry_id, device_id, f"{sensor_key}_select")
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get(sensor_key)

        # Options are the raw state keys (strings) of the mapping so the frontend
        # can translate the displayed state using the integration translations.
        self._options = list(options_map.keys())

        # Mark as configuration if listed in central mapping
        if self._sensor_key in _SYR_CONNECT_SENSOR_CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG

        if self._sensor_key in _SYR_CONNECT_SENSOR_DISABLED_BY_DEFAULT:
            self._attr_entity_registry_enabled_default = False

        _LOGGER.debug(
            "Created SyrConnectDiscreteSelect object: device=%s key=%s unique_id=%s",
            self._device_id,
            self._sensor_key,
            self._attr_unique_id,
        )

    @property
    def options(self) -> list[str]:
        return self._options

    @property
    def current_option(self) -> str | None:
        for dev in self.coordinator.data.get("devices", []):
            if dev.get("id") != self._device_id:
                continue
            status = dev.get("status", {})
            val = status.get(self._sensor_key)
            if val is None or val == "":
                # Some option maps include a sentinel entry (value=None, e.g. "undefined")
                # representing this empty raw state instead of falling back to unknown.
                for opt, mapped in self._options_map.items():
                    if mapped is None:
                        return opt
                return None
            try:
                num = int(float(val))
            except (ValueError, TypeError):
                return None
            for opt, mapped in self._options_map.items():
                if mapped == num:
                    return opt
            return None
        return None

    async def async_select_option(self, option: str) -> None:
        if option not in self._options_map:
            _LOGGER.error("Invalid option for %s: %s", self._sensor_key, option)
            return
        val = self._options_map[option]
        if val is None:
            _LOGGER.error("Option %s for %s has no underlying raw value and cannot be selected", option, self._sensor_key)
            return
        coordinator = cast(SyrConnectDataUpdateCoordinator, self.coordinator)
        set_key = f"set{self._sensor_key[3:]}"
        try:
            await coordinator.async_set_device_value(self._device_id, set_key, val)
            _LOGGER.debug("Requested %s for device %s (value=%s)", set_key, self._device_id, val)
            _LOGGER.debug("Select %s changed for device %s to %s", self._sensor_key, self._device_id, option)
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            _LOGGER.error("Failed to set %s for device %s: %s", set_key, self._device_id, err)
            raise HomeAssistantError(f"Failed to set {self._sensor_key}: {err}") from err

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device.get("available", True)
        return True


class SyrConnectPrfSelect(CoordinatorEntity, SelectEntity):
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
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name

        self._attr_has_entity_name = True
        self._attr_translation_key = "getprf"
        self.entity_id = build_entity_id("select", device_id, "getPRF")
        self._attr_unique_id = build_unique_id(coordinator.entry_id, device_id, "getPRF_select")
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get("getPRF")

        # Set entity category according to central sensor mappings
        if "getPRF" in _SYR_CONNECT_SENSOR_CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG

        if "getPRF" in _SYR_CONNECT_SENSOR_DISABLED_BY_DEFAULT:
            self._attr_entity_registry_enabled_default = False

    @property
    def options(self) -> list[str]:
        opts: list[str] = []
        for dev in self.coordinator.data.get("devices", []):
            if dev.get("id") != self._device_id:
                continue
            status = dev.get("status", {})
            for i in range(1, 9):
                pa = status.get(f"getPA{i}")
                if not is_value_true(pa):
                    continue
                name = status.get(f"getPN{i}") or str(i)
                opts.append(str(name))
            break
        return opts

    @property
    def current_option(self) -> str | None:
        for dev in self.coordinator.data.get("devices", []):
            if dev.get("id") != self._device_id:
                continue
            status = dev.get("status", {})
            val = status.get("getPRF")
            if val is None or val == "":
                return None
            try:
                idx = int(float(val))
            except (ValueError, TypeError):
                return None
            name = status.get(f"getPN{idx}")
            return name
        return None

    async def async_select_option(self, option: str) -> None:
        # Find index corresponding to selected option
        coordinator = cast(SyrConnectDataUpdateCoordinator, self.coordinator)
        selected_idx: int | None = None
        for dev in coordinator.data.get("devices", []):
            if dev.get("id") != self._device_id:
                continue
            status = dev.get("status", {})
            for i in range(1, 9):
                pa = status.get(f"getPA{i}")
                if not is_value_true(pa):
                    continue
                name = status.get(f"getPN{i}") or str(i)
                if str(name) == option:
                    selected_idx = i
                    break
            break

        if selected_idx is None:
            _LOGGER.error("Selected profile not found for device %s: %s", self._device_id, option)
            return

        try:
            await coordinator.async_set_device_value(self._device_id, "setPRF", selected_idx)
            _LOGGER.debug("Requested setPRF for device %s (profile=%s)", self._device_id, selected_idx)
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            _LOGGER.error("Failed to set PRF for device %s: %s", self._device_id, err)
            raise HomeAssistantError(f"Failed to set profile: {err}") from err

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device.get("available", True)
        return True
