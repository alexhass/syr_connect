"""Tests for sensor platform."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect import sensor as sensor_module
from custom_components.syr_connect.const import CONF_SERVICE, DOMAIN
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.devices import SyrConnectDeviceProfile
from custom_components.syr_connect.models import (
    MODEL_SIGNATURES,
    UNKNOWN_MODEL,
    SyrConnectModel,
    detect_model,
)
from custom_components.syr_connect.response_parser import ResponseParser
from custom_components.syr_connect.sensor import (
    _SYR_CONNECT_SENSOR_DESCRIPTIONS,
    _SYR_CONNECT_SENSOR_PROFILE_ONLY_KEYS,
    _SYR_CONNECT_SENSOR_SUPPORTED_KEYS,
    _SYR_CONNECT_SENSOR_TYPES,
    SyrConnectConnectionStateSensor,
    SyrConnectSensor,
    async_setup_entry,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    UnitOfConductivity,
    UnitOfElectricPotential,
    UnitOfRatio,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory


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


def _build_entry(coordinator: SyrConnectDataUpdateCoordinator) -> MockConfigEntry:
    entry = MockConfigEntry(domain="syr_connect", data={})
    entry.runtime_data = coordinator
    return entry


def test_sensor_descriptions_have_unique_keys() -> None:
    """Every key is described once; a duplicate would silently replace the first one."""
    keys = [description.key for description in _SYR_CONNECT_SENSOR_TYPES]
    assert len(keys) == len(set(keys))
    assert (
        set(keys)
        == _SYR_CONNECT_SENSOR_SUPPORTED_KEYS | _SYR_CONNECT_SENSOR_PROFILE_ONLY_KEYS
    )
    assert (
        not _SYR_CONNECT_SENSOR_SUPPORTED_KEYS & _SYR_CONNECT_SENSOR_PROFILE_ONLY_KEYS
    )


def test_sensor_descriptions_keep_as_string_without_value_fn() -> None:
    """keep_as_string has no effect next to a value_fn, so the two are never combined."""
    combined = [
        d.key for d in _SYR_CONNECT_SENSOR_TYPES if d.keep_as_string and d.value_fn
    ]
    assert combined == []


def test_filling_status_sensor_metadata() -> None:
    """CFT and CFV expose their documented units as measurements."""
    assert {"getCFT", "getCFV"} <= _SYR_CONNECT_SENSOR_SUPPORTED_KEYS
    cft = _SYR_CONNECT_SENSOR_DESCRIPTIONS["getCFT"]
    cfv = _SYR_CONNECT_SENSOR_DESCRIPTIONS["getCFV"]
    assert cft.native_unit_of_measurement == UnitOfTime.SECONDS
    assert cfv.native_unit_of_measurement == UnitOfVolume.LITERS
    assert cft.state_class == "measurement"
    assert cfv.state_class == "measurement"


@pytest.mark.parametrize(
    "fixture",
    [
        "SyrSafeFloor_GetDeviceCollectionStatus.xml",
        "SyrSafeTPlus_GetDeviceCollectionStatus.xml",
        "SyrSafeTechV4_GetDeviceCollectionStatus.xml",
    ],
)
async def test_getcno_registration_code_is_not_exposed(
    hass: HomeAssistant, fixture: str
) -> None:
    """The getCNO is printed on the device label and registers the device to an account: never a sensor."""
    xml = (Path(__file__).parent / "fixtures/xml" / fixture).read_text(encoding="utf-8")
    status = ResponseParser().parse_device_status_response(xml)
    assert status is not None
    assert "getCNO" in status
    coordinator = _build_coordinator(
        hass,
        {
            "devices": [
                {
                    "id": "device1",
                    "name": "Device 1",
                    "project_id": "p1",
                    "status": status,
                }
            ]
        },
    )
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)
    added: list = []

    await async_setup_entry(hass, entry, lambda ents: added.extend(ents))  # type: ignore[arg-type]

    assert added  # the device gets its other sensors
    assert not [e for e in added if getattr(e, "_sensor_key", None) == "getCNO"]


def _added_entities(add_entities: Mock) -> list[Any]:
    """Return every entity passed to a mocked async_add_entities (none if not called)."""
    return [entity for call in add_entities.call_args_list for entity in call.args[0]]


async def test_sensor_setup(hass: HomeAssistant) -> None:
    """Test sensor platform setup."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": "50",
                    "getFLO": "10",
                    "getCEL": "220",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 3


@pytest.mark.parametrize(
    ("sensor_key", "raw_value", "expected_value"),
    [
        ("getPRS", "50", 5.0),
        ("getDBD", "10", 1.0),
        ("getCEL", "220", 22.0),
        ("getMIT", "-40", -4.0),
        ("getMIT", "490", 49.0),
        ("getMXT", "490", 49.0),
        ("getMXT", "-30", -3.0),
        ("getFLO", "100", 100),
    ],
)
async def test_sensor_native_value_numeric(
    hass: HomeAssistant, sensor_key: str, raw_value: str, expected_value: float
) -> None:
    """Test sensor native value for numeric sensors."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    sensor_key: raw_value,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", sensor_key)

    assert sensor.native_value == expected_value


@pytest.mark.parametrize(
    ("raw", "expected_utc"),
    [
        # Summer time (CEST, UTC+2): the device reports 01:16 local time
        ("1792718160", datetime(2026, 10, 22, 23, 16, tzinfo=UTC)),
        # Winter time (CET, UTC+1): the device reports 00:00 local time
        ("1704067200", datetime(2023, 12, 31, 23, 0, tzinfo=UTC)),
    ],
)
async def test_sensor_native_value_timestamp_is_local_time(
    hass: HomeAssistant, raw: str, expected_utc: datetime
) -> None:
    """Test getLAR without a UTC offset (local JSON API) uses the Home Assistant time zone."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getLAR": raw,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getLAR")

    value = sensor.native_value
    assert isinstance(value, datetime)
    assert value == expected_utc


@pytest.mark.parametrize(
    ("utc_offset", "expected_utc"),
    [
        # Summer time: the cloud reports tzo="02:00:00"
        (7200, datetime(2026, 10, 22, 23, 16, tzinfo=UTC)),
        # Winter time: the cloud reports tzo="01:00:00"
        (3600, datetime(2026, 10, 23, 0, 16, tzinfo=UTC)),
    ],
)
async def test_sensor_native_value_timestamp_uses_cloud_utc_offset(
    hass: HomeAssistant, utc_offset: int, expected_utc: datetime
) -> None:
    """Test getLAR uses the UTC offset (tzo) of the project, not the Home Assistant time zone."""
    await hass.config.async_set_time_zone("America/New_York")
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "utc_offset": utc_offset,
                "status": {
                    "getLAR": "1792718160",  # 23 October 2026 01:16 local time
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getLAR")

    assert sensor.native_value == expected_utc


async def test_sensor_native_value_string(hass: HomeAssistant) -> None:
    """Test sensor native value for string sensors."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSRN": "123456789",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getSRN")

    assert sensor.native_value == "123456789"


@pytest.mark.parametrize(
    ("available", "last_success", "expected"),
    [
        (True, True, True),
        (False, False, False),
        (True, False, False),
    ],
)
async def test_sensor_availability(
    hass: HomeAssistant, available: bool, last_success: bool, expected: bool
) -> None:
    """Test sensor availability."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": available,
                "status": {
                    "getPRS": "50",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.last_update_success = last_success
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    assert sensor.available is expected


async def test_sensor_regeneration_time(hass: HomeAssistant) -> None:
    """Test combined regeneration time sensor (getRTH and getRTM)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRTH": "2",
                    "getRTM": "30",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRTM")

    assert sensor.native_value == "02:30"


def _signature(name: str) -> SyrConnectModel:
    """Return the model signature with the given name."""
    return next(model for model in MODEL_SIGNATURES if model.name == name)


@pytest.mark.parametrize(
    ("model", "whu", "unit"),
    [
        # LEX family
        ("lex30", "0", "°dH"),
        ("lex30", 1, "°fH"),
        ("lex30", "2", "°e"),
        ("lex30", 3.0, "mg/l CaCO₃"),
        ("lex30", "4", "ppm"),
        ("lex30", "5", "mmol/l"),
        ("lex30", "6", "mval/l"),
        # MultiController and All-in-One+
        ("conelclearprofill", "0", "°dH"),
        ("conelclearprofill", "1", "°e"),
        ("conelclearprofill", "2", "°fH"),
        ("allinoneplus", "3", "ppm"),
        # NeoSoft family
        ("neosoft2500", "0", "°dH"),
        ("neosoft2500", "1", "mmol/l"),
        ("neosoft2500", "2", "°fH"),
        # Unknown or invalid code of the family
        ("neosoft2500", "3", None),
        ("lex30", "invalid", None),
        # A model without water hardness unit codes has no unit
        ("safetechplus", "0", None),
    ],
)
def test_sensor_whu_follows_model_family(
    create_mock_coordinator: Callable[..., MagicMock],
    model: str,
    whu: Any,
    unit: str | None,
) -> None:
    """The water hardness unit (getWHU) and the hardness sensors use the codes of the family."""
    status = {"getIWH": "10", "getWHU": whu}
    data = {
        "devices": [
            {"id": "d1", "name": "D1", "model": _signature(model), "status": status}
        ]
    }
    coordinator = create_mock_coordinator(data)

    whu_sensor = SyrConnectSensor(coordinator, "d1", "D1", "getWHU")
    iwh_sensor = SyrConnectSensor(coordinator, "d1", "D1", "getIWH")

    assert whu_sensor.native_value == unit
    assert iwh_sensor.native_unit_of_measurement == unit


@pytest.mark.parametrize(
    ("cnd", "expected"),
    [
        # getCND / 35 = water hardness in °dH
        ("245", "soft"),
        (280, "soft"),
        ("281", "medium"),
        ("384", "medium"),
        (490, "medium"),
        ("491", "hard"),
        ("608", "hard"),
        ("", None),
        (None, None),
        ("invalid", None),
    ],
)
def test_sensor_cnd_class_from_conductivity(
    create_mock_coordinator: Callable[..., MagicMock], cnd: Any, expected: str | None
) -> None:
    """The water hardness range is soft up to 8 °dH, medium up to 14 °dH, else hard."""
    data = {
        "devices": [
            {
                "id": "d1",
                "name": "D1",
                "model": _signature("safetechplus"),
                "status": {"getCND": cnd},
            }
        ]
    }
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getCND_class")

    assert sensor.native_value == expected
    assert sensor.options == ["soft", "medium", "hard"]


@pytest.mark.parametrize(
    ("model", "whu", "raw", "expected", "precision"),
    [
        # The NeoSoft family reports mmol/l in tenths
        ("neosoft2500", "1", "15", 1.5, 1),
        ("neosoft2500", 1, 4, 0.4, 1),
        # Other units of the family and other families are unscaled
        ("neosoft2500", "0", "15", 15, 0),
        ("neosoft2500", "2", "27", 27, 0),
        ("lex30", "5", "3", 3, 0),
        ("neosoft2500", "invalid", "15", 15, 0),
    ],
)
@pytest.mark.parametrize("key", ["getIWH", "getOWH"])
def test_sensor_hardness_scale_follows_whu(
    create_mock_coordinator: Callable[..., MagicMock],
    key: str,
    model: str,
    whu: Any,
    raw: Any,
    expected: float,
    precision: int,
) -> None:
    """The hardness sensors divide by the scale of the family's unit (getWHU)."""
    status = {key: raw, "getWHU": whu}
    data = {
        "devices": [
            {"id": "d1", "name": "D1", "model": _signature(model), "status": status}
        ]
    }
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", key)

    assert sensor.native_value == expected
    assert sensor.suggested_display_precision == precision


async def test_sensor_status_mapping(hass: HomeAssistant) -> None:
    """Test status sensor mapping (getSTA)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "Płukanie regenerantem (587mA)",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getSTA")

    # Should return mapped translation key
    assert sensor.native_value == "status_regenerant_rinse"


async def test_sensor_status_fast_rinse(hass: HomeAssistant) -> None:
    """Test status sensor for fast rinse (getSTA)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "Płukanie szybkie 1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getSTA")

    assert sensor.native_value == "status_fast_rinse"


async def test_sensor_status_refill_salt(hass: HomeAssistant) -> None:
    """Test status sensor for the German refill salt message (getSTA)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "Bitte Salz nachfüllen",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getSTA")

    assert sensor.native_value == "status_refill_salt"


async def test_sensor_alarm_mapping(hass: HomeAssistant) -> None:
    """Test alarm sensor mapping (getALM)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALM": "LowSalt",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getALM")

    assert sensor.native_value == "alarm_salt_supply_low"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # SafeTech V3/V4, Hansgrohe Pontos
        ("Alarms:->A4 A4 AF AF A3 AF A3 AF", "->A4 A4 AF AF A3 AF A3 AF"),
        # Safe-T+: the "->" before the current alarm stays where it is
        ("Alarms: A5 A5 A6 ->A6 A5 A5 A5 A5", "A5 A5 A6 ->A6 A5 A5 A5 A5"),
        # Without the prefix the value is shown unchanged
        ("A4 A4 AF", "A4 A4 AF"),
    ],
)
async def test_sensor_alarm_memory_without_prefix(
    hass: HomeAssistant, raw: str, expected: str
) -> None:
    """The alarm memory (getALM) is shown without its "Alarms:" prefix."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getALM": raw},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getALM")

    assert sensor.native_value == expected


async def test_sensor_cs_shown_when_zero(hass: HomeAssistant) -> None:
    """Test getCS1-3 are created at zero, with getCS2/3 disabled by default."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCS1": "0",
                    "getCS2": 0,
                    "getCS3": "0",
                    "getSV1": "0",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0]
    enabled = {
        e._sensor_key: e.entity_registry_enabled_default
        for e in entities
        if e._sensor_key in ("getCS1", "getCS2", "getCS3")
    }

    assert enabled == {
        "getCS1": True,
        "getCS2": False,
        "getCS3": False,
    }


