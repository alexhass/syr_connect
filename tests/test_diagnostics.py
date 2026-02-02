"""Tests for diagnostics platform."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.syr_connect.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics(hass: HomeAssistant, mock_config_entry, mock_coordinator) -> None:
    """Test diagnostics data."""
    mock_config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    
    assert "coordinator_data" in diagnostics
    assert "devices" in diagnostics["coordinator_data"]
    assert len(diagnostics["coordinator_data"]["devices"]) == 1
    
    device_data = diagnostics["coordinator_data"]["devices"][0]
    assert device_data["id"] == "1"
    assert device_data["serial"] == "SYR12345"
    assert device_data["name"] == "LEXplus10 S/SL"


async def test_diagnostics_multiple_devices(hass: HomeAssistant, mock_config_entry) -> None:
    """Test diagnostics with multiple devices."""
    from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "1",
                "serial": "SYR12345",
                "name": "LEXplus10 S/SL",
                "sensors": {},
            },
            {
                "id": "2",
                "serial": "SYR67890",
                "name": "LEXplus20",
                "sensors": {},
            },
        ]
    }
    
    mock_config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    
    assert len(diagnostics["coordinator_data"]["devices"]) == 2
    assert diagnostics["coordinator_data"]["devices"][0]["serial"] == "SYR12345"
    assert diagnostics["coordinator_data"]["devices"][1]["serial"] == "SYR67890"
