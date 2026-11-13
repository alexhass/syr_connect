"""Tests for the entities of the All-in-One+."""

# The tests check private attributes of the entities.
# ruff: noqa: SLF001

from collections.abc import Callable
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast
from unittest.mock import MagicMock, Mock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.syr_connect import (
    select as select_module,
    sensor as sensor_module,
    switch as switch_module,
)
from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.models import (
    MODEL_SIGNATURES,
    SyrConnectModel,
    detect_model,
)
from custom_components.syr_connect.response_parser import ResponseParser
from custom_components.syr_connect.select import (
    SyrConnectHardnessSelect,
    SyrConnectRangedHardnessSelect,
)
from custom_components.syr_connect.sensor import SyrConnectSensor
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant

_SYR_CONNECT_TEST_ALLINONEPLUS_MODEL = next(
    model for model in MODEL_SIGNATURES if model.name == "allinoneplus"
)


def _signature(name: str) -> SyrConnectModel:
    """Return the model signature with the given name."""
    return next(model for model in MODEL_SIGNATURES if model.name == name)


@pytest.mark.parametrize(
    ("crt", "expected"),
    [
        pytest.param("0", {"getOWH"}, id="hwe"),
        pytest.param("1", set(), id="hve"),
    ],
)
async def test_allinoneplus_owh_select_only_for_hwe_cartridge(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    crt: str,
    expected: set[str],
) -> None:
    """On the All-in-One+, getOWH is the soft water hardness of the HWE cartridge (0-12)."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "model": _SYR_CONNECT_TEST_ALLINONEPLUS_MODEL,
                "status": {
                    "getCRT": crt,
                    "getOWH": "5",
                    "getLOT": "7",
                    "getOHW": "3",
                    "getWHU": "0",
                },
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    cartridge_selects = [
        e
        for e in entities
        if getattr(e, "_sensor_key", None) in ("getOWH", "getLOT", "getOHW")
    ]
    assert {e._sensor_key for e in cartridge_selects} == expected
    for select in cartridge_selects:
        assert isinstance(select, SyrConnectHardnessSelect)
        assert select.options[0] == "0 °dH"
        assert select.options[-1] == "12 °dH"
        assert select.current_option == "5 °dH"


@pytest.mark.parametrize(
    ("crs", "expected"),
    [
        pytest.param("0", {"getFCS"}, id="custom"),
        pytest.param("1", set(), id="fixed-size"),
    ],
)
async def test_allinoneplus_fcs_only_for_custom_cartridge_size(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    crs: str,
    expected: set[str],
) -> None:
    """The custom cartridge size (getFCS) is a select and a sensor only for getCRS "custom"."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "model": _SYR_CONNECT_TEST_ALLINONEPLUS_MODEL,
                "status": {"getCRS": crs, "getFCS": "2"},
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    selects, async_add_selects = mock_add_entities()
    sensors, async_add_sensors = mock_add_entities()

    await select_module.async_setup_entry(hass, mock_config_entry, async_add_selects)
    await sensor_module.async_setup_entry(hass, mock_config_entry, async_add_sensors)

    for entities in (selects, sensors):
        keys = {getattr(e, "_sensor_key", None) for e in entities}
        assert keys & {"getFCS"} == expected


