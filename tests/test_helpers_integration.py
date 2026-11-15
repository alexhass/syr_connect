"""Tests for the integration helpers (helpers/integration.py)."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from custom_components.syr_connect.const import (
    _SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT,
    _SYR_CONNECT_API_RESPONSE_SIZE_MAXIMUM,
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
    mask_ug_value,
    read_response_text,
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


# ---------------------------------------------------------------------------
# Lines 297-298 — get_sensor_avo_value: mL-pattern except branch
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Lines 306-307 — get_sensor_avo_value: fallback-pattern except branch
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Lines 793-794 — is_sensor_visible is_value_true: int/float except branch
# ---------------------------------------------------------------------------


def test_mask_ug_value_basic() -> None:
    """Test mask ug value basic."""
    payload = '<sc ug="SECRET_TOKEN"><payload>data</payload></sc>'

    masked = mask_ug_value(payload)

    assert 'ug="***"' in masked
    assert "SECRET_TOKEN" not in masked
    assert masked.count('ug="***"') == 1


def test_mask_ug_value_multiple_occurrences() -> None:
    """Test mask ug value multiple occurrences."""
    payload = '<r ug="T1"><a ug="T2"/></r>'

    masked = mask_ug_value(payload)

    assert masked.count('ug="***"') == 2
    assert "T1" not in masked and "T2" not in masked


def test_mask_ug_value_handles_empty_value() -> None:
    """Test mask ug value handles empty value."""
    payload = '<r ug=""><child ug=""/></r>'

    masked = mask_ug_value(payload)

    assert masked.count('ug="***"') == 2


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ('<us ug="SECRET', '<us ug="***'),  # truncated payload
        ('<dcl a="x>y" ug="SECRET"/>', '<dcl a="x>y" ug="***"/>'),  # raw `>` in a value
        ('error: ug="SECRET"', 'error: ug="***"'),  # outside any tag
        ('<a UG = "SECRET"/>', '<a UG = "***"/>'),  # case and spacing
        (
            '<a xug="keep" ug="SECRET"/>',
            '<a xug="keep" ug="***"/>',
        ),  # longer names untouched
    ],
)
def test_mask_ug_value_masks_outside_complete_tags(payload: str, expected: str) -> None:
    """The token must be masked even when the payload is not well-formed XML."""
    assert mask_ug_value(payload) == expected


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


def test_mask_ug_value_empty_string_returns_empty() -> None:
    """When payload is an empty string, return it unchanged."""
    assert mask_ug_value("") == ""


def test_mask_ug_value_non_string_returns_input() -> None:
    """Non-string payloads should be returned unchanged."""
    assert mask_ug_value(cast(Any, None)) is None
    result: Any = mask_ug_value(cast(Any, 123))
    assert result == 123


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


async def test_read_response_text_in_chunks(
    set_response_body: Callable[..., None],
) -> None:
    """A body that arrives in several chunks is joined and decoded as UTF-8."""
    response = MagicMock()
    set_response_body(response, "<sc>Wasserhärte</sc>", chunk_size=4)

    assert await read_response_text(response) == "<sc>Wasserhärte</sc>"


@pytest.mark.parametrize(
    ("charset", "expected"),
    [
        pytest.param("latin-1", "Wasserhärte", id="announced"),
        # An unknown charset falls back to UTF-8, which cannot decode this body
        pytest.param("utf-8", None, id="wrong"),
    ],
)
async def test_read_response_text_charset(
    set_response_body: Callable[..., None], charset: str, expected: str | None
) -> None:
    """The body is decoded with the charset the server announces."""
    response = MagicMock()
    set_response_body(response, "Wasserhärte".encode("latin-1"))
    response.charset = charset

    if expected is None:
        with pytest.raises(UnicodeDecodeError):
            await read_response_text(response)
    else:
        assert await read_response_text(response) == expected


async def test_read_response_text_unknown_charset(
    set_response_body: Callable[..., None],
) -> None:
    """A charset Python does not know falls back to UTF-8."""
    response = MagicMock()
    set_response_body(response, "Wasserhärte")
    response.charset = "no-such-charset"

    assert await read_response_text(response) == "Wasserhärte"


async def test_read_response_text_at_the_limit(
    set_response_body: Callable[..., None],
) -> None:
    """A body of exactly the maximum size is still accepted."""
    limit = _SYR_CONNECT_API_RESPONSE_SIZE_MAXIMUM
    response = MagicMock()
    set_response_body(response, "x" * limit, chunk_size=64 * 1024)
    response.content_length = limit

    assert len(await read_response_text(response)) == limit


async def test_read_response_text_announced_size_too_large(
    set_response_body: Callable[..., None],
) -> None:
    """A response that announces more than the maximum size is not read at all."""
    limit = _SYR_CONNECT_API_RESPONSE_SIZE_MAXIMUM
    response = MagicMock()
    set_response_body(response, "ignored")
    response.content_length = limit + 1
    response.content.iter_chunked = MagicMock()

    with pytest.raises(
        aiohttp.ClientPayloadError,
        match="Response of 1048577 bytes exceeds the limit of 1048576 bytes",
    ):
        await read_response_text(response)

    response.content.iter_chunked.assert_not_called()


async def test_read_response_text_stops_reading_above_the_limit() -> None:
    """A body without an announced size is dropped as soon as it passes the maximum size."""
    limit = _SYR_CONNECT_API_RESPONSE_SIZE_MAXIMUM
    chunk = b"x" * (64 * 1024)
    sent = 0

    async def _endless(_size: int) -> AsyncIterator[bytes]:
        nonlocal sent
        while True:
            sent += len(chunk)
            yield chunk

    response = MagicMock()
    response.content_length = None
    response.content.iter_chunked = _endless

    with pytest.raises(
        aiohttp.ClientPayloadError, match="Response exceeds the limit of 1048576 bytes"
    ):
        await read_response_text(response)

    # Reading stopped with the first chunk above the limit
    assert sent == limit + len(chunk)
