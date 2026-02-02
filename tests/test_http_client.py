"""Tests for HTTP client."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.syr_connect.http_client import HTTPClient


async def test_http_client_post_success() -> None:
    """Test successful HTTP POST request."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="<response>Success</response>")
    mock_response.raise_for_status = MagicMock()
    
    mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))
    
    client = HTTPClient(mock_session, "TestAgent/1.0")
    
    result = await client.post("https://example.com/api", {"key": "value"})
    
    assert result == "<response>Success</response>"


async def test_http_client_post_retry() -> None:
    """Test HTTP POST request with retry logic."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    
    # First attempt fails, second succeeds
    mock_response_fail = AsyncMock()
    mock_response_fail.raise_for_status = MagicMock(side_effect=aiohttp.ClientError("Error"))
    
    mock_response_success = AsyncMock()
    mock_response_success.status = 200
    mock_response_success.text = AsyncMock(return_value="<response>Success</response>")
    mock_response_success.raise_for_status = MagicMock()
    
    mock_session.post = MagicMock(side_effect=[
        AsyncMock(__aenter__=AsyncMock(return_value=mock_response_fail)),
        AsyncMock(__aenter__=AsyncMock(return_value=mock_response_success)),
    ])
    
    client = HTTPClient(mock_session, "TestAgent/1.0", max_retries=3)
    
    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await client.post("https://example.com/api", {"key": "value"})
    
    assert result == "<response>Success</response>"
    assert mock_session.post.call_count == 2


async def test_http_client_post_max_retries() -> None:
    """Test HTTP POST request exceeds max retries."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    
    mock_response_fail = AsyncMock()
    mock_response_fail.raise_for_status = MagicMock(side_effect=aiohttp.ClientError("Error"))
    
    mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response_fail)))
    
    client = HTTPClient(mock_session, "TestAgent/1.0", max_retries=2)
    
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(aiohttp.ClientError):
            await client.post("https://example.com/api", {"key": "value"})
    
    assert mock_session.post.call_count == 2
