"""Tests for migration helpers in migrations.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect.aiosyrconnect import (
    SyrConnectConnectionError,
    SyrConnectInvalidResponseError,
)
from custom_components.syr_connect.const import (
    _SYR_CONNECT_SERVICE_DEFAULT,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_MODEL,
    CONF_SERVICE,
)
from custom_components.syr_connect.migrations import (
    v1_to_v2_update_kwargs,
    v2_to_v3_fix_flo_unit,
    v3_to_v4_add_service,
    v4_to_v5_remove_sta_binary_sensor,
    v5_to_v6_fix_nps_unit,
    v6_to_v7_scope_unique_id_by_entry,
    v7_to_v8_rename_local_model,
    v8_to_v9_detect_local_model,
    v10_to_v11_lowercase_cloud_unique_id,
    v11_to_v12_local_unique_id_by_serial,
)
from homeassistant.const import UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant


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


async def test_v2_to_v3_resets_flo_unit_override_legacy_field(
    hass: HomeAssistant,
) -> None:
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
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity, mock_other]

        v2_to_v3_fix_flo_unit(hass, entry)

    mock_reg.async_update_entity.assert_called_once_with(
        "sensor.device_getflo", unit_of_measurement=None
    )
    mock_reg.async_update_entity_options.assert_not_called()


async def test_v2_to_v3_resets_flo_unit_override_options_field(
    hass: HomeAssistant,
) -> None:
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
    mock_entity.options = {
        "sensor": {"unit_of_measurement": UnitOfVolumeFlowRate.LITERS_PER_MINUTE}
    }

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v2_to_v3_fix_flo_unit(hass, entry)

    mock_reg.async_update_entity.assert_not_called()
    mock_reg.async_update_entity_options.assert_called_once_with(
        "sensor.device_getflo", "sensor", None
    )


async def test_v2_to_v3_resets_flo_suggested_unit_in_options(
    hass: HomeAssistant,
) -> None:
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
    mock_entity.options = {
        "sensor.private": {
            "suggested_unit_of_measurement": UnitOfVolumeFlowRate.LITERS_PER_MINUTE
        }
    }

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
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
    mock_entity.entity_id = "sensor.syr_connect_123456789_getflo"
    mock_entity.unique_id = "123456789_getFLO"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
    mock_entity.options = {
        "conversation": {"should_expose": False},
        "sensor.private": {
            "suggested_unit_of_measurement": UnitOfVolumeFlowRate.LITERS_PER_MINUTE
        },
        "sensor": {"suggested_display_precision": 1},
    }

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v2_to_v3_fix_flo_unit(hass, entry)

    # Legacy top-level field must be cleared
    mock_reg.async_update_entity.assert_called_once_with(
        "sensor.syr_connect_123456789_getflo", unit_of_measurement=None
    )
    # sensor.private namespace must be cleared (suggested_unit removed, namespace becomes None)
    mock_reg.async_update_entity_options.assert_called_once_with(
        "sensor.syr_connect_123456789_getflo", "sensor.private", None
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

    # Entity with user-customized unit (m³/h) — must not be touched
    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getflo"
    mock_entity.unique_id = "device_id_getFLO"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = "m³/h"
    mock_entity.options = {}

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
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
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
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
        data={
            CONF_API_TYPE: API_TYPE_XML,
            "username": "user@example.com",
            "password": "pw",
        },
        entry_id="legacy_xml",
        unique_id="xml_user@example.com",
    )

    result = v3_to_v4_add_service(entry)

    assert result is not None
    assert result["version"] == 4
    assert result["data"][CONF_SERVICE] == _SYR_CONNECT_SERVICE_DEFAULT
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
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [sta_entity, other_entity]

        v4_to_v5_remove_sta_binary_sensor(hass, entry)

    mock_reg.async_remove.assert_called_once_with("binary_sensor.syr_connect_123_sta")


async def test_v4_to_v5_also_removes_sensor_domain_sta_entries(
    hass: HomeAssistant,
) -> None:
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
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
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
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = []

        v4_to_v5_remove_sta_binary_sensor(hass, entry)

    mock_reg.async_remove.assert_not_called()


async def test_v5_to_v6_resets_nps_unit_override_legacy_field(
    hass: HomeAssistant,
) -> None:
    """v5_to_v6_fix_nps_unit should clear empty-string stored in legacy unit_of_measurement field."""
    entry = MockConfigEntry(
        version=5,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v5",
        unique_id="xml_user@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getnps"
    mock_entity.unique_id = "device_id_getNPS"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = ""
    mock_entity.options = {}

    mock_other = MagicMock()
    mock_other.entity_id = "sensor.device_getflo"
    mock_other.unique_id = "device_id_getFLO"
    mock_other.domain = "sensor"
    mock_other.unit_of_measurement = "L/h"
    mock_other.options = {}

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity, mock_other]

        v5_to_v6_fix_nps_unit(hass, entry)

    mock_reg.async_update_entity.assert_called_once_with(
        "sensor.device_getnps", unit_of_measurement=None
    )
    mock_reg.async_update_entity_options.assert_not_called()


async def test_v5_to_v6_resets_nps_unit_override_options_field(
    hass: HomeAssistant,
) -> None:
    """v5_to_v6_fix_nps_unit should clear empty-string stored in sensor options (modern HA path)."""
    entry = MockConfigEntry(
        version=5,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v5_opts",
        unique_id="xml_opts@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getnps"
    mock_entity.unique_id = "device_id_getNPS"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = None
    mock_entity.options = {"sensor": {"unit_of_measurement": ""}}

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v5_to_v6_fix_nps_unit(hass, entry)

    mock_reg.async_update_entity.assert_not_called()
    mock_reg.async_update_entity_options.assert_called_once_with(
        "sensor.device_getnps", "sensor", None
    )


async def test_v5_to_v6_resets_nps_suggested_unit_in_options(
    hass: HomeAssistant,
) -> None:
    """v5_to_v6_fix_nps_unit clears suggested_unit_of_measurement in sensor.private namespace."""
    entry = MockConfigEntry(
        version=5,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v5_sugg",
        unique_id="xml_sugg@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getnps"
    mock_entity.unique_id = "device_id_getNPS"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = None
    mock_entity.options = {"sensor.private": {"suggested_unit_of_measurement": ""}}

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v5_to_v6_fix_nps_unit(hass, entry)

    mock_reg.async_update_entity.assert_not_called()
    mock_reg.async_update_entity_options.assert_called_once_with(
        "sensor.device_getnps", "sensor.private", None
    )


async def test_v5_to_v6_skips_nps_with_different_unit(hass: HomeAssistant) -> None:
    """v5_to_v6_fix_nps_unit must not touch getNPS entries that don't have empty-string stored."""
    entry = MockConfigEntry(
        version=5,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v5b",
        unique_id="xml_user2@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getnps"
    mock_entity.unique_id = "device_id_getNPS"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = "min"
    mock_entity.options = {}

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v5_to_v6_fix_nps_unit(hass, entry)

    mock_reg.async_update_entity.assert_not_called()
    mock_reg.async_update_entity_options.assert_not_called()


async def test_v5_to_v6_skips_nps_with_no_unit_stored(hass: HomeAssistant) -> None:
    """v5_to_v6_fix_nps_unit must not touch getNPS entries with no unit override."""
    entry = MockConfigEntry(
        version=5,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v5c",
        unique_id="xml_user3@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getnps"
    mock_entity.unique_id = "device_id_getNPS"
    mock_entity.domain = "sensor"
    mock_entity.unit_of_measurement = None
    mock_entity.options = {}

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v5_to_v6_fix_nps_unit(hass, entry)

    mock_reg.async_update_entity.assert_not_called()
    mock_reg.async_update_entity_options.assert_not_called()


async def test_v5_to_v6_no_entries(hass: HomeAssistant) -> None:
    """v5_to_v6_fix_nps_unit handles an empty entity registry gracefully."""
    entry = MockConfigEntry(
        version=5,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v5d",
        unique_id="xml_v5d@example.com",
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = []

        v5_to_v6_fix_nps_unit(hass, entry)

    mock_reg.async_update_entity.assert_not_called()
    mock_reg.async_update_entity_options.assert_not_called()


async def test_v6_to_v7_prefixes_unique_id_with_entry_id(hass: HomeAssistant) -> None:
    """v6_to_v7_scope_unique_id_by_entry prepends entry_id to existing unique_ids."""
    entry = MockConfigEntry(
        version=6,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v6",
        unique_id="xml_v6@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getbar"
    mock_entity.unique_id = "device1_getBAR"

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v6_to_v7_scope_unique_id_by_entry(hass, entry)

    mock_reg.async_update_entity.assert_called_once_with(
        "sensor.device_getbar", new_unique_id="entry_v6_device1_getBAR"
    )


async def test_v6_to_v7_skips_already_prefixed_unique_id(hass: HomeAssistant) -> None:
    """v6_to_v7_scope_unique_id_by_entry is idempotent; already-prefixed entries are untouched."""
    entry = MockConfigEntry(
        version=6,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v6b",
        unique_id="xml_v6b@example.com",
    )
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_entity.entity_id = "sensor.device_getbar"
    mock_entity.unique_id = "entry_v6b_device1_getBAR"

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = [mock_entity]

        v6_to_v7_scope_unique_id_by_entry(hass, entry)

    mock_reg.async_update_entity.assert_not_called()


async def test_v6_to_v7_no_entries(hass: HomeAssistant) -> None:
    """v6_to_v7_scope_unique_id_by_entry handles an empty entity registry gracefully."""
    entry = MockConfigEntry(
        version=6,
        domain="syr_connect",
        title="Device",
        data={CONF_API_TYPE: API_TYPE_XML},
        entry_id="entry_v6c",
        unique_id="xml_v6c@example.com",
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.syr_connect.migrations.er.async_get") as mock_er_get,
        patch(
            "custom_components.syr_connect.migrations.er.async_entries_for_config_entry"
        ) as mock_entries,
    ):
        mock_reg = MagicMock()
        mock_er_get.return_value = mock_reg
        mock_entries.return_value = []

        v6_to_v7_scope_unique_id_by_entry(hass, entry)

    mock_reg.async_update_entity.assert_not_called()


def test_v7_to_v8_renames_local_model() -> None:
    """A renamed local model gets its new name."""
    entry = MockConfigEntry(
        domain="syr_connect",
        version=7,
        data={
            CONF_API_TYPE: API_TYPE_JSON,
            CONF_HOST: "10.0.0.2",
            CONF_MODEL: "optimat22duo",
        },
    )

    assert v7_to_v8_rename_local_model(entry) == {
        "data": {
            CONF_API_TYPE: API_TYPE_JSON,
            CONF_HOST: "10.0.0.2",
            CONF_MODEL: "optimat2duo",
        },
        "version": 8,
    }


def test_v7_to_v8_renames_generic_neosoft_to_neosoft5000() -> None:
    """The generic NeoSoft model (dk=1200) is the NeoSoft 5000."""
    entry = MockConfigEntry(
        domain="syr_connect",
        version=7,
        data={
            CONF_API_TYPE: API_TYPE_JSON,
            CONF_HOST: "10.0.0.2",
            CONF_MODEL: "neosoft",
        },
    )

    update = v7_to_v8_rename_local_model(entry)

    assert update is not None
    assert update["data"][CONF_MODEL] == "neosoft5000"


def test_v7_to_v8_keeps_other_local_models_and_cloud_entries() -> None:
    """A current or removed local model and a cloud entry need no rename."""
    for data in (
        {CONF_API_TYPE: API_TYPE_JSON, CONF_HOST: "10.0.0.2", CONF_MODEL: "trio"},
        {CONF_API_TYPE: API_TYPE_JSON, CONF_HOST: "10.0.0.2", CONF_MODEL: "syrmuco"},
        {CONF_API_TYPE: API_TYPE_XML, CONF_MODEL: "optimat22duo"},
    ):
        entry = MockConfigEntry(domain="syr_connect", version=7, data=data)
        assert v7_to_v8_rename_local_model(entry) is None


def _mock_local_device(api_class: MagicMock, status: dict) -> None:
    """Let the patched local JSON API client report one device with this status."""
    api = api_class.return_value
    api.get_devices = AsyncMock(return_value=[{"id": "506AAA12345"}])
    api.get_device_status = AsyncMock(return_value=status)


async def test_v8_to_v9_detects_removed_multicontroller_from_device(
    hass: HomeAssistant,
) -> None:
    """A removed generic MultiController gets the role the device reports (getDFM)."""
    entry = MockConfigEntry(
        domain="syr_connect",
        version=8,
        data={
            CONF_API_TYPE: API_TYPE_JSON,
            CONF_HOST: "10.0.0.2",
            CONF_MODEL: "syrmuco",
        },
    )

    with patch("custom_components.syr_connect.migrations.SyrConnectJsonAPI") as api:
        _mock_local_device(api, {"getSRN": "506AAA12345", "getDFM": 5})
        update = await v8_to_v9_detect_local_model(hass, entry)

    assert api.call_args.kwargs["host"] == "10.0.0.2"
    assert api.call_args.kwargs["base_path"] == "/trio"
    assert update is not None
    assert update["data"][CONF_MODEL] == "syrtriolockconnect"
    assert update["version"] == 9


async def test_v8_to_v9_unknown_multicontroller_role_raises(
    hass: HomeAssistant,
) -> None:
    """A device whose model cannot be detected fails the migration."""
    entry = MockConfigEntry(
        domain="syr_connect",
        version=8,
        data={
            CONF_API_TYPE: API_TYPE_JSON,
            CONF_HOST: "10.0.0.2",
            CONF_MODEL: "syrmuco",
        },
    )

    with patch("custom_components.syr_connect.migrations.SyrConnectJsonAPI") as api:
        _mock_local_device(api, {"getSRN": "506AAA12345", "getDFM": 9})
        with pytest.raises(SyrConnectInvalidResponseError):
            await v8_to_v9_detect_local_model(hass, entry)


async def test_v8_to_v9_unreachable_device_raises(hass: HomeAssistant) -> None:
    """An unreachable device fails the migration with a connection error."""
    entry = MockConfigEntry(
        domain="syr_connect",
        version=8,
        data={
            CONF_API_TYPE: API_TYPE_JSON,
            CONF_HOST: "10.0.0.2",
            CONF_MODEL: "takemuco",
        },
    )

    with patch("custom_components.syr_connect.migrations.SyrConnectJsonAPI") as api:
        api.return_value.get_devices = AsyncMock(
            side_effect=SyrConnectConnectionError("timeout")
        )
        with pytest.raises(SyrConnectConnectionError):
            await v8_to_v9_detect_local_model(hass, entry)


async def test_v8_to_v9_keeps_current_local_model_and_cloud_entries(
    hass: HomeAssistant,
) -> None:
    """A current local model and a cloud entry need no update."""
    local = MockConfigEntry(
        domain="syr_connect",
        version=8,
        data={CONF_API_TYPE: API_TYPE_JSON, CONF_HOST: "10.0.0.2", CONF_MODEL: "trio"},
    )
    cloud = MockConfigEntry(
        domain="syr_connect",
        version=8,
        data={CONF_API_TYPE: API_TYPE_XML, CONF_MODEL: "syrmuco"},
    )

    assert await v8_to_v9_detect_local_model(hass, local) is None
    assert await v8_to_v9_detect_local_model(hass, cloud) is None


def _cloud_entry(
    hass: HomeAssistant, username: str, unique_id: str, entry_id: str
) -> MockConfigEntry:
    """Return a cloud entry of the SYR Connect service, added to hass."""
    entry = MockConfigEntry(
        version=10,
        domain="syr_connect",
        title=f"SYR Connect ({username})",
        data={
            CONF_API_TYPE: API_TYPE_XML,
            CONF_SERVICE: "de.consoft.syr.connect",
            "username": username,
        },
        entry_id=entry_id,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize("username", ["Me@Example.com", " Me@Example.com "])
async def test_v10_to_v11_lowercases_username_in_unique_id(
    hass: HomeAssistant, username: str
) -> None:
    """The unique_id of a cloud entry gets the username in lowercase, without whitespace."""
    entry = _cloud_entry(
        hass, username, f"xml_de.consoft.syr.connect_{username}", "CLOUD"
    )

    assert v10_to_v11_lowercase_cloud_unique_id(hass, entry) == {
        "unique_id": "xml_de.consoft.syr.connect_me@example.com",
        "version": 11,
    }


async def test_v10_to_v11_keeps_lowercase_and_local_unique_id(
    hass: HomeAssistant,
) -> None:
    """A lowercase cloud unique_id and a local entry need no update."""
    cloud = _cloud_entry(
        hass, "me@example.com", "xml_de.consoft.syr.connect_me@example.com", "CLOUD"
    )
    local = MockConfigEntry(
        version=10,
        domain="syr_connect",
        data={CONF_API_TYPE: API_TYPE_JSON, CONF_HOST: "192.0.2.5"},
        unique_id="json_SN1",
    )
    local.add_to_hass(hass)

    assert v10_to_v11_lowercase_cloud_unique_id(hass, cloud) is None
    assert v10_to_v11_lowercase_cloud_unique_id(hass, local) is None


async def test_v10_to_v11_keeps_unique_id_of_account_set_up_twice(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """If another entry has the account, the entry keeps its unique_id and it is logged."""
    _cloud_entry(
        hass, "me@example.com", "xml_de.consoft.syr.connect_me@example.com", "OTHER"
    )
    entry = _cloud_entry(
        hass, "Me@Example.com", "xml_de.consoft.syr.connect_Me@Example.com", "CLOUD"
    )

    assert v10_to_v11_lowercase_cloud_unique_id(hass, entry) is None
    assert "The account of SYR Connect (Me@Example.com)" in caplog.text


def _local_entry(hass: HomeAssistant, unique_id: str, entry_id: str) -> MockConfigEntry:
    """Return a local SafeTech V4 entry at 192.0.2.5, added to hass."""
    entry = MockConfigEntry(
        version=11,
        domain="syr_connect",
        title="SYR Connect Local (192.0.2.5)",
        data={
            CONF_API_TYPE: API_TYPE_JSON,
            CONF_HOST: "192.0.2.5",
            CONF_MODEL: "safetechv4",
        },
        entry_id=entry_id,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize("key", ["getSRN", "getFRN"])
async def test_v11_to_v12_gives_local_entry_serial_unique_id(
    hass: HomeAssistant, key: str
) -> None:
    """A local entry gets the serial number of its device as unique_id."""
    entry = _local_entry(hass, "json_192.0.2.5", "LOCAL")

    with patch("custom_components.syr_connect.migrations.SyrConnectJsonAPI") as api:
        _mock_local_device(api, {key: "SN1"})
        update = await v11_to_v12_local_unique_id_by_serial(hass, entry)

    assert api.call_args.kwargs["host"] == "192.0.2.5"
    assert api.call_args.kwargs["base_path"] == "/safe-tec"
    assert update == {"unique_id": "json_SN1", "version": 12}


async def test_v11_to_v12_keeps_serial_unique_id_and_cloud_entries(
    hass: HomeAssistant,
) -> None:
    """A local entry that has the serial number and a cloud entry need no update."""
    local = _local_entry(hass, "json_SN1", "LOCAL")
    cloud = _cloud_entry(
        hass, "me@example.com", "xml_de.consoft.syr.connect_me@example.com", "CLOUD"
    )

    with patch("custom_components.syr_connect.migrations.SyrConnectJsonAPI") as api:
        _mock_local_device(api, {"getSRN": "SN1"})
        assert await v11_to_v12_local_unique_id_by_serial(hass, local) is None
        assert await v11_to_v12_local_unique_id_by_serial(hass, cloud) is None

    # Only the local device is asked
    api.assert_called_once()


async def test_v11_to_v12_keeps_unique_id_of_device_set_up_twice(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """If another entry has the device, the entry keeps its unique_id and it is logged."""
    _local_entry(hass, "json_SN1", "OTHER")
    entry = _local_entry(hass, "json_192.0.2.5", "LOCAL")

    with patch("custom_components.syr_connect.migrations.SyrConnectJsonAPI") as api:
        _mock_local_device(api, {"getSRN": "SN1"})
        assert await v11_to_v12_local_unique_id_by_serial(hass, entry) is None

    assert "The device SN1 of SYR Connect Local (192.0.2.5)" in caplog.text


@pytest.mark.parametrize(
    "status",
    [
        {},
        {"getSRN": ""},
    ],
    ids=["empty_status", "empty_serial"],
)
async def test_v11_to_v12_device_without_serial_raises(
    hass: HomeAssistant, status: dict
) -> None:
    """A device that reports no serial number fails the migration."""
    entry = _local_entry(hass, "json_192.0.2.5", "LOCAL")

    with patch("custom_components.syr_connect.migrations.SyrConnectJsonAPI") as api:
        _mock_local_device(api, status)
        with pytest.raises(SyrConnectInvalidResponseError):
            await v11_to_v12_local_unique_id_by_serial(hass, entry)


async def test_v11_to_v12_unreachable_device_raises(hass: HomeAssistant) -> None:
    """An unreachable device fails the migration with a connection error."""
    entry = _local_entry(hass, "json_192.0.2.5", "LOCAL")

    with patch("custom_components.syr_connect.migrations.SyrConnectJsonAPI") as api:
        api.return_value.get_devices = AsyncMock(
            side_effect=SyrConnectConnectionError("timeout")
        )
        with pytest.raises(SyrConnectConnectionError):
            await v11_to_v12_local_unique_id_by_serial(hass, entry)
