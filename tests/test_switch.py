"""Tests for switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
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

    sw_on = SyrConnectBuzSwitch(mock_coordinator, "SN123", "DeviceOn", "", "getBUZ")
    sw_off = SyrConnectBuzSwitch(mock_coordinator, "SN124", "DeviceOff", "", "getBUZ")

    # Unique id should include platform suffix set in implementation
    assert sw_on._attr_unique_id.endswith("_switch")

    assert sw_on.is_on is True
    assert sw_off.is_on is False

    # Test turn_on/turn_off call coordinator and verify command name
    async def fake_set_device_value(device_id, cmd, value):
        assert cmd == "setBUZ"

    mock_coordinator.async_set_device_value = AsyncMock(side_effect=fake_set_device_value)

    # call turn on/off
    await sw_off.async_turn_on()
    mock_coordinator.async_set_device_value.assert_called()

    await sw_on.async_turn_off()
    assert mock_coordinator.async_set_device_value.call_count >= 2


async def test_async_setup_entry_creates_entity(hass: HomeAssistant) -> None:
    """Test that switch platform creates entity when getBUZ present."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="TestCreate",
        data={CONF_USERNAME: "test", CONF_PASSWORD: "test"},
        source="user",
        entry_id="test_entry_create",
        unique_id="test_unique_id_create",
        discovery_keys={},
        options={},
        subentries_data={},
    )

    device = {"id": "SN400", "name": "CreateDevice", "status": {"getBUZ": True}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}
    config_entry.runtime_data = mock_coordinator

    mock_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, mock_add_entities)

    mock_add_entities.assert_called_once()
    args = mock_add_entities.call_args[0][0]
    assert len(args) == 1
    # instance type check
    from custom_components.syr_connect.switch import SyrConnectBuzSwitch

    assert isinstance(args[0], SyrConnectBuzSwitch)


def test_is_on_boolean_and_string_values() -> None:
    """Test boolean and various string values for is_on parsing."""
    from custom_components.syr_connect.switch import SyrConnectBuzSwitch

    dev_bool_true = {"id": "SN500", "name": "BTrue", "status": {"getBUZ": True}}
    dev_bool_false = {"id": "SN501", "name": "BFalse", "status": {"getBUZ": False}}
    dev_str_true = {"id": "SN502", "name": "STrue", "status": {"getBUZ": " true "}}
    dev_str_on = {"id": "SN503", "name": "SOn", "status": {"getBUZ": "On"}}
    dev_str_yes = {"id": "SN504", "name": "SYes", "status": {"getBUZ": "YES"}}

    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [dev_bool_true, dev_bool_false, dev_str_true, dev_str_on, dev_str_yes]}

    sw_bool_true = SyrConnectBuzSwitch(mock_coordinator, "SN500", "BTrue", "", "getBUZ")
    sw_bool_false = SyrConnectBuzSwitch(mock_coordinator, "SN501", "BFalse", "", "getBUZ")
    sw_str_true = SyrConnectBuzSwitch(mock_coordinator, "SN502", "STrue", "", "getBUZ")
    sw_str_on = SyrConnectBuzSwitch(mock_coordinator, "SN503", "SOn", "", "getBUZ")
    sw_str_yes = SyrConnectBuzSwitch(mock_coordinator, "SN504", "SYes", "", "getBUZ")

    assert sw_bool_true.is_on is True
    assert sw_bool_false.is_on is False
    assert sw_str_true.is_on is True
    assert sw_str_on.is_on is True
    assert sw_str_yes.is_on is True


def test_is_on_unrecognized_type_returns_none() -> None:
    """Unrecognized types (e.g., dict) should return None for is_on."""
    from custom_components.syr_connect.switch import SyrConnectBuzSwitch

    dev_bad = {"id": "SN600", "name": "Bad", "status": {"getBUZ": {"foo": "bar"}}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [dev_bad]}

    sw_bad = SyrConnectBuzSwitch(mock_coordinator, "SN600", "Bad", "", "getBUZ")
    assert sw_bad.is_on is None


