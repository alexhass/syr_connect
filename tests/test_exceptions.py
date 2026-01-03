"""Test the SYR Connect exceptions."""
import pytest

from syr_connect.exceptions import (
    SyrConnectError,
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectSessionExpiredError,
    SyrConnectInvalidResponseError,
)
from homeassistant.exceptions import HomeAssistantError


def test_exception_hierarchy():
    """Test that all exceptions inherit correctly."""
    assert issubclass(SyrConnectError, HomeAssistantError)
    assert issubclass(SyrConnectAuthError, SyrConnectError)
    assert issubclass(SyrConnectConnectionError, SyrConnectError)
    assert issubclass(SyrConnectSessionExpiredError, SyrConnectError)
    assert issubclass(SyrConnectInvalidResponseError, SyrConnectError)


def test_auth_error():
    """Test authentication error."""
    error = SyrConnectAuthError("Invalid credentials")
    assert str(error) == "Invalid credentials"
    assert isinstance(error, SyrConnectError)


def test_connection_error():
    """Test connection error."""
    error = SyrConnectConnectionError("Cannot connect to API")
    assert str(error) == "Cannot connect to API"
    assert isinstance(error, SyrConnectError)


def test_session_expired_error():
    """Test session expired error."""
    error = SyrConnectSessionExpiredError("Session has expired")
    assert str(error) == "Session has expired"
    assert isinstance(error, SyrConnectError)


def test_invalid_response_error():
    """Test invalid response error."""
    error = SyrConnectInvalidResponseError("Malformed XML")
    assert str(error) == "Malformed XML"
    assert isinstance(error, SyrConnectError)


def test_exception_can_be_caught_as_base():
    """Test that specific exceptions can be caught as base exception."""
    try:
        raise SyrConnectAuthError("Test")
    except SyrConnectError:
        pass  # Should catch it


def test_exception_with_cause():
    """Test exceptions with cause."""
    original = ValueError("Original error")
    
    try:
        raise SyrConnectAuthError("Auth failed") from original
    except SyrConnectAuthError as e:
        assert e.__cause__ == original
