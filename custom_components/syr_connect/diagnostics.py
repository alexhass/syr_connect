"""Diagnostics support for SYR Connect."""

import asyncio
from collections.abc import Coroutine
from datetime import datetime
import ipaddress
import logging
import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .aiosyrconnect import (
    SyrConnectApiDevice,
    SyrConnectConnectionError,
    SyrConnectHTTPError,
    SyrConnectJsonAPI,
    SyrConnectStatus,
    SyrConnectXmlAPI,
    is_empty_ip,
    mask_ug_value,
)
from .const import API_TYPE_JSON, API_TYPE_XML, CONF_API_TYPE, CONF_MODEL, CONF_SERVICE
from .coordinator import SyrConnectConfigEntry, SyrConnectDataUpdateCoordinator
from .data import SyrConnectDevice
from .helpers.device import get_device_model
from .helpers.integration import build_user_agent, get_integration_version
from .models import SyrConnectModel
from .sensor import sensor_keys_for_status

_LOGGER = logging.getLogger(__name__)

# Maximum number of requests the diagnostics send at the same time (cloud status XML,
# local /get/all), so that many devices do not flood the cloud or the LAN
_SYR_CONNECT_DIAGNOSTICS_CONCURRENT_API_CALLS = 5

# Keys whose values are removed completely: in dicts by `_redact_obj` and
# `async_redact_data`, in XML strings by `_redact_xml`.
# Some keys are handled specially and MUST NOT be fully redacted, because the
# unmasked part is needed to analyze problems (vendor, model, production batch):
# - `getMAC`/`getMAC1`/`getMAC2` are masked by `mask_mac_value` (vendor kept),
# - `getSRN` (device serial) is masked by `mask_srn_value` (prefix kept).
_SYR_CONNECT_DIAGNOSTICS_TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "session_data",
    "getCNO",  # Code number printed on the device label; registers the device to an account
    "getDGW",  # Default gateway
    "getEGW",  # Ethernet gateway
    "getEIP",  # Ethernet IP address
    "getIPA",  # IP address
    "getWFC",  # Wi-Fi SSID
    "getWGW",  # Wi-Fi gateway
    "getWIP",  # Wi-Fi IP address
}

# Address and phone attributes of a project in the device list XML -> their placeholder
_SYR_CONNECT_DIAGNOSTICS_PROJECT_PLACEHOLDERS = {
    "adr": "Street+1",
    "cph": "0123456789",
    "fax": "0123456789",
    "pho": "0123456789",
    "rsd": "City",
    "url": "example.com",
    "zip": "12345",
}


def _local_json_model(device: SyrConnectDevice) -> SyrConnectModel | None:
    """Return the device's model if it has a local JSON API, else None.

    The model is detected from the device status; its signature in the library gives
    the local path of the JSON API (`base_path`). Adding a `base_path` to a model is
    therefore enough to include its local `/get/all` data in diagnostics, even when the
    device is set up via the cloud (XML) API.
    """
    model = get_device_model(device)
    return model if model.base_path else None


def mask_mac_value(val: str, last_char_replace: str | None = None) -> str:
    """Mask a MAC address while preserving the vendor (first three octets).

    If the input does not parse as six octets, return the original string.
    If `last_char_replace` is provided, it replaces the final character of the
    masked string (used for `getMAC2`), so two masked addresses of one device differ:
    - getMAC1: "AA:BB:CC:DD:EE:FF" -> "AA:BB:CC:XX:XX:XX"
    - getMAC2: "AA:BB:CC:DD:EE:FF" -> "AA:BB:CC:XX:XX:XY"
    """
    if not isinstance(val, str) or val.strip() == "":
        return val
    s = val.strip()
    pairs = re.findall(r"[0-9A-Fa-f]{2}", s)
    if len(pairs) < 6:
        return s
    sep = ":" if ":" in s else "-" if "-" in s else ":"
    preserved = [p.upper() for p in pairs[:3]]
    masked_tail = ["XX"] * (len(pairs) - 3)
    result = sep.join(preserved + masked_tail)
    if last_char_replace is not None:
        result = result[:-1] + last_char_replace
    return result


