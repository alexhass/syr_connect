"""Measurement history of SafeFloor sensors as external statistics.

SafeFloor Connect sensors measure every getWMP seconds (e.g. every 6 hours) but
upload to the cloud only every getRCP seconds (e.g. every 4 days, configurable
by the user). The regular status therefore only shows the latest measurement
and the sensor entities miss all values in between.

GetSafeFloorStatistics (report type 4) returns the raw measurements of the last
6 days with their timestamps. After every new upload they are imported as
external statistics ``syr_connect:<serial>_temperature`` and
``syr_connect:<serial>_humidity``. Long-term statistics have an hourly
resolution, so each hour that contains a measurement becomes one row (several
measurements within one hour are combined into mean/min/max). Hours without a
measurement stay empty - no values are interpolated.
"""
from __future__ import annotations

import logging
from collections import defaultdict
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
    """Combine measurements into one statistics row per hour that contains a measurement."""
    hours: dict[datetime, list[float]] = defaultdict(list)
    for timestamp, value in measurements:
        hours[timestamp.replace(minute=0, second=0, microsecond=0)].append(value)
    return [
        StatisticData(
            start=start,
            mean=sum(values) / len(values),
            min=min(values),
            max=max(values),
        )
        for start, values in sorted(hours.items())
    ]


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

    Rows that already exist are overwritten, so importing the same window again is harmless.

    Returns:
        Number of imported hourly rows
    """
    statistics = hourly_statistics(measurements)
    if not statistics:
        return 0
    metadata = StatisticMetaData(
        mean_type=StatisticMeanType.ARITHMETIC,
        has_sum=False,
        name=f"{device_name} {key}",
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
