"""Tests for update platform."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.update import SyrConnectFirmwareUpdate, async_setup_entry


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
        discovery_keys={},
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
    assert entity.latest_version != entity.installed_version


def test_update_entity_update_available_no_installed_version() -> None:
    """latest_version still signals an update when getVER is missing."""
    device = {"id": "SN5", "name": "Dev5", "status": {"getNOT": "01"}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN5", "Dev5", "")

    assert entity.installed_version is None
    assert entity.latest_version is not None


def test_update_entity_title_uses_detected_model() -> None:
    """title shows the detected model's display name, not the raw serial number."""
    device = {
        "id": "500AAA12345",
        "name": "500AAA12345",
        "status": {"getNOT": "FF", "getVER": "MuCo V.2.14", "getDFM": 3},
    }
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "500AAA12345", "500AAA12345", "")

    assert entity.title == "CLEAR PRO FILL All-in-One"


def test_update_entity_no_install_feature_supported() -> None:
    """No install command is known yet, so UpdateEntityFeature.INSTALL must not be set."""
    from homeassistant.components.update import UpdateEntityFeature

    device = {"id": "SN6", "name": "Dev6", "status": {"getNOT": "FF"}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN6", "Dev6", "")

    assert UpdateEntityFeature.INSTALL not in entity.supported_features


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


def test_update_entity_unique_id_has_update_suffix() -> None:
    """unique_id gets a '_update' suffix to avoid colliding with the getNOT sensor."""
    mock_coordinator = MagicMock()
    mock_coordinator.entry_id = "entry123"
    mock_coordinator.data = {"devices": [{"id": "SN8", "name": "Dev8", "status": {"getNOT": "FF"}}]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN8", "Dev8", "")

    assert entity._attr_unique_id == "entry123_sn8_getnot_update"


def test_update_entity_category_is_not_diagnostic() -> None:
    """entity_category must be None (not the DIAGNOSTIC default) to show in Settings > Updates."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [{"id": "SN11", "name": "Dev11", "status": {"getNOT": "01"}}]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN11", "Dev11", "")

    assert entity.entity_category is None


def test_update_entity_hidden_by_default() -> None:
    """The entity is hidden from the device page by default (Updates overview only)."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [{"id": "SN12", "name": "Dev12", "status": {"getNOT": "01"}}]}

    entity = SyrConnectFirmwareUpdate(mock_coordinator, "SN12", "Dev12", "")

    assert entity._attr_entity_registry_visible_default is False