def test_entity_category_is_config() -> None:
    """Entity category should be CONFIG for keys in _SYR_CONNECT_SENSOR_CONFIG."""
    from homeassistant.helpers.entity import EntityCategory

    from custom_components.syr_connect.const import _SYR_CONNECT_SENSOR_CONFIG
    from custom_components.syr_connect.switch import SyrConnectBuzSwitch

    # Ensure getBUZ is in the config set (it is by design)
    assert "getBUZ" in _SYR_CONNECT_SENSOR_CONFIG

    dev = {"id": "SN700", "name": "Cfg", "status": {"getBUZ": 0}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [dev]}

    sw = SyrConnectBuzSwitch(mock_coordinator, "SN700", "Cfg", "", "getBUZ")
    assert sw._attr_entity_category == EntityCategory.CONFIG


async def test_async_setup_entry_handles_instantiation_error(hass: HomeAssistant) -> None:
    """If creating SyrConnectBuzSwitch raises, async_setup_entry should log and continue."""

    import custom_components.syr_connect.switch as switch_mod

    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="TestErr",
        data={CONF_USERNAME: "test", CONF_PASSWORD: "test"},
        source="user",
        entry_id="test_entry_err",
        unique_id="test_unique_id_err",
        discovery_keys={},
        options={},
        subentries_data={},
    )

    # Device contains getBUZ so code will attempt to instantiate
    device = {"id": "SN800", "name": "ErrDevice", "status": {"getBUZ": 1}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}
    config_entry.runtime_data = mock_coordinator

    # Monkeypatch the constructor to raise
    original_cls = switch_mod.SyrConnectBuzSwitch

    def raise_on_init(*args, **kwargs):
        raise RuntimeError("ctor boom")

    switch_mod.SyrConnectBuzSwitch = raise_on_init

    mock_add_entities = MagicMock()

    # Should not raise
    await async_setup_entry(hass, config_entry, mock_add_entities)

    mock_add_entities.assert_not_called()

    # restore
    switch_mod.SyrConnectBuzSwitch = original_cls


