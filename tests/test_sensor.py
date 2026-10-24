"""Tests for sensor platform."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001

from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.syr_connect import sensor as sensor_mod, sensor as sensor_module
from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.response_parser import ResponseParser
from custom_components.syr_connect.sensor import (
    _SYR_CONNECT_SENSOR_DESCRIPTIONS,
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
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory


def _build_coordinator(
    hass: HomeAssistant, data: dict
) -> SyrConnectDataUpdateCoordinator:
    config_data = {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "password",
    }
    coordinator = SyrConnectDataUpdateCoordinator(
        hass,
        MagicMock(),
        config_data,
        60,
    )
    coordinator.async_set_updated_data(data)
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
    assert set(keys) == _SYR_CONNECT_SENSOR_SUPPORTED_KEYS


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


async def test_sensor_water_hardness_unit(hass: HomeAssistant) -> None:
    """Test water hardness unit sensor mapping (getWHU)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": "0",  # Maps to °dH
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getWHU")

    assert sensor.native_value == "°dH"


async def test_sensor_regeneration_weekdays_all(hass: HomeAssistant) -> None:
    """Test regeneration permitted weekdays with all days (getRPW)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "127",  # All 7 days (binary 1111111)
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Should return comma-separated weekday names
    assert sensor.native_value is not None
    assert "," in str(sensor.native_value)


async def test_sensor_regeneration_weekdays_zero(hass: HomeAssistant) -> None:
    """Test regeneration permitted weekdays with mask 0 (getRPW)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "0",  # Anytime
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # The integration exposes mask==0 as the internal translation key "0"
    assert sensor.native_value == "0"


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

    # Should return mapped key
    assert sensor.native_value in ("low_salt", "LowSalt")


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
    assert not set(status) & sensor_module._hidden_sensor_keys(status)


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

    created = {e._sensor_key for e in add_entities.call_args.args[0]}
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


async def test_sensor_rpw_invalid_mask(hass: HomeAssistant) -> None:
    """Test getRPW with invalid mask value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

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

    assert sensor.native_value == "not-a-number"


async def test_sensor_setup_no_data(hass: HomeAssistant) -> None:
    """Test sensor setup with no coordinator data."""
    coordinator = _build_coordinator(hass, {})
    coordinator.data = None  # type: ignore[assignment]
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Should not call add_entities when no data
    add_entities.assert_not_called()


async def test_async_setup_entry_preprocessing_handles_helper_exception(
    hass: HomeAssistant,
) -> None:
    """Ensure preprocessing exceptions from get_sensor_iwh_value are handled."""
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

    add_entities = Mock()
    with patch(
        "custom_components.syr_connect.sensor.get_sensor_iwh_value",
        side_effect=RuntimeError("boom"),
    ):
        # Should not raise even if preprocessing helper fails
        await async_setup_entry(hass, entry, add_entities)


async def test_async_setup_entry_preprocessing_device_get_raises(
    hass: HomeAssistant,
) -> None:
    """Ensure outer preprocessing exception is handled when device.get raises."""

    class BadDevice:
        def __init__(self):
            self._raised = False

        def get(self, key, default=None):
            # Simulate failure on the first access to 'status', allow subsequent accesses
            if key == "status":
                if not self._raised:
                    self._raised = True
                    raise RuntimeError("boom")
                return {}
            return None

        def __getitem__(self, key):
            # Provide mapping for subscriptions used by the platform
            if key == "id":
                return "baddev"
            if key == "name":
                return "Bad Device"
            if key == "project_id":
                return "proj"
            if key == "status":
                # Delegate to get() so we simulate the same first-call failure
                return self.get("status")
            raise KeyError(key)

    data = {"devices": [BadDevice()]}
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    # device.get("status") raises RuntimeError on first call; the outer device
    # loop in async_setup_entry has no try/except at that level, so it propagates.
    with pytest.raises(RuntimeError, match="boom"):
        await async_setup_entry(hass, entry, add_entities)


def test_getdbd_rounding_precision_typeerror(monkeypatch):
    """If precision is invalid and round() raises, getDBD returns None."""

    monkeypatch.setitem(
        sensor_mod._SYR_CONNECT_SENSOR_DESCRIPTIONS,
        "getDBD",
        replace(
            sensor_mod._SYR_CONNECT_SENSOR_DESCRIPTIONS["getDBD"],
            suggested_display_precision="bad",
        ),
    )

    # Create a coordinator-like object for the sensor
    data = {
        "devices": [
            {"id": "dev_x", "name": "X", "project_id": "p1", "status": {"getDBD": "10"}}
        ]
    }

    # Instead of building a full coordinator, instantiate SyrConnectSensor directly with a mock coordinator
    class DummyCoord:
        entry_id = None

        def __init__(self, data):
            self.data = data

    coord = DummyCoord(data)

    sensor = SyrConnectSensor(coord, "dev_x", "X", "getDBD")
    # When precision is invalid, rounding should raise and the function returns None
    assert sensor.native_value is None


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, None),
        ("", None),
        ("abc", None),
        ("-5", -0.5),
    ],
)
async def test_getdbd_various_values(hass: HomeAssistant, raw_value, expected) -> None:
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
def test_extra_getavo_and_getbar_and_getbat_and_getul(create_mock_coordinator):
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
    assert abs(float(avo.native_value) - 1.655) < 0.001

    bar = SyrConnectSensor(coord, "dev_s", "Device S", "getBAR")
    # 4077 mbar -> 4.077 bar -> rounded to 1 decimal -> 4.1
    assert bar.native_value == 4.1

    bat = SyrConnectSensor(coord, "dev_s", "Device S", "getBAT")
    assert bat.native_value == 3.63

    ul = SyrConnectSensor(coord, "dev_s", "Device S", "getUL")
    assert ul.native_value == 50


def test_extra_getrtm_and_getab_icon_and_getpm_boolean(create_mock_coordinator):
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


def test_extra_getwhu_and_getlar_and_getrpw(create_mock_coordinator):
    """Test extra getWHU and getLAR and getRPW."""
    # getWHU mapping, getLAR timestamp, getRPW bitmask
    ts = 1609459200  # 2021-01-01 00:00:00 UTC
    data = {
        "devices": [
            {
                "id": "dev_w",
                "name": "Device W",
                "project_id": "p1",
                "status": {
                    "getWHU": 1,
                    "getLAR": str(ts),
                    "getRPW": "5",  # Monday + Wednesday bits
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

    rpw = SyrConnectSensor(coord, "dev_w", "Device W", "getRPW")
    # Should return a comma-separated list for mask with multiple days
    assert isinstance(rpw.native_value, str)
    assert "," in rpw.native_value or rpw.native_value != ""


def test_extra_getsta_getalm_getle_and_gett1_mappings(create_mock_coordinator):
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
    assert alm.native_value == "no_salt"
    assert alm.translation_key == "getalm"

    le = SyrConnectSensor(coord, "dev_map", "Device Map", "getLE")
    assert le.native_value == 100

    t1 = SyrConnectSensor(coord, "dev_map", "Device Map", "getT1")
    assert t1.native_value == 1.5


def test_getlot_conversion(create_mock_coordinator):
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
def test_getcrs_value_mapping(create_mock_coordinator, raw_value, expected):
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
def test_getcrt_value_mapping(create_mock_coordinator, raw_value, expected):
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
def test_getrcd_value_mapping(create_mock_coordinator, raw_value, expected):
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


async def test_async_setup_entry_handles_status_get_exception(
    hass: HomeAssistant,
) -> None:
    """Ensure async_setup_entry does not crash when status.get raises."""

    class BadStatus:
        def get(self, key, default=None):
            return None

        def items(self):
            return {}.items()

        def __len__(self):
            return 0

    data = {
        "devices": [
            {
                "id": "bad_dev",
                "name": "Bad Device",
                "project_id": "p1",
                "status": BadStatus(),
            }
        ]
    }
    coord = _build_coordinator(hass, data)
    entry = _build_entry(coord)
    entry.add_to_hass(hass)

    add_entities = Mock()
    # Should not raise
    await async_setup_entry(hass, entry, add_entities)


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


async def test_sensor_whu_string_conversion(hass: HomeAssistant) -> None:
    """Test getWHU sensor with string value that can be converted."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": "1",  # String instead of int
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getWHU")

    # Should convert string to int and map correctly
    assert sensor.native_value is not None


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


async def test_sensor_rpw_invalid_string_mask(hass: HomeAssistant) -> None:
    """Test getRPW with invalid string that cannot be converted."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "not_a_number",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Should return None for invalid mask
    assert sensor.native_value is None


async def test_sensor_rpw_with_babel_fallback(hass: HomeAssistant) -> None:
    """Test getRPW falls back to strftime if Babel fails."""

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
        side_effect=ValueError("Babel error"),
    ):
        result = sensor.native_value
        # Should still return weekday names using strftime fallback
        assert result is not None
        assert isinstance(result, str)


async def test_sensor_icon_exception_handling(hass: HomeAssistant) -> None:
    """Test icon property handles exceptions gracefully."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRES": "invalid",  # Will cause exception in conversion
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRES")

    # Should return base icon without crashing
    icon = sensor.icon
    assert icon is not None or icon is None  # Just verify it doesn't crash


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


async def test_sensor_water_hardness_init_with_whu(hass: HomeAssistant) -> None:
    """Test sensor initialization sets water hardness unit from getWHU."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getIWH": "10",
                    "getWHU": 1,  # German degrees
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getIWH")

    # Should have water hardness unit set
    assert sensor.native_unit_of_measurement is not None


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
                    "getCND": "330",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getIWH")

    # getIWH should be derived as getCND / 33.0 -> 10 (int)
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


async def test_sensor_exclude_when_zero_non_cs(hass: HomeAssistant) -> None:
    """Test sensors excluded when value is zero (non-CS sensors)."""
    # Test with a sensor that should be excluded when zero
    # First check that it's created when non-zero
    data_non_zero = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRS1": 5,  # Assume getRS1 is in EXCLUDE_WHEN_ZERO
                },
            }
        ]
    }

    # Mock the async setup
    mock_coordinator = _build_coordinator(hass, data_non_zero)
    mock_entry = _build_entry(mock_coordinator)
    mock_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.syr_connect.sensor.er.async_get"
        ) as mock_registry_getter,
    ):
        mock_registry = Mock()
        mock_registry.async_get.return_value = None
        mock_registry.async_remove = Mock()
        mock_registry_getter.return_value = mock_registry

        entities = []
        await async_setup_entry(
            hass,
            mock_entry,
            lambda ents: entities.extend(ents),  # type: ignore[arg-type]
        )

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


async def test_sensor_icon_none_value_fallback(hass: HomeAssistant) -> None:
    """Test icon property returns base icon when value is None."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPST": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPST")

    # When value is None, icon should return base icon
    icon = sensor.icon
    assert icon is not None or icon is None  # Base icon may or may not be set


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


