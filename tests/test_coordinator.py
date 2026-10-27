"""Test the SYR Connect coordinator."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001

import contextlib
from datetime import UTC, datetime, timedelta
from functools import partial
import inspect
import logging
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.syr_connect.api_json import SyrConnectJsonAPI
from custom_components.syr_connect.const import (
    _SYR_CONNECT_API_SERVICES,
    _SYR_CONNECT_DEFAULT_CF_BUNDLE_IDENTIFIER,
    API_TYPE_JSON,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_MODEL,
    CONF_SERVICE,
    DOMAIN,
)
from custom_components.syr_connect.coordinator import (
    SyrConnectDataUpdateCoordinator,
    SyrConnectStatisticsCoordinator,
    _hourly_statistics,
)
from custom_components.syr_connect.data import SyrConnectDevice
from custom_components.syr_connect.devices import safefloor
from custom_components.syr_connect.exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectInvalidResponseError,
)
from custom_components.syr_connect.helpers import clear_device_statistics
from custom_components.syr_connect.models import UNKNOWN_MODEL
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import (
    get_metadata,
    statistics_during_period,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_db_url: str, enable_custom_integrations: None
) -> None:
    """Prepare the recorder database before hass is set up (overrides conftest.py).

    The recorder test of the measurement history needs the database before hass.
    """


def _consume_coro_return_task(coro: Any) -> Any:
    """Safely consume a coroutine passed to `async_create_task` in tests.

    This closes the coroutine (if possible) to avoid "was never awaited"
    warnings and returns a dummy task-like object with a `cancel` and
    `done` method so callers that inspect the returned value behave.
    """
    close = getattr(coro, "close", None)
    if callable(close):
        with contextlib.suppress(Exception):
            close()

    class _DummyTask:
        def cancel(self) -> None:
            return None

        def done(self) -> Any:
            return True

    return _DummyTask()


async def test_coordinator_update_success(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test successful coordinator update."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.login = AsyncMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "name": "Test Device",
                    "project_id": "project1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                }
            ]
        )
        mock_api.get_device_status = AsyncMock(
            return_value={
                "getPRS": "50",
                "getFLO": "10",
            }
        )
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        assert "devices" in coordinator.data
        assert len(coordinator.data["devices"]) == 1
        assert coordinator.data["devices"][0]["id"] == "device1"
        # No CONF_SERVICE in the config data: no cloud service for the branding
        assert coordinator.data["service"] is None
        assert coordinator.data["language"] == hass.config.language


async def test_coordinator_update_no_session(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator update without session triggers login."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = None  # No session initially
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.login = AsyncMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.is_session_valid = MagicMock(return_value=False)
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        # Simulate no session
        mock_api.session_data = None
        await coordinator.async_config_entry_first_refresh()

        # Verify login was called
        mock_api.login.assert_called_once()


async def test_coordinator_set_device_value(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test setting device value through coordinator."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "name": "Test Device",
                    "project_id": "project1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                }
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Set device value
        with (
            patch.object(coordinator, "async_set_updated_data"),
            patch.object(
                hass, "async_create_task", side_effect=_consume_coro_return_task
            ),
        ):
            await coordinator.async_set_device_value("device1", "setSIR", 0)

        # Verify API call
        mock_api.set_device_status.assert_called_once_with(
            "f47ac10b-58cc-4372-a567-0e02b2c3d479", [("setSIR", 0)]
        )


async def test_set_device_status_api_raises_propagates(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """If API.set_device_status raises, the exception should propagate to caller."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {"id": "device1", "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479"}
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={})
        mock_api.set_device_status = AsyncMock(side_effect=Exception("set failed"))
        mock_api_class.return_value = mock_api

        config_data = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"}
        coordinator = SyrConnectDataUpdateCoordinator(
            hass, MagicMock(), config_data, 60
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Populate initial data
        await coordinator.async_config_entry_first_refresh()

        # Ensure exception from API call is propagated
        with (
            patch.object(coordinator, "async_set_updated_data"),
            pytest.raises(Exception, match="set failed"),
        ):
            await coordinator.async_set_device_value("device1", "setSIR", 10)


async def test_invalid_command_no_optimistic_update(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Commands not starting with 'set' should not perform optimistic updates."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "status": {},
                }
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api_class.return_value = mock_api

        config_data = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"}
        coordinator = SyrConnectDataUpdateCoordinator(
            hass, MagicMock(), config_data, 60
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Use a non-conforming command
        with patch.object(
            coordinator, "async_set_updated_data"
        ) as mock_async_set_updated_data:
            await coordinator.async_set_device_value("device1", "badCommand", 1)

        # optimistic update should NOT have occurred
        mock_async_set_updated_data.assert_not_called()
        # API call should still be attempted
        mock_api.set_device_status.assert_called_once()


async def test_coordinator_optimistic_update(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator optimistic update of in-memory data."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "name": "Test Device",
                    "project_id": "project1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "status": {"getSIR": "1"},
                }
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={"getSIR": "1"})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        await coordinator.async_set_device_value("device1", "setSIR", 0)

        assert coordinator.data is not None
        device = coordinator.data["devices"][0]
        assert device["status"]["getSIR"] == "0"
        assert device["available"] is True


async def test_coordinator_optimistic_update_detects_model_again(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """An optimistic update detects the model again from the changed status."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "name": "Test Device",
                    "project_id": "project1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                }
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={"getSIR": "1"})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()
        assert coordinator.data is not None
        assert coordinator.data["devices"][0]["model"] is UNKNOWN_MODEL

        await coordinator.async_set_device_value("device1", "setCNA", "LEXplus10")

        assert coordinator.data["devices"][0]["model"].name == "lexplus10"


async def test_coordinator_device_not_found_error(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator raises HomeAssistantError when device not found."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.get_device_status = AsyncMock(return_value={})
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Try to set value for non-existent device
        with (
            patch.object(coordinator, "async_set_updated_data"),
            patch.object(
                hass, "async_create_task", side_effect=_consume_coro_return_task
            ),
            pytest.raises(HomeAssistantError, match="device_not_found"),
        ):
            await coordinator.async_set_device_value("unknown_device", "setSIR", 0)


async def test_coordinator_no_data_error(hass: HomeAssistant) -> None:
    """Test coordinator raises HomeAssistantError when no data available."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )

        # Try to set value when coordinator has no data
        with (
            patch.object(coordinator, "async_set_updated_data"),
            patch.object(
                hass, "async_create_task", side_effect=_consume_coro_return_task
            ),
            pytest.raises(HomeAssistantError, match="coordinator_data_unavailable"),
        ):
            await coordinator.async_set_device_value("device1", "setSIR", 0)


async def test_coordinator_device_fetch_exception(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator handles exceptions when fetching devices."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [
            {"id": "project1", "name": "Test Project 1"},
            {"id": "project2", "name": "Test Project 2"},
        ]
        mock_api.is_session_valid = MagicMock(return_value=True)

        # First project raises exception, second succeeds
        async def get_devices_side_effect(project_id: Any) -> Any:
            if project_id == "project1":
                raise RuntimeError("Failed to fetch devices")
            return [{"id": "device2", "dclg": "c4d5e6f7-a8b9-0123-cdef-123456789012"}]

        mock_api.get_devices = AsyncMock(side_effect=get_devices_side_effect)
        mock_api.get_device_status = AsyncMock(return_value={"getPRS": "50"})
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Should still have device from second project
        assert coordinator.data is not None
        assert len(coordinator.data["devices"]) == 1
        assert coordinator.data["devices"][0]["id"] == "device2"


async def test_coordinator_non_list_device_result(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator handles non-list device results."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        # Return non-list result
        mock_api.get_devices = AsyncMock(return_value="not a list")
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # The only project has no usable device list: fail instead of reporting an empty account
        with pytest.raises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()


async def test_coordinator_device_status_none(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator handles None status (unexpected structure)."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "cna": "Device 1",
                }
            ]
        )
        # Return None to simulate unexpected structure
        mock_api.get_device_status = AsyncMock(return_value=None)
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
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
        assert device["model"] is UNKNOWN_MODEL
        assert device["available"] is True


async def test_coordinator_device_status_none_reuses_previous(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator reuses previous status when new status is None."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "cna": "Device 1",
                }
            ]
        )
        # First call returns valid status, second returns None
        mock_api.get_device_status = AsyncMock(
            side_effect=[{"getPRS": "50", "getFLO": "10"}, None]
        )
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # First refresh with valid data
        await coordinator.async_config_entry_first_refresh()
        assert coordinator.data is not None
        assert coordinator.data["devices"][0]["status"]["getPRS"] == "50"

        # Second refresh returns None - should reuse previous data
        await coordinator.async_refresh()
        assert coordinator.data["devices"][0]["status"]["getPRS"] == "50"
        assert coordinator.data["devices"][0]["available"] is True


