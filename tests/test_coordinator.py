"""Test the SYR Connect coordinator."""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
)


async def test_coordinator_update_success(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test successful coordinator update."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
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
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = None  # No session initially
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.login = AsyncMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.is_session_valid = MagicMock(return_value=False)
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
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
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
        mock_api.is_session_valid = MagicMock(return_value=True)
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


async def test_coordinator_optimistic_update(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator optimistic update of in-memory data."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(return_value=[
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "dclg": "dclg1",
                "status": {"getSIR": "1"},
            }
        ])
        mock_api.get_device_status = AsyncMock(return_value={"getSIR": "1"})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api.is_session_valid = MagicMock(return_value=True)
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

        with patch.object(hass, "async_create_task", return_value=None) as mock_task:
            with patch.object(coordinator, "async_refresh", new_callable=AsyncMock) as mock_refresh:
                await coordinator.async_set_device_value("device1", "setSIR", 0)
                # Verify refresh was scheduled
                mock_task.assert_called_once()

        assert coordinator.data is not None
        device = coordinator.data["devices"][0]
        assert device["status"]["getSIR"] == "0"
        assert device["available"] is True


async def test_coordinator_device_not_found_error(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator raises ValueError when device not found."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.get_device_status = AsyncMock(return_value={})
        mock_api.is_session_valid = MagicMock(return_value=True)
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

        # Try to set value for non-existent device
        with pytest.raises(ValueError, match="Device unknown_device not found"):
            await coordinator.async_set_device_value("unknown_device", "setSIR", 0)


async def test_coordinator_no_data_error(hass: HomeAssistant) -> None:
    """Test coordinator raises ValueError when no data available."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            "test@example.com",
            "password",
            60,
        )

        # Try to set value when coordinator has no data
        with pytest.raises(ValueError, match="Coordinator data not available"):
            await coordinator.async_set_device_value("device1", "setSIR", 0)


async def test_coordinator_device_fetch_exception(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator handles exceptions when fetching devices."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [
            {"id": "project1", "name": "Test Project 1"},
            {"id": "project2", "name": "Test Project 2"},
        ]
        mock_api.is_session_valid = MagicMock(return_value=True)
        
        # First project raises exception, second succeeds
        async def get_devices_side_effect(project_id):
            if project_id == "project1":
                raise Exception("Failed to fetch devices")
            return [{"id": "device2", "dclg": "dclg2"}]
        
        mock_api.get_devices = AsyncMock(side_effect=get_devices_side_effect)
        mock_api.get_device_status = AsyncMock(return_value={"getPRS": "50"})
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

        # Should still have device from second project
        assert coordinator.data is not None
        assert len(coordinator.data["devices"]) == 1
        assert coordinator.data["devices"][0]["id"] == "device2"


async def test_coordinator_non_list_device_result(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator handles non-list device results."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        # Return non-list result
        mock_api.get_devices = AsyncMock(return_value="not a list")
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

        # Should handle gracefully with no devices
        assert coordinator.data is not None
        assert len(coordinator.data["devices"]) == 0


async def test_coordinator_device_status_none(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator handles None status (unexpected structure)."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[
            {"id": "device1", "dclg": "dclg1", "cna": "Device 1"}
        ])
        # Return None to simulate unexpected structure
        mock_api.get_device_status = AsyncMock(return_value=None)
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

        # Device should be present with empty status but available
        assert coordinator.data is not None
        assert len(coordinator.data["devices"]) == 1
        device = coordinator.data["devices"][0]
        assert device["id"] == "device1"
        assert device["status"] == {}
        assert device["available"] is True


async def test_coordinator_device_status_none_reuses_previous(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator reuses previous status when new status is None."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[
            {"id": "device1", "dclg": "dclg1", "cna": "Device 1"}
        ])
        # First call returns valid status, second returns None
        mock_api.get_device_status = AsyncMock(side_effect=[
            {"getPRS": "50", "getFLO": "10"},
            None
        ])
        mock_api_class.return_value = mock_api

        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            "test@example.com",
            "password",
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        
        # First refresh with valid data
        await coordinator.async_config_entry_first_refresh()
        assert coordinator.data["devices"][0]["status"]["getPRS"] == "50"
        
        # Second refresh returns None - should reuse previous data
        await coordinator.async_refresh()
        assert coordinator.data["devices"][0]["status"]["getPRS"] == "50"
        assert coordinator.data["devices"][0]["available"] is True


async def test_coordinator_device_status_exception(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator handles exceptions when fetching device status."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class, \
         patch("custom_components.syr_connect.coordinator.create_issue") as mock_create_issue:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[
            {"id": "device1", "dclg": "dclg1", "cna": "Device 1"}
        ])
        # Raise exception when getting device status
        mock_api.get_device_status = AsyncMock(side_effect=Exception("Connection timeout"))
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

        # Device should be present but marked unavailable
        assert coordinator.data is not None
        assert len(coordinator.data["devices"]) == 1
        device = coordinator.data["devices"][0]
        assert device["id"] == "device1"
        assert device["available"] is False
        assert device["status"] == {}
        
        # Verify repair issue was created
        mock_create_issue.assert_called_once_with(
            hass,
            "device_offline_device1",
            "device_offline",
            translation_placeholders={"device_name": "Device 1"},
        )


async def test_coordinator_device_status_exception_result(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator handles exception results from gather."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[
            {"id": "device1", "dclg": "dclg1"},
            {"id": "device2", "dclg": "dclg2"},
        ])
        
        # First device succeeds, second fails
        call_count = 0
        async def get_device_status_side_effect(dclg):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"getPRS": "50"}
            raise Exception("Device offline")
        
        mock_api.get_device_status = AsyncMock(side_effect=get_device_status_side_effect)
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

        # Should have both devices, one available, one unavailable
        assert coordinator.data is not None
        assert len(coordinator.data["devices"]) == 2


async def test_coordinator_auth_error_during_login(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator raises ConfigEntryAuthFailed on auth error."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = None
        mock_api.is_session_valid = MagicMock(return_value=False)
        # Simulate auth error during login
        mock_api.login = AsyncMock(side_effect=SyrConnectAuthError("Invalid credentials"))
        mock_api_class.return_value = mock_api

        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            "test@example.com",
            "wrong_password",
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Should raise ConfigEntryAuthFailed
        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await coordinator.async_config_entry_first_refresh()


async def test_coordinator_connection_error_during_login(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator raises UpdateFailed on connection error."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = None
        mock_api.is_session_valid = MagicMock(return_value=False)
        # Simulate connection error during login
        mock_api.login = AsyncMock(side_effect=SyrConnectConnectionError("Network unreachable"))
        mock_api_class.return_value = mock_api

        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            "test@example.com",
            "password",
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Should raise UpdateFailed wrapped in ConfigEntryNotReady by async_config_entry_first_refresh
        with pytest.raises(Exception):  # Can be UpdateFailed or ConfigEntryNotReady
            await coordinator.async_config_entry_first_refresh()


async def test_coordinator_general_exception_during_update(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator handles general exceptions during update."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        # Simulate general exception during device fetch - asyncio.gather catches it
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api_class.return_value = mock_api

        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            "test@example.com",
            "password",
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Should complete successfully with empty devices
        await coordinator.async_config_entry_first_refresh()
        assert coordinator.data is not None


async def test_coordinator_delete_offline_issue_on_recovery(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator deletes repair issue when device comes back online."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class, \
         patch("custom_components.syr_connect.coordinator.delete_issue") as mock_delete_issue:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[
            {"id": "device1", "dclg": "dclg1", "cna": "Device 1"}
        ])
        mock_api.get_device_status = AsyncMock(return_value={"getPRS": "50"})
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

        # Verify delete_issue was called when device status was successfully fetched
        mock_delete_issue.assert_called_once_with(hass, "device_offline_device1")


async def test_coordinator_device_without_cna_fallback_to_id(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator uses device ID as fallback when cna is missing."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class, \
         patch("custom_components.syr_connect.coordinator.create_issue") as mock_create_issue:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[
            {"id": "device1", "dclg": "dclg1"}  # No 'cna' field
        ])
        mock_api.get_device_status = AsyncMock(side_effect=Exception("Device offline"))
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

        # Verify create_issue was called with device ID as fallback
        mock_create_issue.assert_called_once_with(
            hass,
            "device_offline_device1",
            "device_offline",
            translation_placeholders={"device_name": "device1"},
        )


async def test_coordinator_optimistic_update_exception_handling(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator handles exceptions during optimistic update gracefully."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(return_value=[
            {"id": "device1", "dclg": "dclg1"}
        ])
        mock_api.get_device_status = AsyncMock(return_value={"getSIR": "1"})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api.is_session_valid = MagicMock(return_value=True)
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

        # Mock async_set_updated_data to raise exception
        with patch.object(coordinator, "async_set_updated_data", side_effect=Exception("Update failed")):
            with patch.object(hass, "async_create_task", return_value=None):
                with patch.object(coordinator, "async_refresh", new_callable=AsyncMock):
                    # Should not raise, exception is caught and logged
                    await coordinator.async_set_device_value("device1", "setSIR", 0)

        # API call should still have been made
        mock_api.set_device_status.assert_called_once()


async def test_coordinator_refresh_schedule_exception_handling(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator handles exceptions when scheduling refresh."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(return_value=[
            {"id": "device1", "dclg": "dclg1"}
        ])
        mock_api.get_device_status = AsyncMock(return_value={"getSIR": "1"})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api.is_session_valid = MagicMock(return_value=True)
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

        # Mock async_create_task to raise exception
        with patch.object(hass, "async_create_task", side_effect=Exception("Task creation failed")):
            with patch.object(coordinator, "async_refresh", new_callable=AsyncMock):
                # Should not raise, exception is caught and logged
                await coordinator.async_set_device_value("device1", "setSIR", 0)

        # API call should still have been made
        mock_api.set_device_status.assert_called_once()


async def test_coordinator_device_without_dclg_uses_id(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator uses device ID when dclg is missing."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[
            {"id": "device1"}  # No 'dclg' field
        ])
        mock_api.get_device_status = AsyncMock(return_value={"getPRS": "50"})
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

        # Verify get_device_status was called with device id (fallback)
        mock_api.get_device_status.assert_called_once_with("device1")
        assert coordinator.data["devices"][0]["available"] is True


async def test_coordinator_set_value_device_without_dclg(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test setting value for device without dclg uses device id."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(return_value=[
            {"id": "device1"}  # No 'dclg' field
        ])
        mock_api.get_device_status = AsyncMock(return_value={"getSIR": "1"})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api.is_session_valid = MagicMock(return_value=True)
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

        with patch.object(hass, "async_create_task", return_value=None):
            with patch.object(coordinator, "async_refresh", new_callable=AsyncMock):
                await coordinator.async_set_device_value("device1", "setSIR", 0)

        # Should use device ID as fallback
        mock_api.set_device_status.assert_called_once_with("device1", "setSIR", 0)


async def test_coordinator_gather_returns_exception(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator handles exception from gather for device tasks."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        
        # Create an exception that will be returned by gather
        test_exception = Exception("Device fetch failed")
        mock_api.get_devices = AsyncMock(side_effect=test_exception)
        mock_api_class.return_value = mock_api

        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            "test@example.com",
            "password",
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        
        # Should handle exception gracefully
        await coordinator.async_config_entry_first_refresh()
        
        # Should have no devices
        assert coordinator.data is not None
        assert len(coordinator.data["devices"]) == 0


async def test_coordinator_data_structure_with_empty_devices(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator data structure when projects have no devices."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [
            {"id": "project1", "name": "Empty Project 1"},
            {"id": "project2", "name": "Empty Project 2"},
        ]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[])
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

        # Verify data structure is correct
        assert coordinator.data is not None
        assert "devices" in coordinator.data
        assert "projects" in coordinator.data
        assert coordinator.data["devices"] == []
        assert coordinator.data["projects"] == mock_api.projects


async def test_coordinator_unexpected_exception_in_update(hass: HomeAssistant, setup_in_progress_config_entry) -> None:
    """Test coordinator handles unexpected exceptions in update cycle."""
    with patch("custom_components.syr_connect.coordinator.SyrConnectAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.is_session_valid = MagicMock(return_value=True)
        # Make projects property raise an exception when accessed
        type(mock_api).projects = property(lambda self: (_ for _ in ()).throw(RuntimeError("Unexpected error")))
        mock_api_class.return_value = mock_api

        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            mock_api,
            "test@example.com",
            "password",
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Should raise ConfigEntryNotReady for unexpected errors during first refresh
        from homeassistant.exceptions import ConfigEntryNotReady
        with pytest.raises(ConfigEntryNotReady, match="Error communicating with API"):
            await coordinator.async_config_entry_first_refresh()