async def test_allinoneplus_fcs_select_switches_live_on_crs_change(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """Changing getCRS live adds and removes the getFCS select without a reload."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "model": _SYR_CONNECT_TEST_ALLINONEPLUS_MODEL,
                "status": {"getCRS": "1", "getFCS": "2"},
            }
        ]
    }
    mock_config_entry, mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()
    fake_registry = MagicMock()
    fake_registry.async_get.return_value = Mock(config_entry_id=None)

    with patch(
        "homeassistant.helpers.entity_registry.async_get", return_value=fake_registry
    ):
        await select_module.async_setup_entry(
            hass, mock_config_entry, async_add_entities
        )
    assert "getFCS" not in {getattr(e, "_sensor_key", None) for e in entities}
    listener = mock_coordinator.async_add_listener.call_args.args[0]

    # Custom size selected: the select appears with 1-100 L
    mock_coordinator.data["devices"][0]["status"]["getCRS"] = "0"
    entities.clear()
    with patch(
        "homeassistant.helpers.entity_registry.async_get", return_value=fake_registry
    ):
        listener()
    fcs = next(e for e in entities if getattr(e, "_sensor_key", None) == "getFCS")
    assert fcs.options == [f"{value} L" for value in range(1, 101)]
    assert fcs.current_option == "2 L"

    # A fixed size selected again: the select is removed
    mock_coordinator.data["devices"][0]["status"]["getCRS"] = "1"
    fake_registry.async_remove.reset_mock()
    with patch(
        "homeassistant.helpers.entity_registry.async_get", return_value=fake_registry
    ):
        listener()
    fake_registry.async_remove.assert_called_once()


async def test_allinoneplus_cwl_select(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """The remaining capacity warning threshold (getCWL) offers 1-10 %."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "model": _SYR_CONNECT_TEST_ALLINONEPLUS_MODEL,
                "status": {"getCWL": "10"},
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    cwl = next(e for e in entities if getattr(e, "_sensor_key", None) == "getCWL")
    assert cwl.options == [f"{value} %" for value in range(1, 11)]
    assert cwl.current_option == "10 %"


@pytest.mark.parametrize(
    ("whu", "iwh", "iwh_options", "owh_options"),
    [
        pytest.param(
            "0",
            "20",
            [f"{value} °dH" for value in range(1, 51)],
            [f"{value} °dH" for value in range(13)],
            id="dh",
        ),
        pytest.param(
            "1",
            "8",
            [f"{value} °e" for value in range(1, 66)],
            [f"{value} °e" for value in range(9)],
            id="e-limited-by-raw-water",
        ),
        pytest.param(
            "2",
            "40",
            [f"{value} °fH" for value in range(1, 91)],
            [f"{value} °fH" for value in range(23)],
            id="fh",
        ),
        pytest.param(
            "3",
            "350",
            [f"{value} ppm" for value in range(10, 901, 10)],
            [f"{value} ppm" for value in range(0, 221, 10)],
            id="ppm",
        ),
        pytest.param("7", "20", [], [], id="unknown-unit"),
    ],
)
async def test_allinoneplus_hardness_selects_follow_unit(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    whu: str,
    iwh: str,
    iwh_options: list[str],
    owh_options: list[str],
) -> None:
    """The hardness ranges of the All-in-One+ follow the unit; getOWH is at most getIWH."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "model": _SYR_CONNECT_TEST_ALLINONEPLUS_MODEL,
                "status": {
                    "getCRT": "0",
                    "getIWH": iwh,
                    "getOWH": "5",
                    "getWHU": whu,
                },
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    by_key = {getattr(e, "_sensor_key", None): e for e in entities}
    assert isinstance(by_key["getIWH"], SyrConnectRangedHardnessSelect)
    assert isinstance(by_key["getOWH"], SyrConnectRangedHardnessSelect)
    assert by_key["getIWH"].options == iwh_options
    assert by_key["getOWH"].options == owh_options


async def test_allinoneplus_initial_filling_selects(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
) -> None:
    """The initial filling limits (getFVT, getFMT) offer the steps of the SYR app."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "model": _SYR_CONNECT_TEST_ALLINONEPLUS_MODEL,
                "status": {"getFMT": "60", "getFVT": "100"},
            }
        ]
    }
    mock_config_entry, _ = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    by_key = {getattr(e, "_sensor_key", None): e for e in entities}
    fvt = by_key["getFVT"]
    fmt = by_key["getFMT"]
    assert fvt.options[:3] == ["0 L", "10 L", "20 L"]
    assert fvt.options[-1] == "9900 L"
    assert fvt.current_option == "100 L"
    assert fmt.options[:8] == [
        "5 min",
        "10 min",
        "15 min",
        "20 min",
        "30 min",
        "40 min",
        "50 min",
        "60 min",
    ]
    assert fmt.options[-1] == "1500 min"
    assert fmt.current_option == "60 min"


