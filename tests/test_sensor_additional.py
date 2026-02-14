"""Additional tests to increase coverage for sensor.py."""
from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.sensor import SyrConnectSensor


def _build_coordinator(hass: HomeAssistant, data: dict) -> SyrConnectDataUpdateCoordinator:
    coordinator = SyrConnectDataUpdateCoordinator(
        hass,
        MagicMock(),
        "test@example.com",
        "password",
        60,
    )
    coordinator.async_set_updated_data(data)
    coordinator.last_update_success = True
    return coordinator


async def test_getvol_cleaning_then_numeric(hass: HomeAssistant) -> None:
    """getVOL with prefix should be cleaned and returned as numeric."""
    data = {
        "devices": [
            {
                "id": "dev1",
                "name": "Dev 1",
                "project_id": "p1",
                "status": {"getVOL": "Vol[L]6530"},
            }
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "dev1", "Dev 1", "p1", "getVOL")

    # cleaned value '6530' -> numeric conversion -> 6530.0 (apply numeric conversion doesn't change)
    assert sensor.native_value == 6530.0


async def test_getavo_extract_flow(hass: HomeAssistant) -> None:
    """Extract flow value from mL string."""
    data = {
        "devices": [
            {"id": "dev2", "name": "Dev 2", "project_id": "p1", "status": {"getAVO": "1655mL"}},
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "dev2", "Dev 2", "p1", "getAVO")
    assert abs(sensor.native_value - 1.655) < 1e-6


async def test_getbar_parsing(hass: HomeAssistant) -> None:
    """Parse mbar value and convert to bar with precision."""
    data = {
        "devices": [
            {"id": "dev3", "name": "Dev 3", "project_id": "p1", "status": {"getBAR": "4077 mbar"}},
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "dev3", "Dev 3", "p1", "getBAR")
    # 4077 mbar -> 4.077 bar rounded to 3 decimals
    assert sensor.native_value == 4.077


async def test_getbat_parsing_and_icon_zero(hass: HomeAssistant) -> None:
    """Parse battery string with commas and verify icon for zero voltage."""
    data = {
        "devices": [
            {"id": "dev4", "name": "Dev 4", "project_id": "p1", "status": {"getBAT": "6,12 4,38"}},
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "dev4", "Dev 4", "p1", "getBAT")
    assert sensor.native_value == 6.12

    # Now test icon for zero-like battery
    data_zero = {
        "devices": [
            {"id": "dev4", "name": "Dev 4", "project_id": "p1", "status": {"getBAT": "0"}},
        ]
    }
    coordinator_zero = _build_coordinator(hass, data_zero)
    sensor_zero = SyrConnectSensor(coordinator_zero, "dev4", "Dev 4", "p1", "getBAT")
    # icon property should handle 0 -> battery alert variant
    assert sensor_zero.icon == "mdi:battery-alert-variant-outline"


async def test_getul_conversion(hass: HomeAssistant) -> None:
    """getUL value multiplied by 10 to liters."""
    data = {
        "devices": [
            {"id": "dev5", "name": "Dev 5", "project_id": "p1", "status": {"getUL": "5"}},
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "dev5", "Dev 5", "p1", "getUL")
    assert sensor.native_value == 50


async def test_getwhu_invalid_returns_none(hass: HomeAssistant) -> None:
    """Invalid getWHU string returns None."""
    data = {
        "devices": [
            {"id": "dev6", "name": "Dev 6", "project_id": "p1", "status": {"getWHU": "invalid"}},
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "dev6", "Dev 6", "p1", "getWHU")
    assert sensor.native_value is None


async def test_getlar_invalid_and_none(hass: HomeAssistant) -> None:
    """Invalid getLAR values return None."""
    data = {
        "devices": [
            {"id": "dev7", "name": "Dev 7", "project_id": "p1", "status": {"getLAR": ""}},
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "dev7", "Dev 7", "p1", "getLAR")
    assert sensor.native_value is None

    data_bad = {
        "devices": [
            {"id": "dev7", "name": "Dev 7", "project_id": "p1", "status": {"getLAR": "not_a_ts"}},
        ]
    }
    coordinator_bad = _build_coordinator(hass, data_bad)
    sensor_bad = SyrConnectSensor(coordinator_bad, "dev7", "Dev 7", "p1", "getLAR")
    assert sensor_bad.native_value is None


async def test_getrpw_partial_mask(hass: HomeAssistant) -> None:
    """Partial getRPW masks produce multiple weekday names."""
    # mask 5 -> Monday + Wednesday
    data = {
        "devices": [
            {"id": "dev8", "name": "Dev 8", "project_id": "p1", "status": {"getRPW": "5"}},
        ]
    }
    coordinator = _build_coordinator(hass, data)
    sensor = SyrConnectSensor(coordinator, "dev8", "Dev 8", "p1", "getRPW")
    assert sensor.native_value is not None
    assert "," in sensor.native_value


async def test_getsta_fallback_and_mapping(hass: HomeAssistant) -> None:
    """getSTA fallback mapping for unknown strings uses raw mapping."""
    data = {
        "devices": [
            {"id": "dev9", "name": "Dev 9", "project_id": "p1", "status": {"getSTA": "Unknown state"}},
        ]
    }
    coordinator = _build_coordinator(hass, data)
    s = SyrConnectSensor(coordinator, "dev9", "Dev 9", "p1", "getSTA")
    # should return the normalized mapping (fallback to raw string mapping)
    assert s.native_value == "Unknown state"


async def test_icon_variants_for_valves_and_rg(hass: HomeAssistant) -> None:
    """Test icon choices for getAB, getVLV and getRG1."""
    # getAB open
    data_ab_open = {"devices": [{"id": "d1", "name": "D", "project_id": "p", "status": {"getAB": "1"}}]}
    c_ab_open = _build_coordinator(hass, data_ab_open)
    s_ab_open = SyrConnectSensor(c_ab_open, "d1", "D", "p", "getAB")
    assert s_ab_open.icon == "mdi:valve-open"

    # getAB closed
    data_ab_closed = {"devices": [{"id": "d2", "name": "D", "project_id": "p", "status": {"getAB": "2"}}]}
    c_ab_closed = _build_coordinator(hass, data_ab_closed)
    s_ab_closed = SyrConnectSensor(c_ab_closed, "d2", "D", "p", "getAB")
    assert s_ab_closed.icon == "mdi:valve-closed"

    # getVLV states
    for raw, expected in [("10", "mdi:valve-closed"), ("11", "mdi:valve"), ("20", "mdi:valve-open"), ("21", "mdi:valve")]:
        data_vlv = {"devices": [{"id": "v1", "name": "V", "project_id": "p", "status": {"getVLV": raw}}]}
        c_vlv = _build_coordinator(hass, data_vlv)
        s_vlv = SyrConnectSensor(c_vlv, "v1", "V", "p", "getVLV")
        assert s_vlv.icon == expected

    # getRG1 numeric timestamp -> valve icon (1) or closed (0)
    ts = int(datetime(2024, 1, 1, 0, 0).timestamp())
    data_rg = {"devices": [{"id": "r1", "name": "R", "project_id": "p", "status": {"getRG1": str(ts)}}]}
    c_rg = _build_coordinator(hass, data_rg)
    s_rg = SyrConnectSensor(c_rg, "r1", "R", "p", "getRG1")
    assert s_rg.icon in ("mdi:valve", "mdi:valve-closed", "mdi:valve-open")


async def test_string_sensor_behavior(hass: HomeAssistant) -> None:
    """Certain sensors should always return strings (e.g., getSRN)."""
    data = {"devices": [{"id": "s1", "name": "S", "project_id": "p", "status": {"getSRN": 12345}}]}
    c = _build_coordinator(hass, data)
    s = SyrConnectSensor(c, "s1", "S", "p", "getSRN")
    assert s.native_value == "12345"

