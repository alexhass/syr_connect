"""Errors raised by the SYR Connect API clients."""


class SyrConnectError(Exception):
    """Base exception for SYR Connect."""


class SyrConnectAuthError(SyrConnectError):
    """Authentication error."""


class SyrConnectConnectionError(SyrConnectError):
    """Connection error."""


class SyrConnectLoginFailedError(SyrConnectConnectionError):
    """The XML webservice rejected the login (<suc v="false"/>) for another cause than a wrong password.

    The cloud gives the same generic message for an unknown username and during
    outages (see docs/known_issues_xml_api.md, issue 3). A setup can report it as
    invalid credentials; during operation it can be handled like any other connection
    error: the next update logs in again, without a re-authentication.
    """


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
