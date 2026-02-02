"""Tests for HTTP client."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.syr_connect.http_client import HTTPClient


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