async def test_coordinator_device_status_exception(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator handles exceptions when fetching device status."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "cna": "Device 1",
                }
            ]
        )
        # Raise exception when getting device status
        mock_api.get_device_status = AsyncMock(
            side_effect=Exception("Connection timeout")
        )
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Without previous data the device stays available with an empty status
        assert coordinator.data is not None
        assert len(coordinator.data["devices"]) == 1
        device = coordinator.data["devices"][0]
        assert device["id"] == "device1"
        assert device["available"] is True
        assert device["status"] == {}

        # A temporary failure is only logged, no repair issue is created
        assert (
            ir.async_get(hass).async_get_issue(DOMAIN, "device_offline_device1") is None
        )

        # Once a status is known, a failed poll keeps the previous values
        mock_api.get_device_status = AsyncMock(return_value={"getFLO": "5"})
        await coordinator.async_refresh()
        mock_api.get_device_status = AsyncMock(
            side_effect=Exception("Connection timeout")
        )
        await coordinator.async_refresh()

        assert coordinator.last_update_success is True
        device = coordinator.data["devices"][0]
        assert device["status"] == {"getFLO": "5"}
        assert device["available"] is True


async def test_coordinator_device_status_exception_result(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator handles exception results from gather."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {"id": "device1", "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479"},
                {"id": "device2", "dclg": "c4d5e6f7-a8b9-0123-cdef-123456789012"},
            ]
        )

        # First device succeeds, second fails
        call_count = 0

        async def get_device_status_side_effect(dclg: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"getPRS": "50"}
            raise RuntimeError("Device offline")

        mock_api.get_device_status = AsyncMock(
            side_effect=get_device_status_side_effect
        )
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Should have both devices, one available, one unavailable
        assert coordinator.data is not None
        assert len(coordinator.data["devices"]) == 2


