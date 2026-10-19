"""Tests for icons.json."""

import json
from pathlib import Path

import pytest

from custom_components.syr_connect.sensor import SyrConnectSensor

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "syr_connect"
ICONS = json.loads((COMPONENT_DIR / "icons.json").read_text(encoding="utf-8"))["entity"]
TRANSLATIONS = json.loads((COMPONENT_DIR / "translations" / "en.json").read_text(encoding="utf-8"))["entity"]


def _all_icons() -> list[tuple[str, str, str]]:
    result = []
    for platform, entities in ICONS.items():
        for key, spec in entities.items():
            result.append((platform, key, spec["default"]))
            result.extend((platform, key, icon) for icon in spec.get("state", {}).values())
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
    """The reset and regeneration buttons have a dedicated icon."""
    assert {"setala", "setnot", "setsir", "setwrn"} <= set(ICONS["button"])


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


def _sensor_state(create_mock_coordinator, key: str, raw: str) -> str:
    data = {"devices": [{"id": "d1", "name": "D1", "project_id": "p1", "status": {key: raw}}]}
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
def test_state_icons_match_sensor_state(create_mock_coordinator, key: str, raw: str, icon: str) -> None:
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


def test_battery_icon_is_set_in_code() -> None:
    """The getBAT must not be in icons.json, otherwise it would override the battery device class."""
    assert "getbat" not in ICONS["sensor"]
