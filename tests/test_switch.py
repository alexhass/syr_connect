"""Tests for switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.switch import async_setup_entry


async def test_async_setup_entry_no_entities(hass: HomeAssistant) -> None:
    """Test that switch platform does not create any entities."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test", CONF_PASSWORD: "test"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )

    mock_add_entities = MagicMock()

    # Should return without adding entities
    await async_setup_entry(hass, config_entry, mock_add_entities)

    mock_add_entities.assert_not_called()