async def test_sensor_lar_empty_value(hass: HomeAssistant) -> None:
    """Test getLAR with empty value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getLAR": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getLAR")

    assert sensor.native_value is None


async def test_sensor_lar_zero_value(hass: HomeAssistant) -> None:
    """Test getLAR 0 (no regeneration yet) is unknown, not 1970-01-01."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getLAR": "0",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getLAR")

    assert sensor.native_value is None


async def test_sensor_zero_values_created_and_kept(hass: HomeAssistant) -> None:
    """Test sensors reporting 0 are created and not removed by the registry cleanup."""
    status = {
        "getCND": "0",
        "getCYT": "0",
        "getLAR": "0",
        "getTYP": 0,
        "getVS1": 0.0,
        "getWFR": "0",
    }
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": status,
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    created = {e._sensor_key for e in add_entities.call_args.args[0]}
    assert set(status) <= created
    assert not set(status) & sensor_module._hidden_sensor_keys(status, UNKNOWN_MODEL)


async def test_sensor_registered_sensor_created_with_empty_value(
    hass: HomeAssistant,
) -> None:
    """Test a registered sensor is created and kept although its value is empty."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getTYP": "",  # hidden_when="empty"
                    "getWIP": "0.0.0.0",  # hidden_when="empty_ip"
                    "getDWF": "350",  # hidden_when="always"
                    "getCEL": {"nested": "dict"},  # Invalid type
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)
    coordinator.entry_id = entry.entry_id

    registry = er.async_get(hass)
    for key in ("getTYP", "getWIP", "getDWF", "getCEL"):
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{entry.entry_id}_device1_{key}",
            suggested_object_id=f"device1_{key.lower()}",
            config_entry=entry,
        )

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    created = {e._sensor_key for e in add_entities.call_args.args[0]}
    assert created == {"getTYP", "getWIP"}
    for key, kept in (("getTYP", True), ("getWIP", True), ("getDWF", False)):
        unique_id = f"{entry.entry_id}_device1_{key}"
        assert bool(registry.async_get_entity_id("sensor", DOMAIN, unique_id)) is kept


async def test_sensor_registered_always_hidden_not_created(
    hass: HomeAssistant,
) -> None:
    """Test a registered hidden_when="always" sensor is not created if the cleanup failed."""
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "device1_getDWF",
        suggested_object_id="device1_getdwf",
    )

    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getDWF": "350"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    with patch.object(sensor_module, "registry_cleanup"):
        await async_setup_entry(hass, entry, add_entities)

    created = {e._sensor_key for e in _added_entities(add_entities)}
    assert "getDWF" not in created


async def test_sensor_lar_invalid_timestamp(hass: HomeAssistant) -> None:
    """Test getLAR with invalid timestamp."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getLAR": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getLAR")

    assert sensor.native_value is None


async def test_sensor_rtime_invalid(hass: HomeAssistant) -> None:
    """Test getRTH with invalid values."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRTH": "invalid",
                    "getRTM": "30",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRTM")

    assert sensor.native_value is None


async def test_sensor_string_value_numeric(hass: HomeAssistant) -> None:
    """Test sensor with string value that can be converted to numeric."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": "123.45",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getFLO")

    # getFLO has precision 0, so 123.45 is rounded to 123 (int)
    assert sensor.native_value == 123


async def test_sensor_string_value_non_numeric(hass: HomeAssistant) -> None:
    """Test sensor with string value that cannot be converted."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": "not-a-number",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getFLO")

    # getFLO is a numeric sensor, so the text is no value
    assert sensor.native_value is None


async def test_sensor_setup_no_data(hass: HomeAssistant) -> None:
    """Test sensor setup with no coordinator data."""
    coordinator = _build_coordinator(hass, {})
    coordinator.data = None
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Should not call add_entities when no data
    add_entities.assert_not_called()


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, None),
        ("", None),
        ("abc", None),
        ("-5", -0.5),
    ],
)
async def test_getdbd_various_values(
    hass: HomeAssistant, raw_value: Any, expected: Any
) -> None:
    """Test `getDBD` handling for empty, invalid and negative values."""
    data = {
        "devices": [
            {
                "id": "dev_dbd",
                "name": "Device DBD",
                "project_id": "p1",
                "status": {"getDBD": raw_value},
            }
        ]
    }
    coord = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coord, "dev_dbd", "Device DBD", "getDBD")
    assert sensor.native_value == expected


# Additional tests merged from test_sensor_extra.py
def test_extra_getavo_and_getbar_and_getbat_and_getul(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Test extra getAVO and getBAR and getBAT and getUL."""
    data = {
        "devices": [
            {
                "id": "dev_s",
                "name": "Device S",
                "project_id": "p1",
                "status": {
                    "getAVO": "1655mL",
                    "getBAR": "4077 mbar",
                    "getBAT": "363",
                    "getUL": "5",
                },
            }
        ]
    }
    coord = create_mock_coordinator(data)

    avo = SyrConnectSensor(coord, "dev_s", "Device S", "getAVO")
    assert abs(float(cast(Any, avo.native_value)) - 1.655) < 0.001

    bar = SyrConnectSensor(coord, "dev_s", "Device S", "getBAR")
    # 4077 mbar -> 4.077 bar -> rounded to 1 decimal -> 4.1
    assert bar.native_value == 4.1

    bat = SyrConnectSensor(coord, "dev_s", "Device S", "getBAT")
    assert bat.native_value == 3.63

    ul = SyrConnectSensor(coord, "dev_s", "Device S", "getUL")
    assert ul.native_value == 50


def test_extra_getrtm_and_getab_icon_and_getpm_boolean(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Test extra getRTM and getAB icon and getPM boolean."""
    data = {
        "devices": [
            {
                "id": "dev_rt",
                "name": "Device RT",
                "project_id": "p1",
                "status": {
                    "getRTM": "07:15",
                    "getAB": "2",
                    "getPM1": "1",
                },
            }
        ]
    }
    coord = create_mock_coordinator(data)

    rtm = SyrConnectSensor(coord, "dev_rt", "Device RT", "getRTM")
    assert rtm.native_value == "07:15"

    ab = SyrConnectSensor(coord, "dev_rt", "Device RT", "getAB")
    # native_value returns 'true'/'false' strings
    assert ab.native_value == "true"

    pm1 = SyrConnectSensor(coord, "dev_rt", "Device RT", "getPM1")
    assert pm1.native_value == "true"


def test_extra_getwhu_and_getlar(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Test extra getWHU and getLAR."""
    # getWHU mapping, getLAR timestamp
    ts = 1609459200  # 2021-01-01 00:00:00 UTC
    data = {
        "devices": [
            {
                "id": "dev_w",
                "name": "Device W",
                "project_id": "p1",
                "model": _signature("lex30"),
                "status": {
                    "getWHU": 1,
                    "getLAR": str(ts),
                },
            }
        ]
    }
    coord = create_mock_coordinator(data)

    whu = SyrConnectSensor(coord, "dev_w", "Device W", "getWHU")
    assert whu.native_value == "°fH"

    lar = SyrConnectSensor(coord, "dev_w", "Device W", "getLAR")
    assert isinstance(lar.native_value, datetime)
    # Check timestamp matches (allow timezone differences by comparing UTC timestamp)
    assert int(lar.native_value.replace(tzinfo=UTC).timestamp()) == ts


def test_extra_getsta_getalm_getle_and_gett1_mappings(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Test extra getSTA getALM getLE and getT1 mappings."""
    data = {
        "devices": [
            {
                "id": "dev_map",
                "name": "Device Map",
                "project_id": "p1",
                "status": {
                    "getSTA": "Płukanie regenerantem (587mA)",
                    "getALM": "NoSalt",
                    "getLE": "2",
                    "getT1": "3",
                },
            }
        ]
    }
    coord = create_mock_coordinator(data)

    sta = SyrConnectSensor(coord, "dev_map", "Device Map", "getSTA")
    assert sta.native_value == "status_regenerant_rinse"
    assert (
        sta.translation_key == "getsta"
    )  # unchanged; the state is translated under it

    alm = SyrConnectSensor(coord, "dev_map", "Device Map", "getALM")
    assert alm.native_value == "alarm_salt_supply_empty"
    assert alm.translation_key == "getalm"

    le = SyrConnectSensor(coord, "dev_map", "Device Map", "getLE")
    assert le.native_value == 100

    t1 = SyrConnectSensor(coord, "dev_map", "Device Map", "getT1")
    assert t1.native_value == 1.5


def test_getlot_conversion(create_mock_coordinator: Callable[..., MagicMock]) -> None:
    """The getLOT is provided in steps of 10 µS/cm and must be multiplied by 10."""
    data = {
        "devices": [
            {
                "id": "dev_lot",
                "name": "Device LOT",
                "project_id": "p1",
                "status": {"getLOT": "7"},
            }
        ]
    }
    coord = create_mock_coordinator(data)

    lot = SyrConnectSensor(coord, "dev_lot", "Device LOT", "getLOT")
    assert lot.native_value == 70


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("2", 4),
        (None, None),
        ("", None),
        ("abc", None),
    ],
)
def test_getcrs_value_mapping(
    create_mock_coordinator: Callable[..., MagicMock], raw_value: Any, expected: Any
) -> None:
    """The getCRS maps raw cartridge size codes to liters, with None/empty/invalid handled."""
    data = {
        "devices": [
            {
                "id": "dev_crs",
                "name": "Device CRS",
                "project_id": "p1",
                "status": {"getCRS": raw_value},
            }
        ]
    }
    coord = create_mock_coordinator(data)

    crs = SyrConnectSensor(coord, "dev_crs", "Device CRS", "getCRS")
    assert crs.native_value == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("1", "1"),
        (None, "none"),
        ("", "none"),
    ],
)
def test_getcrt_value_mapping(
    create_mock_coordinator: Callable[..., MagicMock], raw_value: Any, expected: Any
) -> None:
    """The getCRT returns 'none' for missing/empty values, otherwise the raw value as string."""
    data = {
        "devices": [
            {
                "id": "dev_crt",
                "name": "Device CRT",
                "project_id": "p1",
                "status": {"getCRT": raw_value},
            }
        ]
    }
    coord = create_mock_coordinator(data)

    crt = SyrConnectSensor(coord, "dev_crt", "Device CRT", "getCRT")
    assert crt.native_value == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("1", "1"),
        (None, "undefined"),
        ("", "undefined"),
    ],
)
def test_getrcd_value_mapping(
    create_mock_coordinator: Callable[..., MagicMock], raw_value: Any, expected: Any
) -> None:
    """The getRCD returns 'undefined' for missing/empty values, otherwise the raw value as string."""
    data = {
        "devices": [
            {
                "id": "dev_rcd",
                "name": "Device RCD",
                "project_id": "p1",
                "status": {"getRCD": raw_value},
            }
        ]
    }
    coord = create_mock_coordinator(data)

    rcd = SyrConnectSensor(coord, "dev_rcd", "Device RCD", "getRCD")
    assert rcd.native_value == expected


async def test_getsro_and_getffm_creation_rules(hass: HomeAssistant) -> None:
    """Test that getSRO only created for integer values and getFFM >=1."""
    data = {
        "devices": [
            {
                "id": "d1",
                "name": "D1",
                "project_id": "p1",
                "status": {"getSRO": "12.3", "getFFM": "0.5"},
            },
            {
                "id": "d2",
                "name": "D2",
                "project_id": "p1",
                "status": {"getSRO": "12", "getFFM": "1"},
            },
        ]
    }
    coord = _build_coordinator(hass, data)
    entry = _build_entry(coord)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0]
    # d1 should not create getSRO/getFFM sensors, d2 should create two sensors
    d1 = [e for e in entities if e._device_id == "d1"]
    d2 = [e for e in entities if e._device_id == "d2"]
    assert all(e._sensor_key not in ("getSRO", "getFFM") for e in d1)
    assert any(e._sensor_key == "getSRO" for e in d2)
    assert any(e._sensor_key == "getFFM" for e in d2)


async def test_sensor_missing_device(hass: HomeAssistant) -> None:
    """Test sensor when device not in coordinator data."""
    data = {
        "devices": [
            {
                "id": "other_device",
                "name": "Other Device",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    assert sensor.native_value is None
    assert sensor.available is False  # Device removed from the account


async def test_sensor_entity_registry_cleanup(hass: HomeAssistant) -> None:
    """Test entity registry cleanup for excluded sensors."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getPRS": "50"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)
    coordinator.entry_id = entry.entry_id

    # getDTY is not in the sensor allowlist; getPRS is
    registry = er.async_get(hass)
    for key in ("getDTY", "getPRS"):
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{entry.entry_id}_device1_{key}",
            config_entry=entry,
        )

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    assert not registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_device1_getDTY"
    )
    assert registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_device1_getPRS"
    )


