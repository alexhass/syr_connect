"""Tests for the entities of the MultiController filling module."""

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect import switch as switch_module
from custom_components.syr_connect.aiosyrconnect import SyrConnectConnectionError
from custom_components.syr_connect.const import CONF_SERVICE
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.models import MODELS
from custom_components.syr_connect.select import (
    SyrConnectCartridgeTypeSelect,
    SyrConnectRangedHardnessSelect,
    async_setup_entry,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

_SYR_CONNECT_TEST_MUCO_FILLING_MODEL = next(
    model for model in MODELS if model.name == "conelclearprofill"
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
                    "getCWL": "10",
                    "getFMT": "30",
                    "getFVT": "100",
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
        "getCWL",
        "getFMT",
        "getFVT",
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


def _cartridge_type_select(
    hass: HomeAssistant, status: dict[str, Any]
) -> tuple[SyrConnectCartridgeTypeSelect, Any]:
    """Return the cartridge type select of a MuCo filling with the status, and its coordinator."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "model": _SYR_CONNECT_TEST_MUCO_FILLING_MODEL,
                "status": status,
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.async_set_device_values = AsyncMock()
    select = SyrConnectCartridgeTypeSelect(
        coordinator,
        "device1",
        "Device 1",
        "getCRT",
        {"none": None, "0": 0, "1": 1, "2": 2},
    )
    return select, coordinator


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(
            {"getCRT": "1", "getWTR": False}, "none", id="water-treatment-off"
        ),
        pytest.param({"getCRT": "1", "getWTR": True}, "1", id="water-treatment-on"),
        pytest.param({"getCRT": "", "getWTR": True}, "none", id="no-cartridge"),
        pytest.param({"getCRT": "2"}, "2", id="without-water-treatment"),
    ],
)
async def test_muco_filling_cartridge_type_follows_water_treatment(
    hass: HomeAssistant, status: dict[str, Any], expected: str
) -> None:
    """While the water treatment (getWTR) is off, the cartridge type shows "none"."""
    select, _ = _cartridge_type_select(hass, status)

    assert select.current_option == expected


@pytest.mark.parametrize(
    ("status", "option", "expected"),
    [
        pytest.param(
            {"getCRT": "1", "getWTR": True},
            "none",
            [("setWTR", False)],
            id="none-switches-off",
        ),
        pytest.param(
            {"getCRT": "1", "getWTR": False},
            "2",
            [("setCRT", 2), ("setWTR", True)],
            id="type-switches-on",
        ),
        pytest.param(
            {"getCRT": "1", "getWTR": True},
            "0",
            [("setCRT", 0)],
            id="type-water-treatment-on",
        ),
    ],
)
async def test_muco_filling_cartridge_type_writes_water_treatment(
    hass: HomeAssistant,
    status: dict[str, Any],
    option: str,
    expected: list[tuple[str, Any]],
) -> None:
    """The cartridge type is written together with the water treatment."""
    select, coordinator = _cartridge_type_select(hass, status)

    await select.async_select_option(option)

    coordinator.async_set_device_values.assert_awaited_once_with("device1", expected)


@pytest.mark.parametrize(
    ("status", "option", "translation_key"),
    [
        pytest.param({"getCRT": ""}, "none", "option_not_selectable", id="none"),
        pytest.param({"getCRT": "1"}, "3", "invalid_option", id="unknown-option"),
    ],
)
async def test_muco_filling_cartridge_type_rejects_option(
    hass: HomeAssistant, status: dict[str, Any], option: str, translation_key: str
) -> None:
    """Without getWTR "none" cannot be selected; an unknown option is rejected."""
    select, coordinator = _cartridge_type_select(hass, status)

    with pytest.raises(ServiceValidationError) as exc_info:
        await select.async_select_option(option)

    assert exc_info.value.translation_key == translation_key
    coordinator.async_set_device_values.assert_not_called()


async def test_muco_filling_cartridge_type_write_failure(hass: HomeAssistant) -> None:
    """A failed request raises the translated error."""
    select, coordinator = _cartridge_type_select(hass, {"getCRT": "1", "getWTR": False})
    coordinator.async_set_device_values.side_effect = SyrConnectConnectionError("boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await select.async_select_option("1")

    assert exc_info.value.translation_key == "set_value_failed"


async def test_muco_filling_no_cartridge_selects_while_water_treatment_off(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """While the water treatment is off, neither getOHW nor getLOT becomes a select."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "model": _SYR_CONNECT_TEST_MUCO_FILLING_MODEL,
                "status": {
                    "getCRT": "0",
                    "getWTR": False,
                    "getOHW": "3",
                    "getLOT": "7",
                    "getWHU": "0",
                },
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert "getCRT" in keys
    assert keys.isdisjoint({"getOHW", "getLOT"})


async def test_muco_filling_initial_filling_duration_steps(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """The MuCo filling has its own steps for the maximum duration of the initial filling."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "model": _SYR_CONNECT_TEST_MUCO_FILLING_MODEL,
                "status": {"getFMT": "30"},
            }
        ]
    }
    mock_config_entry, coordinator = create_mock_entry_with_coordinator(data)
    coordinator.async_set_device_value = AsyncMock()
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    [select] = [e for e in entities if getattr(e, "_sensor_key", None) == "getFMT"]
    # 1-5, 10, 15, 30 and 45 minutes, then 1-25 hours in steps of 30 minutes
    assert select.options == [
        f"{minutes} min"
        for minutes in (1, 2, 3, 4, 5, 10, 15, 30, 45, *range(60, 1501, 30))
    ]
    assert select.current_option == "30 min"

    await select.async_select_option("1 min")

    coordinator.async_set_device_value.assert_called_once_with("device1", "setFMT", 1)


@pytest.mark.parametrize(
    ("status", "translation_key"),
    [
        pytest.param(
            {"getDFI": True, "getSTA": 0},
            "filling_blocked_by_filling_mode",
            id="filling-mode-on",
        ),
        pytest.param(
            {"getDFI": False, "getSTA": 2},
            "filling_requires_standby",
            id="not-standby",
        ),
        pytest.param({"getDFI": False, "getSTA": 0}, None, id="allowed"),
    ],
)
async def test_muco_filling_initial_filling_switch(
    create_mock_coordinator: Callable[..., MagicMock],
    status: dict[str, Any],
    translation_key: str | None,
) -> None:
    """The initial filling starts only while the filling mode is off and in standby."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "model": _SYR_CONNECT_TEST_MUCO_FILLING_MODEL,
                "status": {"getIFL": False, **status},
            }
        ]
    }
    coordinator = create_mock_coordinator(data)
    switch = switch_module.SyrConnectBooleanSwitch(
        coordinator, "device1", "Device 1", "getIFL"
    )

    if translation_key is None:
        await switch.async_turn_on()
        coordinator.async_set_device_value.assert_awaited_once_with(
            "device1", "setIFL", True
        )
        return
    with pytest.raises(ServiceValidationError) as exc_info:
        await switch.async_turn_on()
    assert exc_info.value.translation_key == translation_key
    coordinator.async_set_device_value.assert_not_awaited()
