"""Migration helpers for the SYR Connect integration.

This module contains small, testable helpers that compute update kwargs
for config entry migrations. The helpers return a dict suitable for
passing to `hass.config_entries.async_update_entry(entry, **update_kwargs)`
or `None` if no update is required.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME

from .const import API_TYPE_JSON, API_TYPE_XML, CONF_API_TYPE, CONF_HOST, CONF_MODEL


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