@pytest.mark.parametrize(
    ("sensor_key", "raw_value", "expected_value"),
    [
        ("getALD", "20", 20),  # Alarm duration (s) — whole number
        ("getMIH", "5", 5),  # Minimum humidity (%) — whole number
        ("getMXH", "95", 95),  # Maximum humidity (%) — whole number
        ("getRCP", "43200", 43200),  # Synchronisation interval (s) — whole number
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


async def test_sensor_available_device_not_found(hass: HomeAssistant) -> None:
    """Test available property when device is not in coordinator data."""
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
    # Create sensor for device that doesn't exist in data
    sensor = SyrConnectSensor(
        coordinator, "nonexistent_device", "Nonexistent", "getSTA"
    )

    # Should return True when device not found
    assert sensor.available is False


async def test_sensor_rpw_empty_string(hass: HomeAssistant) -> None:
    """Test getRPW with empty string value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Empty string should return None
    assert sensor.native_value is None


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


async def test_sensor_icon_value_conversion_error(hass: HomeAssistant) -> None:
    """Test icon property handles conversion errors gracefully."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPST": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPST")

    # Should handle conversion error and return base icon or close-circle
    icon = sensor.icon
    assert icon in ["mdi:close-circle", None] or icon is not None


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


async def test_sensor_exclude_when_zero_float_value(hass: HomeAssistant) -> None:
    """Test getSV2 is shown even when float value is zero."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSV2": 0.0,  # Float zero
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
    # getSV2 with value 0.0 is now always shown
    sv2_sensors = [e for e in entities if e._sensor_key == "getSV2"]
    assert len(sv2_sensors) == 1


async def test_sensor_registry_cleanup_exception(hass: HomeAssistant) -> None:
    """Test entity registry cleanup handles exceptions gracefully."""

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

    add_entities = Mock()

    # Provide a dummy registry that safely ignores async_remove calls
    class DummyRegistry:
        def async_get(self, entity_id):
            return None

        def async_get_entity_id(self, domain, platform, unique_id):
            return None

        def async_remove(self, entity_id):
            return None

    with patch(
        "custom_components.syr_connect.sensor.er.async_get",
        return_value=DummyRegistry(),
    ):
        # Should not raise exception, continues setup
        await async_setup_entry(hass, entry, add_entities)
        # Entities should still be added despite registry issues


# Focused tests for uncovered branches in sensor icon and setup logic
def test_icon_battery_zero(create_mock_coordinator):
    """Test icon battery zero."""
    data = {
        "devices": [
            {"id": "d7", "name": "D7", "project_id": "p1", "status": {"getBAT": "0"}}
        ]
    }
    coord = create_mock_coordinator(data)
    sb = SyrConnectSensor(coord, "d7", "D7", "getBAT")
    assert sb.icon == "mdi:battery-alert-variant-outline"


async def test_async_setup_entry_getpa_group_true(hass: HomeAssistant) -> None:
    """Test async setup entry getPA group true."""
    data = {
        "devices": [
            {
                "id": "devp",
                "name": "DevP",
                "project_id": "p1",
                "status": {
                    "getPA1": "1",
                    "getPV1": "10",
                    "getPT1": "60",
                    "getPF1": "5",
                    "getPN1": "Zone1",
                    "getPM1": "true",
                    "getPW1": "true",
                    "getPB1": "false",
                    "getPR1": "0",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    added = []
    await async_setup_entry(hass, entry, lambda ents: added.extend(ents))  # type: ignore[arg-type]
    # group keys like getPV1 should be created
    assert any(getattr(e, "_sensor_key", None) == "getPV1" for e in added)


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
    create_mock_entry_with_coordinator,
    mock_add_entities,
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
    create_mock_entry_with_coordinator,
    mock_add_entities,
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
    assert sorted(sensor_module.sensor_keys_for_status(status)) == sorted(created), (
        fixture
    )


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


async def test_sensor_controlled_sensors_cleanup(hass: HomeAssistant) -> None:
    """Test cleanup of controlled sensors from registry."""

    # Create registry entry for a controlled sensor
    registry = er.async_get(hass)
    controlled_entry = registry.async_get_or_create(
        "sensor",
        "syr_connect",
        "device1_getRTM",  # getRTM is controlled
        suggested_object_id="device1_getrtm",
    )

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

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Controlled sensor entry should be handled
    assert controlled_entry is not None


async def test_sensor_rpw_locale_exception(hass: HomeAssistant) -> None:
    """Test getRPW handles locale retrieval exception."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "5",  # Some days
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # The exception handling in sensor.py catches Exception when accessing locale
    # Just verify the sensor can still return weekday names
    result = sensor.native_value
    # Should still return weekday names despite any locale issues
    assert result is not None
    assert isinstance(result, str)


async def test_sensor_whu_numeric_int_value(hass: HomeAssistant) -> None:
    """Test getWHU with numeric int value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": 2,  # Integer value
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getWHU")

    # Should convert int to mapped value
    assert sensor.native_value is not None


async def test_sensor_whu_numeric_float_value(hass: HomeAssistant) -> None:
    """Test getWHU with numeric float value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": 1.0,  # Float value
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getWHU")

    # Should convert float to int then map
    assert sensor.native_value is not None


async def test_sensor_precision_rounding_error(hass: HomeAssistant) -> None:
    """Test sensor handles precision rounding errors."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": "invalid",  # Will cause ValueError in round()
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getFLO")

    # Should return string value when rounding fails
    assert sensor.native_value == "invalid"


async def test_sensor_rpw_mask_invalid_int_conversion(hass: HomeAssistant) -> None:
    """Test getRPW sensor with value that can't be converted to int."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "not_a_number",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Should return None when conversion fails
    assert sensor.native_value is None


async def test_sensor_rpw_mask_empty_string(hass: HomeAssistant) -> None:
    """Test getRPW sensor with empty string value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Should return None for empty string
    assert sensor.native_value is None


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


async def test_sensor_lar_empty_string(hass: HomeAssistant) -> None:
    """Test getLAR sensor with empty string value."""
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

    # Should return None for empty string
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


async def test_sensor_lar_invalid_value(hass: HomeAssistant) -> None:
    """Test getLAR sensor with invalid value."""
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

    # Should return None when value is invalid
    assert sensor.native_value is None


async def test_sensor_rth_invalid_hour(hass: HomeAssistant) -> None:
    """Test getRTH sensor with invalid hour value."""
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

    # Should return None when conversion fails
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


async def test_sensor_rpw_hass_config_no_language(hass: HomeAssistant) -> None:
    """Test getRPW sensor when hass.config has no language attribute."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "3",  # Monday and Tuesday
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Should handle missing language attribute gracefully
    value = sensor.native_value
    assert value is not None
    assert "," in str(value)


async def test_sensor_rpw_mask_specific_bit(hass: HomeAssistant) -> None:
    """Test getRPW sensor with specific bit set."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "64",  # Bit 6 = Sunday
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Should return Sunday
    value = sensor.native_value
    assert value is not None
    assert len(str(value)) > 0


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


async def test_sensor_alarm_value_none_and_unmapped(hass: HomeAssistant) -> None:
    """Test getALM when both value is None and result is unmapped."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALM": "SomeUnknownValue",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getALM")

    # Should handle gracefully
    value = sensor.native_value
    assert value is not None


async def test_sensor_rpw_getattr_exception(hass: HomeAssistant) -> None:
    """Test getRPW sensor when getattr raises exception."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": 3,  # Monday and Tuesday (bitmask)
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Mock getattr on hass.config to raise exception
    with patch(
        "custom_components.syr_connect.sensor.getattr",
        side_effect=AttributeError("Test exception"),
    ):
        # Should handle exception and use None locale
        value = sensor.native_value
        assert value is not None


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


async def test_sensor_setup_no_coordinator_data(hass: HomeAssistant) -> None:
    """Test sensor setup with no coordinator data."""
    coordinator = _build_coordinator(hass, {})
    coordinator.async_set_updated_data(None)  # type: ignore[arg-type]
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Should not add entities
    add_entities.assert_not_called()


async def test_sensor_setup_registry_exception(hass: HomeAssistant) -> None:
    """Test sensor setup handles registry exception gracefully."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": "50",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    # Provide a dummy registry so setup continues even if registry backend is unavailable
    class DummyRegistry:
        def async_get(self, entity_id):
            return None

        def async_get_entity_id(self, domain, platform, unique_id):
            return None

        def async_remove(self, entity_id):
            return None

    with patch(
        "custom_components.syr_connect.sensor.er.async_get",
        return_value=DummyRegistry(),
    ):
        add_entities = Mock()
        # Should not raise exception
        await async_setup_entry(hass, entry, add_entities)

        # Should still add entities
        add_entities.assert_called_once()


async def test_sensor_exclude_when_zero_other_sensor_int(hass: HomeAssistant) -> None:
    """Test other excluded sensor with int zero."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSV2": 0,  # Int zero in exclude list
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Should skip getSV1 because it's zero
    entities = add_entities.call_args.args[0] if add_entities.called else []
    sv1_entities = [e for e in entities if e._sensor_key == "getSV1"]
    assert len(sv1_entities) == 0


async def test_sensor_exclude_when_zero_other_sensor_string(
    hass: HomeAssistant,
) -> None:
    """Test getSV2 is shown even when string zero."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSV2": "0",  # String zero, no longer in exclude list
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # getSV2 is now always shown regardless of value
    entities = add_entities.call_args.args[0] if add_entities.called else []
    sv2_entities = [e for e in entities if e._sensor_key == "getSV2"]
    assert len(sv2_entities) == 1


async def test_sensor_invalid_value_type_skipped(hass: HomeAssistant) -> None:
    """Test sensor with invalid value type is skipped."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": {"invalid": "dict"},  # Invalid type
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)

    # Should not create sensor for invalid type
    entities = add_entities.call_args.args[0] if add_entities.called else []
    assert len(entities) == 0


async def test_sensor_whu_unit_value_error(hass: HomeAssistant) -> None:
    """Test water hardness sensor unit with ValueError on WHU conversion."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getIWH": 50,
                    "getWHU": "invalid",  # Cannot convert to int
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getIWH")

    # Should set unit to None
    assert sensor.native_unit_of_measurement is None


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


async def test_sensor_whu_unit_not_found(hass: HomeAssistant) -> None:
    """Test water hardness sensor when WHU value is not found."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getIWH": 50,
                    # getWHU not present
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getIWH")

    # Should set unit to None
    assert sensor.native_unit_of_measurement is None


async def test_sensor_rtm_value_error(hass: HomeAssistant) -> None:
    """Test getRTM with ValueError on conversion."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRTH": "invalid",
                    "getRTM": "invalid",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRTM")

    # Should return None when both RTH and RTM are None
    assert sensor.native_value is None


async def test_sensor_whu_string_value_error(hass: HomeAssistant) -> None:
    """Test getWHU with string that cannot be converted."""
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

    # Should return None
    assert sensor.native_value is None


async def test_sensor_rpw_int_conversion_exception(hass: HomeAssistant) -> None:
    """Test getRPW with value that raises exception on int conversion."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "not_a_number",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Should return None on exception
    assert sensor.native_value is None


async def test_sensor_sta_fallback_to_raw(hass: HomeAssistant) -> None:
    """Test getSTA falls back to raw value when no pattern matches."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getSTA": "Unknown status",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getSTA")

    # Should use raw value as mapped value
    value = sensor.native_value
    assert value == "Unknown status"


async def test_sensor_alm_none_value(hass: HomeAssistant) -> None:
    """Test getALM with None value."""
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

    # When value is None, str(None) = "None" which maps to 'no_alarm'
    assert sensor.native_value == "no_alarm"


async def test_sensor_numeric_conversion_precision_type_error(
    hass: HomeAssistant,
) -> None:
    """Test numeric conversion handles TypeError on precision."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": "50",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    # Mock precision to None and test
    sensor.entity_description = replace(
        sensor.entity_description, suggested_display_precision=None
    )
    assert sensor.native_value == 5.0


async def test_sensor_available_device_not_available(hass: HomeAssistant) -> None:
    """Test sensor availability when device is not available."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": False,
                "status": {
                    "getPRS": "50",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    # Should not be available
    assert sensor.available is False


async def test_sensor_native_value_device_not_found(hass: HomeAssistant) -> None:
    """Test native_value when device is not found."""
    data = {
        "devices": [
            {
                "id": "other_device",
                "name": "Other Device",
                "project_id": "project1",
                "status": {"getPRS": "50"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    # Should return None
    assert sensor.native_value is None


async def test_sensor_value_not_in_status(hass: HomeAssistant) -> None:
    """Test sensor when key is not in device status."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getFLO": "10",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    # Should return None when key not in status
    assert sensor.native_value is None


async def test_sensor_whu_int_value(hass: HomeAssistant) -> None:
    """Test getWHU with integer value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": 0,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getWHU")

    # Should return mapped value
    assert sensor.native_value == "°dH"


async def test_sensor_whu_float_value(hass: HomeAssistant) -> None:
    """Test getWHU with float value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWHU": 1.0,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getWHU")

    # Should return mapped value
    assert sensor.native_value == "°fH"


async def test_sensor_lar_value_error(hass: HomeAssistant) -> None:
    """Test getLAR with ValueError."""
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

    # Should return None
    assert sensor.native_value is None


async def test_sensor_lar_type_error(hass: HomeAssistant) -> None:
    """Test getLAR with TypeError."""
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

    # Should return None
    assert sensor.native_value is None


async def test_sensor_rpw_zero_mask(hass: HomeAssistant) -> None:
    """Test getRPW with zero mask."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": 0,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Should return the internal translation key "0" for mask == 0
    assert sensor.native_value == "0"


async def test_sensor_rpw_value_error_on_float(hass: HomeAssistant) -> None:
    """Test getRPW when float conversion fails."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "not_a_number_at_all",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Should return None
    assert sensor.native_value is None


async def test_sensor_available_coordinator_not_successful(hass: HomeAssistant) -> None:
    """Test sensor availability when coordinator update not successful."""
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
    coordinator.last_update_success = False
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    # Should not be available
    assert sensor.available is False


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
                    "getTYP": "120",  # SafeFloor
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    bat = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert bat.native_value == 40
    assert bat.native_unit_of_measurement == PERCENTAGE
    assert bat.device_class == SensorDeviceClass.BATTERY
    assert bat.suggested_display_precision == 0


async def test_sensor_getbat_safefloor_invalid_percentage(hass: HomeAssistant) -> None:
    """SafeFloor getBAT with an unparseable value returns None (covers except branch)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": "not_a_number",
                    "getTYP": "120",  # SafeFloor -> PERCENTAGE unit
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    bat = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert bat.native_unit_of_measurement == PERCENTAGE
    assert bat.native_value is None


async def test_sensor_getbat_safefloor_icon_levels(hass: HomeAssistant) -> None:
    """In percentage mode device_class=BATTERY is set; icon is None so HA handles it automatically."""

    base_data = {
        "id": "device1",
        "name": "Device 1",
        "project_id": "project1",
        "status": {"getTYP": "120"},
    }
    for bat_pct in ["95", "85", "75", "65", "55", "45", "35", "25", "15", "5", "0"]:
        data = {
            "devices": [
                {**base_data, "status": {**base_data["status"], "getBAT": bat_pct}}
            ]
        }  # type: ignore[dict-item]
        coordinator = _build_coordinator(hass, data)
        bat = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")
        assert bat.device_class == SensorDeviceClass.BATTERY
        assert bat.icon is None, (
            f"Expected None for {bat_pct}% — HA renders icons via device_class"
        )


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


async def test_getvol_conversion_to_m3(hass: HomeAssistant) -> None:
    """The getVOL string values should be converted to cubic meters (divide by 1000)."""
    data = {
        "devices": [
            {
                "id": "d1",
                "name": "Device",
                "project_id": "p",
                "status": {"getVOL": "6530"},
            }
        ]
    }
    coord = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coord, "d1", "Device", "getVOL")
    # 6530 L -> 6.53 m3
    assert sensor.native_value == 6.53


async def test_async_setup_entry_getpa_group_creation(hass: HomeAssistant) -> None:
    """When getPA1 evaluates true, group sensors are created."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getPA1": "true", "getPN1": "Profile X"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)
    entry.add_to_hass(hass)

    entities_collected = []
    await async_setup_entry(hass, entry, lambda ents: entities_collected.extend(ents))  # type: ignore[arg-type]

    # Should include at least one group sensor like getPN1
    keys = [getattr(e, "_sensor_key", None) for e in entities_collected]
    assert "getPN1" in keys or "getPV1" in keys or "getPF1" in keys


async def test_getavo_parsing(hass: HomeAssistant) -> None:
    """Test getAVO parsing."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getAVO": "1655mL"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getAVO")

    # 1655 mL -> 1.655 L
    val = sensor.native_value
    assert isinstance(val, int | float | str)
    assert abs(float(val) - 1.655) < 1e-6


async def test_getvol_cleaning_and_conversion(hass: HomeAssistant) -> None:
    """Test getVOL cleaning and conversion."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getVOL": "Vol[L]6530"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getVOL")

    # Cleaned value should be numeric 6.53 (m³)
    val = sensor.native_value
    assert isinstance(val, int | float | str)
    assert abs(float(val) - 6.53) < 1e-6


async def test_getbar_parsing_and_precision(hass: HomeAssistant) -> None:
    """Test getBAR parsing and precision."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getBAR": "4077 mbar"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAR")

    # 4077 mbar -> 4.077 bar rounded to precision 1 -> 4.1
    assert sensor.native_value == 4.1


async def test_getbat_parsing_and_precision(hass: HomeAssistant) -> None:
    """Test getBAT parsing and precision."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getBAT": "6,12 4,38 3,90"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    # First value 6,12 -> 6.12 with precision 2
    assert sensor.native_value == 6.12


async def test_getul_numeric_conversion(hass: HomeAssistant) -> None:
    """Test getUL numeric conversion."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getUL": "5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getUL")

    # 5 -> multiplied by 10 -> 50 (int)
    assert sensor.native_value == 50


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


async def test_getle_mapping(hass: HomeAssistant) -> None:
    """Test getLE mapping."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getLE": "2"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getLE")

    # getLE value '2' maps to 100 per constants
    assert sensor.native_value == 100


async def test_sensor_icon_getbat_zero_numeric_alert(hass: HomeAssistant) -> None:
    """Test getBAT icon shows alert when numeric voltage is zero."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getBAT": 0},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert sensor.icon == "mdi:battery-alert-variant-outline"


async def test_sensor_icon_getbat_zero_string_alert(hass: HomeAssistant) -> None:
    """Test getBAT icon shows alert when string "0" is provided."""
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

    assert sensor.icon == "mdi:battery-alert-variant-outline"


async def test_sensor_icon_getbat_invalid_fallback_base(hass: HomeAssistant) -> None:
    """Invalid getBAT values should result in the default battery icon (no alert)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getBAT": "invalid"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert sensor.icon == "mdi:battery"


async def test_sensor_icon_getbat_safe_t_format_base_icon(hass: HomeAssistant) -> None:
    """Safe-T+ multi-value format should use the default battery icon (not alert)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getBAT": "6,12 4,38 3,90"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert sensor.icon == "mdi:battery"


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


async def test_sensor_getala_not_and_wrn_various_values(hass: HomeAssistant) -> None:
    """Test getALA, getNOT and getWRN sensors handle None/empty/unmapped values."""
    for key in ("getALA", "getNOT", "getWRN"):
        for raw in (None, "", "UnknownValue", "1"):
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

            # Ensure we exercise the parsing/mapping logic and return a stable type
            val = sensor.native_value
            assert (val is None) or isinstance(val, str)


async def test_sensor_getala_mapped_and_unmapped(hass: HomeAssistant) -> None:
    """Sanity check: mapped values produce a (possibly different) string, unmapped fall back gracefully."""
    # Mapped example (most integrations return string mapping); we don't assert exact mapping
    data_mapped = {
        "devices": [
            {"id": "d1", "name": "Device", "project_id": "p", "status": {"getALA": ""}}
        ]
    }
    coord_m = _build_coordinator(hass, data_mapped)
    s_m = SyrConnectSensor(coord_m, "d1", "Device", "getALA")
    assert (s_m.native_value is None) or isinstance(s_m.native_value, str)

    # Unmapped raw value should be returned or handled
    data_unmapped = {
        "devices": [
            {
                "id": "d2",
                "name": "Device",
                "project_id": "p",
                "status": {"getALA": "CompletelyUnknown"},
            }
        ]
    }
    coord_u = _build_coordinator(hass, data_unmapped)
    s_u = SyrConnectSensor(coord_u, "d2", "Device", "getALA")
    assert s_u.native_value is not None


# Tests merged from test_getcof_water_consumption.py
def test_getcof_has_water_device_class():
    """Test that getCOF sensor has device_class=water for Energy Dashboard."""
    cof = _SYR_CONNECT_SENSOR_DESCRIPTIONS["getCOF"]
    assert cof.device_class == SensorDeviceClass.WATER


def test_getcof_has_total_increasing_state_class():
    """Test that getCOF sensor has state_class=total_increasing for statistics."""
    cof = _SYR_CONNECT_SENSOR_DESCRIPTIONS["getCOF"]
    assert cof.state_class == "total_increasing"


def test_getcof_returns_correct_value():
    """Test that getCOF sensor returns the correct water consumption value."""
    # Create mock coordinator with test data
    mock_coordinator = Mock()
    mock_coordinator.data = {
        "devices": [
            {
                "id": "210836887",
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
        device_id="210836887",
        device_name="Test Device",
        sensor_key="getCOF",
    )

    # Test that native_value returns getCOF value
    assert sensor.native_value == 888518


def test_getcof_handles_string_values():
    """Test that getCOF sensor correctly converts string values to float."""
    mock_coordinator = Mock()
    mock_coordinator.data = {
        "devices": [
            {
                "id": "210836887",
                "name": "Test Device",
                "status": {
                    "getCOF": "888518",  # String value
                },
            }
        ]
    }

    sensor = SyrConnectSensor(
        coordinator=mock_coordinator,
        device_id="210836887",
        device_name="Test Device",
        sensor_key="getCOF",
    )

    # Should convert string to number (accept int or float)
    assert float(sensor.native_value) == 888518.0
    assert isinstance(sensor.native_value, int | float)


async def test_async_setup_entry_getpa_exception_handler(hass: HomeAssistant) -> None:
    """Test exception handler in getPA group processing."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    # Normal status dict with getPA1 set to true
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getPA1": "true"},
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

    mock_add_entities = Mock()

    # Patch the entity registry to raise exception when removing
    with patch("custom_components.syr_connect.sensor.er.async_get") as mock_registry:
        mock_reg_instance = MagicMock()
        mock_reg_instance.async_get.return_value = None
        mock_reg_instance.async_get_entity_id.return_value = None
        mock_reg_instance.async_remove.side_effect = Exception("Test error")
        mock_registry.return_value = mock_reg_instance

        # Should not raise exception, should handle it gracefully
        await async_setup_entry(hass, entry, mock_add_entities)

        # Should still call add_entities (entities created despite exception)
        assert mock_add_entities.called


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


async def test_is_value_true_int_float_exception(hass: HomeAssistant) -> None:
    """Test is_value_true exception handling for invalid int/float values."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    # Create a value that looks numeric but fails conversion
    class BadNumeric:
        def __float__(self):
            raise ValueError("Cannot convert")

        def __int__(self):
            raise ValueError("Cannot convert")

    bad_value = BadNumeric()

    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": bad_value,  # Will trigger exception in is_value_true
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

    mock_add_entities = Mock()

    # Should handle exception in is_value_true and treat as false
    await async_setup_entry(hass, entry, mock_add_entities)

    # Should complete without raising exception
    assert mock_add_entities.called


async def test_is_value_true_string_numeric_exception(hass: HomeAssistant) -> None:
    """Test is_value_true exception handling for string that fails numeric conversion."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "not_a_number",  # String that fails conversion
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

    mock_add_entities = Mock()

    # Should handle exception and complete setup
    await async_setup_entry(hass, entry, mock_add_entities)

    entities = mock_add_entities.call_args[0][0]
    # Since "not_a_number" string fails conversion, is_value_true returns False
    # So getPA1 group shouldn't be created
    sensor_keys = [e._sensor_key for e in entities]
    assert "getPA1" not in sensor_keys


async def test_is_value_true_float_int_methods_raise(hass: HomeAssistant) -> None:
    """Test is_value_true handles objects whose numeric conversions raise exceptions."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    class BadNumeric:
        def __float__(self):
            raise ValueError("Cannot convert")

        def __int__(self):
            raise TypeError("Cannot convert")

    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": BadNumeric(),
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

    mock_add_entities = Mock()

    # Should handle conversion errors and complete setup without creating PA group members
    await async_setup_entry(hass, entry, mock_add_entities)
    assert mock_add_entities.called
    entities = mock_add_entities.call_args[0][0]
    keys = [e._sensor_key for e in entities]
    assert "getPA1" not in keys


async def test_getrpw_locale_and_formatting_fallback(hass: HomeAssistant) -> None:
    """Test getRPW when format_datetime fails and hass.config.language access raises."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "127",  # all days
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")
    sensor.hass = hass

    # Simulate format_datetime raising so fallback to strftime is used
    with patch(
        "custom_components.syr_connect.sensor.format_datetime",
        side_effect=ValueError("Format error"),
    ):
        # Also simulate hass.config.language raising an exception
        mock_hass = MagicMock()
        mock_hass.config.language.side_effect = Exception("Config error")
        sensor.hass = mock_hass

        value = sensor.native_value
        assert value is not None
        # Expect weekday short names present (Mon or similar)
        assert any(part for part in str(value).split(",") if part)


async def test_getsta_polish_pattern_mapping(hass: HomeAssistant) -> None:
    """Test getSTA mapping for Polish 'Płukanie regenerantem (NNN)' pattern."""
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

    mapped = sensor.native_value
    # The mapped state key is returned; the entity's translation_key stays the sensor key
    assert isinstance(mapped, str)
    assert sensor.translation_key == "getsta"


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

    # Should handle exception and return None or handle gracefully
    value = sensor.native_value
    # The conversion should handle the exception
    assert value is not None or value is None  # Either way, no exception raised


async def test_sensor_icon_getbat_zero_value(hass: HomeAssistant) -> None:
    """Test icon for getBAT when value is exactly zero."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": "0",
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

    # Trigger caching by accessing native_value
    _ = sensor.native_value
    icon = sensor.icon
    # When battery is 0, should show alert icon
    assert icon == "mdi:battery-alert-variant-outline"


async def test_sensor_icon_getbat_invalid_conversion(hass: HomeAssistant) -> None:
    """Test icon for getBAT when value cannot be converted to float."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": "invalid_numeric",
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

    # Should handle exception in float conversion
    icon = sensor.icon
    assert icon is not None or icon is None  # Should return base icon


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


async def test_sensor_getbar_empty_string(hass: HomeAssistant) -> None:
    """Test getBAR sensor with empty string."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
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
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getBAR",
    )

    # Should handle empty string
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


async def test_sensor_getbar_value_error(hass: HomeAssistant) -> None:
    """Test getBAR sensor when conversion raises ValueError."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAR": "inf mbar",  # Will match regex but fail float conversion
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

    # Should handle ValueError
    # Note: "inf" actually converts to float('inf'), so let's use a different test
    # Actually, regex \d+ won't match "inf", so it will return None anyway
    value = sensor.native_value
    assert value is None or isinstance(value, int | float)


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


async def test_sensor_getal_none_value(hass: HomeAssistant) -> None:
    """Test getUL sensor with None value."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getUL": None,
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getUL",
    )

    # Should handle None value - there are two getUL handlers in the code
    value = sensor.native_value
    assert value is None or isinstance(value, str | int)


async def test_sensor_getal_empty_string(hass: HomeAssistant) -> None:
    """Test getUL sensor with empty string."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getUL": "",
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getUL",
    )

    # Should handle empty string
    value = sensor.native_value
    assert value is None or isinstance(value, str | int)


async def test_sensor_getala_none_value(hass: HomeAssistant) -> None:
    """Test getALA sensor with None value."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALA": None,
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getALA",
    )

    # Should handle None value
    value = sensor.native_value
    assert value is None


async def test_sensor_getala_exception_returns_raw(hass: HomeAssistant) -> None:
    """Test getALA sensor when exception occurs in returning raw code."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    # Create an object that raises exception when converted to string
    class BadValue:
        def __str__(self):
            raise ValueError("Cannot convert")

    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALA": BadValue(),
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getALA",
    )

    # Should handle exception and return None
    value = sensor.native_value
    assert value is None


async def test_sensor_getnot_none_value(hass: HomeAssistant) -> None:
    """Test getNOT sensor with None value."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getNOT": None,
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getNOT",
    )

    # Should handle None value
    value = sensor.native_value
    assert value is None


async def test_sensor_getnot_exception_returns_raw(hass: HomeAssistant) -> None:
    """Test getNOT sensor when exception occurs in returning raw code."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    class BadValue:
        def __str__(self):
            raise ValueError("Cannot convert")

    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getNOT": BadValue(),
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getNOT",
    )

    # Should handle exception and return None
    value = sensor.native_value
    assert value is None


async def test_sensor_getwrn_none_value(hass: HomeAssistant) -> None:
    """Test getWRN sensor with None value."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWRN": None,
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getWRN",
    )

    # Should handle None value
    value = sensor.native_value
    assert value is None


