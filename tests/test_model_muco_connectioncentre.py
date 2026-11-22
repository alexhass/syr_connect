"""Tests for the entities of the MultiController connection centre."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect import (
    select as select_module,
    sensor as sensor_module,
    switch as switch_module,
)
from custom_components.syr_connect.aiosyrconnect import SyrConnectStatus
from custom_components.syr_connect.models import MODELS, SyrConnectModel
from custom_components.syr_connect.select import SyrConnectRotationSelect
from homeassistant.core import HomeAssistant

# The connection centre (getDFM 2) of every MultiController brand
_SYR_CONNECT_TEST_CONNECTION_CENTRES = [
    "conelclearproconnectioncentre",
    "sanibelconnectioncentre",
    "ditechconnectioncentre",
    "takeconnectioncentre",
    "conceptconnectioncentre",
    "optimaconnectioncentre",
    "syrac3200connect",
]

# Water treatment and filling of a connection centre with an HWE cartridge
_SYR_CONNECT_TEST_STATUS: SyrConnectStatus = {
    "getBAR": "1500",
    "getCRS": "3",
    "getCRT": "0",
    "getCWL": "10",
    "getDFI": "True",
    "getFMT": "30",
    "getFVT": "100",
    "getIFL": "False",
    "getIWH": "18",
    "getOHW": "5",
    "getRCD": "1",
    "getRMN": "5",
    "getRMT": "30",
    "getRVT": "100",
    "getSRO": "0",
    "getTPR": "18",
    "getWHU": "0",
    "getWTR": "True",
}


def _model(name: str) -> SyrConnectModel:
    """Return the model with the given name."""
    return next(model for model in MODELS if model.name == name)


def _data(name: str) -> dict[str, Any]:
    """Return the coordinator data of one connection centre of the model."""
    return {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "model": _model(name),
                "status": dict(_SYR_CONNECT_TEST_STATUS),
            }
        ]
    }


@pytest.mark.parametrize("name", _SYR_CONNECT_TEST_CONNECTION_CENTRES)
async def test_connection_centre_water_treatment_and_filling_selects(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    name: str,
) -> None:
    """The connection centre offers the water treatment and filling settings."""
    mock_config_entry, _ = create_mock_entry_with_coordinator(_data(name))
    entities, async_add_entities = mock_add_entities()

    await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    # The display rotation (getSRO) has no _sensor_key
    assert any(isinstance(e, SyrConnectRotationSelect) for e in entities)
    selects = {
        e._sensor_key: e  # noqa: SLF001
        for e in entities
        if not isinstance(e, SyrConnectRotationSelect)
    }
    assert set(selects) == {
        "getCRS",
        "getCRT",
        "getCWL",
        "getFMT",
        "getFVT",
        "getIWH",
        "getOHW",
        "getRCD",
        "getRMN",
        "getRMT",
        "getRVT",
        "getTPR",
    }
    # The hardness is kept in °dH, the initial filling has the steps of the MuCo
    assert selects["getIWH"].options[-1] == "50 °dH"
    assert selects["getOHW"].current_option == "5 °dH"
    assert selects["getFMT"].options[:5] == [
        "1 min",
        "2 min",
        "3 min",
        "4 min",
        "5 min",
    ]


@pytest.mark.parametrize("name", _SYR_CONNECT_TEST_CONNECTION_CENTRES)
async def test_connection_centre_filling_switches(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    name: str,
) -> None:
    """The connection centre switches the filling mode and the initial filling."""
    mock_config_entry, _ = create_mock_entry_with_coordinator(_data(name))
    entities, async_add_entities = mock_add_entities()

    await switch_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert {"getDFI", "getIFL"} <= keys


def test_connection_centre_has_no_inlet_pressure() -> None:
    """The connection centre has no getBAR (validity matrix), but its filling values."""
    model = _model("syrac3200connect")

    keys = set(sensor_module.sensor_keys_for_status(_SYR_CONNECT_TEST_STATUS, model))

    assert "getBAR" not in keys
    assert {"getCWL", "getFMT", "getFVT", "getOHW", "getTPR"} <= keys
