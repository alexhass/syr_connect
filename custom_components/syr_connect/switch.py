"""Switch platform for SYR Connect integration."""

import logging
from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SyrConnectConfigEntry, SyrConnectDataUpdateCoordinator
from .data import SyrConnectDevice
from .entity import SyrConnectEntity, async_add_device_entities
from .exceptions import SyrConnectError
from .helpers import (
    build_unique_id,
    get_device_model,
    get_model_supported_keys,
    is_value_true,
    registry_cleanup,
)

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the API
PARALLEL_UPDATES = 1


# Descriptions of all switches (boolean get<KEY>/set<KEY> settings)
_SYR_CONNECT_SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="getBPB",  # Profile change by button allowed (0 = blocked, 1 = allowed)
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="getBUZ",  # Buzzer on/off
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="getDFI",  # Filling mode enabled flag (Conel Clear Pro Fill)
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="getFD1",  # Stagnation flushing disabled flag (HygBox)
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="getFD2",  # Temperature flushing disabled flag (HygBox)
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="getFD3",  # Periodic flushing disabled flag (HygBox)
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="getIFL",  # Initial filling active flag (All-in-One+)
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="getMFL",  # Manual filling active flag (All-in-One+)
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="getSSA",  # Automatic backwash enabled flag (RSA)
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="getSSE",  # Backwash reminder enabled flag (RSA)
        entity_category=EntityCategory.CONFIG,
    ),
)

_SYR_CONNECT_SWITCH_DESCRIPTIONS: dict[str, SwitchEntityDescription] = {
    description.key: description for description in _SYR_CONNECT_SWITCH_TYPES
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SyrConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up boolean switch entities (e.g. getBUZ, getDFI)."""
    coordinator = entry.runtime_data

    registry_cleanup(
        hass,
        coordinator.data,
        "switch",
        allowed_keys=set(),
        entry_id=coordinator.entry_id,
    )

    async_add_device_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda device: _build_device_switches(coordinator, device),
    )


def _build_device_switches(
    coordinator: SyrConnectDataUpdateCoordinator, device: SyrConnectDevice
) -> list[SyrConnectBooleanSwitch]:
    """Return the switches of one device."""
    entities: list[SyrConnectBooleanSwitch] = []
    device_id = device["id"]
    device_name = device["name"]
    status = device.get("status", {})
    _LOGGER.debug(
        "Checking device: id=%s, name=%s, status_keys=%s",
        device_id,
        device_name,
        list(status.keys()),
    )

    # Only the switches of the device file of the detected model; a model without
    # one has no switches.
    supported_switch_keys = get_model_supported_keys(
        get_device_model(device), "switch", set()
    )

    for sensor_key in sorted(supported_switch_keys):
        if sensor_key not in status:
            _LOGGER.debug(
                "%s not found in status for device %s.", sensor_key, device_id
            )
            continue
        _LOGGER.debug(
            "%s found in status for device %s. Creating SyrConnectBooleanSwitch.",
            sensor_key,
            device_id,
        )
        entities.append(
            SyrConnectBooleanSwitch(coordinator, device_id, device_name, sensor_key)
        )
    return entities


class SyrConnectBooleanSwitch(SyrConnectEntity, SwitchEntity):
    """Generic switch entity for boolean get<KEY>/set<KEY> settings (e.g. getBUZ, getDFI)."""

    entity_description: SwitchEntityDescription

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
    ) -> None:
        """Initialize the switch."""
        _LOGGER.debug(
            "Initializing SyrConnectBooleanSwitch: device_id=%s, name=%s, sensor_key=%s",
            device_id,
            device_name,
            sensor_key,
        )
        super().__init__(coordinator, device_id, device_name, "switch", sensor_key)

        self._sensor_key = sensor_key
        self.entity_description = _SYR_CONNECT_SWITCH_DESCRIPTIONS[sensor_key]
        # The device reports the opposite of the switch, e.g. True means the function
        # is disabled (getFD1-3, HygBox)
        profile = self.device_model.device_profile
        self._inverted = profile is not None and sensor_key in profile.inverted_switches

        # Use a platform-specific suffix to avoid unique_id collision with the
        # binary_sensor that represents the same underlying key (getBUZ).
        # Only lowercase device_id/key, not entry_id (a case-sensitive ULID) -
        # otherwise this would never match the entry_id casing written by the
        # v6->v7 registry migration.
        self._attr_unique_id = build_unique_id(
            coordinator.entry_id, device_id.lower(), f"{sensor_key}_switch".lower()
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the setting is enabled."""
        if self._device is None:
            return None
        value = self._status.get(self._sensor_key)
        if value is None:
            return None
        # A reported but unknown value (e.g. empty) is shown as off
        enabled = is_value_true(value)
        return not enabled if self._inverted else enabled

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        if self._sensor_key in ("getIFL", "getMFL"):
            self._check_filling_allowed()
        await self._set_value(True)

    def _check_filling_allowed(self) -> None:
        """Refuse to start a filling that the device does not allow now.

        The initial (getIFL) and the manual filling (getMFL) can only be started
        while the automatic filling mode (getDFI) is off, the initial filling also
        only while the device is idle (getSTA 0). Turning a filling off is always
        allowed.

        Raises:
            ServiceValidationError: If the filling cannot be started.
        """
        dfi = self._status.get("getDFI")
        if dfi is not None:
            profile = self.device_model.device_profile
            dfi_inverted = profile is not None and "getDFI" in profile.inverted_switches
            if is_value_true(dfi) is not dfi_inverted:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="filling_blocked_by_filling_mode",
                    translation_placeholders={
                        "device": self._device_name,
                        "entity": self._entity_name,
                    },
                )
        sta = self._status.get("getSTA")
        if self._sensor_key == "getIFL" and sta is not None and str(sta) != "0":
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="filling_requires_standby",
                translation_placeholders={
                    "device": self._device_name,
                    "entity": self._entity_name,
                },
            )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self._set_value(False)

    async def _set_value(self, state: bool) -> None:
        """Set the boolean value via API."""
        if self._inverted:
            state = not state
        # Mirror the exact type of the current getter value so the setter
        # uses the same format the device expects.
        current = self._status.get(self._sensor_key)
        value: bool | int | str
        if isinstance(current, bool):
            value = state
        elif isinstance(current, int):
            value = 1 if state else 0
        elif isinstance(current, str) and current.strip() in ("0", "1"):
            value = "1" if state else "0"
        else:
            value = "True" if state else "False"
        # key for setting: remove leading 'get' and prefix with 'set'
        set_key = f"set{self._sensor_key[3:]}"
        try:
            # Use coordinator.async_set_device_value so the DCLG is resolved correctly
            await self.coordinator.async_set_device_value(
                self._device_id, set_key, value
            )
        except SyrConnectError as err:
            # Report the failure to the caller (UI, automation) like valve/select/button do;
            # swallowing it would make the service call look successful. The coordinator has
            # already restored the previous value.
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
        await self.coordinator.async_request_refresh()
