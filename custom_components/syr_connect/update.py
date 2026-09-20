"""Update platform for SYR Connect integration."""

from __future__ import annotations

import logging

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import _SYR_CONNECT_UPDATE_KNOWN_KEYS
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import (
    build_device_info,
    build_entity_id,
    build_unique_id,
    get_model_known_keys,
    get_sensor_not_map,
    registry_cleanup,
)
from .models import detect_model

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SYR Connect update entities (getNOT-derived firmware update indicator)."""
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data

    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for update platform")
        return

    registry_cleanup(
        hass, coordinator.data, "update",
        allowed_keys=_SYR_CONNECT_UPDATE_KNOWN_KEYS,
        entry_id=coordinator.entry_id,
    )

    entities: list[UpdateEntity] = []
    for device in coordinator.data.get("devices", []):
        device_id = device.get("id")
        device_name = device.get("name", device_id)
        project_id = device.get("project_id", "")
        status = device.get("status", {})

        # Scope to the detected model (falls back to the global allowlist for
        # models that haven't opted into per-model key lists).
        known_update_keys = get_model_known_keys(detect_model(status), "update", _SYR_CONNECT_UPDATE_KNOWN_KEYS)
        if "getNOT" not in known_update_keys or "getNOT" not in status:
            continue

        entities.append(SyrConnectFirmwareUpdate(coordinator, device_id, device_name, project_id))

    if entities:
        _LOGGER.debug("Adding %d update entity(ies) total", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No update entities found for any device")


class SyrConnectFirmwareUpdate(CoordinatorEntity, UpdateEntity):
    """Firmware update indicator derived from getNOT == "01" (new_software_available).

    The SYR Connect API does not expose the actual target firmware version, nor a
    documented command to trigger an install remotely - so `latest_version` uses a
    placeholder string instead of a real version when an update is signalled, and
    no UpdateEntityFeature is set (no install button). Once the install command is
    known, add UpdateEntityFeature.INSTALL to _attr_supported_features and
    implement async_install() here.
    """

    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        project_id: str,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)

        self._device_id = device_id
        self._device_name = device_name
        self._project_id = project_id

        # "_update" suffix keeps this apart from the existing getNOT sensor's
        # unique_id, mirroring switch.py's "_switch" suffix convention.
        self._attr_unique_id = build_unique_id(coordinator.entry_id, device_id.lower(), "getNOT_update".lower())
        self._attr_has_entity_name = True
        self._attr_translation_key = "getnot_update"
        # Without UpdateEntityFeature.INSTALL, HA defaults entity_category to
        # DIAGNOSTIC - which the Settings > Updates overview excludes. Force it
        # back to None (primary entity) so a pending update is still surfaced there.
        self._attr_entity_category = None

        self.entity_id = build_entity_id("update", device_id, "getNOT")
        # build_device_info() already replaces a bare-serial device name with
        # "<model> (<serial>)" when no real device name is available - that's
        # what shows as the heading in the Settings > Updates overview.
        self._attr_device_info = build_device_info(device_id, device_name, coordinator.data)

    def _get_status(self) -> dict:
        """Return the current status dict for this device, or {} if not found."""
        for device in self.coordinator.data.get("devices", []):
            if device["id"] == self._device_id:
                return device.get("status", {})
        return {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        for device in self.coordinator.data.get("devices", []):
            if device["id"] == self._device_id:
                return device.get("available", True)
        return True

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed firmware version (getVER)."""
        version = self._get_status().get("getVER")
        return str(version) if version else None

    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version.

        The API only ever reports a notification code (getNOT), never the actual
        new version number. When getNOT signals "new_software_available", return a
        placeholder that differs from installed_version so the entity reports an
        update as available; otherwise report the installed version unchanged
        (no update pending).
        """
        status = self._get_status()
        installed = self.installed_version
        mapped, _raw = get_sensor_not_map(status, status.get("getNOT"))
        if mapped == "new_software_available":
            return f"{installed} (update available)" if installed else "update available"
        return installed
