"""Tests for the HTTP client helper."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import logging

from custom_components.syr_connect.http_client import HTTPClient


def test_get_headers_accept_language_default_and_custom() -> None:
    """Default Accept-Language when no `language` set, and respects `language` when set."""
    client = HTTPClient(session=MagicMock(), user_agent="test-agent")

    # Default fallback when no language set
    headers_default = client._get_headers()
    assert headers_default["Accept-Language"] == "en-US,en;q=0.9"

    # Setting instance language should affect header
    client.language = "de_DE"
    headers_de = client._get_headers()
    assert headers_de["Accept-Language"] == "de-DE,de;q=0.9"


@pytest.mark.asyncio
async def test_post_raises_on_auth_error_immediately() -> None:
    """If response raises ClientResponseError 401/403, it should not retry and re-raise immediately."""
    # Create a ClientResponseError to be raised from the context manager
    exc = aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=401, message="Unauthorized")

    # Create a fake session whose post returns an async context manager that raises on __aenter__
    fake_cm = AsyncMock()
    async def enter():
        raise exc
    fake_cm.__aenter__.side_effect = enter
    fake_cm.__aexit__.return_value = AsyncMock()

    fake_session = MagicMock()
    fake_session.post.return_value = fake_cm

    client = HTTPClient(session=fake_session, user_agent="test-agent", max_retries=3, timeout=1)

    with pytest.raises(aiohttp.ClientResponseError):
        await client.post("http://example", data={})

    # Ensure we only attempted once (no retries)
    assert fake_session.post.call_count == 1


async def test_http_client_initialization() -> None:
    """Test HTTP client initialization."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    client = HTTPClient(mock_session, "TestAgent/1.0")

    assert client.session == mock_session
    assert client.user_agent == "TestAgent/1.0"
    assert client.max_retries == 3
    assert client.timeout == 30


async def test_http_client_custom_settings() -> None:
    """Test HTTP client with custom settings."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    client = HTTPClient(mock_session, "CustomAgent/2.0", max_retries=5, timeout=60)

    assert client.max_retries == 5
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


async def test_http_client_post_retry_on_timeout() -> None:
    """Test HTTP POST request with retry on timeout."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)

    # First attempt times out, second succeeds
    mock_response_success = AsyncMock()
    mock_response_success.status = 200
    mock_response_success.text = AsyncMock(return_value="<response>Success</response>")
    mock_response_success.raise_for_status = MagicMock()

    mock_context_fail = AsyncMock()
    mock_context_fail.__aenter__ = AsyncMock(side_effect=TimeoutError("Timeout"))

    mock_context_success = AsyncMock()
    mock_context_success.__aenter__ = AsyncMock(return_value=mock_response_success)
    mock_context_success.__aexit__ = AsyncMock(return_value=None)

    mock_session.post = MagicMock(side_effect=[mock_context_fail, mock_context_success])

    client = HTTPClient(mock_session, "TestAgent/1.0", max_retries=3)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await client.post("https://example.com/api", {"key": "value"})

    assert result == "<response>Success</response>"
    assert mock_session.post.call_count == 2


async def test_http_client_post_retry_on_client_error() -> None:
    """Test HTTP POST request with retry on client error."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)

    # First attempt fails with ClientError, second succeeds
    mock_response_success = AsyncMock()
    mock_response_success.status = 200
    mock_response_success.text = AsyncMock(return_value="<response>Success</response>")
    mock_response_success.raise_for_status = MagicMock()

    mock_context_fail = AsyncMock()
    mock_context_fail.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Connection error"))

    mock_context_success = AsyncMock()
    mock_context_success.__aenter__ = AsyncMock(return_value=mock_response_success)
    mock_context_success.__aexit__ = AsyncMock(return_value=None)

    mock_session.post = MagicMock(side_effect=[mock_context_fail, mock_context_success])

    client = HTTPClient(mock_session, "TestAgent/1.0", max_retries=3)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await client.post("https://example.com/api", {"key": "value"})

    assert result == "<response>Success</response>"
    assert mock_session.post.call_count == 2


async def test_http_client_post_max_retries_exceeded() -> None:
    """Test HTTP POST request fails after max retries."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)

    # All attempts fail
    mock_context_fail = AsyncMock()
    mock_context_fail.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Connection error"))

    mock_session.post = MagicMock(return_value=mock_context_fail)

    client = HTTPClient(mock_session, "TestAgent/1.0", max_retries=2)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(aiohttp.ClientError, match="Connection error"):
            await client.post("https://example.com/api", {"key": "value"})

    assert mock_session.post.call_count == 2


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


async def test_http_client_post_exponential_backoff() -> None:
    """Test HTTP POST request uses exponential backoff."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)

    # First two attempts fail, third succeeds
    mock_response_success = AsyncMock()
    mock_response_success.status = 200
    mock_response_success.text = AsyncMock(return_value="<response>Success</response>")
    mock_response_success.raise_for_status = MagicMock()

    mock_context_fail = AsyncMock()
    mock_context_fail.__aenter__ = AsyncMock(side_effect=TimeoutError("Timeout"))

    mock_context_success = AsyncMock()
    mock_context_success.__aenter__ = AsyncMock(return_value=mock_response_success)
    mock_context_success.__aexit__ = AsyncMock(return_value=None)

    mock_session.post = MagicMock(side_effect=[mock_context_fail, mock_context_fail, mock_context_success])

    client = HTTPClient(mock_session, "TestAgent/1.0", max_retries=3)

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await client.post("https://example.com/api", {"key": "value"})

    assert result == "<response>Success</response>"
    # Verify exponential backoff: 2^0 = 1s, 2^1 = 2s
    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list[0][0][0] == 1  # First retry: 1 second
    assert mock_sleep.call_args_list[1][0][0] == 2  # Second retry: 2 seconds


async def test_http_client_post_zero_retries_raises() -> None:
    """If max_retries is zero, the loop is skipped and final raise occurs."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    client = HTTPClient(mock_session, "TestAgent/1.0", max_retries=0)

    with pytest.raises(aiohttp.ClientError, match="Request failed after all retries"):
        await client.post("https://example.com/api", {"key": "value"})


def test_build_accept_language_exception_fallback(caplog) -> None:
    """If computing Accept-Language raises, fallback to default is used and error logged."""
    client = HTTPClient(session=MagicMock(), user_agent="test-agent")

    class BadLang:
        def replace(self, *args, **kwargs):
            raise RuntimeError("boom")

    client.language = BadLang()
    caplog.set_level(logging.ERROR)

    result = client._build_accept_language()

    assert result == "en-US,en;q=0.9"
    assert "Failed to determine Accept-Language" in caplog.text
