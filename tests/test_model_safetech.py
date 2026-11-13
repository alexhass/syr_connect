"""Tests for the entities of the SafeTech family."""

# The tests check private attributes of the entities.
# ruff: noqa: SLF001

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from custom_components.syr_connect import sensor as sensor_module
from custom_components.syr_connect.const import CONF_SERVICE
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.helpers import get_sensor_ala_map
from custom_components.syr_connect.models import (
    MODEL_SIGNATURES,
    UNKNOWN_MODEL,
    SyrConnectModel,
    detect_model,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant


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


def _signature(name: str) -> SyrConnectModel:
    """Return the model signature with the given name."""
    return next(model for model in MODEL_SIGNATURES if model.name == name)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("A2", "alarm_no_network_connection"),
        ("AC", "alarm_conductivity_too_high"),
        ("AD", "alarm_battery_low"),
        ("AE", "alarm_leakage_volume_approaching"),
        ("AF", "alarm_no_power_supply"),
        ("FF", "no_alarm"),
    ],
)
@pytest.mark.parametrize(
    ("version", "name"),
    [
        ("Safe-Tech V4.08", "safetechv4"),
        ("PontosBase V1.31", "pontosbase"),
    ],
)
def test_sensor_ala_map_safetech(
    version: str, name: str, raw: str, expected: str
) -> None:
    """SafeTech alarm codes that differ from the generic codes use their own meaning."""
    model = detect_model({"getVER": version})

    assert model.name == name
    assert get_sensor_ala_map(model, raw) == (expected, raw)


@pytest.mark.parametrize(
    ("model", "cnd", "created"),
    [
        # Only the SafeTech family gets the water hardness range
        ("safetech", "384", True),
        ("safetechplus", 245, True),
        ("safetechplus", "", False),
        ("lexplus10sl", "250", False),
        ("unknown", "250", False),
    ],
)
def test_sensor_cnd_class_created_for_safetech_family(
    hass: HomeAssistant, model: str, cnd: Any, created: bool
) -> None:
    """The computed water hardness range is a sensor of the SafeTech profiles only."""
    signature = UNKNOWN_MODEL if model == "unknown" else _signature(model)
    status = {"getCND": cnd}
    device = {"id": "d1", "name": "D1", "model": signature, "status": status}
    coordinator = _build_coordinator(hass, {"devices": [device]})

    keys = sensor_module.sensor_keys_for_status(status, signature)
    entities = sensor_module._build_device_sensors(hass, coordinator, cast(Any, device))
    entity_keys = {getattr(entity, "_sensor_key", None) for entity in entities}

    assert ("getCND_class" in keys) is created
    assert ("getCND_class" in entity_keys) is created
