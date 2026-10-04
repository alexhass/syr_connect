"""SafeFloor measurement history with a real recorder (long-term statistics of the sensors)."""
from datetime import UTC, datetime, timedelta
from functools import partial

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.recorder import Recorder, get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMeanType, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_metadata,
    statistics_during_period,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
    do_adhoc_statistics,
)

from custom_components.syr_connect.safefloor_history import async_write_safefloor_history

ENTITY_ID = "sensor.floor_temperature"
ATTRIBUTES = {"device_class": "temperature", "state_class": "measurement", "unit_of_measurement": "°C"}
DUPLICATE_WARNING = "Blocked attempt to insert duplicated statistic rows"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_db_url: str, enable_custom_integrations: None) -> None:
    """Prepare the recorder database before hass is set up (overrides the conftest fixture)."""


def _utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


async def _compile_hours(hass: HomeAssistant, start: datetime, hours: int) -> None:
    """Run the 5-minute statistics runs of the recorder; the run at :55 compiles the hour."""
    for minutes in range(0, hours * 60, 5):
        do_adhoc_statistics(hass, start=start + timedelta(minutes=minutes))
    await async_wait_recording_done(hass)


async def _hourly_rows(
    hass: HomeAssistant, statistic_id: str, units: dict[str, str] | None = None
) -> list[tuple[str, float, float, float]]:
    stats = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        _utc("2026-10-01 00:00"),
        None,
        {statistic_id},
        "hour",
        units,
        {"mean", "min", "max"},
    )
    return [
        (
            datetime.fromtimestamp(row["start"], UTC).strftime("%H:%M"),
            round(row["mean"], 3),
            round(row["min"], 3),
            round(row["max"], 3),
        )
        for row in stats.get(statistic_id, [])
    ]


async def _metadata(hass: HomeAssistant, statistic_id: str) -> dict:
    return await get_instance(hass).async_add_executor_job(partial(get_metadata, hass, statistic_ids={statistic_id}))


def _import(hass: HomeAssistant, statistic_id: str, unit_class: str, unit: str, rows: list[StatisticData]) -> None:
    """Create hourly rows as the recorder would have compiled them."""
    async_import_statistics(
        hass,
        StatisticMetaData(
            mean_type=StatisticMeanType.ARITHMETIC,
            has_sum=False,
            name=None,
            source="recorder",
            statistic_id=statistic_id,
            unit_class=unit_class,
            unit_of_measurement=unit,
        ),
        rows,
    )