async def test_sensor_whu_invalid_value(hass: HomeAssistant) -> None:
    """Test getWHU sensor with invalid value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getWHU")

    # Should return None for invalid values
    assert sensor.native_value is None


async def test_sensor_alarm_none_value(hass: HomeAssistant) -> None:
    """Test getALM sensor with None value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALM": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getALM")

    # When getALM is None, it gets mapped via the alarm value map
    # str(None or "") = "" which maps to 'no_alarm'
    assert sensor.native_value == "no_alarm"


async def test_sensor_water_hardness_init_invalid_whu(hass: HomeAssistant) -> None:
    """Test sensor initialization with invalid getWHU value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getOWH": "15",
                    "getWHU": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getOWH")

    # Should fallback to None for invalid WHU
    assert sensor.native_unit_of_measurement is None


async def test_sensor_water_hardness_init_no_whu(hass: HomeAssistant) -> None:
    """Test sensor initialization when getWHU is not present."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getIWH": "10",
                    # No getWHU
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getIWH")

    # Should be None when WHU not present
    assert sensor.native_unit_of_measurement is None


async def test_sensor_getiwh_derived_from_getcnd(hass: HomeAssistant) -> None:
    """Test that `getIWH` is derived from `getCND` when explicit getIWH is missing."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCND": "350",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getIWH")

    # getIWH should be derived as getCND / 35 -> 10 (int)
    assert sensor.native_value == 10


async def test_sensor_numeric_int_value(hass: HomeAssistant) -> None:
    """Test sensor with integer value is converted correctly."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": 100,  # Integer instead of string
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getFLO")

    # Should convert int to float
    assert isinstance(sensor.native_value, int | float)
    assert sensor.native_value == 100


async def test_sensor_numeric_float_value(hass: HomeAssistant) -> None:
    """Test sensor with float value applies precision."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": 123.45,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getFLO")

    # getFLO has precision 0, so 123.45 should be rounded to 123
    assert sensor.native_value == 123

    # Sensor should be created when value is non-zero
    # Note: actual behavior depends on if getRS1 is in EXCLUDE_WHEN_ZERO const


async def test_sensor_cel_temperature_conversion(hass: HomeAssistant) -> None:
    """Test getCEL temperature conversion (divides by 10)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCEL": 110,  # 110 -> 11.0°C
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getCEL")

    # getCEL values are provided as 1/10 °C
    assert sensor.native_value == 11.0


async def test_sensor_prs_pressure_conversion(hass: HomeAssistant) -> None:
    """Test getPRS pressure conversion (divides by 10)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": 35,  # 35 dbar -> 3.5 bar
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    # getPRS divides by 10 to convert from dbar to bar
    assert sensor.native_value == 3.5


async def test_sensor_sta_unknown_status(hass: HomeAssistant) -> None:
    """Test getSTA with unknown/unmapped status value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "Unknown Status XYZ",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getSTA")

    # Unknown status should be returned as-is (or mapped to itself)
    assert sensor.native_value == "Unknown Status XYZ"


async def test_sensor_mit_temperature_conversion(hass: HomeAssistant) -> None:
    """Test getMIT minimum temperature threshold conversion (divides by 10)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getMIT": "-40"},  # -40 raw -> -4.0 °C
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getMIT")
    assert sensor.native_value == -4.0


async def test_sensor_mxt_temperature_conversion(hass: HomeAssistant) -> None:
    """Test getMXT maximum temperature threshold conversion (divides by 10)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getMXT": "490"},  # 490 raw -> 49.0 °C
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getMXT")
    assert sensor.native_value == 49.0


async def test_sensor_cel_string_value(hass: HomeAssistant) -> None:
    """Test getCEL with string value that gets converted."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCEL": "150",  # String "150" -> 15.0°C
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getCEL")

    # String should be converted to float then divided by 10
    assert sensor.native_value == 15.0


async def test_sensor_prs_string_value(hass: HomeAssistant) -> None:
    """Test getPRS with string value that gets converted."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": "42",  # String "42" -> 4.2 bar
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    # String should be converted to float then divided by 10
    assert sensor.native_value == 4.2


async def test_sensor_sta_empty_value(hass: HomeAssistant) -> None:
    """Test getSTA with empty string value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getSTA")

    # Empty string maps to 'status_inactive' per const.py mapping
    assert sensor.native_value == "status_inactive"


async def test_sensor_precision_without_config(hass: HomeAssistant) -> None:
    """Test sensor numeric conversion when no precision is configured."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSRH": 123.456,  # Sensor without configured precision
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getSRH")

    # Without precision config, value should be returned as-is
    assert sensor.native_value == 123.456


async def test_sensor_native_value_none_status_key(hass: HomeAssistant) -> None:
    """Test native_value when sensor key doesn't exist in status."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "some value",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    # Create sensor for a supported key that is missing from the status
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRES")

    # Should return None when key doesn't exist
    assert sensor.native_value is None


async def test_sensor_exclude_when_zero_int_value(hass: HomeAssistant) -> None:
    """Test getSV2 is shown even when integer value is zero."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSV2": 0,  # Integer zero, no longer excluded
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0]
    # getSV2 with value 0 is now always shown
    sv2_sensors = [e for e in entities if e._sensor_key == "getSV2"]
    assert len(sv2_sensors) == 1

    # Entities should still be added despite registry issues


# Focused tests for uncovered branches in sensor setup logic


def _register_sensor(
    hass: HomeAssistant, device_id: str, key: str, object_id: str | None = None
) -> str:
    """Register a sensor of this integration (no owning entry: unique_id "<device_id>_<key>") and return its entity_id."""

    return (
        er.async_get(hass)
        .async_get_or_create(
            "sensor",
            DOMAIN,
            f"{device_id}_{key}",
            suggested_object_id=object_id or f"syr_connect_{device_id}_{key}".lower(),
        )
        .entity_id
    )


def _registered(hass: HomeAssistant, entity_id: str) -> bool:

    return er.async_get(hass).async_get(entity_id) is not None


async def test_async_setup_entry_getpa_group_false_removes_registry(
    hass: HomeAssistant,
) -> None:
    """getPA1 reported false removes the profile 1 sensors, found by unique_id (also when renamed)."""
    data = {
        "devices": [
            {
                "id": "devp2",
                "name": "DevP2",
                "project_id": "p1",
                "status": {"getPA1": "0"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)
    renamed = _register_sensor(hass, "devp2", "getPV1", "my_profile_volume")

    await async_setup_entry(hass, entry, lambda ents: None)  # type: ignore[arg-type]

    assert not _registered(hass, renamed)


async def test_getpa_group_true_creates_group_entities(hass: HomeAssistant) -> None:
    """When getPA1 evaluates true, group sensors should be created."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    # Use a truthy string that is_value_true should accept
                    "getPA1": "true",
                    # Include all group keys so the 'skip if not in status' guard passes
                    "getPV1": "200",
                    "getPT1": "60",
                    "getPF1": "5",
                    "getPN1": "Zone1",
                    "getPM1": "true",
                    "getPW1": "true",
                    "getPB1": "false",
                    "getPR1": "0",
                    # Also include an unrelated sensor to ensure normal sensors are added
                    "getFLO": "10",
                },
            }
        ]
    }

    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    added: list = []
    await async_setup_entry(hass, entry, lambda ents: added.extend(ents))  # type: ignore[arg-type]

    # group keys for idx=1 should include getPA1, getPV1, getPT1, getPF1, getPN1, getPM1, getPW1, getPB1, getPR1
    group_expected = {
        "getPA1",
        "getPV1",
        "getPT1",
        "getPF1",
        "getPN1",
        "getPM1",
        "getPW1",
        "getPB1",
        "getPR1",
    }
    created_keys = {e._sensor_key for e in added}

    # All group keys should be represented among created entities
    assert group_expected.issubset(created_keys)


async def test_getpa_group_false_removes_registry_entries(hass: HomeAssistant) -> None:
    """When getPA1 evaluates false, existing group entities in registry should be removed."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    # False-like value
                    "getPA1": "0",
                    "getFLO": "10",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)
    group = [
        _register_sensor(hass, "device1", key) for key in ("getPV1", "getPT1", "getPF1")
    ]

    await async_setup_entry(hass, entry, lambda ents: None)  # type: ignore[arg-type]

    assert not [eid for eid in group if _registered(hass, eid)]


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("ConelClearProFill_get_all.json", {"getLOT"}),  # MuCo filling, getCRT=1
        (
            "ConelClearProLeakProtection.json",
            set(),
        ),  # reports getCRT=0/getOHW=1, but no OHW/LOT
        ("SanibelLeakProtectionModuleA25_get_all.json", set()),
        ("SyrTrioLock_get_all.json", set()),
    ],
)
async def test_muco_lot_ohw_sensor_only_for_models_listing_it(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    fixture: str,
    expected: set,
) -> None:
    """The dynamic getLOT/getOHW sensor respects the per-model allowlist (real fixtures)."""

    status = json.loads(
        (Path(__file__).parent / "fixtures/json" / fixture).read_text(encoding="utf-8")
    )
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

    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert keys & {"getLOT", "getOHW"} == expected


def _fixture_statuses() -> list[Any]:
    """Return the device status of every JSON fixture and every XML status fixture."""
    fixtures = Path(__file__).parent / "fixtures"
    statuses = [
        pytest.param(
            path.name, json.loads(path.read_text(encoding="utf-8")), id=path.name
        )
        for path in sorted((fixtures / "json").glob("*.json"))
    ]
    statuses.extend(
        pytest.param(
            path.name,
            ResponseParser().parse_device_status_response(
                path.read_text(encoding="utf-8")
            ),
            id=path.name,
        )
        for path in sorted((fixtures / "xml").glob("*_GetDeviceCollectionStatus.xml"))
    )
    return statuses


@pytest.mark.parametrize(("fixture", "status"), _fixture_statuses())
async def test_sensor_keys_for_status_match_created_sensors(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    fixture: str,
    status: dict,
) -> None:
    """sensor_keys_for_status (used by diagnostics) lists exactly the sensors the setup creates."""
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

    created = [
        "dst" if isinstance(e, SyrConnectConnectionStateSensor) else e._sensor_key
        for e in entities
    ]
    assert sorted(
        sensor_module.sensor_keys_for_status(status, detect_model(status))
    ) == sorted(created), fixture


async def test_getpa_group_empty_status_keeps_registry_entries(
    hass: HomeAssistant,
) -> None:
    """An empty status (not fetched yet, e.g. temporary failure at startup) must not remove the profile sensors."""
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
    group = [
        _register_sensor(hass, "device1", key) for key in ("getPN1", "getPV1", "getPT1")
    ]

    await async_setup_entry(hass, entry, lambda ents: None)  # type: ignore[arg-type]

    assert all(_registered(hass, eid) for eid in group)


async def test_getpa_group_without_flag_pontos_removes_registry_entries(
    hass: HomeAssistant,
) -> None:
    """Pontos Base reports profile keys without getPAx: they stay hidden and old registry entries are removed."""
    status = {"getPN1": "Home", "getPV1": "250", "getPRF": "1", "getFLO": "10"}
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": status,
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)
    old_entry = _register_sensor(hass, "device1", "getPN1")
    added: list = []

    await async_setup_entry(hass, entry, lambda ents: added.extend(ents))  # type: ignore[arg-type]

    assert not _registered(hass, old_entry)
    assert not [
        e for e in added if getattr(e, "_sensor_key", "") in ("getPN1", "getPV1")
    ]


async def test_sensor_rpw_format_datetime_exception(hass: HomeAssistant) -> None:
    """Test getRPW sensor handles format_datetime exception."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "127",  # All days
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Mock format_datetime to raise exception
    with patch(
        "custom_components.syr_connect.sensor.format_datetime",
        side_effect=ValueError("Test error"),
    ):
        result = sensor.native_value
        # Should fallback to strftime and still return weekday names
        assert result is not None
        assert isinstance(result, str)


async def test_sensor_lar_none_value(hass: HomeAssistant) -> None:
    """Test getLAR sensor with None value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getLAR": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getLAR")

    # Should return None for None value
    assert sensor.native_value is None


async def test_sensor_lar_overflow_error(hass: HomeAssistant) -> None:
    """Test getLAR sensor with timestamp that causes overflow."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getLAR": "9999999999999999999",  # Very large timestamp
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getLAR")

    # Should return None when overflow occurs
    assert sensor.native_value is None


async def test_sensor_string_sensor_none_value(hass: HomeAssistant) -> None:
    """Test string sensor with None value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSRN": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getSRN")

    # Should return None for None value
    assert sensor.native_value is None


