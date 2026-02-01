"""Custom exceptions for SYR Connect integration."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError


class SyrConnectError(HomeAssistantError):
    """Base exception for SYR Connect."""


class SyrConnectAuthError(SyrConnectError):
    """Authentication error."""


class SyrConnectConnectionError(SyrConnectError):
    """Connection error."""


class SyrConnectInvalidResponseError(SyrConnectError):
    """Invalid response error."""
