"""Tests for update platform."""

from __future__ import annotations

import logging
from time import monotonic
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.update import (
    INSTALL_TIMEOUT_SECONDS,
    NEW_VERSION_PLACEHOLDER,
    SyrConnectFirmwareUpdate,
    async_setup_entry,
)


def _build_entry(entry_id: str, coordinator: MagicMock) -> ConfigEntry:
    entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test", CONF_PASSWORD: "test"},
        source="user",
        entry_id=entry_id,
        unique_id=f"unique_{entry_id}",
        discovery_keys=MappingProxyType({}),
        options={},
        subentries_data={},
    )
    entry.runtime_data = coordinator
    return entry


async def test_async_setup_entry_no_coordinator_data_logs_warning(hass: HomeAssistant, caplog) -> None:
    """When `entry.runtime_data.data` is falsy, setup should warn and return."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    config_entry = _build_entry("entry_nodata", mock_coordinator)

    mock_add_entities = MagicMock()

    caplog.set_level(logging.WARNING)
    await async_setup_entry(hass, config_entry, mock_add_entities)

    mock_add_entities.assert_not_called()
    assert "No coordinator data available for update platform" in caplog.text


async def test_async_setup_entry_no_entities_when_getnot_missing(hass: HomeAssistant) -> None:
    """No update entity is created for a device without a getNOT key."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [{"id": "SN1", "name": "Dev1", "status": {}}]}
    config_entry = _build_entry("entry_no_getnot", mock_coordinator)

    mock_add_entities = MagicMock()
    await async_setup_entry(hass, config_entry, mock_add_entities)

    mock_add_entities.assert_not_called()


async def test_async_setup_entry_creates_entity_when_getnot_present(hass: HomeAssistant) -> None:
    """An update entity is created for a device reporting getNOT."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "devices": [{"id": "SN2", "name": "Dev2", "status": {"getNOT": "FF", "getVER": "1.0"}}]
    }
    config_entry = _build_entry("entry_creates", mock_coordinator)

    mock_add_entities = MagicMock()
    await async_setup_entry(hass, config_entry, mock_add_entities)

    mock_add_entities.assert_called_once()
    args = mock_add_entities.call_args[0][0]
    assert len(args) == 1
    assert isinstance(args[0], SyrConnectFirmwareUpdate)


def test_update_entity_no_update_pending() -> None:
    """installed_version == latest_version when getNOT does not signal a new update."""
    device = {"id": "SN3", "name": "Dev3", "status": {"getNOT": "FF", "getVER": "MuCo V.2.14"}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN3", "Dev3", "")

    assert entity.installed_version == "MuCo V.2.14"
    assert entity.latest_version == "MuCo V.2.14"


def test_update_entity_update_available() -> None:
    """latest_version differs from installed_version when getNOT == '01'."""
    device = {"id": "SN4", "name": "Dev4", "status": {"getNOT": "01", "getVER": "MuCo V.2.14"}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN4", "Dev4", "")

    assert entity.installed_version == "MuCo V.2.14"
    assert entity.latest_version == NEW_VERSION_PLACEHOLDER


def test_update_entity_update_available_no_installed_version() -> None:
    """latest_version still signals an update when getVER is missing."""
    device = {"id": "SN5", "name": "Dev5", "status": {"getNOT": "01"}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN5", "Dev5", "")

    assert entity.installed_version is None
    assert entity.latest_version == NEW_VERSION_PLACEHOLDER


def test_update_entity_naming_uses_translation_key() -> None:
    """The entity uses has_entity_name + translation_key, not a custom title/name."""
    device = {
        "id": "500AAA12345",
        "name": "500AAA12345",
        "status": {"getNOT": "FF", "getVER": "MuCo V.2.14", "getDFM": 3},
    }
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "500AAA12345", "500AAA12345", "")

    assert entity._attr_has_entity_name is True
    assert entity._attr_translation_key == "getnot_update"


def test_update_entity_install_feature_supported() -> None:
    """UpdateEntityFeature.INSTALL is set now that setUPG is known to trigger an update."""
    from homeassistant.components.update import UpdateEntityFeature

    device = {"id": "SN6", "name": "Dev6", "status": {"getNOT": "FF"}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN6", "Dev6", "")

    assert UpdateEntityFeature.INSTALL in entity.supported_features


async def test_update_entity_async_install_sends_empty_setupg() -> None:
    """async_install() sends setUPG with an empty value."""
    device = {"id": "SN6", "name": "Dev6", "status": {"getNOT": "01"}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}
    mock_coordinator.async_set_device_value = AsyncMock()

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN6", "Dev6", "")
    await entity.async_install(version=None, backup=False)

    mock_coordinator.async_set_device_value.assert_called_once_with("SN6", "setUPG", "")


async def test_update_entity_async_install_wraps_errors() -> None:
    """async_install() wraps failures from the coordinator in HomeAssistantError."""
    device = {"id": "SN6", "name": "Dev6", "status": {"getNOT": "01"}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}
    mock_coordinator.async_set_device_value = AsyncMock(side_effect=ValueError("boom"))

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN6", "Dev6", "")
    with pytest.raises(HomeAssistantError):
        await entity.async_install(version=None, backup=False)

    assert entity.in_progress is False


async def test_update_entity_in_progress_until_getnot_04() -> None:
    """in_progress is True after install until getNOT switches to '04'."""
    status = {"getNOT": "01", "getVER": "MuCo V.2.14"}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [{"id": "SN9", "name": "Dev9", "status": status}]}
    mock_coordinator.async_set_device_value = AsyncMock()

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN9", "Dev9", "")
    entity.async_write_ha_state = MagicMock()  # type: ignore[method-assign, misc]
    assert entity.in_progress is False
    assert UpdateEntityFeature.PROGRESS in entity.supported_features

    await entity.async_install(version=None, backup=False)
    assert entity.in_progress is True

    # Still installing: getNOT stays at "01".
    entity._handle_coordinator_update()
    assert entity.in_progress is True

    status["getNOT"] = "04"
    entity._handle_coordinator_update()
    assert entity.in_progress is False


async def test_update_entity_in_progress_times_out() -> None:
    """in_progress ends after INSTALL_TIMEOUT_SECONDS even if getNOT never reaches '04'."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [{"id": "SN12", "name": "Dev12", "status": {"getNOT": "01"}}]}
    mock_coordinator.async_set_device_value = AsyncMock()

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN12", "Dev12", "")
    entity.async_write_ha_state = MagicMock()  # type: ignore[method-assign, misc]

    with patch("custom_components.syr_connect.update.monotonic", return_value=1000.0):
        await entity.async_install(version=None, backup=False)
        assert entity.in_progress is True

    with patch("custom_components.syr_connect.update.monotonic", return_value=1000.0 + INSTALL_TIMEOUT_SECONDS - 1):
        assert entity.in_progress is True

    with patch("custom_components.syr_connect.update.monotonic", return_value=1000.0 + INSTALL_TIMEOUT_SECONDS):
        assert entity.in_progress is False
        entity._handle_coordinator_update()

    assert entity._install_started is None


