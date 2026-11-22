"""Tests for the entities of the NeoSoft family."""

# The tests check private attributes of the entities.
# ruff: noqa: SLF001

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect import button as button_module
from custom_components.syr_connect.aiosyrconnect import SyrConnectJsonAPI
from custom_components.syr_connect.button import SyrConnectButton
from custom_components.syr_connect.models import MODELS, detect_model
from custom_components.syr_connect.select import async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError


@pytest.mark.parametrize(
    ("srn_prefix", "expected_name"),
    [
        ("206", "neosoft2500"),
        ("207", "sanibelsoftwateruno"),
        ("208", "conceptsingle"),
        ("209", "optimasingle"),
        ("210", "concept200duo"),
        ("211", "optimat2duo"),
        ("212", "sanibelsoftwaterduo"),
        ("213", "optimaduo"),
        ("214", "conelclearprosofttwin"),
        ("215", "conelclearprosoft"),
        ("216", "conceptduo"),
        ("217", "ditechduo"),
        ("218", "takeduo"),
        ("219", "ditechsingle"),
        ("220", "takesingle"),
    ],
)
async def test_async_setup_entry_skips_getsv1_select_for_neosoft_family_rebrands(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    srn_prefix: Any,
    expected_name: Any,
) -> None:
    """No NeoSoft rebrand sibling gets a getSV1 select.

    All rebrand-only siblings sharing the device file neosoft_single/neosoft_duo
    (CONEL/Sanibel/Concept/Optima/Ditech/TAKE) are the same NeoSoft-platform
    hardware with the same built-in salt level sensor, so none of them get a
    getSV1 select.
    """
    status: dict[str, object] = {
        "getSRN": f"{srn_prefix}AAA00001",
        "getSV1": "5",
    }
    assert detect_model(status).name == expected_name

    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Test Device",
                "project_id": "project1",
                "status": status,
            }
        ]
    }
    mock_config_entry, _mock_coordinator = create_mock_entry_with_coordinator(data)
    entities, async_add_entities = mock_add_entities()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    sv1_entities = [
        e for e in entities if hasattr(e, "_sensor_key") and e._sensor_key == "getSV1"
    ]
    assert len(sv1_entities) == 0


def _neosoft_data(name: str, status: dict[str, Any]) -> dict[str, Any]:
    """Return the coordinator data of one NeoSoft of the model with the status."""
    return {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "model": next(model for model in MODELS if model.name == name),
                "status": status,
            }
        ]
    }


@pytest.mark.parametrize(
    ("name", "status"),
    [
        pytest.param("neosoft2500", {"getRG1": "0"}, id="cloud-without-getsir"),
        pytest.param("sanibelsoftwateruno", {"getRG1": 0}, id="local-without-getsir"),
        pytest.param("neosoft5000", {"getRG1": 0, "getSIR": False}, id="local"),
    ],
)
async def test_neosoft_regeneration_button_follows_getrg1(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    name: str,
    status: dict[str, Any],
) -> None:
    """A NeoSoft that reports getRG1 gets the manual regeneration button."""
    mock_config_entry, _ = create_mock_entry_with_coordinator(
        _neosoft_data(name, status)
    )
    entities, async_add_entities = mock_add_entities()

    await button_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert "setSIR" in {e._command for e in entities}


@pytest.mark.parametrize(
    ("local", "status", "expected"),
    [
        pytest.param(False, {"getRG1": "0"}, ("dmSIR", "true"), id="cloud"),
        pytest.param(
            True, {"getRG1": 0, "getSIR": False}, ("setSIR", "true"), id="local"
        ),
    ],
)
async def test_neosoft_regeneration_button_command(
    create_mock_coordinator: Callable[..., MagicMock],
    local: bool,
    status: dict[str, Any],
    expected: tuple[str, Any],
) -> None:
    """The NeoSoft starts a regeneration with dmSIR in the cloud, setSIR locally."""
    coordinator = create_mock_coordinator(_neosoft_data("neosoft2500", status))
    if local:
        coordinator.api.__class__ = SyrConnectJsonAPI
    button = SyrConnectButton(coordinator, "device1", "Device 1", "setSIR")

    await button.async_press()

    coordinator.async_set_device_value.assert_awaited_once_with("device1", *expected)


async def test_neosoft_regeneration_button_refused_while_running(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """No regeneration is started while one runs (getRG1 is not 0)."""
    coordinator = create_mock_coordinator(_neosoft_data("neosoft2500", {"getRG1": "1"}))
    button = SyrConnectButton(coordinator, "device1", "Device 1", "setSIR")

    with pytest.raises(ServiceValidationError) as exc_info:
        await button.async_press()

    assert exc_info.value.translation_key == "regeneration_running"
    assert exc_info.value.translation_placeholders == {"device": "Device 1"}
    coordinator.async_set_device_value.assert_not_awaited()
