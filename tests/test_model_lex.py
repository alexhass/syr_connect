"""Tests for the entities of the LEX family."""

# The tests check private attributes of the entities.
# ruff: noqa: SLF001

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect import (
    select as select_module,
    sensor as sensor_module,
)
from custom_components.syr_connect.aiosyrconnect.xml_parser import ResponseParser
from custom_components.syr_connect.button import SyrConnectButton
from custom_components.syr_connect.models import MODELS, SyrConnectModel, detect_model
from custom_components.syr_connect.select import SyrConnectHardnessSelect
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError


def _signature(name: str) -> SyrConnectModel:
    """Return the model signature with the given name."""
    return next(signature for signature in MODELS if signature.name == name)


@pytest.mark.parametrize("name", ["l10", "lex100", "lexplus10", "lexplus10s"])
def test_alarm_meaning_lex_short_table(name: str) -> None:
    """i-LEX, LEX Plus 10 and LEX Plus 10 S know only the alarm codes 1-5."""
    model = _signature(name)
    assert model.alarm_meaning("LowSalt") == "alarm_salt_supply_low"
    assert model.alarm_meaning("NoSalt") == "alarm_salt_supply_empty"
    assert model.alarm_meaning("1") == "alarm_salt_supply_empty"
    assert model.alarm_meaning("2") == "alarm_pressure_too_low"
    assert model.alarm_meaning("3") == "alarm_pressure_too_high"
    assert model.alarm_meaning("4") == "alarm_pressure_sensor_faulty"
    assert model.alarm_meaning("5") == "alarm_valve_malfunction"
    assert model.alarm_meaning("6") is None
    assert model.alarm_meaning("23") is None


def test_alarm_meaning_lex_full_table() -> None:
    """The LEX Plus 10 SL knows the full LEX alarm code table."""
    model = _signature("lexplus10sl")
    assert model.alarm_meaning("LowSalt") == "alarm_salt_supply_low"
    assert model.alarm_meaning("NoSalt") == "alarm_salt_supply_empty"
    assert model.alarm_meaning("1") == "alarm_salt_supply_empty"
    assert model.alarm_meaning("2") == "alarm_chlor_generator_fault"
    assert model.alarm_meaning("3") == "alarm_valve_malfunction"
    assert model.alarm_meaning("4") == "alarm_pressure_too_low"
    assert model.alarm_meaning("5") == "alarm_pressure_too_high"
    assert model.alarm_meaning("6") == "alarm_brine_level_low"
    assert model.alarm_meaning("19") == "alarm_pressure_sensor_faulty"
    assert model.alarm_meaning("23") == "alarm_leakage_volume_approaching"


async def test_async_setup_entry_creates_hardness_selects_for_lex(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """The plain LEX family (here i-LEX 10) gets raw/outlet water hardness selects."""
    status = {"getCNA": "L10", "getIWH": "20", "getOWH": "2", "getWHU": "0"}
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

    await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    by_key = {
        e._sensor_key: e
        for e in entities
        if getattr(e, "_sensor_key", None) in ("getIWH", "getOWH")
    }
    assert set(by_key) == {"getIWH", "getOWH"}
    assert all(isinstance(e, SyrConnectHardnessSelect) for e in by_key.values())
    assert by_key["getIWH"].options[0] == "1 °dH"
    assert by_key["getIWH"].options[-1] == "100 °dH"
    assert by_key["getOWH"].options[0] == "0 °dH"
    assert by_key["getOWH"].options[-1] == "100 °dH"
    assert by_key["getIWH"].current_option == "20 °dH"
    assert by_key["getOWH"].current_option == "2 °dH"


@pytest.mark.parametrize(
    "cna",
    [
        "LEXplus10",
        "LEXplus10S",
        "LEXplus10SL",
    ],
)
async def test_async_setup_entry_creates_hardness_selects_for_lex_plus(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    cna: str,
) -> None:
    """LEX Plus models also get raw/outlet water hardness selects."""
    status = {"getCNA": cna, "getIWH": "20", "getOWH": "2", "getWHU": "0"}
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

    await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    hardness = {
        e._sensor_key for e in entities if isinstance(e, SyrConnectHardnessSelect)
    }
    assert hardness == {"getIWH", "getOWH"}


@pytest.mark.parametrize("model", ["SyrLEXplus10S", "SyrLEXplus10SL"])
def test_lexplus_has_only_one_tank(model: str) -> None:
    """LEXplus 10 S/SL have one tank: no sensors for tank 2 and 3, even if reported."""
    xml = (
        Path(__file__).parent / f"fixtures/xml/{model}_GetDeviceCollectionStatus.xml"
    ).read_text(encoding="utf-8")
    status = ResponseParser().parse_device_status_response(xml)
    assert status is not None

    keys = set(sensor_module.sensor_keys_for_status(status, detect_model(status)))

    assert {"getCS1", "getSS1", "getSV1"} <= keys
    assert not keys & {"getCS2", "getCS3", "getSS2", "getSS3", "getSV2", "getSV3"}


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("SyrLEX30", set()),
        ("SyrLEXplus10S", set()),
        # Leakage detection only on the 10 SL; the fixture reports getVS1 only
        ("SyrLEXplus10SL", {"getVS1"}),
    ],
)
def test_lex_volume_thresholds(model: str, expected: set[str]) -> None:
    """Volume thresholds (getVS1-3) are a leakage detection feature: only LEXplus 10 SL."""
    xml = (
        Path(__file__).parent / f"fixtures/xml/{model}_GetDeviceCollectionStatus.xml"
    ).read_text(encoding="utf-8")
    status = ResponseParser().parse_device_status_response(xml)
    assert status is not None

    keys = set(sensor_module.sensor_keys_for_status(status, detect_model(status)))

    assert keys & {"getVS1", "getVS2", "getVS3"} == expected


def _lex_button(
    create_mock_coordinator: Callable[..., MagicMock], status: dict[str, Any]
) -> tuple[SyrConnectButton, MagicMock]:
    """Return the manual regeneration button of a LEX Plus 10 S and its coordinator."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "model": next(model for model in MODELS if model.name == "lexplus10s"),
                "status": status,
            }
        ]
    }
    coordinator = create_mock_coordinator(data)
    return SyrConnectButton(coordinator, "device1", "Device 1", "setSIR"), coordinator


async def test_lex_regeneration_button_sends_setsir(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The LEX starts a regeneration with setSIR, also with the cloud."""
    button, coordinator = _lex_button(
        create_mock_coordinator,
        {"getRG1": "0", "getRG2": "0", "getRG3": "0", "getSIR": "1"},
    )

    await button.async_press()

    coordinator.async_set_device_value.assert_awaited_once_with("device1", "setSIR", 0)


async def test_lex_regeneration_button_refused_while_a_tank_regenerates(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """No regeneration is started while one of the tanks regenerates (getRG1-3)."""
    button, coordinator = _lex_button(
        create_mock_coordinator,
        {"getRG1": "0", "getRG2": "1", "getRG3": "0", "getSIR": "1"},
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await button.async_press()

    assert exc_info.value.translation_key == "regeneration_running"
    coordinator.async_set_device_value.assert_not_awaited()
