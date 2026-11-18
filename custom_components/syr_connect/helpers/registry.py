"""Entity, device and issue registry: ids, lookups, cleanup and recorder statistics."""

from collections.abc import Callable, Mapping, Set as AbstractSet
import logging
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.const import CONF_HOST, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import slugify

from ..aiosyrconnect import SyrConnectStatus
from ..const import API_TYPE_JSON, API_TYPE_XML, CONF_SERVICE, DOMAIN
from ..data import SyrConnectCoordinatorData, SyrConnectDevice
from ..models import MODEL_SIGNATURES, SyrConnectModel
from .device import get_device_model
from .profile import get_model_supported_keys

_LOGGER = logging.getLogger(__name__)


def build_entity_id(platform: str, device_id: str, key: str) -> str:
    """Build consistent entity ID.

    Args:
        platform: Platform name (sensor, binary_sensor, button)
        device_id: Device ID (serial number)
        key: Entity key (sensor_key, command, etc.)

    Returns:
        Formatted entity ID
    """
    return f"{platform}.{DOMAIN}_{device_id.lower()}_{key.lower()}"


def build_unique_id(entry_id: str | None, device_id: str, key: str) -> str:
    """Build a unique_id scoped to the owning config entry.

    The same physical device (serial number) can be reachable from more than
    one config entry (e.g. a device visible via two SYR Connect accounts).
    Prefixing with `entry_id` keeps unique_ids distinct per hub in that case.
    `entry_id` is omitted when not available (e.g. legacy/test callers) to
    preserve the historical `device_id_key` format.

    Args:
        entry_id: Owning config entry ID, or None if unavailable.
        device_id: Device ID (serial number).
        key: Entity key (sensor_key, command, etc.), optionally with a
            platform-specific suffix (e.g. 'getBAR_switch').

    Returns:
        Formatted unique_id.
    """
    if entry_id:
        return f"{entry_id}_{device_id}_{key}"
    return f"{device_id}_{key}"


def build_entry_unique_id(
    api_type: str, data: Mapping[str, Any], serial: str | None = None
) -> str:
    """Return the unique_id of a config entry for its connection data.

    A local entry is identified by the serial number of its device, so a new IP
    address keeps it and the same device cannot be set up twice (by IP address and
    by hostname). Without a serial number it is the host: the unique_id of the local
    entries set up before the serial number was used, until their next setup.

    A cloud account belongs to its cloud service (CONF_SERVICE, the
    cf_bundle_identifier of the app): the login only works with the app name of the
    service, also where several services share one server. The same e-mail address
    can therefore be a different account in every service. The username is a name
    or an e-mail address; the cloud ignores its letter case, so it is lowercased,
    and it cannot start or end with whitespace, which older entries may still have.

    Args:
        api_type: API type of the entry (API_TYPE_XML or API_TYPE_JSON).
        data: Entry data with the host (local) or the service and username (cloud).
        serial: Serial number of the local device, None for the host-based unique_id.

    Returns:
        "json_<serial>", "json_<host>" or "xml_<cf_bundle_identifier>_<username>"
        with the username in lowercase, e.g. "xml_de.consoft.syr.connect_me@example.com".
    """
    if api_type == API_TYPE_JSON:
        return f"{API_TYPE_JSON}_{data[CONF_HOST] if serial is None else serial}"
    return f"{API_TYPE_XML}_{data[CONF_SERVICE]}_{str(data[CONF_USERNAME]).strip().lower()}"


def build_statistic_id(device_id: str, key: str) -> str:
    """Build the external statistic ID of the measurement history of a sensor.

    External statistics need the form "<domain>:<object id>" with slugs. The ID has
    no entry_id: a device reachable from several hubs shares one history.

    Args:
        device_id: Device ID (serial number).
        key: Sensor key of the series (e.g. "getCEL").

    Returns:
        Statistic ID, e.g. "syr_connect:123456789_getcel_history".
    """
    return f"{DOMAIN}:{slugify(device_id)}_{key.lower()}_history"


def clear_device_statistics(
    hass: HomeAssistant, entry_id: str, device_ids: AbstractSet[str]
) -> None:
    """Delete the measurement history statistics of devices removed from an entry.

    The statistic ID has no entry_id (see build_statistic_id), so a device that
    another config entry of this integration still has keeps its history. The model
    of a removed device is no longer known, so the IDs of every series key of every
    device profile are cleared; IDs without statistics are ignored.

    Args:
        hass: Home Assistant instance.
        entry_id: Config entry the devices were removed from.
        device_ids: Device IDs (serial numbers) of the removed devices.
    """
    if not device_ids or "recorder" not in hass.config.components:
        return
    device_registry = dr.async_get(hass)
    device_ids = set(device_ids) - {
        identifier
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id != entry_id
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        )
        for domain, identifier in device_entry.identifiers
        if domain == DOMAIN
    }
    keys = {
        statistic.key
        for signature in MODEL_SIGNATURES
        if signature.device_profile is not None
        for statistic in signature.device_profile.statistics
    }
    statistic_ids = sorted(
        build_statistic_id(device_id, key) for device_id in device_ids for key in keys
    )
    if statistic_ids:
        _LOGGER.debug("Clearing statistics of removed devices: %s", statistic_ids)
        get_instance(hass).async_clear_statistics(statistic_ids)


