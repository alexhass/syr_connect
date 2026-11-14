"""Tests for the entities of the TrioLock with a real fixture."""

# The tests check private attributes of the entities.
# ruff: noqa: SLF001

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock

from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect import (
    button as button_module,
    select as select_module,
    sensor as sensor_module,
    valve as valve_module,
)
from custom_components.syr_connect.api_json import SyrConnectJsonAPI
from custom_components.syr_connect.response_parser import ResponseParser
from custom_components.syr_connect.select import (
    SyrConnectPrfSelect,
    SyrConnectRotationSelect,
)
from homeassistant.core import HomeAssistant


async def test_async_setup_entry_creates_setdex_for_triolock_real_fixture(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """SYR TRIO Lock Connect (muco_triolock) real fixture creates setDEX on the JSON API."""

    xml = (
        Path(__file__).parent / "fixtures/xml/SyrTrioLock_GetDeviceCollectionStatus.xml"
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
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    mock_coordinator.api.__class__ = SyrConnectJsonAPI
    entities, async_add_entities = mock_add_entities()

    await button_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert any(e._command == "setDEX" for e in entities)


async def test_async_setup_entry_creates_triolock_selects_from_real_fixture(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """SYR TRIO Lock Connect (muco_triolock) real fixture creates getPRF/getSRO selects, no getFFM select."""
    xml = (
        Path(__file__).parent / "fixtures/xml/SyrTrioLock_GetDeviceCollectionStatus.xml"
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
    mock_config_entry, _mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    # SyrConnectPrfSelect/SyrConnectRotationSelect don't set `_sensor_key` (unlike
    # SyrConnectNumericSelect), so identify them by type instead.
    assert any(isinstance(e, SyrConnectPrfSelect) for e in entities)
    assert any(isinstance(e, SyrConnectRotationSelect) for e in entities)
    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert "getFFM" not in keys


async def test_async_setup_entry_creates_triolock_sensors_from_real_fixture(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """SYR TRIO Lock Connect (muco_triolock) real fixture creates the newly-confirmed sensors."""
    xml = (
        Path(__file__).parent / "fixtures/xml/SyrTrioLock_GetDeviceCollectionStatus.xml"
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

    await sensor_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert {
        "getAB",
        "getVLV",
        "getDBD",
        "getDBT",
        "getDCM",
        "getDMA",
        "getDOM",
        "getDPL",
        "getDRP",
        "getDST",
        "getDSV",
        "getDTC",
        "getDTT",
        "getPA1",
        "getPRF",
        "getPRN",
    } <= keys


async def test_async_setup_entry_creates_valve_for_triolock_real_fixture(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """SYR TRIO Lock Connect (muco_triolock) real fixture creates a valve entity for getAB."""
    xml = (
        Path(__file__).parent / "fixtures/xml/SyrTrioLock_GetDeviceCollectionStatus.xml"
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
    mock_config_entry, _mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await valve_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert len(entities) == 1
