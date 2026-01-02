"""Diagnostics support for SYR Connect."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import SyrConnectDataUpdateCoordinator

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "session_data",
    "mac",
    "getMAC",
    "getIPA",
    "getDGW",
    "ip",
    "gateway",
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
    
    diagnostics_data = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_update_time": coordinator.last_update_success_time.isoformat()
            if coordinator.last_update_success_time
            else None,
        },
        "devices": [],
        "projects": [],
    }
    
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
            diagnostics_data["devices"].append(device_info)
        
        # Add project information
        for project in coordinator.data.get("projects", []):
            project_info = {
                "id": project.get("id"),
                "name": project.get("name"),
            }
            diagnostics_data["projects"].append(project_info)
    
    # Redact sensitive information
    return async_redact_data(diagnostics_data, TO_REDACT)
