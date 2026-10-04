"""Measurement history of SafeFloor sensors written into the sensors' long-term statistics.

SafeFloor Connect sensors measure every getWMP seconds (e.g. every 6 hours) but
upload to the cloud only every getRCP seconds (e.g. every 4 days, configurable
by the user). Between two uploads the temperature (getCEL) and humidity (getHMD)
sensors keep the last uploaded value, so their long-term statistics show a flat
line followed by a jump at every upload.

GetSafeFloorStatistics (report type 4) returns the raw measurements of the last
6 days with their timestamps. After every upload they are written into the
hourly long-term statistics of the two sensor entities: every measurement is
valid until the next one, and each hour gets mean, min and max of this step
curve (time-weighted mean).

Only hourly rows that the recorder has already compiled are overwritten, a row
is never added. The recorder inserts the row of an hour exactly once, in the
statistics run right after the hour has ended, and that insert fails if the row
already exists (all statistics of that run would be lost). A row that exists has
therefore been compiled already and will never be inserted again, so overwriting
it cannot collide with the recorder - independent of the clock or a delayed
recorder queue. Hours the recorder has not compiled yet (e.g. the current hour)
are skipped and corrected by the next fetch.

The state history (history graph of the last days) and the 5-minute statistics
can not be changed afterwards and keep the flat line.
"""
from __future__ import annotations

import logging
from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_metadata,
    statistics_during_period,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import (
    BaseUnitConverter,
    TemperatureConverter,
    UnitlessRatioConverter,
)

from .const import (
    _SYR_CONNECT_SAFEFLOOR_HISTORY_FOLLOW_UP_MINUTES,
    _SYR_CONNECT_SAFEFLOOR_HISTORY_REFRESH_HOURS,
    _SYR_CONNECT_SAFEFLOOR_HISTORY_RETRY_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

_HOUR = timedelta(hours=1)

# Unit of the cloud values -> converter into the unit of the entity statistics (e.g. °F)
_UNIT_CONVERTERS: dict[str, type[BaseUnitConverter]] = {
    UnitOfTemperature.CELSIUS: TemperatureConverter,
    PERCENTAGE: UnitlessRatioConverter,
}


@dataclass
class SafeFloorHistoryState:
    """Fetch state of the measurement history of one SafeFloor device.

    The history is fetched when the device uploaded new data (the timestamp of
    getSRN changes) and on the first update after setup. Such a fetch is followed
    by a second one _SYR_CONNECT_SAFEFLOOR_HISTORY_FOLLOW_UP_MINUTES later: the
    hour in which the sensor state jumped is compiled by the recorder only after
    it has ended. Without new uploads the history is fetched again after
    _SYR_CONNECT_SAFEFLOOR_HISTORY_REFRESH_HOURS as a safety net. After a failed
    fetch the next attempt waits _SYR_CONNECT_SAFEFLOOR_HISTORY_RETRY_MINUTES.
    """

    upload_marker: str | None = None
    imported_at: datetime | None = None
    retry_at: datetime | None = None
    follow_up_at: datetime | None = None

    def is_due(self, upload_marker: str | None, now: datetime) -> bool:
        """Return True if the history should be fetched now."""
        if self.retry_at is not None and now < self.retry_at:
            return False
        if self.imported_at is None or upload_marker != self.upload_marker:
            return True
        if self.follow_up_at is not None and now >= self.follow_up_at:
            return True
        return now - self.imported_at >= timedelta(hours=_SYR_CONNECT_SAFEFLOOR_HISTORY_REFRESH_HOURS)

    def mark_imported(self, upload_marker: str | None, now: datetime) -> None:
        """Remember a successful import and plan the follow-up after a new upload."""
        new_upload = self.imported_at is None or upload_marker != self.upload_marker
        self.upload_marker = upload_marker
        self.imported_at = now
        self.retry_at = None
        self.follow_up_at = (
            now + timedelta(minutes=_SYR_CONNECT_SAFEFLOOR_HISTORY_FOLLOW_UP_MINUTES) if new_upload else None
        )

    def mark_failed(self, now: datetime) -> None:
        """Delay the next attempt after a failed fetch."""
        self.retry_at = now + timedelta(minutes=_SYR_CONNECT_SAFEFLOOR_HISTORY_RETRY_MINUTES)


def step_curve_statistics(
    measurements: list[tuple[datetime, float]], hours: Iterable[datetime]
) -> list[StatisticData]:
    """Return mean, min and max of the step curve of the measurements for the given hours.

    Every measurement is valid until the next one, the last one until the end of
    the hour. Only hours starting at or after the first measurement are returned,
    for earlier hours the value is not known for the whole hour.
    """
    points = sorted(measurements)
    if not points:
        return []
    times = [timestamp for timestamp, _ in points]
    result: list[StatisticData] = []
    for start in sorted(hours):
        if start < times[0]:
            continue
        end = start + _HOUR
        # Measurement valid at the start of the hour, then all measurements within the hour
        index = bisect_right(times, start) - 1
        weighted_sum = 0.0
        values: list[float] = []
        while index < len(points) and times[index] < end:
            segment_start = max(times[index], start)
            segment_end = min(times[index + 1], end) if index + 1 < len(points) else end
            weighted_sum += points[index][1] * (segment_end - segment_start).total_seconds()
            values.append(points[index][1])
            index += 1
        result.append(
            StatisticData(
                start=start,
                mean=weighted_sum / _HOUR.total_seconds(),
                min=min(values),
                max=max(values),
            )
        )
    return result


async def async_write_safefloor_history(
    hass: HomeAssistant,
    statistic_id: str,
    unit: str,
    measurements: list[tuple[datetime, float]],
) -> datetime | None:
    """Overwrite the compiled hourly statistics of a sensor entity with its measurement history.

    Args:
        hass: Home Assistant instance
        statistic_id: Entity ID of the sensor (its long-term statistics)
        unit: Unit of the measurement values
        measurements: (timestamp in UTC, value) tuples

    Returns:
        Start of the newest hour written, or None if nothing was written
    """
    if not measurements:
        return None
    instance = get_instance(hass)

    metadata = await instance.async_add_executor_job(
        partial(get_metadata, hass, statistic_ids={statistic_id})
    )
    if statistic_id not in metadata:
        _LOGGER.debug("No long-term statistics for %s yet, measurement history not written", statistic_id)
        return None
    current = metadata[statistic_id][1]
    if current["mean_type"] != StatisticMeanType.ARITHMETIC or current["has_sum"]:
        _LOGGER.debug("Statistics of %s are not a plain mean, measurement history not written", statistic_id)
        return None

    # The statistics keep the unit of the entity (e.g. °F if the user changed it)
    statistics_unit = current["unit_of_measurement"]
    if statistics_unit != unit:
        converter = _UNIT_CONVERTERS.get(unit)
        if converter is None or statistics_unit not in converter.VALID_UNITS:
            _LOGGER.debug(
                "Can not convert %s to %s of %s, measurement history not written", unit, statistics_unit, statistic_id
            )
            return None
        convert = converter.converter_factory(unit, statistics_unit)
        measurements = [(timestamp, convert(value)) for timestamp, value in measurements]

    # Hourly rows the recorder has already compiled; only these are overwritten (see module docstring)
    first_hour = min(timestamp for timestamp, _ in measurements).replace(minute=0, second=0, microsecond=0)
    rows = await instance.async_add_executor_job(
        statistics_during_period, hass, first_hour, None, {statistic_id}, "hour", None, {"mean"}
    )
    compiled_hours = [dt_util.utc_from_timestamp(row["start"]) for row in rows.get(statistic_id, [])]
    statistics = step_curve_statistics(measurements, compiled_hours)
    if not statistics:
        return None

    # Pass the metadata unchanged, otherwise the import would modify it
    async_import_statistics(
        hass,
        StatisticMetaData(
            mean_type=current["mean_type"],
            has_sum=current["has_sum"],
            name=current["name"],
            source=current["source"],
            statistic_id=statistic_id,
            unit_class=current["unit_class"],
            unit_of_measurement=statistics_unit,
        ),
        statistics,
    )
    _LOGGER.debug(
        "Wrote %d hourly row(s) of %s (%s to %s)",
        len(statistics),
        statistic_id,
        statistics[0]["start"].isoformat(),
        statistics[-1]["start"].isoformat(),
    )
    return statistics[-1]["start"]