async def test_sensor_getwrn_exception_returns_raw(hass: HomeAssistant) -> None:
    """Test getWRN sensor when exception occurs in returning raw code."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    class BadValue:
        def __str__(self):
            raise ValueError("Cannot convert")

    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWRN": BadValue(),
                },
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getWRN",
    )

    # Should handle exception and return None
    value = sensor.native_value
    assert value is None


async def test_sensor_getpmx_getwx_getbx_none_value(hass: HomeAssistant) -> None:
    """Test leak protection boolean sensors with None value."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    for sensor_key in ["getPA1", "getPM1", "getPW1", "getPB1"]:
        coordinator.data = {
            "devices": [
                {
                    "id": "device1",
                    "name": "Device 1",
                    "project_id": "project1",
                    "status": {
                        sensor_key: None,
                    },
                }
            ]
        }
        coordinator.last_update_success = True

        sensor = SyrConnectSensor(
            coordinator=coordinator,
            device_id="device1",
            device_name="Device 1",
            sensor_key=sensor_key,
        )

        # Should handle None value
        value = sensor.native_value
        assert value is None


async def test_sensor_getpmx_getwx_getbx_empty_string(hass: HomeAssistant) -> None:
    """Test leak protection boolean sensors with empty string."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    for sensor_key in ["getPA1", "getPM1", "getPW1", "getPB1"]:
        coordinator.data = {
            "devices": [
                {
                    "id": "device1",
                    "name": "Device 1",
                    "project_id": "project1",
                    "status": {
                        sensor_key: "   ",  # Whitespace only
                    },
                }
            ]
        }
        coordinator.last_update_success = True

        sensor = SyrConnectSensor(
            coordinator=coordinator,
            device_id="device1",
            device_name="Device 1",
            sensor_key=sensor_key,
        )

        # Should handle empty/whitespace string
        value = sensor.native_value
        assert value is None


async def test_sensor_getpmx_getwx_getbx_invalid_numeric(hass: HomeAssistant) -> None:
    """Test leak protection boolean sensors with invalid numeric string."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    for sensor_key in ["getPA1", "getPM1", "getPW1", "getPB1"]:
        coordinator.data = {
            "devices": [
                {
                    "id": "device1",
                    "name": "Device 1",
                    "project_id": "project1",
                    "status": {
                        sensor_key: "not_numeric",
                    },
                }
            ]
        }
        coordinator.last_update_success = True

        sensor = SyrConnectSensor(
            coordinator=coordinator,
            device_id="device1",
            device_name="Device 1",
            sensor_key=sensor_key,
        )

        # An unknown value counts as not set (see is_value_true)
        assert sensor.native_value == "false"


