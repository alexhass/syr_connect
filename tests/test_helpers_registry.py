"""Tests for the registry helpers (helpers/registry.py)."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect import sensor
from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.helpers.registry import (
    _entity_key,
    build_entity_id,
    build_statistic_id,
    build_unique_id,
    cleanup_removed_devices,
    clear_device_statistics,
    delete_issue,
    registry_cleanup,
)
from custom_components.syr_connect.sensor import _SYR_CONNECT_SENSOR_SUPPORTED_KEYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


def test_registry_cleanup_handles_exception() -> None:
    """A failing entity registry does not stop the caller."""
    hass = MagicMock()
    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        side_effect=RuntimeError("boom"),
    ) as mock_registry:
        registry_cleanup(
            hass,
            cast(Any, {"devices": [{"id": "DEV"}]}),
            "sensor",
            allowed_keys={"getPRS"},
            entry_id="entry",
        )

    mock_registry.assert_called_once_with(hass)


def test_cleanup_removed_devices_removes_stale_device() -> None:
    """A registry device whose id no longer appears in coordinator data is removed."""
    hass = MagicMock()
    device_registry = MagicMock()
    stale_entry = SimpleNamespace(
        id="registry_entry_id", identifiers={(DOMAIN, "STALE_DEV")}
    )

    with (
        patch(
            "custom_components.syr_connect.helpers.registry.dr.async_get",
            return_value=device_registry,
        ),
        patch(
            "custom_components.syr_connect.helpers.registry.dr.async_entries_for_config_entry",
            return_value=[stale_entry],
        ),
    ):
        cleanup_removed_devices(
            hass, cast(Any, {"devices": [{"id": "CURRENT_DEV"}]}), "entry1"
        )

    device_registry.async_remove_device.assert_called_once_with("registry_entry_id")


async def test_cleanup_removed_devices_keeps_device_of_other_entry(
    hass: HomeAssistant,
) -> None:
    """Only the device of this entry is removed, the same serial of another entry stays."""
    entry = MockConfigEntry(domain=DOMAIN, entry_id="01JENTRYA")
    other = MockConfigEntry(domain=DOMAIN, entry_id="01JENTRYB")
    entry.add_to_hass(hass)
    other.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    for config_entry in (entry, other):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, "STALE_DEV")},
        )

    cleanup_removed_devices(
        hass, cast(Any, {"devices": [{"id": "CURRENT_DEV"}]}), entry.entry_id
    )

    assert not dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert dr.async_entries_for_config_entry(device_registry, other.entry_id)


def test_cleanup_removed_devices_clears_statistics_of_removed_device() -> None:
    """A removed device loses its history (unless another entry has it)."""
    hass = MagicMock()
    device_registry = MagicMock()
    stale_entry = SimpleNamespace(
        id="registry_entry_id", identifiers={(DOMAIN, "STALE_DEV")}
    )

    with (
        patch(
            "custom_components.syr_connect.helpers.registry.dr.async_get",
            return_value=device_registry,
        ),
        patch(
            "custom_components.syr_connect.helpers.registry.dr.async_entries_for_config_entry",
            return_value=[stale_entry],
        ),
        patch(
            "custom_components.syr_connect.helpers.registry.clear_device_statistics"
        ) as mock_clear,
    ):
        cleanup_removed_devices(
            hass, cast(Any, {"devices": [{"id": "CURRENT_DEV"}]}), "entry1"
        )

    mock_clear.assert_called_once_with(hass, "entry1", {"STALE_DEV"})


def test_build_statistic_id() -> None:
    """The ID is an external statistic ID: domain, colon, slugs only."""
    assert (
        build_statistic_id("200AAA-12345", "getCEL")
        == "syr_connect:200aaa_12345_getcel_history"
    )


async def test_clear_device_statistics_clears_every_series_key(
    hass: HomeAssistant,
) -> None:
    """Every series key of every profile is cleared, except for devices of other entries."""
    hass.config.components.add("recorder")
    entry = MockConfigEntry(domain=DOMAIN, entry_id="01JENTRYA")
    other = MockConfigEntry(domain=DOMAIN, entry_id="01JENTRYB")
    entry.add_to_hass(hass)
    other.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={(DOMAIN, "SHARED_DEV")}
    )

    with patch(
        "custom_components.syr_connect.helpers.registry.get_instance"
    ) as mock_get_instance:
        clear_device_statistics(hass, entry.entry_id, {"123456789", "SHARED_DEV"})

    mock_get_instance.return_value.async_clear_statistics.assert_called_once_with(
        [
            "syr_connect:123456789_getcel_history",
            "syr_connect:123456789_gethmd_history",
        ]
    )


@pytest.mark.parametrize(
    ("recorder", "device_ids"),
    [
        (False, {"123456789"}),
        (True, set()),
        (True, {"SHARED_DEV"}),
    ],
)
async def test_clear_device_statistics_skipped(
    hass: HomeAssistant, recorder: bool, device_ids: set[str]
) -> None:
    """Without the recorder, devices, or with a device another entry has, nothing is cleared."""
    if recorder:
        hass.config.components.add("recorder")
    other = MockConfigEntry(domain=DOMAIN, entry_id="01JENTRYB")
    other.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={(DOMAIN, "SHARED_DEV")}
    )

    with patch(
        "custom_components.syr_connect.helpers.registry.get_instance"
    ) as mock_get_instance:
        clear_device_statistics(hass, "01JENTRYA", device_ids)

    mock_get_instance.assert_not_called()


async def test_clear_device_statistics_without_series(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without any profile with series there is nothing to clear."""
    hass.config.components.add("recorder")
    monkeypatch.setattr("custom_components.syr_connect.helpers.registry.MODELS", [])

    with patch(
        "custom_components.syr_connect.helpers.registry.get_instance"
    ) as mock_get_instance:
        clear_device_statistics(hass, "01JENTRYA", {"123456789"})

    mock_get_instance.assert_not_called()


