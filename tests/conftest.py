
import pytest
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

pytest_plugins = "pytest_homeassistant_custom_component"

@pytest.fixture
def setup_in_progress_config_entry():
    """Mock ConfigEntry im State SETUP_IN_PROGRESS."""
    entry = MagicMock()
    entry.state = config_entries.ConfigEntryState.SETUP_IN_PROGRESS
    return entry


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
        "custom_components.syr_connect.async_setup_entry", new_callable=AsyncMock
    ) as mock_setup_entry:
        mock_setup_entry.return_value = True
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
        api_instance.get_devices = AsyncMock(return_value=[])
        api_instance.get_device_status = AsyncMock(return_value={})
        api_instance.is_session_valid = MagicMock(return_value=True)
        # Prevent accidental async mock creation
        api_instance._is_coroutine = False
        mock_api.return_value = api_instance
        yield api_instance


@pytest.fixture
def mock_config_entry():
    """Mock ConfigEntry."""
    return {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "test_password",
    }


@pytest.fixture
def create_mock_coordinator():
    """Create a mock coordinator with given data."""
    from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
    
    def _create(data: dict | None = None) -> MagicMock:
        mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
        mock_coordinator.data = data
        return mock_coordinator
    
    return _create


@pytest.fixture
def create_mock_entry_with_coordinator(create_mock_coordinator):
    """Create a mock config entry with coordinator."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    def _create(data: dict | None = None) -> tuple[MockConfigEntry, MagicMock]:
        mock_config_entry = MockConfigEntry()
        mock_coordinator = create_mock_coordinator(data)
        mock_config_entry.runtime_data = mock_coordinator
        return mock_config_entry, mock_coordinator
    
    return _create


@pytest.fixture
def mock_add_entities():
    """Create a mock add_entities function that captures entities."""
    def _create() -> tuple[list, Mock]:
        entities = []
        async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
        return entities, async_add_entities
    
    return _create


