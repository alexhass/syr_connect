"""Platform smoke tests for SYR Connect."""
from __future__ import annotations

from unittest.mock import MagicMock, Mock

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.syr_connect.binary_sensor import async_setup_entry as async_setup_binary_sensor
from custom_components.syr_connect.button import async_setup_entry as async_setup_button
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.select import (
    SyrConnectNumericSelect,
    SyrConnectRegenerationSelect,
)
from custom_components.syr_connect.select import (
    async_setup_entry as async_setup_select,
)


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


def _build_entry(coordinator: SyrConnectDataUpdateCoordinator) -> MockConfigEntry:
    entry = MockConfigEntry(domain="syr_connect", data={})
    entry.runtime_data = coordinator
    return entry


async def test_binary_sensor_platform_creates_entities(hass: HomeAssistant) -> None:
    """Ensure binary sensor platform creates expected entities."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getBUZ": "1"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_binary_sensor(hass, entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    # 1 getBUZ binary sensor (connectivity sensor moved to sensor platform)
    assert len(entities) == 1


async def test_button_platform_creates_entities(hass: HomeAssistant) -> None:
    """Ensure button platform creates action entities."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getSIR": 1, "getCNA": "LEXplus10S"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_button(hass, entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1


async def test_select_platform_creates_entities(hass: HomeAssistant) -> None:
    """Ensure select platform creates expected entities and types."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRTH": "2",
                    "getRTM": "30",
                    "getSV1": "5",
                    "getRPD": "2",
                    "getCNA": "LEXplus10S",  # model with maximum_salt_volume and maximum_regeneration_interval set
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_select(hass, entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 3

    regen_select = [e for e in entities if isinstance(e, SyrConnectRegenerationSelect)]
    numeric_select = [e for e in entities if isinstance(e, SyrConnectNumericSelect)]

    assert len(regen_select) == 1
    assert len(numeric_select) == 2
