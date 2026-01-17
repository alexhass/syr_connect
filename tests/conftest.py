@pytest.fixture
def setup_in_progress_config_entry():
    """Mock ConfigEntry im State SETUP_IN_PROGRESS."""
    entry = MagicMock()
    entry.state = config_entries.ConfigEntryState.SETUP_IN_PROGRESS
    return entry
"""Fixtures for SYR Connect tests."""
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    return enable_custom_integrations


@pytest.fixture(autouse=True)
def expected_lingering_timers() -> bool:
    """Temporarily allow lingering timers."""
    return True


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "syr_connect.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_syr_api():
    """Mock SyrConnectAPI."""
    with patch("syr_connect.config_flow.SyrConnectAPI") as mock_api:
        api_instance = MagicMock()
        api_instance.login = AsyncMock(return_value=True)
        api_instance.session_data = "test_session_id"
        api_instance.projects = [
            {"id": "project1", "name": "Test Project"}
        ]
        api_instance.get_devices = AsyncMock(return_value=[])
        api_instance.get_device_status = AsyncMock(return_value={})
        mock_api.return_value = api_instance
        yield api_instance


@pytest.fixture
def mock_config_entry():
    """Mock ConfigEntry."""
    return {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "test_password",
    }


