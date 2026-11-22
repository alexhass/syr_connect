"""Per-device-model entity allowlist overrides.

Each module here describes one device family and defines one POSITIVE allowlist
constant per platform: `SENSOR_SUPPORTED_KEYS`, `SELECT_SUPPORTED_KEYS`,
`SWITCH_SUPPORTED_KEYS`, `BINARY_SENSOR_SUPPORTED_KEYS`, `BUTTON_SUPPORTED_KEYS`,
`VALVE_SUPPORTED_KEYS`. They are collected in the module's `PROFILE`, which the
models of the family reference in `_SYR_CONNECT_MODEL_PROFILES` of `models.py`.
How a device reports its values (units, scales, statistics) is part of its signature
in the library (`aiosyrconnect/model_detection.py`).

`helpers.profile.get_model_supported_keys()` uses these allowlists instead of the global
ones, so the entities created for a device are limited to keys explicitly
confirmed for that model rather than the union of every model's keys. Models
without a profile keep using the global allowlists unchanged.

The global fallback allowlists these override are `_SYR_CONNECT_<PLATFORM>_SUPPORTED_KEYS`
in the platform modules (sensor.py, select.py, ...).
"""

from collections.abc import Mapping, Set as AbstractSet
from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class SyrConnectDeviceProfile:
    """Entity allowlists of a device family.

    Each allowlist field is named after its platform and replaces the platform's global
    allowlist completely; an empty set means "no entities of this platform", None
    keeps the global allowlist.
    """

    binary_sensor: AbstractSet[str] | None
    button: AbstractSet[str] | None
    # Water hardness selects (getIWH, getOWH) whose range depends on the unit: key ->
    # getWHU code -> (lowest, highest, step) in that unit
    hardness_ranges: Mapping[str, Mapping[int, tuple[int, int, int]]] = field(
        default_factory=dict
    )
    select: AbstractSet[str] | None
    # Select keys with an "off" option: key -> raw value written for "off"; a reported
    # value below the lowest other option is shown as "off"
    select_off_values: Mapping[str, int] = field(default_factory=dict)
    # Select keys whose options differ from the global step list of the platform: key ->
    # raw values in ascending order, e.g. other durations for getRMT
    select_options: Mapping[str, list[int]] = field(default_factory=dict)
    sensor: AbstractSet[str] | None
    switch: AbstractSet[str] | None
    # None means the global allowlist of the platform
    update: AbstractSet[str] | None = None
    valve: AbstractSet[str] | None