async def test_sensor_setup_invalid_value_type(hass: HomeAssistant) -> None:
    """Test sensor setup skips values that are not int/float/str."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getCS1": {"nested": "dict"},  # Invalid type (dict)
                    "getRES": 42,  # Valid type (int)
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Should only create sensor for valid type
    entities = add_entities.call_args.args[0] if add_entities.called else []
    valid_entities = [e for e in entities if e._sensor_key == "getRES"]
    invalid_entities = [e for e in entities if e._sensor_key == "getCS1"]

    assert len(valid_entities) == 1
    assert len(invalid_entities) == 0


async def test_sensor_setup_always_hidden_key_not_created(hass: HomeAssistant) -> None:
    """A key with hidden_when="always" is never created, whatever its value."""
    assert _SYR_CONNECT_SENSOR_DESCRIPTIONS["getSCR"].hidden_when == "always"
    assert not sensor_module.is_sensor_visible({}, "getSCR", "5")

    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSCR": "5",
                    "getRES": "42",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0]
    assert not any(e._sensor_key == "getSCR" for e in entities)
    assert any(e._sensor_key == "getRES" for e in entities)


async def test_sensor_setup_unsupported_key_not_created(hass: HomeAssistant) -> None:
    """A key the device reports but that has no sensor description is not created."""

    assert "getDEN" not in _SYR_CONNECT_SENSOR_SUPPORTED_KEYS

    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getDEN": "1",  # Not in SUPPORTED_KEYS → must be skipped
                    "getRES": "42",  # In SUPPORTED_KEYS → must be created
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0] if add_entities.called else []
    assert not any(e._sensor_key == "getDEN" for e in entities)
    assert any(e._sensor_key == "getRES" for e in entities)


async def test_sensor_setup_binary_key_in_supported_keys_not_created(
    hass: HomeAssistant,
) -> None:
    """Binary sensor keys must be skipped as sensors even if in SUPPORTED_KEYS."""

    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRES": "10",  # Normal sensor key
                    "getFAKE": "1",  # Key we'll put into BINARY via patch
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()

    # Temporarily add getFAKE to SUPPORTED_KEYS and BINARY so it reaches the binary-sensor guard
    patched_known = _SYR_CONNECT_SENSOR_SUPPORTED_KEYS | {"getFAKE"}
    patched_binary = {"getFAKE"}

    with (
        patch.object(
            sensor_module, "_SYR_CONNECT_SENSOR_SUPPORTED_KEYS", patched_known
        ),
        patch.object(
            sensor_module, "_SYR_CONNECT_BINARY_SENSOR_SUPPORTED_KEYS", patched_binary
        ),
    ):
        await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0] if add_entities.called else []
    assert not any(e._sensor_key == "getFAKE" for e in entities)
    assert any(e._sensor_key == "getRES" for e in entities)


async def test_sensor_alarm_unmapped_value(hass: HomeAssistant) -> None:
    """Test getALM sensor with value not in mapping returns original value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALM": "UnknownAlarm",  # Not in the alarm value map
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getALM")

    # When value is not in map, .get() returns None, should fallback to original value
    value = sensor.native_value
    # The implementation now returns the raw unmapped value as-is.
    assert value == "UnknownAlarm"


async def test_sensor_sta_with_rapide_variant(hass: HomeAssistant) -> None:
    """Test getSTA sensor with 'Płukanie rapide' pattern."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "Płukanie szybkie 2",  # Fast rinse round 2
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getSTA")

    # Should map to status_fast_rinse
    value = sensor.native_value
    assert value == "status_fast_rinse"


async def test_sensor_whu_none_value_returns_none(hass: HomeAssistant) -> None:
    """Test getWHU sensor with None value returns None."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getWHU")

    # Should return None
    assert sensor.native_value is None


async def test_sensor_whu_unit_type_error(hass: HomeAssistant) -> None:
    """Test water hardness sensor unit with TypeError on WHU conversion."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getOWH": 50,
                    "getWHU": None,  # TypeError on int(None)
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getOWH")

    # Should set unit to None
    assert sensor.native_unit_of_measurement is None


async def test_sensor_getvol_with_prefix(hass: HomeAssistant) -> None:
    """Test getVOL sensor when device sends value with prefix like 'Vol[L]6530'."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getVOL": "Vol[L]6530",  # Value with prefix
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    # Test getVOL sensor - should extract numeric value
    vol_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getVOL")
    val = vol_sensor.native_value
    assert isinstance(val, int | float | str)
    assert abs(float(val) - 6.53) < 1e-6


async def test_sensor_getvol_normal_value(hass: HomeAssistant) -> None:
    """Test getVOL sensor with normal numeric value (backward compatibility)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getVOL": "6530",  # Normal value without prefix
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    vol_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getVOL")
    val = vol_sensor.native_value
    assert isinstance(val, int | float | str)
    assert abs(float(val) - 6.53) < 1e-6


async def test_sensor_getvol_numeric_value(hass: HomeAssistant) -> None:
    """Test getVOL sensor with direct numeric value (not string)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getVOL": 6530,  # Direct numeric value
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    vol_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getVOL")
    val = vol_sensor.native_value
    assert isinstance(val, int | float | str)
    assert abs(float(val) - 6.53) < 1e-6


async def test_sensor_getbat_with_multiple_values(hass: HomeAssistant) -> None:
    """Test getBAT sensor extracts first voltage value from Safe-T+ format."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": "6,12 4,38 3,90",  # Safe-T+ battery format
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    bat_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")
    assert bat_sensor.native_value == 6.12


async def test_sensor_getbat_empty_value(hass: HomeAssistant) -> None:
    """Test getBAT sensor with empty value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    bat_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")
    assert bat_sensor.native_value is None


async def test_sensor_getbat_invalid_value(hass: HomeAssistant) -> None:
    """Test getBAT sensor with invalid value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    bat_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")
    assert bat_sensor.native_value is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        # A reported getBAP wins over the computed level
        ({"getBAP": "59", "getBAT": "601", "getBMA": "585", "getBMI": "515"}, 59),
        ({"getBAP": 56, "getBAT": 600, "getBMA": 585, "getBMI": 515}, 56),
        # Without getBAP: 100 % from getBMA on, 0 % up to getBMI, linear in between
        ({"getBAT": "601", "getBMA": "585", "getBMI": "515"}, 100),
        ({"getBAT": "585", "getBMA": "585", "getBMI": "515"}, 100),
        ({"getBAT": "550", "getBMA": "585", "getBMI": "515"}, 50),
        ({"getBAT": 540, "getBMA": 585, "getBMI": 515}, 36),
        ({"getBAP": "", "getBAT": "550", "getBMA": "585", "getBMI": "515"}, 50),
        ({"getBAT": "515", "getBMA": "585", "getBMI": "515"}, 0),
        ({"getBAT": "500", "getBMA": "585", "getBMI": "515"}, 0),
        # No level without a positive voltage, without getBMA/getBMI or with getBMI > getBMA
        ({"getBAT": "0", "getBMA": "585", "getBMI": "515"}, None),
        ({"getBAT": "550", "getBMI": "515"}, None),
        ({"getBAT": "550", "getBMA": "585"}, None),
        ({"getBAT": "550", "getBMA": "515", "getBMI": "585"}, None),
        ({"getBMA": "585", "getBMI": "515"}, None),
    ],
)
async def test_sensor_getbap_computed_from_voltages(
    hass: HomeAssistant, status: dict[str, Any], expected: int | None
) -> None:
    """Battery level (getBAP) is the reported level, else computed from the voltages."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": status,
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    bap = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAP")

    assert bap.native_value == expected


@pytest.mark.parametrize(
    ("status", "created"),
    [
        ({"getBAT": "550", "getBMA": "585", "getBMI": "515"}, True),
        # Without one of the voltages no level can be computed
        ({"getBAT": "550", "getBMA": "585"}, False),
    ],
)
async def test_async_setup_entry_creates_computed_battery_level(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    status: dict[str, Any],
    created: bool,
) -> None:
    """A device without getBAP gets a battery level sensor if it reports the voltages."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": status,
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    bap = [e for e in entities if getattr(e, "_sensor_key", None) == "getBAP"]
    assert len(bap) == (1 if created else 0)
    if created:
        assert bap[0].native_value == 50


@pytest.mark.parametrize(
    ("device", "unit"),
    [
        # SafeFloor detected by the cloud device kind, without getTYP
        (
            {"dk": 122, "dkv": 34, "sbt": 0, "status": {"getBAT": "40"}},
            UnitOfRatio.PERCENTAGE,
        ),
        # getTYP 120 alone does not make an unknown model a SafeFloor
        (
            {"status": {"getBAT": "363", "getTYP": "120"}},
            UnitOfElectricPotential.VOLT,
        ),
    ],
)
async def test_sensor_getbat_percentage_follows_the_model(
    hass: HomeAssistant, device: dict[str, Any], unit: str
) -> None:
    """Battery (getBAT) is a percentage only for models whose profile says so (SafeFloor)."""
    data = {
        "devices": [
            {"id": "device1", "name": "Device 1", "project_id": "project1", **device}
        ]
    }
    coordinator = _build_coordinator(hass, data)
    bat = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert bat.native_unit_of_measurement == unit


async def test_sensor_getbat_voltage_keeps_voltage_name(hass: HomeAssistant) -> None:
    """Devices that report getBAT as voltage keep the name "Battery voltage"."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getBAT": "363"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    bat = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert bat.native_unit_of_measurement == UnitOfElectricPotential.VOLT
    assert bat.translation_key == "getbat"


async def test_sensor_getbat_voltage_device_unaffected(hass: HomeAssistant) -> None:
    """Non-SafeFloor devices still parse getBAT as voltage (Trio DFR/LS format)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": "363",
                    "getTYP": "80",  # LEXplus
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    bat = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert bat.native_value == 3.63
    assert bat.native_unit_of_measurement == UnitOfElectricPotential.VOLT
    assert bat.device_class == SensorDeviceClass.VOLTAGE


async def test_sensor_getbar_with_unit(hass: HomeAssistant) -> None:
    """Test getBAR sensor with 'mbar' unit suffix."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAR": "4077 mbar",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    bar_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAR")
    assert bar_sensor.native_value == 4.1


async def test_sensor_getbar_numeric_only(hass: HomeAssistant) -> None:
    """Test getBAR sensor with numeric value only."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAR": "4077",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    bar_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAR")
    assert bar_sensor.native_value == 4.1


async def test_sensor_getbar_empty_value(hass: HomeAssistant) -> None:
    """Test getBAR sensor with empty value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAR": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    bar_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAR")
    assert bar_sensor.native_value is None


async def test_sensor_getbar_invalid_value(hass: HomeAssistant) -> None:
    """Test getBAR sensor with invalid value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAR": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    bar_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAR")
    assert bar_sensor.native_value is None


async def test_sensor_getavo_with_ml_suffix(hass: HomeAssistant) -> None:
    """Test getAVO sensor with 'mL' unit suffix."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getAVO": "1655mL",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    avo_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getAVO")
    assert avo_sensor.native_value == 1.655  # mL converted to L


async def test_sensor_getavo_numeric_value(hass: HomeAssistant) -> None:
    """Test getAVO sensor with numeric value only."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getAVO": 1655,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    avo_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getAVO")
    assert avo_sensor.native_value == 1.655


async def test_sensor_getavo_empty_value(hass: HomeAssistant) -> None:
    """Test getAVO sensor with empty value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getAVO": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    avo_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getAVO")
    assert avo_sensor.native_value is None


async def test_sensor_getavo_none_value(hass: HomeAssistant) -> None:
    """Test getAVO sensor with None value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getAVO": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    avo_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getAVO")
    assert avo_sensor.native_value is None


async def test_sensor_gettmp_numeric_value(hass: HomeAssistant) -> None:
    """Test getTMP sensor with numeric value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getTMP": "300",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    tmp_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getTMP")
    assert tmp_sensor.native_value == 300.0


async def test_sensor_gettmp_zero_value(hass: HomeAssistant) -> None:
    """Test getTMP sensor with zero value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getTMP": "0",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    tmp_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getTMP")
    assert tmp_sensor.native_value == 0.0


async def test_sensor_getle_value_mapping(hass: HomeAssistant) -> None:
    """Test getLE sensor value mapping from API value to display value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getLE": "5",  # API value
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    le_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getLE")
    # Mapped display value (matches mapping in const.py)
    assert le_sensor.native_value == 250  # Mapped display value


async def test_sensor_getul_value_mapping(hass: HomeAssistant) -> None:
    """Test getUL sensor value mapping from API value to display value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getUL": "3",  # API value
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    ul_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getUL")
    # Integration returns scaled integer (value*10)
    assert ul_sensor.native_value == 30  # Mapped display value as int


async def test_sensor_gett1_value_mapping(hass: HomeAssistant) -> None:
    """Test getT1 sensor value mapping from API value to display value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getT1": "10",  # API value
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    t1_sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getT1")
    assert t1_sensor.native_value == 5.0  # Mapped display value


async def test_sensor_getul_integer_input(hass: HomeAssistant) -> None:
    """Test getUL when API returns an integer (should multiply by 10)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getUL": 4},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getUL")

    # 4 -> 40 liters
    assert sensor.native_value == 40


async def test_sensor_getul_mapped_string_key(hass: HomeAssistant) -> None:
    """Test getUL with string key that exists in mapping (e.g., '1')."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getUL": "1"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getUL")

    # Mapping '1' -> 10 liters; implementation returns numeric int
    assert sensor.native_value == 10