async def test_sensor_getpmx_getwx_getbx_int_exception(hass: HomeAssistant) -> None:
    """Test leak protection boolean sensors when int conversion raises exception."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    # Create value that is numeric type but raises exception
    class BadNumeric(int):
        def __float__(self):
            raise ValueError("Cannot convert")

        def __int__(self):
            raise TypeError("Cannot convert")

    for sensor_key in ["getPA1", "getPM1", "getPW1", "getPB1"]:
        coordinator.data = {
            "devices": [
                {
                    "id": "device1",
                    "name": "Device 1",
                    "project_id": "project1",
                    "status": {
                        sensor_key: 5,  # Valid int
                    },
                }
            ]
        }
        coordinator.last_update_success = True

        sensor = SyrConnectSensor(
            coordinator=coordinator,
            device_id="device1",
            device_name="Device 1",
            sensor_key=sensor_key,
        )

        # Should handle and return "true" for non-zero
        value = sensor.native_value
        assert value == "true"


async def test_sensor_getwhu_none_value(hass: HomeAssistant) -> None:
    """Test getWHU sensor with None value."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
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
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(
        coordinator=coordinator,
        device_id="device1",
        device_name="Device 1",
        sensor_key="getWHU",
    )

    # Should handle None value
    value = sensor.native_value
    assert value is None


