"""Tests for migration helpers in migrations.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.const import UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.syr_connect.const import (
    _SYR_CONNECT_DEFAULT_CF_BUNDLE_IDENTIFIER,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_SERVICE,
)
from custom_components.syr_connect.migrations import (
    v1_to_v2_update_kwargs,
    v2_to_v3_fix_flo_unit,
    v3_to_v4_add_service,
    v4_to_v5_remove_sta_binary_sensor,
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


async def test_v2_to_v3_resets_flo_unit_override_legacy_field(hass: HomeAssistant) -> None:
    """v2_to_v3_fix_flo_unit should clear L/min stored in legacy unit_of_measurement field."""
    entry = MockConfigEntry(
        version=2,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v2",
        unique_id="xml_user@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getflo"
    mock_entity.unique_id = "device_id_getFLO"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
    mock_entity.options = {}  # No options stored

    # An unrelated entity that should NOT be touched
    mock_other = MagicMock()
    mock_other.entity_id = "sensor.device_gettmp"
    mock_other.unique_id = "device_id_getTMP"
    mock_other.domain = "sensor"
    mock_other.unit_of_measurement = "°C"
    mock_other.options = {}

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch("custom_components.syr_connect.migrations.er.async_entries_for_config_entry") as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity, mock_other]

        v2_to_v3_fix_flo_unit(hass, entry)

    mock_reg.async_update_entity.assert_called_once_with(
        "sensor.device_getflo", unit_of_measurement=None
    )
    mock_reg.async_update_entity_options.assert_not_called()


async def test_v2_to_v3_resets_flo_unit_override_options_field(hass: HomeAssistant) -> None:
    """v2_to_v3_fix_flo_unit should clear L/min stored in sensor options (modern HA path)."""
    entry = MockConfigEntry(
        version=2,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v2_opts",
        unique_id="xml_opts@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getflo"
    mock_entity.unique_id = "device_id_getFLO"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = None  # Legacy field NOT set
    mock_entity.options = {"sensor": {"unit_of_measurement": UnitOfVolumeFlowRate.LITERS_PER_MINUTE}}

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch("custom_components.syr_connect.migrations.er.async_entries_for_config_entry") as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v2_to_v3_fix_flo_unit(hass, entry)

    mock_reg.async_update_entity.assert_not_called()
    mock_reg.async_update_entity_options.assert_called_once_with(
        "sensor.device_getflo", "sensor", None
    )


async def test_v2_to_v3_resets_flo_suggested_unit_in_options(hass: HomeAssistant) -> None:
    """v2_to_v3_fix_flo_unit clears suggested_unit_of_measurement in sensor.private namespace."""
    entry = MockConfigEntry(
        version=2,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v2_sugg",
        unique_id="xml_sugg@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getflo"
    mock_entity.unique_id = "device_id_getFLO"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = None
    mock_entity.options = {"sensor.private": {"suggested_unit_of_measurement": UnitOfVolumeFlowRate.LITERS_PER_MINUTE}}

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch("custom_components.syr_connect.migrations.er.async_entries_for_config_entry") as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v2_to_v3_fix_flo_unit(hass, entry)

    mock_reg.async_update_entity.assert_not_called()
    mock_reg.async_update_entity_options.assert_called_once_with(
        "sensor.device_getflo", "sensor.private", None
    )


async def test_v2_to_v3_real_world_snapshot(hass: HomeAssistant) -> None:
    """v2_to_v3_fix_flo_unit handles the real-world entity registry snapshot.

    Replicates the exact structure observed in core.entity_registry:
    unit_of_measurement = 'L/min'  (top-level legacy field)
    options['sensor.private']['suggested_unit_of_measurement'] = 'L/min'
    options['sensor']['suggested_display_precision'] = 1  (must be preserved)
    """
    entry = MockConfigEntry(
        version=2,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v2_real",
        unique_id="xml_real@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.syr_connect_213240945_getflo"
    mock_entity.unique_id = "213240945_getFLO"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
    mock_entity.options = {
        "conversation": {"should_expose": False},
        "sensor.private": {"suggested_unit_of_measurement": UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
        "sensor": {"suggested_display_precision": 1},
    }

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch("custom_components.syr_connect.migrations.er.async_entries_for_config_entry") as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v2_to_v3_fix_flo_unit(hass, entry)

    # Legacy top-level field must be cleared
    mock_reg.async_update_entity.assert_called_once_with(
        "sensor.syr_connect_213240945_getflo", unit_of_measurement=None
    )
    # sensor.private namespace must be cleared (suggested_unit removed, namespace becomes None)
    mock_reg.async_update_entity_options.assert_called_once_with(
        "sensor.syr_connect_213240945_getflo", "sensor.private", None
    )


async def test_v2_to_v3_skips_flo_with_different_unit(hass: HomeAssistant) -> None:
    """v2_to_v3_fix_flo_unit must not touch getFLO entries that don't have L/min stored."""
    entry = MockConfigEntry(
        version=2,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v2b",
        unique_id="xml_user2@example.com",
    )
    entry.add_to_hass(hass)

    # Entity with user-customised unit (m³/h) — must not be touched
    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getflo"
    mock_entity.unique_id = "device_id_getFLO"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = "m³/h"
    mock_entity.options = {}

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch("custom_components.syr_connect.migrations.er.async_entries_for_config_entry") as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v2_to_v3_fix_flo_unit(hass, entry)

    mock_reg.async_update_entity.assert_not_called()
    mock_reg.async_update_entity_options.assert_not_called()