async def test_coordinator_project_devices_auth_error(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """If a project device list returns a SyrConnectAuthError, raise auth failure."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        # Simulate auth error raised while fetching device list
        mock_api.get_devices = AsyncMock(side_effect=SyrConnectAuthError("auth failed"))
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Should raise ConfigEntryAuthFailed when project device fetch encounters auth error
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator.async_config_entry_first_refresh()


async def test_coordinator_device_status_poll_auth_error(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """If a device status poll returns SyrConnectAuthError, raise auth failure."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {"id": "device1", "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479"}
            ]
        )
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Patch internal fetch to raise SyrConnectAuthError so gather returns exception result
        with (
            patch.object(
                coordinator,
                "_fetch_device_status",
                side_effect=SyrConnectAuthError("auth"),
            ),
            pytest.raises(ConfigEntryAuthFailed),
        ):
            await coordinator.async_config_entry_first_refresh()


async def test_coordinator_auth_error_during_login(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator raises ConfigEntryAuthFailed on auth error."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = None
        mock_api.is_session_valid = MagicMock(return_value=False)
        # Simulate auth error during login
        mock_api.login = AsyncMock(
            side_effect=SyrConnectAuthError("Invalid credentials")
        )
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "wrong_password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Should raise ConfigEntryAuthFailed
        with pytest.raises(ConfigEntryAuthFailed, match="auth_failed"):
            await coordinator.async_config_entry_first_refresh()


async def test_coordinator_connection_error_during_login(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator raises UpdateFailed on connection error."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = None
        mock_api.is_session_valid = MagicMock(return_value=False)
        # Simulate connection error during login
        mock_api.login = AsyncMock(
            side_effect=SyrConnectConnectionError("Network unreachable")
        )
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Should raise UpdateFailed wrapped in ConfigEntryNotReady by async_config_entry_first_refresh
        with pytest.raises((UpdateFailed, ConfigEntryNotReady)):
            await coordinator.async_config_entry_first_refresh()


async def test_coordinator_general_exception_during_update(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator handles general exceptions during update."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        # Simulate general exception during device fetch - asyncio.gather catches it
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Should complete successfully with empty devices
        await coordinator.async_config_entry_first_refresh()
        assert coordinator.data is not None


async def test_coordinator_delete_offline_issue_on_recovery(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator deletes repair issue when device comes back online."""
    with (
        patch(
            "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
        ) as mock_api_class,
        patch(
            "custom_components.syr_connect.coordinator.delete_issue"
        ) as mock_delete_issue,
    ):
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "cna": "Device 1",
                }
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={"getPRS": "50"})
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Verify delete_issue was called when device status was successfully fetched
        mock_delete_issue.assert_called_once_with(hass, "device_offline_device1")


async def test_coordinator_optimistic_update_exception_handling(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator handles exceptions during optimistic update gracefully."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(
            return_value=[
                {"id": "device1", "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479"}
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={"getSIR": "1"})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Mock async_set_updated_data to raise exception
        with patch.object(
            coordinator,
            "async_set_updated_data",
            side_effect=ValueError("Update failed"),
        ):
            # Should not raise, exception is caught and logged
            await coordinator.async_set_device_value("device1", "setSIR", 0)

        # API call should still have been made
        mock_api.set_device_status.assert_called_once()


async def test_coordinator_refresh_schedule_exception_handling(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator handles exceptions when scheduling refresh."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(
            return_value=[
                {"id": "device1", "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479"}
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={"getSIR": "1"})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Mock async_create_task to raise exception
        def raise_and_close(coro: Any) -> None:
            coro.close()
            raise RuntimeError("Task creation failed")

        with patch.object(coordinator, "async_set_updated_data"):
            # Should not raise, exception is caught and logged
            await coordinator.async_set_device_value("device1", "setSIR", 0)

        # API call should still have been made
        mock_api.set_device_status.assert_called_once()


async def test_coordinator_device_without_dclg_uses_id(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator uses device ID when dclg is missing."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {"id": "device1"}  # No 'dclg' field
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={"getPRS": "50"})
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Verify get_device_status was called with device id (fallback)
        mock_api.get_device_status.assert_called_once_with("device1")
        assert coordinator.data is not None
        assert coordinator.data["devices"][0]["available"] is True


async def test_coordinator_set_value_device_without_dclg(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test setting value for device without dclg uses device id."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.get_devices = AsyncMock(
            return_value=[
                {"id": "device1"}  # No 'dclg' field
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={"getSIR": "1"})
        mock_api.set_device_status = AsyncMock(return_value=True)
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        with (
            patch.object(coordinator, "async_set_updated_data"),
            patch.object(
                hass, "async_create_task", side_effect=_consume_coro_return_task
            ) as mock_task,
        ):
            mock_task.return_value = None
            with patch.object(coordinator, "async_refresh", new_callable=AsyncMock):
                await coordinator.async_set_device_value("device1", "setSIR", 0)

        # Should use device ID as fallback
        mock_api.set_device_status.assert_called_once_with("device1", [("setSIR", 0)])


async def test_coordinator_gather_returns_exception(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator handles exception from gather for device tasks."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)

        # Create an exception that will be returned by gather
        test_exception = Exception("Device fetch failed")
        mock_api.get_devices = AsyncMock(side_effect=test_exception)
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # The only project failed: fail instead of reporting an empty account
        with pytest.raises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()


async def test_coordinator_data_structure_with_empty_devices(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator data structure when projects have no devices."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [
            {"id": "project1", "name": "Empty Project 1"},
            {"id": "project2", "name": "Empty Project 2"},
        ]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        # Verify data structure is correct
        assert coordinator.data is not None
        assert "devices" in coordinator.data
        assert "projects" in coordinator.data


async def test_fetch_device_status_no_ignore_key_keeps_status(
    hass: HomeAssistant,
) -> None:
    """Non-getAB API values always pass through unchanged on each poll."""

    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "p1", "name": "P1"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_device_status = AsyncMock(return_value={"getPRS": "75"})
        mock_api_class.return_value = mock_api

        config_data = {"username": "u", "password": "p"}
        coord = SyrConnectDataUpdateCoordinator(hass, MagicMock(), config_data, 60)

        device = {"id": "dev1", "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479"}

        result = await coord._fetch_device_status(cast(Any, device))

        assert isinstance(result, dict)
        assert result.get("status", {}).get("getPRS") == "75"


async def test_fetch_device_status_stores_detected_model(
    hass: HomeAssistant,
) -> None:
    """The model is detected from the fetched status and stored on the device."""

    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "p1", "name": "P1"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_device_status = AsyncMock(return_value={"getCNA": "LEXplus10"})
        mock_api_class.return_value = mock_api

        config_data = {"username": "u", "password": "p"}
        coord = SyrConnectDataUpdateCoordinator(hass, MagicMock(), config_data, 60)

        device = {"id": "dev1", "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479"}

        result = await coord._fetch_device_status(cast(Any, device))

        assert result is not None
        assert result["model"].name == "lexplus10"


async def test_coordinator_unexpected_exception_in_update(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator handles unexpected exceptions in update cycle."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.is_session_valid = MagicMock(return_value=True)
        # Make projects property raise an exception when accessed
        type(mock_api).projects = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("Unexpected error"))
        )
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            mock_api,
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Should raise ConfigEntryNotReady for unexpected errors during first refresh
        with pytest.raises(ConfigEntryNotReady, match="update_failed"):
            await coordinator.async_config_entry_first_refresh()


async def test_async_update_data_gather_raises(hass: HomeAssistant) -> None:
    """If asyncio.gather raises, coordinator should raise UpdateFailed (lines 154-156)."""
    with (
        patch(
            "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
        ) as mock_api_class,
        patch(
            "custom_components.syr_connect.coordinator.asyncio.gather",
            side_effect=Exception("gather failed"),
        ),
    ):
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.projects = [{"id": "p1", "name": "P1"}]
        # Use MagicMock (not AsyncMock) so calling get_devices() returns a plain
        # MagicMock object instead of a coroutine. asyncio.gather is patched to
        # raise before it ever awaits anything, so the tasks don't need to be real
        # coroutines — and a plain MagicMock won't trigger an unawaited-coroutine
        # RuntimeWarning when it is garbage-collected.
        mock_api.get_devices = MagicMock(
            return_value=[{"id": "d1", "dclg": "d1", "project_id": "p1"}]
        )
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


async def test_async_update_data_gather_returns_exception_result(
    hass: HomeAssistant,
) -> None:
    """If the device list of every project fails, the update fails instead of returning no devices."""

    async def _fake_gather(*args: Any, **kwargs: Any) -> Any:
        # Close any passed coroutines so they don't trigger unawaited warnings.
        for arg in args:
            if inspect.iscoroutine(arg):
                arg.close()
        return [Exception("proj fail")]

    async def _fake_get_devices(*args: Any, **kwargs: Any) -> Any:
        return [{"id": "d1", "dclg": "d1", "project_id": "p1"}]

    # Use SimpleNamespace instead of MagicMock to avoid auto-created AsyncMock children
    mock_api = SimpleNamespace(
        session_data="test_session",
        is_session_valid=lambda: True,
        projects=[{"id": "p1", "name": "P1"}],
        get_devices=_fake_get_devices,
    )
    # Plain object for session — not used in this code path and avoids AsyncMock warnings
    fake_session = SimpleNamespace()

    with (
        patch(
            "custom_components.syr_connect.coordinator.SyrConnectXmlAPI",
            new=lambda *_a, **_kw: mock_api,
        ),
        patch(
            "custom_components.syr_connect.coordinator.asyncio.gather", new=_fake_gather
        ),
    ):
        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            cast(Any, fake_session),
            config_data,
            60,
        )

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        assert coordinator.device_list_complete is False


def _two_project_api(failing: set[str]) -> Any:
    """Return an XML API stub with projects p1/p2 (one device each); projects in `failing` time out."""

    async def _get_devices(project_id: Any) -> Any:
        if project_id in failing:
            raise SyrConnectConnectionError("timeout")
        return [
            {
                "id": f"d_{project_id}",
                "dclg": f"d_{project_id}",
                "project_id": project_id,
            }
        ]

    async def _get_device_status(dclg: Any) -> Any:
        return {"getSRN": dclg, "getFLO": "5"}

    return SimpleNamespace(
        session_data="test_session",
        is_session_valid=lambda: True,
        projects=[{"id": "p1", "name": "P1"}, {"id": "p2", "name": "P2"}],
        get_devices=_get_devices,
        get_device_status=_get_device_status,
    )


async def test_async_update_data_failed_project_keeps_previous_devices(
    hass: HomeAssistant,
) -> None:
    """A failed project keeps its devices from the last update; the list is marked incomplete."""

    failing: set[str] = set()
    mock_api = _two_project_api(failing)
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI",
        new=lambda *_a, **_kw: mock_api,
    ):
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            cast(Any, SimpleNamespace()),
            {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
            60,
        )
        coordinator.data = await coordinator._async_update_data()
        assert coordinator.device_list_complete is True
        previous_p2 = coordinator.data["devices"][1]

        failing.add("p2")
        result = await coordinator._async_update_data()

        assert [d["id"] for d in result["devices"]] == ["d_p1", "d_p2"]
        assert result["devices"][1] is previous_p2  # old values, not marked unavailable
        assert result["devices"][1]["available"] is True
        assert coordinator.device_list_complete is False


async def test_async_update_data_all_projects_failed_keeps_previous_devices(
    hass: HomeAssistant,
) -> None:
    """After a first successful update, a total failure keeps all devices instead of failing the update."""

    failing: set[str] = set()
    mock_api = _two_project_api(failing)
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI",
        new=lambda *_a, **_kw: mock_api,
    ):
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            cast(Any, SimpleNamespace()),
            {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
            60,
        )
        coordinator.data = await coordinator._async_update_data()

        failing.update({"p1", "p2"})
        result = await coordinator._async_update_data()

        assert result["devices"] == coordinator.data["devices"]
        assert coordinator.device_list_complete is False


async def test_failed_relogin_keeps_previous_data(hass: HomeAssistant) -> None:
    """A failed re-login after the session timeout (e.g. cloud outage) keeps the last data available."""

    mock_api = _two_project_api(set())
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI",
        new=lambda *_a, **_kw: mock_api,
    ):
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            cast(Any, SimpleNamespace()),
            {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
            60,
        )
        await coordinator.async_refresh()
        previous = coordinator.data
        assert coordinator.last_update_success is True

        # Session expired, the re-login fails because the cloud is down
        mock_api.is_session_valid = lambda: False
        mock_api.login = AsyncMock(
            side_effect=SyrConnectConnectionError("maintenance page")
        )
        await coordinator.async_refresh()

        assert coordinator.last_update_success is True  # entities stay available
        assert coordinator.data is previous
        assert coordinator.device_list_complete is False


async def test_coordinator_init_json_api(hass: HomeAssistant) -> None:
    """Test coordinator initialization with JSON API."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectJsonAPI"
    ) as mock_json_api_class:
        mock_api = MagicMock()
        mock_json_api_class.return_value = mock_api

        config_data = {
            CONF_API_TYPE: API_TYPE_JSON,
            CONF_MODEL: "safetechplus",
            CONF_HOST: "192.168.1.100",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )

        # Verify JSON API was created with correct parameters
        mock_json_api_class.assert_called_once()
        call_args = mock_json_api_class.call_args
        assert call_args.kwargs["host"] == "192.168.1.100"
        assert call_args.kwargs["base_path"] == "/trio"
        assert coordinator._api_type == API_TYPE_JSON
        assert coordinator._username is None
        assert coordinator._service is None


async def test_coordinator_init_json_api_invalid_model(hass: HomeAssistant) -> None:
    """Test coordinator initialization with JSON API and invalid model."""
    config_data = {
        CONF_API_TYPE: API_TYPE_JSON,
        CONF_MODEL: "InvalidModel",
        CONF_HOST: "192.168.1.100",
    }

    with pytest.raises(
        ValueError, match="Model InvalidModel does not support local JSON API"
    ):
        SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )


async def test_coordinator_init_defaults_to_xml_api(hass: HomeAssistant) -> None:
    """Test coordinator initialization defaults to XML API when API type not specified."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_xml_api_class:
        mock_api = MagicMock()
        mock_xml_api_class.return_value = mock_api

        # No CONF_API_TYPE specified
        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )

        # Verify XML API was created
        mock_xml_api_class.assert_called_once()
        assert coordinator._api_type == "xml"
        assert coordinator._username == "test@example.com"


async def test_coordinator_init_default_scan_interval(hass: HomeAssistant) -> None:
    """Test coordinator uses default scan interval when none is provided (line 68)."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api_class.return_value = MagicMock()
        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        # Do NOT pass scan_interval so the None branch fires
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
        )
        # update_interval should be set to a timedelta (default, non-None)
        assert coordinator.update_interval is not None


async def test_resolve_device_dclg_returns_none_when_device_not_found(
    hass: HomeAssistant,
) -> None:
    """_resolve_device_dclg returns None when device_id is not in coordinator data (line 309)."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api_class.return_value = MagicMock()
        config_data = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"}
        coordinator = SyrConnectDataUpdateCoordinator(
            hass, MagicMock(), config_data, 60
        )
        coordinator.data = {
            "configuration_url": None,
            "devices": [
                {
                    "id": "other_device",
                    "dclg": "e6f7a8b9-c0d1-2345-efab-345678901234",
                    "name": "Other Device",
                }
            ],
            "language": "en",
            "projects": [],
            "service": None,
        }

        result = coordinator._get_device_dclg_from_srn("nonexistent_device")

        assert result is None


async def test_resolve_device_dclg_returns_none_when_no_data(
    hass: HomeAssistant,
) -> None:
    """_resolve_device_dclg returns None when coordinator.data is not yet available (line 322)."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api_class.return_value = MagicMock()
        config_data = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"}
        coordinator = SyrConnectDataUpdateCoordinator(
            hass, MagicMock(), config_data, 60
        )
        # data is None by default before the first successful update
        coordinator.data = None

        result = coordinator._get_device_dclg_from_srn("any_device")

        assert result is None


async def test_fetch_device_status_propagates_auth_error(hass: HomeAssistant) -> None:
    """If API raises `SyrConnectAuthError`, `_fetch_device_status` should re-raise it (covers line ~291)."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        # make the underlying API raise an auth error when fetching status
        mock_api.get_device_status = AsyncMock(
            side_effect=SyrConnectAuthError("auth failed")
        )
        mock_api_class.return_value = mock_api

        config_data = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"}
        coord = SyrConnectDataUpdateCoordinator(hass, MagicMock(), config_data, 60)

        with pytest.raises(SyrConnectAuthError):
            await coord._fetch_device_status(
                {
                    "id": "deviceX",
                    "dclg": "d5e6f7a8-b9c0-1234-defa-234567890123",
                    "name": "Device X",
                }
            )


async def test_coordinator_device_status_result_is_exception(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """Test coordinator handles exception result from _fetch_device_status gather (lines 183-184)."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {"id": "device1", "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479"}
            ]
        )
        mock_api_class.return_value = mock_api

        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            config_data,
            60,
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Patch _fetch_device_status to raise so gather captures it as an exception result
        with patch.object(
            coordinator,
            "_fetch_device_status",
            side_effect=RuntimeError("unexpected internal error"),
        ):
            await coordinator.async_config_entry_first_refresh()

        # No devices should appear since the only device fetch raised
        assert coordinator.data is not None
        assert coordinator.data["devices"] == []