def find_entity_id(
    registry: er.EntityRegistry,
    domain: str,
    entry_id: str | None,
    device_id: str,
    key: str,
) -> str | None:
    """Return the entity_id registered for an entity of this integration, or None.

    Looks the entity up by its unique_id (see build_unique_id), not by the entity_id
    built from the key: HA appends "_2" to the entity_id when the same device is set up
    via a second hub, and users may rename it. Because the unique_id contains the
    entry_id, only entities of this config entry are found.

    Args:
        registry: The entity registry.
        domain: Entity domain (e.g. "sensor").
        entry_id: Owning config entry ID, or None if unavailable.
        device_id: Device ID (serial number).
        key: Entity key as passed to build_unique_id, including any platform
            suffix (e.g. "getOHW_select").
    """
    return registry.async_get_entity_id(
        domain, DOMAIN, build_unique_id(entry_id, device_id, key)
    )


def delete_issue(hass: HomeAssistant, issue_id: str) -> None:
    """Delete a repair issue of this integration.

    Args:
        hass: Home Assistant instance
        issue_id: Unique identifier for the issue to delete
    """
    ir.async_delete_issue(hass, DOMAIN, issue_id)


def cleanup_removed_devices(
    hass: HomeAssistant,
    coordinator_data: SyrConnectCoordinatorData | None,
    entry_id: str,
) -> None:
    """Remove HA devices for this entry that no longer exist in the SYR Connect account.

    If a device is deleted from the account (e.g. by another user of the same
    hub) it simply stops appearing in `coordinator_data["devices"]`, but
    nothing else ever notices - the device (and all its entities) would
    otherwise stay in Home Assistant forever. This compares the device
    registry entries owned by `entry_id` against the serial numbers
    currently returned by the coordinator and removes any that disappeared,
    together with their entities.

    Every config entry has a device of its own in the registry, also when the
    same physical device is visible via two SYR Connect accounts, so removing
    it leaves the device of the other entry untouched.

    Args:
        hass: Home Assistant instance.
        coordinator_data: Coordinator .data mapping containing devices.
        entry_id: Owning config entry ID.
    """
    try:
        current_ids = {
            d["id"]
            for d in (coordinator_data.get("devices", []) if coordinator_data else [])
            if d.get("id")
        }
        removed_ids: set[str] = set()
        device_registry = dr.async_get(hass)
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry_id
        ):
            device_id = next(
                (
                    identifier
                    for domain, identifier in device_entry.identifiers
                    if domain == DOMAIN
                ),
                None,
            )
            if device_id is not None and device_id not in current_ids:
                _LOGGER.debug("Removing stale device from registry: %s", device_id)
                device_registry.async_remove_device(device_entry.id)
                removed_ids.add(device_id)
        clear_device_statistics(hass, entry_id, removed_ids)
    except Exception:
        _LOGGER.exception("Failed to cleanup removed devices from registry")


def _is_status_usable(device: SyrConnectDevice, domain: str) -> bool:
    """Return True if the device status tells which entities the device has.

    Args:
        device: The device from the coordinator data.
        domain: Entity domain of the cleanup, for the log message.
    """
    # An empty status means it could not be fetched yet (e.g. a temporary
    # failure at startup), not that the device lost all its keys. Removing
    # entities now would drop their registry customizations (name, area, ...).
    if not device.get("status", {}):
        _LOGGER.debug(
            "No status for device %s yet; skipping %s registry cleanup",
            device["id"],
            domain,
        )
        return False

    # While the cloud reports the device offline (dst 0/1, available=False) its status
    # says nothing about which entities it has: the measurements are empty strings
    # (docs/known_issues_xml_api.md, issue 2), and a never-online device reports little
    # more than getSRN, so detect_model may pick the wrong model and key list.
    if not device.get("available", True):
        _LOGGER.debug(
            "Device %s is offline; skipping %s registry cleanup",
            device["id"],
            domain,
        )
        return False
    return True


def _entity_key(unique_id: str, unique_id_prefix: str, domain: str) -> str | None:
    """Return the lowercase key of an entity of a device, or None for another device.

    The key is taken from the unique_id, not from the entity_id. Both are set by
    the entities of this integration, but only the unique_id is stable:
    - unique_id: "<entry_id>_<device_id>_<key>" (see build_unique_id), e.g.
      "01J..._206AAA12345_getFLO". Home Assistant never changes it.
    - entity_id: "<domain>.syr_connect_<device_id>_<key>" (see build_entity_id),
      e.g. "sensor.syr_connect_206aaa12345_getflo". It is not reliable: if the
      same device is set up via a second hub, HA appends "_2" because the
      entity_id is already taken, and users may rename it. Reading the key from
      it would turn "getflo_2" or a renamed "..._durchfluss" into an unknown key
      and remove a valid entity (with its name, area, ... customizations) on
      every setup.

    Some platforms add their own suffix to keep unique_ids distinct from a sensor
    with the same key: "getRTM_select", "getbuz_switch", "getnot_update". It is
    stripped to get the plain key ("getrtm"). Comparisons are case-insensitive
    because switch/update build their unique_id lowercased.

    Args:
        unique_id: unique_id of the registry entry.
        unique_id_prefix: Lowercase "<entry_id>_<device_id>_" of the device.
        domain: Entity domain, the platform suffix to strip.
    """
    unique_id = unique_id.lower()
    if not unique_id.startswith(unique_id_prefix):
        return None
    return unique_id[len(unique_id_prefix) :].removesuffix(f"_{domain}")


