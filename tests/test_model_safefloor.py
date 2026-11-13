"""Tests for the entities of the SafeFloor."""

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import MagicMock, Mock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.syr_connect import select as select_module
from custom_components.syr_connect.const import CONF_SERVICE
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.helpers import get_sensor_ala_map
from custom_components.syr_connect.models import MODEL_SIGNATURES, SyrConnectModel
from custom_components.syr_connect.sensor import SyrConnectSensor
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfRatio
from homeassistant.core import HomeAssistant


def _signature(name: str) -> SyrConnectModel:
    """Return the model signature with the given name."""
    return next(signature for signature in MODEL_SIGNATURES if signature.name == name)


_SAFEFLOOR_STATUS = {
    "getVER": "Syr Floorsensor 2.23",
    "getALD": "20",
    "getMIH": "0",
    "getMXH": "100",
    "getMIT": "0",
    "getMXT": "500",
    "getRCP": "43200",
    "getWMP": "3600",
}


def _build_coordinator(
    hass: HomeAssistant, data: dict
) -> SyrConnectDataUpdateCoordinator:
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


def test_get_sensor_ala_map_safefloor_known_codes() -> None:
    """SafeFloor model maps its alarm codes correctly."""
    model = _signature("safefloor")
    mapped, raw = get_sensor_ala_map(model, "A0X0000")
    assert mapped == "no_alarm" and raw == "A0X0000"

    mapped, raw = get_sensor_ala_map(model, "A0X0004")
    assert mapped == "alarm_safefloor_flood" and raw == "A0X0004"

    # Bit 8 is the low battery alarm
    mapped, raw = get_sensor_ala_map(model, "A0x0100")
    assert mapped == "alarm_battery_low" and raw == "A0x0100"


async def test_async_setup_entry_creates_safefloor_threshold_selects(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """async_setup_entry creates all 7 SafeFloor threshold/interval selects when present in status."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": dict(_SAFEFLOOR_STATUS),
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert {
        "getALD",
        "getMIH",
        "getMXH",
        "getMIT",
        "getMXT",
        "getRCP",
        "getWMP",
    } <= keys


async def test_async_setup_entry_skips_invalid_safefloor_threshold_values(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """Non-numeric/empty SafeFloor threshold values must not create select entities."""
    status = {key: "" for key in _SAFEFLOOR_STATUS if key != "getVER"}
    status["getVER"] = _SAFEFLOOR_STATUS["getVER"]
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

    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert not (
        {"getALD", "getMIH", "getMXH", "getMIT", "getMXT", "getRCP", "getWMP"} & keys
    )


async def test_async_setup_entry_skips_non_numeric_safefloor_threshold_values(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """Garbage (non-numeric) SafeFloor threshold values must not create select entities."""
    status = {key: "n/a" for key in _SAFEFLOOR_STATUS if key != "getVER"}
    status["getVER"] = _SAFEFLOOR_STATUS["getVER"]
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

    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert not (
        {"getALD", "getMIH", "getMXH", "getMIT", "getMXT", "getRCP", "getWMP"} & keys
    )


@pytest.mark.parametrize(
    ("sensor_key", "raw_value", "expected_value"),
    [
        ("getALD", "20", 20),  # Alarm duration (s) — whole number
        ("getMIH", "5", 5),  # Minimum humidity (%) — whole number
        ("getMXH", "95", 95),  # Maximum humidity (%) — whole number
        ("getRCP", "43200", 43200),  # Synchronization interval (s) — whole number
        ("getWMP", "3600", 3600),  # Measurement interval (s) — whole number
    ],
)
async def test_sensor_safefloor_config_sensors(
    hass: HomeAssistant, sensor_key: str, raw_value: str, expected_value: int
) -> None:
    """Test SafeFloor config/threshold sensors return correct integer values."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {sensor_key: raw_value},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", sensor_key)
    assert sensor.native_value == expected_value


async def test_sensor_getbat_safefloor_percentage(hass: HomeAssistant) -> None:
    """SafeFloor (TYP=120) reports getBAT as integer percentage."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": "40",
                    "getTYP": "120",
                    "getVER": "Syr Floorsensor 2.23",  # SafeFloor
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    bat = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert bat.native_value == 40
    assert bat.native_unit_of_measurement == UnitOfRatio.PERCENTAGE
    assert bat.device_class == SensorDeviceClass.BATTERY
    assert bat.suggested_display_precision == 0
    # The name follows the unit ("Battery level"), the unique_id stays getBAT
    assert bat.translation_key == "getbap"
    assert bat.unique_id == "device1_getBAT"


async def test_sensor_getbat_safefloor_invalid_percentage(hass: HomeAssistant) -> None:
    """SafeFloor getBAT with an unparsable value returns None (covers except branch)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": "not_a_number",
                    "getTYP": "120",
                    "getVER": "Syr Floorsensor 2.23",  # SafeFloor -> percentage unit
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    bat = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert bat.native_unit_of_measurement == UnitOfRatio.PERCENTAGE
    assert bat.native_value is None


async def test_sensor_getbat_safefloor_icon_levels(hass: HomeAssistant) -> None:
    """In percentage mode device_class=BATTERY is set; icon is None so HA handles it automatically."""

    base_data: dict[str, Any] = {
        "id": "device1",
        "name": "Device 1",
        "project_id": "project1",
        "status": {"getTYP": "120", "getVER": "Syr Floorsensor 2.23"},
    }
    for bat_pct in ["95", "85", "75", "65", "55", "45", "35", "25", "15", "5", "0"]:
        data = {
            "devices": [
                {**base_data, "status": {**base_data["status"], "getBAT": bat_pct}}
            ]
        }
        coordinator = _build_coordinator(hass, data)
        bat = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")
        assert bat.device_class == SensorDeviceClass.BATTERY
        assert bat.icon is None, (
            f"Expected None for {bat_pct}% — HA renders icons via device_class"
        )
