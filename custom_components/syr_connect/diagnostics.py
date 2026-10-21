"""Diagnostics support for SYR Connect."""

import asyncio
import contextlib
from datetime import datetime
import ipaddress
import logging
import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .api_json import SyrConnectJsonAPI
from .api_xml import SyrConnectXmlAPI
from .const import API_TYPE_JSON, API_TYPE_XML, CONF_API_TYPE
from .coordinator import SyrConnectDataUpdateCoordinator
from .data import SyrConnectDevice
from .helpers import mask_ug_value
from .models import detect_model
from .sensor import sensor_keys_for_status

_LOGGER = logging.getLogger(__name__)

# Maximum number of requests the diagnostics send at the same time (cloud status XML,
# local /get/all), so that many devices do not flood the cloud or the LAN
_SYR_CONNECT_DIAGNOSTICS_CONCURRENT_API_CALLS = 5

# Keys whose values are removed completely: in dicts by `_redact_obj` and
# `async_redact_data`, in XML strings by `_redact_xml`.
# Some keys are handled specially and MUST NOT be fully redacted, because the
# unmasked part is needed to analyse problems (vendor, model, production batch):
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


def _local_json_base_path(device: SyrConnectDevice) -> str | None:
    """Return the local JSON API base path of the device's model, or None without local access.

    The base path is not part of the coordinator's device dict; it comes from the model
    signature (`MODEL_SIGNATURES`) detected from the device status. Adding a `base_path`
    to a model is therefore enough to include its local `/get/all` data in diagnostics,
    even when the device is set up via the cloud (XML) API.
    """
    status = device.get("status")
    base_path = detect_model(status if isinstance(status, dict) else {}).get(
        "base_path"
    )
    return base_path if isinstance(base_path, str) and base_path else None


