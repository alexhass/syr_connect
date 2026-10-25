"""Per-device-model entity allowlist overrides.

Each module here describes one device family and defines one POSITIVE allowlist
constant per platform: `SENSOR_SUPPORTED_KEYS`, `SELECT_SUPPORTED_KEYS`,
`SWITCH_SUPPORTED_KEYS`, `BINARY_SENSOR_SUPPORTED_KEYS`, `BUTTON_SUPPORTED_KEYS`,
`VALVE_SUPPORTED_KEYS`. They are collected in the module's `PROFILE`, which the
signatures of the family reference as `device_profile` in `models.MODEL_SIGNATURES`.
A profile also lists the measurement history series the cloud keeps for the family
(`statistics`), see "Statistics web services" in docs/syrconnect-protocol.md.

`helpers.get_model_supported_keys()` uses these allowlists instead of the global
ones, so the entities created for a device are limited to keys explicitly
confirmed for that model rather than the union of every model's keys. Models
without a profile keep using the global allowlists unchanged.

The global fallback allowlists these override are `_SYR_CONNECT_<PLATFORM>_SUPPORTED_KEYS`
in the platform modules (sensor.py, select.py, ...).
"""

from collections.abc import Mapping, Set as AbstractSet
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class SyrConnectStatistic:
    """Measurement history series that the cloud keeps for a device family.

    The fields are the web service method and the attributes of the ``<sh>`` element
    of the request, see "SafeFloor measurement history" in docs/syrconnect-protocol.md.
    """

    # Sensor key whose measurement history this series holds
    key: str
    # Web service method below the device service path, e.g. "GetSafeFloorStatistics"
    method: str
    # Report type: 1 = week, 2 = month, 3 = year, 4 = raw measurements
    rtyp: int
    # Measurement within the method, e.g. 1 = temperature, 2 = humidity
    t: int
    # Unit of the measurement; the cloud answers with an empty <col /> without it
    unit: str


@dataclass(frozen=True, kw_only=True)
class SyrConnectDeviceProfile:
    """Entity allowlists, alarm codes and statistics of a device family.

    Each allowlist field is named after its platform and replaces the platform's global
    allowlist completely; an empty set means "no entities of this platform".
    """

    # Alarm code family (getALA) of the device; None means the generic codes
    ala_codes: Mapping[str, str] | None = None
    binary_sensor: AbstractSet[str]
    button: AbstractSet[str]
    select: AbstractSet[str]
    sensor: AbstractSet[str]
    # Measurement history series the cloud keeps for the device; empty means none
    statistics: tuple[SyrConnectStatistic, ...] = ()
    switch: AbstractSet[str]
    # None means the global allowlist of the platform
    update: AbstractSet[str] | None = None
    valve: AbstractSet[str]
