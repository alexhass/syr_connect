"""Tests for switch platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from custom_components.syr_connect.const import (
    _SYR_CONNECT_DEVICE_SETTINGS,
    _SYR_CONNECT_DEVICE_USE_JSON_API,
    DOMAIN,
)
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.switch import (
    SyrConnectJsonAPISwitch,
    async_setup_entry,
)


async def test_async_setup_entry_no_data(hass: HomeAssistant) -> None:
    """Test setup when coordinator has no data."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    # Should return early without adding entities
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    mock_add_entities.assert_not_called()


async def test_async_setup_entry_device_not_dict(hass: HomeAssistant) -> None:
    """Test setup skips devices that should not create switches."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {"id": "dev_no_url", "name": "No URL Device", "base_path": None},  # base_path is None, skip
            {"id": "dev1", "base_path": "/api/v1/", "name": "Device 1"},  # Valid
        ]
    }
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    # Should only create entity for device with base_path
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert entities[0]._device_id == "dev1"


async def test_async_setup_entry_no_base_path(hass: HomeAssistant) -> None:
    """Test setup when devices have base_path set to None."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {"id": "dev1", "name": "Device 1", "base_path": None},  # base_path is None
        ]
    }
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    # Should not create entities without base_path
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 0


async def test_async_setup_entry_with_options(hass: HomeAssistant) -> None:
    """Test setup with device settings in options."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={
            _SYR_CONNECT_DEVICE_SETTINGS: {
                "dev1": {_SYR_CONNECT_DEVICE_USE_JSON_API: True}
            }
        },
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {"id": "dev1", "base_path": "/api/v1/", "name": "Device 1"},
        ]
    }
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert entities[0].is_on is True


async def test_async_setup_entry_with_in_memory_value(hass: HomeAssistant) -> None:
    """Test setup with in-memory device value."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "dev1",
                "base_path": "/api/v1/",
                "name": "Device 1",
                _SYR_CONNECT_DEVICE_USE_JSON_API: True,
            },
        ]
    }
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert entities[0].is_on is True


async def test_async_setup_entry_default_false(hass: HomeAssistant) -> None:
    """Test setup defaults to False when no settings."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {"id": "dev1", "base_path": "/api/v1/", "name": "Device 1"},
        ]
    }
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert entities[0].is_on is False


async def test_async_setup_entry_no_entry_options(hass: HomeAssistant) -> None:
    """Test setup when entry has no options attribute."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options=None,
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {"id": "dev1", "base_path": "/api/v1/", "name": "Device 1"},
        ]
    }
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1


async def test_async_setup_entry_device_no_name(hass: HomeAssistant) -> None:
    """Test setup when device has no name."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {"id": "dev1", "base_path": "/api/v1/"},  # No name
        ]
    }
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1
    # Should use device_id as name
    assert entities[0]._device_name == "dev1"


async def test_switch_initialization(hass: HomeAssistant) -> None:
    """Test switch initialization."""
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [{"id": "dev1", "name": "Device 1", "base_path": None}]}
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=True,
    )
    
    assert switch.is_on is True
    assert switch._device_id == "dev1"
    assert switch._device_name == "Device 1"
    assert switch.unique_id == "dev1_use_local_json_api"
    assert switch._attr_has_entity_name is True
    assert switch._attr_translation_key == _SYR_CONNECT_DEVICE_USE_JSON_API
    assert switch._attr_entity_category == EntityCategory.CONFIG


async def test_switch_is_on_property(hass: HomeAssistant) -> None:
    """Test switch is_on property."""
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": []}
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=False,
    )
    
    assert switch.is_on is False
    
    switch._is_on = True
    assert switch.is_on is True


async def test_switch_turn_on(hass: HomeAssistant) -> None:
    """Test switch turn_on method."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.options = {}
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [{"id": "dev1", "name": "Device 1", "base_path": None}]}
    mock_coordinator.config_entry = mock_entry
    mock_coordinator.async_request_refresh = AsyncMock()
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=False,
    )
    switch.hass = hass
    
    with patch.object(switch, 'async_write_ha_state') as mock_write_state:
        with patch.object(hass.config_entries, 'async_update_entry') as mock_update:
            await switch.async_turn_on()
            
            assert switch.is_on is True
            mock_write_state.assert_called_once()
            mock_update.assert_called_once()