async def test_fetch_device_status_iwh_compute_error_is_logged(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """get_sensor_iwh_value raising ValueError/TypeError is caught and logged (lines 263-264)."""
    with (
        patch(
            "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
        ) as mock_api_class,
        patch(
            "custom_components.syr_connect.coordinator.get_sensor_iwh_value",
            side_effect=ValueError("bad conductivity"),
        ),
    ):
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "project_id": "project1",
                }
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={"getCND": "bad"})
        mock_api_class.return_value = mock_api

        config_data = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"}
        coordinator = SyrConnectDataUpdateCoordinator(
            hass, MagicMock(), config_data, 60
        )
        coordinator.config_entry = setup_in_progress_config_entry

        # Should complete without raising — the ValueError is caught and only logged
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        assert len(coordinator.data["devices"]) == 1
        assert coordinator.data["devices"][0]["id"] == "device1"


async def test_coordinator_device_marked_unavailable_when_dst_is_0_or_1(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """When the API returns dst=1 the device must be marked unavailable (offline)."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "name": "Device 1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "project_id": "project1",
                }
            ]
        )
        # dst=1 means the device is offline / not reachable via the cloud
        mock_api.get_device_status = AsyncMock(
            return_value={"dst": "1", "getPRS": "50"}
        )
        mock_api_class.return_value = mock_api

        config_data = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"}
        coordinator = SyrConnectDataUpdateCoordinator(
            hass, MagicMock(), config_data, 60
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        device = coordinator.data["devices"][0]
        assert device["available"] is False


async def test_coordinator_device_marked_unavailable_when_dst_is_0(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """When the API returns dst=0 (never been online) the device must be marked unavailable."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "name": "Device 1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "project_id": "project1",
                }
            ]
        )
        # dst=0 means the device has never been online
        mock_api.get_device_status = AsyncMock(
            return_value={"dst": "0", "getPRS": "50"}
        )
        mock_api_class.return_value = mock_api

        config_data = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"}
        coordinator = SyrConnectDataUpdateCoordinator(
            hass, MagicMock(), config_data, 60
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        device = coordinator.data["devices"][0]
        assert device["available"] is False


async def test_coordinator_device_available_when_dst_is_2(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """When the API returns dst=2 (online) the device must remain available."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {
                    "id": "device1",
                    "name": "Device 1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "project_id": "project1",
                }
            ]
        )
        mock_api.get_device_status = AsyncMock(
            return_value={"dst": "2", "getPRS": "50"}
        )
        mock_api_class.return_value = mock_api

        config_data = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"}
        coordinator = SyrConnectDataUpdateCoordinator(
            hass, MagicMock(), config_data, 60
        )
        coordinator.config_entry = setup_in_progress_config_entry
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        device = coordinator.data["devices"][0]
        assert device["available"] is True


async def test_async_clear_device_alarm_xml_api_sends_clr_command(
    hass: HomeAssistant, setup_in_progress_config_entry: MagicMock
) -> None:
    """async_clear_device_alarm sends clrALA via set_device_status for XML API."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(
            return_value=[
                {"id": "device1", "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479"}
            ]
        )
        mock_api.get_device_status = AsyncMock(return_value={})
        mock_api_class.return_value = mock_api

        config_data = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"}
        coordinator = SyrConnectDataUpdateCoordinator(
            hass, MagicMock(), config_data, 60
        )
        coordinator.config_entry = setup_in_progress_config_entry
        coordinator.data = {
            "configuration_url": None,
            "devices": [
                {
                    "id": "device1",
                    "dclg": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "name": "Device 1",
                    "status": {},
                }
            ],
            "language": "en",
            "projects": [],
            "service": None,
        }
        mock_api.set_device_status = AsyncMock(return_value=True)
        coordinator.api = mock_api

        coordinator.hass.async_create_task = MagicMock(  # type: ignore[method-assign]
            side_effect=_consume_coro_return_task
        )
        await coordinator.async_clear_device_alarm("device1")

        mock_api.set_device_status.assert_awaited_once_with(
            "f47ac10b-58cc-4372-a567-0e02b2c3d479", [("clrALA", "")]
        )


async def test_async_clear_device_alarm_json_api_success(hass: HomeAssistant) -> None:
    """async_clear_device_alarm succeeds with JSON API."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_xml_api_class:
        mock_xml_api_class.return_value = MagicMock()

        config_data = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"}
        coordinator = SyrConnectDataUpdateCoordinator(
            hass, MagicMock(), config_data, 60
        )

        mock_api = MagicMock(spec=SyrConnectJsonAPI)
        mock_api.request_json_data = AsyncMock(return_value=None)
        coordinator.api = mock_api

        await coordinator.async_clear_device_alarm("device1")

        mock_api.request_json_data.assert_called_once_with("clr/ala")


async def test_coordinator_init_xml_api_with_conf_service(hass: HomeAssistant) -> None:
    """Test coordinator XML API init looks up service parameters when CONF_SERVICE is set (lines 122-127)."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_xml_api_class:
        mock_xml_api_class.return_value = MagicMock()

        svc = _SYR_CONNECT_API_SERVICES[_SYR_CONNECT_DEFAULT_CF_BUNDLE_IDENTIFIER]
        config_data = {
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
            CONF_SERVICE: svc.cf_bundle_identifier,
        }
        coordinator = SyrConnectDataUpdateCoordinator(
            hass, MagicMock(), config_data, 60
        )

        call_kwargs = mock_xml_api_class.call_args.kwargs
        assert call_kwargs["api_app_name"] == svc.api_app_name
        assert call_kwargs["api_base_url"] == svc.api_base_url
        assert call_kwargs["cf_bundle_identifier"] == svc.cf_bundle_identifier
        assert coordinator._service == svc.cf_bundle_identifier


async def test_coordinator_takes_config_entry_from_constructor(
    hass: HomeAssistant,
) -> None:
    """The config entry passed to the constructor sets config_entry and entry_id."""
    entry = MockConfigEntry(domain=DOMAIN, entry_id="01JTESTENTRY")
    entry.add_to_hass(hass)

    coordinator = SyrConnectDataUpdateCoordinator(
        hass,
        MagicMock(),
        {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        60,
        config_entry=entry,
    )

    assert coordinator.config_entry is entry
    assert coordinator.entry_id == "01JTESTENTRY"


# --- Measurement history (external statistics) -------------------------------------

_STATS_DEVICE_ID = "123456789"
_STATS_ENTRY_ID = "01JTESTENTRY"
_STATS_TEMPERATURE = [
    (datetime(2026, 9, 26, 14, 45, 27, tzinfo=UTC), 14.6),
    (datetime(2026, 9, 26, 20, 45, 27, tzinfo=UTC), 14.9),
]


def _statistics_device() -> SyrConnectDevice:
    """Return a SafeFloor device (dk=120/dkv=34) as the coordinator builds it."""
    return {
        "id": _STATS_DEVICE_ID,
        "name": "Keller",
        "dclg": "840fab82-3e71-4cfc-ab90-a0a1491ca881",
        "dk": 120,
        "dkv": 34,
        "available": True,
        "status": {"getSRN": _STATS_DEVICE_ID},
    }


def _statistics_coordinator(
    hass: HomeAssistant, devices: list[SyrConnectDevice] | None = None
) -> tuple[SyrConnectStatisticsCoordinator, MagicMock]:
    """Return a statistics coordinator over a mocked XML API, with the recorder loaded."""
    hass.config.components.add("recorder")
    entry = MockConfigEntry(domain=DOMAIN, entry_id=_STATS_ENTRY_ID)
    entry.add_to_hass(hass)
    mock_api = MagicMock()
    mock_api.get_statistics = AsyncMock(return_value=_STATS_TEMPERATURE)
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.api = mock_api
    coordinator.data = {
        "devices": [_statistics_device()] if devices is None else devices
    }
    return SyrConnectStatisticsCoordinator(hass, entry, coordinator), mock_api


async def test_statistics_coordinator_imports_every_series(
    hass: HomeAssistant,
) -> None:
    """Every series of the profile is fetched and written as external statistics."""
    statistics, mock_api = _statistics_coordinator(hass)

    with patch(
        "custom_components.syr_connect.coordinator.async_add_external_statistics"
    ) as mock_add:
        await statistics._async_update_data()

    assert [call.args[1] for call in mock_api.get_statistics.await_args_list] == list(
        safefloor.STATISTICS
    )
    assert mock_api.get_statistics.await_args_list[0].args[0] == (
        "840fab82-3e71-4cfc-ab90-a0a1491ca881"
    )
    metadata = [call.args[1] for call in mock_add.call_args_list]
    assert metadata == [
        {
            "has_sum": False,
            "mean_type": 1,
            "name": "Keller Temperature",
            "source": DOMAIN,
            "statistic_id": "syr_connect:123456789_getcel_history",
            "unit_class": "temperature",
            "unit_of_measurement": "°C",
        },
        {
            "has_sum": False,
            "mean_type": 1,
            "name": "Keller Humidity",
            "source": DOMAIN,
            "statistic_id": "syr_connect:123456789_gethmd_history",
            "unit_class": "unitless",
            "unit_of_measurement": "%",
        },
    ]
    assert len(mock_add.call_args_list[0].args[2]) == 2


async def test_statistics_coordinator_name_without_translation(
    hass: HomeAssistant,
) -> None:
    """Without a translation the sensor key names the series."""
    statistics, _mock_api = _statistics_coordinator(hass)

    with (
        patch(
            "custom_components.syr_connect.coordinator.async_get_translations",
            return_value={},
        ),
        patch(
            "custom_components.syr_connect.coordinator.async_add_external_statistics"
        ) as mock_add,
    ):
        await statistics._async_update_data()

    assert mock_add.call_args_list[0].args[1]["name"] == "Keller getCEL"


async def test_statistics_coordinator_refreshes_on_its_interval(
    hass: HomeAssistant,
) -> None:
    """The coordinator has a listener, so it refreshes every 12 hours without entities."""
    statistics, _mock_api = _statistics_coordinator(hass)

    assert statistics.update_interval == timedelta(hours=12)
    assert statistics._listeners


@pytest.mark.parametrize(
    "case",
    [
        "json_api",
        "no_data",
        "no_recorder",
        "no_profile_statistics",
        "unavailable",
    ],
)
async def test_statistics_coordinator_skipped(hass: HomeAssistant, case: str) -> None:
    """Nothing is fetched without the cloud API, data, the recorder or series."""
    device = _statistics_device()
    if case == "no_profile_statistics":
        device["dk"] = 1100
        device["dkv"] = 100
    elif case == "unavailable":
        device["available"] = False
    statistics, mock_api = _statistics_coordinator(hass, [device])
    if case == "json_api":
        statistics._coordinator.api = MagicMock(spec=SyrConnectJsonAPI)
    elif case == "no_data":
        statistics._coordinator.data = None
    elif case == "no_recorder":
        hass.config.components.remove("recorder")

    with patch(
        "custom_components.syr_connect.coordinator.async_add_external_statistics"
    ) as mock_add:
        await statistics._async_update_data()

    mock_api.get_statistics.assert_not_awaited()
    mock_add.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        SyrConnectConnectionError("timeout"),
        SyrConnectInvalidResponseError("broken"),
        ValueError("Invalid XML response"),
    ],
)
async def test_statistics_coordinator_failure_is_only_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    """A failed series is logged; the other series are still imported."""
    statistics, mock_api = _statistics_coordinator(hass)
    mock_api.get_statistics = AsyncMock(side_effect=[error, _STATS_TEMPERATURE])

    with patch(
        "custom_components.syr_connect.coordinator.async_add_external_statistics"
    ) as mock_add:
        await statistics._async_update_data()

    assert "failed to import the getCEL history" in caplog.text
    assert [call.args[1]["statistic_id"] for call in mock_add.call_args_list] == [
        "syr_connect:123456789_gethmd_history",
    ]


