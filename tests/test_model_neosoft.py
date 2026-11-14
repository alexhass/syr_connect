"""Tests for the entities of the NeoSoft family."""

# The tests check private attributes of the entities.
# ruff: noqa: SLF001

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect.models import detect_model
from custom_components.syr_connect.select import async_setup_entry
from homeassistant.core import HomeAssistant


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
