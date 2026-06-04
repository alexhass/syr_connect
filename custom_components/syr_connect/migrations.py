"""Migration helpers for the SYR Connect integration.

This module contains small, testable helpers that compute update kwargs
for config entry migrations. The helpers return a dict suitable for
passing to `hass.config_entries.async_update_entry(entry, **update_kwargs)`
or `None` if no update is required.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    _SYR_CONNECT_DEFAULT_CF_BUNDLE_IDENTIFIER,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_MODEL,
    CONF_SERVICE,
)


def v1_to_v2_update_kwargs(entry: ConfigEntry) -> dict | None:
    """Compute update kwargs for migrating v1 -> v2.

    Ensure `CONF_API_TYPE` is set correctly ("json" if `host`/`model`
    is present, otherwise "xml") and update `unique_id` where possible.
    Return kwargs to update the entry data and bump the config version
    to 2, or `None` if no migration is required.
    """
    host = entry.data.get(CONF_HOST)
    model = entry.data.get(CONF_MODEL)
    username = entry.data.get(CONF_USERNAME)

    desired_api = API_TYPE_JSON if (host or model) else API_TYPE_XML
    current_api = entry.data.get(CONF_API_TYPE)

    # If already correct and at least version 2, nothing to do
    if current_api == desired_api and entry.version >= 2:
        return None

    new_data = {**entry.data, CONF_API_TYPE: desired_api}
    update_kwargs: dict = {"data": new_data, "version": 2}

    if desired_api == API_TYPE_JSON and host:
        update_kwargs["unique_id"] = f"{API_TYPE_JSON}_{host}"
    elif username:
        update_kwargs["unique_id"] = f"{desired_api}_{username}"

    return update_kwargs


def v2_to_v3_fix_flo_unit(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reset entity registry unit override for getFLO sensors (v2 → v3).

    When getFLO's native_unit_of_measurement changed from L/min to L/h,
    existing entity registry entries may have "L/min" stored as the display
    unit override. HA respects that override and keeps converting the value
    back to L/min even though the native unit is now L/h. Resetting the
    override to None lets HA pick up the new native unit from the code.
    """
    ent_reg = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if entity_entry.domain != "sensor" or not entity_entry.unique_id.endswith("_getFLO"):
            continue
        # Legacy field: set directly on entity (older HA versions / manual UI override)
        if entity_entry.unit_of_measurement == UnitOfVolumeFlowRate.LITERS_PER_MINUTE:
            ent_reg.async_update_entity(entity_entry.entity_id, unit_of_measurement=None)
        # HA stores the suggested unit in "sensor.private" (set automatically on first
        # registration) and the user-selected unit in "sensor" (set via UI).
        # Both namespaces must be cleared so HA picks up the new native unit from code.
        for namespace in ("sensor.private", "sensor"):
            ns_opts = dict(entity_entry.options.get(namespace, {}))
            changed = False
            for key in ("unit_of_measurement", "suggested_unit_of_measurement"):
                if ns_opts.get(key) == UnitOfVolumeFlowRate.LITERS_PER_MINUTE:
                    ns_opts.pop(key)
                    changed = True
            if changed:
                ent_reg.async_update_entity_options(
                    entity_entry.entity_id, namespace, ns_opts or None
                )


def v3_to_v4_add_service(entry: ConfigEntry) -> dict | None:
    """Compute update kwargs for migrating v3 -> v4.

    Existing XML API config entries created before CONF_SERVICE was introduced
    don't have a service set. Without it the coordinator cannot look up the
    service and configuration_url stays None. Default to the SYR Connect
    service (the only service that existed before multi-service support).
    JSON API entries don't use CONF_SERVICE and are left unchanged.
    """
    if entry.data.get(CONF_API_TYPE) != API_TYPE_XML:
        return None
    if entry.data.get(CONF_SERVICE):
        return None
    new_data = {**entry.data, CONF_SERVICE: _SYR_CONNECT_DEFAULT_CF_BUNDLE_IDENTIFIER}
    return {"data": new_data, "version": 4}
