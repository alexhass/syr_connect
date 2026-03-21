"""Custom exceptions for SYR Connect integration."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError


class SyrConnectError(HomeAssistantError):
    """Base exception for SYR Connect."""


class SyrConnectAuthError(SyrConnectError):
    """Authentication error."""


class SyrConnectConnectionError(SyrConnectError):
    """Connection error."""


class SyrConnectHTTPError(SyrConnectConnectionError):
    """HTTP error with status code information.

    Args:
        msg: Error message
        status: Optional HTTP status code
    """

    def __init__(self, msg: str | None = None, status: int | None = None) -> None:
        super().__init__(msg or "HTTP error")
        self.status = status


class SyrConnectInvalidResponseError(SyrConnectError):
    """Invalid response error."""
