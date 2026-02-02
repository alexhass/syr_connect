"""Tests for diagnostics platform."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics(hass: HomeAssistant) -> None:
    """Test diagnostics data."""
    # Create a proper config entry
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="test",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    # Create mock coordinator
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "1",
                "serial": "SYR12345",
                "name": "LEXplus10 S/SL",
                "sensors": {},
            },
        ]
    }
    mock_coordinator.last_update_success_time = None
    
    # Attach coordinator to config entry
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    assert "entry" in diagnostics
    assert "coordinator_data" in diagnostics


async def test_diagnostics_with_coordinator_data(hass: HomeAssistant) -> None:
    """Test diagnostics includes coordinator data."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="test",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "1",
                "serial": "SYR12345",
                "name": "LEXplus10 S/SL",
                "sensors": {"getWVI": {"value": 100}},
            },
            {
                "id": "2",
                "serial": "SYR67890",
                "name": "LEXplus20",
                "sensors": {"getWVI": {"value": 200}},
            },
        ]
    }
    mock_coordinator.last_update_success_time = None
    
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    assert "coordinator_data" in diagnostics
    assert diagnostics["coordinator_data"] == mock_coordinator.data