async def test_switch_turn_off(hass: HomeAssistant) -> None:
    """Test switch turn_off method."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.options = {}
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [{"id": "dev1", "name": "Device 1", "base_path": None}]}
    mock_coordinator.config_entry = mock_entry
    mock_coordinator.async_request_refresh = AsyncMock()
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=True,
    )
    switch.hass = hass
    
    with patch.object(switch, 'async_write_ha_state') as mock_write_state:
        with patch.object(hass.config_entries, 'async_update_entry') as mock_update:
            await switch.async_turn_off()
            
            assert switch.is_on is False
            mock_write_state.assert_called_once()
            mock_update.assert_called_once()


async def test_switch_set_enabled_no_entry(hass: HomeAssistant) -> None:
    """Test _set_enabled when coordinator has no config_entry."""
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": []}
    # No config_entry attribute
    type(mock_coordinator).config_entry = None
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=False,
    )
    switch.hass = hass
    
    with patch.object(switch, 'async_write_ha_state') as mock_write_state:
        await switch._set_enabled(True)
        
        # Should fallback to in-memory only
        assert switch.is_on is True
        mock_write_state.assert_called_once()


async def test_switch_set_enabled_with_entry(hass: HomeAssistant) -> None:
    """Test _set_enabled successfully persists to config entry."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.options = {}
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [{"id": "dev1", "name": "Device 1", "base_path": None}]}
    mock_coordinator.config_entry = mock_entry
    mock_coordinator.async_request_refresh = AsyncMock()
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=False,
    )
    switch.hass = hass
    
    with patch.object(switch, 'async_write_ha_state') as mock_write_state:
        with patch.object(hass.config_entries, 'async_update_entry') as mock_update:
            await switch._set_enabled(True)
            
            assert switch.is_on is True
            mock_update.assert_called_once()
            mock_write_state.assert_called_once()
            mock_coordinator.async_request_refresh.assert_called_once()
            
            # Verify options structure
            call_args = mock_update.call_args
            assert call_args[0][0] == mock_entry
            options = call_args[1]['options']
            assert _SYR_CONNECT_DEVICE_SETTINGS in options
            assert "dev1" in options[_SYR_CONNECT_DEVICE_SETTINGS]
            assert options[_SYR_CONNECT_DEVICE_SETTINGS]["dev1"][_SYR_CONNECT_DEVICE_USE_JSON_API] is True


async def test_switch_set_enabled_entry_no_options(hass: HomeAssistant) -> None:
    """Test _set_enabled when entry has no options."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.options = None
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [{"id": "dev1", "name": "Device 1", "base_path": None}]}
    mock_coordinator.config_entry = mock_entry
    mock_coordinator.async_request_refresh = AsyncMock()
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=False,
    )
    switch.hass = hass
    
    with patch.object(switch, 'async_write_ha_state') as mock_write_state:
        with patch.object(hass.config_entries, 'async_update_entry') as mock_update:
            await switch._set_enabled(True)
            
            assert switch.is_on is True
            mock_update.assert_called_once()
            mock_write_state.assert_called_once()


async def test_switch_set_enabled_existing_device_settings(hass: HomeAssistant) -> None:
    """Test _set_enabled with existing device settings."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.options = {
        _SYR_CONNECT_DEVICE_SETTINGS: {
            "dev1": {"some_other_setting": "value"},
            "dev2": {"other_device": "value"},
        }
    }
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [{"id": "dev1", "name": "Device 1", "base_path": None}]}
    mock_coordinator.config_entry = mock_entry
    mock_coordinator.async_request_refresh = AsyncMock()
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=False,
    )
    switch.hass = hass
    
    with patch.object(switch, 'async_write_ha_state'):
        with patch.object(hass.config_entries, 'async_update_entry') as mock_update:
            await switch._set_enabled(True)
            
            # Verify existing settings are preserved
            call_args = mock_update.call_args
            options = call_args[1]['options']
            assert options[_SYR_CONNECT_DEVICE_SETTINGS]["dev1"]["some_other_setting"] == "value"
            assert options[_SYR_CONNECT_DEVICE_SETTINGS]["dev2"]["other_device"] == "value"
            assert options[_SYR_CONNECT_DEVICE_SETTINGS]["dev1"][_SYR_CONNECT_DEVICE_USE_JSON_API] is True


