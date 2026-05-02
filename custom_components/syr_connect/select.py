"""Select platform for SYR Connect (regeneration time wrapper)."""
from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    _SYR_CONNECT_MODEL_SALT_CAPACITY,
    _SYR_CONNECT_SELECT_KNOWN_KEYS,
    _SYR_CONNECT_SENSOR_CONFIG,
    _SYR_CONNECT_SENSOR_EXCLUDED,
    _SYR_CONNECT_SENSOR_ICON,
    _SYR_CONNECT_SENSOR_UNIT,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .exceptions import SyrConnectError
from .helpers import (
    build_device_info,
    build_entity_id,
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

    registry_cleanup(hass, coordinator.data, "select", allowed_keys=_SYR_CONNECT_SELECT_KNOWN_KEYS - _SYR_CONNECT_SENSOR_EXCLUDED)

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
        # Salt amount selects (max depends on device model)
        model = detect_model(status)["name"]
        max_capacity = int(_SYR_CONNECT_MODEL_SALT_CAPACITY.get(str(model), 25))
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
                    coordinator, device_id, device_name, sv_key, 0, max_capacity, 1
                )
            )

        # Regeneration interval select (1..4 days)
        rpd_value = status.get("getRPD")
        if rpd_value is not None and rpd_value != "":
            try:
                if float(rpd_value) != 0:
                    # Lex models support up to 4 days, other models only up to 3 days
                    lex_models = {"lexplus10", "lexplus10s", "lexplus10sl"}
                    max_rpd = 4 if str(model) in lex_models else 3
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

    if entities:
        _LOGGER.debug("Adding %d select(s) total", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No select entities to add")


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
        self._attr_unique_id = f"{device_id}_getRTM_select"
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

        # Use same icon as the combined regeneration time sensor if available
        # Use the regeneration-time icon mapped to `getRTM`
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get("getRTM")

        # Options: 15 minute steps by default
        self._options = _build_time_options(15)

        # Set entity category according to central sensor mappings
        if "getRTM" in _SYR_CONNECT_SENSOR_CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG

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
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name
        self._sensor_key = sensor_key

        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_key.lower()
        self.entity_id = build_entity_id("select", device_id, sensor_key)
        self._attr_unique_id = f"{device_id}_{sensor_key}_select"
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)
        # Icon mapping if present
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get(sensor_key)

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
            if unit_label:
                opts.append(f"{int(v)} {unit_label}")
            else:
                opts.append(str(int(v)))
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
                # Return the option that starts with the numeric value (preserves unit if present)
                for opt in self._options:
                    if opt.startswith(f"{num}"):
                        return opt
                return str(num)
            except (ValueError, TypeError, AttributeError):
                return None
        return None

    async def async_select_option(self, option: str) -> None:
        try:
            # Option may include a unit suffix (e.g., '2 days'), so parse first token
            token = str(option).split()[0]
            val = int(token)
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
        self._attr_unique_id = f"{device_id}_getSRO_select"
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get("getSRO")

        # Use raw state keys so the frontend will translate them via the translation files
        self._options = ["0", "90", "180", "270"]

        if "getSRO" in _SYR_CONNECT_SENSOR_CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG

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
        options_map: dict[str, int],
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name
        self._sensor_key = sensor_key
        self._options_map = options_map

        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_key.lower()
        self.entity_id = build_entity_id("select", device_id, sensor_key)
        self._attr_unique_id = f"{device_id}_{sensor_key}_select"
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get(sensor_key)

        # Options are the raw state keys (strings) of the mapping so the frontend
        # can translate the displayed state using the integration translations.
        self._options = list(options_map.keys())

        # Mark as configuration if listed in central mapping
        if self._sensor_key in _SYR_CONNECT_SENSOR_CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG

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
        self._attr_unique_id = f"{device_id}_getPRF_select"
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)
        self._attr_icon = _SYR_CONNECT_SENSOR_ICON.get("getPRF")

        # Set entity category according to central sensor mappings
        if "getPRF" in _SYR_CONNECT_SENSOR_CONFIG:
            self._attr_entity_category = EntityCategory.CONFIG

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
