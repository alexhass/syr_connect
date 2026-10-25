"""Tests for the SYR Connect base entity."""

# The unit tests in this module check private attributes directly.
# ruff: noqa: SLF001

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

from custom_components.syr_connect.data import SyrConnectDevice
from custom_components.syr_connect.entity import async_add_device_entities
from custom_components.syr_connect.switch import SyrConnectBooleanSwitch


def test_entity_name_before_added_is_translation_key(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Before the entity is added, exception messages name it by its translation key."""
    switch = SyrConnectBooleanSwitch(
        create_mock_coordinator({"devices": []}), "dev", "Keller", "getBUZ"
    )

    assert switch._entity_name == "getbuz"


def test_entity_name_after_added_is_translated_name(
    create_mock_coordinator: Callable[..., MagicMock],
) -> None:
    """Once the entity is added, exception messages use its translated name."""
    switch = SyrConnectBooleanSwitch(
        create_mock_coordinator({"devices": []}), "dev", "Keller", "getBUZ"
    )
    switch.platform = MagicMock()

    with patch.object(
        SyrConnectBooleanSwitch, "name", new_callable=PropertyMock
    ) as name:
        name.return_value = "Summer"
        assert switch._entity_name == "Summer"

        # No name (e.g. translation missing): fall back to the translation key
        name.return_value = None
        assert switch._entity_name == "getbuz"


def _device(device_id: str, status: dict[str, Any]) -> SyrConnectDevice:
    return {"id": device_id, "dclg": device_id, "name": device_id, "status": status}


def _build(device: SyrConnectDevice) -> list[Any]:
    """Stand in for the entities of a device: one marker per device."""
    return [f"entity-{device['id']}"]


def test_add_device_entities_adds_devices_that_appear_later() -> None:
    """Every device is set up once, also when it appears after the setup."""
    coordinator = MagicMock()
    coordinator.data = {"devices": [_device("A", {"getSRN": "A"})]}
    entry = MagicMock()
    add_entities = MagicMock()

    async_add_device_entities(entry, coordinator, add_entities, _build)
    add_entities.assert_called_once_with(["entity-A"])
    listener = coordinator.async_add_listener.call_args.args[0]
    # The listener is removed when the entry is unloaded
    entry.async_on_unload.assert_called_once_with(
        coordinator.async_add_listener.return_value
    )

    # An update with the same device adds nothing
    add_entities.reset_mock()
    listener()
    add_entities.assert_not_called()

    # A new device in the account gets its entities with the next update
    coordinator.data["devices"].append(_device("B", {"getSRN": "B"}))
    listener()
    add_entities.assert_called_once_with(["entity-B"])


def test_add_device_entities_waits_for_the_status() -> None:
    """A device without status (not fetched yet) is set up once its status arrives."""
    coordinator = MagicMock()
    coordinator.data = {"devices": [_device("A", {})]}
    add_entities = MagicMock()

    async_add_device_entities(MagicMock(), coordinator, add_entities, _build)
    add_entities.assert_not_called()

    coordinator.data["devices"][0]["status"] = {"getSRN": "A"}
    coordinator.async_add_listener.call_args.args[0]()
    add_entities.assert_called_once_with(["entity-A"])


def test_add_device_entities_without_data() -> None:
    """Without coordinator data nothing is added."""
    coordinator = MagicMock()
    coordinator.data = None
    add_entities = MagicMock()

    async_add_device_entities(MagicMock(), coordinator, add_entities, _build)

    add_entities.assert_not_called()
