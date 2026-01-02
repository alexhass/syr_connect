"""HTTP client with retry logic for SYR Connect API."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class HTTPClient:
    """HTTP client with built-in retry logic and error handling."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        user_agent: str,
        max_retries: int = 3,
        timeout: int = 30,
    ) -> None:
        """Initialize HTTP client.

        Args:
            session: aiohttp client session
            user_agent: User agent string for requests
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        """
        self.session = session
        self.user_agent = user_agent
        self.max_retries = max_retries
        self.timeout = timeout

    def _get_headers(self, content_type: str = 'application/x-www-form-urlencoded') -> dict[str, str]:
        """Get standard headers for API requests.

        Args:
            content_type: Content-Type header value

        Returns:
            Dictionary of headers
        """
        return {
            'Content-Type': content_type,
            'Connection': 'keep-alive',
            'Accept': '*/*',
            'User-Agent': self.user_agent,
            'Accept-Language': 'de-DE,de;q=0.9',
        }

    async def post(
        self,
        url: str,
        data: dict[str, Any] | str,
        content_type: str = 'application/x-www-form-urlencoded',
    ) -> str:
        """Make POST request with retry logic.

        Args:
            url: URL to request
            data: Request data (dict or string)
            content_type: Content-Type header value

        Returns:
            Response text

        Raises:
            aiohttp.ClientError: If request fails after all retries
        """
        headers = self._get_headers(content_type)
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        for attempt in range(self.max_retries):
            try:
                _LOGGER.debug(
                    "Making POST request to %s (attempt %d/%d)",
                    url, attempt + 1, self.max_retries
                )

                async with self.session.post(
                    url, data=data, headers=headers, timeout=timeout
                ) as response:
                    _LOGGER.debug("Response status: %d", response.status)
                    response.raise_for_status()
                    text = await response.text()
                    _LOGGER.debug("Response received (length: %d)", len(text))
                    return text

            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                is_last_attempt = attempt == self.max_retries - 1

                if is_last_attempt:
                    _LOGGER.error("Request failed after %d attempts: %s", self.max_retries, err)
                    raise

                # Calculate backoff time (exponential: 1s, 2s, 4s, ...)
                backoff_time = 2 ** attempt
                _LOGGER.warning(
                    "Request failed (attempt %d/%d): %s. Retrying in %ds...",
                    attempt + 1, self.max_retries, err, backoff_time
                )
                await asyncio.sleep(backoff_time)

        # Should never reach here, but for type safety
        raise aiohttp.ClientError("Request failed after all retries")
