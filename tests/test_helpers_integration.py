"""Tests for the integration helpers (helpers/integration.py)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest

from custom_components.syr_connect.aiosyrconnect.http_client import is_valid_user_agent
from custom_components.syr_connect.const import (
    _SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT,
    _SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT,
    _SYR_CONNECT_SCAN_INTERVAL_CONF,
    API_TYPE_JSON,
    CONF_API_TYPE,
    DOMAIN,
)
from custom_components.syr_connect.helpers.integration import (
    build_user_agent,
    get_api_locale,
    get_default_scan_interval_for_entry,
    get_integration_version,
    get_month_version,
    host_has_port,
    is_valid_host,
)
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration


def test_get_default_scan_interval_for_entry_none() -> None:
    """Test get default scan interval for entry none."""
    assert (
        get_default_scan_interval_for_entry(None)
        == _SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT
    )


def test_get_default_scan_interval_for_entry_options_and_data() -> None:
    """Test get default scan interval for entry options and data."""
    # Use an object with attributes (ConfigEntry-like) rather than a plain dict
    entry = SimpleNamespace(
        options={_SYR_CONNECT_SCAN_INTERVAL_CONF: "30"},
        data={CONF_API_TYPE: API_TYPE_JSON},
    )
    assert get_default_scan_interval_for_entry(cast(Any, entry)) == 30

    # invalid option falls back to API default
    entry = SimpleNamespace(
        options={_SYR_CONNECT_SCAN_INTERVAL_CONF: "bad"},
        data={CONF_API_TYPE: API_TYPE_JSON},
    )
    assert (
        get_default_scan_interval_for_entry(cast(Any, entry))
        == _SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT
    )


def test_get_default_scan_interval_for_entry_with_dict() -> None:
    """Entry provided as plain dict should be handled like a mapping."""
    entry = {
        "options": {_SYR_CONNECT_SCAN_INTERVAL_CONF: "30"},
        "data": {CONF_API_TYPE: API_TYPE_JSON},
    }
    # Implementation handles plain dicts: reads scan_interval from options directly.
    assert get_default_scan_interval_for_entry(entry) == 30


@pytest.mark.parametrize(
    ("language", "country", "expected"),
    [
        (None, None, "en-US"),
        ("", "DE", "en-DE"),
        ("de", "DE", "de-DE"),
        ("de", "AT", "de-AT"),
        ("de", None, "de-US"),  # no country: region defaults to US
        ("zh-Hans", None, "zh-US"),
        ("en-GB", "DE", "en-GB"),  # region in the language wins
        ("pt_BR", None, "pt-BR"),
        ("zh-Hans", "CN", "zh-CN"),  # script is not a region
        ("EN", "us", "en-US"),
    ],
)
def test_get_api_locale(language: Any, country: Any, expected: Any) -> None:
    """The cloud locale combines the HA language with its region or the HA country."""
    assert get_api_locale(language, country) == expected


@pytest.mark.parametrize(
    "host",
    [
        "192.168.1.5",
        "syr.local",
        "my-device",
        # IPv6 literals, including ones ending in a decimal group that used to be
        # mistaken for "host:port"
        "fe80::1",
        "::1",
        "2001:db8::5",
        "2001:db8::1:5",
        "fd00::abcd",
    ],
)
def test_is_valid_host_accepts(host: str) -> None:
    """IPv4, IPv6 and hostnames without a port are valid."""
    assert is_valid_host(host) is True


@pytest.mark.parametrize(
    "host",
    [
        "",
        "   ",
        "host:80",
        "192.168.1.5:5333",
        "[fe80::1]",
        "bad host",
        "-bad.local",
        "a..b",
    ],
)
def test_is_valid_host_rejects(host: str) -> None:
    """Empty values, whitespace, explicit ports and malformed names are invalid."""
    assert is_valid_host(host) is False


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("192.168.1.10:5333", True),
        ("device.local:80", True),
        ("[fe80::1]:5333", True),
        ("192.168.1.10", False),
        ("device.local", False),
        ("fe80::1", False),
        ("2001:db8::5333", False),
        ("", False),
    ],
)
def test_host_has_port(host: Any, expected: Any) -> None:
    """A trailing :<port> is detected; plain IPv6 addresses ending in digits are not hosts with port."""
    assert host_has_port(host) is expected


async def test_get_integration_version_reads_the_manifest(hass: HomeAssistant) -> None:
    """The integration version comes from the loaded integration, i.e. manifest.json."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.version is not None
    assert get_integration_version(hass) == str(integration.version)


def test_get_integration_version_without_version(hass: HomeAssistant) -> None:
    """Without a version in the manifest, the current year and month are used."""
    with (
        patch(
            "custom_components.syr_connect.helpers.integration.async_get_loaded_integration",
            return_value=SimpleNamespace(version=None),
        ),
        patch(
            "custom_components.syr_connect.helpers.integration.get_month_version",
            return_value="2026.11.0",
        ),
    ):
        assert get_integration_version(hass) == "2026.11.0"


def test_get_month_version() -> None:
    """The version is the current year and month with patch 0."""
    with patch(
        "custom_components.syr_connect.helpers.integration.dt_util.now",
        return_value=datetime(2026, 1, 31, 23, 0, tzinfo=UTC),
    ):
        assert get_month_version() == "2026.1.0"


def test_build_user_agent(integration_version: str) -> None:
    """The User-Agent names the integration and Home Assistant with their versions."""
    assert (
        build_user_agent(integration_version)
        == f"syr_connect/{integration_version} HomeAssistant/{HA_VERSION}"
    )
    assert (
        build_user_agent(integration_version, "2026.11.0")
        == f"syr_connect/{integration_version} HomeAssistant/2026.11.0"
    )
    # The library accepts it (RFC 9110)
    assert is_valid_user_agent(build_user_agent(integration_version))
