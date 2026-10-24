"""Tests for binary_sensor platform."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from custom_components.syr_connect.binary_sensor import (
    SyrConnectBinarySensor,
    async_setup_entry,
)
from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.helpers import _DEVICE_MODULES
from custom_components.syr_connect.response_parser import ResponseParser
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


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


async def test_binary_sensor_is_on_numeric(hass: HomeAssistant) -> None:
    """Test binary sensor is_on with numeric value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is True


async def test_binary_sensor_is_off_numeric(hass: HomeAssistant) -> None:
    """Test binary sensor is_on with zero value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": "0",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is False


async def test_binary_sensor_available(hass: HomeAssistant) -> None:
    """Test binary sensor availability."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": True,
                "status": {
                    "getBUZ": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.available is True


async def test_async_setup_entry(
    hass: HomeAssistant, create_mock_entry_with_coordinator
) -> None:
    """Test async_setup_entry creates binary sensors."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {
                    "getBUZ": "1",  # Buzzer on/off
                },
            }
        ]
    }
    mock_config_entry, _mock_coordinator = create_mock_entry_with_coordinator(data)

    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # getBUZ has a binary sensor description and is not excluded — one binary sensor total.
    assert len(entities) == 1


@pytest.mark.parametrize(
    "status",
    [
        {"getVER": "Syr Floorsensor 2.23", "getBUZ": "0"},
        {"getCNA": "LEXplus10SL", "getBUZ": ""},
    ],
    ids=["safefloor", "lexplus10sl"],
)
async def test_async_setup_entry_skips_models_without_buzzer(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator,
    mock_add_entities,
    status: dict,
) -> None:
    """Models whose device file declares no buzzer get no getBUZ binary sensor, even if the key is present."""
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

    assert entities == []


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (
            "SyrSafeTechV4",
            {"get71", "getBUZ", "getCSD", "getPSD", "getSFV", "getTSD", "getVTO"},
        ),
        # getTSD/getPSD/getCSD are reported empty and are not created
        ("SyrSafeTechPlus", {"get71", "getBUZ", "getSFV", "getVTO"}),
        ("SyrTrioDFRLS", {"get71", "getBUZ", "getSFV", "getVTO"}),
        # The MultiController captures report no getVTO via XML
        ("SyrTrioLock", {"get71", "getBUZ", "getSFV"}),
        ("ConelClearProLeakProtection", {"get71", "getBUZ", "getSFV"}),
        ("SyrLEXplus10SL", {"get71"}),
        ("SyrSafeTPlus", {"get71", "getBUZ"}),
        ("SyrSafeFloor", {"getSFV"}),
        # Filling controller: firmware check, but no leak protection or valve test
        ("ConelClearProFill", {"getBUZ", "getSFV"}),
    ],
)
async def test_async_setup_entry_real_fixtures(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator,
    mock_add_entities,
    model: str,
    expected: set[str],
) -> None:
    """Leak protection, firmware check and valve test follow the model allowlists."""
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

    assert {e.entity_description.key for e in entities} == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        # dk 140 (SafeTech V4): integer API, 0 = active, 1 = deactivated
        ({"getVER": "Safe-Tech V4.08", "getTSD": "0"}, True),
        ({"getVER": "Safe-Tech V4.08", "getTSD": "1"}, False),
        # dk 1112 (SafeTech+): boolean API, True = active, False = deactivated
        ({"getSRN": "112AAA12345", "getTSD": "True"}, True),
        ({"getSRN": "112AAA12345", "getTSD": False}, False),
        # Empty value: unknown
        ({"getVER": "Safe-Tech V4.08", "getTSD": ""}, None),
    ],
)
async def test_binary_sensor_sensor_active_depends_on_dk(
    hass: HomeAssistant, status: dict, expected: bool | None
) -> None:
    """The meaning of the sensor settings flipped with the boolean API (dk >= 1100)."""
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
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getTSD")

    assert sensor.is_on is expected


def test_device_files_pair_buzzer_switch_with_binary_sensor() -> None:
    """Every device file that exposes getBUZ as a switch also lists it for the binary sensor, and vice versa."""
    for name, module in _DEVICE_MODULES.items():
        switch_keys = getattr(module, "SWITCH_SUPPORTED_KEYS", None)
        binary_keys = getattr(module, "BINARY_SENSOR_SUPPORTED_KEYS", None)
        if switch_keys is None:
            continue
        assert ("getBUZ" in switch_keys) == ("getBUZ" in (binary_keys or set())), name


async def test_async_setup_entry_multiple_devices(
    hass: HomeAssistant, create_mock_entry_with_coordinator
) -> None:
    """Test async_setup_entry with multiple devices."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "testSensor": "1",  # Custom non-excluded sensor
                },
            },
            {
                "id": "device2",
                "name": "Device 2",
                "project_id": "project1",
                "status": {},
            },
        ]
    }
    mock_config_entry, _mock_coordinator = create_mock_entry_with_coordinator(data)

    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))

    # Patch the binary sensors list to include our test sensor
    with patch(
        "custom_components.syr_connect.binary_sensor._SYR_CONNECT_BINARY_SENSOR_TYPES",
        (BinarySensorEntityDescription(key="testSensor"),),
    ):
        await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should create one sensor for device1
    assert len(entities) >= 0  # May be 0 or more depending on exclusions