def mask_srn_value(val: Any) -> Any:
    """Mask a SRN value when it matches the expected serial format.

    Expected format: 3 digits, 3 uppercase letters, 5 digits — e.g. '206AAA12345'.
    When matched, replace the trailing 5 digits with the constant '12345'.
    """
    if not isinstance(val, str):
        return val
    m = re.match(r"^(\d{3}[A-Z]{3})(\d{5})$", val)
    return f"{m.group(1)}12345" if m else val


def _redact_xml(xml: str) -> str:
    """Redact sensitive keys inside an XML string using patterns.

    This will replace attribute values, <c n="..." v="..."/> entries,
    and generic IP/MAC/email patterns for any key listed in `_SYR_CONNECT_DIAGNOSTICS_TO_REDACT`.

    Works on the text, not on a parsed tree: the responses may be truncated or
    malformed, and the same function also cleans plain strings elsewhere in the
    diagnostics (see `_redact_obj`).
    """
    if not isinstance(xml, str) or not xml:
        return ""

    cleaned = xml
    # Mask session token `ug` attributes early to avoid leaking tokens
    cleaned = mask_ug_value(cleaned)

    # getMAC2 ends with "Y" as in `_mask_sensitive`, so that it differs from getMAC1
    cleaned = re.sub(
        r'(<c\b[^>]*\bn\s*=\s*"getMAC2"[^>]*\bv\s*=\s*")([^\"]*)(")',
        lambda m: m.group(1) + mask_mac_value(m.group(2), "Y") + m.group(3),
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r'(\bgetMAC2\s*=\s*")([^\"]*)(")',
        lambda m: m.group(1) + mask_mac_value(m.group(2), "Y") + m.group(3),
        cleaned,
        flags=re.IGNORECASE,
    )

    # Replace standalone MAC addresses in text using the shared helper
    cleaned = re.sub(
        r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
        lambda m: mask_mac_value(m.group(0), None),
        cleaned,
    )

    # Mask SRN values inside XML attribute forms and <c n="getSRN" v="..."/> entries
    cleaned = re.sub(
        r'(<c\b[^>]*\bn\s*=\s*"getSRN"[^>]*\bv\s*=\s*")([^\"]*)(")',
        lambda m: m.group(1) + mask_srn_value(m.group(2)) + m.group(3),
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r'(\bgetSRN\s*=\s*")([^\"]*)(")',
        lambda m: m.group(1) + mask_srn_value(m.group(2)) + m.group(3),
        cleaned,
        flags=re.IGNORECASE,
    )

    # The same serial number as attribute of a device: <d sn="..." />
    cleaned = re.sub(
        r'(\bsn\s*=\s*")([^\"]*)(")',
        lambda m: m.group(1) + mask_srn_value(m.group(2)) + m.group(3),
        cleaned,
    )

    # For each redact key, replace attribute values like key="..."
    for key in _SYR_CONNECT_DIAGNOSTICS_TO_REDACT:
        if not key:
            continue
        key_str = str(key)
        placeholder = f"***REDACTED_{re.sub(r'[^A-Za-z0-9]', '_', key_str).upper()}***"

        # Attributes like mac="..."
        cleaned = re.sub(
            rf'({re.escape(key_str)}\s*=\s*")([^"]*)(")',
            rf"\1{placeholder}\3",
            cleaned,
            flags=re.IGNORECASE,
        )

        # <c n="getMAC" v="..." /> or similar: redact v when n matches key
        cleaned = re.sub(
            rf'(<c\b[^>]*\bn\s*=\s*"{re.escape(key_str)}"[^>]*\bv\s*=\s*")([^"]*)(")',
            rf"\1{placeholder}\3",
            cleaned,
            flags=re.IGNORECASE,
        )

        # Simple key:value or key=val patterns
        cleaned = re.sub(
            rf'({re.escape(key_str)}\s*[:=]\s*)([^\s><"\']+)',
            rf"\1{placeholder}",
            cleaned,
            flags=re.IGNORECASE,
        )

    # Generic redactions
    cleaned = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "***REDACTED_IP***", cleaned)

    # Replace standalone MAC addresses in text using the shared helper
    cleaned = re.sub(
        r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
        lambda m: mask_mac_value(m.group(0), None),
        cleaned,
    )

    cleaned = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "***REDACTED_USERNAME***", cleaned)

    # Remove any whitespace (including newlines) between XML tags: '>   <' -> '><'
    cleaned = re.sub(r">\s+<", "><", cleaned)
    return cleaned.strip()