def test_cleanup_removed_devices_keeps_current_device() -> None:
    """A registry device still present in coordinator data must not be removed."""
    hass = MagicMock()
    device_registry = MagicMock()
    current_entry = SimpleNamespace(
        id="registry_entry_id", identifiers={(DOMAIN, "CURRENT_DEV")}
    )

    with (
        patch(
            "custom_components.syr_connect.helpers.registry.dr.async_get",
            return_value=device_registry,
        ),
        patch(
            "custom_components.syr_connect.helpers.registry.dr.async_entries_for_config_entry",
            return_value=[current_entry],
        ),
    ):
        cleanup_removed_devices(
            hass, cast(Any, {"devices": [{"id": "CURRENT_DEV"}]}), "entry1"
        )

    device_registry.async_remove_device.assert_not_called()


def test_cleanup_removed_devices_handles_exception() -> None:
    """Any error while scanning/removing devices must not propagate."""
    hass = MagicMock()
    with patch(
        "custom_components.syr_connect.helpers.registry.dr.async_get",
        side_effect=RuntimeError("boom"),
    ) as mock_registry:
        cleanup_removed_devices(hass, cast(Any, {"devices": []}), "entry1")

    mock_registry.assert_called_once_with(hass)


def test_build_entity_id() -> None:
    """Test entity ID building."""
    entity_id = build_entity_id("sensor", "DEVICE123", "getPRS")

    assert entity_id == "sensor.syr_connect_device123_getprs"


def _set_registry_entries(registry: MagicMock, entries: list) -> None:
    """Let the registry mock return the given entries, looked up by config entry."""
    registry.entities.get_entries_for_config_entry_id.side_effect = lambda entry_id: [
        entry for entry in entries if entry.config_entry_id == entry_id
    ]


def _registry_entry(
    domain: str,
    device_id: str,
    key: str,
    config_entry_id: str | None = None,
    entity_id: str | None = None,
) -> SimpleNamespace:
    """Return an entity registry entry as created by this integration (entity_id defaults to the standard one)."""
    return SimpleNamespace(
        entity_id=entity_id or build_entity_id(domain, device_id, key),
        unique_id=build_unique_id(config_entry_id, device_id, key),
        platform=DOMAIN,
        domain=domain,
        config_entry_id=config_entry_id,
    )


