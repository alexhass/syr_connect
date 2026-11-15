"""Tests for the HTTP client helper."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001
from collections.abc import AsyncIterator, Callable
import re
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.syr_connect.aiosyrconnect import mask_ug_value
from custom_components.syr_connect.aiosyrconnect.const import (
    _SYR_CONNECT_API_RESPONSE_SIZE_MAXIMUM,
)
from custom_components.syr_connect.aiosyrconnect.http_client import (
    HTTPClient,
    read_response_text,
)


def test_get_headers_accept_language_default_and_custom() -> None:
    """Default Accept-Language is en-US, and respects `language` when set."""
    client = HTTPClient(session=MagicMock(), user_agent="test-agent")

    # Default when no language is passed
    headers_default = client._get_headers()
    assert headers_default["Accept-Language"] == "en-US,en;q=0.9"

    # Setting instance language should affect header
    client.language = "de_DE"
    headers_de = client._get_headers()
    assert headers_de["Accept-Language"] == "de-DE,de;q=0.9"


def test_build_accept_language_computes_value() -> None:
    """Accept-Language is computed from `language` or defaults."""
    client = HTTPClient(session=MagicMock(), user_agent="test-agent")

    # Default when no language is passed
    assert client._build_accept_language() == "en-US,en;q=0.9"

    # Custom language is respected and formatted
    client.language = "es_ES"
    assert client._build_accept_language() == "es-ES,es;q=0.9"


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError(),
        aiohttp.ClientError("Connection error"),
        aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=401, message="Unauthorized"
        ),
    ],
)
async def test_http_client_post_fails_after_one_attempt(error: Exception) -> None:
    """A failed request is not repeated; the next poll tries again."""
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(side_effect=error)
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.post = MagicMock(return_value=mock_context)

    client = HTTPClient(mock_session, "TestAgent/1.0")

    with pytest.raises(
        aiohttp.ClientError,
        match=re.escape(f"Request to https://example.com/api failed: {error!r}"),
    ) as excinfo:
        await client.post("https://example.com/api", {"key": "value"})

    assert excinfo.value.__cause__ is error
    assert mock_session.post.call_count == 1


async def test_http_client_initialization() -> None:
    """Test HTTP client initialization."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    client = HTTPClient(mock_session, "TestAgent/1.0")

    assert client.session == mock_session
    assert client.user_agent == "TestAgent/1.0"
    assert client.timeout == 30


async def test_http_client_custom_settings() -> None:
    """Test HTTP client with custom settings."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    client = HTTPClient(mock_session, "CustomAgent/2.0", timeout=60)

    assert client.timeout == 60


async def test_http_client_get_headers() -> None:
    """Test HTTP client header generation."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    client = HTTPClient(mock_session, "TestAgent/1.0")

    assert client._get_headers() == {
        "Content-Type": "application/x-www-form-urlencoded",
        "Connection": "keep-alive",
        "Accept": "*/*",
        "User-Agent": "TestAgent/1.0",
        "Accept-Language": "en-US,en;q=0.9",
    }


async def test_http_client_get_headers_custom_content_type() -> None:
    """Test HTTP client header generation with custom content type."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    client = HTTPClient(mock_session, "TestAgent/1.0")

    headers = client._get_headers("application/json")
    assert headers["Content-Type"] == "application/json"


async def test_http_client_post_success(set_response_body: Callable[..., None]) -> None:
    """Test successful HTTP POST request."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 200
    set_response_body(mock_response, "<response>Success</response>")
    mock_response.raise_for_status = MagicMock()

    # Create context manager mock
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_context)

    client = HTTPClient(mock_session, "TestAgent/1.0")

    result = await client.post("https://example.com/api", {"key": "value"})

    assert result == "<response>Success</response>"
    assert mock_session.post.call_count == 1


async def test_http_client_post_rejects_oversized_response(
    set_response_body: Callable[..., None],
) -> None:
    """A response above the maximum size fails the request like a connection error."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, "x" * (1024 * 1024 + 1))

    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_context)

    client = HTTPClient(mock_session, "TestAgent/1.0")

    with pytest.raises(
        aiohttp.ClientError, match="Response exceeds the limit of 1048576 bytes"
    ):
        await client.post("https://example.com/api", {"key": "value"})


async def test_http_client_post_does_not_follow_redirects() -> None:
    """A redirect is not followed and fails the request."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 307
    mock_response.raise_for_status = MagicMock()

    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_context)

    client = HTTPClient(mock_session, "TestAgent/1.0")

    with pytest.raises(aiohttp.ClientError, match="Redirect not followed"):
        await client.post("https://example.com/api", {"key": "value"})

    assert mock_session.post.call_args.kwargs["allow_redirects"] is False
    mock_response.content.iter_chunked.assert_not_called()


async def test_http_client_post_with_string_data(
    set_response_body: Callable[..., None],
) -> None:
    """Test HTTP POST request with string data."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 200
    set_response_body(mock_response, "<response>OK</response>")
    mock_response.raise_for_status = MagicMock()

    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_context)

    client = HTTPClient(mock_session, "TestAgent/1.0")

    result = await client.post("https://example.com/api", "raw_data=value")

    assert result == "<response>OK</response>"


def test_build_accept_language_from_constructor() -> None:
    """The language passed to the constructor is used."""
    client = HTTPClient(session=MagicMock(), user_agent="test-agent", language="en-DE")

    assert client._build_accept_language() == "en-DE,en;q=0.9"


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


def test_mask_ug_value_empty_string_returns_empty() -> None:
    """When payload is an empty string, return it unchanged."""
    assert mask_ug_value("") == ""


def test_mask_ug_value_non_string_returns_input() -> None:
    """Non-string payloads should be returned unchanged."""
    assert mask_ug_value(cast(Any, None)) is None
    result: Any = mask_ug_value(cast(Any, 123))
    assert result == 123


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