def _remove_unlisted_entities(
    registry: er.EntityRegistry,
    platform_entries: list[er.RegistryEntry],
    unique_id_prefix: str,
    domain: str,
    allowed_keys: AbstractSet[str],
) -> None:
    """Remove the entities of a device whose key is not in its allowlist.

    Args:
        registry: The entity registry.
        platform_entries: Registry entries of the config entry and the domain.
        unique_id_prefix: Lowercase "<entry_id>_<device_id>_" of the device.
        domain: Entity domain of the cleanup.
        allowed_keys: Keys the device may have entities for.
    """
    allowed_lower = {k.lower() for k in allowed_keys}
    for entry in platform_entries:
        key_lower = _entity_key(str(entry.unique_id), unique_id_prefix, domain)
        if key_lower is not None and key_lower not in allowed_lower:
            _LOGGER.debug(
                "Removing unlisted %s from registry: %s",
                domain,
                entry.entity_id,
            )
            registry.async_remove(entry.entity_id)


def _remove_hidden_entities(
    registry: er.EntityRegistry,
    domain: str,
    entry_id: str,
    device_id: str,
    keys: AbstractSet[str],
) -> None:
    """Remove the entities of a device that the platform hides for its status.

    Found by unique_id, so a renamed or "_2"-suffixed entity is removed as well; the
    unique_id contains the entry_id, so only entities of this config entry are found.

    Args:
        registry: The entity registry.
        domain: Entity domain of the cleanup.
        entry_id: Owning config entry ID.
        device_id: Device ID (serial number).
        keys: Keys of the hidden entities.
    """
    for key in keys:
        entity_id = find_entity_id(registry, domain, entry_id, device_id, key)
        if entity_id is not None:
            _LOGGER.debug(
                "Removing conditionally hidden %s from registry: %s",
                domain,
                entity_id,
            )
            registry.async_remove(entity_id)


def registry_cleanup(
    hass: HomeAssistant,
    coordinator_data: SyrConnectCoordinatorData | None,
    domain: str,
    allowed_keys: set[str] | None = None,
    entry_id: str | None = None,
    hidden_keys: Callable[[SyrConnectStatus, SyrConnectModel], set[str]] | None = None,
) -> None:
    """Remove previously-registered entities from the entity registry.

    Scans all registered entities for the given domain/devices and removes
    any whose key is NOT in allowed_keys. If allowed_keys is None,
    nothing is removed.

    With `hidden_keys`, also removes the entities of the keys it returns for the
    current device status (the sensor platform passes the sensors that never become
    an entity and the keys of the other cartridge types).

    Args:
        hass: Home Assistant instance.
        coordinator_data: Coordinator .data mapping containing devices.
        domain: Entity domain string (e.g. "sensor").
        allowed_keys: Set of permitted sensor keys. Entities whose key is not
            in this set will be removed from the entity registry.
        entry_id: Owning config entry ID. Only entities registered under this
            entry are considered; entities of a *different* hub that shares the
            same device_id (the same physical device visible from two hubs) are
            not ours to remove. Without it, nothing is removed.
        hidden_keys: Returns the keys whose entities are hidden for a device
            status and model; they are removed as well.
    """
    if allowed_keys is None or entry_id is None:
        return
    try:
        registry = er.async_get(hass)
        # Only the entities of this config entry and of the platform being cleaned up
        # (sensor cleanup must not touch a select of the same device). The registry
        # looks them up by config entry, without scanning the whole registry.
        platform_entries = [
            entry
            for entry in er.async_entries_for_config_entry(registry, entry_id)
            if entry.domain == domain
        ]

        for device in coordinator_data.get("devices", []) if coordinator_data else []:
            device_id = device.get("id")
            if not device_id or not _is_status_usable(device, domain):
                continue

            # Scope the allowlist to the detected model (falls back to allowed_keys
            # unchanged for models that haven't opted into per-model key lists).
            model_info = get_device_model(device)
            _remove_unlisted_entities(
                registry,
                platform_entries,
                build_unique_id(entry_id, device_id, "").lower(),
                domain,
                get_model_supported_keys(model_info, domain, allowed_keys),
            )
            if hidden_keys is not None:
                _remove_hidden_entities(
                    registry,
                    domain,
                    entry_id,
                    device_id,
                    hidden_keys(device.get("status", {}), model_info),
                )
    except Exception:
        _LOGGER.exception(
            "Failed to cleanup excluded %s entities from registry", domain
        )
