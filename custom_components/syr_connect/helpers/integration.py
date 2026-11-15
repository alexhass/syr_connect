"""Integration-wide helpers: version, scan interval, locale and hosts."""

import ipaddress
import logging
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_loaded_integration
from homeassistant.util import dt as dt_util

from ..const import (
    _SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT,
    _SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT,
    _SYR_CONNECT_SCAN_INTERVAL_CONF,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


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


def get_month_version() -> str:
    """Return the current year and month with patch 0 as a version, e.g. "2026.11.0"."""
    now = dt_util.now()
    return f"{now.year}.{now.month}.0"


def get_integration_version(hass: HomeAssistant) -> str:
    """Return the version of this integration from its manifest.

    Without a version in the manifest, the current year and month are used
    (get_month_version).
    """
    version = async_get_loaded_integration(hass, DOMAIN).version
    return str(version) if version is not None else get_month_version()


def build_user_agent(integration_version: str, ha_version: str = HA_VERSION) -> str:
    """Build the HTTP User-Agent that names the integration and Home Assistant.

    Example: "syr_connect/2.1.0 HomeAssistant/2026.11.1"
    """
    return f"{DOMAIN}/{integration_version} HomeAssistant/{ha_version}"


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