def _redact_device_list_xml(xml: str) -> str:
    """Redact a device list XML and replace the personal attributes.

    - `pn="..."` -> `My+Project` (project name)
    - `com="..."` -> `Firstname+Lastname` (contact/owner name)
    - the address and phone numbers of the project
      (`_SYR_CONNECT_DIAGNOSTICS_PROJECT_PLACEHOLDERS`), unless they are empty

    All are free text the user entered in the app and often contain an address or
    family name. They are replaced by fixed placeholders instead of being removed,
    so the structure of the response stays recognizable.
    """
    cleaned = _redact_xml(xml)
    cleaned = re.sub(r'(\bpn\s*=\s*")([^"]*)(")', r"\1My+Project\3", cleaned)
    cleaned = re.sub(r'(\bcom\s*=\s*")([^"]*)(")', r"\1Firstname+Lastname\3", cleaned)
    for name, placeholder in _SYR_CONNECT_DIAGNOSTICS_PROJECT_PLACEHOLDERS.items():
        cleaned = re.sub(
            rf'(\b{name}\s*=\s*")([^"]+)(")', rf"\g<1>{placeholder}\3", cleaned
        )
    return cleaned


def _redact_json_payload(data: Any) -> Any:
    """Redact a parsed local JSON API payload for `raw_json`.

    Used for both sources of local data (local entries and cloud devices with local
    access). Unlike in the rest of the diagnostics, where `getSRN` is only masked
    (`mask_srn_value`), it is replaced completely in these raw payloads.
    """
    # Remove the values of all sensitive keys from the parsed payload
    redacted = async_redact_data(data, _SYR_CONNECT_DIAGNOSTICS_TO_REDACT)
    # Ensure SRN is fully redacted for raw_json payloads
    if isinstance(redacted, dict) and "getSRN" in redacted:
        redacted["getSRN"] = "**REDACTED**"
    return redacted


async def _async_xml_api_with_session(
    coordinator: SyrConnectDataUpdateCoordinator,
) -> SyrConnectXmlAPI | None:
    """Return the XML API client of the coordinator with a valid session, or None.

    None without a client, if the login fails or if the account has no projects.
    """
    api = getattr(coordinator, "api", None)
    if not api:
        return None
    # Ensure we have a valid session for read-only calls
    try:
        if not api.is_session_valid():
            await api.login()
    except Exception:
        # Don't fail diagnostics if login fails
        _LOGGER.debug("Diagnostics: XML API login failed", exc_info=True)
        return None
    if not api.projects:
        return None
    xml_api: SyrConnectXmlAPI = api
    return xml_api


async def _async_raw_xml(
    semaphore: asyncio.Semaphore, request: Coroutine[Any, Any, str], name: str
) -> str:
    """Return the raw XML answer of a request; empty if the request fails."""
    try:
        async with semaphore:
            return await request
    except Exception:
        _LOGGER.debug("Diagnostics: XML request %s failed", name, exc_info=True)
        return ""