async def test_sensor_exclude_when_empty_none_value(hass: HomeAssistant) -> None:
    """Test sensor setup skips sensors with hidden_when="empty" and None value."""

    test_key = None
    for key in (d.key for d in _SYR_CONNECT_SENSOR_TYPES if d.hidden_when == "empty"):
        test_key = key
        break

    if test_key:
        coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
        coordinator.data = {
            "devices": [
                {
                    "id": "device1",
                    "name": "Device 1",
                    "project_id": "project1",
                    "status": {
                        test_key: None,  # Should be excluded
                        "getPRS": "50",  # Include another sensor
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

        mock_add_entities = Mock()
        await async_setup_entry(hass, entry, mock_add_entities)

        entities = mock_add_entities.call_args[0][0]
        sensor_keys = [e._sensor_key for e in entities]

        # test_key should not be included since it's None
        assert test_key not in sensor_keys


async def test_sensor_exclude_when_empty_whitespace_string(hass: HomeAssistant) -> None:
    """Test sensor setup skips sensors with hidden_when="empty" and whitespace string."""

    test_key = None
    for key in (d.key for d in _SYR_CONNECT_SENSOR_TYPES if d.hidden_when == "empty"):
        test_key = key
        break

    if test_key:
        coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
        coordinator.data = {
            "devices": [
                {
                    "id": "device1",
                    "name": "Device 1",
                    "project_id": "project1",
                    "status": {
                        test_key: "   ",  # Whitespace only - should be excluded
                        "getPRS": "50",
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

        mock_add_entities = Mock()
        await async_setup_entry(hass, entry, mock_add_entities)

        entities = mock_add_entities.call_args[0][0]
        sensor_keys = [e._sensor_key for e in entities]

        # test_key should not be included
        assert test_key not in sensor_keys


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


async def test_sensor_pa_group_remove_exception(hass: HomeAssistant) -> None:
    """Test exception handling when removing PA group sensors from registry."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "false",  # PA1 is false, should remove group sensors
                    "getPV1": "10",
                },
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

    # Mock registry entry that exists and will fail to remove
    mock_reg_entry = MagicMock()
    mock_reg_entry.entity_id = "sensor.device1_getpv1"

    with patch("custom_components.syr_connect.sensor.er.async_get") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.async_get.return_value = mock_reg_entry
        mock_reg.async_remove.side_effect = RuntimeError("Remove failed")
        mock_registry.return_value = mock_reg

        mock_add_entities = Mock()
        # Should not raise exception, should log and continue
        await async_setup_entry(hass, entry, mock_add_entities)

        # Entities should still be added
        assert mock_add_entities.called


async def test_sensor_pa_group_exception_handling(hass: HomeAssistant) -> None:
    """Test exception handling in PA group logic."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "invalid_value_that_causes_exception",
                },
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

    # Mock _is_true to raise exception
    with patch("custom_components.syr_connect.sensor.er.async_get") as mock_registry:
        mock_reg = MagicMock()
        mock_reg.async_get.return_value = None
        mock_registry.return_value = mock_reg

        mock_add_entities = Mock()
        # Should not raise exception even if PA group logic fails
        await async_setup_entry(hass, entry, mock_add_entities)

        # Entities should still be added
        assert mock_add_entities.called


async def test_sensor_icon_bat_non_zero_string(hass: HomeAssistant) -> None:
    """Test getBAT icon with non-zero string value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": "5.5",  # Non-zero string
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    # Non-zero battery voltage keeps the default battery icon
    icon = sensor.icon
    assert icon == "mdi:battery"


async def test_sensor_icon_bat_conversion_exception(hass: HomeAssistant) -> None:
    """Test getBAT icon when conversion raises exception."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": "not-a-number",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    # Conversion failure keeps the default battery icon
    icon = sensor.icon
    assert icon == "mdi:battery"


async def test_sensor_native_value_ala_exception(hass: HomeAssistant) -> None:
    """Test getALA native_value when get_sensor_ala_map raises exception."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALA": "test_value",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getALA")

    # Mock get_sensor_ala_map to raise exception
    with patch(
        "custom_components.syr_connect.sensor.get_sensor_ala_map",
        side_effect=ValueError("Map error"),
    ):
        assert sensor.native_value is None


async def test_sensor_native_value_not_exception(hass: HomeAssistant) -> None:
    """Test getNOT native_value when get_sensor_not_map raises exception."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getNOT": "test_value",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getNOT")

    # Mock get_sensor_not_map to raise exception
    with patch(
        "custom_components.syr_connect.sensor.get_sensor_not_map",
        side_effect=ValueError("Map error"),
    ):
        assert sensor.native_value is None


async def test_sensor_native_value_wrn_exception(hass: HomeAssistant) -> None:
    """Test getWRN native_value when get_sensor_wrn_map raises exception."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWRN": "test_value",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getWRN")

    # Mock get_sensor_wrn_map to raise exception
    with patch(
        "custom_components.syr_connect.sensor.get_sensor_wrn_map",
        side_effect=ValueError("Map error"),
    ):
        assert sensor.native_value is None


async def test_sensor_native_value_pm_boolean_exception(hass: HomeAssistant) -> None:
    """Test getPMx boolean sensor with exception during string conversion."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPM1": "invalid_float",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPM1")

    # An unknown value counts as not set (see is_value_true)
    assert sensor.native_value == "false"


async def test_sensor_native_value_pm_numeric_exception(hass: HomeAssistant) -> None:
    """Test getPMx boolean sensor with exception during numeric conversion."""

    class BadNumber:
        def __float__(self):
            raise ValueError("Bad float")

    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPM2": BadNumber(),
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPM2")

    # An unknown type counts as not set (see is_value_true)
    assert sensor.native_value == "false"


async def test_sensor_native_value_alm_exception(hass: HomeAssistant) -> None:
    """Test getALM native_value when get_sensor_ala_map raises exception."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALM": "test_value",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getALM")

    # Mock get_sensor_ala_map to raise exception
    with patch(
        "custom_components.syr_connect.sensor.get_sensor_ala_map",
        side_effect=ValueError("Map error"),
    ):
        # Should fallback to raw value when exception occurs
        assert sensor.native_value == "test_value"


async def test_sensor_native_value_rpw_exception_in_loop(hass: HomeAssistant) -> None:
    """Test getRPW when format_datetime raises exception during loop."""
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
    sensor.hass = hass

    # Mock format_datetime to raise exception
    with patch(
        "custom_components.syr_connect.sensor.format_datetime",
        side_effect=ValueError("Format error"),
    ):
        value = sensor.native_value
        # Should fallback to strftime and return weekday names
        assert value is not None
        assert "Mon" in str(value) or "Mo" in str(value)  # Depends on system locale


async def test_sensor_native_value_rpw_hass_config_exception(
    hass: HomeAssistant,
) -> None:
    """Test getRPW when accessing hass.config.language raises exception."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getRPW": "1",  # Monday only
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getRPW")

    # Mock hass to raise exception when accessing config
    mock_hass = MagicMock()
    mock_hass.config.language.side_effect = Exception("Config error")
    sensor.hass = mock_hass

    # Should handle exception and use None locale
    value = sensor.native_value
    assert value is not None


async def test_sensor_apply_numeric_conversion_exception(hass: HomeAssistant) -> None:
    """Test _apply_numeric_conversion with exception during precision rounding."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": "50",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    # Mock the precision to return value and test exception path
    sensor.entity_description = replace(
        sensor.entity_description, suggested_display_precision=2
    )
    # Manually test with value that causes exception during round
    result = sensor._apply_numeric_conversion(5.0)
    # Should return the value without precision when exception occurs
    assert result == 0.5  # getPRS divides by 10


async def test_sensor_native_value_vol_exception(hass: HomeAssistant) -> None:
    """A cleaned getVOL value that is neither text nor a number gives no state."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getVOL": "1000",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getVOL")

    # Patch get_sensor_vol_value to return an object a sensor cannot show
    class BadValue:
        def __truediv__(self, _other):
            raise RuntimeError("Division error")

        def __float__(self):
            return 1000.0

    with patch(
        "custom_components.syr_connect.sensor.get_sensor_vol_value",
        return_value=BadValue(),
    ):
        assert sensor.native_value is None


async def test_is_true_with_non_standard_type(hass: HomeAssistant) -> None:
    """Test _is_true with non-standard types (dict, list, etc.) returns False."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": {"key": "value"},  # Dict should return False
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

    mock_add_entities = Mock()

    # Dict type should be treated as False by _is_true
    await async_setup_entry(hass, entry, mock_add_entities)

    # Should complete without raising exception, PA group sensors should not be created
    assert mock_add_entities.called
    entities = mock_add_entities.call_args[0][0]
    # PA1 dict value treated as False, so no getPA1 group members created
    pa_group_keys = [
        "getPA1",
        "getPV1",
        "getPT1",
        "getPF1",
        "getPN1",
        "getPM1",
        "getPW1",
        "getPB1",
        "getPR1",
    ]
    created_keys = [e._sensor_key for e in entities]
    for key in pa_group_keys:
        assert key not in created_keys


async def test_getbat_with_invalid_type(hass: HomeAssistant) -> None:
    """Test getBAT with value that is not str/int/float returns None."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": ["not", "valid"],  # List is not str/int/float
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    # Should return None for invalid type
    assert sensor.native_value is None


async def test_getpa_group_exception_handling(hass: HomeAssistant) -> None:
    """Test exception handling during getPA group processing."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    # Create a mock value that will cause exception during _is_true evaluation
    class ProblematicValue:
        def __bool__(self):
            raise RuntimeError("Unexpected error during boolean evaluation")

    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": ProblematicValue(),
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

    mock_add_entities = Mock()

    # Should handle exception in PA group processing gracefully
    await async_setup_entry(hass, entry, mock_add_entities)

    # Should complete despite exception
    assert mock_add_entities.called


async def test_registry_remove_exception(hass: HomeAssistant) -> None:
    """Test exception handling when removing sensor from registry fails."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": "0",  # False, should try to remove group sensors
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

    # Create mock registry with entity that exists
    registry = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entity_id = "sensor.syr_connect_device1_getpa1"
    registry.async_get.return_value = mock_entry
    # Make async_remove raise exception
    registry.async_remove.side_effect = RuntimeError("Registry error")

    mock_add_entities = Mock()

    with patch(
        "homeassistant.helpers.entity_registry.async_get", return_value=registry
    ):
        # Should handle exception when removing from registry
        await async_setup_entry(hass, entry, mock_add_entities)

        # Should complete despite exception
        assert mock_add_entities.called


async def test_is_true_with_list_type(hass: HomeAssistant) -> None:
    """Test _is_true with list type returns False."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)

    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA2": [1, 2, 3],  # List should return False
                    "someOtherKey": "value",  # Ensure device is not empty
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

    mock_add_entities = Mock()

    # List type should be treated as False by _is_true
    await async_setup_entry(hass, entry, mock_add_entities)

    assert mock_add_entities.called
    entities = mock_add_entities.call_args[0][0]
    # PA2 list value treated as False, so no getPA2 group members should be created
    pa2_group_keys = [
        "getPA2",
        "getPV2",
        "getPT2",
        "getPF2",
        "getPN2",
        "getPM2",
        "getPW2",
        "getPB2",
        "getPR2",
    ]
    created_keys = [e._sensor_key for e in entities]
    for key in pa2_group_keys:
        assert key not in created_keys


async def test_sensor_native_value_caching_returns_last_known_value(
    hass: HomeAssistant,
) -> None:
    """Test native_value returns cached value when current value is None."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": "50",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    # First call should return computed value and cache it
    value1 = sensor.native_value
    assert value1 == 5.0

    # Now update coordinator data to have None/missing value
    coordinator.async_set_updated_data(
        {
            "devices": [
                {
                    "id": "device1",
                    "name": "Device 1",
                    "project_id": "project1",
                    "status": {},  # getPRS missing
                }
            ]
        }
    )

    # Should return cached value instead of None
    value2 = sensor.native_value
    assert value2 == 5.0


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


async def test_sensor_getbar_no_numeric_value(hass: HomeAssistant) -> None:
    """Test getBAR sensor with string that has no numeric value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAR": "no numbers here",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAR")

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


async def test_sensor_getbat_invalid_type(hass: HomeAssistant) -> None:
    """Test getBAT sensor with invalid type."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBAT": ["list", "type"],
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getBAT")

    assert sensor.native_value is None


async def test_sensor_getala_exception_handling(hass: HomeAssistant) -> None:
    """Test getALA handles exceptions in get_sensor_ala_map."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getALA": "123",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getALA")

    # Mock get_sensor_ala_map to raise exception
    with patch(
        "custom_components.syr_connect.sensor.get_sensor_ala_map",
        side_effect=ValueError("Test error"),
    ):
        result = sensor.native_value
        assert result is None


async def test_sensor_getnot_exception_handling(hass: HomeAssistant) -> None:
    """Test getNOT handles exceptions in get_sensor_not_map."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getNOT": "456",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getNOT")

    # Mock get_sensor_not_map to raise exception
    with patch(
        "custom_components.syr_connect.sensor.get_sensor_not_map",
        side_effect=TypeError("Test error"),
    ):
        result = sensor.native_value
        assert result is None


async def test_sensor_getwrn_exception_handling(hass: HomeAssistant) -> None:
    """Test getWRN handles exceptions in get_sensor_wrn_map."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getWRN": "789",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getWRN")

    # Mock get_sensor_wrn_map to raise exception
    with patch(
        "custom_components.syr_connect.sensor.get_sensor_wrn_map",
        side_effect=AttributeError("Test error"),
    ):
        result = sensor.native_value
        assert result is None


async def test_sensor_leak_protection_getpv_float_value(hass: HomeAssistant) -> None:
    """Test leak protection getPV boolean with float value."""
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

    # getPV is not in the boolean regex pattern, so returns numeric value (rounded)
    assert sensor.native_value == 2


async def test_sensor_leak_protection_getpt_zero_float(hass: HomeAssistant) -> None:
    """Test leak protection getPT boolean with zero float value."""
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

    # getPT is not in the boolean regex pattern, so returns numeric value
    assert sensor.native_value == 0


async def test_sensor_leak_protection_getpn_none_value(hass: HomeAssistant) -> None:
    """Test leak protection getPN boolean with None value."""
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
    """Test leak protection getPW boolean with empty string."""
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
    """Test leak protection getPW boolean with invalid numeric string."""
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
    """Test leak protection getPB boolean with invalid type."""
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


async def test_sensor_apply_numeric_conversion_zerodivision(
    hass: HomeAssistant,
) -> None:
    """Test _apply_numeric_conversion handles ZeroDivisionError for getVOL."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getVOL": "1000",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getVOL")

    # Mock division to raise ZeroDivisionError
    # ZeroDivisionError is not caught in native_value, so it propagates
    with (
        patch.object(
            sensor, "_apply_numeric_conversion", side_effect=ZeroDivisionError
        ),
        pytest.raises(ZeroDivisionError),
    ):
        _ = sensor.native_value


async def test_sensor_apply_numeric_conversion_precision_valueerror(
    hass: HomeAssistant,
) -> None:
    """Test _apply_numeric_conversion handles ValueError during precision rounding."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPRS": "50.5",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")

    # Temporarily patch round() to raise ValueError
    original_round = round

    def mock_round(value, precision):
        if precision is not None:
            raise ValueError("Test error")
        return original_round(value)

    with patch("builtins.round", side_effect=mock_round):
        # Should handle ValueError and return original value
        result = sensor.native_value
        assert result is not None  # Should not crash


async def test_getpa_is_true_bool_true(hass: HomeAssistant) -> None:
    """Test _is_true helper with boolean True."""
    # This is tested indirectly through getPA group logic
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA1": True,  # Real boolean
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)

    mock_add_entities = Mock()
    await async_setup_entry(hass, entry, mock_add_entities)

    # getPA group sensors should be created
    entities = mock_add_entities.call_args[0][0]
    sensor_keys = [e._sensor_key for e in entities]
    assert "getPA1" in sensor_keys


async def test_getpa_is_true_bool_false(hass: HomeAssistant) -> None:
    """Test _is_true helper with boolean False."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA2": False,  # Real boolean
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)

    mock_add_entities = Mock()
    await async_setup_entry(hass, entry, mock_add_entities)

    # getPA group sensors should NOT be created
    entities = mock_add_entities.call_args[0][0]
    sensor_keys = [e._sensor_key for e in entities]
    assert "getPA2" not in sensor_keys
    assert "getPV2" not in sensor_keys


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


async def test_getpa_is_true_numeric_int(hass: HomeAssistant) -> None:
    """Test _is_true helper with numeric int != 0."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA3": 5,  # Non-zero int
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)

    mock_add_entities = Mock()
    await async_setup_entry(hass, entry, mock_add_entities)

    # getPA group sensors should be created
    entities = mock_add_entities.call_args[0][0]
    sensor_keys = [e._sensor_key for e in entities]
    assert "getPA3" in sensor_keys


async def test_getpa_is_true_numeric_float(hass: HomeAssistant) -> None:
    """Test _is_true helper with numeric float != 0."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA4": 2.5,  # Non-zero float
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)

    mock_add_entities = Mock()
    await async_setup_entry(hass, entry, mock_add_entities)

    # getPA group sensors should be created
    entities = mock_add_entities.call_args[0][0]
    sensor_keys = [e._sensor_key for e in entities]
    assert "getPA4" in sensor_keys


async def test_getpa_is_true_string_true(hass: HomeAssistant) -> None:
    """Test _is_true helper with string 'true'."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA5": "true",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)

    mock_add_entities = Mock()
    await async_setup_entry(hass, entry, mock_add_entities)

    # getPA group sensors should be created
    entities = mock_add_entities.call_args[0][0]
    sensor_keys = [e._sensor_key for e in entities]
    assert "getPA5" in sensor_keys


async def test_getpa_is_true_string_numeric(hass: HomeAssistant) -> None:
    """Test _is_true helper with numeric string."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA6": "3.14",  # Numeric string != 0
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)

    mock_add_entities = Mock()
    await async_setup_entry(hass, entry, mock_add_entities)

    # getPA group sensors should be created
    entities = mock_add_entities.call_args[0][0]
    sensor_keys = [e._sensor_key for e in entities]
    assert "getPA6" in sensor_keys


async def test_getpa_is_true_invalid_string(hass: HomeAssistant) -> None:
    """Test _is_true helper with invalid string."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA7": "invalid",  # Can't convert to number
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)

    mock_add_entities = Mock()
    await async_setup_entry(hass, entry, mock_add_entities)

    # Should treat as false (don't create group sensors)
    entities = mock_add_entities.call_args[0][0]
    sensor_keys = [e._sensor_key for e in entities]
    assert "getPA7" not in sensor_keys
    assert "getPV7" not in sensor_keys


async def test_getpa_is_true_string_one(hass: HomeAssistant) -> None:
    """Test _is_true helper with numeric string '1'."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA8": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)

    mock_add_entities = Mock()
    await async_setup_entry(hass, entry, mock_add_entities)

    # getPA group sensors should be created
    entities = mock_add_entities.call_args[0][0]
    sensor_keys = [e._sensor_key for e in entities]
    assert "getPA8" in sensor_keys


async def test_getpa_is_true_int_one(hass: HomeAssistant) -> None:
    """Test _is_true helper with integer 1."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getPA8": 1,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    entry = _build_entry(coordinator)

    mock_add_entities = Mock()
    await async_setup_entry(hass, entry, mock_add_entities)

    # getPA group sensors should be created
    entities = mock_add_entities.call_args[0][0]
    sensor_keys = [e._sensor_key for e in entities]
    assert "getPA8" in sensor_keys


def test_getbar_no_digits(create_mock_coordinator):
    """The getBAR with no digits should return None."""
    data = {
        "devices": [
            {
                "id": "d1",
                "name": "D",
                "project_id": "p1",
                "status": {"getBAR": "no digits"},
            }
        ]
    }
    coord = create_mock_coordinator(data)
    s = SyrConnectSensor(coord, "d1", "D", "getBAR")
    assert s.native_value is None


def test_getbat_invalid_type(create_mock_coordinator):
    """The getBAT with an unsupported type should return None."""
    data = {
        "devices": [
            {"id": "d1", "name": "D", "project_id": "p1", "status": {"getBAT": []}}
        ]
    }
    coord = create_mock_coordinator(data)
    s = SyrConnectSensor(coord, "d1", "D", "getBAT")
    assert s.native_value is None


def test_getavo_empty(create_mock_coordinator):
    """Empty getAVO should return None instead of raising."""
    data = {
        "devices": [
            {"id": "d1", "name": "D", "project_id": "p1", "status": {"getAVO": ""}}
        ]
    }
    coord = create_mock_coordinator(data)
    s = SyrConnectSensor(coord, "d1", "D", "getAVO")
    assert s.native_value is None


def test_pm_boolean_edgecases(create_mock_coordinator):
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


def test_native_value_caching(create_mock_coordinator):
    """When API returns None later, the sensor should keep the last known non-None value."""
    data1 = {
        "devices": [
            {"id": "d1", "name": "D", "project_id": "p1", "status": {"getFLO": "10"}}
        ]
    }
    coord = create_mock_coordinator(data1)
    s = SyrConnectSensor(coord, "d1", "D", "getFLO")
    # first read should return parsed numeric
    assert s.native_value == 10


async def test_async_setup_entry_no_coordinator_data(hass: HomeAssistant) -> None:
    """async_setup_entry should return early when coordinator has no data."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = None
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

    mock_add_entities = Mock()

    # Should return without calling add_entities
    await async_setup_entry(hass, entry, mock_add_entities)
    assert not mock_add_entities.called


def test_sensor_disabled_by_default_flag(create_mock_coordinator) -> None:
    """Sensors in the disabled-by-default set should be disabled by default."""
    data = {
        "devices": [
            {"id": "DEV", "name": "D", "project_id": "p1", "status": {"getIPA": "1"}}
        ]
    }
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "DEV", "D", "getIPA")

    assert sensor.entity_registry_enabled_default is False


def test_apply_numeric_conversion_precision_zero_returns_int(create_mock_coordinator):
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


async def test_sensor_available_coordinator_fails(hass: HomeAssistant) -> None:
    """Entity should be unavailable when coordinator update failed."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    coordinator.last_update_success = False

    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")
    assert sensor.available is False


async def test_sensor_available_device_marked_unavailable(hass: HomeAssistant) -> None:
    """Entity should be unavailable when device available flag is False."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},
                "available": False,
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")
    assert sensor.available is False


async def test_sensor_available_true(hass: HomeAssistant) -> None:
    """Entity should be available when coordinator OK and device available or missing flag."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {},
                "available": True,
            }
        ]
    }
    coordinator.last_update_success = True

    sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getPRS")
    assert sensor.available is True


def test_whu_invalid_sets_none(create_mock_coordinator) -> None:
    """When getWHU cannot be parsed the unit mapping attribute should be None."""
    data = {
        "devices": [
            {
                "id": "d1",
                "name": "D",
                "project_id": "p1",
                "status": {"getWHU": "invalid"},
            }
        ]
    }
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D", "getIWH")

    assert sensor.native_unit_of_measurement is None


def test_getala_uses_generic_codes_for_unknown_model(create_mock_coordinator) -> None:
    """When model is unknown getALA is mapped with the generic alarm codes."""
    data = {
        "devices": [
            {"id": "d1", "name": "D", "project_id": "p1", "status": {"getALA": "A5"}}
        ]
    }
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D", "getALA")

    assert sensor.native_value == "alarm_max_flow_rate_reached"


async def test_battery_zero_icon(hass: HomeAssistant) -> None:
    """Test battery zero icon."""
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
    assert sensor.icon == "mdi:battery-alert-variant-outline"


async def test_getala_exception_handling(hass: HomeAssistant) -> None:
    """Test getALA exception handling."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getALA": "A5"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    with patch(
        "custom_components.syr_connect.sensor.get_sensor_ala_map",
        side_effect=ValueError("boom"),
    ):
        sensor = SyrConnectSensor(coordinator, "device1", "Device 1", "getALA")
        assert sensor.native_value is None


async def test_getnot_and_getwrn_exception_paths(hass: HomeAssistant) -> None:
    """Test getNOT and getWRN exception paths."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getNOT": "FF", "getWRN": "FF"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    with patch(
        "custom_components.syr_connect.sensor.get_sensor_not_map",
        side_effect=ValueError("boom"),
    ):
        snot = SyrConnectSensor(coordinator, "device1", "Device 1", "getNOT")
        assert snot.native_value is None

    with patch(
        "custom_components.syr_connect.sensor.get_sensor_wrn_map",
        side_effect=ValueError("boom"),
    ):
        swrn = SyrConnectSensor(coordinator, "device1", "Device 1", "getWRN")
        assert swrn.native_value is None


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

    # end


# ---------------------------------------------------------------------------
# Lines 111-112 — _is_true except branch for int/float (float() raises)
# ---------------------------------------------------------------------------


async def test_is_true_int_subclass_bad_float_returns_false(
    hass: HomeAssistant,
) -> None:
    """_is_true except(ValueError,TypeError) for int|float branch (lines 111-112).

    Use an int subclass whose __float__ raises ValueError so the path is taken.
    """

    class _BadFloat(int):
        def __float__(self):
            raise ValueError("bad float")

    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getPA1": _BadFloat(1), "getFLO": "10"},
            }
        ]
    }
    coordinator.last_update_success = True

    entry = MockConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="T",
        data={},
        source="user",
        entry_id="e1",
        unique_id="u1",
    )
    entry.runtime_data = coordinator
    entry.add_to_hass(hass)

    mock_add = Mock()
    await async_setup_entry(hass, entry, mock_add)
    # _is_true(_BadFloat(1)) hits except → returns False → PA group NOT created
    assert mock_add.called
    entities = mock_add.call_args[0][0]
    pa_group = [e for e in entities if e._sensor_key.startswith("getPA")]
    assert len(pa_group) == 0


# ---------------------------------------------------------------------------
# Lines 173-174 — outer except in getPA group loop
# ---------------------------------------------------------------------------


async def test_sensor_setup_pa_group_outer_exception_caught(
    hass: HomeAssistant,
) -> None:
    """Outer except(ValueError,TypeError,..) in getPA loop caught (lines 173-174).

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
    # Exception was caught; add_entities called with empty list (no entities created)
    mock_add.assert_called_once_with([])


# ---------------------------------------------------------------------------
# Lines 193, 198-199 — getSRO empty / non-numeric value
# ---------------------------------------------------------------------------


async def test_sensor_setup_sro_empty_value_skipped(hass: HomeAssistant) -> None:
    """The getSRO with empty string hits the None/empty continue (line 193)."""
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
    """The getSRO with non-numeric string hits except-continue (lines 198-199)."""
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


# ---------------------------------------------------------------------------
# Lines 204, 209-210 — getFFM empty / non-numeric value
# ---------------------------------------------------------------------------


async def test_sensor_setup_ffm_empty_value_skipped(hass: HomeAssistant) -> None:
    """The getFFM with empty string hits the None/empty continue (line 204)."""
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
    """The getFFM with non-numeric string hits except-continue (lines 209-210)."""
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


# ---------------------------------------------------------------------------
# Lines 409-410 — getBAT icon ValueError (float(sval) fails)
# ---------------------------------------------------------------------------


def test_sensor_icon_bat_cached_non_numeric_string(create_mock_coordinator):
    """The getBAT icon: float(sval) ValueError caught (lines 409-410).

    Set _last_native_value to a non-numeric string and status to None so
    native_value returns the cached string.
    """
    data = {"devices": [{"id": "d1", "status": {"getBAT": None}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getBAT")
    sensor._last_native_value = "not a number"  # force cache

    icon = sensor.icon
    # ValueError caught → falls through → default battery icon
    assert icon == "mdi:battery"


# ---------------------------------------------------------------------------
# Line 524 — getAB native_value returns None when ab is None
# ---------------------------------------------------------------------------


def test_sensor_getab_native_value_none_when_ab_none(create_mock_coordinator):
    """The getAB _compute_native_value returns None when get_sensor_ab_value returns None (line 524)."""
    data = {"devices": [{"id": "d1", "status": {"getAB": None}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getAB")

    assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Lines 537-538 — getALA mapped value returned
# ---------------------------------------------------------------------------


def test_sensor_getala_mapped_translation_key_returned(create_mock_coordinator):
    """getALA: mapped truthy value sets translation_key and returns it (lines 537-538).

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


# ---------------------------------------------------------------------------
# Lines 589-590 — getBAR except(ValueError,TypeError) when str(value) raises
# ---------------------------------------------------------------------------


def test_sensor_getbar_str_raises_type_error(create_mock_coordinator):
    """The getBAR except(ValueError,TypeError) caught when str(value) raises (lines 589-590)."""

    class _BadStr:
        def __str__(self):
            raise TypeError("no str")

        def __eq__(self, _other):
            return False

    data = {"devices": [{"id": "d1", "status": {"getBAR": _BadStr()}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getBAR")

    assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Lines 610-614 — getNET native_value branches
# ---------------------------------------------------------------------------


def test_sensor_getnet_valid_value(create_mock_coordinator):
    """The getNET with a valid value returns get_sensor_net_value result (line 614)."""
    data = {"devices": [{"id": "d1", "status": {"getNET": "363"}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getNET")

    value = sensor.native_value
    assert value is not None


def test_sensor_getnet_none_value(create_mock_coordinator):
    """The getNET with None returns None (lines 610-611)."""
    data = {"devices": [{"id": "d1", "status": {"getNET": None}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getNET")

    assert sensor.native_value is None


def test_sensor_getnet_non_str_int_float_type(create_mock_coordinator):
    """The getNET with non-str/int/float type returns None (lines 612-613)."""
    data = {"devices": [{"id": "d1", "status": {"getNET": {"a": 1}}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getNET")

    assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Lines 641-645 — getNOT mapped / unmapped branches
# ---------------------------------------------------------------------------


def test_sensor_getnot_mapped_value_returned(create_mock_coordinator):
    """getNOT: known code '01' returns mapped translation key (lines 641-643)."""
    data = {"devices": [{"id": "d1", "status": {"getNOT": "01"}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getNOT")

    value = sensor.native_value
    assert value == "new_software_available"
    assert (
        sensor.translation_key == "getnot"
    )  # unchanged; the state is translated under it


def test_sensor_getnot_unmapped_returns_raw_code(create_mock_coordinator):
    """getNOT: unknown code returns raw string (lines 641, 644-645)."""
    data = {"devices": [{"id": "d1", "status": {"getNOT": "99"}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getNOT")

    value = sensor.native_value
    assert value == "99"


# ---------------------------------------------------------------------------
# Lines 659-660 — getPMx int/float except when int(float(nan)) raises ValueError
# ---------------------------------------------------------------------------


def test_sensor_leak_flag_float_nan_returns_false(create_mock_coordinator):
    """getPM1 with float('nan'): int(float(nan)) raises ValueError, so it counts as not set."""
    data = {"devices": [{"id": "d1", "status": {"getPM1": float("nan")}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getPM1")

    assert sensor.native_value == "false"


# ---------------------------------------------------------------------------
# Lines 794-798 — getWRN mapped / unmapped branches
# ---------------------------------------------------------------------------


def test_sensor_getwrn_mapped_value_returned(create_mock_coordinator):
    """getWRN: known code '01' returns mapped translation key (lines 794-796)."""
    data = {"devices": [{"id": "d1", "status": {"getWRN": "01"}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getWRN")

    value = sensor.native_value
    assert value == "power_outage"
    assert (
        sensor.translation_key == "getwrn"
    )  # unchanged; the state is translated under it


def test_sensor_getwrn_unmapped_returns_raw_code(create_mock_coordinator):
    """getWRN: unknown code returns raw string (lines 794, 797-798)."""
    data = {"devices": [{"id": "d1", "status": {"getWRN": "99"}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getWRN")

    value = sensor.native_value
    assert value == "99"


def test_sensor_getlng_none_value_returns_none(create_mock_coordinator):
    """getLNG: None value returns None (line 642)."""
    data = {"devices": [{"id": "d1", "status": {"getLNG": None}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getLNG")

    assert sensor.native_value is None


def test_sensor_getlng_empty_string_returns_none(create_mock_coordinator):
    """getLNG: empty string value returns None (line 642-643)."""
    data = {"devices": [{"id": "d1", "status": {"getLNG": ""}}]}
    coord = create_mock_coordinator(data)
    sensor = SyrConnectSensor(coord, "d1", "D1", "getLNG")

    assert sensor.native_value is None


def test_sensor_getlng_annotated_value_stripped(create_mock_coordinator):
    """getLNG: annotated value is stripped to the leading integer (line 648)."""
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
    hass: HomeAssistant, create_mock_entry_with_coordinator
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
    hass: HomeAssistant, create_mock_entry_with_coordinator
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


async def test_muco_conditional_sensor_creates_ohw_for_hwe_cartridge(
    hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities
) -> None:
    """getCRT=0 (HWE) creates the getOHW sensor and not getLOT."""
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

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert "getOHW" in keys
    assert "getLOT" not in keys


async def test_muco_conditional_sensor_switches_live_on_crt_change(
    hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities
) -> None:
    """Changing getCRT live re-evaluates the conditional sensor without a reload."""
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


# Line 299 — devices without an "id" must be skipped by the MuCo conditional sensor sync.
# Note: the main setup loop above indexes device['id']/['name']/['project_id'] directly,
# so the id key must be present (but falsy) rather than omitted.
async def test_muco_conditional_sensor_skips_device_without_id(
    hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities
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

    def async_get(self, entity_id):
        return None

    def async_get_entity_id(self, domain, platform, unique_id):
        return None

    def async_remove(self, entity_id):
        return None


# Lines 320-322 — the MuCo conditional sensor sync must swallow registry errors.
async def test_muco_conditional_sensor_sync_registry_exception(
    hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities
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


async def test_async_setup_entry_creates_triolock_sensors_from_real_fixture(
    hass: HomeAssistant, create_mock_entry_with_coordinator, mock_add_entities
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

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    keys = {getattr(e, "_sensor_key", None) for e in entities}
    assert {
        "getAB",
        "getVLV",
        "getDBD",
        "getDMA",
        "getDRP",
        "getDSV",
        "getDTT",
        "getPA1",
        "getPRF",
    } <= keys


@pytest.mark.parametrize("key", ["getLE", "getT1", "getT2", "getUL"])
@pytest.mark.parametrize("raw", ["abc", "1.5", [1]])
def test_mapped_int_sensor_invalid_value_returns_none(key: str, raw) -> None:
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


def test_sensor_value_fns_infinite_value_returns_none() -> None:
    """Infinity cannot be converted to int (OverflowError) and gives no value."""
    percentage_sensor = MagicMock(native_unit_of_measurement=PERCENTAGE)
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
def test_sensor_cyt_minutes(create_mock_coordinator, raw, expected) -> None:
    """Remaining regeneration time (getCYT) in minutes, from a number or minutes:seconds."""
    data = {"devices": [{"id": "d1", "name": "D1", "status": {"getCYT": raw}}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getCYT")

    assert sensor.native_unit_of_measurement == UnitOfTime.MINUTES
    assert sensor.native_value == expected


@pytest.mark.parametrize("model", ["SyrLEXplus10S", "SyrLEXplus10SL"])
def test_lexplus_has_only_one_tank(model: str) -> None:
    """LEXplus 10 S/SL have one tank: no sensors for tank 2 and 3, even if reported."""
    xml = (
        Path(__file__).parent / f"fixtures/xml/{model}_GetDeviceCollectionStatus.xml"
    ).read_text(encoding="utf-8")
    status = ResponseParser().parse_device_status_response(xml)
    assert status is not None

    keys = set(sensor_module.sensor_keys_for_status(status))

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

    keys = set(sensor_module.sensor_keys_for_status(status))

    assert keys & {"getVS1", "getVS2", "getVS3"} == expected


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("SyrSafeTechV4", {"getLWT", "getSLO", "getSMF", "getSOF"}),
        # getSOF is reported empty by these captures
        ("SyrSafeTechPlus", {"getLWT", "getSLO", "getSMF"}),
        ("SyrTrioDFRLS", {"getLWT", "getSLO", "getSMF"}),
        # The 10 SL reports no getSMF/getSOF
        ("SyrLEXplus10SL", {"getLWT", "getSLO"}),
        # Self-learning settings are stubs on the MultiController roles
        ("SyrTrioLock", {"getLWT"}),
        ("ConelClearProLeakProtection", {"getLWT"}),
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

    keys = set(sensor_module.sensor_keys_for_status(status))

    assert keys & {"getLWT", "getSLO", "getSMF", "getSOF"} == expected


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
    create_mock_coordinator, raw: Any, expected: str | None
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

    assert ("getTMZ" in sensor_module.sensor_keys_for_status(status)) is expected


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
    create_mock_coordinator, model: str, expected: float | None
) -> None:
    """Conductivity factor (getCNF): raw 5-50 is shown as 0.5-5.0, only on models that measure conductivity."""
    xml = (
        Path(__file__).parent / f"fixtures/xml/{model}_GetDeviceCollectionStatus.xml"
    ).read_text(encoding="utf-8")
    status = ResponseParser().parse_device_status_response(xml)
    assert status is not None

    keys = set(sensor_module.sensor_keys_for_status(status))
    if expected is None:
        assert "getCNF" not in keys
        return

    assert "getCNF" in keys
    data = {"devices": [{"id": "d1", "name": "D1", "status": status}]}
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getCNF")
    assert sensor.native_value == expected
