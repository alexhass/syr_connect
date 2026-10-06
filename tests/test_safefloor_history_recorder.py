"""SafeFloor measurement history with a real recorder (long-term statistics)."""
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.recorder import Recorder, get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
    do_adhoc_statistics,
)

from custom_components.syr_connect.response_parser import ResponseParser
from custom_components.syr_connect.safefloor_history import async_import_safefloor_history

FIXTURES = Path(__file__).parent / "fixtures/xml"
SERIAL = "123456789"
STATISTIC_ID = "syr_connect:123456789_temperature"
ENTITY_ID = "sensor.floor_temperature"
ATTRIBUTES = {"device_class": "temperature", "state_class": "measurement", "unit_of_measurement": "°C"}
DUPLICATE_WARNING = "Blocked attempt to insert duplicated statistic rows"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_db_url: str, enable_custom_integrations: None) -> None:
    """Prepare the recorder database before hass is set up (overrides the conftest fixture)."""


def _utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


async def _hourly_means(hass: HomeAssistant, statistic_id: str, start: datetime) -> list[tuple[str, float]]:
    stats = await get_instance(hass).async_add_executor_job(
        statistics_during_period, hass, start, None, {statistic_id}, "hour", None, {"mean"}
    )
    return [
        (datetime.fromtimestamp(row["start"], UTC).strftime("%d. %H:%M"), round(row["mean"], 3))
        for row in stats.get(statistic_id, [])
    ]


async def test_import_into_recorder(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """The measurements end up in the long-term statistics, one row for every hour without gaps."""
    measurements = ResponseParser.parse_safefloor_statistics_response(
        (FIXTURES / "SyrSafeFloor_GetSafeFloorStatistics_Temperature.xml").read_text(encoding="utf-8")
    )
    async_import_safefloor_history(hass, SERIAL, "Floor", "temperature", "°C", measurements)
    # Importing the same window again (next upload) must not duplicate rows
    async_import_safefloor_history(hass, SERIAL, "Floor", "temperature", "°C", measurements)
    await async_wait_recording_done(hass)

    rows = await _hourly_means(hass, STATISTIC_ID, _utc("2026-09-26 00:00:00"))
    # One row for every hour, no gaps: 26.09. 14:00 to 28.09. 14:00
    assert len(rows) == 49
    assert rows[0] == ("26. 14:00", 14.6)
    # Hours without a measurement take over the hour before, the next measurement hour has its value
    assert rows[5] == ("26. 19:00", 14.6)
    assert rows[6] == ("26. 20:00", 14.9)
    assert rows[-1] == ("28. 14:00", 15.8)


async def test_import_does_not_interfere_with_the_recorder(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """External statistics can be written for any hour, even one the recorder has not compiled yet.

    This is the reason the history is not written into the statistics of the sensor entities:
    the recorder compiles every hour of those exactly once, and a row written there before
    would make that compile run fail. External statistics are never compiled by the recorder,
    so the sensor statistics are compiled as usual and stay unchanged.
    """
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    freezer.move_to(_utc("2026-10-02 10:00:00"))
    hass.states.async_set(ENTITY_ID, "15.0", ATTRIBUTES)
    await async_wait_recording_done(hass)

    # New upload at 11:20: its measurements reach into the running hour 11:00
    freezer.move_to(_utc("2026-10-02 11:20:00"))
    measurements = [(_utc("2026-10-02 09:00:00"), 16.0), (_utc("2026-10-02 11:10:00"), 18.0)]
    assert async_import_safefloor_history(hass, SERIAL, "Floor", "temperature", "°C", measurements) == 3
    await async_wait_recording_done(hass)

    # Afterwards the recorder compiles 10:00 and 11:00 of the sensor (the 5-minute run at :55
    # completes the hour)
    freezer.move_to(_utc("2026-10-02 12:00:00"))
    for minutes in range(0, 120, 5):
        do_adhoc_statistics(hass, start=_utc("2026-10-02 10:00:00") + timedelta(minutes=minutes))
    await async_wait_recording_done(hass)

    start = _utc("2026-10-02 00:00:00")
    assert await _hourly_means(hass, ENTITY_ID, start) == [("02. 10:00", 15.0), ("02. 11:00", 15.0)]
    assert await _hourly_means(hass, STATISTIC_ID, start) == [
        ("02. 09:00", 16.0),
        ("02. 10:00", 16.0),
        ("02. 11:00", 18.0),
    ]
    assert DUPLICATE_WARNING not in caplog.text