def test_registry_cleanup_removes_existing_getcno_sensor() -> None:
    """The getCNO (registration code on the device label) is no longer a supported key: an existing sensor is removed."""

    registry = MagicMock()
    registry.async_get = MagicMock(return_value=None)
    stale = _registry_entry("sensor", "DEV", "getCNO", config_entry_id="entry")
    _set_registry_entries(
        registry,
        [
            stale,
            _registry_entry("sensor", "DEV", "getSRN", config_entry_id="entry"),
        ],
    )

    # SafeFloor has its own per-model allowlist, which listed getCNO before
    status = {
        "getVER": "Syr Floorsensor 2.23",
        "getSRN": "123",
        "getCNO": "XXXXXXXXXXXXXXXX",
    }
    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        registry_cleanup(
            MagicMock(),
            cast(Any, {"devices": [{"id": "DEV", "status": status}]}),
            "sensor",
            allowed_keys=_SYR_CONNECT_SENSOR_SUPPORTED_KEYS,
            entry_id="entry",
        )

    registry.async_remove.assert_called_once_with(stale.entity_id)


def test_registry_cleanup_remove_called() -> None:
    """Allowlist mode: entity with key NOT in allowed_keys is removed."""
    hass = MagicMock()
    registry = MagicMock()
    device_id = "DEV"
    unlisted_entity_id = build_entity_id("sensor", device_id, "getFOO")
    _set_registry_entries(
        registry,
        [
            _registry_entry("sensor", device_id, "getFOO", config_entry_id="entry"),
            _registry_entry("sensor", device_id, "getPRS", config_entry_id="entry"),
            # Another device of the same entry: not part of this device's cleanup
            _registry_entry("sensor", "OTHER", "getFOO", config_entry_id="entry"),
        ],
    )
    registry.async_remove = MagicMock()
    # No conditional entities exist in the registry for this test.
    registry.async_get = MagicMock(return_value=None)

    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        coordinator = {"devices": [{"id": device_id, "status": {"getPRS": "3"}}]}
        registry_cleanup(
            hass,
            cast(Any, coordinator),
            "sensor",
            allowed_keys={"getPRS"},
            entry_id="entry",
        )

    registry.async_remove.assert_called_once_with(unlisted_entity_id)


def test_registry_cleanup_without_entry_id_removes_nothing() -> None:
    """Without the owning config entry the entities cannot be scoped: nothing is removed."""
    registry = MagicMock()
    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        coordinator = {"devices": [{"id": "DEV", "status": {"getPRS": "3"}}]}
        registry_cleanup(
            MagicMock(),
            cast(Any, coordinator),
            "sensor",
            allowed_keys=set(),
            entry_id=None,
        )

    registry.async_remove.assert_not_called()


def test_registry_cleanup_skips_device_with_empty_status() -> None:
    """Without a status (not fetched yet, e.g. temporary failure at startup) nothing is removed."""
    hass = MagicMock()
    registry = MagicMock()
    device_id = "DEV"
    _set_registry_entries(
        registry,
        [
            _registry_entry("sensor", device_id, "getFOO", config_entry_id="entry"),
        ],
    )
    registry.async_remove = MagicMock()
    # A conditionally hidden sensor that would be removed if the empty status were trusted
    registry.async_get = MagicMock(return_value=SimpleNamespace(config_entry_id=None))

    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        coordinator = {"devices": [{"id": device_id, "status": {}}]}
        registry_cleanup(
            hass,
            cast(Any, coordinator),
            "sensor",
            allowed_keys={"getPRS"},
            entry_id="entry",
        )

    registry.async_remove.assert_not_called()


def test_registry_cleanup_entry_id_scoping_ignores_other_hub() -> None:
    """Entities owned by a DIFFERENT config entry must not be touched (cross-hub safety).

    Regression test: without entry_id scoping, one hub's cleanup pass could
    delete another hub's entities for the same device_id (e.g. the same
    physical device reachable from two SYR Connect accounts).
    """
    hass = MagicMock()
    registry = MagicMock()
    device_id = "DEV"
    _set_registry_entries(
        registry,
        [
            _registry_entry("sensor", device_id, "getFOO", config_entry_id="other_hub"),
        ],
    )
    registry.async_remove = MagicMock()
    registry.async_get = MagicMock(return_value=None)

    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        coordinator = {"devices": [{"id": device_id, "status": {"getPRS": "3"}}]}
        registry_cleanup(
            hass,
            cast(Any, coordinator),
            "sensor",
            allowed_keys={"getPRS"},
            entry_id="this_hub",
        )

    registry.async_remove.assert_not_called()