async def test_rtm_combined_string_and_invalid(hass: HomeAssistant) -> None:
    """Test rtm combined string and invalid."""
    # Combined valid string
    data_ok = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getRTM": "07:05"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data_ok)
    sensor_ok = SyrConnectSensor(coordinator, "device1", "Device 1", "getRTM")
    assert sensor_ok.native_value == "07:05"

    # Combined invalid string (hour out of range)
    data_bad = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getRTM": "25:00"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data_bad)
    sensor_bad = SyrConnectSensor(coordinator, "device1", "Device 1", "getRTM")
    assert sensor_bad.native_value is None


@pytest.mark.parametrize(
    ("key", "raw", "expected"),
    [
        ("getPM1", 1, "true"),
        ("getPM1", 0, "false"),
        ("getPW2", "1", "true"),
        ("getPW2", "0", "false"),
        ("getPB3", "true", "true"),
        ("getPB3", "True", "true"),
        ("getPB3", True, "true"),
        ("getPM1", "false", "false"),
        ("getPM1", "False", "false"),
        ("getPW2", "maybe", "false"),
    ],
)
async def test_leak_protection_boolean_flags_various_values(
    hass: HomeAssistant, key: str, raw: object, expected: str
) -> None:
    """Test leak-protection boolean flags parsing for various inputs."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {key: raw},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", key)

    assert sensor.native_value == expected


async def test_leak_protection_boolean_flags_empty_and_none(
    hass: HomeAssistant,
) -> None:
    """Empty string or None for leak-protection flags should return None."""
    for raw in (None, "", "   "):
        data = {
            "devices": [
                {
                    "id": "device1",
                    "name": "Device 1",
                    "project_id": "project1",
                    "status": {"getPM1": raw},
                }
            ]
        }
        coordinator = _build_coordinator(hass, data)
        sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPM1")
        assert sensor.native_value is None


async def test_sensor_ala_not_wrn_exhaustive_variants(hass: HomeAssistant) -> None:
    """Blank getALA codes give None; other codes give a string (mapped key or the raw value)."""
    unmapped = {"true", "off", "UnknownValue", "CompletelyUnknown", 123}
    variants = [None, "", "   ", "1", "0", 1, 0, True, False, *unmapped]

    for key in ("getALA", "getNOT", "getWRN"):
        for raw in variants:
            data = {
                "devices": [
                    {
                        "id": "d_ex",
                        "name": "Device",
                        "project_id": "p",
                        "status": {key: raw},
                    }
                ]
            }
            coord = _build_coordinator(hass, data)
            s = SyrConnectSensor(coord, "d_ex", "Device", key)

            val = s.native_value

            # getNOT/getWRN map an empty code to their "none" key, so only None and getALA blanks give None.
            if raw is None or (
                key == "getALA" and isinstance(raw, str) and raw.strip() == ""
            ):
                assert val is None, (
                    f"Key {key} raw={raw!r} -> got {val!r}, expected None"
                )
            else:
                assert isinstance(val, str), f"Key {key} raw={raw!r} -> got {val!r}"
                if raw in unmapped:
                    assert val == str(raw), f"Key {key} raw={raw!r} -> got {val!r}"


# Tests merged from test_getcof_water_consumption.py
def test_getcof_has_water_device_class() -> None:
    """Test that getCOF sensor has device_class=water for Energy Dashboard."""
    cof = _SYR_CONNECT_SENSOR_DESCRIPTIONS["getCOF"]
    assert cof.device_class == SensorDeviceClass.WATER


def test_getcof_has_total_increasing_state_class() -> None:
    """Test that getCOF sensor has state_class=total_increasing for statistics."""
    cof = _SYR_CONNECT_SENSOR_DESCRIPTIONS["getCOF"]
    assert cof.state_class == "total_increasing"


def test_getcof_returns_correct_value() -> None:
    """Test that getCOF sensor returns the correct water consumption value."""
    # Create mock coordinator with test data
    mock_coordinator = Mock()
    mock_coordinator.data = {
        "devices": [
            {
                "id": "123456789",
                "name": "Test Device",
                "status": {
                    "getCOF": 888518,  # Water consumption in liters
                },
            }
        ]
    }

    # Create sensor instance
    sensor = SyrConnectSensor(
        coordinator=mock_coordinator,
        device_id="123456789",
        device_name="Test Device",
        sensor_key="getCOF",
    )

    # Test that native_value returns getCOF value
    assert sensor.native_value == 888518


def test_getcof_handles_string_values() -> None:
    """Test that getCOF sensor correctly converts string values to float."""
    mock_coordinator = Mock()
    mock_coordinator.data = {
        "devices": [
            {
                "id": "123456789",
                "name": "Test Device",
                "status": {
                    "getCOF": "888518",  # String value
                },
            }
        ]
    }

    sensor = SyrConnectSensor(
        coordinator=mock_coordinator,
        device_id="123456789",
        device_name="Test Device",
        sensor_key="getCOF",
    )

    # Should convert string to number (accept int or float)
    assert float(cast(Any, sensor.native_value)) == 888518.0
    assert isinstance(sensor.native_value, int | float)


async def test_async_setup_entry_registry_remove_exception(hass: HomeAssistant) -> None:
    """Test exception handler when registry.async_remove fails."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "0",  # False, triggers removal
                },
            }
        ]
    }
    coordinator.last_update_success = True

    entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )
    entry.runtime_data = coordinator
    entry.add_to_hass(hass)
    coordinator.entry_id = entry.entry_id

    # Mock the entity registry with an entry that exists
    with patch("custom_components.syr_connect.sensor.er.async_get") as mock_er:
        mock_registry = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entity_id = "sensor.device1_getpa1"
        mock_entry.config_entry_id = entry.entry_id

        # Make async_get return the mock entry
        mock_registry.async_get = Mock(return_value=mock_entry)

        # Make async_remove raise an exception
        mock_registry.async_remove = Mock(side_effect=RuntimeError("Remove failed"))
        mock_er.return_value = mock_registry

        mock_add_entities = Mock()

        # Should not raise exception, should handle it gracefully
        await async_setup_entry(hass, entry, mock_add_entities)

        # Verify async_remove was attempted
        assert mock_registry.async_remove.called


async def test_sensor_apply_numeric_conversion_vol_exception(
    hass: HomeAssistant,
) -> None:
    """Test exception handling in get VOL conversion."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getVOL": "Vol[L]invalid",  # Will cause exception in conversion
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getVOL",
    )

    # A numeric sensor gets no text as its value, Home Assistant would reject it
    assert sensor.native_value is None


def _flo_sensor(
    create_mock_coordinator: Callable[..., MagicMock], raw: object
) -> tuple[MagicMock, SyrConnectSensor]:
    data = {"devices": [{"id": "d1", "name": "D1", "status": {"getFLO": raw}}]}
    coordinator = create_mock_coordinator(data)
    return coordinator, SyrConnectSensor(coordinator, "d1", "D1", "getFLO")


def _set_flo(coordinator: MagicMock, raw: object) -> None:
    coordinator.data["devices"][0]["status"]["getFLO"] = raw


def _non_numeric_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING and "non-numeric" in record.getMessage()
    ]


def test_sensor_non_numeric_text_keeps_last_value_and_warns_once(
    create_mock_coordinator: Callable[..., MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A text of a numeric sensor keeps the last value, warned once until a number comes."""
    caplog.set_level(logging.DEBUG)
    coordinator, sensor = _flo_sensor(create_mock_coordinator, "240")
    assert sensor.native_value == 240

    _set_flo(coordinator, "-")
    assert sensor.native_value == 240
    assert sensor.native_value == 240
    assert _non_numeric_warnings(caplog) == [
        "Device D1 (d1): getFLO reported the non-numeric value '-'; keeping the last value"
    ]

    # A number resets the warning, the next text is warned again
    _set_flo(coordinator, 300)
    assert sensor.native_value == 300
    caplog.clear()
    _set_flo(coordinator, "n/a")
    assert sensor.native_value == 300
    assert len(_non_numeric_warnings(caplog)) == 1


def test_sensor_non_numeric_text_without_last_value(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Without an earlier number the state is unknown (None)."""
    _coordinator, sensor = _flo_sensor(create_mock_coordinator, "n/a")
    assert sensor.native_value is None


def test_sensor_empty_text_is_missing_without_warning(
    create_mock_coordinator: Callable[..., MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An empty value of a numeric sensor is a missing value, not a wrong format."""
    _coordinator, sensor = _flo_sensor(create_mock_coordinator, " ")
    assert sensor.native_value is None
    assert not _non_numeric_warnings(caplog)


def test_sensor_text_sensor_keeps_text(
    create_mock_coordinator: Callable[..., MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A sensor without unit, state class, precision or device class shows the text."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": {"getSRV": "next week"}}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getSRV")
    assert sensor.native_value == "next week"
    assert not _non_numeric_warnings(caplog)


def test_sensor_non_numeric_device_class_keeps_text(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """A non-numeric device class (e.g. timestamp) is no numeric sensor."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": {"getSRV": "soon"}}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getSRV")
    sensor._attr_device_class = SensorDeviceClass.TIMESTAMP
    assert sensor.numeric_value("soon") == "soon"


async def test_sensor_native_value_caching(hass: HomeAssistant) -> None:
    """Test that native_value caches last non-None value."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": "100",
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getFLO",
    )

    # Get initial value
    first_value = sensor.native_value
    assert first_value == 100

    # Update data to return None (API omitted the field)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},  # getFLO missing
            }
        ]
    }

    # Should return cached value
    cached_value = sensor.native_value
    assert cached_value == 100  # Returns last known value


async def test_sensor_getbar_none_value(hass: HomeAssistant) -> None:
    """Test getBAR sensor with None value."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAR": None,
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getBAR",
    )

    # Should handle None value
    value = sensor.native_value
    assert value is None


async def test_sensor_getbar_no_match(hass: HomeAssistant) -> None:
    """Test getBAR sensor when regex doesn't match."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAR": "no digits here",
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getBAR",
    )

    # Should handle no match
    value = sensor.native_value
    assert value is None


async def test_sensor_getbat_not_string_int_float(hass: HomeAssistant) -> None:
    """Test getBAT when value is not string/int/float."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": ["not", "valid"],  # List instead of expected type
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getBAT",
    )

    # Should handle invalid type
    value = sensor.native_value
    assert value is None


async def test_sensor_registry_cleanup_exception_async_get(hass: HomeAssistant) -> None:
    """Test exception handling during registry cleanup in async_setup_entry when async_get fails."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": "50"
                },  # Normal sensor, cleanup tries all excluded keys
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )
    entry.runtime_data = coordinator
    entry.add_to_hass(hass)

    # Mock registry to raise exception during cleanup
    with patch("custom_components.syr_connect.sensor.er.async_get") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.async_get.side_effect = RuntimeError("Registry error")
        mock_registry.return_value = mock_reg

        mock_add_entities = Mock()
        # Should not raise exception, should be caught
        await async_setup_entry(hass, entry, mock_add_entities)

        # Entities should still be added despite exception
        assert mock_add_entities.called

    # Should complete despite exception

    # Should complete despite exception


async def test_sensor_getvol_none_value(hass: HomeAssistant) -> None:
    """Test getVOL sensor with None value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getVOL": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getVOL")

    assert sensor.native_value is None


async def test_sensor_getbar_invalid_type(hass: HomeAssistant) -> None:
    """Test getBAR sensor with value that raises TypeError during conversion."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAR": {"invalid": "dict"},
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAR")

    assert sensor.native_value is None


async def test_sensor_getbat_none_value(hass: HomeAssistant) -> None:
    """Test getBAT sensor with None value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert sensor.native_value is None


async def test_sensor_leak_protection_getpv_float_value(hass: HomeAssistant) -> None:
    """Test leak protection getPV with float value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPV1": 1.5,  # Non-zero float
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPV1")

    # getPV is a number, rounded to its precision
    assert sensor.native_value == 2


async def test_sensor_leak_protection_getpt_zero_float(hass: HomeAssistant) -> None:
    """Test leak protection getPT with zero float value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPT2": 0.0,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPT2")

    assert sensor.native_value == 0


async def test_sensor_leak_protection_getpn_none_value(hass: HomeAssistant) -> None:
    """Test leak protection getPN with None value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPN3": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPN3")

    assert sensor.native_value is None


async def test_sensor_leak_protection_getpw_empty_string(hass: HomeAssistant) -> None:
    """Test leak protection flag getPW with empty string."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPW4": "  ",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPW4")

    assert sensor.native_value is None


async def test_sensor_leak_protection_getpw_invalid_numeric_string(
    hass: HomeAssistant,
) -> None:
    """Test leak protection flag getPW with a text that is no number."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPW8": "not_a_number",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPW8")

    # An unknown value counts as not set (see is_value_true)
    assert sensor.native_value == "false"


