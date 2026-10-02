"""SafeFloor measurement history with a real recorder (long-term statistics)."""
from datetime import UTC, datetime
from pathlib import Path

import pytest
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done

from custom_components.syr_connect.response_parser import ResponseParser
from custom_components.syr_connect.safefloor_history import async_import_safefloor_history

FIXTURES = Path(__file__).parent / "fixtures/xml"
SERIAL = "123456789"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_db_url: str, enable_custom_integrations: None) -> None:
    """Prepare the recorder database before hass is set up (overrides the conftest fixture)."""


def _utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


async def test_import_into_recorder(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """The measurements end up in the long-term statistics, one row per measurement."""
    measurements = ResponseParser.parse_safefloor_statistics_response(
        (FIXTURES / "SyrSafeFloor_GetSafeFloorStatistics_Temperature.xml").read_text(encoding="utf-8")
    )
    async_import_safefloor_history(hass, SERIAL, "Floor", "temperature", "°C", measurements)
    # Importing the same window again (next upload) must not duplicate rows
    async_import_safefloor_history(hass, SERIAL, "Floor", "temperature", "°C", measurements)
    await async_wait_recording_done(hass)

    statistic_id = "syr_connect:123456789_temperature"
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        _utc("2026-09-26 00:00:00"),
        None,
        {statistic_id},
        "hour",
        None,
        {"mean", "min", "max"},
    )
    rows = stats[statistic_id]
    assert len(rows) == 9
    assert rows[0]["start"] == _utc("2026-09-26 14:00:00").timestamp()
    assert rows[0]["mean"] == pytest.approx(14.6)
    assert rows[-1]["start"] == _utc("2026-09-28 14:00:00").timestamp()
    assert rows[-1]["mean"] == pytest.approx(15.8)