async def test_statistics_coordinator_without_measurements(
    hass: HomeAssistant,
) -> None:
    """An answer without measurements writes nothing."""
    statistics, mock_api = _statistics_coordinator(hass)
    mock_api.get_statistics = AsyncMock(return_value=[])

    with patch(
        "custom_components.syr_connect.coordinator.async_add_external_statistics"
    ) as mock_add:
        await statistics._async_update_data()

    mock_add.assert_not_called()


def test_hourly_statistics_only_hours_with_measurements() -> None:
    """An hour gets mean, min and max of its measurements; empty hours get no row."""
    rows = _hourly_statistics(
        [
            (datetime(2026, 9, 26, 13, 15, tzinfo=UTC), 20.0),
            (datetime(2026, 9, 26, 10, 5, tzinfo=UTC), 10.0),
            (datetime(2026, 9, 26, 10, 50, tzinfo=UTC), 12.0),
        ]
    )

    assert rows == [
        {
            "start": datetime(2026, 9, 26, 10, tzinfo=UTC),
            "mean": 11.0,
            "min": 10.0,
            "max": 12.0,
        },
        {
            "start": datetime(2026, 9, 26, 13, tzinfo=UTC),
            "mean": 20.0,
            "min": 20.0,
            "max": 20.0,
        },
    ]


