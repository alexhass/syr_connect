"""Custom exceptions for SYR Connect integration."""

from homeassistant.exceptions import HomeAssistantError


class SyrConnectError(HomeAssistantError):
    """Base exception for SYR Connect."""


class SyrConnectAuthError(SyrConnectError):
    """Authentication error."""


class SyrConnectConnectionError(SyrConnectError):
    """Connection error."""


class SyrConnectSessionExpiredError(SyrConnectConnectionError):
    """The XML webservice rejected the session token (invalid or expired).

    Raised by the response parser for `<sc><msg mtid="1" .../></sc>`
    (see docs/known_issues_xml_api.md, issue 4). The XML API client then logs
    in again and repeats the request once; if it is rejected again, it is
    handled like any other connection error.
    """


class SyrConnectHTTPError(SyrConnectConnectionError):
    """HTTP error with status code information.

    Args:
        msg: Error message
        status: Optional HTTP status code
    """

    def __init__(self, msg: str | None = None, status: int | None = None) -> None:
        """Initialize the error with a message and an optional HTTP status code."""
        super().__init__(msg or "HTTP error")
        self.status = status


class SyrConnectInvalidResponseError(SyrConnectError):
    """Invalid response error."""


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuthError(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class HostInvalidError(HomeAssistantError):
    """Error to indicate the host field value is invalid."""


class HostWithPortError(HostInvalidError):
    """Error to indicate the host field contains a port, which is not allowed (fixed port 5333)."""
