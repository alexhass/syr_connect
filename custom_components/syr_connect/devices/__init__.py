"""Per-device-model entity allowlist overrides.

Each module here describes one device family and defines one POSITIVE allowlist
constant per platform: `SENSOR_SUPPORTED_KEYS`, `SELECT_SUPPORTED_KEYS`,
`SWITCH_SUPPORTED_KEYS`, `BINARY_SENSOR_SUPPORTED_KEYS`, `BUTTON_SUPPORTED_KEYS`,
`VALVE_SUPPORTED_KEYS`. They are collected in the module's `PROFILE`, which the
signatures of the family reference as `device_profile` in `models.MODEL_SIGNATURES`.

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
class SyrConnectDeviceProfile:
    """Entity allowlists and alarm codes of a device family.

    Each allowlist field is named after its platform and replaces the platform's global
    allowlist completely; an empty set means "no entities of this platform".
    """

    # Alarm code family (getALA) of the device; None means the generic codes
    ala_codes: Mapping[str, str] | None = None
    binary_sensor: AbstractSet[str]
    button: AbstractSet[str]
    select: AbstractSet[str]
    sensor: AbstractSet[str]
    switch: AbstractSet[str]
    # None means the global allowlist of the platform
    update: AbstractSet[str] | None = None
    valve: AbstractSet[str]