def test_registry_cleanup_entry_id_scoping_removes_own_hub() -> None:
    """Entities owned by the MATCHING config entry are still cleaned up normally."""
    hass = MagicMock()
    registry = MagicMock()
    device_id = "DEV"
    unlisted_entity_id = build_entity_id("sensor", device_id, "getFOO")
    _set_registry_entries(
        registry,
        [
            _registry_entry("sensor", device_id, "getFOO", config_entry_id="this_hub"),
        ],
    )
    registry.async_remove = MagicMock()
    registry.async_get = MagicMock(return_value=None)

    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        coordinator = {"devices": [{"id": device_id, "status": {"getPRS": "3"}}]}
        registry_cleanup(
            hass,
            cast(Any, coordinator),
            "sensor",
            allowed_keys={"getPRS"},
            entry_id="this_hub",
        )

    registry.async_remove.assert_called_once_with(unlisted_entity_id)


def test_registry_cleanup_remove_raises_does_not_propagate() -> None:
    """If registry.async_remove raises, cleanup should not propagate the exception."""
    hass = MagicMock()
    registry = MagicMock()
    device_id = "DEV2"
    unlisted_entity_id = build_entity_id("sensor", device_id, "getFOO")
    _set_registry_entries(
        registry, [_registry_entry("sensor", device_id, "getFOO", config_entry_id="e")]
    )
    registry.async_get = MagicMock(return_value=None)
    registry.async_remove.side_effect = RuntimeError("boom")

    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        coordinator = {"devices": [{"id": device_id, "status": {"getPRS": "3"}}]}
        # Should not raise despite async_remove throwing
        registry_cleanup(
            hass, cast(Any, coordinator), "sensor", allowed_keys=set(), entry_id="e"
        )

    registry.async_remove.assert_called_once_with(unlisted_entity_id)


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.syr_connect_206aaa12345_getflo_2",  # same device set up via a second hub
        "sensor.syr_connect_206aaa12345_durchfluss",  # renamed by the user, prefix kept
    ],
)
def test_registry_cleanup_uses_unique_id_not_entity_id(entity_id: str) -> None:
    """An allowed key is kept even if its entity_id differs from the standard one."""
    registry = MagicMock()
    registry.async_get = MagicMock(return_value=None)
    _set_registry_entries(
        registry,
        [
            _registry_entry(
                "sensor",
                "206AAA12345",
                "getFLO",
                config_entry_id="hub2",
                entity_id=entity_id,
            ),
        ],
    )

    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        coordinator = {"devices": [{"id": "206AAA12345", "status": {"getFLO": "5"}}]}
        registry_cleanup(
            MagicMock(),
            cast(Any, coordinator),
            "sensor",
            allowed_keys={"getFLO"},
            entry_id="hub2",
        )

    registry.async_remove.assert_not_called()


def test_registry_cleanup_strips_platform_suffix_and_ignores_other_platforms() -> None:
    """Select unique_ids end in "_select"; entities of other platforms are not touched."""
    registry = MagicMock()
    registry.async_get = MagicMock(return_value=None)
    stale = _registry_entry("select", "DEV", "getFOO_select", config_entry_id="hub")
    _set_registry_entries(
        registry,
        [
            _registry_entry("select", "DEV", "getRTM_select", config_entry_id="hub"),
            stale,
            _registry_entry("sensor", "DEV", "getFOO", config_entry_id="hub"),
        ],
    )

    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        coordinator = {"devices": [{"id": "DEV", "status": {"getRTM": "02:00"}}]}
        registry_cleanup(
            MagicMock(),
            cast(Any, coordinator),
            "select",
            allowed_keys={"getRTM"},
            entry_id="hub",
        )

    registry.async_remove.assert_called_once_with(stale.entity_id)


def test_registry_cleanup_allowed_keys_none_is_noop() -> None:
    """registry_cleanup with allowed_keys=None must return immediately without accessing registry."""
    hass = MagicMock()
    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get"
    ) as mock_get:
        registry_cleanup(
            hass, cast(Any, {"devices": [{"id": "DEV"}]}), "sensor", allowed_keys=None
        )
        mock_get.assert_not_called()


