"""Diagnostics support for SYR Connect."""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .api_json import _SYR_CONNECT_DEFAULT_API_TIMEOUT, SyrConnectJsonAPI
from .api_xml import SyrConnectXmlAPI
from .const import (
    _SYR_CONNECT_API_XML_DEVICE_GET_STATUS_URL,
    _SYR_CONNECT_API_XML_DEVICE_LIST_URL,
    _SYR_CONNECT_SENSOR_KNOWN_KEYS,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
)
from .coordinator import SyrConnectDataUpdateCoordinator
from .helpers import is_sensor_visible
from .models import detect_model

# Maximum concurrent API calls for diagnostics data collection
_SYR_CONNECT_CONCURRENT_API_CALLS = 5

# Some keys are handled specially and MUST NOT be fully redacted:
# - `getMAC`/`getMAC1`/`getMAC2` are masked with custom rules below,
# - `getSRN` (device serial)
_TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "session_data",
    "getDGW",   # Default gateway
    "getEGW",   # Ethernet gateway
    "getEIP",   # Ethernet IP address
    "getIPA",   # IP address
    "getWFC",   # Wi-Fi SSID
    "getWGW",   # Wi-Fi gateway
    "getWIP",   # Wi-Fi IP address
}


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
    sep = ':' if ':' in s else '-' if '-' in s else ':'
    preserved = [p.upper() for p in pairs[:3]]
    masked_tail = ['XX'] * (len(pairs) - 3)
    result = sep.join(preserved + masked_tail)
    if last_char_replace is not None:
        try:
            result = re.sub(r"([0-9A-F])$", last_char_replace, result)
        except re.error:
            pass
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

    # Use module-level `mask_mac_value` helper defined above.

    # Redact username in entry title if present, e.g. "SYR Connect (username)" ->
    # "SYR Connect (***REDACTED_USERNAME***)" to avoid leaking usernames in diagnostics.
    try:
        entry_obj = diagnostics_data.get("entry")
        if isinstance(entry_obj, dict):
            title_obj = entry_obj.get("title")
            if isinstance(title_obj, str):
                entry_obj["title"] = re.sub(r"\(([^)]+)\)", "(***REDACTED_USERNAME***)", title_obj)
    except (TypeError, AttributeError, re.error):
        pass

    # Attempt to include raw XML responses (redacted) for diagnostics.
    # This collects data for ALL projects and their devices but uses
    # limited concurrency and truncates very large responses to avoid
    # excessive load or extremely large diagnostics payloads.
    def _redact_xml(xml: str, api: SyrConnectXmlAPI | None) -> str:
        """Redact sensitive keys inside an XML string using patterns.

        This will replace attribute values, <c n="..." v="..."/> entries,
        and generic IP/MAC/email patterns for any key listed in `_TO_REDACT`.
        """
        if not isinstance(xml, str) or not xml:
            return ""

        cleaned = xml

        # Replace standalone MAC addresses in text using the shared helper
        cleaned = re.sub(
            r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
            lambda m: mask_mac_value(m.group(0), None),
            cleaned,
        )

        # Mask SRN values inside XML attribute forms and <c n="getSRN" v="..."/> entries
        try:
            cleaned = re.sub(
                r'(<c\b[^>]*\bn\s*=\s*"getSRN"[^>]*\bv\s*=\s*")([^\"]*)(")',
                lambda m: m.group(1) + mask_srn_value(m.group(2)) + m.group(3),
                cleaned,
                flags=re.IGNORECASE,
            )
        except (re.error, TypeError, ValueError):
            pass

        try:
            cleaned = re.sub(
                r'(\bgetSRN\s*=\s*")([^\"]*)(")',
                lambda m: m.group(1) + mask_srn_value(m.group(2)) + m.group(3),
                cleaned,
                flags=re.IGNORECASE,
            )
        except (re.error, TypeError, ValueError):
            pass

        # For each redact key, replace attribute values like key="..."
        for key in _TO_REDACT:
            if not key:
                continue
            key_str = str(key)
            placeholder = f"***REDACTED_{re.sub(r'[^A-Za-z0-9]', '_', key_str).upper()}***"

            # Attributes like mac="..."
            try:
                cleaned = re.sub(
                    rf'({re.escape(key_str)}\s*=\s*")([^"]*)(")',
                    rf'\1{placeholder}\3',
                    cleaned,
                    flags=re.IGNORECASE,
                )
            except (re.error, TypeError, ValueError):
                pass

            # <c n="getMAC" v="..." /> or similar: redact v when n matches key
            try:
                cleaned = re.sub(
                    rf'(<c\b[^>]*\bn\s*=\s*"{re.escape(key_str)}"[^>]*\bv\s*=\s*")([^"]*)(")',
                    rf'\1{placeholder}\3',
                    cleaned,
                    flags=re.IGNORECASE,
                )
            except (re.error, TypeError, ValueError):
                pass

            # Simple key:value or key=val patterns
            try:
                cleaned = re.sub(
                    rf'({re.escape(key_str)}\s*[:=]\s*)([^\s><"\']+)',
                    rf'\1{placeholder}',
                    cleaned,
                    flags=re.IGNORECASE,
                )
            except (re.error, TypeError, ValueError):
                pass

        # Generic redactions
        try:
            cleaned = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "***REDACTED_IP***", cleaned)

            # Replace standalone MAC addresses in text using the shared helper
            cleaned = re.sub(
                r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
                lambda m: mask_mac_value(m.group(0), None),
                cleaned,
            )

            cleaned = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "***REDACTED_USERNAME***", cleaned)
        except (re.error, TypeError, ValueError):
            pass

        # Remove any whitespace (including newlines) between XML tags: '>   <' -> '><'
        try:
            cleaned = re.sub(r">\s+<", "><", cleaned)
            cleaned = cleaned.strip()
        except (re.error, TypeError, ValueError):
            pass

        return cleaned

    raw_xml: dict[str, Any] = {}

    # Determine API type from config entry
    api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML)

    # Only collect raw XML for XML API (not for JSON API)
    if api_type == API_TYPE_XML:
        try:
            api = getattr(coordinator, "api", None)
            if api:
                # Ensure we have a valid session for read-only calls
                try:
                    if not api.is_session_valid():
                        await api.login()
                except Exception:  # pragma: no cover - diagnostics should never fail
                    # Don't fail diagnostics if login fails
                    api = None

            if api and api.projects:
                # Capture api in local variable for type narrowing in closures
                # mypy doesn't understand that api is not None after the check above
                xml_api: SyrConnectXmlAPI = api
                semaphore = asyncio.Semaphore(_SYR_CONNECT_CONCURRENT_API_CALLS)

                async def _fetch(url: str, payload: dict[str, Any]) -> str:
                    try:
                        async with semaphore:
                            return await xml_api.http_client.post(url, payload)
                    except Exception:  # pragma: no cover - diagnostics should never fail
                        return ""

                # Iterate all projects
                projects_raw: dict[str, Any] = {}
                for project in xml_api.projects:
                    pid = project.get("id")
                    if not pid:
                        continue
                    projects_raw[pid] = {"device_list": "", "devices": {}}
                    payload = xml_api.payload_builder.build_device_list_payload(
                        xml_api.session_data or "", pid
                    )
                    xml_resp = await _fetch(_SYR_CONNECT_API_XML_DEVICE_LIST_URL, {"xml": payload})

                    # Redact the device list XML and replace personal attributes:
                    # - `pn="..."` -> `My+Project` (project name)
                    # - `com="..."` -> `Firstname+Lastname` (contact/owner name)
                    cleaned_list = _redact_xml(xml_resp, xml_api)
                    try:
                        cleaned_list = re.sub(r'(\bpn\s*=\s*")([^"]*)(")', r'\1My+Project\3', cleaned_list)
                    except (re.error, TypeError, ValueError):
                        # If replacement fails, keep the redacted content as-is
                        pass
                    try:
                        cleaned_list = re.sub(r'(\bcom\s*=\s*")([^"]*)(")', r'\1Firstname+Lastname\3', cleaned_list)
                    except (re.error, TypeError, ValueError):
                        # If replacement fails, keep the redacted content as-is
                        pass
                    projects_raw[pid]["device_list"] = cleaned_list

                    # Parse devices (best-effort)
                    try:
                        devices = xml_api.response_parser.parse_device_list_response(xml_resp)
                    except Exception:  # pragma: no cover - diagnostics should never fail
                        devices = []

                    # Fetch status for each device (limited concurrency by semaphore)
                    status_tasks = []
                    for device in devices:
                        device_id = device.get("dclg") or device.get("id")
                        if not device_id:
                            continue

                        async def _fetch_status(did: str):
                            payload2 = xml_api.payload_builder.build_device_status_payload(
                                xml_api.session_data or "", did
                            )
                            xml_status = await _fetch(_SYR_CONNECT_API_XML_DEVICE_GET_STATUS_URL, {"xml": payload2})
                            return did, _redact_xml(xml_status, xml_api)

                        status_tasks.append(_fetch_status(device_id))

                    if status_tasks:
                        results = await asyncio.gather(*status_tasks, return_exceptions=True)
                        for res in results:
                            if isinstance(res, Exception):
                                continue
                            if isinstance(res, tuple) and len(res) == 2:
                                did, xmls = res
                                projects_raw[pid]["devices"][did] = xmls

                raw_xml = projects_raw

        except Exception:  # pragma: no cover - diagnostics should never fail
            # Never raise from diagnostics
            raw_xml = {"error": "failed to collect raw xml for all projects"}

    diagnostics_data["raw_xml"] = raw_xml

    # Attempt to include raw JSON responses from devices that support
    # the local JSON API (have a `base_path`). We fetch `/get/all` and
    # redact sensitive keys using `async_redact_data` before including
    # the result in diagnostics.
    raw_json: dict[str, Any] = {}

    # For JSON API, collect data directly from coordinator.api
    if api_type == API_TYPE_JSON:
        try:
            api = getattr(coordinator, "api", None)
            if api and isinstance(api, SyrConnectJsonAPI):
                try:
                    # Ensure we have a valid session
                    if not api.is_session_valid():
                        await api.login()
                except Exception:  # pragma: no cover - diagnostics should never fail
                    # If login fails, still attempt to fetch once
                    pass

                try:
                    data = await api._request_json_data("get/all", timeout=_SYR_CONNECT_DEFAULT_API_TIMEOUT)
                    # Redact sensitive keys from the parsed JSON payload
                    redacted = async_redact_data(data, _TO_REDACT)
                    # Ensure SRN is fully redacted for raw_json payloads
                    try:
                        if isinstance(redacted, dict) and "getSRN" in redacted:
                            redacted["getSRN"] = "**REDACTED**"
                    except Exception:
                        pass
                    # Use the first device ID from coordinator data as key, or "local_device"
                    device_id = "local_device"
                    if coordinator.data and coordinator.data.get("devices"):
                        device_id = coordinator.data["devices"][0].get("id", "local_device")
                    raw_json[device_id] = redacted
                except Exception:  # pragma: no cover - diagnostics should never fail
                    # Set error but don't overwrite the entire dict
                    raw_json["error"] = "failed to fetch JSON data from device"
        except Exception:  # pragma: no cover - diagnostics should never fail
            # Set error but don't overwrite the entire dict
            raw_json["error"] = "failed to collect raw json for JSON API"
    else:
        # For XML API, attempt to collect JSON data from devices with base_path
        try:
            # Use the coordinator's aiohttp session so we reuse the existing
            # HA-managed ClientSession and its connectors.
            session = getattr(coordinator, "_session", None)
            if session is None:
                # If coordinator unexpectedly lacks a session, skip JSON collection
                raw_json = {"error": "no http session available on coordinator"}
                diagnostics_data["raw_json"] = raw_json
            else:
                async def _fetch_device_json(dev: dict[str, Any]):
                    dev_id = str(dev.get("id") or dev.get("dclg") or "unknown")
                    base_path = dev.get("base_path")
                    if not base_path:
                        return dev_id, None

                    # Determine IP from device fields or status
                    ip = dev.get("ip") or dev.get("getWIP") or dev.get("getEIP")
                    if not ip:
                        # try status dict
                        status = dev.get("status") or {}
                        ip = status.get("getWIP") or status.get("getEIP") or status.get("getIPA")

                    # Normalize IP: treat empty string or the placeholder 0.0.0.0 as absent
                    if isinstance(ip, str) and (ip.strip() == "" or ip == "0.0.0.0"):
                        ip = None

                    # If no usable IP, skip JSON fetch for this device
                    if not ip:
                        return dev_id, None

                    json_api = SyrConnectJsonAPI(session, host=ip, base_path=base_path)
                    try:
                        # Login is required for some devices
                        try:
                            if not json_api.is_session_valid():
                                await json_api.login()
                        except Exception:  # pragma: no cover - diagnostics should never fail
                            # If login fails, still attempt to fetch once
                            pass

                        base = json_api._build_base_url()
                        if not base:
                            return dev_id, None

                        try:
                            data = await json_api._request_json_data("get/all", timeout=_SYR_CONNECT_DEFAULT_API_TIMEOUT)
                        except Exception:  # pragma: no cover - diagnostics should never fail
                            return dev_id, None

                        # Redact sensitive keys from the parsed JSON payload
                        redacted = async_redact_data(data, _TO_REDACT)
                        # Ensure SRN is fully redacted for raw_json payloads
                        try:
                            if isinstance(redacted, dict) and "getSRN" in redacted:
                                redacted["getSRN"] = "**REDACTED**"
                        except Exception:
                            pass
                        return dev_id, redacted
                    except Exception:  # pragma: no cover - diagnostics should never fail
                        return dev_id, None

                if coordinator and getattr(coordinator, "data", None):
                    devices = coordinator.data.get("devices", [])
                    semaphore = asyncio.Semaphore(_SYR_CONNECT_CONCURRENT_API_CALLS)

                    async def _wrap(dev):
                        async with semaphore:
                            return await _fetch_device_json(dev)

                    tasks = [_wrap(d) for d in devices if isinstance(d, dict) and d.get("base_path")]
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for res in results:
                            if isinstance(res, Exception):
                                continue
                            if isinstance(res, tuple) and len(res) == 2:
                                did, payload = res
                                if payload is not None:
                                    raw_json[did] = payload
        except Exception:  # pragma: no cover - diagnostics should never fail
            raw_json = {"error": "failed to collect raw json for devices"}

    diagnostics_data["raw_json"] = raw_json

    # Apply redaction for all configured keys everywhere in the diagnostics
    def _redact_obj(obj: Any) -> Any:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                # Preserve raw_xml completely unchanged
                if str(k) == "raw_xml":
                    out[k] = v
                    continue

                # If the dict key itself matches a redact key, replace value entirely
                if any(str(k).lower() == str(r).lower() for r in _TO_REDACT):
                    placeholder = f"***REDACTED_{re.sub(r'[^A-Za-z0-9]', '_', str(k)).upper()}***"
                    out[k] = placeholder
                else:
                    out[k] = _redact_obj(v)
            return out

        if isinstance(obj, list):
            return [_redact_obj(i) for i in obj]

        if isinstance(obj, str):
            # Redact sensitive values inside strings (including raw XML)
            return _redact_xml(obj, getattr(coordinator, "api", None))

        return obj

    # Populate devices and projects BEFORE redaction
    if coordinator.data:
        # Add device information
        for device in coordinator.data.get("devices", []):
            status = device.get("status", {})

            # Extract model information
            model_info = detect_model(status)
            model_display = model_info.get("display_name") if isinstance(model_info, dict) else None

            # Determine visible status keys using centralized helper
            visible_keys: list[str] = [
                k for k, v in status.items()
                if k in _SYR_CONNECT_SENSOR_KNOWN_KEYS and is_sensor_visible(status, k, v)
            ]

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

            devices_info.append(device_info)

        # Add project information
        for project in coordinator.data.get("projects", []):
            project_info = {
                "id": project.get("id"),
                "name": project.get("name"),
            }
            projects_info.append(project_info)

        # Mask sensitive values BEFORE global redaction.
        # 1) `getSRN`: If value matches `\d{3}[A-Z]{3}\d{5}`, replace trailing 5 digits with '12345'.
        # 2) `getMAC` / `getMAC1`: Replace vendor part (first 3 octets) with 'XX'.
        # 3) `getMAC2`: Same vendor masking, then replace final character with 'Y'.
        # Use module-level `mask_srn_value` helper defined above

        def _mask_sensitive(obj: Any) -> Any:
            if isinstance(obj, dict):
                for k, v in list(obj.items()):
                    key = str(k)

                    # Mask SRN value when the key is `getSRN` (case-insensitive)
                    if key.lower() == 'getsrn':
                        obj[k] = mask_srn_value(v)
                        continue

                    # Mask MACs with custom rules using shared helper
                    if isinstance(v, str) and key.lower() in ('getmac', 'getmac1'):
                        obj[k] = mask_mac_value(v, last_char_replace=None)
                        continue
                    if isinstance(v, str) and key.lower() == 'getmac2':
                        obj[k] = mask_mac_value(v, last_char_replace='Y')
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

        diagnostics_data = _mask_sensitive(diagnostics_data)

        # Apply redaction after populating devices and projects
        diagnostics_data = _redact_obj(diagnostics_data)

    # Redact sensitive information from the dict fields (not raw XML strings)
    return async_redact_data(diagnostics_data, _TO_REDACT)
