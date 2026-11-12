"""Control tests: the entities that write to a device come only from its device file."""

# The control tests build the entities with the private builders of the platforms.
# ruff: noqa: SLF001

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from custom_components.syr_connect.api_json import SyrConnectJsonAPI
from custom_components.syr_connect.button import SyrConnectButton, _build_device_buttons
from custom_components.syr_connect.data import SyrConnectDevice
from custom_components.syr_connect.models import MODEL_SIGNATURES, SyrConnectModel
from custom_components.syr_connect.response_parser import ResponseParser
from custom_components.syr_connect.select import (
    SyrConnectPrfSelect,
    SyrConnectRegenerationSelect,
    SyrConnectRotationSelect,
    _build_device_selects,
)
from custom_components.syr_connect.switch import (
    SyrConnectBooleanSwitch,
    _build_device_switches,
)
from custom_components.syr_connect.valve import SyrConnectValve, _build_device_valves
from homeassistant.core import HomeAssistant

_SYR_CONNECT_TEST_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "xml"


def _all_fixture_keys() -> dict[str, Any]:
    """Return every status key of the XML fixtures with its first non-empty value.

    A device that reports every key known from real devices shows which entities the
    platforms would create beyond the device file.
    """
    status: dict[str, Any] = {}
    parser = ResponseParser()
    for path in sorted(
        _SYR_CONNECT_TEST_FIXTURE_DIR.glob("*_GetDeviceCollectionStatus*.xml")
    ):
        parsed = parser.parse_device_status_response(path.read_text(encoding="utf-8"))
        for key, value in (parsed or {}).items():
            if value is not None and value != "" and key not in status:
                status[key] = value
    # At least one leak protection profile active, so the profile select applies
    status["getPA1"] = "true"
    return status


_SYR_CONNECT_TEST_ALL_KEYS_STATUS = _all_fixture_keys()


def _device(model: SyrConnectModel) -> SyrConnectDevice:
    """Return a device of the model that reports every known status key."""
    device = {
        "id": "device1",
        "name": "Device 1",
        "model": model,
        "status": dict(_SYR_CONNECT_TEST_ALL_KEYS_STATUS),
    }
    return cast(SyrConnectDevice, device)


def _select_key(entity: Any) -> str:
    """Return the status key of a select entity."""
    if isinstance(entity, SyrConnectPrfSelect):
        return "getPRF"
    if isinstance(entity, SyrConnectRotationSelect):
        return "getSRO"
    if isinstance(entity, SyrConnectRegenerationSelect):
        return "getRTM"
    return str(entity._sensor_key)


def _allowlist(model: SyrConnectModel, platform: str) -> set[str]:
    """Return the allowlist of the device file for a platform, empty without one."""
    profile = model.device_profile
    return set(getattr(profile, platform)) if profile is not None else set()


@pytest.mark.parametrize("model", MODEL_SIGNATURES, ids=lambda model: model.name)
async def test_write_entities_only_from_the_device_file(
    hass: HomeAssistant,
    create_mock_coordinator: Callable[..., MagicMock],
    model: SyrConnectModel,
) -> None:
    """Selects, switches, buttons and valves only come from the device file of the model.

    The device reports every key of the fixtures. Any entity whose key is not in the
    allowlist of the device file would come from a global list, which the platforms
    that write to the device must not have; a model without a device file has none.
    """
    device = _device(model)
    coordinator = create_mock_coordinator({"devices": [device]})
    # setDEX is only offered by the local JSON API
    coordinator.api.__class__ = SyrConnectJsonAPI

    selects = {_select_key(e) for e in _build_device_selects(coordinator, device)}
    switches = {
        e._sensor_key
        for e in _build_device_switches(coordinator, device)
        if isinstance(e, SyrConnectBooleanSwitch)
    }
    buttons = {
        e._command
        for e in _build_device_buttons(hass, coordinator, device)
        if isinstance(e, SyrConnectButton)
    }
    valves = {
        e._sensor_key
        for e in _build_device_valves(coordinator, device)
        if isinstance(e, SyrConnectValve)
    }

    assert selects <= _allowlist(model, "select")
    assert switches <= _allowlist(model, "switch")
    assert buttons <= _allowlist(model, "button")
    assert valves <= _allowlist(model, "valve")
    if model.device_profile is None:
        assert not (selects | switches | buttons | valves)


@pytest.mark.parametrize(
    "model",
    [model for model in MODEL_SIGNATURES if model.device_profile is not None],
    ids=lambda model: model.name,
)
def test_regeneration_button_only_for_models_with_regeneration(
    model: SyrConnectModel,
) -> None:
    """The manual regeneration (setSIR) is only listed for models with a regeneration.

    Models without scheduled regeneration report getSIR as well, but a manual
    regeneration makes no sense there (issue #24).
    """
    assert model.device_profile is not None
    if "setSIR" in model.device_profile.button:
        assert model.maximum_regeneration_interval is not None