async def test_v2_to_v3_skips_flo_with_no_unit_stored(hass: HomeAssistant) -> None:
    """v2_to_v3_fix_flo_unit must not touch getFLO entries with no unit override."""
    entry = MockConfigEntry(
        version=2,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v2c",
        unique_id="xml_user3@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getflo"
    mock_entity.unique_id = "device_id_getFLO"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = None
    mock_entity.options = {}

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch("custom_components.syr_connect.migrations.er.async_entries_for_config_entry") as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v2_to_v3_fix_flo_unit(hass, entry)

    mock_reg.async_update_entity.assert_not_called()
    mock_reg.async_update_entity_options.assert_not_called()


def test_v3_to_v4_adds_default_service_to_xml_entry() -> None:
    """XML entries without CONF_SERVICE should get the default SYR Connect service."""
    entry = MockConfigEntry(
        version=3,
        domain="syr_connect",
        title="Legacy",
        data={CONF_API_TYPE: API_TYPE_XML, "username": "user@example.com", "password": "pw"},
        entry_id="legacy_xml",
        unique_id="xml_user@example.com",
    )

    result = v3_to_v4_add_service(entry)

    assert result is not None
    assert result["version"] == 4
    assert result["data"][CONF_SERVICE] == _SYR_CONNECT_DEFAULT_CF_BUNDLE_IDENTIFIER
    assert result["data"]["username"] == "user@example.com"


def test_v3_to_v4_skips_xml_entry_with_service_already_set() -> None:
    """XML entries that already have CONF_SERVICE set should not be changed."""
    entry = MockConfigEntry(
        version=3,
        domain="syr_connect",
        title="Already set",
        data={CONF_API_TYPE: API_TYPE_XML, CONF_SERVICE: "de.consoft.rwc.connect"},
        entry_id="xml_with_service",
        unique_id="xml_rwc",
    )

    result = v3_to_v4_add_service(entry)

    assert result is None


def test_v3_to_v4_skips_json_entry() -> None:
    """JSON API entries do not use CONF_SERVICE and must not be touched."""
    entry = MockConfigEntry(
        version=3,
        domain="syr_connect",
        title="JSON",
        data={CONF_API_TYPE: API_TYPE_JSON, CONF_HOST: "192.0.2.1"},
        entry_id="json_entry",
        unique_id="json_192.0.2.1",
    )

    result = v3_to_v4_add_service(entry)

    assert result is None


async def test_v4_to_v5_removes_sta_binary_sensor(hass: HomeAssistant) -> None:
    """v4_to_v5 removes any entry whose unique_id ends with '_sta' (any domain)."""
    entry = MockConfigEntry(
        version=4,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v4",
        unique_id="xml_v4@example.com",
    )
    entry.add_to_hass(hass)

    sta_entity = MagicMock()
    sta_entity.entity_id = "binary_sensor.syr_connect_123_sta"
    sta_entity.unique_id = "123_sta"
    sta_entity.domain = "binary_sensor"

    other_entity = MagicMock()
    other_entity.entity_id = "binary_sensor.syr_connect_123_getbuz"
    other_entity.unique_id = "123_getBUZ"
    other_entity.domain = "binary_sensor"

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch("custom_components.syr_connect.migrations.er.async_entries_for_config_entry") as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [sta_entity, other_entity]

        v4_to_v5_remove_sta_binary_sensor(hass, entry)

    mock_reg.async_remove.assert_called_once_with("binary_sensor.syr_connect_123_sta")


async def test_v4_to_v5_also_removes_sensor_domain_sta_entries(hass: HomeAssistant) -> None:
    """v4_to_v5 also removes sensor.* entries with unique_id ending '_sta' (field renamed to dst)."""
    entry = MockConfigEntry(
        version=4,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v4b",
        unique_id="xml_v4b@example.com",
    )
    entry.add_to_hass(hass)

    sensor_sta = MagicMock()
    sensor_sta.entity_id = "sensor.syr_connect_123_sta"
    sensor_sta.unique_id = "123_sta"
    sensor_sta.domain = "sensor"

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch("custom_components.syr_connect.migrations.er.async_entries_for_config_entry") as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [sensor_sta]

        v4_to_v5_remove_sta_binary_sensor(hass, entry)

    mock_reg.async_remove.assert_called_once_with("sensor.syr_connect_123_sta")


async def test_v4_to_v5_no_entries(hass: HomeAssistant) -> None:
    """v4_to_v5 handles an empty entity registry gracefully."""
    entry = MockConfigEntry(
        version=4,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v4c",
        unique_id="xml_v4c@example.com",
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch("custom_components.syr_connect.migrations.er.async_entries_for_config_entry") as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = []

        v4_to_v5_remove_sta_binary_sensor(hass, entry)

    mock_reg.async_remove.assert_not_called()
