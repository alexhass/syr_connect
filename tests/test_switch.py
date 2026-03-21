"""Tests for switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock

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

    # Tests construct a bare ConfigEntry; provide minimal runtime_data
    # so platform setup can access coordinator data without altering product code.
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": []}
    config_entry.runtime_data = mock_coordinator

    mock_add_entities = MagicMock()

    # Should return without adding entities
    await async_setup_entry(hass, config_entry, mock_add_entities)

    mock_add_entities.assert_not_called()


async def test_switch_entity_states_and_actions(hass: HomeAssistant) -> None:
    """Test SyrConnectBuzSwitch behavior: is_on, turn_on, turn_off."""
    from custom_components.syr_connect.switch import SyrConnectBuzSwitch

    device_on = {"id": "SN123", "name": "DeviceOn", "status": {"getBUZ": "1"}, "available": True}
    device_off = {"id": "SN124", "name": "DeviceOff", "status": {"getBUZ": "0"}, "available": True}

    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device_on, device_off]}

    # Async refresh stub
    mock_coordinator.async_request_refresh = AsyncMock()

    sw_on = SyrConnectBuzSwitch(mock_coordinator, "SN123", "DeviceOn", "getBUZ")
    sw_off = SyrConnectBuzSwitch(mock_coordinator, "SN124", "DeviceOff", "getBUZ")

    # Unique id should include platform suffix set in implementation
    assert sw_on._attr_unique_id.endswith("_switch")

    assert sw_on.is_on is True
    assert sw_off.is_on is False

    # Test turn_on/turn_off call API and refresh
    async def fake_set_device_status(dclg, cmd, value):
        # ensure parameters passed through
        assert cmd == "BUZ"

    mock_coordinator.api = MagicMock()
    mock_coordinator.api.set_device_status = AsyncMock(side_effect=fake_set_device_status)
    mock_coordinator.async_request_refresh = AsyncMock()

    # call turn on/off
    await sw_off.async_turn_on()
    mock_coordinator.api.set_device_status.assert_called()
    mock_coordinator.async_request_refresh.assert_called()

    await sw_on.async_turn_off()
    assert mock_coordinator.api.set_device_status.call_count >= 2
