"""Test the SYR Connect exceptions."""

from custom_components.syr_connect.aiosyrconnect import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectError,
    SyrConnectInvalidResponseError,
)


def test_exception_hierarchy() -> None:
    """Test that all exceptions inherit correctly.

    SyrConnectError does not depend on Home Assistant; the integration turns it into
    the Home Assistant errors.
    """
    assert issubclass(SyrConnectError, Exception)
    assert issubclass(SyrConnectAuthError, SyrConnectError)
    assert issubclass(SyrConnectConnectionError, SyrConnectError)
    assert issubclass(SyrConnectInvalidResponseError, SyrConnectError)
