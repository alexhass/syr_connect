"""Tests for the HTTP client helper."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001

import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.syr_connect.http_client import HTTPClient


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

    headers = client._get_headers()
    assert headers["User-Agent"] == "TestAgent/1.0"
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert "Connection" in headers
    assert "Accept" in headers


async def test_http_client_get_headers_custom_content_type() -> None:
    """Test HTTP client header generation with custom content type."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    client = HTTPClient(mock_session, "TestAgent/1.0")

    headers = client._get_headers("application/json")
    assert headers["Content-Type"] == "application/json"


async def test_http_client_post_success() -> None:
    """Test successful HTTP POST request."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="<response>Success</response>")
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
    mock_response.text.assert_not_called()


async def test_http_client_post_with_string_data() -> None:
    """Test HTTP POST request with string data."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="<response>OK</response>")
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


def test_build_accept_language_assignment_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If assigning the cached attribute fails, the computed value is returned."""
    mock_session = MagicMock()
    client = HTTPClient(session=mock_session, user_agent="test-agent")

    # Capture original __setattr__ so our broken setter can delegate for other attributes
    orig_setattr = HTTPClient.__setattr__

    def broken_setattr(self: Any, name: Any, value: Any) -> Any:
        if name == "_accept_language":
            raise RuntimeError("cannot assign")
        return orig_setattr(self, name, value)

    # Patch class __setattr__ to simulate assignment failure for the cache
    monkeypatch.setattr(HTTPClient, "__setattr__", broken_setattr)

    # Setting language should still work (broken_setattr delegates for non-_accept_language)
    client.language = "de_DE"

    # Should compute and return the header even though caching assignment fails
    assert client._build_accept_language() == "de-DE,de;q=0.9"
