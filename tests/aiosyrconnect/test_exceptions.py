"""Tests of the errors of the library."""

from custom_components.syr_connect.aiosyrconnect import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectError,
    SyrConnectHTTPError,
    SyrConnectInvalidResponseError,
    SyrConnectLoginFailedError,
    SyrConnectSessionExpiredError,
)


def test_exception_hierarchy() -> None:
    """Every error of the library is a SyrConnectError, so a caller can catch them all.

    The login, session and HTTP errors are connection errors: the caller can retry later.
    """
    assert issubclass(SyrConnectError, Exception)
    assert issubclass(SyrConnectAuthError, SyrConnectError)
    assert issubclass(SyrConnectConnectionError, SyrConnectError)
    assert issubclass(SyrConnectInvalidResponseError, SyrConnectError)
    assert issubclass(SyrConnectLoginFailedError, SyrConnectConnectionError)
    assert issubclass(SyrConnectSessionExpiredError, SyrConnectConnectionError)
    assert issubclass(SyrConnectHTTPError, SyrConnectConnectionError)


def test_http_error_keeps_the_status() -> None:
    """The HTTP status of the local API is kept on the error."""
    error = SyrConnectHTTPError("Endpoint not found (HTTP 404)", status=404)
    assert error.status == 404
    assert str(error) == "Endpoint not found (HTTP 404)"
    assert str(SyrConnectHTTPError()) == "HTTP error"
