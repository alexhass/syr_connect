"""Tests of the errors of the library."""

from unittest.mock import MagicMock

import aiohttp
import pytest

from custom_components.syr_connect.aiosyrconnect import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectDeviceNotFoundError,
    SyrConnectError,
    SyrConnectHTTPError,
    SyrConnectInvalidResponseError,
    SyrConnectLoginFailedError,
    SyrConnectSessionExpiredError,
    is_network_error,
)


def test_exception_hierarchy() -> None:
    """Every error of the library is a SyrConnectError, so a caller can catch them all.

    The login, session and HTTP errors are connection errors: the caller can retry later.
    """
    assert issubclass(SyrConnectError, Exception)
    assert issubclass(SyrConnectAuthError, SyrConnectError)
    assert issubclass(SyrConnectConnectionError, SyrConnectError)
    assert issubclass(SyrConnectInvalidResponseError, SyrConnectError)
    assert issubclass(SyrConnectDeviceNotFoundError, SyrConnectError)
    assert issubclass(SyrConnectLoginFailedError, SyrConnectConnectionError)
    assert issubclass(SyrConnectSessionExpiredError, SyrConnectConnectionError)
    assert issubclass(SyrConnectHTTPError, SyrConnectConnectionError)


def test_http_error_keeps_the_status() -> None:
    """The HTTP status of the local API is kept on the error."""
    error = SyrConnectHTTPError("Endpoint not found (HTTP 404)", status=404)
    assert error.status == 404
    assert str(error) == "Endpoint not found (HTTP 404)"
    assert str(SyrConnectHTTPError()) == "HTTP error"


def _wrapped(err: BaseException) -> SyrConnectConnectionError:
    """Return a connection error that wraps an error twice, like the XML API client."""
    try:
        try:
            try:
                raise err
            except (aiohttp.ClientError, TimeoutError) as inner:
                raise aiohttp.ClientError("Request failed") from inner
        except aiohttp.ClientError as outer:
            raise SyrConnectConnectionError("Connection failed") from outer
    except SyrConnectConnectionError as wrapped:
        return wrapped


def _connector_error(error_class: type[aiohttp.ClientConnectorError]) -> BaseException:
    """Return an aiohttp connector error of the given class."""
    return error_class(MagicMock(), OSError(-2, "Name or service not known"))


@pytest.mark.parametrize(
    ("err", "expected"),
    [
        (_connector_error(aiohttp.ClientConnectorDNSError), True),
        (_connector_error(aiohttp.ClientConnectorError), True),
        (_connector_error(aiohttp.ClientSSLError), False),
        (TimeoutError(), False),
        (aiohttp.ClientError("Server disconnected"), False),
    ],
)
def test_is_network_error(err: BaseException, expected: bool) -> None:
    """DNS and connect errors are network errors, also when wrapped; TLS errors and timeouts are not."""
    assert is_network_error(_wrapped(err)) is expected


def test_is_network_error_without_cause() -> None:
    """An error without a cause, e.g. an unusable answer, is no network error."""
    assert (
        is_network_error(SyrConnectConnectionError("Invalid login response")) is False
    )