async def _async_project_raw_xml(
    xml_api: SyrConnectXmlAPI, semaphore: asyncio.Semaphore, pid: str
) -> dict[str, Any]:
    """Return the redacted raw XML of a project: its device list and device statuses.

    A failed request only leaves an empty response for this project or device.

    Returns:
        `{"device_list": xml, "devices": {dclg: status_xml}}`
    """
    project_raw: dict[str, Any] = {"device_list": "", "devices": {}}
    xml_resp = await _async_raw_xml(
        semaphore, xml_api.get_raw_device_list(pid), f"device list of {pid}"
    )
    project_raw["device_list"] = _redact_device_list_xml(xml_resp)

    # Parse devices (best-effort) from the original, unredacted response
    try:
        devices = xml_api.parse_device_list(xml_resp)
    except Exception:
        _LOGGER.debug(
            "Diagnostics: device list of project %s could not be parsed",
            pid,
            exc_info=True,
        )
        devices = []

    async def _fetch_status(device: SyrConnectApiDevice) -> tuple[str, str]:
        xml_status = await _async_raw_xml(
            semaphore,
            xml_api.get_raw_device_status(device["id"]),
            f"status of {device['id']}",
        )
        # Keyed by the device collection, as the cloud addresses the device; the parser
        # takes only devices with one
        return device["dclg"], _redact_xml(xml_status)

    # Fetch status for each device (limited concurrency by semaphore)
    status_tasks = [_fetch_status(device) for device in devices]
    project_raw["devices"] = dict(await asyncio.gather(*status_tasks))
    return project_raw


async def _collect_raw_xml(
    coordinator: SyrConnectDataUpdateCoordinator,
) -> dict[str, Any]:
    """Collect the redacted raw XML of all projects and their devices (XML API only).

    The responses are fetched fresh from the cloud instead of taken from the
    coordinator, which only keeps the parsed values: the raw XML shows exactly what
    the cloud sends, including attributes the parser ignores.

    Result: `{project_id: {"device_list": xml, "devices": {dclg: status_xml}}}`, `{}`
    without a usable session, or `{"error": ...}`. Uses limited concurrency to avoid
    excessive load on the cloud API.
    """
    try:
        xml_api = await _async_xml_api_with_session(coordinator)
        if xml_api is None:
            return {}
        semaphore = asyncio.Semaphore(_SYR_CONNECT_DIAGNOSTICS_CONCURRENT_API_CALLS)

        # Iterate all projects of the account (from the login response)
        projects_raw: dict[str, Any] = {}
        for project in xml_api.projects:
            pid = project.get("id")
            if pid:
                projects_raw[pid] = await _async_project_raw_xml(
                    xml_api, semaphore, pid
                )
    except Exception:
        # Never raise from diagnostics
        _LOGGER.debug("Diagnostics: failed to collect raw XML", exc_info=True)
        return {"error": "failed to collect raw xml for all projects"}
    else:
        return projects_raw


async def _collect_raw_json_local_entry(
    coordinator: SyrConnectDataUpdateCoordinator,
) -> dict[str, Any]:
    """Collect the redacted `/get/all` data of a local (JSON API) entry from its own API client.

    A local entry has exactly one device. Result: `{device_id: data}`; on failure an
    "error" entry is added instead.
    """
    raw_json: dict[str, Any] = {}
    try:
        api = getattr(coordinator, "api", None)
        if api and isinstance(api, SyrConnectJsonAPI):
            try:
                # Ensure we have a valid session
                if not api.is_session_valid():
                    await api.login()
            except Exception:
                # If login fails, still attempt to fetch once
                _LOGGER.debug("Diagnostics: JSON API login failed", exc_info=True)

            try:
                # Use public API methods to fetch device data so we don't
                # depend on a private implementation that may change.
                devices = await api.get_devices("local")
                if devices:
                    data = await api.get_device_status(str(devices[0].get("id")))
            except Exception:
                _LOGGER.debug(
                    "Diagnostics: failed to fetch JSON data from device", exc_info=True
                )
                devices = []
            if not devices:
                # Set error but don't overwrite the entire dict
                raw_json["error"] = "failed to fetch JSON data from device"
            else:
                # Use the first device ID from coordinator data as key, or "local_device"
                device_id = "local_device"
                if coordinator.data and coordinator.data.get("devices"):
                    device_id = coordinator.data["devices"][0].get("id", "local_device")
                raw_json[device_id] = _redact_json_payload(data)
    except Exception:
        # Set error but don't overwrite the entire dict
        _LOGGER.debug("Diagnostics: failed to collect raw JSON", exc_info=True)
        raw_json["error"] = "failed to collect raw json for JSON API"
    return raw_json


