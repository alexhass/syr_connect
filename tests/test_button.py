"""Tests for button platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.syr_connect.button import SyrConnectButton, async_setup_entry
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator


def _build_coordinator(hass: HomeAssistant, data: dict) -> SyrConnectDataUpdateCoordinator:
    config_data = {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "password",
    }
    coordinator = SyrConnectDataUpdateCoordinator(
        hass,
        MagicMock(),
        config_data,
        60,
    )
    coordinator.async_set_updated_data(data)
    coordinator.last_update_success = True
    return coordinator


async def test_button_press_success(hass: HomeAssistant) -> None:
    """Test button press succeeds."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device1", "setSIR", 0)


async def test_button_press_setsir_when_getsir_false(hass: HomeAssistant) -> None:
    """Test setSIR button press sends 'true' when getSIR reports False (softener idle)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getSIR": False},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device1", "setSIR", "true")


async def test_button_press_setsir_when_getsir_false_string(hass: HomeAssistant) -> None:
    """Test setSIR button press sends 'true' when getSIR reports the string 'false' (softener idle)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getSIR": "false"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device1", "setSIR", "true")


async def test_button_press_failure(hass: HomeAssistant) -> None:
    """Test button press handles failure."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock(side_effect=ValueError("Test error"))

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR")

    with pytest.raises(HomeAssistantError):
        await button.async_press()


async def test_button_available(hass: HomeAssistant) -> None:
    """Test button availability."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": True,
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR")

    assert button.available is True


async def test_async_setup_entry(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry creates button entities."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {"getSIR": 1, "getCNA": "LEXplus10S"},
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should create regeneration button
    assert len(entities) >= 1


async def test_async_setup_entry_multiple_devices(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry with multiple devices."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getSIR": 1, "getCNA": "LEXplus10S"},
            },
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {"getSIR": 1, "getCNA": "LEXplus10S"},
            },
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should create buttons for both devices
    assert len(entities) >= 2


async def test_button_press_other_command(hass: HomeAssistant) -> None:
    """Test button press with non-setSIR command uses value 1."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    # Use a different command that should use value=1
    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setOTHER")

    await button.async_press()

    # Default action is a no-op for commands we don't explicitly handle
    coordinator.async_set_device_value.assert_not_called()


async def test_button_press_unexpected_error(hass: HomeAssistant) -> None:
    """Test button press handles unexpected errors."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock(side_effect=ValueError("Unexpected error"))

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR")

    with pytest.raises(HomeAssistantError, match="Failed to press button"):
        await button.async_press()


async def test_button_unavailable_coordinator(hass: HomeAssistant) -> None:
    """Test button unavailable when coordinator update fails."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": True,
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.last_update_success = False

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR")

    assert button.available is False


async def test_button_unavailable_device(hass: HomeAssistant) -> None:
    """Test button unavailable when device is marked unavailable."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": False,
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR")

    assert button.available is False


