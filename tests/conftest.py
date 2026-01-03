"""Fixtures for SYR Connect tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

pytest_plugins = "pytest_homeassistant_custom_component"


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


class MockConfigEntry(ConfigEntry):
    """Mock ConfigEntry for testing."""

    def __init__(
        self,
        *,
        domain: str,
        data: dict,
        unique_id: str | None = None,
        options: dict | None = None,
    ) -> None:
        """Initialize mock config entry."""
        super().__init__(
            version=1,
            minor_version=1,
            domain=domain,
            title="",
            data=data,
            source=config_entries.SOURCE_USER,
            options=options or {},
            unique_id=unique_id,
        )
