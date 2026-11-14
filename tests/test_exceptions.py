"""Test the SYR Connect exceptions."""

from custom_components.syr_connect.exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectError,
    SyrConnectInvalidResponseError,
)
from homeassistant.exceptions import HomeAssistantError


def test_exception_hierarchy() -> None:
    """Test that all exceptions inherit correctly."""
    assert issubclass(SyrConnectError, HomeAssistantError)
    assert issubclass(SyrConnectAuthError, SyrConnectError)
    assert issubclass(SyrConnectConnectionError, SyrConnectError)
    assert issubclass(SyrConnectInvalidResponseError, SyrConnectError)