async def test_button_missing_device(hass: HomeAssistant) -> None:
    """Test button when device not in coordinator data."""
    data = {
        "devices": [
            {
                "id": "other_device",
                "name": "Other Device",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR")

    # Should return True when device not found (default availability)
    assert button.available is True


async def test_async_setup_entry_no_data(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry with no coordinator data."""
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(None)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should not add any entities when no data
    async_add_entities.assert_not_called()


async def test_button_initialization_attributes(hass: HomeAssistant) -> None:
    """Test button initialization sets correct attributes."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setSIR")

    # Check attributes
    assert button._attr_unique_id == "device1_setSIR"
    assert button._attr_has_entity_name is True
    assert button._attr_translation_key == "setsir"
    assert button._device_id == "device1"
    assert button._command == "setSIR"


async def test_async_setup_entry_skip_setsir_when_getsir_missing(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry skips setSIR button when getSIR is not available."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getBAR": "4077 mbar",
                    "getBAT": "6,12 4,38 3,90",
                    # getSIR is missing - setSIR button should not be created
                },
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should not create any buttons since getSIR is not available
    assert len(entities) == 0


async def test_async_setup_entry_create_setsir_when_getsir_present(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry creates setSIR button when getSIR is available."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getSIR": "1",  # getSIR is present - setSIR button should be created
                    "getCNA": "LEXplus10S",  # model with maximum_regeneration_interval set
                },
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should create setSIR button
    assert len(entities) == 1
    assert entities[0]._command == "setSIR"


async def test_async_setup_entry_no_getsir(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities) -> None:
    """Test async_setup_entry with device that does not support setSIR (no getSIR in status)."""
    data = {
        "devices": [
            {
                "id": "safe_t_plus",
                "name": "Safe-T+",
                "project_id": "project1",
                "status": {},  # No getSIR present
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    # Should not create any button
    assert len(entities) == 0


@pytest.mark.parametrize("falsy_value", ["false"])
async def test_async_setup_entry_skip_setsir_when_getsir_false(hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities, falsy_value) -> None:
    """Test async_setup_entry creates a setSIR button when getSIR is 'false'.

    getSIR='false' means the water softener is idle (not regenerating).
    The button must still be created so the user can trigger a regeneration.
    """
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getSIR": falsy_value, "getCNA": "LEXplus10S"},
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    # getSIR='false' -> softener is idle -> setSIR button must be created
    assert len(entities) == 1


async def test_async_setup_entry_removes_stale_setsir_from_registry(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator,
    mock_add_entities,
) -> None:
    """Test that a previously-registered setSIR button is removed from the registry
    when the device no longer reports a getSIR key in its status."""
    from unittest.mock import MagicMock, patch

    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},  # getSIR is absent — button must not be created
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    stale_entity_id = "button.syr_connect_device1_setsir"

    class FakeEntry:
        def __init__(self, eid: str) -> None:
            self.entity_id = eid

    mock_registry = MagicMock()
    mock_registry.async_remove = MagicMock()
    mock_registry.entities = {stale_entity_id: FakeEntry(stale_entity_id)}

    with patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_registry):
        await async_setup_entry(hass, mock_config_entry, async_add_entities)

    mock_registry.async_remove.assert_called_once_with(stale_entity_id)
    assert len(entities) == 0


async def test_async_setup_entry_registry_cleanup_skips_other_device_entries(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator,
    mock_add_entities,
) -> None:
    """Cleanup loop skips registry entries that belong to a different device (line 121 continue)."""
    from unittest.mock import MagicMock, patch

    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getSIR": "false"},
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    # An entry for a completely different device — should be skipped (continue)
    other_entity_id = "button.syr_connect_other_device_setsir"

    class FakeEntry:
        def __init__(self, eid: str) -> None:
            self.entity_id = eid

    mock_registry = MagicMock()
    mock_registry.async_remove = MagicMock()
    mock_registry.entities = {other_entity_id: FakeEntry(other_entity_id)}

    with patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_registry):
        await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # The other-device entry must NOT be removed by this device's cleanup pass
    mock_registry.async_remove.assert_not_called()


async def test_async_setup_entry_registry_cleanup_exception_is_caught(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator,
    mock_add_entities,
) -> None:
    """Exception from er.async_get during per-device cleanup is caught (line 134)."""
    from unittest.mock import patch

    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getSIR": "false"},
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    call_count = 0

    def er_async_get_side_effect(_hass_instance):
        nonlocal call_count
        call_count += 1
        # First call is for registry_cleanup (let it succeed with an empty registry),
        # second call is the per-device cleanup in async_setup_entry.
        from unittest.mock import MagicMock
        if call_count == 1:
            empty_reg = MagicMock()
            empty_reg.entities = {}
            return empty_reg
        raise RuntimeError("registry unavailable")

    with patch(
        "homeassistant.helpers.entity_registry.async_get",
        side_effect=er_async_get_side_effect,
    ):
        # Must not raise — the except block swallows the error
        await async_setup_entry(hass, mock_config_entry, async_add_entities)


async def test_button_reset_no_reset_required(hass: HomeAssistant) -> None:
    """Reset button raises when no reset required (missing/empty get key)."""
    data = {
        "devices": [
            {
                "id": "device_reset",
                "name": "Device Reset",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    button = SyrConnectButton(coordinator, "device_reset", "Device Reset", "project1", "setALA")

    with pytest.raises(HomeAssistantError, match=r"No reset required for getALA on device_reset"):
        await button.async_press()


async def test_button_reset_ala_lexplus10s_calls_clr_alm(hass: HomeAssistant) -> None:
    """LEXplus10S uses getALM (alarm_style_alm=True) and clears via clrALM (alarm_clear_via_set=False)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getALM": "LowSalt", "getCNA": "LEXplus10S"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    coordinator.async_clear_device_alarm = AsyncMock()

    button = SyrConnectButton(coordinator, "device1", "Device 1", "project1", "setALA")

    await button.async_press()

    coordinator.async_clear_device_alarm.assert_called_once_with("device1", "alm")
    coordinator.async_set_device_value.assert_not_called()


async def test_button_reset_ala_unknown_model_calls_clr_ala(hass: HomeAssistant) -> None:
    """Unknown model (no alarm_clear_via_set) clears alarm via clrALA endpoint."""
    data = {
        "devices": [
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {"getALA": "A5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    coordinator.async_clear_device_alarm = AsyncMock()

    button = SyrConnectButton(coordinator, "device2", "Device 2", "project1", "setALA")

    await button.async_press()

    coordinator.async_clear_device_alarm.assert_called_once_with("device2", "ala")
    coordinator.async_set_device_value.assert_not_called()


async def test_button_reset_detect_model_exception(hass: HomeAssistant, monkeypatch) -> None:
    """If detect_model raises, falls back to default model_info={} and calls clrALA."""
    from custom_components.syr_connect import button as button_mod

    data = {
        "devices": [
            {
                "id": "device3",
                "name": "Device 3",
                "project_id": "project1",
                "status": {"getALA": "A5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    coordinator.async_clear_device_alarm = AsyncMock()

    # Make detect_model raise
    monkeypatch.setattr(button_mod, "detect_model", lambda *_: (_ for _ in ()).throw(ValueError("boom")))

    button = SyrConnectButton(coordinator, "device3", "Device 3", "project1", "setALA")

    await button.async_press()

    # model_info={} -> alarm_clear_via_set=False -> clrALA endpoint
    coordinator.async_clear_device_alarm.assert_called_once_with("device3", "ala")
    coordinator.async_set_device_value.assert_not_called()

async def test_button_reset_ala_clr_endpoint_pontosbase(hass: HomeAssistant) -> None:
    """Pontos Base (JSON API) clears alarm via /clr/ala, not setALA."""
    data = {
        "devices": [
            {
                "id": "device_pontos",
                "name": "Device Pontos",
                "project_id": "project1",
                "status": {"getALA": "A5", "getVER": "PontosBase V1.31"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    coordinator.async_clear_device_alarm = AsyncMock()

    button = SyrConnectButton(coordinator, "device_pontos", "Device Pontos", "project1", "setALA")
    await button.async_press()

    coordinator.async_clear_device_alarm.assert_called_once_with("device_pontos", "ala")
    coordinator.async_set_device_value.assert_not_called()


async def test_button_reset_ala_clr_endpoint_safetechv4(hass: HomeAssistant) -> None:
    """SafeTech V4 (JSON API) clears alarm via /clr/ala, not setALA."""
    data = {
        "devices": [
            {
                "id": "device_stv4",
                "name": "Device STv4",
                "project_id": "project1",
                "status": {"getALA": "A5", "getVER": "Safe-Tech V4.1"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    coordinator.async_clear_device_alarm = AsyncMock()

    button = SyrConnectButton(coordinator, "device_stv4", "Device STv4", "project1", "setALA")
    await button.async_press()

    coordinator.async_clear_device_alarm.assert_called_once_with("device_stv4", "ala")
    coordinator.async_set_device_value.assert_not_called()


async def test_button_reset_ala_clr_error_propagates(hass: HomeAssistant) -> None:
    """Errors from async_clear_device_alarm propagate and are not swallowed."""
    data = {
        "devices": [
            {
                "id": "device_pontos",
                "name": "Device Pontos",
                "project_id": "project1",
                "status": {"getALA": "A5", "getVER": "PontosBase V1.31"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    coordinator.async_clear_device_alarm = AsyncMock(
        side_effect=HomeAssistantError("Connection failed")
    )

    button = SyrConnectButton(coordinator, "device_pontos", "Device Pontos", "project1", "setALA")
    with pytest.raises(HomeAssistantError):
        await button.async_press()

    coordinator.async_clear_device_alarm.assert_called_once_with("device_pontos", "ala")
    coordinator.async_set_device_value.assert_not_called()


async def test_button_reset_not_no_reset_required(hass: HomeAssistant) -> None:
    """setNOT raises when no reset required (missing/empty getNOT)."""
    data = {
        "devices": [
            {
                "id": "device_not",
                "name": "Device NOT",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    button = SyrConnectButton(coordinator, "device_not", "Device NOT", "project1", "setNOT")

    with pytest.raises(HomeAssistantError, match=r"No reset required for getNOT on device_not"):
        await button.async_press()


async def test_button_reset_not_sends_ff_via_xml_api(hass: HomeAssistant) -> None:
    """setNOT sends 'FF' when using the XML API (MagicMock api is not SyrConnectJsonAPI)."""
    data = {
        "devices": [
            {
                "id": "device_not1",
                "name": "Device NOT1",
                "project_id": "project1",
                "status": {"getNOT": "01"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    button = SyrConnectButton(coordinator, "device_not1", "Device NOT1", "project1", "setNOT")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device_not1", "setNOT", "FF")


async def test_button_reset_not_send_ff_for_other_models(hass: HomeAssistant) -> None:
    """When model unknown/other, setNOT reset sends 'FF'."""
    data = {
        "devices": [
            {
                "id": "device_not2",
                "name": "Device NOT2",
                "project_id": "project1",
                "status": {"getNOT": "01"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    button = SyrConnectButton(coordinator, "device_not2", "Device NOT2", "project1", "setNOT")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device_not2", "setNOT", "FF")


async def test_button_reset_wrn_no_reset_required(hass: HomeAssistant) -> None:
    """setWRN raises when no reset required (missing/empty getWRN)."""
    data = {
        "devices": [
            {
                "id": "device_wrn",
                "name": "Device WRN",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    button = SyrConnectButton(coordinator, "device_wrn", "Device WRN", "project1", "setWRN")

    with pytest.raises(HomeAssistantError, match=r"No reset required for getWRN on device_wrn"):
        await button.async_press()


async def test_button_reset_wrn_sends_ff_via_xml_api(hass: HomeAssistant) -> None:
    """setWRN sends 'FF' when using the XML API (MagicMock api is not SyrConnectJsonAPI)."""
    data = {
        "devices": [
            {
                "id": "device_wrn1",
                "name": "Device WRN1",
                "project_id": "project1",
                "status": {"getWRN": "02"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    button = SyrConnectButton(coordinator, "device_wrn1", "Device WRN1", "project1", "setWRN")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device_wrn1", "setWRN", "FF")


async def test_button_reset_wrn_send_ff_for_other_models(hass: HomeAssistant) -> None:
    """When model unknown/other, setWRN reset sends 'FF'."""
    data = {
        "devices": [
            {
                "id": "device_wrn2",
                "name": "Device WRN2",
                "project_id": "project1",
                "status": {"getWRN": "02"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    button = SyrConnectButton(coordinator, "device_wrn2", "Device WRN2", "project1", "setWRN")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device_wrn2", "setWRN", "FF")


async def test_button_reset_ala_alarm_clear_via_set_sends_ff(hass: HomeAssistant) -> None:
    """When alarm_clear_via_set=True (Trio LS), reset sends setALA 'FF' instead of calling clrALA."""
    data = {
        "devices": [
            {
                "id": "device_trio",
                "name": "Device Trio",
                "project_id": "project1",
                # getSRN starting with "100AAA" matches Trio LS (srn_prefix="100")
                "status": {"getALA": "A5", "getSRN": "100AAA001"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    coordinator.async_clear_device_alarm = AsyncMock()

    button = SyrConnectButton(coordinator, "device_trio", "Device Trio", "project1", "setALA")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device_trio", "setALA", "FF")
    coordinator.async_clear_device_alarm.assert_not_called()


async def test_button_reset_not_sends_255_via_json_api(hass: HomeAssistant) -> None:
    """setNOT sends integer 255 when using the JSON API (/set/not/255)."""
    from custom_components.syr_connect.api_json import SyrConnectJsonAPI

    data = {
        "devices": [
            {
                "id": "device_not_json",
                "name": "Device NOT JSON",
                "project_id": "project1",
                "status": {"getNOT": "01"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    coordinator.api.__class__ = SyrConnectJsonAPI

    button = SyrConnectButton(coordinator, "device_not_json", "Device NOT JSON", "project1", "setNOT")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device_not_json", "setNOT", 255)


async def test_button_reset_wrn_sends_255_via_json_api(hass: HomeAssistant) -> None:
    """setWRN sends integer 255 when using the JSON API (/set/wrn/255)."""
    from custom_components.syr_connect.api_json import SyrConnectJsonAPI

    data = {
        "devices": [
            {
                "id": "device_wrn_json",
                "name": "Device WRN JSON",
                "project_id": "project1",
                "status": {"getWRN": "02"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    coordinator.api.__class__ = SyrConnectJsonAPI

    button = SyrConnectButton(coordinator, "device_wrn_json", "Device WRN JSON", "project1", "setWRN")

    await button.async_press()

    coordinator.async_set_device_value.assert_called_once_with("device_wrn_json", "setWRN", 255)


@pytest.mark.parametrize("sentinel", ["0", "00", "a0x0000", "A0X0000"])
async def test_button_reset_ala_sentinel_values_no_reset(hass: HomeAssistant, sentinel: str) -> None:
    """Sentinel values (0, 00, a0x0000) suppress the alarm reset."""
    data = {
        "devices": [
            {
                "id": "device_sentinel",
                "name": "Device Sentinel",
                "project_id": "project1",
                "status": {"getALA": sentinel},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()
    coordinator.async_clear_device_alarm = AsyncMock()

    button = SyrConnectButton(coordinator, "device_sentinel", "Device Sentinel", "project1", "setALA")

    with pytest.raises(HomeAssistantError, match="No reset required"):
        await button.async_press()

    coordinator.async_set_device_value.assert_not_called()
    coordinator.async_clear_device_alarm.assert_not_called()