def test_allinoneplus_last_filling_volume_in_milliliters(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """The All-in-One+ reports the last filling volume (getLFV) in milliliters."""
    data = {
        "devices": [
            {
                "id": "d1",
                "name": "D1",
                "model": _signature("allinoneplus"),
                "status": {"getLFV": "6600"},
            }
        ]
    }
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getLFV")

    assert sensor.native_value == 6.6
    assert sensor.native_unit_of_measurement == UnitOfVolume.LITERS
    # Shown as "6.60 L"
    assert sensor.suggested_display_precision == 2


@pytest.mark.parametrize(
    ("crt", "expected"),
    [
        pytest.param("0", {"getOWH"}, id="hwe"),
        pytest.param("1", set(), id="hve"),
    ],
)
def test_allinoneplus_owh_sensor_only_for_hwe_cartridge(
    crt: str, expected: set[str]
) -> None:
    """On the All-in-One+, getOWH is the soft water hardness of the HWE cartridge."""
    status = {"getCRT": crt, "getOWH": "5", "getLOT": "7", "getOHW": "3"}
    model = _signature("allinoneplus")

    keys = sensor_module.sensor_keys_for_status(status, model)

    assert set(keys) & {"getOWH", "getLOT", "getOHW"} == expected
    assert ("getOWH" in sensor_module._hidden_sensor_keys(status, model)) is not bool(
        expected
    )


def _fixture_status(fixture: str) -> dict[str, Any]:
    """Return the status of the All-in-One+ from a local JSON or cloud XML fixture."""
    path = Path(__file__).parent / "fixtures" / fixture
    if path.suffix == ".json":
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    status = ResponseParser().parse_device_status_response(
        path.read_text(encoding="utf-8")
    )
    assert status is not None
    return status


@pytest.mark.parametrize(
    ("fixture", "temperature"),
    [
        pytest.param("json/SyrAllInOnePlus_get_all.json", 23.5, id="json"),
        pytest.param(
            "xml/SyrAllInOnePlus_GetDeviceCollectionStatus.xml", 23.6, id="xml"
        ),
    ],
)
def test_allinoneplus_fixture_mac_and_temperature(
    create_mock_coordinator: Callable[..., MagicMock],
    fixture: str,
    temperature: float,
) -> None:
    """The All-in-One+ reports one MAC address (getMAC) and the water temperature (getCEL)."""
    status = _fixture_status(fixture)
    model = detect_model(status)
    assert model.name == "allinoneplus"

    keys = set(sensor_module.sensor_keys_for_status(status, model))

    assert {"getCEL", "getMAC"} <= keys
    # getCRS 1 (2.5 L): the reported custom size getFCS does not apply
    assert "getFCS" not in keys
    data = {"devices": [{"id": "d1", "name": "D1", "model": model, "status": status}]}
    cel = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", "getCEL")
    assert cel.native_value == temperature
    assert cel.native_unit_of_measurement == UnitOfTemperature.CELSIUS


async def test_async_setup_entry_creates_allinoneplus_manual_filling(
    hass: HomeAssistant,
) -> None:
    """The All-in-One+ gets the initial (getIFL) and manual (getMFL) filling switches."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="TestManualFilling",
        data={CONF_USERNAME: "test", CONF_PASSWORD: "test"},
        source="user",
        entry_id="test_entry_mfl",
        unique_id="test_unique_id_mfl",
        discovery_keys=MappingProxyType({}),
        options={},
        subentries_data={},
    )
    model = next(model for model in MODEL_SIGNATURES if model.name == "allinoneplus")
    device = {
        "id": "SN401",
        "name": "AllInOnePlus",
        "model": model,
        "status": {"getDFI": "False", "getIFL": "False", "getMFL": "True"},
    }
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"devices": [device]}
    config_entry.runtime_data = mock_coordinator

    mock_add_entities = MagicMock()

    await switch_module.async_setup_entry(hass, config_entry, mock_add_entities)

    switches = {
        getattr(e, "_sensor_key", None): e for e in mock_add_entities.call_args[0][0]
    }
    assert set(switches) == {"getDFI", "getIFL", "getMFL"}
    assert switches["getIFL"].is_on is False
    assert switches["getMFL"].is_on is True