async def test_switch_set_enabled_updates_coordinator_device(hass: HomeAssistant) -> None:
    """Test _set_enabled updates device in coordinator data."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.options = {}
    
    device_dict = {"id": "dev1", "name": "Device 1", "base_path": None, _SYR_CONNECT_DEVICE_USE_JSON_API: False}
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [device_dict]}
    mock_coordinator.config_entry = mock_entry
    mock_coordinator.async_request_refresh = AsyncMock()
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=False,
    )
    switch.hass = hass
    
    with patch.object(switch, 'async_write_ha_state'):
        with patch.object(hass.config_entries, 'async_update_entry'):
            await switch._set_enabled(True)
            
            # Verify device dict was updated
            assert device_dict[_SYR_CONNECT_DEVICE_USE_JSON_API] is True


async def test_switch_set_enabled_device_not_in_coordinator(hass: HomeAssistant) -> None:
    """Test _set_enabled when device is not in coordinator data."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.options = {}
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [{"id": "other_dev", "name": "Other Device", "base_path": None}]}
    mock_coordinator.config_entry = mock_entry
    mock_coordinator.async_request_refresh = AsyncMock()
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=False,
    )
    switch.hass = hass
    
    with patch.object(switch, 'async_write_ha_state'):
        with patch.object(hass.config_entries, 'async_update_entry'):
            # Should not raise exception, just skip device update
            await switch._set_enabled(True)
            
            assert switch.is_on is True


async def test_switch_set_enabled_refresh_fails(hass: HomeAssistant) -> None:
    """Test _set_enabled when coordinator refresh fails."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.options = {}
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [{"id": "dev1", "name": "Device 1", "base_path": None}]}
    mock_coordinator.config_entry = mock_entry
    mock_coordinator.async_request_refresh = AsyncMock(side_effect=Exception("Refresh failed"))
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=False,
    )
    switch.hass = hass
    
    with patch.object(switch, 'async_write_ha_state') as mock_write_state:
        with patch.object(hass.config_entries, 'async_update_entry'):
            # Should not raise exception despite refresh failure
            await switch._set_enabled(True)
            
            assert switch.is_on is True
            mock_write_state.assert_called_once()


async def test_switch_set_enabled_persist_exception(hass: HomeAssistant) -> None:
    """Test _set_enabled handles exceptions during persist."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.options = {}
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [{"id": "dev1", "name": "Device 1", "base_path": None}]}
    mock_coordinator.config_entry = mock_entry
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=False,
    )
    switch.hass = hass
    
    with patch.object(hass.config_entries, 'async_update_entry', side_effect=Exception("Update failed")):
        # Should not raise exception, just log it
        await switch._set_enabled(True)
        
        # State may or may not be updated depending on where exception occurs
        # Just verify no exception is raised


