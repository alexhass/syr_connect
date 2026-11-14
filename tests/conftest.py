"""Fixtures for the SYR Connect tests."""

from collections.abc import AsyncIterator, Callable, Generator
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from homeassistant import config_entries


@pytest.fixture
def setup_in_progress_config_entry() -> Any:
    """Mock ConfigEntry in state SETUP_IN_PROGRESS."""
    entry = MagicMock()
    entry.state = config_entries.ConfigEntryState.SETUP_IN_PROGRESS
    return entry


@pytest.fixture(name="integration_version")
def integration_version_fixture() -> str:
    """Return the version of the integration from its manifest."""
    manifest = (
        Path(__file__).parent.parent
        / "custom_components"
        / "syr_connect"
        / "manifest.json"
    )
    return str(json.loads(manifest.read_text(encoding="utf-8"))["version"])


@pytest.fixture(autouse=True)
def mock_integration_version(integration_version: str) -> Generator[None]:
    """Provide the integration version; most tests do not load the integration."""
    with (
        patch(
            "custom_components.syr_connect.config_flow.get_integration_version",
            return_value=integration_version,
        ),
        patch(
            "custom_components.syr_connect.coordinator.get_integration_version",
            return_value=integration_version,
        ),
        patch(
            "custom_components.syr_connect.diagnostics.get_integration_version",
            return_value=integration_version,
        ),
        patch(
            "custom_components.syr_connect.migrations.get_integration_version",
            return_value=integration_version,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def expected_lingering_timers() -> bool:
    """Temporarily allow lingering timers."""
    return True


@pytest.fixture
def mock_syr_api() -> Generator[Any]:
    """Mock SyrConnectXmlAPI."""
    with patch(
        "custom_components.syr_connect.config_flow.SyrConnectXmlAPI"
    ) as mock_api:
        api_instance = MagicMock()
        api_instance.login = AsyncMock(return_value=True)
        api_instance.session_data = "test_session_id"
        api_instance.projects = [{"id": "project1", "name": "Test Project"}]
        api_instance.get_devices = AsyncMock(return_value=[])
        api_instance.get_device_status = AsyncMock(return_value={})
        api_instance.is_session_valid = MagicMock(return_value=True)
        mock_api.return_value = api_instance
        yield api_instance


@pytest.fixture
def create_mock_coordinator() -> Any:
    """Create a mock coordinator with given data."""

    def _create(data: dict | None = None) -> MagicMock:
        mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
        mock_coordinator.data = data
        mock_coordinator.api = MagicMock()  # not SyrConnectJsonAPI → XML API by default
        # No owning config entry by default; unique_id falls back to the
        # legacy "device_id_key" format (see helpers.build_unique_id).
        mock_coordinator.entry_id = None
        return mock_coordinator

    return _create


@pytest.fixture
def create_mock_entry_with_coordinator(
    create_mock_coordinator: Callable[..., MagicMock],
) -> Any:
    """Create a mock config entry with coordinator."""

    def _create(data: dict | None = None) -> tuple[MockConfigEntry, MagicMock]:
        mock_config_entry = MockConfigEntry()
        mock_coordinator = create_mock_coordinator(data)
        mock_config_entry.runtime_data = mock_coordinator
        return mock_config_entry, mock_coordinator

    return _create


@pytest.fixture
def mock_add_entities() -> Any:
    """Create a mock add_entities function that captures entities."""

    def _create() -> tuple[list, Mock]:
        entities = []
        async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))
        return entities, async_add_entities

    return _create


@pytest.fixture
def set_response_body() -> Callable[..., None]:
    """Return a function that gives a fake HTTP response a body read like the one of aiohttp.

    Usage: set_response_body(response, body, chunk_size=None). Text is sent as UTF-8;
    chunk_size is the size of the chunks the body arrives in, None sends it at once.
    """

    def _set_response_body(
        response: MagicMock, body: str | bytes, *, chunk_size: int | None = None
    ) -> None:
        raw = body.encode() if isinstance(body, str) else body
        size = chunk_size or len(raw) or 1

        async def _iter_chunked(_size: int) -> AsyncIterator[bytes]:
            for start in range(0, len(raw), size):
                yield raw[start : start + size]

        response.content = MagicMock()
        response.content.iter_chunked = _iter_chunked
        response.content_length = None
        response.charset = None

    return _set_response_body
