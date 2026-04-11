"""Tests for __init__.py integration setup."""
from __future__ import annotations

import logging
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.syr_connect import (
    async_migrate_entry,
    async_options_update_listener,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.syr_connect.const import DOMAIN


async def test_async_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup of config entry."""
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch("custom_components.syr_connect.SyrConnectDataUpdateCoordinator") as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        with patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock) as mock_forward:
            mock_forward.return_value = None
            result = await async_setup_entry(hass, config_entry)

    assert result is True
    assert config_entry.runtime_data == mock_coordinator
    mock_coordinator.async_config_entry_first_refresh.assert_called_once()


async def test_async_setup_entry_json_api_identifier_and_clamp(hass: HomeAssistant) -> None:
    """Test JSON API path uses host identifier and clamps scan interval below minimum."""
    from custom_components.syr_connect.const import API_TYPE_JSON, CONF_API_TYPE, CONF_HOST

    # Create entry with JSON API and very small scan_interval to trigger clamp
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test JSON",
        data={
            CONF_USERNAME: "json@example.com",
            CONF_PASSWORD: "password",
            CONF_API_TYPE: API_TYPE_JSON,
            CONF_HOST: "192.0.2.1",
        },
        source="user",
        entry_id="json_entry_id",
        unique_id=f"{API_TYPE_JSON}_json@example.com",
        options={"scan_interval": 1},
    )
    config_entry.add_to_hass(hass)

    with patch("custom_components.syr_connect.SyrConnectDataUpdateCoordinator") as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        with patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock) as mock_forward:
            mock_forward.return_value = None
            result = await async_setup_entry(hass, config_entry)

    assert result is True
    # Minimum for JSON API is 10 seconds, so scan interval (options=1) should be clamped to 10
    call_args = mock_coordinator_class.call_args
    assert call_args[0][3] == 10


async def test_async_migrate_entry_v1_missing_username(hass: HomeAssistant) -> None:
    """Test v1->v2 migration bumps version even when username is missing."""
    from custom_components.syr_connect.const import API_TYPE_XML, CONF_API_TYPE

    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Legacy Missing Username",
        data={},
        source="user",
        entry_id="legacy_no_user",
        unique_id="legacy_no_user",
    )
    config_entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_update_entry") as mock_update:
        result = await async_migrate_entry(hass, config_entry)

    assert result is True
    call_kwargs = mock_update.call_args[1]
    assert call_kwargs["version"] == 2
    assert call_kwargs["data"][CONF_API_TYPE] == API_TYPE_XML
    # unique_id must NOT be updated when username is missing
    assert "unique_id" not in call_kwargs


async def test_async_migrate_entry_v1_with_username(hass: HomeAssistant) -> None:
    """Test v1->v2 migration adds CONF_API_TYPE and updates unique_id."""
    from custom_components.syr_connect.const import API_TYPE_XML, CONF_API_TYPE

    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Legacy With Username",
        data={CONF_USERNAME: "legacy_user@example.com"},
        source="user",
        entry_id="legacy_with_user",
        unique_id="legacy_with_user",
    )
    config_entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_update_entry") as mock_update:
        result = await async_migrate_entry(hass, config_entry)

    assert result is True
    call_kwargs = mock_update.call_args[1]
    assert call_kwargs["version"] == 2
    assert call_kwargs["data"][CONF_API_TYPE] == API_TYPE_XML
    assert call_kwargs["unique_id"] == f"{API_TYPE_XML}_legacy_user@example.com"


async def test_async_setup_entry_connection_failure(hass: HomeAssistant) -> None:
    """Test setup fails when connection to API fails."""
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

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
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        options={"scan_interval": 120},  # Custom interval
    )
    config_entry.add_to_hass(hass)

    with patch("custom_components.syr_connect.SyrConnectDataUpdateCoordinator") as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        with patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock) as mock_forward:
            mock_forward.return_value = None
            result = await async_setup_entry(hass, config_entry)

    assert result is True
    # Verify coordinator was created with custom scan interval
    mock_coordinator_class.assert_called_once()
    call_args = mock_coordinator_class.call_args
    assert call_args[0][3] == 120  # scan_interval is now 4th positional argument (index 3)


async def test_async_unload_entry_success(hass: HomeAssistant) -> None:
    """Test successful unload of config entry."""
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )

    with patch.object(hass.config_entries, "async_unload_platforms", new_callable=AsyncMock) as mock_unload:
        mock_unload.return_value = True
        result = await async_unload_entry(hass, config_entry)

    assert result is True


async def test_async_unload_entry_failure(hass: HomeAssistant) -> None:
    """Test unload returns False when platforms fail to unload."""
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )

    with patch.object(hass.config_entries, "async_unload_platforms", new_callable=AsyncMock) as mock_unload:
        mock_unload.return_value = False
        result = await async_unload_entry(hass, config_entry)

    assert result is False


async def test_async_options_update_listener_interval_changed(hass: HomeAssistant) -> None:
    """Test options update listener when scan interval changes."""
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        options={"scan_interval": 120},  # New interval
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
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        options={"scan_interval": 60},  # Same as current
    )

    mock_coordinator = MagicMock()
    mock_coordinator.update_interval = timedelta(seconds=60)  # Same interval
    mock_coordinator.async_request_refresh = AsyncMock()
    config_entry.runtime_data = mock_coordinator

    await async_options_update_listener(hass, config_entry)

    # Verify refresh was not called
    mock_coordinator.async_request_refresh.assert_not_called()


async def test_async_setup_entry_clamps_scan_interval_and_logs(hass: HomeAssistant, caplog) -> None:
    """Test JSON API clamps scan interval below minimum and logs a warning."""
    from custom_components.syr_connect.const import API_TYPE_JSON, CONF_API_TYPE, CONF_HOST

    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test JSON Log",
        data={
            CONF_USERNAME: "json@example.com",
            CONF_PASSWORD: "password",
            CONF_API_TYPE: API_TYPE_JSON,
            CONF_HOST: "192.0.2.1",
        },
        source="user",
        entry_id="json_log_entry_id",
        unique_id=f"{API_TYPE_JSON}_json@example.com",
        options={"scan_interval": 1},
    )
    config_entry.add_to_hass(hass)

    with patch("custom_components.syr_connect.SyrConnectDataUpdateCoordinator") as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        caplog.set_level(logging.WARNING)
        with patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock) as mock_forward:
            mock_forward.return_value = None
            result = await async_setup_entry(hass, config_entry)

    assert result is True
    assert "clamping to" in caplog.text or "below minimum" in caplog.text


async def test_async_unload_entry_logs(hass: HomeAssistant, caplog) -> None:
    """Verify unload logs for both success and failure."""
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )

    caplog.set_level(logging.INFO)
    with patch.object(hass.config_entries, "async_unload_platforms", new_callable=AsyncMock) as mock_unload:
        mock_unload.return_value = True
        result = await async_unload_entry(hass, config_entry)

    assert result is True
    assert "unloaded successfully" in caplog.text

    caplog.clear()
    caplog.set_level(logging.WARNING)
    with patch.object(hass.config_entries, "async_unload_platforms", new_callable=AsyncMock) as mock_unload2:
        mock_unload2.return_value = False
        result2 = await async_unload_entry(hass, config_entry)

    assert result2 is False
    assert "Failed to unload" in caplog.text


async def test_async_reload_entry(hass: HomeAssistant) -> None:
    """Test reload entry."""
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )

    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock) as mock_reload:
        await async_reload_entry(hass, config_entry)

        mock_reload.assert_called_once_with("test_entry_id")


    async def test_async_setup_entry_logs_migration(hass: HomeAssistant, caplog) -> None:
        """Ensure legacy migration branch logs a migration message."""

        config_entry = MockConfigEntry(
            version=1,
            minor_version=0,
            domain=DOMAIN,
            title="Test Legacy Log",
            data={"username": "legacylog@example.com", "password": "password"},
            source="user",
            entry_id="legacy_log_entry",
            unique_id="legacylog@example.com",
        )
        config_entry.add_to_hass(hass)

        with patch("custom_components.syr_connect.SyrConnectDataUpdateCoordinator") as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            caplog.set_level(logging.INFO)
            with patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock):
                with patch.object(
                    hass.config_entries,
                    "async_update_entry",
                    new_callable=MagicMock
                ):
                    result = await async_setup_entry(hass, config_entry)

        assert result is True
        assert "Migrating legacy config entry" in caplog.text


    async def test_async_options_update_listener_logs_unchanged(hass: HomeAssistant, caplog) -> None:
        """Ensure options update listener logs when scan interval is unchanged."""
        config_entry = MockConfigEntry(
            version=1,
            minor_version=0,
            domain=DOMAIN,
            title="Test",
            data={"username": "test@example.com", "password": "password"},
            source="user",
            entry_id="test_entry_id",
            unique_id="test_unique_id",
            options={"scan_interval": 60},  # Same as current
        )

        mock_coordinator = MagicMock()
        mock_coordinator.update_interval = timedelta(seconds=60)  # Same interval
        mock_coordinator.async_request_refresh = AsyncMock()
        config_entry.runtime_data = mock_coordinator

        caplog.set_level(logging.DEBUG)
        await async_options_update_listener(hass, config_entry)

        assert "Options updated but scan interval unchanged" in caplog.text


async def test_async_setup_entry_migrates_legacy_entry(hass: HomeAssistant) -> None:
    """Test that legacy config entries without API_TYPE are migrated automatically."""
    from custom_components.syr_connect.const import API_TYPE_XML, CONF_API_TYPE

    # Create a legacy entry without CONF_API_TYPE
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test Legacy",
        data={CONF_USERNAME: "legacy@example.com", CONF_PASSWORD: "password"},
        source="user",
        entry_id="legacy_entry_id",
        unique_id="legacy@example.com",  # Old format without prefix
    )
    config_entry.add_to_hass(hass)

    with patch("custom_components.syr_connect.SyrConnectDataUpdateCoordinator") as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        with patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock):
            with patch.object(
                hass.config_entries,
                "async_update_entry",
                new_callable=MagicMock
            ) as mock_update:
                result = await async_setup_entry(hass, config_entry)

    # Verify setup succeeded
    assert result is True

    # Verify migration was called
    mock_update.assert_called_once()
    call_args = mock_update.call_args

    # Check that data was updated with API_TYPE_XML
    assert CONF_API_TYPE in call_args.kwargs["data"]
    assert call_args.kwargs["data"][CONF_API_TYPE] == API_TYPE_XML

    # Check that unique_id was updated to new format
    assert call_args.kwargs["unique_id"] == f"{API_TYPE_XML}_legacy@example.com"


async def test_async_setup_entry_skips_migration_for_new_entries(hass: HomeAssistant) -> None:
    """Test that new config entries with API_TYPE are not migrated."""
    from custom_components.syr_connect.const import API_TYPE_XML, CONF_API_TYPE

    # Create a new entry with CONF_API_TYPE already set
    config_entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test New",
        data={
            CONF_USERNAME: "new@example.com",
            CONF_PASSWORD: "password",
            CONF_API_TYPE: API_TYPE_XML,
        },
        source="user",
        entry_id="new_entry_id",
        unique_id=f"{API_TYPE_XML}_new@example.com",
    )
    config_entry.add_to_hass(hass)

    with patch("custom_components.syr_connect.SyrConnectDataUpdateCoordinator") as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        with patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock):
            with patch.object(
                hass.config_entries,
                "async_update_entry",
                new_callable=MagicMock
            ) as mock_update:
                result = await async_setup_entry(hass, config_entry)

    # Verify setup succeeded
    assert result is True

    # Verify migration was NOT called (entry already has API_TYPE)
    mock_update.assert_not_called()