def test_registry_cleanup_skips_device_with_no_id() -> None:
    """Devices without an 'id' key must be silently skipped."""
    hass = MagicMock()
    registry = MagicMock()
    _set_registry_entries(registry, [])
    registry.async_remove = MagicMock()

    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        # One device with no id, one with empty-string id
        registry_cleanup(
            hass,
            cast(Any, {"devices": [{"name": "no-id"}, {"id": ""}]}),
            "sensor",
            allowed_keys={"getPRS"},
            entry_id="entry",
        )

    registry.async_remove.assert_not_called()


def _registry_with_unique_id(unique_id: str, entity_id: str) -> MagicMock:
    """Return a registry mock that knows one entity, found by its unique_id."""
    registry = MagicMock()
    _set_registry_entries(registry, [])
    registry.async_get_entity_id = MagicMock(
        side_effect=lambda domain, platform, uid: (
            entity_id if uid == unique_id else None
        )
    )
    registry.async_remove = MagicMock()
    return registry


def test_registry_cleanup_keeps_sensor_with_empty_value() -> None:
    """A registered sensor whose value is empty at startup keeps its registry entry."""
    hass = MagicMock()
    device_id = "DEV"
    # getTYP has hidden_when="empty" and the device reports "": removing the entry would
    # drop its customizations (name, area, ...)
    entity_id = build_entity_id("sensor", device_id, "getTYP")
    registry = _registry_with_unique_id(
        build_unique_id("entry", device_id, "getTYP"), entity_id
    )

    coordinator = {"devices": [{"id": device_id, "status": {"getTYP": ""}}]}
    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        registry_cleanup(
            hass,
            cast(Any, coordinator),
            "sensor",
            allowed_keys={"getTYP"},
            hidden_keys=sensor._hidden_sensor_keys,
            entry_id="entry",
        )

    registry.async_remove.assert_not_called()


def test_registry_cleanup_keeps_conditional_sensors_of_offline_device() -> None:
    """An offline device (dst 0/1) reports empty measurements; that must not remove its sensors."""
    registry = MagicMock()
    _set_registry_entries(registry, [])
    registry.async_get_entity_id = MagicMock(
        side_effect=lambda domain, platform, uid: f"sensor.{uid.lower()}"
    )
    registry.async_remove = MagicMock()

    # Offline as marked by the coordinator; measurements are empty strings
    device = {
        "id": "DEV",
        "available": False,
        "status": {"dst": "1", "getCEL": "", "getBAR": "", "getWIP": ""},
    }
    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        registry_cleanup(
            MagicMock(),
            cast(Any, {"devices": [device]}),
            "sensor",
            allowed_keys={"getCEL", "getBAR", "getWIP"},
            hidden_keys=sensor._hidden_sensor_keys,
            entry_id="entry",
        )

    registry.async_remove.assert_not_called()


def test_registry_cleanup_keeps_unlisted_entities_of_offline_device() -> None:
    """A never-online device reports only getSRN; model detection on that must not remove its entities."""
    registry = MagicMock()
    _set_registry_entries(
        registry,
        [
            SimpleNamespace(
                entity_id="sensor.syr_connect_dev_getdfm",
                unique_id=build_unique_id("entry", "DEV", "getDFM"),
                platform=DOMAIN,
                domain="sensor",
                config_entry_id="entry",
            )
        ],
    )
    registry.async_get = MagicMock(return_value=None)
    registry.async_remove = MagicMock()

    # getDFM is not in the allowlist, but the device is offline: skip the cleanup
    device = {
        "id": "DEV",
        "available": False,
        "status": {"dst": "0", "getSRN": "123456789"},
    }
    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        registry_cleanup(
            MagicMock(),
            cast(Any, {"devices": [device]}),
            "sensor",
            allowed_keys={"getSRN"},
            entry_id="entry",
        )

    registry.async_remove.assert_not_called()


def test_registry_cleanup_conditionally_hidden_sensor_ignores_other_hub() -> None:
    """Conditionally hidden sensor owned by a DIFFERENT config entry must not be removed."""
    hass = MagicMock()
    device_id = "DEV"
    # Only the other hub has the entity; its unique_id contains the other entry_id
    registry = _registry_with_unique_id(
        build_unique_id("other_hub", device_id, "getDWF"),
        build_entity_id("sensor", device_id, "getDWF"),
    )

    # getDWF has hidden_when="always"
    coordinator = {"devices": [{"id": device_id, "status": {"getDWF": "350"}}]}
    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        registry_cleanup(
            hass,
            cast(Any, coordinator),
            "sensor",
            allowed_keys={"getDWF"},
            entry_id="this_hub",
            hidden_keys=sensor._hidden_sensor_keys,
        )

    registry.async_remove.assert_not_called()


