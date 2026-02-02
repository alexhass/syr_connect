"""Tests for __init__.py integration setup."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.syr_connect import (
    async_options_update_listener,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.syr_connect.const import DOMAIN


async def test_async_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup of config entry."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    with patch("custom_components.syr_connect.SyrConnectDataUpdateCoordinator") as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator
        
        with patch.object(hass.config_entries, "async_forward_entry_setups", return_value=AsyncMock()):
            result = await async_setup_entry(hass, config_entry)
    
    assert result is True
    assert config_entry.runtime_data == mock_coordinator
    mock_coordinator.async_config_entry_first_refresh.assert_called_once()


async def test_async_setup_entry_connection_failure(hass: HomeAssistant) -> None:
    """Test setup fails when connection to API fails."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    with patch("custom_components.syr_connect.SyrConnectDataUpdateCoordinator") as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        mock_coordinator_class.return_value = mock_coordinator
        
        with pytest.raises(ConfigEntryNotReady, match="Unable to connect to SYR Connect"):
            await async_setup_entry(hass, config_entry)


async def test_async_setup_entry_with_custom_scan_interval(hass: HomeAssistant) -> None:
    """Test setup with custom scan interval from options."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={"scan_interval": 120},  # Custom interval
        subentries_data={},
    )
    
    with patch("custom_components.syr_connect.SyrConnectDataUpdateCoordinator") as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator
        
        with patch.object(hass.config_entries, "async_forward_entry_setups", return_value=AsyncMock()):
            result = await async_setup_entry(hass, config_entry)
    
    assert result is True
    # Verify coordinator was created with custom scan interval
    mock_coordinator_class.assert_called_once()
    call_args = mock_coordinator_class.call_args
    assert call_args[0][4] == 120  # scan_interval argument


async def test_async_unload_entry_success(hass: HomeAssistant) -> None:
    """Test successful unload of config entry."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await async_unload_entry(hass, config_entry)
    
    assert result is True


async def test_async_unload_entry_failure(hass: HomeAssistant) -> None:
    """Test unload returns False when platforms fail to unload."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=False):
        result = await async_unload_entry(hass, config_entry)
    
    assert result is False


async def test_async_options_update_listener_interval_changed(hass: HomeAssistant) -> None:
    """Test options update listener when scan interval changes."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={"scan_interval": 120},  # New interval
        subentries_data={},
    )
    
    mock_coordinator = MagicMock()
    mock_coordinator.update_interval = timedelta(seconds=60)  # Old interval
    mock_coordinator.async_request_refresh = AsyncMock()
    config_entry.runtime_data = mock_coordinator
    
    await async_options_update_listener(hass, config_entry)
    
    # Verify interval was updated
    assert config_entry.runtime_data.update_interval == timedelta(seconds=120)
    mock_coordinator.async_request_refresh.assert_called_once()


async def test_async_options_update_listener_interval_unchanged(hass: HomeAssistant) -> None:
    """Test options update listener when scan interval unchanged."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={"scan_interval": 60},  # Same as current
        subentries_data={},
    )
    
    mock_coordinator = MagicMock()
    mock_coordinator.update_interval = timedelta(seconds=60)  # Same interval
    mock_coordinator.async_request_refresh = AsyncMock()
    config_entry.runtime_data = mock_coordinator
    
    await async_options_update_listener(hass, config_entry)
    
    # Verify refresh was not called
    mock_coordinator.async_request_refresh.assert_not_called()


async def test_async_reload_entry(hass: HomeAssistant) -> None:
    """Test reload entry."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    with patch.object(hass.config_entries, "async_reload", return_value=AsyncMock()) as mock_reload:
        await async_reload_entry(hass, config_entry)
        
        mock_reload.assert_called_once_with("test_entry_id")