async def test_switch_set_enabled_outer_exception(hass: HomeAssistant) -> None:
    """Test _set_enabled handles outer exception gracefully."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.options = {}
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [{"id": "dev1", "name": "Device 1", "base_path": None}]}
    mock_coordinator.config_entry = mock_entry
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=False,
    )
    switch.hass = hass
    
    # Make async_update_entry raise an exception to trigger outer exception handler
    with patch.object(hass.config_entries, 'async_update_entry', side_effect=Exception("Test exception")):
        # Should handle exception gracefully and not raise
        await switch._set_enabled(True)
        # The state may or may not be updated depending on where exception occurs


async def test_async_setup_entry_device_settings_no_device_id(hass: HomeAssistant) -> None:
    """Test setup with device settings that don't contain the device_id."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={
            _SYR_CONNECT_DEVICE_SETTINGS: {
                "other_dev": {_SYR_CONNECT_DEVICE_USE_JSON_API: True}
            }
        },
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {"id": "dev1", "base_path": "/api/v1/", "name": "Device 1"},
        ]
    }
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1
    # Should default to False when device_id not in settings
    assert entities[0].is_on is False


async def test_async_setup_entry_device_use_json_api_none(hass: HomeAssistant) -> None:
    """Test setup when device has _SYR_CONNECT_DEVICE_USE_JSON_API set to None."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "dev1",
                "base_path": "/api/v1/",
                "name": "Device 1",
                _SYR_CONNECT_DEVICE_USE_JSON_API: None,  # Explicitly None
            },
        ]
    }
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1
    # Should default to False when value is None
    assert entities[0].is_on is False


async def test_async_setup_entry_empty_device_settings(hass: HomeAssistant) -> None:
    """Test setup when device_settings is empty dict."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={_SYR_CONNECT_DEVICE_SETTINGS: {}},  # Empty dict
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {"id": "dev1", "base_path": "/api/v1/", "name": "Device 1"},
        ]
    }
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert entities[0].is_on is False


async def test_switch_set_enabled_value_false(hass: HomeAssistant) -> None:
    """Test _set_enabled with False value."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.options = {}
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {"devices": [{"id": "dev1", "name": "Device 1", "base_path": None}]}
    mock_coordinator.config_entry = mock_entry
    mock_coordinator.async_request_refresh = AsyncMock()
    
    switch = SyrConnectJsonAPISwitch(
        coordinator=mock_coordinator,
        device_id="dev1",
        device_name="Device 1",
        initial=True,
    )
    switch.hass = hass
    
    with patch.object(switch, 'async_write_ha_state') as mock_write_state:
        with patch.object(hass.config_entries, 'async_update_entry') as mock_update:
            await switch._set_enabled(False)
            
            assert switch.is_on is False
            mock_update.assert_called_once()
            mock_write_state.assert_called_once()
            
            # Verify False value is persisted
            call_args = mock_update.call_args
            options = call_args[1]['options']
            assert options[_SYR_CONNECT_DEVICE_SETTINGS]["dev1"][_SYR_CONNECT_DEVICE_USE_JSON_API] is False


async def test_async_setup_entry_multiple_devices(hass: HomeAssistant) -> None:
    """Test setup with multiple devices with different configurations."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={"username": "test", "password": "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={
            _SYR_CONNECT_DEVICE_SETTINGS: {
                "dev1": {_SYR_CONNECT_DEVICE_USE_JSON_API: True}
            }
        },
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {"id": "dev1", "base_path": "/api/v1/", "name": "Device 1"},
            {"id": "dev2", "base_path": "/api/v2/", "name": "Device 2", _SYR_CONNECT_DEVICE_USE_JSON_API: True},
            {"id": "dev3", "base_path": "/api/v3/"},  # No name
            {"id": "dev4", "base_path": None},  # base_path is None, should be skipped
        ]
    }
    
    config_entry.runtime_data = mock_coordinator
    
    mock_add_entities = MagicMock()
    
    await async_setup_entry(hass, config_entry, mock_add_entities)
    
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 3  # dev4 skipped
    assert entities[0].is_on is True  # dev1 from options
    assert entities[1].is_on is True  # dev2 from device
    assert entities[2].is_on is False  # dev3 default