def _private_device_ip(status: SyrConnectStatus) -> str | None:
    """Return the IP of a device from its status if it is in the local network, else None.

    The IP is taken from Wi-Fi first, then Ethernet, then the generic IP address.
    The IP comes from the cloud; only devices in the local network are contacted. A
    wrong or manipulated cloud answer must not make Home Assistant send requests
    (including the ADM login) to an arbitrary public address, to Home Assistant itself
    (loopback) or to a link-local address, where no SYR device is reachable.
    """
    ip = status.get("getWIP") or status.get("getEIP") or status.get("getIPA")

    # No usable IP (missing, blank or the unspecified placeholder 0.0.0.0)
    if is_empty_ip(ip):
        return None
    try:
        address = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        return None
    if not address.is_private or address.is_loopback or address.is_link_local:
        return None
    return str(ip)


async def _async_local_login(json_api: SyrConnectJsonAPI, dev_id: str, ip: str) -> bool:
    """Log in to a local device if it needs it; False if the device is not reachable.

    A failed login of a reachable device is only logged: the data is fetched anyway.
    """
    try:
        if not json_api.is_session_valid():
            await json_api.login()
    except SyrConnectHTTPError:
        # The device answered, only without the login endpoint: fetch anyway
        _LOGGER.debug(
            "Diagnostics: local login to device %s failed", dev_id, exc_info=True
        )
    except SyrConnectConnectionError as err:
        # Not reachable (e.g. timeout, another network): /get/all would wait again
        _LOGGER.debug(
            "Diagnostics: device %s is not reachable at %s: %s", dev_id, ip, err
        )
        return False
    except Exception:
        # If login fails, still attempt to fetch once
        _LOGGER.debug(
            "Diagnostics: local login to device %s failed", dev_id, exc_info=True
        )
    return True


async def _fetch_local_device_json(
    session: Any,
    dev: SyrConnectDevice,
    model: SyrConnectModel,
    integration_version: str,
) -> tuple[str, Any]:
    """Fetch the redacted local `/get/all` data of a cloud device.

    Returns (device id, data), with None as data when the device has no usable
    private IP or the request fails.
    """
    dev_id = dev["id"]
    ip = _private_device_ip(dev.get("status") or {})
    if ip is None:
        return dev_id, None

    json_api = SyrConnectJsonAPI(
        session,
        host=ip,
        model=model,
        user_agent=build_user_agent(integration_version),
    )
    try:
        if not await _async_local_login(json_api, dev_id, ip):
            return dev_id, None

        try:
            # get_device_status() fetches /get/all and returns the parsed dict
            data = await json_api.get_device_status(dev_id)
        except Exception:
            _LOGGER.debug(
                "Diagnostics: local /get/all of device %s failed", dev_id, exc_info=True
            )
            return dev_id, None

        return dev_id, _redact_json_payload(data)
    except Exception:
        _LOGGER.debug(
            "Diagnostics: local data of device %s could not be collected",
            dev_id,
            exc_info=True,
        )
        return dev_id, None


async def _collect_raw_json_cloud_devices(
    hass: HomeAssistant,
    coordinator: SyrConnectDataUpdateCoordinator,
) -> dict[str, Any]:
    """Collect local `/get/all` data of cloud (XML API) devices whose model offers local access.

    Only models with a `base_path` are queried (see `_local_json_model`), at the
    device IP from the status. Result: `{device_id: data}` for the devices that
    answered, or `{"error": ...}`.
    """
    raw_json: dict[str, Any] = {}
    try:
        # Reuse the coordinator's HA-managed aiohttp session and its connectors
        session = getattr(coordinator, "_session", None)
        if session is None:
            return {"error": "no http session available on coordinator"}

        if coordinator and coordinator.data:
            devices = coordinator.data.get("devices", [])
            semaphore = asyncio.Semaphore(_SYR_CONNECT_DIAGNOSTICS_CONCURRENT_API_CALLS)
            integration_version = get_integration_version(hass)

            async def _wrap(
                dev: SyrConnectDevice, model: SyrConnectModel
            ) -> tuple[str, Any]:
                async with semaphore:
                    return await _fetch_local_device_json(
                        session, dev, model, integration_version
                    )

            tasks = [
                _wrap(d, model)
                for d in devices
                if isinstance(d, dict) and (model := _local_json_model(d)) is not None
            ]
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, Exception):
                        continue
                    if isinstance(res, tuple) and len(res) == 2:
                        did, payload = res
                        if payload is not None:
                            raw_json[did] = payload
    except Exception:
        _LOGGER.debug(
            "Diagnostics: failed to collect local JSON of cloud devices", exc_info=True
        )
        return {"error": "failed to collect raw json for devices"}
    return raw_json