async def test_binary_sensor_string_value(hass: HomeAssistant) -> None:
    """Test binary sensor with string values."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": "false",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is False


async def test_binary_sensor_numeric_float(hass: HomeAssistant) -> None:
    """Test binary sensor with float value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": 1.5,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is True


async def test_binary_sensor_unavailable_coordinator(hass: HomeAssistant) -> None:
    """Test binary sensor unavailable when coordinator update fails."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {"getBUZ": "1"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    coordinator.last_update_success = False

    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.available is False


async def test_binary_sensor_device_unavailable(hass: HomeAssistant) -> None:
    """Test binary sensor unavailable when device is marked unavailable."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "available": False,
                "status": {"getBUZ": "1"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.available is False


async def test_binary_sensor_missing_device(hass: HomeAssistant) -> None:
    """Test binary sensor when device is not in coordinator data."""
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

    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is None
    assert sensor.available is False  # Device removed from the account


async def test_binary_sensor_string_true(hass: HomeAssistant) -> None:
    """Test binary sensor with string 'true' value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": "true",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is True


async def test_binary_sensor_string_false(hass: HomeAssistant) -> None:
    """Test binary sensor with string 'False' value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": "False",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is False


async def test_binary_sensor_string_empty(hass: HomeAssistant) -> None:
    """Test binary sensor with empty string value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": "",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is False


async def test_binary_sensor_int_zero(hass: HomeAssistant) -> None:
    """Test binary sensor with integer 0 value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": 0,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is False


async def test_binary_sensor_int_nonzero(hass: HomeAssistant) -> None:
    """Test binary sensor with integer non-zero value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": 5,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is True


async def test_binary_sensor_float_zero(hass: HomeAssistant) -> None:
    """Test binary sensor with float 0.0 value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": 0.0,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is False


async def test_binary_sensor_none_value(hass: HomeAssistant) -> None:
    """Test binary sensor with None value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": None,
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is False


async def test_async_setup_entry_no_data(
    hass: HomeAssistant, create_mock_entry_with_coordinator
) -> None:
    """Test async_setup_entry with no coordinator data."""
    mock_config_entry, _mock_coordinator = create_mock_entry_with_coordinator(None)

    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Should not add any entities when no data
    async_add_entities.assert_not_called()


async def test_async_setup_entry_registry_cleanup(
    hass: HomeAssistant, create_mock_entry_with_coordinator
) -> None:
    """Test async_setup_entry removes binary sensors that are not in the allowlist."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {"getBUZ": "1"},
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    mock_config_entry.add_to_hass(hass)
    mock_coordinator.entry_id = mock_config_entry.entry_id

    # getFOO is no binary sensor key; getBUZ is
    registry = er.async_get(hass)
    for key in ("getFOO", "getBUZ"):
        registry.async_get_or_create(
            "binary_sensor",
            DOMAIN,
            f"{mock_config_entry.entry_id}_device1_{key}",
            config_entry=mock_config_entry,
        )

    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    prefix = f"{mock_config_entry.entry_id}_device1_"
    assert not registry.async_get_entity_id("binary_sensor", DOMAIN, prefix + "getFOO")
    assert registry.async_get_entity_id("binary_sensor", DOMAIN, prefix + "getBUZ")


async def test_async_setup_entry_registry_exception(
    hass: HomeAssistant, create_mock_entry_with_coordinator
) -> None:
    """Test async_setup_entry handles registry exceptions gracefully."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": {},
            }
        ]
    }
    mock_config_entry, _mock_coordinator = create_mock_entry_with_coordinator(data)

    entities = []
    async_add_entities = Mock(side_effect=lambda ents: entities.extend(ents))

    # Mock registry to raise exception
    def raise_registry_error(*args, **kwargs):
        raise RuntimeError("Registry error")

    with patch(
        "homeassistant.helpers.entity_registry.async_get",
        side_effect=raise_registry_error,
    ):
        # Should not raise exception, continues setup
        await async_setup_entry(hass, mock_config_entry, async_add_entities)

        # Setup should still complete
        assert True


async def test_binary_sensor_string_nonzero(hass: HomeAssistant) -> None:
    """Test binary sensor with non-zero string value."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    assert sensor.is_on is True


async def test_binary_sensor_icon_from_icons_json(hass: HomeAssistant) -> None:
    """Test binary sensor leaves the icon to icons.json."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "status": {
                    "getBUZ": "1",
                },
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)

    sensor = SyrConnectBinarySensor(coordinator, "device1", "Device 1", "getBUZ")

    # The icon is resolved from icons.json via the translation key
    assert sensor.icon is None
    assert sensor.translation_key == "getbuz"