async def test_sensor_leak_protection_getpb_invalid_type(hass: HomeAssistant) -> None:
    """Test leak protection flag getPB with invalid type."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPB1": {"dict": "value"},
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPB1")

    # An unknown type counts as not set (see is_value_true)
    assert sensor.native_value == "false"


@pytest.mark.parametrize(
    ("value", "active"),
    [
        pytest.param(True, True, id="true"),
        pytest.param(1, True, id="one"),
        pytest.param(5, True, id="int"),
        pytest.param(2.5, True, id="float"),
        pytest.param("true", True, id="text-true"),
        pytest.param("1", True, id="text-one"),
        pytest.param("3.14", True, id="text-float"),
        pytest.param(False, False, id="false"),
        pytest.param("invalid", False, id="text-without-number"),
        pytest.param({"key": "value"}, False, id="dict"),
        pytest.param([1, 2, 3], False, id="list"),
    ],
)
async def test_sensor_setup_profile_sensors_follow_profile_flag(
    hass: HomeAssistant, value: object, active: bool
) -> None:
    """The sensors of a leak protection profile are only created for an active profile (getPA)."""
    group = {"getPA1", "getPV1", "getPN1"}
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getPA1": value, "getPV1": "10", "getPN1": "Present"},
            }
        ]
    }
    entry = _build_entry(_build_coordinator(hass, data))
    add_entities = Mock()

    await async_setup_entry(hass, entry, add_entities)

    keys = {entity._sensor_key for entity in _added_entities(add_entities)}
    assert keys & group == (group if active else set())


async def test_getpa_group_key_excluded_by_model_allowlist(hass: HomeAssistant) -> None:
    """PA-group sensors are skipped when the model's SENSOR_SUPPORTED_KEYS override excludes them.

    This holds even though getPAx is true.

    The muco_filling override (conelclearprofill, getDFM==3) deliberately excludes
    the whole leak-protection-profile family (getPA1-8/getPV1-8/etc.).
    """
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSRN": "500AAA00001",
                    "getDFM": 3,
                    "getPA1": "true",
                    "getPV1": "200",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)

    mock_add_entities = Mock()
    await async_setup_entry(hass, entry, mock_add_entities)

    entities = mock_add_entities.call_args[0][0]
    sensor_keys = [e._sensor_key for e in entities]
    assert "getPA1" not in sensor_keys
    assert "getPV1" not in sensor_keys


def test_pm_boolean_edgecases(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Various boolean-like values for getPMx should be handled gracefully."""
    data = {
        "devices": [
            {
                "id": "d1",
                "name": "D",
                "project_id": "p1",
                "status": {
                    "getPM1": "True",
                    "getPM2": "False",
                    "getPM3": "xyz",
                    "getPM4": 0,
                },
            }
        ]
    }
    coord = create_mock_coordinator(data)

    pm1 = SyrConnectSensor(coord, "d1", "D", "getPM1")
    pm2 = SyrConnectSensor(coord, "d1", "D", "getPM2")
    pm3 = SyrConnectSensor(coord, "d1", "D", "getPM3")
    pm4 = SyrConnectSensor(coord, "d1", "D", "getPM4")

    assert pm1.native_value == "true"
    assert pm2.native_value == "false"
    assert pm3.native_value == "false"
    assert pm4.native_value == "false"


