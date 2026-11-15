"""Tests for the device files (devices/*.py) and their profiles."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001
import importlib
import pkgutil

import pytest

from custom_components.syr_connect import (
    binary_sensor,
    button,
    devices,
    select,
    sensor,
    switch,
    update,
    valve,
)
from custom_components.syr_connect.models import MODEL_SIGNATURES

# The profiles of all device files, keyed by module name.
_DEVICE_PROFILES = {
    module.name: importlib.import_module(f"{devices.__name__}.{module.name}").PROFILE
    for module in pkgutil.iter_modules(devices.__path__)
}


_DESCRIBED_KEYS = {
    "sensor": set(sensor._SYR_CONNECT_SENSOR_DESCRIPTIONS),
    "binary_sensor": set(binary_sensor._SYR_CONNECT_BINARY_SENSOR_DESCRIPTIONS),
    "switch": set(switch._SYR_CONNECT_SWITCH_DESCRIPTIONS),
    "button": set(button._SYR_CONNECT_BUTTON_DESCRIPTIONS),
    "select": set(select._SYR_CONNECT_SELECT_DESCRIPTIONS),
    "update": set(update._SYR_CONNECT_UPDATE_DESCRIPTIONS),
    "valve": set(valve._SYR_CONNECT_VALVE_DESCRIPTIONS),
}


@pytest.mark.parametrize("platform", sorted(_DESCRIBED_KEYS))
@pytest.mark.parametrize("device_file", sorted(_DEVICE_PROFILES))
def test_device_file_keys_have_descriptions(device_file: str, platform: str) -> None:
    """Every key a device file supports has an entity description of its platform.

    The entities look their description up by key, so a key without one would fail
    when the entity is created.
    """
    keys = getattr(_DEVICE_PROFILES[device_file], platform) or set()
    assert keys <= _DESCRIBED_KEYS[platform]


@pytest.mark.parametrize("device_file", sorted(_DEVICE_PROFILES))
def test_device_file_statistics_belong_to_its_sensors(device_file: str) -> None:
    """Every measurement history series of a device file is one of its sensors, once."""
    profile = _DEVICE_PROFILES[device_file]
    keys = [statistic.key for statistic in profile.statistics]
    assert set(keys) <= profile.sensor
    assert len(keys) == len(set(keys))


def test_every_device_profile_is_used_by_a_signature() -> None:
    """Every devices/<name>.py profile is referenced by at least one model signature."""
    used = {
        id(signature.device_profile)
        for signature in MODEL_SIGNATURES
        if signature.device_profile is not None
    }
    assert used == {id(profile) for profile in _DEVICE_PROFILES.values()}