def test_registry_cleanup_keeps_conditionally_visible_sensor() -> None:
    """Registry entry for a conditionally shown sensor is NOT removed when value is non-empty."""
    hass = MagicMock()
    device_id = "DEV"
    # getTYP has hidden_when - device reports a real value
    registry = _registry_with_unique_id(
        build_unique_id("entry", device_id, "getTYP"),
        build_entity_id("sensor", device_id, "getTYP"),
    )

    coordinator = {"devices": [{"id": device_id, "status": {"getTYP": "SafeTech"}}]}
    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        registry_cleanup(
            hass,
            cast(Any, coordinator),
            "sensor",
            allowed_keys={"getTYP"},
            hidden_keys=sensor._hidden_sensor_keys,
            entry_id="entry",
        )

    registry.async_remove.assert_not_called()


def test_registry_cleanup_removes_always_hidden_sensor_with_suffix() -> None:
    """A sensor with hidden_when="always" is removed even with a value and a "_2" entity_id."""
    device_id = "DEV"
    entity_id = build_entity_id("sensor", device_id, "getDWF") + "_2"
    registry = _registry_with_unique_id(
        build_unique_id("entry", device_id, "getDWF"), entity_id
    )

    # getDWF is supported (allowlist) but must never become an entity
    coordinator = {"devices": [{"id": device_id, "status": {"getDWF": "350"}}]}
    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        registry_cleanup(
            MagicMock(),
            cast(Any, coordinator),
            "sensor",
            allowed_keys={"getDWF"},
            entry_id="entry",
            hidden_keys=sensor._hidden_sensor_keys,
        )

    registry.async_remove.assert_called_once_with(entity_id)


def test_registry_cleanup_conditional_only_applies_to_sensor_domain() -> None:
    """Conditional hidden-sensor cleanup must NOT run for non-sensor domains."""
    hass = MagicMock()
    registry = MagicMock()
    device_id = "DEV"
    # getTYP is conditionally hidden - but domain is "binary_sensor", so no removal expected
    entity_id = build_entity_id("binary_sensor", device_id, "getTYP")
    _set_registry_entries(registry, [])
    registry.async_get = MagicMock(return_value=SimpleNamespace(entity_id=entity_id))
    registry.async_remove = MagicMock()

    coordinator = {"devices": [{"id": device_id, "status": {"getTYP": ""}}]}
    with patch(
        "custom_components.syr_connect.helpers.registry.er.async_get",
        return_value=registry,
    ):
        registry_cleanup(
            hass,
            cast(Any, coordinator),
            "binary_sensor",
            allowed_keys={"getTYP"},
            entry_id="entry",
        )

    registry.async_remove.assert_not_called()


@pytest.mark.parametrize(
    ("unique_id", "domain", "expected"),
    [
        # The key of an entity of the device, lowercased
        ("01JENTRY_206AAA12345_getFLO", "sensor", "getflo"),
        # The platform suffix is stripped
        ("01JENTRY_206AAA12345_getRTM_select", "select", "getrtm"),
        ("01jentry_206aaa12345_getbuz_switch", "switch", "getbuz"),
        # A suffix of another platform is part of the key
        ("01JENTRY_206AAA12345_getRTM_select", "sensor", "getrtm_select"),
        # Another device or another config entry
        ("01JENTRY_206AAA99999_getFLO", "sensor", None),
        ("01JOTHER_206AAA12345_getFLO", "sensor", None),
    ],
)
def test_entity_key(unique_id: str, domain: str, expected: str | None) -> None:
    """The key comes from the unique_id of an entity of the device, else None."""
    assert _entity_key(unique_id, "01jentry_206aaa12345_", domain) == expected


async def test_delete_issue(hass: HomeAssistant) -> None:
    """A repair issue is deleted from the issue registry of the integration."""
    with patch(
        "homeassistant.helpers.issue_registry.async_delete_issue"
    ) as mock_delete:
        delete_issue(hass, "test_issue_to_delete")

        mock_delete.assert_called_once_with(hass, DOMAIN, "test_issue_to_delete")
