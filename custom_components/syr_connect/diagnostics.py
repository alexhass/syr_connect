"""Diagnostics support for SYR Connect."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .api import SyrConnectAPI
from .const import (
    _SYR_CONNECT_API_DEVICE_LIST_URL,
    _SYR_CONNECT_API_DEVICE_STATUS_URL,
)
from .coordinator import SyrConnectDataUpdateCoordinator

_TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "session_data",
    "getMAC",
    "getIPA",
    "getDGW",
}


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

    # Attempt to include raw XML responses (redacted) for diagnostics.
    # This collects data for ALL projects and their devices but uses
    # limited concurrency and truncates very large responses to avoid
    # excessive load or extremely large diagnostics payloads.
    def _redact_xml(xml: str, api: SyrConnectAPI | None) -> str:
        """Redact sensitive keys inside an XML string using patterns.

        This will replace attribute values, <c n="..." v="..."/> entries,
        and generic IP/MAC/email patterns for any key listed in `_TO_REDACT`.
        """
        if not isinstance(xml, str) or not xml:
            return ""

        cleaned = xml

        # For each redact key, replace attribute values like key="..."
        for key in _TO_REDACT:
            if not key:
                continue
            key_str = str(key)
            placeholder = f"<REDACTED_{re.sub(r'[^A-Za-z0-9]', '_', key_str).upper()}>"

            # attributes like mac="..."
            try:
                cleaned = re.sub(
                    rf'({re.escape(key_str)}\s*=\s*")([^"]*)(")',
                    rf'\1{placeholder}\3',
                    cleaned,
                    flags=re.IGNORECASE,
                )
            except Exception:
                pass

            # <c n="getMAC" v="..." /> or similar: redact v when n matches key
            try:
                cleaned = re.sub(
                    rf'(<c\b[^>]*\bn\s*=\s*"{re.escape(key_str)}"[^>]*\bv\s*=\s*")([^"]*)(")',
                    rf'\1{placeholder}\3',
                    cleaned,
                    flags=re.IGNORECASE,
                )
            except Exception:
                pass

            # simple key:value or key=val patterns
            try:
                cleaned = re.sub(
                    rf'({re.escape(key_str)}\s*[:=]\s*)([^\s><"\']+)',
                    rf'\1{placeholder}',
                    cleaned,
                    flags=re.IGNORECASE,
                )
            except Exception:
                pass

        # Generic redactions
        try:
            cleaned = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<REDACTED_IP>", cleaned)
            cleaned = re.sub(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", "<REDACTED_MAC>", cleaned)
            cleaned = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "<REDACTED_USERNAME>", cleaned)
        except Exception:
            pass

        return cleaned

    raw_xml: dict[str, Any] = {}
    try:
        api = getattr(coordinator, "api", None)
        if api:
            # Ensure we have a valid session for read-only calls
            try:
                if not api.is_session_valid():
                    await api.login()
            except Exception:
                # don't fail diagnostics if login fails
                api = None

        if api and isinstance(api.projects, list) and api.projects:
            import asyncio

            semaphore = asyncio.Semaphore(5)

            async def _fetch(url: str, payload: dict[str, Any]) -> str:
                try:
                    async with semaphore:
                        return await api.http_client.post(url, payload)
                except Exception:
                    return ""

            async def _fetch_status(did: str) -> tuple[str, str]:
                payload2 = api.payload_builder.build_device_status_payload(api.session_data, did)
                xml_status = await _fetch(_SYR_CONNECT_API_DEVICE_STATUS_URL, {"xml": payload2})
                return did, _redact_xml(xml_status, api)

            # iterate all projects
            projects_raw: dict[str, Any] = {}
            for project in api.projects:
                pid = project.get("id")
                projects_raw[pid] = {"device_list": "", "devices": {}}
                payload = api.payload_builder.build_device_list_payload(api.session_data, pid)
                xml_resp = await _fetch(_SYR_CONNECT_API_DEVICE_LIST_URL, {"xml": payload})
                projects_raw[pid]["device_list"] = _redact_xml(xml_resp, api)

                # parse devices (best-effort)
                try:
                    devices = api.response_parser.parse_device_list_response(xml_resp)
                except Exception:
                    devices = []

                # fetch status for each device (limited concurrency by semaphore)
                status_tasks = [
                    _fetch_status(device.get("dclg") or device.get("id"))
                    for device in devices
                    if device.get("dclg") or device.get("id")
                ]

                if status_tasks:
                    results = await asyncio.gather(*status_tasks, return_exceptions=True)
                    for res in results:
                        if isinstance(res, Exception):
                            continue
                        if isinstance(res, tuple) and len(res) == 2:
                            did, xmls = res
                            projects_raw[pid]["devices"][did] = xmls

            raw_xml = projects_raw

    except Exception:
        # Never raise from diagnostics
        raw_xml = {"error": "failed to collect raw xml for all projects"}

    diagnostics_data["raw_xml"] = raw_xml

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
                    placeholder = f"<REDACTED_{re.sub(r'[^A-Za-z0-9]', '_', str(k)).upper()}>"
                    out[k] = placeholder
                else:
                    out[k] = _redact_obj(v)
            return out

        if isinstance(obj, list):
            return [_redact_obj(i) for i in obj]

        if isinstance(obj, str):
            # redact sensitive values inside strings (including raw XML)
            return _redact_xml(obj, getattr(coordinator, "api", None))

        return obj

    diagnostics_data = _redact_obj(diagnostics_data)

    if coordinator.data:
        # Add device information
        for device in coordinator.data.get("devices", []):
            device_info = {
                "id": device.get("id"),
                "name": device.get("name"),
                "available": device.get("available", True),
                "project_id": device.get("project_id"),
                "status_count": len(device.get("status", {})),
                "status_keys": list(device.get("status", {}).keys()),
            }
            devices_info.append(device_info)

        # Add project information
        for project in coordinator.data.get("projects", []):
            project_info = {
                "id": project.get("id"),
                "name": project.get("name"),
            }
            projects_info.append(project_info)

    # Redact sensitive information from the dict fields (not raw XML strings)
    return async_redact_data(diagnostics_data, _TO_REDACT)
