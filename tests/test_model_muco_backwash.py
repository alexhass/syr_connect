"""Tests for the entities of the MultiController automatic backwash (RSA)."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect import select as select_module
from custom_components.syr_connect.models import MODELS
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("key", "raw", "option", "value"),
    [
        pytest.param("getRSA", "7", "365 d", 365, id="backwash-interval"),
        pytest.param("getRSE", "30", "1 d", 1, id="reminder-interval"),
    ],
)
async def test_backwash_interval_selects(
    hass: HomeAssistant,
    create_mock_entry_with_coordinator: Callable[
        ..., tuple[MockConfigEntry, MagicMock]
    ],
    mock_add_entities: Callable[[], tuple[list[Any], Mock]],
    key: str,
    raw: str,
    option: str,
    value: int,
) -> None:
    """The backwash and the reminder interval can be set to 1-365 days."""
    data = {
        "devices": [
            {
                "id": "device1",
                "name": "Device 1",
                "project_id": "project1",
                "model": next(m for m in MODELS if m.name == "syrrsaconnect"),
                "status": {key: raw, "getRSD": "30"},
            }
        ]
    }
    mock_config_entry, coordinator = create_mock_entry_with_coordinator(data)
    coordinator.async_set_device_value = AsyncMock()
    entities, async_add_entities = mock_add_entities()

    await select_module.async_setup_entry(hass, mock_config_entry, async_add_entities)

    # The backwash duration (getRSD) is no select
    [select] = entities
    assert select.options == [f"{days} d" for days in range(1, 366)]
    assert select.current_option == f"{raw} d"

    await select.async_select_option(option)

    coordinator.async_set_device_value.assert_called_once_with(
        "device1", f"set{key[3:]}", value
    )
