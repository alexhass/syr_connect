"""Tests for the entities of the Safe-T+."""

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock

from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect.response_parser import ResponseParser
from custom_components.syr_connect.sensor import async_setup_entry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant


async def test_async_setup_entry_safetplus_dom(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """The Safe-T+ shows getDOM ("1 min") in seconds; the other test parameters stay hidden."""
    xml = (
        Path(__file__).parent
        / "fixtures/xml/SyrSafeTPlus_GetDeviceCollectionStatus.xml"
    ).read_text(encoding="utf-8")
    status = ResponseParser().parse_device_status_response(xml)
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": status,
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    sensors = {getattr(e, "_sensor_key", None): e for e in entities}
    assert sensors["getDOM"].native_value == 60
    assert sensors["getDOM"].native_unit_of_measurement == UnitOfTime.SECONDS
    assert not {"getDBT", "getDCM", "getDPL", "getDST", "getDTC"} & set(sensors)