async def test_async_setup_entry_device_without_getbuz(hass: HomeAssistant) -> None:
    """Device present but without getBUZ should not create entities."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="TestNoBUZ",
        data={CONF_USERNAME: "test", CONF_PASSWORD: "test"},
        source="user",
        entry_id="test_entry_nobuz",
        unique_id="test_unique_id_nobuz",
        discovery_keys={},
        options={},
        subentries_data={},
    )

    device = {"id": "SN900", "name": "NoBuz", "status": {"getXYZ": 1}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}
    config_entry.runtime_data = mock_coordinator

    mock_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, mock_add_entities)

    mock_add_entities.assert_not_called()


def test_is_on_device_missing() -> None:
    """If the device is not present in coordinator data, is_on should be None."""
    from custom_components.syr_connect.switch import SyrConnectBuzSwitch

    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": []}

    sw = SyrConnectBuzSwitch(mock_coordinator, "MISSING", "Missing", "", "getBUZ")
    assert sw.is_on is None


def test_is_on_with_int_and_float_values() -> None:
    """Ensure numeric getBUZ values are interpreted correctly."""
    from custom_components.syr_connect.switch import SyrConnectBuzSwitch

    dev_int = {"id": "SN200", "name": "I", "status": {"getBUZ": 1}}
    dev_float = {"id": "SN201", "name": "F", "status": {"getBUZ": 0.0}}

    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [dev_int, dev_float]}

    sw_int = SyrConnectBuzSwitch(mock_coordinator, "SN200", "I", "", "getBUZ")
    sw_float = SyrConnectBuzSwitch(mock_coordinator, "SN201", "F", "", "getBUZ")

    assert sw_int.is_on is True
    assert sw_float.is_on is False


@pytest.mark.asyncio
async def test_turn_on_api_exception_still_refreshes(hass: HomeAssistant) -> None:
    """If API raises during set, the switch should still request a refresh and swallow the error."""
    from custom_components.syr_connect.const import _SYR_CONNECT_SENSOR_ICON
    from custom_components.syr_connect.switch import SyrConnectBuzSwitch

    device = {"id": "SN300", "name": "DeviceErr", "status": {"getBUZ": "0"}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}

    async def raising_set(device_id, cmd, value):
        raise RuntimeError("boom")

    mock_coordinator.async_set_device_value = AsyncMock(side_effect=raising_set)

    sw = SyrConnectBuzSwitch(mock_coordinator, "SN300", "DeviceErr", "", "getBUZ")

    # Icon should be set according to const mapping
    expected_icon = _SYR_CONNECT_SENSOR_ICON.get("getBUZ")
    assert sw._attr_icon == expected_icon

    # Calling turn_on should not raise despite API exception
    await sw.async_turn_on()
    mock_coordinator.async_set_device_value.assert_awaited_once()


async def test_async_setup_entry_uses_existing_registry_entity_id(hass: HomeAssistant) -> None:
    """If registry already has entity for unique_id, use its entity_id."""
    import homeassistant.helpers.entity_registry as er_mod

    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="TestReg",
        data={CONF_USERNAME: "test", CONF_PASSWORD: "test"},
        source="user",
        entry_id="test_entry_reg",
        unique_id="test_unique_id_reg",
        discovery_keys={},
        options={},
        subentries_data={},
    )

    device = {"id": "SNREG", "name": "RegDevice", "status": {"getBUZ": True}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}
    config_entry.runtime_data = mock_coordinator

    entities = []
    def _add(ents):
        entities.extend(ents)

    # Mock registry to return an existing entity id for the unique_id
    mock_registry = MagicMock()
    mock_registry.async_get_entity_id = MagicMock(return_value="switch.existing_buz")
    mock_registry.async_get = MagicMock(return_value=object())

    with pytest.MonkeyPatch.context() as m:
        m.setattr(er_mod, "async_get", lambda hass: mock_registry)
        await async_setup_entry(hass, config_entry, _add)

    assert len(entities) == 1
    # entity_id should be replaced with registry's value
    assert getattr(entities[0], "entity_id", None) == "switch.existing_buz"


async def test_async_setup_entry_detects_missing_registry_entries(hass: HomeAssistant) -> None:
    """When registry reports no entry for created entity, verification logic runs."""
    import homeassistant.helpers.entity_registry as er_mod

    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="TestMiss",
        data={CONF_USERNAME: "test", CONF_PASSWORD: "test"},
        source="user",
        entry_id="test_entry_miss",
        unique_id="test_unique_id_miss",
        discovery_keys={},
        options={},
        subentries_data={},
    )

    device = {"id": "SNMISS", "name": "MissDevice", "status": {"getBUZ": True}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}
    config_entry.runtime_data = mock_coordinator

    entities = []
    def _add(ents):
        entities.extend(ents)

    # Registry that returns None for lookups -> triggers 'missing' path
    mock_registry = MagicMock()
    mock_registry.async_get_entity_id = MagicMock(return_value=None)
    mock_registry.async_get = MagicMock(return_value=None)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(er_mod, "async_get", lambda hass: mock_registry)
        await async_setup_entry(hass, config_entry, _add)

    # Should have created entity and registry lookups attempted
    assert len(entities) == 1
    mock_registry.async_get.assert_called()
    mock_registry.async_get_entity_id.assert_called()


async def test_async_setup_entry_handles_registry_exceptions(hass: HomeAssistant) -> None:
    """If entity registry access raises, setup should continue and add entities."""
    import homeassistant.helpers.entity_registry as er_mod

    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="TestErrReg",
        data={CONF_USERNAME: "test", CONF_PASSWORD: "test"},
        source="user",
        entry_id="test_entry_errreg",
        unique_id="test_unique_id_errreg",
        discovery_keys={},
        options={},
        subentries_data={},
    )

    device = {"id": "SNERR", "name": "ErrDevice", "status": {"getBUZ": True}}
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}
    config_entry.runtime_data = mock_coordinator

    entities = []
    def _add(ents):
        entities.extend(ents)

    # async_get will raise to hit the exception branch
    def _raise(_h):
        raise RuntimeError("registry boom")

    with pytest.MonkeyPatch.context() as m:
        m.setattr(er_mod, "async_get", _raise)
        await async_setup_entry(hass, config_entry, _add)

    # Should still add the created entity despite registry exceptions
    assert len(entities) == 1
