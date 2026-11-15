"""HTTP client for the SYR Connect XML API and helpers for the API responses."""

import logging
import re
from typing import Any

import aiohttp

from .const import (
    _SYR_CONNECT_API_RESPONSE_SIZE_MAXIMUM,
    _SYR_CONNECT_CLIENT_OS_LANGUAGE,
)

_LOGGER = logging.getLogger(__name__)

# Default timeout for HTTP requests (seconds)
_SYR_CONNECT_DEFAULT_HTTP_TIMEOUT = 30

# Number of bytes read at once from a response body
_SYR_CONNECT_HTTP_CLIENT_RESPONSE_CHUNK_SIZE = 64 * 1024


async def read_response_text(response: aiohttp.ClientResponse) -> str:
    """Read the body of a response as text, up to the maximum response size.

    The body is read in chunks, so that a server or device that sends endless data
    cannot fill the memory. A wrong or missing charset falls back to UTF-8.

    Args:
        response: Response whose body has not been read yet

    Returns:
        The decoded body

    Raises:
        aiohttp.ClientPayloadError: If the body is larger than the maximum response size
    """
    limit = _SYR_CONNECT_API_RESPONSE_SIZE_MAXIMUM
    # The announced size saves reading an oversized body; it is the compressed size and
    # may be missing, so the bytes that arrive are counted as well
    announced = response.content_length
    if announced is not None and announced > limit:
        raise aiohttp.ClientPayloadError(
            f"Response of {announced} bytes exceeds the limit of {limit} bytes"
        )
    body = bytearray()
    async for chunk in response.content.iter_chunked(
        _SYR_CONNECT_HTTP_CLIENT_RESPONSE_CHUNK_SIZE
    ):
        body.extend(chunk)
        if len(body) > limit:
            raise aiohttp.ClientPayloadError(
                f"Response exceeds the limit of {limit} bytes"
            )
    try:
        return body.decode(response.charset or "utf-8")
    except LookupError:
        return body.decode("utf-8")


def mask_ug_value(payload: str) -> str:
    """Redact `ug` attribute values in an XML payload.

    Replaces values like `ug="..."` with `ug="***"` (case-insensitive)
    so session tokens are not leaked in logs or diagnostics.

    The payload is edited as text, not parsed, and `ug="..."` is masked anywhere in it: diagnostics
    may pass truncated or malformed XML, server responses may contain a raw `>` inside attribute
    values, and error messages may quote the token outside any tag. An unterminated value is masked
    up to the end of the string. Non-string and empty payloads are returned unchanged.
    """
    if not isinstance(payload, str) or payload == "":
        return payload
    # The lookbehind keeps `ug` from matching inside longer names such as `xug` or `a:ug`.
    return re.sub(r'(?i)(?<![\w:.-])(ug\s*=\s*")[^"]*', r"\1***", payload)


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

        Uses ``self.language`` (the locale passed in by the XML API
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
            # Redirects are not followed: the request carries the password or the
            # session token, which must not be sent to another address
            async with self.session.post(
                url,
                data=data,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
            ) as response:
                _LOGGER.debug("Response status: %d", response.status)
                response.raise_for_status()
                if 300 <= response.status < 400:
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message="Redirect not followed",
                    )
                text = await read_response_text(response)
                _LOGGER.debug("Response received (length: %d)", len(text))
                return text
        except (TimeoutError, aiohttp.ClientError) as err:
            # Debug only: the caller decides what the user sees, e.g. the coordinator logs a
            # failed update once instead of at every poll. repr: a timeout has no message text
            _LOGGER.debug("Request to %s failed: %r", url, err)
            raise aiohttp.ClientError(f"Request to {url} failed: {err!r}") from err
