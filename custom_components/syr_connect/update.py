"""Update platform for SYR Connect integration."""

from __future__ import annotations

import logging
from time import monotonic
from typing import Any, cast

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import _SYR_CONNECT_UPDATE_KNOWN_KEYS
from .coordinator import SyrConnectDataUpdateCoordinator
from .exceptions import SyrConnectError
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

# Give up showing progress if getNOT never switches to "04".
INSTALL_TIMEOUT_SECONDS = 600


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

    The SYR Connect API does not expose the actual target firmware version, so
    `latest_version` uses a placeholder string instead of a real version when an
    update is signalled. Installing is supported via setUPG, a write-only command
    shared identically by 8 device base classes (SafeTech, SafeFloor, LEX Plus,
    All-in-One+, MultiController, HygBox, Dosing Pump, Trio LS); it is always sent
    with an empty value (see docs/syrconnect-protocol.md).

    After install is triggered, `in_progress` stays True until getNOT switches to
    "04" (new_software_installed) or INSTALL_TIMEOUT_SECONDS have passed.
    """

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

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
        self._install_started: float | None = None

        # "_update" suffix keeps this apart from the existing getNOT sensor's
        # unique_id, mirroring switch.py's "_switch" suffix convention.
        self._attr_unique_id = build_unique_id(coordinator.entry_id, device_id.lower(), "getNOT_update".lower())
        self._attr_has_entity_name = True
        self._attr_translation_key = "getnot_update"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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

    def _install_timed_out(self) -> bool:
        return self._install_started is not None and monotonic() - self._install_started >= INSTALL_TIMEOUT_SECONDS

    @property
    def in_progress(self) -> bool:
        """Return True from install trigger until getNOT reports "04" or the timeout expires."""
        return self._install_started is not None and not self._install_timed_out()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Finish the progress state on getNOT == "04" (new_software_installed) or timeout."""
        if self._install_started is not None:
            status = self._get_status()
            mapped, _raw = get_sensor_not_map(status, status.get("getNOT"))
            if mapped == "new_software_installed":
                self._install_started = None
            elif self._install_timed_out():
                _LOGGER.warning(
                    "Firmware update for %s did not report completion (getNOT=04) within %d s",
                    self._device_id,
                    INSTALL_TIMEOUT_SECONDS,
                )
                self._install_started = None
        super()._handle_coordinator_update()

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Trigger a firmware update by sending setUPG (always with an empty value)."""
        coordinator = cast(SyrConnectDataUpdateCoordinator, self.coordinator)
        self._install_started = monotonic()
        try:
            await coordinator.async_set_device_value(self._device_id, "setUPG", "")
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            self._install_started = None
            raise HomeAssistantError(f"Failed to trigger firmware update: {err}") from err