def _device_summary(
    device: SyrConnectDevice, api_type: str, service: str | None
) -> dict[str, Any]:
    """Return the diagnostics summary of a coordinator device.

    Lists the detected model, versions and the keys that become visible sensors, so
    a missing entity can be told apart from a key the device does not report.
    The values are still unmasked here; masking happens afterwards for the whole result.
    """
    status = device.get("status", {})

    # Extract model information, with the names of the cloud service (`service_branding`)
    model_info = get_device_model(device)
    manufacturer, model_display = model_info.branded(service)

    # The sensors the integration creates for this status, with the same rules as the setup
    visible_keys = sensor_keys_for_status(status, model_info)

    device_info = {
        "id": device.get("id"),
        "name": device.get("name"),
        "available": device.get("available", True),
        "project_id": device.get("project_id"),
        "manufacturer": manufacturer,
        "model": model_display,
        # Local JSON API path of the model, None without local access
        "base_path": model_info.base_path,
        "sw_version": status.get("getVER"),
        "hw_version": status.get("getFIR"),
        "api_type": api_type,
        "status_count": len(visible_keys),
        "status_keys": sorted(visible_keys),
    }

    # Add XML API specific fields
    if api_type == API_TYPE_XML and device.get("dclg"):
        device_info["dclg"] = device.get("dclg")

    return device_info


def _mask_sensitive(obj: Any) -> Any:
    r"""Mask serial numbers and MAC addresses, keeping their recognizable parts.

    1) `getSRN`: If value matches `\d{3}[A-Z]{3}\d{5}`, replace trailing 5 digits with '12345'.
    2) `getMAC` / `getMAC1`: Replace the device part (last 3 octets) with 'XX'.
    3) `getMAC2`: Same masking, then replace final character with 'Y'.
    SRN-like strings in other keys (e.g. `id`) are masked as well.
    """
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            key = str(k)

            # Mask SRN value when the key is `getSRN` (case-insensitive)
            if key.lower() == "getsrn":
                obj[k] = mask_srn_value(v)
                continue

            # Mask MACs with custom rules using shared helper
            if isinstance(v, str) and key.lower() in ("getmac", "getmac1"):
                obj[k] = mask_mac_value(v, last_char_replace=None)
                continue
            if isinstance(v, str) and key.lower() == "getmac2":
                obj[k] = mask_mac_value(v, last_char_replace="Y")
                continue

            # Also mask SRN-like strings found in arbitrary keys (e.g. `id`)
            if isinstance(v, str):
                masked = mask_srn_value(v)
                if masked != v:
                    obj[k] = masked
                    continue

            # Recurse for nested structures
            obj[k] = _mask_sensitive(v)
        return obj
    if isinstance(obj, list):
        return [_mask_sensitive(i) for i in obj]
    return obj


