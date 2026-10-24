"""Update platform for SYR Connect integration."""

import logging
from time import monotonic
from typing import Any, override

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SyrConnectDataUpdateCoordinator
from .entity import SyrConnectEntity
from .exceptions import SyrConnectError
from .helpers import (
    build_unique_id,
    get_device_model,
    get_model_supported_keys,
    get_sensor_not_map,
    registry_cleanup,
)

_LOGGER = logging.getLogger(__name__)

# Give up showing progress if getNOT never switches to "04".
_SYR_CONNECT_UPDATE_INSTALL_TIMEOUT_SECONDS = 600

# Shown as "latest version" because the API never reports the real new version number.
_SYR_CONNECT_UPDATE_NEW_VERSION_PLACEHOLDER = "New version available"

# Descriptions of all update entities
_SYR_CONNECT_UPDATE_TYPES: tuple[UpdateEntityDescription, ...] = (
    UpdateEntityDescription(
        key="getNOT",  # Notification code; "01" == new_software_available
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

_SYR_CONNECT_UPDATE_DESCRIPTIONS: dict[str, UpdateEntityDescription] = {
    description.key: description for description in _SYR_CONNECT_UPDATE_TYPES
}

# Supported keys for the update platform — used by registry_cleanup to remove stale entries.
_SYR_CONNECT_UPDATE_SUPPORTED_KEYS = set(_SYR_CONNECT_UPDATE_DESCRIPTIONS)


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
        hass,
        coordinator.data,
        "update",
        allowed_keys=_SYR_CONNECT_UPDATE_SUPPORTED_KEYS,
        entry_id=coordinator.entry_id,
    )

    entities: list[UpdateEntity] = []
    for device in coordinator.data.get("devices", []):
        device_id = device["id"]
        device_name = device["name"]
        status = device.get("status", {})

        # Scope to the detected model (falls back to the global allowlist for
        # models that haven't opted into per-model key lists).
        supported_update_keys = get_model_supported_keys(
            get_device_model(device), "update", _SYR_CONNECT_UPDATE_SUPPORTED_KEYS
        )
        if "getNOT" not in supported_update_keys or "getNOT" not in status:
            continue

        entities.append(SyrConnectFirmwareUpdate(coordinator, device_id, device_name))

    if entities:
        _LOGGER.debug("Adding %d update entity(ies) total", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No update entities found for any device")


class SyrConnectFirmwareUpdate(SyrConnectEntity, UpdateEntity):
    """Firmware update indicator derived from getNOT == "01" (new_software_available).

    The SYR Connect API does not expose the actual target firmware version, so
    `latest_version` uses a placeholder string instead of a real version when an
    update is signalled. Installing is supported via setUPG, a write-only command
    shared identically by 8 device base classes (SafeTech, SafeFloor, LEX Plus,
    All-in-One+, MultiController, HygBox, Dosing Pump, Trio LS); it is always sent
    with an empty value (see docs/syrconnect-protocol.md).

    After install is triggered, `in_progress` stays True until getNOT switches to
    "04" (new_software_installed) or _SYR_CONNECT_UPDATE_INSTALL_TIMEOUT_SECONDS have passed.
    """

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the update entity."""
        # build_device_info() (in the base class) already replaces a bare-serial device name
        # with "<model> (<serial>)" when no real device name is available - that's what
        # shows as the heading in the Settings > Updates overview.
        super().__init__(
            coordinator,
            device_id,
            device_name,
            "update",
            "getNOT",
            translation_key="getnot_update",
        )

        self.entity_description = _SYR_CONNECT_UPDATE_DESCRIPTIONS["getNOT"]
        self._install_started: float | None = None

        # "_update" suffix keeps this apart from the existing getNOT sensor's
        # unique_id, mirroring switch.py's "_switch" suffix convention. Built in lowercase,
        # unlike the base class; must stay unchanged to keep existing registry entries.
        self._attr_unique_id = build_unique_id(
            coordinator.entry_id, device_id.lower(), "getNOT_update".lower()
        )

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        # The device goes offline while flashing; stay available so the progress bar remains visible.
        if self.in_progress:
            return True
        return super().available

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the currently installed firmware version (getVER)."""
        version = self._status.get("getVER")
        return str(version) if version else None

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest available firmware version.

        The API only ever reports a notification code (getNOT), never the actual
        new version number. When getNOT signals "new_software_available", return
        _SYR_CONNECT_UPDATE_NEW_VERSION_PLACEHOLDER (never equal to installed_version) so the entity
        reports an update as available; otherwise report the installed version
        unchanged (no update pending).
        """
        status = self._status
        mapped, _raw = get_sensor_not_map(self.device_model, status.get("getNOT"))
        if mapped == "new_software_available":
            return _SYR_CONNECT_UPDATE_NEW_VERSION_PLACEHOLDER
        return self.installed_version

    def _install_timed_out(self) -> bool:
        return (
            self._install_started is not None
            and monotonic() - self._install_started
            >= _SYR_CONNECT_UPDATE_INSTALL_TIMEOUT_SECONDS
        )

    @property
    @override
    def in_progress(self) -> bool:
        """Return True from install trigger until getNOT reports "04" or the timeout expires."""
        return self._install_started is not None and not self._install_timed_out()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Finish the progress state on getNOT == "04" (new_software_installed) or timeout."""
        if self._install_started is not None:
            status = self._status
            mapped, _raw = get_sensor_not_map(self.device_model, status.get("getNOT"))
            _LOGGER.debug(
                "Firmware update %s in progress, getNOT=%s",
                self._device_id,
                status.get("getNOT"),
            )
            if mapped == "new_software_installed":
                _LOGGER.debug(
                    "Firmware update %s finished (getNOT=04)", self._device_id
                )
                self._install_started = None
            elif self._install_timed_out():
                _LOGGER.warning(
                    "Firmware update for %s did not report completion (getNOT=04) within %d s",
                    self._device_id,
                    _SYR_CONNECT_UPDATE_INSTALL_TIMEOUT_SECONDS,
                )
                self._install_started = None
        super()._handle_coordinator_update()

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Trigger a firmware update by sending setUPG (always with an empty value)."""
        _LOGGER.debug(
            "Triggering firmware update for %s (getNOT=%s)",
            self._device_id,
            self._status.get("getNOT"),
        )
        self._install_started = monotonic()
        try:
            await self.coordinator.async_set_device_value(self._device_id, "setUPG", "")
        except (SyrConnectError, ValueError, TypeError, KeyError) as err:
            self._install_started = None
            _LOGGER.error(
                "Failed to trigger firmware update for %s: %s", self._device_id, err
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_update_failed",
                translation_placeholders={"device": self._device_name},
            ) from err