def mask_mac_value(val: str, last_char_replace: str | None = None) -> str:
    """Mask a MAC address while preserving the vendor (first three octets).

    If the input does not parse as six octets, return the original string.
    If `last_char_replace` is provided, replace the final hex character
    in the resulting masked string with that value (used for `getMAC2`).
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
        with contextlib.suppress(re.error):
            result = re.sub(r"([0-9A-F])$", last_char_replace, result)
    return result


def mask_srn_value(val: Any) -> Any:
    """Mask a SRN value when it matches the expected serial format.

    Expected format: 3 digits, 3 uppercase letters, 5 digits — e.g. '206AAA12345'.
    When matched, replace the trailing 5 digits with the constant '12345'.
    """
    if not isinstance(val, str):
        return val
    try:
        m = re.match(r"^(\d{3}[A-Z]{3})(\d{5})$", val)
    except re.error:
        return val
    return f"{m.group(1)}12345" if m else val


def _redact_xml(xml: str) -> str:
    """Redact sensitive keys inside an XML string using patterns.

    This will replace attribute values, <c n="..." v="..."/> entries,
    and generic IP/MAC/email patterns for any key listed in `_SYR_CONNECT_DIAGNOSTICS_TO_REDACT`.

    Works on the text, not on a parsed tree: the responses may be truncated or
    malformed, and the same function also cleans plain strings elsewhere in the
    diagnostics (see `_redact_obj`). Each step catches its own errors so that one
    failing pattern does not leave the rest of the string unredacted.
    """
    if not isinstance(xml, str) or not xml:
        return ""

    cleaned = xml
    # Mask session token `ug` attributes early to avoid leaking tokens
    with contextlib.suppress(Exception):
        cleaned = mask_ug_value(cleaned)

    # Replace standalone MAC addresses in text using the shared helper
    cleaned = re.sub(
        r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
        lambda m: mask_mac_value(m.group(0), None),
        cleaned,
    )

    # Mask SRN values inside XML attribute forms and <c n="getSRN" v="..."/> entries
    with contextlib.suppress(re.error, TypeError, ValueError):
        cleaned = re.sub(
            r'(<c\b[^>]*\bn\s*=\s*"getSRN"[^>]*\bv\s*=\s*")([^\"]*)(")',
            lambda m: m.group(1) + mask_srn_value(m.group(2)) + m.group(3),
            cleaned,
            flags=re.IGNORECASE,
        )

    with contextlib.suppress(re.error, TypeError, ValueError):
        cleaned = re.sub(
            r'(\bgetSRN\s*=\s*")([^\"]*)(")',
            lambda m: m.group(1) + mask_srn_value(m.group(2)) + m.group(3),
            cleaned,
            flags=re.IGNORECASE,
        )

    # For each redact key, replace attribute values like key="..."
    for key in _SYR_CONNECT_DIAGNOSTICS_TO_REDACT:
        if not key:
            continue
        key_str = str(key)
        placeholder = f"***REDACTED_{re.sub(r'[^A-Za-z0-9]', '_', key_str).upper()}***"

        # Attributes like mac="..."
        with contextlib.suppress(re.error, TypeError, ValueError):
            cleaned = re.sub(
                rf'({re.escape(key_str)}\s*=\s*")([^"]*)(")',
                rf"\1{placeholder}\3",
                cleaned,
                flags=re.IGNORECASE,
            )

        # <c n="getMAC" v="..." /> or similar: redact v when n matches key
        with contextlib.suppress(re.error, TypeError, ValueError):
            cleaned = re.sub(
                rf'(<c\b[^>]*\bn\s*=\s*"{re.escape(key_str)}"[^>]*\bv\s*=\s*")([^"]*)(")',
                rf"\1{placeholder}\3",
                cleaned,
                flags=re.IGNORECASE,
            )

        # Simple key:value or key=val patterns
        with contextlib.suppress(re.error, TypeError, ValueError):
            cleaned = re.sub(
                rf'({re.escape(key_str)}\s*[:=]\s*)([^\s><"\']+)',
                rf"\1{placeholder}",
                cleaned,
                flags=re.IGNORECASE,
            )

    # Generic redactions
    try:
        cleaned = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "***REDACTED_IP***", cleaned)

        # Replace standalone MAC addresses in text using the shared helper
        cleaned = re.sub(
            r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
            lambda m: mask_mac_value(m.group(0), None),
            cleaned,
        )

        cleaned = re.sub(
            r"[\w.+-]+@[\w-]+\.[\w.-]+", "***REDACTED_USERNAME***", cleaned
        )
    except re.error, TypeError, ValueError:
        pass

    # Remove any whitespace (including newlines) between XML tags: '>   <' -> '><'
    try:
        cleaned = re.sub(r">\s+<", "><", cleaned)
        cleaned = cleaned.strip()
    except re.error, TypeError, ValueError:
        pass

    return cleaned


def _redact_device_list_xml(xml: str) -> str:
    """Redact a device list XML and replace the personal attributes.

    - `pn="..."` -> `My+Project` (project name)
    - `com="..."` -> `Firstname+Lastname` (contact/owner name)

    Both are free text the user entered in the app and often contain an address or
    family name. They are replaced by fixed placeholders instead of being removed,
    so the structure of the response stays recognizable.
    """
    cleaned = _redact_xml(xml)
    # If a replacement fails, keep the redacted content as-is
    with contextlib.suppress(re.error, TypeError, ValueError):
        cleaned = re.sub(r'(\bpn\s*=\s*")([^"]*)(")', r"\1My+Project\3", cleaned)
    with contextlib.suppress(re.error, TypeError, ValueError):
        cleaned = re.sub(
            r'(\bcom\s*=\s*")([^"]*)(")', r"\1Firstname+Lastname\3", cleaned
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
        api = getattr(coordinator, "api", None)
        if api:
            # Ensure we have a valid session for read-only calls
            try:
                if not api.is_session_valid():
                    await api.login()
            except Exception:
                # Don't fail diagnostics if login fails
                _LOGGER.debug("Diagnostics: XML API login failed", exc_info=True)
                api = None

        if not (api and api.projects):
            return {}

        # Capture api in a typed local variable for the closures below;
        # mypy does not narrow `api` to not-None inside them.
        xml_api: SyrConnectXmlAPI = api
        semaphore = asyncio.Semaphore(_SYR_CONNECT_DIAGNOSTICS_CONCURRENT_API_CALLS)

        # A failed request only leaves an empty response for this project/device
        async def _fetch(url: str, payload: dict[str, Any]) -> str:
            try:
                async with semaphore:
                    return await xml_api.http_client.post(url, payload)
            except Exception:
                _LOGGER.debug(
                    "Diagnostics: XML request to %s failed", url, exc_info=True
                )
                return ""

        async def _fetch_status(did: str) -> tuple[str, str]:
            payload = xml_api.payload_builder.build_device_get_status_payload(
                xml_api.session_data or "", did
            )
            xml_status = await _fetch(xml_api.device_get_status_url, {"xml": payload})
            return did, _redact_xml(xml_status)

        # Iterate all projects of the account (from the login response)
        projects_raw: dict[str, Any] = {}
        for project in xml_api.projects:
            pid = project.get("id")
            if not pid:
                continue
            projects_raw[pid] = {"device_list": "", "devices": {}}
            payload = xml_api.payload_builder.build_device_get_list_payload(
                xml_api.session_data or "", pid
            )
            xml_resp = await _fetch(xml_api.device_list_url, {"xml": payload})
            projects_raw[pid]["device_list"] = _redact_device_list_xml(xml_resp)

            # Parse devices (best-effort) from the original, unredacted response
            try:
                devices = xml_api.response_parser.parse_device_list_response(xml_resp)
            except Exception:
                _LOGGER.debug(
                    "Diagnostics: device list of project %s could not be parsed",
                    pid,
                    exc_info=True,
                )
                devices = []

            # Fetch status for each device (limited concurrency by semaphore)
            status_tasks = [
                _fetch_status(device_id)
                for device in devices
                if (device_id := device.get("dclg") or device.get("id"))
            ]
            if status_tasks:
                results = await asyncio.gather(*status_tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, Exception):
                        continue
                    if isinstance(res, tuple) and len(res) == 2:
                        did, xmls = res
                        projects_raw[pid]["devices"][did] = xmls

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


async def _fetch_local_device_json(
    session: Any, dev: SyrConnectDevice, base_path: str
) -> tuple[str, Any]:
    """Fetch the redacted local `/get/all` data of a cloud device.

    Returns (device id, data), with None as data when the device has no usable
    private IP or the request fails.
    """
    dev_id = str(dev.get("id") or dev.get("dclg") or "unknown")

    # Determine the IP from the status (Wi-Fi first, then Ethernet, then the generic
    # IP address)
    status = dev.get("status") or {}
    ip = status.get("getWIP") or status.get("getEIP") or status.get("getIPA")

    # Normalize IP: treat empty string or the placeholder 0.0.0.0 as absent
    if isinstance(ip, str) and (ip.strip() == "" or ip == "0.0.0.0"):
        ip = None

    # If no usable IP, skip JSON fetch for this device
    if not ip:
        return dev_id, None

    # The IP comes from the cloud; only contact devices in the local network. A wrong
    # or manipulated cloud answer must not make Home Assistant send requests (including
    # the ADM login below) to an arbitrary public address.
    try:
        if not ipaddress.ip_address(str(ip).strip()).is_private:
            return dev_id, None
    except ValueError:
        return dev_id, None

    json_api = SyrConnectJsonAPI(session, host=ip, base_path=base_path)
    try:
        # Login is required for some devices
        try:
            if not json_api.is_session_valid():
                await json_api.login()
        except Exception:
            # If login fails, still attempt to fetch once
            _LOGGER.debug(
                "Diagnostics: local login to device %s failed", dev_id, exc_info=True
            )

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
    coordinator: SyrConnectDataUpdateCoordinator,
) -> dict[str, Any]:
    """Collect local `/get/all` data of cloud (XML API) devices whose model offers local access.

    Only models with a `base_path` are queried (see `_local_json_base_path`), at the
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

            async def _wrap(dev: SyrConnectDevice, base_path: str) -> tuple[str, Any]:
                async with semaphore:
                    return await _fetch_local_device_json(session, dev, base_path)

            tasks = [
                _wrap(d, base_path)
                for d in devices
                if isinstance(d, dict) and (base_path := _local_json_base_path(d))
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


def _device_summary(device: SyrConnectDevice, api_type: str) -> dict[str, Any]:
    """Return the diagnostics summary of a coordinator device.

    Lists the detected model, versions and the keys that become visible sensors, so
    a missing entity can be told apart from a key the device does not report.
    The values are still unmasked here; masking happens afterwards for the whole result.
    """
    status = device.get("status", {})

    # Extract model information
    model_info = detect_model(status)
    model_display = (
        model_info.get("display_name") if isinstance(model_info, dict) else None
    )

    # The sensors the integration creates for this status, with the same rules as the setup
    visible_keys = sensor_keys_for_status(status)

    device_info = {
        "id": device.get("id"),
        "name": device.get("name"),
        "available": device.get("available", True),
        "project_id": device.get("project_id"),
        "model": model_display,
        "sw_version": status.get("getVER"),
        "hw_version": status.get("getFIR"),
        "api_type": api_type,
        "status_count": len(visible_keys),
        "status_keys": sorted(visible_keys),
    }

    # Add XML API specific fields
    if api_type == API_TYPE_XML and device.get("dclg"):
        device_info["dclg"] = device.get("dclg")

    # Add JSON API specific fields
    if api_type == API_TYPE_JSON and device.get("base_path"):
        device_info["base_path"] = device.get("base_path")

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
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        Dictionary with diagnostic information
    """
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data

    devices_info: list[dict[str, Any]] = []
    projects_info: list[dict[str, Any]] = []

    last_success_time = getattr(coordinator, "last_update_success_time", None)

    diagnostics_data = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "options": dict(entry.options),
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
    try:
        entry_obj = diagnostics_data.get("entry")
        if isinstance(entry_obj, dict):
            title_obj = entry_obj.get("title")
            if isinstance(title_obj, str):
                entry_obj["title"] = re.sub(
                    r"\(([^)]+)\)", "(***REDACTED_USERNAME***)", title_obj
                )
    except TypeError, AttributeError, re.error:
        pass

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
            coordinator
        )

    if coordinator.data:
        # Populate devices and projects BEFORE masking and redaction, so the steps
        # below cover them as well
        devices_info.extend(
            _device_summary(device, api_type)
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