def _redact_obj(obj: Any) -> Any:
    """Redact all `_SYR_CONNECT_DIAGNOSTICS_TO_REDACT` keys (case-insensitive) and sensitive values in strings.

    Values of matching keys become `***REDACTED_<KEY>***`; every other string is
    passed through `_redact_xml`, so IP and MAC addresses or e-mail addresses inside
    free text (e.g. a device name) are caught too. Returns a new object.
    """
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            # Preserve raw_xml unchanged: it was already redacted while it was collected
            # (including the project/contact names, which `_redact_xml` alone does not replace)
            if str(k) == "raw_xml":
                out[k] = v
                continue

            # If the dict key itself matches a redact key, replace value entirely
            if any(
                str(k).lower() == str(r).lower()
                for r in _SYR_CONNECT_DIAGNOSTICS_TO_REDACT
            ):
                out[k] = (
                    f"***REDACTED_{re.sub(r'[^A-Za-z0-9]', '_', str(k)).upper()}***"
                )
            else:
                out[k] = _redact_obj(v)
        return out

    if isinstance(obj, list):
        return [_redact_obj(i) for i in obj]

    if isinstance(obj, str):
        # Redact sensitive values inside strings (including raw XML)
        return _redact_xml(obj)

    return obj


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SyrConnectConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        Dictionary with diagnostic information
    """
    coordinator = entry.runtime_data

    devices_info: list[dict[str, Any]] = []
    projects_info: list[dict[str, Any]] = []

    last_success_time = getattr(coordinator, "last_update_success_time", None)

    diagnostics_data = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "options": dict(entry.options),
            "service": entry.data.get(CONF_SERVICE),
            # Model chosen at setup of a local entry, None for cloud entries
            "model": entry.data.get(CONF_MODEL),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_update_time": last_success_time.isoformat()
            if isinstance(last_success_time, datetime)
            else None,
        },
        "devices": devices_info,
        "projects": projects_info,
    }

    # Redact username in entry title if present, e.g. "SYR Connect (username)" ->
    # "SYR Connect (***REDACTED_USERNAME***)" to avoid leaking usernames in diagnostics.
    entry_obj = diagnostics_data.get("entry")
    if isinstance(entry_obj, dict):
        title_obj = entry_obj.get("title")
        if isinstance(title_obj, str):
            entry_obj["title"] = re.sub(
                r"\(([^)]+)\)", "(***REDACTED_USERNAME***)", title_obj
            )

    # Determine API type from config entry
    api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML)

    # Raw XML responses (redacted), only for the XML API; local entries have no cloud XML
    diagnostics_data["raw_xml"] = (
        await _collect_raw_xml(coordinator) if api_type == API_TYPE_XML else {}
    )

    # Raw local JSON data (redacted): from the entry's own client for JSON entries,
    # otherwise from cloud devices whose model offers local access
    if api_type == API_TYPE_JSON:
        diagnostics_data["raw_json"] = await _collect_raw_json_local_entry(coordinator)
    else:
        diagnostics_data["raw_json"] = await _collect_raw_json_cloud_devices(
            hass, coordinator
        )

    if coordinator.data:
        # Populate devices and projects BEFORE masking and redaction, so the steps
        # below cover them as well
        devices_info.extend(
            _device_summary(device, api_type, coordinator.data.get("service"))
            for device in coordinator.data.get("devices", [])
        )

        # The project name is user-defined and often an address or family name;
        # it is masked like `pn` in raw_xml above ("My+Project").
        projects_info.extend(
            {
                "id": project.get("id"),
                "name": "My Project" if project.get("name") else project.get("name"),
            }
            for project in coordinator.data.get("projects", [])
        )

        # 1) Mask serial numbers and MACs, keeping their recognizable parts (in place)
        diagnostics_data = _mask_sensitive(diagnostics_data)
        # 2) Redact all `_SYR_CONNECT_DIAGNOSTICS_TO_REDACT` keys (any letter case) and sensitive text in strings
        diagnostics_data = _redact_obj(diagnostics_data)

    # 3) Home Assistant's standard redaction. It runs even without coordinator data,
    # when steps 1 and 2 are skipped. Keys that match `_SYR_CONNECT_DIAGNOSTICS_TO_REDACT` exactly end up as
    # "**REDACTED**" (overwriting the placeholder of step 2); keys with a different
    # letter case keep the `***REDACTED_<KEY>***` placeholder of step 2.
    return async_redact_data(diagnostics_data, _SYR_CONNECT_DIAGNOSTICS_TO_REDACT)
