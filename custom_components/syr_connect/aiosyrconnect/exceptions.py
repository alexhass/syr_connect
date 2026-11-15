"""Errors raised by the SYR Connect API clients."""


class SyrConnectError(Exception):
    """Base class of all errors raised by the SYR Connect clients."""


class SyrConnectAuthError(SyrConnectError):
    """The credentials were rejected.

    Raised by the XML API client for a wrong password and by the JSON API client for
    HTTP 401/403 or an ADM request the device does not accept. The caller should ask
    for new credentials.
    """


class SyrConnectConnectionError(SyrConnectError):
    """The cloud or the device could not be reached or gave no usable answer.

    Temporary by nature: the caller can retry later.
    """


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
    """The local JSON API answered with an HTTP error status."""

    def __init__(self, msg: str | None = None, status: int | None = None) -> None:
        """Initialize the error.

        Args:
            msg: Error message; default "HTTP error"
            status: HTTP status code, if known
        """
        super().__init__(msg or "HTTP error")
        self.status = status


class SyrConnectInvalidResponseError(SyrConnectError):
    """An answer was received but cannot be used.

    For example an empty answer of the JSON API, JSON that is no object, an error code
    (NSC, MIMA) for a set command, or a statistics answer that is no XML.
    """
