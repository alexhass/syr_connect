"""HTTP client for the SYR Connect XML API."""

import logging
from typing import Any

import aiohttp

from .const import _SYR_CONNECT_CLIENT_OS_LANGUAGE

_LOGGER = logging.getLogger(__name__)

# Default timeout for HTTP requests (seconds)
_SYR_CONNECT_DEFAULT_HTTP_TIMEOUT = 30


class HTTPClient:
    """HTTP client with error handling."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        user_agent: str,
        timeout: int = _SYR_CONNECT_DEFAULT_HTTP_TIMEOUT,
        language: str = _SYR_CONNECT_CLIENT_OS_LANGUAGE,
    ) -> None:
        """Initialize HTTP client.

        Args:
            session: aiohttp client session
            user_agent: User agent string for requests
            timeout: Request timeout in seconds
            language: Locale like ``de-DE`` for the Accept-Language header
        """
        self.session = session
        self.user_agent = user_agent
        self.timeout = timeout
        self.language = language

    def _build_accept_language(self) -> str:
        """Compute the Accept-Language header value from the instance language.

        Uses ``self.language`` (the Home Assistant locale passed in by the XML API
        client), normalizing underscore locale codes (``de_DE``) to BCP-47 hyphen
        form (``de-DE``), e.g. ``de-DE,de;q=0.9``.
        """
        lang_tag = self.language.replace("_", "-")
        primary = lang_tag.split("-")[0]
        return f"{lang_tag},{primary};q=0.9"

    def _get_headers(
        self, content_type: str = "application/x-www-form-urlencoded"
    ) -> dict[str, str]:
        """Get standard headers for API requests."""
        return {
            "Content-Type": content_type,
            "Connection": "keep-alive",
            "Accept": "*/*",
            "User-Agent": self.user_agent,
            "Accept-Language": self._build_accept_language(),
        }

    async def post(
        self,
        url: str,
        data: dict[str, Any] | str,
        content_type: str = "application/x-www-form-urlencoded",
    ) -> str:
        """Make a POST request.

        Args:
            url: URL to request
            data: Request data (dict or string)
            content_type: Content-Type header value

        Returns:
            Response text

        Raises:
            aiohttp.ClientError: If the request fails
        """
        headers = self._get_headers(content_type)
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        # One attempt only: a failed poll keeps the previous values and the next poll
        # tries again, and a repeated set command could be executed twice
        try:
            _LOGGER.debug("Making POST request to %s", url)
            async with self.session.post(
                url, data=data, headers=headers, timeout=timeout
            ) as response:
                _LOGGER.debug("Response status: %d", response.status)
                response.raise_for_status()
                text = await response.text()
                _LOGGER.debug("Response received (length: %d)", len(text))
                return text
        except (TimeoutError, aiohttp.ClientError) as err:
            # repr: a timeout has no message text
            _LOGGER.error("Request to %s failed: %r", url, err)
            raise aiohttp.ClientError(f"Request to {url} failed: {err!r}") from err
