"""Fixtures for SYR Connect tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.syr_connect.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_syr_api():
    """Mock SyrConnectAPI."""
    with patch("custom_components.syr_connect.config_flow.SyrConnectAPI") as mock_api:
        api_instance = MagicMock()
        api_instance.login = AsyncMock(return_value=True)
        api_instance.session_data = "test_session_id"
        api_instance.projects = [
            {"id": "project1", "name": "Test Project"}
        ]
        mock_api.return_value = api_instance
        yield api_instance


@pytest.fixture
def mock_config_entry():
    """Mock ConfigEntry."""
    return {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "test_password",
    }
