"""Base entity for SYR Connect."""

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import (
    build_device_info,
    build_entity_id,
    build_unique_id,
    is_device_available,
)


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

        self._attr_unique_id = build_unique_id(coordinator.entry_id, device_id, unique_key or key)
        self._attr_translation_key = translation_key or key.lower()
        # Technical entity_id from the serial number, independent of the display name
        self.entity_id = build_entity_id(platform, device_id, key)
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

    @property
    def _device(self) -> dict[str, Any] | None:
        """Return this entity's device from the coordinator data, or None if it is missing."""
        for device in (self.coordinator.data or {}).get("devices", []):
            if device.get("id") == self._device_id:
                return device
        return None

    @property
    def _status(self) -> dict[str, Any]:
        """Return the status of this entity's device; empty if the device is missing."""
        device = self._device
        return device.get("status", {}) if device is not None else {}

    @property
    def available(self) -> bool:
        """Return if the entity is available (last update successful and device not offline)."""
        return is_device_available(self.coordinator, self._device_id)
