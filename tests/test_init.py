"""Test the SYR Connect initialization."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from syr_connect.const import DOMAIN
from .conftest import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test successful setup of entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "syr_connect.coordinator.SyrConnectAPI"
    ) as mock_api_class:
        # Mock API instance
        mock_api = MagicMock()
        mock_api.login = AsyncMock(return_value=True)
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "p1", "name": "Project 1"}]
        mock_api.get_devices = AsyncMock(return_value=[
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "p1",
                "dclg": "dclg1",
            }
        ])
        mock_api.get_device_status = AsyncMock(return_value={
            "getPRS": "50",
            "getFLO": "10",
        })
        mock_api_class.return_value = mock_api

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    assert DOMAIN in hass.data


async def test_setup_entry_connection_error(hass: HomeAssistant) -> None:
    """Test setup entry with connection error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "syr_connect.coordinator.SyrConnectAPI"
    ) as mock_api_class:
        # Mock API that fails on first_refresh
        mock_api = MagicMock()
        mock_api.login = AsyncMock(side_effect=Exception("Connection failed"))
        mock_api_class.return_value = mock_api

        with pytest.raises(ConfigEntryNotReady):
            await hass.config_entries.async_setup(entry.entry_id)


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "syr_connect.coordinator.SyrConnectAPI"
    ) as mock_api_class:
        # Mock successful setup
        mock_api = MagicMock()
        mock_api.login = AsyncMock(return_value=True)
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "p1", "name": "Project 1"}]
        mock_api.get_devices = AsyncMock(return_value=[
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "p1",
                "dclg": "dclg1",
            }
        ])
        mock_api.get_device_status = AsyncMock(return_value={
            "getPRS": "50",
        })
        mock_api_class.return_value = mock_api

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED

        # Now unload
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.NOT_LOADED
        assert DOMAIN not in hass.data


async def test_reload_entry(hass: HomeAssistant) -> None:
    """Test reload of entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
        options={"scan_interval": 60},
    )
    entry.add_to_hass(hass)

    with patch(
        "syr_connect.coordinator.SyrConnectAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.login = AsyncMock(return_value=True)
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "p1", "name": "Project 1"}]
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.get_device_status = AsyncMock(return_value={})
        mock_api_class.return_value = mock_api

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Trigger reload via options update
        hass.config_entries.async_update_entry(entry, options={"scan_interval": 120})
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED
