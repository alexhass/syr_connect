"""Measurement history of SafeFloor sensors as external statistics.

The problem
-----------
SafeFloor Connect sensors are battery powered. They measure every getWMP seconds
(e.g. every 6 hours) but upload to the cloud only every getRCP seconds (e.g. every
4 days, configurable by the user). The regular status therefore only carries the
latest measurement: the temperature and humidity sensor entities stay flat for
days and then jump. GetSafeFloorStatistics (report type 4) returns the raw
measurements of the last 6 days with their timestamps.

Why external statistics and not the history of the sensor entities
------------------------------------------------------------------
Home Assistant offers integrations one supported way to store values with a
timestamp in the past: external statistics, written with
``async_add_external_statistics`` ("Add hourly statistics from an external
source"). It was added for exactly this purpose (home-assistant/architecture
discussion #559, "inject historical data"), and core integrations whose data
arrives late from a cloud use it the same way (e.g. opower, tibber, suez_water,
ista_ecotrend, solaredge).

The other places are either impossible or not meant for integrations:

* State history: an entity only has a current state. There is no API to set
  past states, so the flat line in the history of the sensor entities can not be
  corrected. It is not wrong either: it shows what was known at that time.
* Long-term statistics of the sensor entities: these rows belong to the recorder
  (source "recorder"), which compiles every hour exactly once from the recorded
  states. ``async_import_statistics`` is meant for an "internal source" and no
  core integration uses it for its own entities. Writing an hour the recorder has
  not compiled yet makes its next compile run fail on duplicate rows, and that
  hour is then lost for *all* sensors. Using it safely would depend on recorder
  internals that may change with any Home Assistant release.

External statistics belong to this integration (statistic ID
``syr_connect:<serial>_<key>``, source ``syr_connect``). The recorder never
compiles them, so their rows can be written and rewritten at any time without
touching data of Home Assistant, of the sensor entities or of other
integrations.

An external statistic is not a new sensor: it is no entity, has no state, no
entity registry entry and can not be used in automations. It is only the time
series of the real measurements and shows up wherever statistics can be
selected (statistics graph card, Developer tools > Statistics). The sensor
entities are unchanged and keep showing the latest uploaded value. See the
README section "SafeFloor Measurement History".

How the rows are built
----------------------
Long-term statistics have an hourly resolution. Every measurement is valid until
the next one (step curve), and every hour from the first to the last measurement
gets the time-weighted mean and the min/max of the values valid in it - the same
way the recorder compiles the statistics of a sensor entity from its states.
Nothing is interpolated or extrapolated: hours before the first and after the
last measurement are left out and follow with the next upload. Importing the
same 6-day window again overwrites the same rows.
"""
from __future__ import annotations

import logging
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify
from homeassistant.util.unit_conversion import TemperatureConverter, UnitlessRatioConverter

from .const import (
    _SYR_CONNECT_SAFEFLOOR_HISTORY_REFRESH_HOURS,
    _SYR_CONNECT_SAFEFLOOR_HISTORY_RETRY_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_HOUR = timedelta(hours=1)

# Unit -> unit class used by the recorder for unit conversion
_UNIT_CLASSES: dict[str, str | None] = {
    UnitOfTemperature.CELSIUS: TemperatureConverter.UNIT_CLASS,
    PERCENTAGE: UnitlessRatioConverter.UNIT_CLASS,
}


@dataclass
class SafeFloorHistoryState:
    """Fetch state of the measurement history of one SafeFloor device.

    The history is fetched when the device uploaded new data (the timestamp of
    getSRN changes), on the first update after setup and at the latest after
    _SYR_CONNECT_SAFEFLOOR_HISTORY_REFRESH_HOURS as a safety net. After a failed
    fetch the next attempt waits _SYR_CONNECT_SAFEFLOOR_HISTORY_RETRY_MINUTES.
    """

    upload_marker: str | None = None
    imported_at: datetime | None = None
    retry_at: datetime | None = None

    def is_due(self, upload_marker: str | None, now: datetime) -> bool:
        """Return True if the history should be fetched now."""
        if self.retry_at is not None and now < self.retry_at:
            return False
        if self.imported_at is None or upload_marker != self.upload_marker:
            return True
        return now - self.imported_at >= timedelta(hours=_SYR_CONNECT_SAFEFLOOR_HISTORY_REFRESH_HOURS)

    def mark_imported(self, upload_marker: str | None, now: datetime) -> None:
        """Remember a successful import."""
        self.upload_marker = upload_marker
        self.imported_at = now
        self.retry_at = None

    def mark_failed(self, now: datetime) -> None:
        """Delay the next attempt after a failed fetch."""
        self.retry_at = now + timedelta(minutes=_SYR_CONNECT_SAFEFLOOR_HISTORY_RETRY_MINUTES)


def safefloor_statistic_id(serial_number: str, key: str) -> str:
    """Return the external statistic ID of a SafeFloor measurement series."""
    return f"{DOMAIN}:{slugify(serial_number)}_{key}"


def hourly_statistics(measurements: list[tuple[datetime, float]]) -> list[StatisticData]:
    """Return one row per hour from the first to the last measurement (step curve).

    Every measurement is valid until the next one, the last one until the end of
    its hour. A row holds the time-weighted mean and the min/max of the values
    valid during that hour. Every hour needs a row: the statistics graph card
    draws a gap between rows that do not follow each other, so one row per
    measurement (e.g. every 6 hours) would only be shown as short dashes.

    The hour of the first measurement is skipped unless the measurement is at the
    full hour, because the value before it is not known.
    """
    points = sorted(measurements)
    if not points:
        return []
    times = [timestamp for timestamp, _ in points]
    start = times[0].replace(minute=0, second=0, microsecond=0)
    if start < times[0]:
        start += _HOUR
    last_hour = times[-1].replace(minute=0, second=0, microsecond=0)
    result: list[StatisticData] = []
    while start <= last_hour:
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
        start = end
    return result


@callback
def async_import_safefloor_history(
    hass: HomeAssistant,
    serial_number: str,
    device_name: str,
    key: str,
    unit: str,
    measurements: list[tuple[datetime, float]],
) -> int:
    """Import SafeFloor measurements as external statistics.

    This is the supported Home Assistant API for values with a past timestamp
    (see the module docstring for why the sensor entities are not changed).
    Rows that already exist are overwritten, so importing the same window again is harmless.

    Returns:
        Number of imported hourly rows
    """
    statistics = hourly_statistics(measurements)
    if not statistics:
        return 0
    # mean_type and unit_class are set explicitly: without them Home Assistant logs a
    # warning and refuses the import from 2026.11 on.
    metadata = StatisticMetaData(
        mean_type=StatisticMeanType.ARITHMETIC,
        has_sum=False,
        # "history" marks the series as measurement history, not as a second sensor
        name=f"{device_name} {key} history",
        source=DOMAIN,
        statistic_id=safefloor_statistic_id(serial_number, key),
        unit_class=_UNIT_CLASSES.get(unit),
        unit_of_measurement=unit,
    )
    async_add_external_statistics(hass, metadata, statistics)
    _LOGGER.debug(
        "Imported %d hourly row(s) into %s (%s to %s)",
        len(statistics),
        metadata["statistic_id"],
        statistics[0]["start"].isoformat(),
        statistics[-1]["start"].isoformat(),
    )
    return len(statistics)
