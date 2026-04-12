"""Tests for migration helpers in migrations.py."""
from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.syr_connect.migrations import v1_to_v2_update_kwargs
from custom_components.syr_connect.const import (
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_MODEL,
)


def test_v1_to_v2_with_host_sets_json_and_unique_id() -> None:
    """Host present should select JSON API and unique_id uses host."""
    entry = MockConfigEntry(
        version=1,
        domain="syr_connect",
        title="With Host",
        data={CONF_HOST: "192.0.2.5"},
        entry_id="with_host",
        unique_id="with_host",
    )

    result = v1_to_v2_update_kwargs(entry)

    assert result is not None
    assert result["version"] == 2
    assert result["data"][CONF_API_TYPE] == API_TYPE_JSON
    assert result["unique_id"] == f"{API_TYPE_JSON}_192.0.2.5"


def test_v1_to_v2_with_username_uses_username_for_unique_id() -> None:
    """Username present should select JSON API (when applicable) and use username for unique_id."""
    entry = MockConfigEntry(
        version=1,
        domain="syr_connect",
        title="With Username",
        data={"username": "legacy@example.com"},
        entry_id="with_username",
        unique_id="with_username",
    )

    result = v1_to_v2_update_kwargs(entry)

    assert result is not None
    assert result["version"] == 2
    # No host/model present → legacy XML API should be selected
    assert result["data"][CONF_API_TYPE] == API_TYPE_XML
    # Username-based unique_id should be used with XML API for legacy entries
    assert result["unique_id"] == f"{API_TYPE_XML}_legacy@example.com"


def test_v1_to_v2_no_migration_when_already_v2_and_api_matches() -> None:
    """Should return None when entry already has desired API and version>=2."""
    entry = MockConfigEntry(
        version=2,
        domain="syr_connect",
        title="Already Migrated",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="migrated",
        unique_id="migrated",
    )

    result = v1_to_v2_update_kwargs(entry)

    assert result is None