async def test_overwrites_only_hours_the_recorder_has_compiled(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Compiled hours get the step curve, newer hours are left to the recorder: no duplicate rows."""
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    # Last upload: 15.0 °C. The recorder compiles 10:00 and 11:00 with this flat value.
    freezer.move_to(_utc("2026-10-02 10:00"))
    hass.states.async_set(ENTITY_ID, "15.0", ATTRIBUTES)
    await async_wait_recording_done(hass)
    freezer.move_to(_utc("2026-10-02 12:20"))
    await _compile_hours(hass, _utc("2026-10-02 10:00"), 2)
    assert await _hourly_rows(hass, ENTITY_ID) == [("10:00", 15.0, 15.0, 15.0), ("11:00", 15.0, 15.0, 15.0)]
    metadata = await _metadata(hass, ENTITY_ID)

    # New upload at 12:20 with the measurements taken since the last upload
    hass.states.async_set(ENTITY_ID, "18.0", ATTRIBUTES)
    measurements = [
        (_utc("2026-10-02 10:30"), 16.0),
        (_utc("2026-10-02 11:30"), 17.0),
        (_utc("2026-10-02 12:10"), 18.0),
    ]
    assert await async_write_safefloor_history(hass, ENTITY_ID, "°C", measurements) == _utc("2026-10-02 11:00")
    await async_wait_recording_done(hass)

    # 10:00 started before the first measurement and is kept; 11:00 gets the step curve;
    # 12:00 has not been compiled yet and is not written
    assert await _hourly_rows(hass, ENTITY_ID) == [("10:00", 15.0, 15.0, 15.0), ("11:00", 16.5, 16.0, 17.0)]
    assert await _metadata(hass, ENTITY_ID) == metadata

    # The recorder compiles 12:00 after it has ended, without conflict
    freezer.move_to(_utc("2026-10-02 13:00"))
    await _compile_hours(hass, _utc("2026-10-02 12:00"), 1)
    assert [row[0] for row in await _hourly_rows(hass, ENTITY_ID)] == ["10:00", "11:00", "12:00"]

    # The follow-up fetch corrects the hour of the upload
    assert await async_write_safefloor_history(hass, ENTITY_ID, "°C", measurements) == _utc("2026-10-02 12:00")
    await async_wait_recording_done(hass)
    assert (await _hourly_rows(hass, ENTITY_ID))[2] == ("12:00", round((10 * 17.0 + 50 * 18.0) / 60, 3), 17.0, 18.0)
    assert await _metadata(hass, ENTITY_ID) == metadata
    assert DUPLICATE_WARNING not in caplog.text


async def test_converts_unit_and_keeps_gaps(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Values are converted into the unit of the statistics; hours without a row stay empty."""
    _import(
        hass,
        ENTITY_ID,
        "temperature",
        "°F",
        [
            StatisticData(start=_utc("2026-10-02 10:00"), mean=50.0, min=50.0, max=50.0),
            StatisticData(start=_utc("2026-10-02 12:00"), mean=50.0, min=50.0, max=50.0),
        ],
    )
    await async_wait_recording_done(hass)

    measurements = [(_utc("2026-10-02 10:00"), 20.0), (_utc("2026-10-02 12:30"), 25.0)]
    assert await async_write_safefloor_history(hass, ENTITY_ID, "°C", measurements) == _utc("2026-10-02 12:00")
    await async_wait_recording_done(hass)

    assert await _hourly_rows(hass, ENTITY_ID, {"temperature": "°F"}) == [
        ("10:00", 68.0, 68.0, 68.0),
        ("12:00", 72.5, 68.0, 77.0),
    ]


async def test_nothing_written(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Nothing is written without measurements, statistics, plain mean, convertible unit or compiled hour."""
    measurements = [(_utc("2026-10-02 10:30"), 20.0)]
    assert await async_write_safefloor_history(hass, ENTITY_ID, "°C", []) is None
    # No statistics yet (e.g. sensor just added)
    assert await async_write_safefloor_history(hass, ENTITY_ID, "°C", measurements) is None

    row = StatisticData(start=_utc("2026-10-02 10:00"), mean=1.0, min=1.0, max=1.0)
    _import(hass, ENTITY_ID, "temperature", "°C", [row])
    _import(hass, "sensor.floor_power", "power", "W", [row])
    async_import_statistics(
        hass,
        StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=None,
            source="recorder",
            statistic_id="sensor.floor_energy",
            unit_class="energy",
            unit_of_measurement="kWh",
        ),
        [StatisticData(start=_utc("2026-10-02 10:00"), state=1.0, sum=1.0)],
    )
    await async_wait_recording_done(hass)

    # Not a mean, unit not convertible, unit without converter
    assert await async_write_safefloor_history(hass, "sensor.floor_energy", "kWh", measurements) is None
    assert await async_write_safefloor_history(hass, "sensor.floor_power", "°C", measurements) is None
    assert await async_write_safefloor_history(hass, ENTITY_ID, "lx", measurements) is None
    # The only compiled hour started before the first measurement
    assert await async_write_safefloor_history(hass, ENTITY_ID, "°C", measurements) is None
    await async_wait_recording_done(hass)

    assert await _hourly_rows(hass, ENTITY_ID) == [("10:00", 1.0, 1.0, 1.0)]
    assert await _hourly_rows(hass, "sensor.floor_power") == [("10:00", 1.0, 1.0, 1.0)]
