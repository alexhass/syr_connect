"""Tests for icons.json."""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.syr_connect.button import _SYR_CONNECT_BUTTON_DESCRIPTIONS
from custom_components.syr_connect.sensor import SyrConnectSensor

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "syr_connect"
ICONS = json.loads((COMPONENT_DIR / "icons.json").read_text(encoding="utf-8"))["entity"]
TRANSLATIONS = json.loads(
    (COMPONENT_DIR / "translations" / "en.json").read_text(encoding="utf-8")
)["entity"]


def _all_icons() -> list[tuple[str, str, str]]:
    result = []
    for platform, entities in ICONS.items():
        for key, spec in entities.items():
            result.append((platform, key, spec["default"]))
            result.extend(
                (platform, key, icon) for icon in spec.get("state", {}).values()
            )
            result.extend(
                (platform, key, icon) for icon in spec.get("range", {}).values()
            )
    return result


@pytest.mark.parametrize(("platform", "key", "icon"), _all_icons())
def test_icon_is_mdi(platform: str, key: str, icon: str) -> None:
    """Every icon must be an mdi icon name."""
    assert icon.startswith("mdi:"), f"{platform}.{key}: {icon}"


@pytest.mark.parametrize("platform", sorted(ICONS))
def test_icon_keys_have_translations(platform: str) -> None:
    """Every icon is keyed by an entity translation key."""
    missing = set(ICONS[platform]) - set(TRANSLATIONS.get(platform, {}))
    assert not missing, f"{platform}: {sorted(missing)}"


def test_button_icons() -> None:
    """Every button has a dedicated icon."""
    missing = {key.lower() for key in _SYR_CONNECT_BUTTON_DESCRIPTIONS} - set(
        ICONS["button"]
    )
    assert not missing, sorted(missing)


def test_connection_state_icons() -> None:
    """The connection state sensor maps every dst value to an icon."""
    dst = ICONS["sensor"]["dst"]
    assert dst["default"] == "mdi:network-outline"
    assert dst["state"] == {
        "0": "mdi:network-outline",
        "1": "mdi:close-network-outline",
        "2": "mdi:check-network-outline",
        "3": "mdi:check-network-outline",
    }


def _sensor_state(
    create_mock_coordinator: Callable[..., MagicMock], key: str, raw: str
) -> str:
    data = {
        "devices": [
            {"id": "d1", "name": "D1", "project_id": "p1", "status": {key: raw}}
        ]
    }
    sensor = SyrConnectSensor(create_mock_coordinator(data), "d1", "D1", key)
    return str(sensor.native_value)


@pytest.mark.parametrize(
    ("key", "raw", "icon"),
    [
        ("getVLV", "10", "mdi:valve-closed"),
        ("getVLV", "11", "mdi:valve"),
        ("getVLV", "20", "mdi:valve-open"),
        ("getVLV", "21", "mdi:valve"),
        ("getPST", "1", "mdi:close-circle"),
        ("getPST", "2", "mdi:check-circle"),
        ("getRG1", "1", "mdi:valve"),
        ("getRG2", "1", "mdi:valve"),
        ("getRG3", "1", "mdi:valve"),
        ("getAB", "1", "mdi:valve-open"),
        ("getAB", "2", "mdi:valve-closed"),
        ("getALA", "FF", "mdi:bell-outline"),
    ],
)
def test_state_icons_match_sensor_state(
    create_mock_coordinator: Callable[..., MagicMock], key: str, raw: str, icon: str
) -> None:
    """The state a sensor reports is a key of its state map in icons.json."""
    spec = ICONS["sensor"][key.lower()]
    state = _sensor_state(create_mock_coordinator, key, raw)
    assert spec["state"].get(state, spec["default"]) == icon


@pytest.mark.parametrize("key", ["getRG1", "getRG2", "getRG3"])
def test_regeneration_relay_default_is_closed(key: str) -> None:
    """A relay that is not 1 shows the closed valve."""
    assert ICONS["sensor"][key.lower()]["default"] == "mdi:valve-closed"


def test_valve_state_icons() -> None:
    """Valve entities map the standard valve states."""
    assert ICONS["valve"]["getab"]["state"] == {
        "closed": "mdi:valve-closed",
        "open": "mdi:valve-open",
        "opening": "mdi:valve",
        "closing": "mdi:valve",
    }


def test_battery_level_icon_comes_from_device_class() -> None:
    """The getbap must not be in icons.json, otherwise it would override the battery device class.

    It is also the translation key of getBAT on devices that report a percentage.
    """
    assert "getbap" not in ICONS["sensor"]


def _range_icon(spec: dict[str, Any], state: str) -> str:
    """Return the icon the frontend shows for a numeric state of a range icon.

    The icon of the highest range value less than or equal to the state, or the
    default for a state below all ranges or one that is not a number.
    """
    try:
        value = float(state)
    except ValueError:
        return str(spec["default"])
    matches = [float(limit) for limit in spec["range"] if float(limit) <= value]
    if not matches:
        return str(spec["default"])
    limit = max(matches)
    return str(next(icon for key, icon in spec["range"].items() if float(key) == limit))


@pytest.mark.parametrize(
    ("raw", "icon"),
    [
        ("0", "mdi:battery-alert-variant-outline"),
        ("0,00", "mdi:battery-alert-variant-outline"),
        ("1", "mdi:car-battery"),
        ("363", "mdi:car-battery"),
        ("6,12 4,38 3,90", "mdi:car-battery"),
        ("invalid", "mdi:car-battery"),
    ],
)
def test_battery_voltage_icon(
    create_mock_coordinator: Callable[..., MagicMock], raw: str, icon: str
) -> None:
    """A dead battery (getBAT 0 V) shows the alert icon, every other voltage the battery."""
    state = _sensor_state(create_mock_coordinator, "getBAT", raw)
    assert _range_icon(ICONS["sensor"]["getbat"], state) == icon