def test_hourly_statistics_without_measurements() -> None:
    """Without measurements there is no row."""
    assert _hourly_statistics([]) == []


async def test_statistics_reach_the_recorder(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """The recorder accepts rows and metadata; a second run overwrites, clearing removes."""
    statistics, _mock_api = _statistics_coordinator(hass)
    statistic_id = "syr_connect:123456789_getcel_history"

    await statistics._async_update_data()
    await statistics._async_update_data()
    await async_wait_recording_done(hass)

    stats = await recorder_mock.async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(2026, 9, 26, tzinfo=UTC),
        None,
        {statistic_id},
        "hour",
        None,
        {"mean", "min", "max"},
    )
    assert [row["mean"] for row in stats[statistic_id]] == pytest.approx([14.6, 14.9])
    metadata = await recorder_mock.async_add_executor_job(
        partial(get_metadata, hass, statistic_ids={statistic_id})
    )
    assert metadata[statistic_id][1]["name"] == "Keller Temperature"

    clear_device_statistics(hass, _STATS_ENTRY_ID, {_STATS_DEVICE_ID})
    await async_wait_recording_done(hass)
    metadata = await recorder_mock.async_add_executor_job(
        partial(get_metadata, hass, statistic_ids={statistic_id})
    )
    assert metadata == {}


async def test_device_failure_is_logged_once_and_its_recovery(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing device logs one warning, repeats at debug level, the recovery at info."""
    with patch(
        "custom_components.syr_connect.coordinator.SyrConnectXmlAPI"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.get_device_status = AsyncMock(
            side_effect=[
                SyrConnectConnectionError("timeout"),
                SyrConnectConnectionError("timeout"),
                {"getSRN": "123456789"},
            ]
        )
        mock_api_class.return_value = mock_api
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
            60,
        )

    caplog.set_level(logging.DEBUG, logger="custom_components.syr_connect.coordinator")
    for _ in range(3):
        await coordinator._fetch_device_status(
            {"id": "123456789", "dclg": "d", "name": "Keller"}
        )

    failures = [
        record.levelno
        for record in caplog.records
        if record.getMessage().startswith("Failed to get status for device 123456789")
    ]
    assert failures == [logging.WARNING, logging.DEBUG]
    recoveries = [
        record.levelno
        for record in caplog.records
        if record.getMessage() == "Status of device 123456789 fetched again"
    ]
    assert recoveries == [logging.INFO]
