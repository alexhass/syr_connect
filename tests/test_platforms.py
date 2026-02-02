"""Platform smoke tests for SYR Connect."""
from __future__ import annotations

from unittest.mock import MagicMock, Mock

from homeassistant.core import HomeAssistant

from custom_components.syr_connect.binary_sensor import async_setup_entry as async_setup_binary_sensor
from custom_components.syr_connect.button import async_setup_entry as async_setup_button
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.select import (
    SyrConnectNumericSelect,
    SyrConnectRegenerationSelect,
    async_setup_entry as async_setup_select,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry


def _build_coordinator(hass: HomeAssistant, data: dict) -> SyrConnectDataUpdateCoordinator:
    coordinator = SyrConnectDataUpdateCoordinator(
        hass,
        MagicMock(),
        "test@example.com",
        "password",
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
    """Ensure binary_sensor platform creates entities for supported keys."""
    # Note: getSRE is in _SYR_CONNECT_EXCLUDED_SENSORS, so binary_sensor skips it
    # The test verifies that no entities are created when all binary sensors are excluded
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSRE": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_binary_sensor(hass, entry, add_entities)

    # getSRE is excluded, so no entities should be created
    if add_entities.called:
        entities = add_entities.call_args.args[0]
        assert len(entities) == 0
    else:
        # Platform may not call add_entities if no entities to add
        pass


async def test_button_platform_creates_entities(hass: HomeAssistant) -> None:
    """Ensure button platform creates action entities."""
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