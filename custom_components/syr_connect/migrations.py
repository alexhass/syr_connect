"""Migration helpers for the SYR Connect integration.

This module contains small, testable helpers that compute update kwargs
for config entry migrations. The helpers return a dict suitable for
passing to `hass.config_entries.async_update_entry(entry, **update_kwargs)`
or `None` if no update is required.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_json import SyrConnectJsonAPI
from .const import (
    _SYR_CONNECT_DEFAULT_CF_BUNDLE_IDENTIFIER,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_LOGIN_REQUIRED,
    CONF_MODEL,
    CONF_SERVICE,
)
from .exceptions import SyrConnectInvalidResponseError
from .helpers import build_entry_unique_id
from .models import detect_model

# Renamed local JSON API models (CONF_MODEL) -> their new name
_SYR_CONNECT_MIGRATIONS_LOCAL_MODEL_RENAMES = {
    "neosoft": "neosoft5000",
    "optimat22duo": "optimat2duo",
}

# Removed generic MultiController models (CONF_MODEL) -> their local base path. Such a
# model could be any role (getDFM) of its brand, so the migration asks the device.
_SYR_CONNECT_MIGRATIONS_LOCAL_MODEL_REMOVED = {
    "conceptmuco": "/trio",
    "conelmuco": "/trio",
    "ditechmuco": "/trio",
    "optimamuco": "/trio",
    "sanibelmuco": "/trio",
    "syrmuco": "/trio",
    "takemuco": "/trio",
}


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
        if entity_entry.domain != "sensor" or not entity_entry.unique_id.endswith(
            "_getFLO"
        ):
            continue
        # Legacy field: set directly on entity (older HA versions / manual UI override)
        if entity_entry.unit_of_measurement == UnitOfVolumeFlowRate.LITERS_PER_MINUTE:
            ent_reg.async_update_entity(
                entity_entry.entity_id, unit_of_measurement=None
            )
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


def v4_to_v5_remove_sta_binary_sensor(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove stale 'sta' entities from the registry (v4 → v5).

    The 'sta' connectivity field was renamed to 'dst'. Any remaining
    binary_sensor or sensor entries with unique_id ending in '_sta' are
    ghost entities and must be removed.
    """
    ent_reg = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if entity_entry.unique_id.endswith("_sta"):
            ent_reg.async_remove(entity_entry.entity_id)


def v5_to_v6_fix_nps_unit(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reset entity registry unit override for getNPS sensors (v5 → v6).

    When getNPS's native_unit_of_measurement changed from "" to "s"
    (UnitOfTime.SECONDS), existing entity registry entries may have ""
    stored as the display unit override. Resetting the override to None
    lets HA pick up the new native unit from the code.
    """
    ent_reg = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if entity_entry.domain != "sensor" or not entity_entry.unique_id.endswith(
            "_getNPS"
        ):
            continue
        if entity_entry.unit_of_measurement == "":
            ent_reg.async_update_entity(
                entity_entry.entity_id, unit_of_measurement=None
            )
        for namespace in ("sensor.private", "sensor"):
            ns_opts = dict(entity_entry.options.get(namespace, {}))
            changed = False
            for key in ("unit_of_measurement", "suggested_unit_of_measurement"):
                if ns_opts.get(key) == "":
                    ns_opts.pop(key)
                    changed = True
            if changed:
                ent_reg.async_update_entity_options(
                    entity_entry.entity_id, namespace, ns_opts or None
                )


def v6_to_v7_scope_unique_id_by_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Prefix entity unique_ids with the owning config entry ID (v6 → v7).

    unique_id used to be `device_id_key` only. The same physical device
    (serial number) can be reachable from more than one config entry (e.g.
    a device visible via two SYR Connect accounts), which caused unique_id
    collisions across hubs. Prepending `entry_id` (already the prefix used
    by `build_unique_id`) keeps existing entities intact while making
    unique_ids distinct per hub going forward.
    """
    ent_reg = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if entity_entry.unique_id.startswith(prefix):
            continue
        ent_reg.async_update_entity(
            entity_entry.entity_id,
            new_unique_id=f"{entry.entry_id}_{entity_entry.unique_id}",
        )


def v7_to_v8_rename_local_model(entry: ConfigEntry) -> dict | None:
    """Compute update kwargs for migrating v7 -> v8.

    Local JSON API entries store the model chosen at setup (CONF_MODEL). The
    Optima T2.3 model was renamed, and the generic NeoSoft model (dk=1200) turned
    out to be the NeoSoft 5000, so these entries could no longer be loaded.
    """
    if entry.data.get(CONF_API_TYPE) != API_TYPE_JSON:
        return None
    new_model = _SYR_CONNECT_MIGRATIONS_LOCAL_MODEL_RENAMES.get(
        str(entry.data.get(CONF_MODEL))
    )
    if new_model is None:
        return None
    return {"data": {**entry.data, CONF_MODEL: new_model}, "version": 8}


async def v8_to_v9_detect_local_model(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict | None:
    """Compute update kwargs for migrating v8 -> v9.

    Local JSON API entries store the model chosen at setup (CONF_MODEL). The
    generic MultiController models were removed, so these entries could no longer
    be loaded. Such a model could be any of its brand's roles, so the model is
    detected from the device.

    Raises:
        SyrConnectConnectionError: If the device cannot be reached
        SyrConnectError: If the device's model cannot be detected
    """
    if entry.data.get(CONF_API_TYPE) != API_TYPE_JSON:
        return None
    base_path = _SYR_CONNECT_MIGRATIONS_LOCAL_MODEL_REMOVED.get(
        str(entry.data.get(CONF_MODEL))
    )
    if base_path is None:
        return None
    new_model = await _async_detect_local_model(hass, entry, base_path)
    return {"data": {**entry.data, CONF_MODEL: new_model}, "version": 9}


def v9_to_v10_entry_unique_id_by_service(entry: ConfigEntry) -> dict | None:
    """Compute update kwargs for migrating v9 -> v10.

    The unique_id of a cloud entry was "xml_<username>", so the same e-mail address
    could not be set up for a second cloud service, although every service has
    accounts of its own. It now contains the service (see
    helpers.build_entry_unique_id). Local entries keep "json_<host>".
    """
    if entry.data.get(CONF_API_TYPE) != API_TYPE_XML:
        return None
    return {
        "unique_id": build_entry_unique_id(API_TYPE_XML, entry.data),
        "version": 10,
    }


async def _async_detect_local_model(
    hass: HomeAssistant, entry: ConfigEntry, base_path: str
) -> str:
    """Detect the model of a local device from its status.

    Raises:
        SyrConnectConnectionError: If the device cannot be reached
        SyrConnectInvalidResponseError: If no model with local access matches
    """
    api = SyrConnectJsonAPI(
        async_get_clientsession(hass),
        host=entry.data[CONF_HOST],
        base_path=base_path,
        login_required=entry.data.get(CONF_LOGIN_REQUIRED),
    )
    devices = await api.get_devices("local")
    status = await api.get_device_status(devices[0]["id"])
    model = detect_model(status)
    if model.base_path is None:
        raise SyrConnectInvalidResponseError(
            f"No model with local access matches the device ({model.display_name})"
        )
    return model.name
