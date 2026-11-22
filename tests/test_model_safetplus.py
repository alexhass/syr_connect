"""Tests for the entities of the Safe-T+."""

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect import select as select_module
from custom_components.syr_connect.aiosyrconnect.xml_parser import ResponseParser
from custom_components.syr_connect.select import SyrConnectLeakVolumeSelect
from custom_components.syr_connect.sensor import SyrConnectSensor, async_setup_entry
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


def _fixture_data(**changes: Any) -> dict[str, Any]:
    """Return the coordinator data of the Safe-T+ fixture (firmware 2.00) with changes."""
    xml = (
        Path(__file__).parent
        / "fixtures/xml/SyrSafeTPlus_GetDeviceCollectionStatus.xml"
    ).read_text(encoding="utf-8")
    status = ResponseParser().parse_device_status_response(xml)
    assert status is not None
    return {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {**status, **changes},
            }
        ]
    }


async def _selects(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    data: dict[str, Any],
) -> tuple[dict[str, Any], MagicMock]:
    """Return the selects of the Safe-T+ by key and the coordinator."""
    mock_config_entry, coordinator = create_mock_entry_with_coordinator(data)
    coordinator.async_set_device_value = AsyncMock()
    entities, async_add_entities = mock_add_entities()
    await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)
    return {e._sensor_key: e for e in entities}, coordinator  # noqa: SLF001


async def test_safetplus_leak_protection_selects(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """The Safe-T+ sets its volume limits, the leakage time and the deactivation."""
    selects, _ = await _selects(
        hass, create_mock_entry_with_coordinator, mock_add_entities, _fixture_data()
    )

    assert set(selects) == {"getLE", "getT1", "getTMP", "getUL"}
    # Firmware 2.00: steps of 100 l from 100 l on; getLE "2" is 200 l
    assert isinstance(selects["getLE"], SyrConnectLeakVolumeSelect)
    assert selects["getLE"].options == [
        f"{liters} L" for liters in range(100, 1501, 100)
    ]
    assert selects["getLE"].current_option == "200 L"
    assert selects["getUL"].options == ["off", *(str(raw) for raw in range(1, 11))]
    assert selects["getUL"].current_option == "5"
    assert selects["getT1"].options == ["off", *(str(raw) for raw in range(1, 51))]
    assert selects["getT1"].current_option == "1"
    assert selects["getTMP"].options == [
        "off",
        "900",
        "1800",
        "3600",
        "7200",
        "10800",
        "21600",
        "43200",
        "86400",
    ]
    assert selects["getTMP"].current_option == "off"


@pytest.mark.parametrize(
    ("key", "option", "value"),
    [
        pytest.param("getLE", "500 L", 5, id="present-volume"),
        pytest.param("getUL", "off", 0, id="back-to-present"),
        pytest.param("getT1", "50", 50, id="leakage-time"),
        pytest.param("getTMP", "3600", 3600, id="deactivate"),
    ],
)
async def test_safetplus_leak_protection_select_writes(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    key: str,
    option: str,
    value: int,
) -> None:
    """A selected option is written as the raw value of the device."""
    selects, coordinator = await _selects(
        hass, create_mock_entry_with_coordinator, mock_add_entities, _fixture_data()
    )

    await selects[key].async_select_option(option)

    coordinator.async_set_device_value.assert_called_once_with(
        "device1", f"set{key[3:]}", value
    )


async def test_safetplus_old_firmware_and_running_deactivation(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """Old firmware has steps of 50 l; a running deactivation shows no option."""
    selects, coordinator = await _selects(
        hass,
        create_mock_entry_with_coordinator,
        mock_add_entities,
        _fixture_data(getVER="Safe-T+ V1.20", getTMP="3000"),
    )

    assert selects["getLE"].options == [
        f"{liters} L" for liters in range(100, 1501, 50)
    ]
    assert selects["getLE"].current_option == "100 L"
    assert selects["getTMP"].current_option is None

    await selects["getLE"].async_select_option("150 L")

    coordinator.async_set_device_value.assert_called_once_with("device1", "setLE", 3)


async def test_safetplus_leak_volume_select_without_value(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """A volume limit without a step (0) shows no option."""
    selects, _ = await _selects(
        hass,
        create_mock_entry_with_coordinator,
        mock_add_entities,
        _fixture_data(getLE="0"),
    )

    assert selects["getLE"].current_option is None


def test_safetplus_present_volume_sensor_follows_firmware(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The getLE sensor shows 200 l for the step 2 with firmware 2.00."""
    coordinator = create_mock_coordinator(_fixture_data())
    sensor = SyrConnectSensor(coordinator, "device1", "Test Device", "getLE")

    assert sensor.native_value == 200
