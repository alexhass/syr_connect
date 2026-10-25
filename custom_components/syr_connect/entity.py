"""Base entity for SYR Connect."""

from collections.abc import Callable, Iterable
from typing import Any, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SyrConnectDataUpdateCoordinator
from .data import SyrConnectDevice
from .helpers import (
    build_device_info,
    build_entity_id,
    build_unique_id,
    get_device,
    get_device_model,
    is_device_available,
)
from .models import SyrConnectModel


class SyrConnectEntity(CoordinatorEntity[SyrConnectDataUpdateCoordinator]):
    """Common base of all SYR Connect entities of a device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        platform: str,
        key: str,
        *,
        unique_key: str | None = None,
        translation_key: str | None = None,
    ) -> None:
        """Initialize the entity.

        Args:
            coordinator: Data update coordinator
            device_id: Device ID (serial number)
            device_name: Device display name
            platform: Entity platform, used in the entity_id (e.g. "binary_sensor")
            key: Entity key (e.g. "getBUZ"), used in the entity_id
            unique_key: Key for the unique_id if it differs from `key`, e.g. with a
                platform suffix ("getRTM_select"). Must keep existing unique_ids unchanged.
            translation_key: Translation key; defaults to `key` in lowercase
        """
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name

        self._attr_unique_id = build_unique_id(
            coordinator.entry_id, device_id, unique_key or key
        )
        self._attr_translation_key = translation_key or key.lower()
        # Technical entity_id from the serial number, independent of the display name
        self.entity_id = build_entity_id(platform, device_id, key)
        self._attr_device_info = build_device_info(
            device_id, device_name, coordinator.data
        )

    @property
    def _entity_name(self) -> str:
        """Return the entity name for exception messages.

        The translated name once the entity is added to Home Assistant, otherwise its
        translation key.
        """
        if self.platform is not None:
            name = self.name
            if isinstance(name, str):
                return name
        return str(self._attr_translation_key)

    @property
    def device_utc_offset(self) -> int | None:
        """Return the current UTC offset of the device's time zone in seconds, if known."""
        device = self._device
        return device.get("utc_offset") if device is not None else None

    @property
    def _device(self) -> SyrConnectDevice | None:
        """Return this entity's device from the coordinator data, or None if it is missing."""
        return get_device(self.coordinator.data, self._device_id)

    @property
    def _status(self) -> dict[str, Any]:
        """Return the status of this entity's device; empty if the device is missing."""
        device = self._device
        return device.get("status", {}) if device is not None else {}

    @property
    def device_model(self) -> SyrConnectModel:
        """Return the detected model of this entity's device."""
        return get_device_model(self._device)

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available (last update successful and device not offline)."""
        return is_device_available(self.coordinator, self._device_id)


def async_add_device_entities(
    entry: ConfigEntry,
    coordinator: SyrConnectDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
    build_entities: Callable[[SyrConnectDevice], Iterable[Entity]],
) -> None:
    """Add the entities of every device, also of devices that appear after the setup.

    A device is set up once, as soon as the coordinator data has a status for it: at
    the setup of the platform, or at the first update that has it, for a device added
    to the account later or one whose status could not be fetched at the setup.

    Args:
        entry: Config entry of the platform
        coordinator: Data update coordinator
        async_add_entities: Callback of the platform to add entities
        build_entities: Returns the entities of the platform for one device
    """
    set_up: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        entities: list[Entity] = []
        for device in coordinator.data.get("devices", []) if coordinator.data else []:
            if device["id"] in set_up or not device.get("status"):
                continue
            set_up.add(device["id"])
            entities.extend(build_entities(device))
        if entities:
            async_add_entities(entities)

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))