def test_sensor_disabled_by_default_flag(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Sensors in the disabled-by-default set should be disabled by default."""
    data = {
        "devices": [
            {"id": "DEV", "name": "D", "project_id": "p1", "status": {"getIPA": "1"}}
        ]
    }
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "DEV", "D", "getIPA")

    assert sensor.entity_registry_enabled_default is False


def test_apply_numeric_conversion_precision_zero_returns_int(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """When precision == 0, _apply_numeric_conversion should return int."""
    data = {
        "devices": [
            {"id": "d1", "name": "D", "project_id": "p1", "status": {"getPRS": "50"}}
        ]
    }
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D", "getPRS")

    sensor.entity_description = replace(
        sensor.entity_description, suggested_display_precision=0
    )
    result = sensor._apply_numeric_conversion(50.0)
    assert isinstance(result, int)
    assert result == 5


def test_getala_uses_generic_codes_for_unknown_model(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """When model is unknown getALA is mapped with the generic alarm codes."""
    data = {
        "devices": [
            {"id": "d1", "name": "D", "project_id": "p1", "status": {"getALA": "A5"}}
        ]
    }
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D", "getALA")

    assert sensor.native_value == "alarm_max_flow_rate_reached"


async def test_sensor_getbat_zero_value(hass: HomeAssistant) -> None:
    """A battery voltage of zero is a value, not a missing one."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getBAT": "0"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert sensor.native_value == 0.0


async def test_bar_avo_invalid_and_vol_prefix(hass: HomeAssistant) -> None:
    """Test bar avo invalid and vol prefix."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAR": "no digits",
                    "getAVO": "abc",
                    "getVOL": "Vol[L]6530",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    bar = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAR")
    assert bar.native_value is None

    avo = SyrConnectSensor(coordinator, "device1", "Device 1", "getAVO")
    assert avo.native_value is None

    vol = SyrConnectSensor(coordinator, "device1", "Device 1", "getVOL")
    assert abs(float(vol.native_value) - 6.53) < 0.001  # type: ignore[arg-type]


async def test_sensor_setup_pa_group_outer_exception_caught(
    hass: HomeAssistant,
) -> None:
    """Outer except(ValueError,TypeError,..) in getPA loop caught.

    Patch SyrConnectSensor to raise TypeError inside the True branch so the outer
    handler fires.  Only getPA1 is true; status has no other keys so the
    status-items loop never calls SyrConnectSensor.
    """
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getPA1": "true"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    mock_add = Mock()
    with patch(
        "custom_components.syr_connect.sensor.SyrConnectSensor",
        side_effect=TypeError("boom"),
    ):
        await async_setup_entry(hass, entry, mock_add)
    # Exception was caught; no entity was created
    mock_add.assert_not_called()


async def test_sensor_setup_sro_empty_value_skipped(hass: HomeAssistant) -> None:
    """The getSRO with empty string hits the None/empty continue."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getSRO": "", "getFLO": "5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0]
    sro = [e for e in entities if e._sensor_key == "getSRO"]
    assert len(sro) == 0  # getSRO with empty value → not created


async def test_sensor_setup_sro_bad_string_skipped(hass: HomeAssistant) -> None:
    """The getSRO with non-numeric string hits except-continue."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getSRO": "bad_value", "getFLO": "5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0]
    sro = [e for e in entities if e._sensor_key == "getSRO"]
    assert len(sro) == 0  # non-numeric → not created


async def test_sensor_setup_ffm_empty_value_skipped(hass: HomeAssistant) -> None:
    """The getFFM with empty string hits the None/empty continue."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getFFM": "", "getFLO": "5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0]
    ffm = [e for e in entities if e._sensor_key == "getFFM"]
    assert len(ffm) == 0


async def test_sensor_setup_ffm_bad_string_skipped(hass: HomeAssistant) -> None:
    """The getFFM with non-numeric string hits except-continue."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getFFM": "bad_value", "getFLO": "5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args.args[0]
    ffm = [e for e in entities if e._sensor_key == "getFFM"]
    assert len(ffm) == 0


def test_sensor_getab_native_value_none_when_ab_none(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The getAB _compute_native_value returns None when get_sensor_ab_value returns None."""
    data = {"devices": [{"id": "d1", "status": {"getAB": None}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getAB")

    assert sensor.native_value is None


def test_sensor_getala_mapped_translation_key_returned(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """getALA: mapped truthy value sets translation_key and returns it.

    Use LEXplus10SL + code '0' which maps to 'no_alarm'.
    """
    data = {
        "devices": [
            {
                "id": "d1",
                "status": {"getCNA": "LEXplus10SL", "getALA": "0"},
            }
        ]
    }
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getALA")

    value = sensor.native_value
    assert value == "no_alarm"
    assert (
        sensor.translation_key == "getala"
    )  # unchanged; the state is translated under it


def test_sensor_getnet_valid_value(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Mains voltage (getNET) of a Trio DFR/LS: "363" -> 3.63 V."""
    data = {"devices": [{"id": "d1", "status": {"getNET": "363"}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getNET")
    assert sensor.native_value == 3.63


def test_sensor_getnet_none_value(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The getNET with None returns None."""
    data = {"devices": [{"id": "d1", "status": {"getNET": None}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getNET")

    assert sensor.native_value is None


def test_sensor_getnet_non_str_int_float_type(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The getNET with non-str/int/float type returns None."""
    data = {"devices": [{"id": "d1", "status": {"getNET": {"a": 1}}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getNET")

    assert sensor.native_value is None


def test_sensor_getnot_mapped_value_returned(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """getNOT: known code '01' returns mapped translation key."""
    data = {"devices": [{"id": "d1", "status": {"getNOT": "01"}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getNOT")

    value = sensor.native_value
    assert value == "new_software_available"
    assert (
        sensor.translation_key == "getnot"
    )  # unchanged; the state is translated under it


def test_sensor_getnot_unmapped_returns_raw_code(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """getNOT: unknown code returns raw string."""
    data = {"devices": [{"id": "d1", "status": {"getNOT": "99"}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getNOT")

    value = sensor.native_value
    assert value == "99"


def test_sensor_leak_flag_float_nan_returns_false(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """getPM1 with float('nan'): int(float(nan)) raises ValueError, so it counts as not set."""
    data = {"devices": [{"id": "d1", "status": {"getPM1": float("nan")}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getPM1")

    assert sensor.native_value == "false"


def test_sensor_getwrn_mapped_value_returned(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """getWRN: known code '01' returns mapped translation key."""
    data = {"devices": [{"id": "d1", "status": {"getWRN": "01"}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getWRN")

    value = sensor.native_value
    assert value == "power_outage"
    assert (
        sensor.translation_key == "getwrn"
    )  # unchanged; the state is translated under it


def test_sensor_getwrn_unmapped_returns_raw_code(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """getWRN: unknown code returns raw string."""
    data = {"devices": [{"id": "d1", "status": {"getWRN": "99"}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getWRN")

    value = sensor.native_value
    assert value == "99"


def test_sensor_getlng_none_value_returns_none(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """getLNG: None value returns None."""
    data = {"devices": [{"id": "d1", "status": {"getLNG": None}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getLNG")

    assert sensor.native_value is None


def test_sensor_getlng_empty_string_returns_none(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """getLNG: empty string value returns None."""
    data = {"devices": [{"id": "d1", "status": {"getLNG": ""}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getLNG")

    assert sensor.native_value is None


def test_sensor_getlng_annotated_value_stripped(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """getLNG: annotated value is stripped to the leading integer."""
    data = {"devices": [{"id": "d1", "status": {"getLNG": "0 (0=Deutsch 1=English)"}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getLNG")

    assert sensor.native_value == "0"


# ---------------------------------------------------------------------------
# SyrConnectConnectionStateSensor tests
# ---------------------------------------------------------------------------


def _build_connection_state_sensor(
    hass: HomeAssistant,
    data: dict,
    device_id: str = "device1",
) -> SyrConnectConnectionStateSensor:
    coordinator = _build_coordinator(hass, data)
    return SyrConnectConnectionStateSensor(coordinator, device_id, "Device 1")


async def test_connection_state_sensor_always_available(hass: HomeAssistant) -> None:
    """Connection state sensor is always available."""
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
    sensor = _build_connection_state_sensor(hass, data)
    assert sensor.available is True


async def test_connection_state_sensor_available_when_coordinator_fails(
    hass: HomeAssistant,
) -> None:
    """Connection state sensor stays available even when coordinator update fails."""
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
    coordinator.last_update_success = False
    sensor = SyrConnectConnectionStateSensor(coordinator, "device1", "Device 1")
    assert sensor.available is True


async def test_connection_state_sensor_native_value_numeric(
    hass: HomeAssistant,
) -> None:
    """native_value returns string for numeric dst value."""
    for dst_val, expected in [(0, "0"), (1, "1"), (2, "2"), (3, "3")]:
        data = {
            "devices": [
                {
                    "id": "device1",
                    "name": "Device 1",
                    "project_id": "project1",
                    "status": {"dst": dst_val},
                }
            ]
        }
        sensor = _build_connection_state_sensor(hass, data)
        assert sensor.native_value == expected, f"dst={dst_val}"


async def test_connection_state_sensor_native_value_string(hass: HomeAssistant) -> None:
    """native_value returns string for string dst value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"dst": "2"},
            }
        ]
    }
    sensor = _build_connection_state_sensor(hass, data)
    assert sensor.native_value == "2"


async def test_connection_state_sensor_native_value_none(hass: HomeAssistant) -> None:
    """native_value returns None when dst is absent."""
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
    sensor = _build_connection_state_sensor(hass, data)
    assert sensor.native_value is None


async def test_connection_state_sensor_native_value_non_integer_string(
    hass: HomeAssistant,
) -> None:
    """native_value returns the raw string when dst cannot be cast to int."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"dst": "unknown"},
            }
        ]
    }
    sensor = _build_connection_state_sensor(hass, data)
    assert sensor.native_value == "unknown"


async def test_connection_state_sensor_native_value_no_data(
    hass: HomeAssistant,
) -> None:
    """native_value returns None when coordinator has no data."""
    coordinator = _build_coordinator(hass, {})
    sensor = SyrConnectConnectionStateSensor(coordinator, "device1", "Device 1")
    assert sensor.native_value is None


async def test_connection_state_sensor_entity_category(hass: HomeAssistant) -> None:
    """Connection state sensor has DIAGNOSTIC entity category."""

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
    sensor = _build_connection_state_sensor(hass, data)
    assert sensor.entity_category == EntityCategory.DIAGNOSTIC


async def test_connection_state_sensor_unique_id(hass: HomeAssistant) -> None:
    """Connection state sensor unique_id is {device_id}_dst."""
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
    sensor = _build_connection_state_sensor(hass, data)
    assert sensor.unique_id == "device1_dst"


async def test_connection_state_sensor_translation_key(hass: HomeAssistant) -> None:
    """Connection state sensor uses 'dst' as translation key."""
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
    sensor = _build_connection_state_sensor(hass, data)
    assert sensor.translation_key == "dst"


async def test_async_setup_entry_creates_connection_state_sensor(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
) -> None:
    """async_setup_entry creates a connection state sensor for each device."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"dst": "2"},
            },
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities = []

    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    connection_sensors = [
        e for e in entities if isinstance(e, SyrConnectConnectionStateSensor)
    ]
    assert len(connection_sensors) == 1


async def test_async_setup_entry_connection_state_sensor_per_device(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
) -> None:
    """async_setup_entry creates one connection state sensor per device."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"dst": "2"},
            },
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {"dst": "1"},
            },
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities = []

    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    connection_sensors = [
        e for e in entities if isinstance(e, SyrConnectConnectionStateSensor)
    ]
    assert len(connection_sensors) == 2


@pytest.mark.parametrize(
    "crt_value",
    [
        pytest.param(0, id="json-integer"),
        pytest.param("0", id="xml-string"),
    ],
)
async def test_muco_conditional_sensor_creates_ohw_for_hwe_cartridge(
    hass: HomeAssistant,
    crt_value: int | str,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """getCRT=0 (HWE) creates the getOHW sensor and not getLOT."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "model": _signature("conelclearprofill"),
                "status": {"getCRT": crt_value, "getOHW": "5"},
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert "getOHW" in keys
    assert "getLOT" not in keys


async def test_muco_conditional_sensor_switches_live_on_crt_change(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """Changing getCRT live re-evaluates the conditional sensor without a reload."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "model": _signature("conelclearprofill"),
                "status": {"getCRT": "0", "getOHW": "5"},
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    mock_coordinator.entry_id = None
    entities, async_add_entities = mock_add_entities()

    fake_existing_entry = Mock(config_entry_id=None)
    fake_registry = MagicMock()
    fake_registry.async_get.return_value = fake_existing_entry

    with patch(
        "homeassistant.helpers.entity_registry.async_get", return_value=fake_registry
    ):
        await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert "getOHW" in {getattr(e, "_sensor_key", None) for e in entities}

    # Capture the listener registered for live re-sync
    listener = mock_coordinator.async_add_listener.call_args.args[0]

    # Switch cartridge type to HVE (getLOT applies instead of getOHW)
    mock_coordinator.data["devices"][0]["status"] = {"getCRT": "1", "getLOT": "7"}
    entities.clear()
    fake_registry.async_remove.reset_mock()

    with patch(
        "homeassistant.helpers.entity_registry.async_get", return_value=fake_registry
    ):
        listener()

    removed_entity_id = fake_registry.async_remove.call_args.args[0]
    assert removed_entity_id.endswith("_getohw")
    assert "getLOT" in {getattr(e, "_sensor_key", None) for e in entities}


# Devices without an "id" must be skipped by the MuCo conditional sensor sync.
# Note: the main setup loop above indexes device['id']/['name']/['project_id'] directly,
# so the id key must be present (but falsy) rather than omitted.
async def test_muco_conditional_sensor_skips_device_without_id(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """The conditional MuCo sensor sync skips devices without an id."""
    data = {
        "devices": [
            {"id": "", "name": "No ID Device", "project_id": "project1", "status": {}},
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert entities == []


class _FakeRegistry:
    """Minimal registry stand-in so registry_cleanup()/the main setup loop no-op cleanly."""

    entities: dict = {}

    def async_get(self, entity_id: Any) -> None:
        return None

    def async_get_entity_id(self, domain: Any, platform: Any, unique_id: Any) -> None:
        return None

    def async_remove(self, entity_id: Any) -> None:
        return None


# The MuCo conditional sensor sync must swallow registry errors.
async def test_muco_conditional_sensor_sync_registry_exception(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """The conditional MuCo sensor sync logs and returns on registry errors."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {"getCRT": "0", "getOHW": "5"},
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    # er.async_get() is called twice during setup: once in the main sensor loop and once
    # inside the MuCo conditional sync (registry_cleanup() skips without an entry_id) -
    # only the last one should fail, to isolate the except branch under test.
    with patch(
        "homeassistant.helpers.entity_registry.async_get",
        side_effect=[_FakeRegistry(), RuntimeError("boom")],
    ):
        # Should not raise despite the registry accessor failing.
        await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # No conditional MuCo sensor could be added since the registry sync failed.
    assert "getOHW" not in {getattr(e, "_sensor_key", None) for e in entities}


async def test_connection_state_sensor_device_not_found(hass: HomeAssistant) -> None:
    """native_value returns None when device is not in coordinator data."""
    data = {
        "devices": [
            {
                "id": "other_device",
                "name": "Other",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    sensor = _build_connection_state_sensor(hass, data)
    assert sensor.native_value is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        # LEX family: l/min, e.g. 4 l/min = 240 l/h
        ({"getCNA": "LEXplus10S", "getFLO": "4"}, 240),
        ({"getCNA": "LEXplus10SL", "getFLO": 7}, 420),
        ({"getCNA": "LEXplus10", "getFLO": "3"}, 180),
        ({"getCNA": "LEX30", "getFLO": "9"}, 540),
        ({"getCNA": "LEX100", "getFLO": "12"}, 720),
        ({"getCNA": "L20", "getFLO": "5"}, 300),
        ({"getCNA": "L100", "getFLO": "11"}, 660),
        ({"getCNA": "LEXplus10S", "getFLO": "0"}, 0),
        # Rounded after the conversion: 4.5 l/min = 270 l/h
        ({"getCNA": "LEXplus10S", "getFLO": "4.5"}, 270),
        ({"getCNA": "LEXplus10S", "getFLO": "abc"}, None),
        # Other models: l/h
        ({"getVER": "Safe-Tech V4.08", "getFLO": "240"}, 240),
        ({"getSRN": "206AAA12345", "getVER": "NSS.V.2.028", "getFLO": "380"}, 380),
        ({"getSRN": "206AAA12345", "getVER": "NSS.V.2.028", "getFLO": 615}, 615),
        # Unknown model: l/h
        ({"getFLO": "240"}, 240),
    ],
)
def test_sensor_flo_unit_depends_on_model(
    create_mock_coordinator: Callable[..., MagicMock],
    status: dict[str, Any],
    expected: Any,
) -> None:
    """Water flow (getFLO) is shown in l/h; the LEX family reports it in l/min."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": status}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getFLO")

    assert sensor.native_unit_of_measurement == UnitOfVolumeFlowRate.LITERS_PER_HOUR
    assert sensor.native_value == expected


@pytest.mark.parametrize(
    ("key", "raw", "expected", "precision"),
    [
        # The profile reports getLFV in milliliters; liters keep two decimals
        ("getLFV", "6600", 6.6, 2),
        ("getLFV", 6600, 6.6, 2),
        ("getLFV", "10", 0.01, 2),
        ("getLFV", "6604", 6.6, 2),
        # Keys without a profile divisor keep the scale of their description
        ("getCFV", "4", 4, 2),
        ("getCEL", "215", 21.5, 1),
    ],
)
def test_sensor_profile_divide_by_replaces_description_scale(
    create_mock_coordinator: Callable[..., MagicMock],
    key: str,
    raw: Any,
    expected: float,
    precision: int,
) -> None:
    """A device profile can report a key in another scale than its description."""
    model = replace(
        UNKNOWN_MODEL,
        name="testml",
        device_profile=SyrConnectDeviceProfile(
            binary_sensor=set(),
            button=set(),
            select=set(),
            sensor={
                "getCEL",
                "getCFV",
                "getLFV",
            },
            sensor_divisors={
                "getLFV": 1000,
            },
            switch=set(),
            valve=set(),
        ),
    )
    data = {
        "devices": [{"id": "d1", "name": "D1", "model": model, "status": {key: raw}}]
    }
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", key)

    assert sensor.native_value == expected
    assert sensor.suggested_display_precision == precision
    assert _SYR_CONNECT_SENSOR_DESCRIPTIONS["getLFV"].divide_by == 1


@pytest.mark.parametrize(
    ("key", "raw", "unit", "expected"),
    [
        ("getDBT", "15", UnitOfTime.SECONDS, 15),
        ("getDCM", "3", UnitOfTime.MINUTES, 3),
        ("getDOM", "60", UnitOfTime.SECONDS, 60),
        ("getDPL", "10", None, 10),
        ("getDST", "180", UnitOfTime.MINUTES, 180),
        ("getDTC", "3", None, 3),
    ],
)
def test_sensor_microleakage_test_parameters(
    create_mock_coordinator: Callable[..., MagicMock],
    key: str,
    raw: str,
    unit: str | None,
    expected: int,
) -> None:
    """Microleakage test parameters are shown as numbers with their unit."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": {key: raw}}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", key)

    assert sensor.native_unit_of_measurement == unit
    assert sensor.native_value == expected
    assert sensor.entity_registry_enabled_default is False


@pytest.mark.parametrize("key", ["getAPT", "getPRN", "getSLO", "getSOF", "getTMZ"])
def test_sensor_settings_disabled_by_default(
    create_mock_coordinator: Callable[..., MagicMock], key: str
) -> None:
    """Rarely changed settings are disabled by default."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": {key: "4"}}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", key)

    assert sensor.entity_registry_enabled_default is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # SafeTech: seconds
        ("60", 60),
        (45, 45),
        # Safe-T+: with unit in minutes
        ("1 min", 60),
        ("2min", 120),
        (" 3 MIN ", 180),
        # Unit without a number
        ("min", None),
        ("abc min", None),
    ],
)
def test_sensor_dom_seconds(
    create_mock_coordinator: Callable[..., MagicMock], raw: Any, expected: Any
) -> None:
    """Microleakage test valve open time (getDOM) is shown in seconds in both formats."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": {"getDOM": raw}}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getDOM")

    assert sensor.native_value == expected


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("SyrSafeTechV4", 0),
        ("SyrSafeTechPlus", 0),
        # The validity matrix lists a conductivity sensor for NeoSoft 5000 only
        ("SyrNeoSoft5000", 10),
        # NeoSoft 2500 reports getCNL as empty string, it measures no conductivity
        ("SyrNeoSoft2500", None),
        # TRIO Lock has no conductivity sensor
        ("SyrTrioLock", None),
    ],
)
async def test_async_setup_entry_conductivity_limit(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    model: str,
    expected: int | None,
) -> None:
    """The conductivity limit (getCNL) is only created for models that measure conductivity.

    `expected` is the shown value, or None when the sensor is not created.
    """
    xml = (
        Path(__file__).parent / f"fixtures/xml/{model}_GetDeviceCollectionStatus.xml"
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

    cnl = [e for e in entities if getattr(e, "_sensor_key", None) == "getCNL"]
    assert bool(cnl) is (expected is not None)
    if expected is not None:
        assert cnl[0].native_unit_of_measurement == (
            UnitOfConductivity.MICROSIEMENS_PER_CM
        )
        assert cnl[0].native_value == expected


async def test_async_setup_entry_turbine_no_pulse_max_time(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """SafeTech V4 shows the time without turbine pulses until alarm A8 (getTTM) in days."""
    xml = (
        Path(__file__).parent
        / "fixtures/xml/SyrSafeTechV4_GetDeviceCollectionStatus.xml"
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

    ttm = [e for e in entities if getattr(e, "_sensor_key", None) == "getTTM"]
    assert len(ttm) == 1
    assert ttm[0].native_unit_of_measurement == UnitOfTime.DAYS
    assert ttm[0].native_value == 30
    assert ttm[0].entity_registry_enabled_default is False


@pytest.mark.parametrize("key", ["getLE", "getT1", "getUL"])
@pytest.mark.parametrize("raw", ["abc", "1.5", [1]])
def test_mapped_int_sensor_invalid_value_returns_none(key: str, raw: Any) -> None:
    """A non-integer raw value of a mapped sensor gives None instead of raising."""
    coordinator = MagicMock()
    coordinator.entry_id = None
    coordinator.data = {
        "devices": [
            {"id": "dev", "name": "Dev", "project_id": "p1", "status": {key: raw}}
        ]
    }

    sensor = SyrConnectSensor(coordinator, "dev", "Dev", key)

    assert sensor._compute_native_value() is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", 1),  # XML
        (1, 1),  # JSON
        ("99", 99),
        ("0", 0),
    ],
)
def test_sensor_t2_minutes(
    create_mock_coordinator: Callable[..., MagicMock], raw: Any, expected: Any
) -> None:
    """Maximum flow leakage time (getT2) is shown in minutes, without a value map."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": {"getT2": raw}}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getT2")

    assert sensor.native_unit_of_measurement == UnitOfTime.MINUTES
    assert sensor.native_value == expected


def test_sensor_value_fns_infinite_value_returns_none() -> None:
    """Infinity cannot be converted to int (OverflowError) and gives no value."""
    percentage_sensor = MagicMock(native_unit_of_measurement=UnitOfRatio.PERCENTAGE)
    assert sensor_module._value_bat(percentage_sensor, {}, "inf") is None
    assert sensor_module._value_rpw(MagicMock(), {}, "inf") is None
    assert sensor_module._value_crs(MagicMock(), {}, "inf") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (45, 45),  # NeoSoft, Sanibel UNO, Conel Clear Pro Soft (JSON)
        ("45", 45),  # same devices (XML)
        (0, 0),
        ("12:30", 12.5),  # LEX, L20: minutes:seconds
        ("00:00", 0),
        ("abc", None),
        ("1:2:3", None),
        ("", None),
    ],
)
def test_sensor_cyt_minutes(
    create_mock_coordinator: Callable[..., MagicMock], raw: Any, expected: Any
) -> None:
    """Remaining regeneration time (getCYT) in minutes, from a number or minutes:seconds."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": {"getCYT": raw}}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getCYT")

    assert sensor.native_unit_of_measurement == UnitOfTime.MINUTES
    assert sensor.native_value == expected


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("SyrSafeTechV4", {"getLWT", "getSLO", "getSMF", "getSOF"}),
        # getSOF is reported empty by these captures
        ("SyrSafeTechPlus", {"getLWT", "getSLO", "getSMF"}),
        ("SyrTrioDFRLS", {"getLWT", "getSLO", "getSMF"}),
        # The 10 SL reports no getSMF/getSOF
        ("SyrLEXplus10SL", {"getLWT", "getSLO"}),
        # The MultiController captures report no getSOF via XML
        ("SyrTrioLock", {"getLWT", "getSLO", "getSMF"}),
        ("ConelClearProLeakProtection", {"getLWT", "getSLO", "getSMF"}),
        # Filling controller: no leak protection
        ("ConelClearProFill", set()),
    ],
)
def test_leak_protection_settings(model: str, expected: set[str]) -> None:
    """Leakage warning threshold and self-learning settings follow the model allowlists."""
    xml = (
        Path(__file__).parent / f"fixtures/xml/{model}_GetDeviceCollectionStatus.xml"
    ).read_text(encoding="utf-8")
    status = ResponseParser().parse_device_status_response(xml)
    assert status is not None

    keys = set(sensor_module.sensor_keys_for_status(status, detect_model(status)))

    assert keys & {"getLWT", "getSLO", "getSMF", "getSOF"} == expected


# getSLP is a documented key that never becomes a sensor (hidden_when="always")
_SELF_LEARNING_KEYS = {"getSLE", "getSLF", "getSLT", "getSLV"}
_MICROLEAKAGE_KEYS = {"getDBD", "getDMA", "getDRP", "getDSV", "getDTT", "getNPS"}


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        # Official API: self-learning phase and microleakage test on these models
        (
            "ConelClearProLeakProtection.json",
            _SELF_LEARNING_KEYS | _MICROLEAKAGE_KEYS,
        ),
        (
            "SanibelLeakProtectionModuleA25_get_all.json",
            _SELF_LEARNING_KEYS | _MICROLEAKAGE_KEYS,
        ),
        ("SyrTrioLock_get_all.json", _SELF_LEARNING_KEYS | _MICROLEAKAGE_KEYS),
        ("SyrSafeTechPlus_get_all.json", _SELF_LEARNING_KEYS | _MICROLEAKAGE_KEYS),
        ("SyrTrioDFRLS_get_all.json", _SELF_LEARNING_KEYS | _MICROLEAKAGE_KEYS),
        # Filling controller: neither
        ("ConelClearProFill_get_all.json", set()),
    ],
)
def test_self_learning_and_microleakage_follow_official_matrix(
    fixture: str, expected: set[str]
) -> None:
    """Self-learning phase and microleakage test sensors follow the official validity matrix."""
    status = json.loads(
        (Path(__file__).parent / "fixtures/json" / fixture).read_text(encoding="utf-8")
    )

    keys = set(sensor_module.sensor_keys_for_status(status, detect_model(status)))

    assert keys & (_SELF_LEARNING_KEYS | _MICROLEAKAGE_KEYS) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("4", "UTC+01:00"),  # Germany (CET)
        (4, "UTC+01:00"),  # JSON API
        ("22", "UTC+05:30"),  # India
        ("-14", "UTC-03:30"),  # Newfoundland
        ("0", "UTC+00:00"),
        ("-44", "UTC-11:00"),
        ("48", "UTC+12:00"),
        ("49", None),
        ("-45", None),
        ("", None),
        ("abc", None),
    ],
)
def test_sensor_tmz_utc_offset(
    create_mock_coordinator: Callable[..., MagicMock], raw: Any, expected: str | None
) -> None:
    """Time zone (getTMZ) in quarter hours is shown as UTC offset."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": {"getTMZ": raw}}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getTMZ")

    assert sensor.native_value == expected


@pytest.mark.parametrize(
    ("now", "raw", "expected"),
    [
        # Germany, winter (CET, UTC+1)
        (datetime(2026, 1, 15, 12, 0, tzinfo=UTC), "04:00", "05:00"),
        # Germany, summer (CEST, UTC+2)
        (datetime(2026, 7, 15, 12, 0, tzinfo=UTC), "04:00", "06:00"),
        # Crosses midnight
        (datetime(2026, 1, 15, 12, 0, tzinfo=UTC), "23:30", "00:30"),
        (datetime(2026, 1, 15, 12, 0, tzinfo=UTC), "", None),
        (datetime(2026, 1, 15, 12, 0, tzinfo=UTC), "25:00", None),
        (datetime(2026, 1, 15, 12, 0, tzinfo=UTC), "abc", None),
    ],
)
async def test_sensor_dtt_utc_to_local_time(
    hass: HomeAssistant, now: datetime, raw: str, expected: str | None
) -> None:
    """Microleakage test time (getDTT) is stored as UTC and shown in the Home Assistant time zone."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getDTT": raw},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getDTT")

    with patch.object(sensor_module.dt_util, "utcnow", return_value=now):
        assert sensor.native_value == expected


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("SyrSafeTechV4", True),
        ("SyrNeoSoft2500", True),
        ("SyrLEXplus10SL", True),
        # Reported empty
        ("SyrSafeTechPlus", False),
        ("SyrTrioDFRLS", False),
    ],
)
def test_sensor_tmz_follows_allowlists(model: str, expected: bool) -> None:
    """The time zone sensor is created on the models that report it."""
    xml = (
        Path(__file__).parent / f"fixtures/xml/{model}_GetDeviceCollectionStatus.xml"
    ).read_text(encoding="utf-8")
    status = ResponseParser().parse_device_status_response(xml)
    assert status is not None

    assert (
        "getTMZ" in sensor_module.sensor_keys_for_status(status, detect_model(status))
    ) is expected


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("SyrSafeTechV4", 2.0),
        ("SyrSafeTechPlus", 1.0),
        ("ConelClearProFill", 1.0),
        # No conductivity measurement on these models
        ("SyrTrioDFRLS", None),
        ("SyrTrioLock", None),
    ],
)
def test_conductivity_factor(
    create_mock_coordinator: Callable[..., MagicMock],
    model: str,
    expected: float | None,
) -> None:
    """Conductivity factor (getCNF): raw 5-50 is shown as 0.5-5.0, only on models that measure conductivity."""
    xml = (
        Path(__file__).parent / f"fixtures/xml/{model}_GetDeviceCollectionStatus.xml"
    ).read_text(encoding="utf-8")
    status = ResponseParser().parse_device_status_response(xml)
    assert status is not None

    keys = set(sensor_module.sensor_keys_for_status(status, detect_model(status)))
    if expected is None:
        assert "getCNF" not in keys
        return

    assert "getCNF" in keys
    data = {"devices": [{"id": "d1", "name": "D1", "status": status}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getCNF")
    assert sensor.native_value == expected


def test_owh_sensor_without_cartridge_type_always_applies() -> None:
    """A softener reports getOWH without getCRT, there it is the outlet water hardness."""
    status = {"getOWH": "7", "getWHU": "0"}

    keys = sensor_module.sensor_keys_for_status(status, _signature("lex30"))

    assert keys.count("getOWH") == 1
    assert "getOWH" not in sensor_module._hidden_sensor_keys(
        status, _signature("lex30")
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param({"getCRS": "3"}, 7, id="fixed-size"),
        pytest.param({"getCRS": "0", "getFCS": "20"}, 20.0, id="custom-size"),
        pytest.param({"getCRS": "0"}, None, id="custom-size-missing"),
    ],
)
def test_crs_sensor_custom_size(status: dict[str, Any], expected: float | None) -> None:
    """The custom cartridge size (getCRS 0) of the All-in-One+ is the liters of getFCS."""
    assert sensor_module._value_crs(MagicMock(), status, status["getCRS"]) == expected


@pytest.mark.parametrize(
    ("model", "key", "whu", "raw", "expected", "unit"),
    [
        # The MuCo filling keeps °dH; getWHU is only the unit of the display
        ("conelclearprofill", "getIWH", "0", "18", 18, "°dH"),
        ("conelclearprofill", "getIWH", "1", "18", 23, "°e"),
        ("conelclearprofill", "getOHW", "2", "5", 9, "°fH"),
        ("conelclearprofill", "getOHW", 3, 5, 89, "ppm"),
        ("conelclearprofill", "getOHW", "7", "5", 5, "°dH"),
        # Other families report the value in the unit
        ("allinoneplus", "getIWH", "1", "18", 18, "°e"),
    ],
)
def test_sensor_hardness_converted_from_dh(
    create_mock_coordinator: Callable[..., MagicMock],
    model: str,
    key: str,
    whu: Any,
    raw: Any,
    expected: int,
    unit: str,
) -> None:
    """A device that keeps the water hardness in °dH shows it in the unit of getWHU."""
    status = {key: raw, "getWHU": whu}
    data = {
        "devices": [
            {"id": "d1", "name": "D1", "model": _signature(model), "status": status}
        ]
    }
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", key)

    assert sensor.native_value == expected
    assert sensor.native_unit_of_measurement == unit


def _rpw_sensor(
    create_mock_coordinator: Callable[..., MagicMock],
    raw: object,
    language: str = "en",
) -> SyrConnectSensor:
    """Return a getRPW sensor of a Home Assistant instance with the given language."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": {"getRPW": raw}}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getRPW")
    sensor.hass = MagicMock()
    sensor.hass.config.language = language
    return sensor


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(127, "Mon,Tue,Wed,Thu,Fri,Sat,Sun", id="all-days"),
        pytest.param("5", "Mon,Wed", id="text"),
        pytest.param(5.0, "Mon,Wed", id="float"),
        pytest.param(64, "Sun", id="highest-bit"),
        pytest.param(0, "0", id="zero"),
        pytest.param("0", "0", id="zero-text"),
        pytest.param("", None, id="empty"),
        pytest.param("invalid", None, id="no-number"),
        pytest.param(None, None, id="none"),
    ],
)
def test_sensor_rpw_weekdays(
    create_mock_coordinator: Callable[..., MagicMock], raw: object, expected: str | None
) -> None:
    """Permitted regeneration weekdays (getRPW): bit 1 is Monday; 0 is "not specified"."""
    assert _rpw_sensor(create_mock_coordinator, raw).native_value == expected


def test_sensor_rpw_weekdays_in_home_assistant_language(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The weekday names follow the language of Home Assistant."""
    sensor = _rpw_sensor(create_mock_coordinator, 127, language="de")

    assert sensor.native_value == "Mo.,Di.,Mi.,Do.,Fr.,Sa.,So."


def test_sensor_rpw_weekdays_before_added_to_hass(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Without a Home Assistant instance the names are formatted without a language."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": {"getRPW": 3}}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getRPW")

    with patch(
        "custom_components.syr_connect.sensor.format_datetime", return_value="day"
    ) as mock_format:
        assert sensor.native_value == "day,day"

    assert [call.kwargs for call in mock_format.call_args_list] == [
        {"locale": None},
        {"locale": None},
    ]


def test_sensor_rpw_weekdays_without_babel_locale(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """If Babel cannot format the names, the short names of the system are used."""
    sensor = _rpw_sensor(create_mock_coordinator, 127)

    with patch(
        "custom_components.syr_connect.sensor.format_datetime",
        side_effect=ValueError("unknown locale"),
    ):
        assert sensor.native_value == "Mon,Tue,Wed,Thu,Fri,Sat,Sun"


@pytest.mark.parametrize("value", [None, "", "   "])
async def test_sensor_setup_hides_sensor_without_value(
    hass: HomeAssistant, value: str | None
) -> None:
    """A sensor that is hidden while it is empty (getCEL) is not created without a value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getCEL": value, "getPRS": "50"},
            }
        ]
    }
    entry = _build_entry(_build_coordinator(hass, data))
    entry.add_to_hass(hass)
    add_entities = Mock()

    await async_setup_entry(hass, entry, add_entities)

    keys = {entity._sensor_key for entity in _added_entities(add_entities)}
    assert "getPRS" in keys
    assert "getCEL" not in keys
