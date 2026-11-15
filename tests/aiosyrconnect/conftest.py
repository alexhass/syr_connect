"""Fixtures of the aiosyrconnect tests."""

from collections.abc import AsyncIterator, Callable
from unittest.mock import MagicMock

import pytest


@pytest.fixture(name="user_agent")
def user_agent_fixture() -> str:
    """Return the User-Agent the tests pass to the API clients."""
    return "aiosyrconnect-tests/1.0"


@pytest.fixture
def set_response_body() -> Callable[..., None]:
    """Return a function that gives a fake HTTP response a body read like the one of aiohttp.

    Usage: set_response_body(response, body, chunk_size=None). Text is sent as UTF-8;
    chunk_size is the size of the chunks the body arrives in, None sends it at once.
    """

    def _set_response_body(
        response: MagicMock, body: str | bytes, *, chunk_size: int | None = None
    ) -> None:
        raw = body.encode() if isinstance(body, str) else body
        size = chunk_size or len(raw) or 1

        async def _iter_chunked(_size: int) -> AsyncIterator[bytes]:
            for start in range(0, len(raw), size):
                yield raw[start : start + size]

        response.content = MagicMock()
        response.content.iter_chunked = _iter_chunked
        response.content_length = None
        response.charset = None

    return _set_response_body
