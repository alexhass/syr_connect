"""Tests for the entities of the MultiController filling module."""

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.syr_connect.const import CONF_SERVICE
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.models import MODEL_SIGNATURES
from custom_components.syr_connect.select import (
    SyrConnectRangedHardnessSelect,
    async_setup_entry,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

_SYR_CONNECT_TEST_MUCO_FILLING_MODEL = next(
    model for model in MODEL_SIGNATURES if model.name == "conelclearprofill"
)


def _build_coordinator(hass: HomeAssistant, data: dict) -> Any:
    """Build a real coordinator; typed Any because tests replace its methods with mocks."""
    config_data = {
        CONF_SERVICE: "de.consoft.syr.connect",
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "password",
    }
    coordinator = SyrConnectDataUpdateCoordinator(
        hass,
        MagicMock(),
        config_data,
        60,
    )
    coordinator.async_set_updated_data(cast(Any, data))
    coordinator.last_update_success = True
    return coordinator


async def test_async_setup_entry_creates_muco_config_selects(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """async_setup_entry creates all MuCo/CONEL config selects when present in status."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "model": _SYR_CONNECT_TEST_MUCO_FILLING_MODEL,
                "status": {
                    "getCRS": "3",
                    "getCRT": "1",
                    "getRCD": "2",
                    "getRMN": "5",
                    "getRMT": "30",
                    "getRVT": "100",
                    "getTPR": "18",
                    "getLOT": "7",
                },
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert {
        "getCRS",
        "getCRT",
        "getRCD",
        "getRMN",
        "getRMT",
        "getRVT",
        "getTPR",
        "getLOT",
    } <= keys


@pytest.mark.parametrize(
    ("whu", "iwh", "iwh_options", "ohw_options", "iwh_current", "ohw_current"),
    [
        pytest.param(
            "0",
            "18",
            [f"{value} °dH" for value in range(1, 51)],
            [f"{value} °dH" for value in range(13)],
            "18 °dH",
            "5 °dH",
            id="dh",
        ),
        pytest.param(
            "1",
            "18",
            [f"{value} °e" for value in range(1, 66)],
            [f"{value} °e" for value in range(17)],
            "23 °e",
            "6 °e",
            id="e",
        ),
        pytest.param(
            "1",
            "5",
            [f"{value} °e" for value in range(1, 66)],
            [f"{value} °e" for value in range(7)],
            "6 °e",
            "6 °e",
            id="e-limited-by-raw-water",
        ),
        pytest.param(
            "2",
            "18",
            [f"{value} °fH" for value in range(1, 91)],
            [f"{value} °fH" for value in range(23)],
            "32 °fH",
            "9 °fH",
            id="fh",
        ),
        pytest.param(
            "3",
            "18",
            [f"{value} ppm" for value in range(10, 901, 10)],
            [f"{value} ppm" for value in range(0, 221, 10)],
            "320 ppm",
            "80 ppm",
            id="ppm-step-below",
        ),
        pytest.param("7", "18", [], [], "18", "5", id="unknown-unit"),
    ],
)
async def test_muco_filling_hardness_selects_convert_from_dh(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    whu: str,
    iwh: str,
    iwh_options: list[str],
    ohw_options: list[str],
    iwh_current: str,
    ohw_current: str,
) -> None:
    """The MuCo filling keeps the water hardness in °dH and shows it in the unit."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "model": _SYR_CONNECT_TEST_MUCO_FILLING_MODEL,
                "status": {
                    "getCRT": "0",
                    "getIWH": iwh,
                    "getOHW": "5",
                    "getWHU": whu,
                },
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    by_key = {getattr(e, "_sensor_key", None): e for e in entities}
    assert isinstance(by_key["getIWH"], SyrConnectRangedHardnessSelect)
    assert isinstance(by_key["getOHW"], SyrConnectRangedHardnessSelect)
    assert by_key["getIWH"].options == iwh_options
    assert by_key["getOHW"].options == ohw_options
    assert by_key["getIWH"].current_option == iwh_current
    assert by_key["getOHW"].current_option == ohw_current


@pytest.mark.parametrize(
    ("whu", "key", "option", "set_key", "expected"),
    [
        pytest.param("0", "getIWH", "18 °dH", "setIWH", 18, id="dh"),
        pytest.param("1", "getIWH", "23 °e", "setIWH", 18, id="e"),
        pytest.param("2", "getOHW", "9 °fH", "setOHW", 5, id="fh"),
        pytest.param("3", "getIWH", "320 ppm", "setIWH", 18, id="ppm"),
        pytest.param("3", "getOHW", "80 ppm", "setOHW", 4, id="ppm-step-below"),
    ],
)
async def test_muco_filling_hardness_select_writes_dh(
    hass: HomeAssistant, whu: str, key: str, option: str, set_key: str, expected: int
) -> None:
    """An option in the unit of the display is written to the MuCo filling in °dH."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "model": _SYR_CONNECT_TEST_MUCO_FILLING_MODEL,
                "status": {"getIWH": "18", "getOHW": "5", "getWHU": whu},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_value = AsyncMock()

    select = SyrConnectRangedHardnessSelect(coordinator, "device1", "Device 1", key)
    await select.async_select_option(option)

    coordinator.async_set_device_value.assert_called_once_with(
        "device1", set_key, expected
    )
