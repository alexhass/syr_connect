"""Tests for the SYR Connect base entity."""

# The unit tests in this module check private attributes directly.
# ruff: noqa: SLF001

from unittest.mock import MagicMock, PropertyMock, patch

from custom_components.syr_connect.switch import SyrConnectBooleanSwitch


def test_entity_name_before_added_is_translation_key(create_mock_coordinator) -> None:
    """Before the entity is added, exception messages name it by its translation key."""
    switch = SyrConnectBooleanSwitch(
        create_mock_coordinator({"devices": []}), "dev", "Keller", "getBUZ"
    )

    assert switch._entity_name == "getbuz"


def test_entity_name_after_added_is_translated_name(create_mock_coordinator) -> None:
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
