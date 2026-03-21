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


def test_is_on_device_missing() -> None:
    """If the device is not present in coordinator data, is_on should be None."""
    from custom_components.syr_connect.switch import SyrConnectBuzSwitch

    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": []}

    sw = SyrConnectBuzSwitch(mock_coordinator, "MISSING", "Missing", "getBUZ")
    assert sw.is_on is None


def test_is_on_with_int_and_float_values() -> None:
    """Ensure numeric getBUZ values are interpreted correctly."""
    from custom_components.syr_connect.switch import SyrConnectBuzSwitch

    dev_int = {"id": "SN200", "name": "I", "status": {"getBUZ": 1}}
    dev_float = {"id": "SN201", "name": "F", "status": {"getBUZ": 0.0}}

    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [dev_int, dev_float]}

    sw_int = SyrConnectBuzSwitch(mock_coordinator, "SN200", "I", "getBUZ")
    sw_float = SyrConnectBuzSwitch(mock_coordinator, "SN201", "F", "getBUZ")

    assert sw_int.is_on is True
    assert sw_float.is_on is False


@pytest.mark.asyncio
async def test_turn_on_api_exception_still_refreshes(hass: HomeAssistant) -> None:
    """If API raises during set, the switch should still request a refresh and swallow the error."""
    from custom_components.syr_connect.switch import SyrConnectBuzSwitch
    from custom_components.syr_connect.const import _SYR_CONNECT_SENSOR_ICON

    device = {"id": "SN300", "name": "DeviceErr", "status": {"getBUZ": "0"}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}

    async def raising_set(dclg, cmd, value):
        raise RuntimeError("boom")

    mock_coordinator.api = MagicMock()
    mock_coordinator.api.set_device_status = AsyncMock(side_effect=raising_set)
    mock_coordinator.async_request_refresh = AsyncMock()

    sw = SyrConnectBuzSwitch(mock_coordinator, "SN300", "DeviceErr", "getBUZ")

    # Icon should be set according to const mapping
    expected_icon = _SYR_CONNECT_SENSOR_ICON.get("getBUZ")
    assert sw._attr_icon == expected_icon

    # Calling turn_on should not raise despite API exception
    await sw.async_turn_on()
    mock_coordinator.api.set_device_status.assert_awaited_once()
    mock_coordinator.async_request_refresh.assert_awaited_once()