def test_update_entity_not_in_progress_without_install() -> None:
    """getNOT == '01' alone does not show progress; only a triggered install does."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [{"id": "SN10", "name": "Dev10", "status": {"getNOT": "01"}}]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN10", "Dev10", "")
    entity.async_write_ha_state = MagicMock()  # type: ignore[method-assign, misc]
    entity._handle_coordinator_update()

    assert entity.in_progress is False


def test_update_entity_available_while_installing_even_if_device_offline() -> None:
    """The device is offline while flashing; the entity must stay available during install."""
    device = {"id": "SN13", "name": "Dev13", "status": {"getNOT": "01"}, "available": False}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}
    mock_coordinator.last_update_success = False

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN13", "Dev13", "")
    assert entity.available is False

    entity._install_started = monotonic()
    assert entity.available is True


def test_update_entity_available_property() -> None:
    """available reflects coordinator.last_update_success and per-device availability."""
    device = {"id": "SN7", "name": "Dev7", "status": {"getNOT": "FF"}, "available": False}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}
    mock_coordinator.last_update_success = True

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN7", "Dev7", "")
    assert entity.available is False

    mock_coordinator.last_update_success = False
    assert entity.available is False


def test_get_status_returns_empty_dict_when_device_missing() -> None:
    """_get_status returns {} when the device is no longer in coordinator.data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": []}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN_MISSING", "DevMissing", "")

    assert entity._get_status() == {}


def test_available_defaults_true_when_device_missing() -> None:
    """available defaults to True when the device is no longer in coordinator.data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": []}
    mock_coordinator.last_update_success = True

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN_MISSING", "DevMissing", "")

    assert entity.available is True


def test_update_entity_unique_id_has_update_suffix() -> None:
    """unique_id gets a '_update' suffix to avoid colliding with the getNOT sensor."""
    mock_coordinator = MagicMock()
    mock_coordinator.entry_id = "entry123"
    mock_coordinator.data = {"devices": [{"id": "SN8", "name": "Dev8", "status": {"getNOT": "FF"}}]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN8", "Dev8", "")

    assert entity._attr_unique_id == "entry123_sn8_getnot_update"


def test_update_entity_category_is_diagnostic() -> None:
    """entity_category is DIAGNOSTIC so it doesn't show under the device page's Controls section."""
    from homeassistant.const import EntityCategory

    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [{"id": "SN11", "name": "Dev11", "status": {"getNOT": "01"}}]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN11", "Dev11", "")

    assert entity.entity_category is EntityCategory.DIAGNOSTIC

