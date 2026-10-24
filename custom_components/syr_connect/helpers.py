"""Helper functions for SYR Connect integration."""

from collections.abc import Callable, Set as AbstractSet
import contextlib
import ipaddress
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    _SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT,
    _SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT,
    _SYR_CONNECT_SCAN_INTERVAL_CONF,
    _SYR_CONNECT_SENSOR_ALA_CODES_GENERIC,
    _SYR_CONNECT_SENSOR_NOT_CODES_GENERIC,
    _SYR_CONNECT_SENSOR_WRN_CODES_GENERIC,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    DOMAIN,
)
from .data import SyrConnectCoordinatorData, SyrConnectDevice
from .models import UNKNOWN_MODEL, SyrConnectModel, detect_model

_LOGGER = logging.getLogger(__name__)


def is_value_true(val: object) -> bool:
    """Normalize a heterogeneous API flag value to a Python bool.

    SYR devices report binary activation flags (e.g. getPAx, getBUZ) in varying
    formats depending on API and firmware version: the XML API always sends strings
    ("1", "0", "True", "false"), the local JSON API native bool or int/float. This
    function is the single conversion for all boolean keys, so callers do not need
    to handle each format separately.

    Args:
        val: Raw value received from the device API.

    Returns:
        True if val represents a truthy/active state, False otherwise.
        Unknown or unconvertible values always return False.
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, (int | float)):
        try:
            return int(float(val)) != 0
        except ValueError, TypeError, OverflowError:
            return False
    if isinstance(val, str):
        sval = val.strip().lower()
        if sval in ("1", "true"):
            return True
        if sval in ("0", "false"):
            return False
        try:
            return int(float(sval)) != 0
        except ValueError, TypeError, OverflowError:
            return False
    return False


def get_default_scan_interval_for_entry(entry: ConfigEntry | dict | None) -> int:
    """Return the default scan interval for a config entry.

    Logic:
    - If `entry` is None -> return XML default
    - If the entry has an explicit `scan_interval` option -> return it
    - Otherwise, return the per-API default: JSON -> JSON default, else XML default
    """
    # If no entry provided, preserve legacy XML default
    if entry is None:
        return _SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT

    # Accept either a ConfigEntry or a plain dict (used internally by the coordinator)
    if isinstance(entry, dict):
        options = entry.get("options") or {}
        data = entry.get("data") or {}
    else:
        options = getattr(entry, "options", None) or {}
        data = getattr(entry, "data", None) or {}

    # If user explicitly set a scan interval option, use it
    if _SYR_CONNECT_SCAN_INTERVAL_CONF in options:
        try:
            return int(options[_SYR_CONNECT_SCAN_INTERVAL_CONF])
        except TypeError, ValueError:
            pass

    # Otherwise use per-API default (default to XML for legacy)
    api_type = data.get(CONF_API_TYPE, API_TYPE_XML)
    return (
        _SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT
        if api_type == API_TYPE_JSON
        else _SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT
    )


def get_device(
    coordinator_data: SyrConnectCoordinatorData | None, device_id: str
) -> SyrConnectDevice | None:
    """Return the device with the given id from the coordinator data.

    Args:
        coordinator_data: Coordinator data, None before the first refresh
        device_id: Device ID (serial number)

    Returns:
        The device, or None if it is not in the data
    """
    if not coordinator_data:
        return None
    for device in coordinator_data.get("devices", []):
        if device.get("id") == device_id:
            return device
    return None


def detect_device_model(device: SyrConnectDevice) -> SyrConnectModel:
    """Detect the model of a device from its cloud device kind and its status.

    Only the cloud API (XML) reports `dk`, `dkv` and `sbt`; without them the model is
    detected from the status alone.

    Args:
        device: The device from the coordinator data

    Returns:
        The detected model, or `UNKNOWN_MODEL`
    """
    return detect_model(
        device.get("status"),
        dk=device.get("dk"),
        dkv=device.get("dkv"),
        sbt=device.get("sbt"),
    )


def get_device_model(device: SyrConnectDevice | None) -> SyrConnectModel:
    """Return the model of a device, as detected by the coordinator.

    Device data that was not built by the coordinator has no stored model; it is
    detected instead.

    Args:
        device: The device from the coordinator data, or None if it is missing

    Returns:
        The detected model, or `UNKNOWN_MODEL` without a device
    """
    if device is None:
        return UNKNOWN_MODEL
    model = device.get("model")
    if model is not None:
        return model
    return detect_device_model(device)


def is_device_available(coordinator: Any, device_id: str) -> bool:
    """Return whether the entities of a device are available.

    Shared by the `available` property of all entities of a device:
    - False if the last coordinator update failed.
    - The device's own `available` flag otherwise (False while the cloud reports it offline).
    - False if the device is not in the data: temporary failures keep the devices of the
      last update, so a missing device was removed from the account (it is removed from
      Home Assistant at the next setup).
    """
    if not coordinator.last_update_success:
        return False
    device = get_device(coordinator.data, device_id)
    if device is None:
        return False
    return bool(device.get("available", True))


def build_device_info(
    device_id: str,
    device_name: str,
    coordinator_data: SyrConnectCoordinatorData | None,
) -> DeviceInfo:
    """Build DeviceInfo object from coordinator data.

    Args:
        device_id: Device ID (serial number)
        device_name: Device display name
        coordinator_data: Coordinator data containing device information

    Returns:
        DeviceInfo object with device metadata
    """

    model = None
    manufacturer = None
    sw_version = None
    hw_version = None
    mac = None
    connections = set()
    configuration_url: str | None = None

    # Extract device information from coordinator data
    device = get_device(coordinator_data, device_id)
    if coordinator_data is not None and device is not None:
        status = device.get("status", {})

        # Get human-friendly model display name and manufacturer
        detected = get_device_model(device)
        model = detected.display_name
        manufacturer = detected.manufacturer
        configuration_url = coordinator_data.get("configuration_url")

        # Get software version from getVER
        if status.get("getVER"):
            sw_version = str(status["getVER"])

        # Get hardware version from getFIR
        if status.get("getFIR"):
            hw_version = str(status["getFIR"])

        # Get MAC address using prioritized helper
        detected_mac = get_current_mac(status)
        if detected_mac:
            mac = str(detected_mac)
            connections.add(("mac", mac))

    # Use fallback if no model found
    if model is None:
        model = "Unknown model"
        _LOGGER.debug("No model found for device %s, using fallback", device_id)
    if manufacturer is None:
        manufacturer = "Unknown"

    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=device_name,
        manufacturer=manufacturer,
        model=model,
        sw_version=sw_version,
        hw_version=hw_version,
        serial_number=device_id,
        connections=connections or set(),
        configuration_url=configuration_url,
    )


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


def get_model_supported_keys(
    model_info: SyrConnectModel, platform: str, global_supported_keys: set[str]
) -> set[str]:
    """Return the supported-keys allowlist for a platform, scoped to the detected model.

    If the detected model has a `device_profile` (from a `devices/<name>.py` file,
    see `models.MODEL_SIGNATURES`), its allowlist for the platform is used as a
    POSITIVE, device-specific allowlist instead of `global_supported_keys`.
    Rebranded variants of the same hardware share one profile.
    This is deliberately an allowlist, not an exclusion list — the global
    allowlists of the platform modules cover ~90 different models, and new/unexpected keys can
    show up in any device's API response at any time, so only explicitly
    confirmed keys are trusted per device. Falls back to `global_supported_keys`
    unchanged when the model has no profile, or its profile has no allowlist for
    this platform (an explicit empty set is honored as "no entities of this
    platform for this model", not a fallback trigger).

    Args:
        model_info: Result of `models.detect_model()`.
        platform: Entity domain string (e.g. "sensor", "select", "switch"); the name
            of a `SyrConnectDeviceProfile` allowlist field.
        global_supported_keys: The platform's full/default allowlist.

    Returns:
        The effective allowlist to use for this device.
    """
    profile = model_info.device_profile
    if profile is None:
        return global_supported_keys
    # No default: a platform without a profile field is a programming error.
    device_keys: AbstractSet[str] | None = getattr(profile, platform)
    # None means "not defined" -> fall back. An explicit empty set is a valid
    # override meaning "this model has none of this platform's entities".
    if device_keys is None:
        return global_supported_keys
    return set(device_keys)


def cleanup_removed_devices(
    hass: HomeAssistant,
    coordinator_data: SyrConnectCoordinatorData | None,
    entry_id: str,
) -> None:
    """Detach HA devices for this entry that no longer exist in the SYR Connect account.

    If a device is deleted from the account (e.g. by another user of the same
    hub) it simply stops appearing in `coordinator_data["devices"]`, but
    nothing else ever notices - the device (and all its entities) would
    otherwise stay in Home Assistant forever. This compares the device
    registry entries owned by `entry_id` against the serial numbers
    currently returned by the coordinator and detaches any that disappeared.

    Detaching only this `entry_id` (rather than a hard delete) is important
    because the same physical device can be shared across config entries
    (e.g. visible via two SYR Connect accounts); Home Assistant only fully
    removes the device - cascading its entities - once no config entry
    references it anymore.

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
                device_registry.async_update_device(
                    device_entry.id, remove_config_entry_id=entry_id
                )
    except Exception:
        _LOGGER.exception("Failed to cleanup removed devices from registry")


def registry_cleanup(
    hass: HomeAssistant,
    coordinator_data: SyrConnectCoordinatorData | None,
    domain: str,
    allowed_keys: set[str] | None = None,
    entry_id: str | None = None,
    hidden_keys: Callable[[dict[str, Any]], set[str]] | None = None,
) -> None:
    """Remove previously-registered entities from the entity registry.

    Scans all registered entities for the given domain/devices and removes
    any whose key is NOT in allowed_keys. If allowed_keys is None,
    nothing is removed.

    With `hidden_keys`, also removes the entities of the keys it returns for the
    current device status (the sensor platform passes the sensors that never become
    an entity and getLOT/getOHW for the wrong cartridge type).

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
            status; they are removed as well.
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
            if not device_id:
                continue

            # An empty status means it could not be fetched yet (e.g. a temporary
            # failure at startup), not that the device lost all its keys. Removing
            # entities now would drop their registry customizations (name, area, ...).
            status = device.get("status", {})
            if not status:
                _LOGGER.debug(
                    "No status for device %s yet; skipping %s registry cleanup",
                    device_id,
                    domain,
                )
                continue

            # While the cloud reports the device offline (dst 0/1, available=False) its status
            # says nothing about which entities it has: the measurements are empty strings
            # (docs/known_issues_xml_api.md, issue 2), and a never-online device reports little
            # more than getSRN, so detect_model may pick the wrong model and key list.
            if not device.get("available", True):
                _LOGGER.debug(
                    "Device %s is offline; skipping %s registry cleanup",
                    device_id,
                    domain,
                )
                continue

            # Scope the allowlist to the detected model (falls back to allowed_keys
            # unchanged for models that haven't opted into per-model key lists).
            model_info = get_device_model(device)
            device_allowed_keys = get_model_supported_keys(
                model_info, domain, allowed_keys
            )
            allowed_lower = {k.lower() for k in device_allowed_keys}

            # Remove entities whose key is no longer in the allowed set.
            #
            # The key is taken from the unique_id, not from the entity_id. Both are set by
            # the entities of this integration, but only the unique_id is stable:
            # - unique_id: "<entry_id>_<device_id>_<key>" (see build_unique_id), e.g.
            #   "01J..._206AAA12345_getFLO". Home Assistant never changes it.
            # - entity_id: "<domain>.syr_connect_<device_id>_<key>" (see build_entity_id),
            #   e.g. "sensor.syr_connect_206aaa12345_getflo". It is not reliable: if the
            #   same device is set up via a second hub, HA appends "_2" because the
            #   entity_id is already taken, and users may rename it. Reading the key from
            #   it would turn "getflo_2" or a renamed "..._durchfluss" into an unknown key
            #   and remove a valid entity (with its name, area, ... customizations) on
            #   every setup.
            #
            # All ids of this device and config entry start with the same prefix,
            # "<entry_id>_<device_id>_". Comparisons are case-insensitive because
            # switch/update build their unique_id lowercased.
            unique_id_prefix = build_unique_id(entry_id, device_id, "").lower()
            for entry in platform_entries:
                # Only entities of this device.
                unique_id = str(entry.unique_id).lower()
                if not unique_id.startswith(unique_id_prefix):
                    continue
                # What remains is the key. Some platforms add their own suffix to keep
                # unique_ids distinct from a sensor with the same key: "getRTM_select",
                # "getbuz_switch", "getnot_update". Strip it to get the plain key ("getrtm").
                key_lower = unique_id[len(unique_id_prefix) :].removesuffix(
                    f"_{domain}"
                )
                if key_lower not in allowed_lower:
                    _LOGGER.debug(
                        "Removing unlisted %s from registry: %s",
                        domain,
                        entry.entity_id,
                    )
                    try:
                        registry.async_remove(entry.entity_id)
                    except Exception:
                        _LOGGER.exception("Failed to remove entity %s", entry.entity_id)

            # Remove the entities the platform hides for the current device status. Found by
            # unique_id, so a renamed or "_2"-suffixed entity is removed as well; the unique_id
            # contains the entry_id, so only entities of this config entry are found.
            for key in hidden_keys(status) if hidden_keys is not None else ():
                entity_id = find_entity_id(registry, domain, entry_id, device_id, key)
                if entity_id is not None:
                    _LOGGER.debug(
                        "Removing conditionally hidden %s from registry: %s",
                        domain,
                        entity_id,
                    )
                    try:
                        registry.async_remove(entity_id)
                    except Exception:
                        _LOGGER.exception("Failed to remove entity %s", entity_id)
    except Exception:
        _LOGGER.exception(
            "Failed to cleanup excluded %s entities from registry", domain
        )


def is_empty_ip(value: Any) -> bool:
    """Return True if an IP address value is missing, blank or the unspecified address.

    Formats:
    - Missing or blank: None, "" -> True
    - Unspecified address (Trio DFR/LS without an address): "0.0.0.0", "::" -> True
    - Any other value, also a hostname: "192.168.1.10" -> False
    """
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    text = value.strip()
    if text == "":
        return True
    try:
        return ipaddress.ip_address(text).is_unspecified
    except ValueError:
        return False


def get_current_mac(status: dict[str, Any]) -> str | None:
    """Return the current MAC address following priority rules.

    Priority:
    1. If `getIPA` not empty -> use `getMAC`
    2. If `getWIP` not empty and getWFS = 2 (Wi-Fi is connected) -> use `getMAC1`
    3. If `getEIP` not empty -> use `getMAC2`

    If the selected MAC is missing or empty, fall back to any available
    non-empty `getMAC` / `getMAC1` / `getMAC2`.
    """
    if not status:
        return None

    def is_not_empty_ip(key: str) -> bool:
        return not is_empty_ip(status.get(key))

    # Priority selection for MAC address:
    # 1. If getIPA (primary IP) is set and not empty, use getMAC (primary MAC)
    if is_not_empty_ip("getIPA"):
        mac_val = status.get("getMAC")
        if mac_val is not None and str(mac_val).strip() != "":
            return str(mac_val)

    # 2. If getWIP (Wi-Fi IP) is set and not empty, only use getMAC1 (Wi-Fi MAC)
    #    if and only if getWFS == 2 (Wi-Fi is connected).
    #    This prevents returning a Wi-Fi MAC address when the device is not actually
    #    connected to a Wi-Fi network, which avoids confusion and ensures that only
    #    active/connected MAC addresses are reported.
    if is_not_empty_ip("getWIP"):
        wfs_val = status.get("getWFS")
        # getWFS meaning:
        #   2 = Wi-Fi connected
        #   1 = Wi-Fi connecting
        #   0 = Wi-Fi not connected
        if wfs_val is not None:
            try:
                wfs_int = int(wfs_val)
            except ValueError, TypeError:
                wfs_int = None
        else:
            wfs_int = None
        if wfs_int == 2:
            # Only return the Wi-Fi MAC if Wi-Fi is confirmed to be connected
            mac_val = status.get("getMAC1")
            if mac_val is not None and str(mac_val).strip() != "":
                return str(mac_val)
        # If Wi-Fi is not connected, skip getMAC1 and continue to next fallback

    # 3. If getEIP (Ethernet IP) is set and not empty, use getMAC2 (Ethernet MAC)
    if is_not_empty_ip("getEIP"):
        mac_val = status.get("getMAC2")
        if mac_val is not None and str(mac_val).strip() != "":
            return str(mac_val)

    # No fallback: only return a MAC if it matches the priority rules above
    return None


def get_sensor_avo_value(value: Any) -> float | None:
    """Extract numeric flow value from strings like '1655mL' -> 1.655 (L).

    The getAVO sensor returns flow values in the format '1655mL', '0mL', etc.
    This function extracts the numeric value, converts from mL to L, and returns it as a float.

    Args:
        value: The raw sensor value (e.g., '1655mL', '0mL')

    Returns:
        Numeric flow value in L (converted from mL), or None if extraction fails
    """
    # Return None for None input
    if value is None:
        return None

    # If already numeric, convert from mL to L
    if isinstance(value, int | float):
        return float(value) / 1000

    # Only process string values
    if not isinstance(value, str):
        return None

    # Pattern to match values like '1655mL', '0mL', etc.
    # Extract the numeric part before 'mL'
    match = re.match(r"^(\d+)mL$", value)
    if match:
        try:
            flow_ml = int(match.group(1))
            flow_l = flow_ml / 1000  # Convert mL to L
            _LOGGER.debug("Extracted flow value from '%s' to %.3f L", value, flow_l)
        except ValueError, TypeError:
            return None
        else:
            return flow_l

    # If pattern doesn't match, try to extract any number at the start and convert
    match = re.match(r"^(\d+)", value)
    if match:
        try:
            flow_ml = int(match.group(1))
            return flow_ml / 1000  # Convert mL to L
        except ValueError, TypeError:
            return None

    return None


def get_sensor_vol_value(value: str | float) -> str | int | float | None:
    """Clean sensor value by removing prefixes like 'Vol[L]6530' -> '6530'.

    Some devices send values with prefixes that include the parameter name
    and unit in brackets, e.g., 'Vol[L]6530', 'Temp[C]25', etc.
    This function extracts the numeric value from such strings.

    Examples:
        >>> get_sensor_vol_value("")
        None
        >>> get_sensor_vol_value(6530)
        6530
        >>> get_sensor_vol_value("Vol[L]6530")
        '6530'

    Args:
        value: The raw sensor value

    Returns:
        Cleaned value with prefix removed if applicable, or None for empty string
    """
    # Only process string values
    if not isinstance(value, str):
        return value

    # Return None for empty string
    if value.strip() == "":
        return None

    # Pattern to match values like 'Vol[L]6530', 'Temp[C]25', etc.
    # Format: word characters, optional brackets with content, then the actual value
    match = re.match(r"^[A-Za-z]+\[[^\]]+\](.+)$", value)
    if match:
        cleaned = match.group(1).strip()
        _LOGGER.debug("Cleaned sensor value from '%s' to '%s'", value, cleaned)
        return cleaned

    return value


def get_sensor_lng_value(value: str | float) -> str | int | float | None:
    """Extract the leading integer from a getLNG value.

    Some devices append a human-readable annotation to the numeric value,
    e.g. "0 (0=Deutsch 1=English)" instead of plain "0".
    This function returns only the leading integer token so it can be matched
    against the translation state map.

    Examples:
        >>> get_sensor_lng_value("0 (0=Deutsch 1=English)")
        '0'
        >>> get_sensor_lng_value("1")
        '1'
        >>> get_sensor_lng_value(0)
        0

    Args:
        value: The raw getLNG sensor value

    Returns:
        Leading integer token as string, original value if no annotation present,
        or None for empty string.
    """
    if not isinstance(value, str):
        return value

    if value.strip() == "":
        return None

    token = value.split(maxsplit=1)[0]
    try:
        int(token)
    except ValueError:
        return value
    else:
        return token


def get_sensor_net_value(value: Any) -> float | None:
    """Parse mains voltage (getNET) supporting three formats.

    Formats supported:
    - Safe-T+ format:   "ADC:950 6,16V" -> extract "6,16" and parse comma as decimal -> 6.16
    - Safe-Tech+ format: "11,86"         -> parse comma as decimal -> 11.86
    - Trio DFR/LS format: "363"          -> value in 1/100 V, divide by 100 -> 3.63

    Returns the voltage as float rounded to 2 decimals, or None on failure.
    """
    if value is None:
        return None

    # If already numeric, assume it's in 1/100 V (int) and divide
    if isinstance(value, (int | float)):
        try:
            return round(float(value) / 100.0, 2)
        except TypeError, ValueError:
            return None

    if not isinstance(value, str):
        return None

    s = value.strip()
    if s == "":
        return None

    # Safe-T+ format: "ADC:950 6,16V" — extract the token that ends with 'V'
    if "ADC:" in s:
        for token in s.split():
            if token.upper().endswith("V"):
                raw = token[:-1]  # strip trailing 'V'
                try:
                    return round(float(raw.replace(",", ".")), 2)
                except ValueError, TypeError:
                    return None
        return None

    # Safe-Tech+ format with comma decimal, e.g. "11,86"
    if "," in s:
        try:
            return round(float(s.replace(",", ".")), 2)
        except ValueError, TypeError:
            return None

    # Digits-only Trio DFR/LS format "363" -> divide by 100
    if s.isdigit():
        try:
            return round(int(s) / 100.0, 2)
        except ValueError, TypeError:
            return None

    return None


def host_has_port(host: object) -> bool:
    """Return True if *host* ends with an explicit port, e.g. "192.168.1.10:5333".

    A plain IPv6 address such as "fe80::1" is not a host with port, although it ends
    with ":<digits>". Used by `is_valid_host` and to tell the user specifically that
    the port must be left out (the local API always uses its fixed port).
    """
    if not isinstance(host, str):
        return False
    try:
        ipaddress.ip_address(host.strip())
    except ValueError:
        pass
    else:
        return False
    return bool(re.match(r"^.+:\d+$", host.strip()))


def is_valid_host(host: str) -> bool:
    """Return True if *host* is a valid IPv4, IPv6 or hostname (no port).

    - Accepts IPv4 and IPv6 addresses using the stdlib ipaddress module
      (checked first, so an IPv6 literal such as ``fe80::1`` is not mistaken
      for ``host:port``)
    - Rejects explicit host:port strings
    - Allows DNS hostnames that meet length and label rules

    This function intentionally returns a boolean so callers can handle
    error reporting / translation to Home Assistant errors as appropriate.
    """
    if not isinstance(host, str) or not host.strip():
        return False

    # Reject surrounding whitespace
    if re.search(r"\s", host):
        return False

    # Try IP address (IPv4/IPv6) first: "fe80::1" would otherwise match the
    # host:port pattern below.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return True

    # Reject explicit host:port
    if host_has_port(host):
        return False

    # Hostname validation: length and label rules
    hostname_pattern = r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
    return bool(re.match(hostname_pattern, host))


def get_sensor_bat_value(value: Any) -> float | None:
    """Parse battery voltage supporting two formats.

    Formats supported:
    - Safe-T+ format: "6,11 4,38 3,90" -> take first token and parse comma as decimal
    - Safe-Tech+ format: "9,36" -> take as is and parse comma as decimal
    - Trio DFR/LS format: "363" -> value in 1/100 V, so divide by 100 -> 3.63

    Returns the voltage as float rounded to 2 decimals, or None on failure.
    """
    if value is None:
        return None

    # If already numeric, assume it's in 1/100 V (int) and divide
    if isinstance(value, (int | float)):
        try:
            return round(float(value) / 100.0, 2)
        except TypeError, ValueError:
            return None

    if not isinstance(value, str):
        return None

    s = value.strip()
    if s == "":
        return None

    # If space-separated Safe-T+ format, take firstech token
    if " " in s:
        first = s.split()[0]
        try:
            return round(float(first.replace(",", ".")), 2)
        except ValueError, TypeError:
            return None

    # Single-token Safe-Tech+ format with comma decimal, e.g. "9,36"
    if "," in s:
        try:
            return round(float(s.replace(",", ".")), 2)
        except ValueError, TypeError:
            return None

    # Digits-only Trio DFR/LS format "363" -> divide by 100
    if s.isdigit():
        try:
            return round(int(s) / 100.0, 2)
        except ValueError, TypeError:
            return None

    # No other variants supported. Return None.
    return None


def get_sensor_rtm_value(status: dict[str, Any]) -> str | None:
    """Return regeneration time as HH:MM string or None.

    Handles two device representations:
    - Separate hour (`getRTH`) and minutes (`getRTM`) numeric values.
    - Combined string in `getRTM` containing an HH:MM value.

    Returns a zero-padded "HH:MM" string when valid, otherwise None.
    """
    if not status:
        return None

    rth = status.get("getRTH")
    rtm = status.get("getRTM")

    if rtm is None or rtm == "":
        return None

    # Case A:Combined representation: getRTH missing/empty and getRTM contains HH:MM
    if rth is None or rth == "":
        if isinstance(rtm, str):
            m_match = re.match(r"\s*(\d{2}):(\d{2})\s*$", rtm)
            if not m_match:
                return None
            try:
                hh = int(m_match.group(1))
                mm = int(m_match.group(2))
                # Strict validation: hours 0-23, minutes 0-59
                if 0 <= hh <= 23 and 0 <= mm <= 59:
                    return f"{hh:02d}:{mm:02d}"
            except (ValueError, IndexError, AttributeError) as err:
                _LOGGER.debug("Failed to parse time from match: %s", err)
                return None
        return None

    # Case B: Separate numeric values
    try:
        h = int(float(rth))
        m = int(float(rtm))
        # Strict validation: hours 0-23, minutes 0-59
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    except (ValueError, TypeError, OverflowError) as err:
        _LOGGER.debug("Failed to parse regeneration time from separate values: %s", err)
        return None

    return None


def is_device_offline(dst: Any) -> bool:
    """Return True if the cloud device state means offline.

    dst="0" never online, dst="1" offline (2 = online, 3 = standby).

    Args:
        dst: The ``dst`` value of a status response

    Returns:
        True if the device is not reachable via the cloud
    """
    return str(dst if dst is not None else "").strip() in ("0", "1")


def get_sensor_iwh_value(status: dict[str, Any]) -> int | float | None:
    """Compute or return incoming water hardness (getIWH).

    Rules:
    1. If `getIWH` exists and is numeric, return it (int if whole).
    2. If `getIWH` missing/empty but `getCND` exists and is numeric,
       default `getWHU` to 0 when missing and compute `getIWH = getCND / 33`.
    3. Return None when values are missing or unparseable.
    """
    if not status:
        return None

    raw_iwh = status.get("getIWH")
    raw_whu = status.get("getWHU")
    # Only accept an explicit getIWH when WHU is also present (unit known)
    if raw_iwh is not None and raw_iwh != "" and raw_whu is not None and raw_whu != "":
        try:
            val = float(raw_iwh)
            # Persist normalized numeric getiwh back into status
            with contextlib.suppress(Exception):
                status["getIWH"] = int(val) if val.is_integer() else val
            # Return int when it's an exact whole number
            return int(val) if val.is_integer() else val
        except ValueError, TypeError:
            # Fall through to fallback derivation
            pass

    # Fallback: derive from getCND when available
    raw_cnd = status.get("getCND")
    if raw_cnd is None or raw_cnd == "":
        return None
    try:
        cnd = float(raw_cnd)
    except ValueError, TypeError:
        return None

    # Normalize/ensure getWHU exists; default to 0 when missing or invalid
    raw_whu = status.get("getWHU")
    try:
        whu = int(float(raw_whu)) if (raw_whu is not None and raw_whu != "") else 0
    except ValueError, TypeError, OverflowError:
        whu = 0
    with contextlib.suppress(Exception):
        status["getWHU"] = whu

    # Compute and persist getIWH
    # Calculation notes:
    # - 1 °dH is equivalent to approximately 30-35 µS/cm per scientific articles.
    # - However, the more precise standard value for clean, unpolluted fresh water appears to be 1 °dH = 33 µS/cm.
    iwh = cnd / 33.0
    iwh_out = int(iwh) if iwh.is_integer() else iwh
    with contextlib.suppress(Exception):
        status["getIWH"] = iwh_out
    return iwh_out


def set_sensor_rtm_value(status: dict[str, Any], option: str) -> list[tuple[str, Any]]:
    """Build set commands for regeneration time selection.

    Given the current `status` and a chosen `option` string in "HH:MM" format,
    return a list of (set_key, value) tuples that should be called on the API.

    If the device uses the combined representation (no `getRTH` and `getRTM` is
    a HH:MM string), a single `setRTM` with the HH:MM string is returned.
    Otherwise, returns two commands: `setRTH` (hour int) and `setRTM` (minute int).
    """
    commands: list[tuple[str, Any]] = []
    if not option or not isinstance(option, str):
        return commands

    # Determine combined-mode
    combined_mode = False
    if status is not None:
        raw_rth = status.get("getRTH")
        raw_rtm = status.get("getRTM")
        if (
            (raw_rth is None or raw_rth == "")
            and isinstance(raw_rtm, str)
            and ":" in raw_rtm
        ):
            combined_mode = True

    if combined_mode:
        commands.append(("setRTM", option))
        return commands

    # Parse HH:MM into integers
    try:
        parts = option.split(":")
        h = int(parts[0])
        m = int(parts[1])
    except (ValueError, IndexError, AttributeError) as err:
        _LOGGER.debug("Failed to parse time option '%s': %s", option, err)
        return commands

    commands.append(("setRTH", h))
    commands.append(("setRTM", m))
    return commands


def get_sensor_ab_value(status: dict[str, Any]) -> bool | None:
    """Parse `getAB` value from device status and return closed state as bool.

    Returns:
        - True if valve is closed
        - False if valve is open
        - None if unknown/unparseable

    The value stored under getAB may be a plain raw value from the API
    (string, int, bool). The device itself signals a pending change via the
    "s" attribute in the XML response, which the ResponseParser already
    writes as the current value.

    Devices may report the raw value in multiple formats:
    - Numeric: 1 (open), 2 (closed) - Used by older Safe-T devices
    - Boolean strings: "true" (closed), "false" (open) - Used by newer Trio devices

    The numeric mapping (1=open, 2=closed) appears counterintuitive but
    matches the SYR device firmware convention.
    """
    if not status:
        return None

    val = status.get("getAB")
    if val is None or val == "":
        return None

    return _parse_ab_raw(val)


def _parse_ab_raw(val: Any) -> bool | None:
    """Parse a single raw getAB value (string/int/bool) to bool | None.

    Returns True (closed), False (open), or None (unknown).
    """
    # Boolean values (native JSON booleans)
    if isinstance(val, bool):
        # In JSON API boolean True means closed, False means open
        return bool(val)

    # Numeric values (int/float or digit strings)
    try:
        if isinstance(val, (int | float)):
            # Safe-T: Syr seems to use 1 for open and 2 for closed, but we want True=closed, False=open
            ival = int(float(val))
            if ival == 2:
                return True
            if ival == 1:
                return False
            return None
        if isinstance(val, str):
            # Trio DFR/LS and other new devices: Normalize string and check for boolean-like values
            s = val.strip().lower()
            # Boolean-like strings
            if s in ("true", "false"):
                return s == "true"
            # Numeric string fallback
            if s.isdigit():
                ival = int(s)
                if ival == 2:
                    return True
                if ival == 1:
                    return False
    except (ValueError, TypeError, AttributeError, OverflowError) as err:
        _LOGGER.debug("Failed to parse getAB value: %s", err)
        return None

    return None


def get_sensor_ala_map(model: SyrConnectModel, raw_code: Any) -> tuple[str | None, str]:
    """Map raw getALA alarm code to internal translation key.

    Args:
        model: Detected model of the device (selects the alarm code family).
        raw_code: Raw code value from the API (e.g. "FF", "A5", "0").

    Returns:
        Internal translation key (e.g. "no_alarm", "alarm_low_salt") or None if unknown.
    """
    if raw_code is None:
        return (None, "")

    # Normalize code and prepare uppercase form for mapping lookups
    code = str(raw_code)
    code_upper = code.strip().upper()

    # Model-specific families take precedence; every other model (including unknown ones) uses the generic codes.
    profile = model.device_profile
    codes = (
        profile.ala_codes
        if profile is not None and profile.ala_codes is not None
        else _SYR_CONNECT_SENSOR_ALA_CODES_GENERIC
    )

    mapped = codes.get(code_upper)
    return (mapped, code) if mapped is not None else (None, code)


def get_sensor_not_map(model: SyrConnectModel, raw_code: Any) -> tuple[str | None, str]:
    """Map raw getNOT notification code to internal translation key.

    Args:
        model: Detected model of the device (unused but kept for signature parity)
        raw_code: Raw code value from the API (e.g. "01", "FF")

    Returns:
        (mapped_key, raw_code) where mapped_key is internal translation key or None
    """
    # Accept None
    if raw_code is None:
        return (None, "")

    code = str(raw_code)
    code_upper = code.strip().upper()
    mapped = _SYR_CONNECT_SENSOR_NOT_CODES_GENERIC.get(code_upper)
    return (mapped, code) if mapped is not None else (None, code)


def get_sensor_wrn_map(model: SyrConnectModel, raw_code: Any) -> tuple[str | None, str]:
    """Map raw getWRN warning code to internal translation key.

    Args:
        model: Detected model of the device (unused but kept for signature parity)
        raw_code: Raw code value from the API (e.g. "01", "FF")

    Returns:
        (mapped_key, raw_code) where mapped_key is internal translation key or None
    """
    # Accept None
    if raw_code is None:
        return (None, "")

    code = str(raw_code)
    code_upper = code.strip().upper()
    mapped = _SYR_CONNECT_SENSOR_WRN_CODES_GENERIC.get(code_upper)
    return (mapped, code) if mapped is not None else (None, code)


def build_set_ab_command(
    status: dict[str, Any], closed: bool
) -> tuple[str, Any] | None:
    """Build the appropriate (`setAB`, value) command for desired closed state.

    This function mirrors the device's own format for `getAB` when sending `setAB`:
    - Native bool (`True`/`False`) or boolean strings ("true"/"false") → "true" (closed) / "false" (open)
    - Native integer or numeric string ("1"/"2") → numeric `1` (open) / `2` (closed)
    - Unknown or absent → `None` (error is logged; caller must not send the command)

    Using the device's native format prevents potential parsing errors or
    firmware issues when the device receives commands in an unexpected format.

    Returns a tuple (set_key, value), or None when the format is unrecognised.
    """
    raw = None
    if status:
        raw = status.get("getAB")

    # Native bool (JSON API devices like SafeTech/Trio) → boolean string
    # Must be checked before int because bool is a subclass of int in Python.
    if isinstance(raw, bool):
        return ("setAB", "true" if closed else "false")

    # Boolean-like strings ("true"/"false") → boolean string
    if isinstance(raw, str) and raw.strip().lower() in ("true", "false"):
        return ("setAB", "true" if closed else "false")

    # Native integer (JSON API devices that report getAB as int 1/2) → numeric
    if isinstance(raw, int | float):
        return ("setAB", 2 if closed else 1)

    # Numeric string ("1"/"2") → numeric (XML API and some JSON API devices)
    if isinstance(raw, str) and raw.strip().isdigit():
        return ("setAB", 2 if closed else 1)

    # Unknown format — this should not happen with known device firmware.
    # Log an error and return None so the caller knows not to send a command.
    _LOGGER.error(
        "build_set_ab_command: unexpected getAB format %r (type %s); "
        "command will not be sent. Please report this issue.",
        raw,
        type(raw).__name__,
    )
    return None


def get_api_locale(language: str | None, country: str | None) -> str:
    """Build the locale sent to the SYR Connect cloud from the Home Assistant settings.

    Takes `hass.config.language` (e.g. `de`, `en-GB`, `zh-Hans`) and `hass.config.country`
    (e.g. `DE`). A region in the language wins; otherwise the country is used, so `de` + `AT`
    gives `de-AT`. Scripts such as `Hans` are not regions and are dropped.

    HA always sets a language (default `en`), but the country is optional. A missing region
    becomes `US`, matching the app, which always sends a full locale.

    Returns:
        A full locale like `de-DE`, `de-US` (no country) or `en-US` (no language).
    """
    parts = (language or "en").replace("_", "-").split("-")
    lang = parts[0].lower()
    region = next((p.upper() for p in parts[1:] if len(p) == 2 and p.isalpha()), None)
    if region is None:
        region = country.upper() if country else "US"
    return f"{lang}-{region}"


def mask_login_password(payload: str) -> str:
    """Redact the password in a login payload so the payload can be logged.

    The login payload carries the credentials as `<usr n="<username>" v="<password>" />`;
    only the `v` value of `<usr>` is replaced with `***`. The payload is built by
    `PayloadBuilder.build_login_payload` with ElementTree, which escapes `"` and `>`
    inside attribute values, so the value always ends at the next `"`. Non-string and
    empty payloads are returned unchanged.
    """
    if not isinstance(payload, str) or payload == "":
        return payload
    # Group 1 keeps `<usr ... v="`; `\s` keeps `v` from matching the end of a longer name.
    return re.sub(r'(<usr\b[^>]*?\sv\s*=\s*")[^"]*', r"\1***", payload)


def mask_ug_value(payload: str) -> str:
    """Redact `ug` attribute values in an XML payload.

    Replaces values like `ug="..."` with `ug="***"` (case-insensitive)
    so session tokens are not leaked in logs or diagnostics.

    The payload is edited as text, not parsed, and `ug="..."` is masked anywhere in it: diagnostics
    may pass truncated or malformed XML, server responses may contain a raw `>` inside attribute
    values, and error messages may quote the token outside any tag. An unterminated value is masked
    up to the end of the string. Non-string and empty payloads are returned unchanged.
    """
    if not isinstance(payload, str) or payload == "":
        return payload
    try:
        # The lookbehind keeps `ug` from matching inside longer names such as `xug` or `a:ug`.
        return re.sub(r'(?i)(?<![\w:.-])(ug\s*=\s*")[^"]*', r"\1***", payload)
    except re.error:
        return payload
