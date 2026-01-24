"""Test the SYR Connect coordinator."""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from syr_connect.coordinator import SyrConnectDataUpdateCoordinator


async def test_coordinator_update_success(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test successful coordinator update."""
    with patch("syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.login = AsyncMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "dclg": "dclg1",
            }
        ])
        mock_api.get_device_status = AsyncMock(return_value={
            "getPRS": "50",
            "getFLO": "10",
        })
        mock_api_class.return_value = mock_api

        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            "test@example.com",
            "password",
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        assert "devices" in coordinator.data
        assert len(coordinator.data["devices"]) == 1
        assert coordinator.data["devices"][0]["id"] == "device1"


async def test_coordinator_update_no_session(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator update without session triggers login."""
    with patch("syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = None  # No session initially
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.login = AsyncMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api._is_session_valid = MagicMock(return_value=False)
        mock_api_class.return_value = mock_api

        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            "test@example.com",
            "password",
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        # Simulate no session
        mock_api.session_data = None
        await coordinator.async_config_entry_first_refresh()

        # Verify login was called
        mock_api.login.assert_called_once()



async def test_coordinator_set_device_value(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test setting device value through coordinator."""
    with patch("syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(return_value=[
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "dclg": "dclg1",
            }
        ])
        mock_api.get_device_status = AsyncMock(return_value={})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api._is_session_valid = MagicMock(return_value=True)
        mock_api_class.return_value = mock_api

        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            "test@example.com",
            "password",
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Set device value
        await coordinator.async_set_device_value("device1", "setSIR", 0)

        # Verify API call
        mock_api.set_device_status.assert_called_once_with("dclg1", "setSIR", 0)
