"""Tests for the local JSON API client using fixtures."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.syr_connect.api_json import SyrConnectJsonAPI
from custom_components.syr_connect.exceptions import SyrConnectInvalidResponseError

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "json"


def load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize(
    "fixture",
    [
        "SafeTech_get_all.json",
        "SafeTech_get_all_v4.json",
        "SafeTech_get_all_v4_copy.json",
        "NeoSoft2500_get_all.json",
    ],
)
async def test_json_client_parses_fixture(fixture: str) -> None:
    """Ensure SyrConnectJsonAPI returns the JSON as status dict when _request_json_data is patched."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://127.0.0.1:5333/local/")

    data = load_fixture(fixture)

    # Patch _request_json_data to return fixture data
    with patch.object(client, "_request_json_data", return_value=data):
        status = await client.get_device_status("local")

    assert isinstance(status, dict)
    # Sanity check: fixture contains at least one getXXX key
    assert any(k.startswith("get") for k in status.keys())


def test_init_with_base_url() -> None:
    """Test initialization with explicit base_url."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://192.168.1.100:5333/api/v1/")
    assert client._base_url == "http://192.168.1.100:5333/api/v1/"
    assert client._session is sess


def test_init_without_base_url() -> None:
    """Test initialization without base_url (requires host and base_path)."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/api/v1/"
    )
    assert client._base_url is None
    assert client._host == "192.168.1.100"
    assert client._base_path == "/api/v1/"


def test_build_base_url_with_explicit_base_url() -> None:
    """Test _build_base_url returns explicit base_url when set."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")
    result = client._build_base_url()
    assert result == "http://test:5333/api/"


def test_build_base_url_without_ip_or_base_path() -> None:
    """Test _build_base_url returns None when host or base_path missing."""
    sess = MagicMock()

    # Missing both
    client = SyrConnectJsonAPI(sess)
    assert client._build_base_url() is None

    # Missing base_path
    client = SyrConnectJsonAPI(sess, host="192.168.1.100")
    assert client._build_base_url() is None

    # Missing host
    client = SyrConnectJsonAPI(sess, base_path="/api/v1/")
    assert client._build_base_url() is None


def test_build_base_url_constructs_url() -> None:
    """Test _build_base_url constructs URL from host and base_path."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.50",
        base_path="/api/v1/"
    )
    result = client._build_base_url()
    assert result == "http://192.168.1.50:5333/api/v1/"


def test_is_session_valid_no_last_login() -> None:
    """Test is_session_valid returns False when session not started."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/")
    assert client.is_session_valid() is False


def test_is_session_valid_expired() -> None:
    """Test is_session_valid returns False when session expired."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/")
    # Set last login to 31 minutes ago (expired, timeout is 30 min)
    client._last_login = datetime.now() - timedelta(minutes=31)
    assert client.is_session_valid() is False


def test_is_session_valid_active() -> None:
    """Test is_session_valid returns True when session active."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/")
    # Set last login to 10 minutes ago (still valid)
    client._last_login = datetime.now() - timedelta(minutes=10)
    assert client.is_session_valid() is True


async def test_login_no_base_url_raises() -> None:
    """Test login raises ValueError when base URL cannot be built."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess)  # No host/base_path/base_url
    with pytest.raises(ValueError, match="Base URL not configured"):
        await client.login()


async def test_login_success() -> None:
    """Test login makes GET request and updates session state."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setADM(2)f": "OK"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/api/v1/"
    )

    result = await client.login()

    # Verify GET called with login URL pattern
    called_url = str(sess.get.call_args[0][0])
    assert "/set/ADM/(2)f" in called_url
    assert result is True
    assert client._last_login is not None
    assert len(client.projects) == 1


async def test_login_http_error() -> None:
    """Test login raises exception on HTTP error."""
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=500,
        message="Internal Server Error"
    ))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/api/v1/"
    )

    with pytest.raises(SyrConnectConnectionError):
        await client.login()


async def test_login_invalid_response_status() -> None:
    """Test login raises exception when response status is not 'OK'."""
    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setADM(2)f": "ERROR"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/api/v1/"
    )

    with pytest.raises(SyrConnectAuthError, match="Login failed: Device returned status 'ERROR'"):
        await client.login()


async def test_login_missing_status_key() -> None:
    """Test login raises exception when response is missing the status key."""
    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"someOtherKey": "value"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/api/v1/"
    )

    with pytest.raises(SyrConnectAuthError, match="Login failed: Response missing expected key"):
        await client.login()


async def test_login_mima_status() -> None:
    """Test login raises exception when response status is MIMA."""
    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setADM(2)f": "MIMA"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/api/v1/"
    )

    with pytest.raises(SyrConnectAuthError, match="Login failed: Value .* is outside valid range for command ADM"):
        await client.login()


async def test_login_nsc_status() -> None:
    """Test login raises exception when response status is NSC."""
    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setADM(2)f": "NSC"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/api/v1/"
    )

    with pytest.raises(SyrConnectAuthError, match="Login failed: Command .* does not exist"):
        await client.login()


async def test_login_404_treated_as_not_required() -> None:
    """Test login treats HTTP 404 as 'login not required' and sets flag."""

    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/api/v1/"
    )

    # Simulate _execute_http_get raising a connection error for 404 endpoint
    from custom_components.syr_connect.exceptions import SyrConnectHTTPError

    exc = SyrConnectHTTPError("Endpoint not found (HTTP 404)", status=404)
    with patch.object(client, "_execute_http_get", side_effect=exc):
        result = await client.login()

    assert result is True
    assert client._login_required is False


async def test_get_device_status_does_not_call_login_if_not_required() -> None:
    """Ensure get_device_status skips login when login not required."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, host="192.168.1.100", base_path="/api/v1/")

    # Mark that login is known not required
    client._login_required = False
    client.login = AsyncMock()

    data = {"getAB": "value"}
    with patch.object(client, "_request_json_data", return_value=data):
        status = await client.get_device_status("device1")

    # Verify login was NOT called
    client.login.assert_not_called()
    assert status == data


async def test_request_json_data_no_base_url_raises() -> None:
    """Test _request_json_data raises ValueError when base URL not configured."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess)  # No host/base_path/base_url
    with pytest.raises(ValueError, match="Base URL not configured"):
        await client._request_json_data("/get/all")


async def test_request_json_data_non_dict_raises() -> None:
    """Test _request_json_data raises SyrConnectInvalidResponseError when response is not a dict."""
    from custom_components.syr_connect.exceptions import SyrConnectInvalidResponseError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value=["not", "a", "dict"])
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectInvalidResponseError, match="API returned unexpected payload"):
        await client._request_json_data("/get/all")


async def test_request_json_data_http_error() -> None:
    """Test _request_json_data raises exception on HTTP error."""
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=500,
        message="Internal Server Error"
    ))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectConnectionError):
        await client._request_json_data("/get/all")


async def test_request_json_data_success() -> None:
    """Test _request_json_data returns dict on success."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"getAB": "value", "getCD": "123"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    result = await client._request_json_data("/get/all")

    assert result == {"getAB": "value", "getCD": "123"}


async def test_get_device_status_calls_login() -> None:
    """Test get_device_status calls login when session invalid and no cached data."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, host="192.168.1.100", base_path="/api/v1/")

    # Mock login
    client.login = AsyncMock()

    data = {"getAB": "value", "getCD": "123"}
    with patch.object(client, "_request_json_data", return_value=data):
        status = await client.get_device_status("device1")

    # Verify login was called (no cached data)
    client.login.assert_called_once()
    assert status == data


async def test_get_device_status_exception_returns_none() -> None:
    """Test get_device_status returns None on exception."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Mock _request_json_data to raise exception
    with patch.object(client, "_request_json_data", side_effect=ValueError("Network error")):
        status = await client.get_device_status("device1")

    assert status is None


async def test_set_device_status_no_base_url_raises() -> None:
    """Test set_device_status raises ValueError when base URL not configured."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess)  # No host/base_path/base_url

    with pytest.raises(ValueError, match="Base URL not configured"):
        await client.set_device_status("device1", "setAB", "true")


async def test_set_device_status_strips_set_prefix() -> None:
    """Test set_device_status strips 'set' prefix from command."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    result = await client.set_device_status("device1", "setAB", "true")

    # Verify URL contains "/set/ab/true" (not "/set/setAB/true")
    called_url = str(sess.get.call_args[0][0])
    assert "/set/ab/true" in called_url
    assert "/set/setAB/" not in called_url
    assert result is True


async def test_set_device_status_success() -> None:
    """Test set_device_status returns True when response status is OK."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setXY123": "OK"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    result = await client.set_device_status("device1", "XY", "123")

    assert result is True


async def test_set_device_status_http_error() -> None:
    """Test set_device_status raises exception on HTTP error."""
    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 403
    mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=403,
        message="Forbidden"
    ))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectAuthError):
        await client.set_device_status("device1", "AB", "false")


async def test_get_device_status_skips_login_with_base_url() -> None:
    """Test get_device_status skips login when explicit base_url provided."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Mark session as valid to verify login still not called
    client._last_login = datetime.now()
    client.login = AsyncMock()

    data = {"getAB": "value"}
    with patch.object(client, "_request_json_data", return_value=data):
        status = await client.get_device_status("device1")

    # Verify login was NOT called even though we could
    client.login.assert_not_called()
    assert status == {"getAB": "value"}


def test_build_base_url_strips_trailing_slash() -> None:
    """Test _build_base_url adds slash after stripping existing one."""
    sess = MagicMock()
    # Test with trailing slash
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/v1/")
    assert client._build_base_url() == "http://test:5333/api/v1/"

    # Test without trailing slash
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/v1")
    assert client._build_base_url() == "http://test:5333/api/v1/"


def test_build_base_url_with_correct_base_path() -> None:
    """Test _build_base_url constructs URL when base_path is correctly formatted."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/api/v1/"  # Correctly formatted with slashes
    )
    result = client._build_base_url()
    assert result == "http://192.168.1.100:5333/api/v1/"


async def test_set_device_status_command_without_set_prefix() -> None:
    """Test set_device_status handles command without 'set' prefix correctly."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    result = await client.set_device_status("device1", "AB", "true")

    # Verify URL contains "/set/ab/true"
    called_url = str(sess.get.call_args[0][0])
    assert "/set/ab/true" in called_url
    assert result is True


async def test_request_json_data_logs_nsc_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test _request_json_data logs warning when response contains NSC error code."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"getXYZ": "NSC", "getABC": "value"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with caplog.at_level(logging.WARNING):
        result = await client._request_json_data("/get/all")

    assert result == {"getXYZ": "NSC", "getABC": "value"}
    assert "JSON API: 'getXYZ' Command does not exist (NSC error)" in caplog.text


async def test_request_json_data_logs_mima_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test _request_json_data logs warning when response contains MIMA error code."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    # Use a GET key (not SET) to test warning logging for error codes
    mock_response.json = AsyncMock(return_value={"getPRF": "MIMA", "getABC": "value"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with caplog.at_level(logging.WARNING):
        result = await client._request_json_data("/get/all")

    assert result == {"getPRF": "MIMA", "getABC": "value"}
    assert "JSON API: 'getPRF' Value is outside valid range (MIMA error)" in caplog.text


async def test_set_device_status_raises_on_nsc_error() -> None:
    """Test set_device_status raises SyrConnectInvalidResponseError when response contains NSC error code."""
    from custom_components.syr_connect.exceptions import SyrConnectInvalidResponseError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setINVALIDvalue": "NSC"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectInvalidResponseError, match="Command INVALID does not exist"):
        await client.set_device_status("device1", "INVALID", "value")


async def test_set_device_status_raises_on_mima_error() -> None:
    """Test set_device_status raises SyrConnectInvalidResponseError when response contains MIMA error code."""
    from custom_components.syr_connect.exceptions import SyrConnectInvalidResponseError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setPRF9999": "MIMA"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectInvalidResponseError, match="Value 999 is outside valid range for command PRF9"):
        await client.set_device_status("device1", "PRF9", "999")


async def test_set_device_status_url_encodes_special_characters() -> None:
    """Test set_device_status URL-encodes special characters in command and value."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setRTM2:15": "OK"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Test with time value containing colon (e.g., "2:15")
    result = await client.set_device_status("device1", "RTM", "2:15")

    # Verify URL contains URL-encoded value (%3A for colon)
    called_url = str(sess.get.call_args[0][0])
    assert "/set/rtm/2%3A15" in called_url
    assert result is True

    # Test with value containing slash
    mock_response.json = AsyncMock(return_value={"setCMDvalue/with/slash": "OK"})
    result2 = await client.set_device_status("device1", "CMD", "value/with/slash")
    called_url2 = str(sess.get.call_args[0][0])
    assert "%2F" in called_url2  # slash should be encoded
    assert result2 is True


async def test_set_device_status_missing_response_key(caplog: pytest.LogCaptureFixture) -> None:
    """Test set_device_status handles missing response key gracefully."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"someOtherKey": "OK"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with caplog.at_level(logging.WARNING):
        result = await client.set_device_status("device1", "TEST", "123")

    # Should not raise exception, just log warning and return True
    assert result is True
    assert "Response missing expected key 'setTEST123'" in caplog.text


async def test_set_device_status_unknown_status_code(caplog: pytest.LogCaptureFixture) -> None:
    """Test set_device_status handles unknown status codes gracefully."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setUNKNOWN42": "WEIRD"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with caplog.at_level(logging.WARNING):
        result = await client.set_device_status("device1", "UNKNOWN", "42")

    # Should not raise exception, just log warning and return True
    assert result is True
    assert "Unexpected status 'WEIRD'" in caplog.text


def test_strip_set_prefix_and_cases():
    sess = MagicMock()
    api = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    assert api._strip_set_prefix("setRTM") == "RTM"
    assert api._strip_set_prefix("RTM") == "RTM"
    assert api._strip_set_prefix("setAB") == "AB"
    assert api._strip_set_prefix("setadm") == "adm"


def test_normalize_cmd_for_url():
    sess = MagicMock()
    api = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # ADM is special and must remain uppercase
    assert api._normalize_cmd_for_url("ADM") == "ADM"
    assert api._normalize_cmd_for_url("adm") == "ADM"

    # Other commands should be lowercased for URL usage
    assert api._normalize_cmd_for_url("RTM") == "rtm"
    assert api._normalize_cmd_for_url("prf9") == "prf9"


def test_response_key_for():
    sess = MagicMock()
    api = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    assert api._response_key_for("rtm", "0:15") == "setRTM0:15"
    assert api._response_key_for("rtm", "2:15") == "setRTM2:15"
    assert api._response_key_for("rtm", "15:15") == "setRTM15:15"
    assert api._response_key_for("PRF9", "999") == "setPRF9999"


def test_build_set_url_encodes_and_cases():
    sess = MagicMock()
    api = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    url = api._build_set_url("RTM", "2:15")
    assert "/set/rtm/2%3A15" in str(url)

    url2 = api._build_set_url("ADM", "(2)f")
    # _build_set_url encodes by default; parentheses should be percent-encoded
    assert "/set/ADM/%282%29f" in str(url2)


async def test_validate_response_errors_case_sensitive() -> None:
    """Test _validate_response_errors requires exact uppercase error codes.

    Uppercase codes should log warnings; any non-uppercase variant
    should raise SyrConnectInvalidResponseError.
    """
    from custom_components.syr_connect.exceptions import SyrConnectInvalidResponseError

    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Uppercase is accepted (no exception)
    client._validate_response_errors({"key_ok": "NSC"}, "http://test")
    client._validate_response_errors({"key_ok2": "MIMA"}, "http://test")

    # Non-uppercase variants are invalid and should raise
    with pytest.raises(SyrConnectInvalidResponseError):
        client._validate_response_errors({"key1": "nsc"}, "http://test")

    with pytest.raises(SyrConnectInvalidResponseError):
        client._validate_response_errors({"key3": "Nsc"}, "http://test")

    with pytest.raises(SyrConnectInvalidResponseError):
        client._validate_response_errors({"key4": "mima"}, "http://test")

    with pytest.raises(SyrConnectInvalidResponseError):
        client._validate_response_errors({"key6": "MiMa"}, "http://test")


async def test_validate_response_errors_ignores_non_string_values() -> None:
    """Test _validate_response_errors ignores non-string values."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Should not raise exceptions for non-string values
    client._validate_response_errors({"key1": 123}, "http://test")
    client._validate_response_errors({"key2": None}, "http://test")
    client._validate_response_errors({"key3": []}, "http://test")
    client._validate_response_errors({"key4": {}}, "http://test")


async def test_get_devices_fetches_and_caches() -> None:
    """Test that get_devices fetches /get/all and caches response."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    data = load_fixture("SafeTech_get_all_v4.json")

    # Mock _request_json_data to track calls
    fetch_call_count = 0
    original_data = data.copy()

    async def mock_fetch(path: str, timeout: int = 10) -> dict[str, Any]:
        nonlocal fetch_call_count
        fetch_call_count += 1
        return original_data

    with patch.object(client, "_request_json_data", side_effect=mock_fetch):
        # Call get_devices - should fetch /get/all
        devices = await client.get_devices("local")
        assert len(devices) == 1
        assert fetch_call_count == 1

        # Response should be cached
        assert client._cached_get_all == original_data

        # Second call to get_device_status should use cache
        status = await client.get_device_status(devices[0]["id"])
        assert isinstance(status, dict)
        # Should still be 1 because cache was used
        assert fetch_call_count == 1


async def test_get_device_status_without_cache() -> None:
    """Test that get_device_status fetches directly if no cached data."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    data = load_fixture("SafeTech_get_all_v4.json")

    with patch.object(client, "_request_json_data", return_value=data):
        # Call get_device_status without calling get_devices first
        status = await client.get_device_status("local")
        assert isinstance(status, dict)
        assert len(status) > 0


async def test_get_devices_uses_frn_fallback() -> None:
    """Test that get_devices uses getFRN when getSRN is missing."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    data = {"getFRN": "67890", "getOther": "value"}  # No getSRN
    with patch.object(client, "_request_json_data", return_value=data):
        devices = await client.get_devices("local")

    assert len(devices) == 1
    assert devices[0]["id"] == "67890"  # Uses getFRN
    assert devices[0]["name"] == "67890"  # Falls back to device_id


async def test_get_devices_uses_local_device_fallback() -> None:
    """Test that get_devices uses 'local_device' when no serial available."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    data = {"getOther": "value"}  # No getSRN or getFRN
    with patch.object(client, "_request_json_data", return_value=data):
        devices = await client.get_devices("local")

    assert len(devices) == 1
    assert devices[0]["id"] == "local_device"
    assert devices[0]["name"] == "local_device"


async def test_get_devices_calls_login_when_session_invalid() -> None:
    """Test that get_devices calls login when session is invalid (no base_url)."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, host="192.168.1.1", base_path="/api/")

    # Mock login
    client.login = AsyncMock()

    data = {"getSRN": "12345", "getOther": "value"}
    with patch.object(client, "_request_json_data", return_value=data):
        devices = await client.get_devices("local")

    # Should have called login because session is invalid
    client.login.assert_called_once()
    assert len(devices) == 1
    assert devices[0]["id"] == "12345"


async def test_execute_http_get_404_error() -> None:
    """Test _execute_http_get raises SyrConnectConnectionError on 404."""
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 404
    mock_response.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=404,
            message="Not Found",
        )
    )
    mock_response.text = AsyncMock(return_value="Endpoint not found")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectConnectionError, match="Endpoint not found"):
        await client._execute_http_get("http://test:5333/api/missing")


async def test_execute_http_get_timeout_error() -> None:
    """Test _execute_http_get raises SyrConnectConnectionError on timeout."""
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    sess = MagicMock()
    sess.get = MagicMock(side_effect=TimeoutError("Request timed out"))

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectConnectionError, match="Connection failed"):
        await client._execute_http_get("http://test:5333/api/slow")


async def test_execute_http_get_client_error() -> None:
    """Test _execute_http_get raises SyrConnectConnectionError on aiohttp.ClientError."""
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    sess = MagicMock()
    sess.get = MagicMock(side_effect=aiohttp.ClientError("Connection refused"))

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectConnectionError, match="Connection failed"):
        await client._execute_http_get("http://test:5333/api/test")


async def test_execute_http_get_unexpected_error() -> None:
    """Test _execute_http_get raises SyrConnectConnectionError on unexpected errors."""
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    sess = MagicMock()
    sess.get = MagicMock(side_effect=RuntimeError("Unexpected error"))

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectConnectionError, match="Unexpected error"):
        await client._execute_http_get("http://test:5333/api/test")


async def test_execute_http_get_logs_error_response_body() -> None:
    """Test _execute_http_get logs error response body for debugging."""
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=500,
            message="Internal Server Error",
        )
    )
    mock_response.text = AsyncMock(return_value="Server encountered an error")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectConnectionError):
        await client._execute_http_get("http://test:5333/api/error")


async def test_execute_http_get_logs_error_response_read_failure(caplog: pytest.LogCaptureFixture) -> None:
    """Test _execute_http_get handles error when reading error response body."""
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=500,
            message="Internal Server Error",
        )
    )
    # Simulate error when trying to read response body
    mock_response.text = AsyncMock(side_effect=Exception("Cannot read response"))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(SyrConnectConnectionError):
            await client._execute_http_get("http://test:5333/api/error")

    # Should log that it couldn't read the error response
    assert "Could not read error response" in caplog.text


async def test_execute_http_get_reraises_invalid_response_error() -> None:
    """Test _execute_http_get re-raises SyrConnectInvalidResponseError without wrapping."""
    from custom_components.syr_connect.exceptions import SyrConnectInvalidResponseError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value=[])  # Returns list instead of dict
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # The error should be raised as-is, not wrapped
    with pytest.raises(SyrConnectInvalidResponseError, match="unexpected payload type"):
        await client._execute_http_get("http://test:5333/api/test")


async def test_construct_encoded_url_no_base_url_raises() -> None:
    """Test _construct_encoded_url raises ValueError when base URL is not configured."""
    sess = MagicMock()
    # Create client without base_url, host, or base_path
    client = SyrConnectJsonAPI(sess)

    with pytest.raises(ValueError, match="Base URL not configured"):
        client._construct_encoded_url("test", "path")


async def test_get_device_status_with_cached_response() -> None:
    """Test get_device_status uses cached response from previous get_devices call."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Manually set cached response
    cached_data = {"getSRN": "12345", "getTemp": "25"}
    client._cached_get_all = cached_data

    # get_device_status should use the cached data without calling _request_json_data
    with patch.object(client, "_request_json_data") as mock_request:
        status = await client.get_device_status("12345")

    # Should NOT have called _request_json_data
    mock_request.assert_not_called()

    # Should return the cached data
    assert status == cached_data


async def test_request_json_data_returns_none_raises() -> None:
    """Test _request_json_data raises error when _execute_http_get returns None unexpectedly."""
    from custom_components.syr_connect.exceptions import SyrConnectInvalidResponseError

    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Mock _execute_http_get to return None even though expect_json=True
    with patch.object(client, "_execute_http_get", return_value=None):
        with pytest.raises(SyrConnectInvalidResponseError, match="No data returned"):
            await client._request_json_data("/get/all")


async def test_login_clears_cached_data() -> None:
    """Test login clears any cached _get_all data from previous session."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setADM(2)f": "OK"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, host="192.168.1.100", base_path="/api/")

    # Set some cached data
    client._cached_get_all = {"getSRN": "old_data"}

    # Login should clear the cache
    await client.login()

    assert client._cached_get_all is None


async def test_construct_encoded_url_with_encode_false() -> None:
    """Test _construct_encoded_url with encode=False preserves special characters."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Test with encode=False (used for login URL with parentheses)
    url = client._construct_encoded_url("set", "ADM", "(2)f", encode=False)

    # Should contain literal parentheses, not URL-encoded %28 and %29
    assert "(2)f" in str(url)
    assert "%28" not in str(url)
    assert "%29" not in str(url)


async def test_construct_encoded_url_with_encode_true() -> None:
    """Test _construct_encoded_url with encode=True encodes special characters."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Test with encode=True (used for set commands with special chars)
    url = client._construct_encoded_url("set", "rtm", "02:30", encode=True)

    # Colon should be URL-encoded as %3A
    assert "02%3A30" in str(url)
    assert "02:30" not in str(url)


async def test_get_device_status_without_cache_with_base_url() -> None:
    """Test get_device_status without cache but with base_url (skips login)."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Mock _request_json_data
    data = {"getSRN": "12345", "getTemp": "25"}
    client._request_json_data = AsyncMock(return_value=data)

    # Should not call login because base_url is set
    client.login = AsyncMock()

    status = await client.get_device_status("12345")

    # Should NOT have called login
    client.login.assert_not_called()

    # Should have fetched data
    assert status == data


async def test_request_json_data_strips_leading_slash() -> None:
    """Test _request_json_data strips leading slash from path."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"key": "value"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Call with leading slash
    await client._request_json_data("/get/all")

    # URL should not have double slashes
    called_url = str(sess.get.call_args[0][0])
    assert "api//get" not in called_url
    assert "api/get/all" in called_url


async def test_request_json_data_without_leading_slash() -> None:
    """Test _request_json_data works with path without leading slash."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"key": "value"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Call without leading slash
    await client._request_json_data("get/all")

    # URL should be correct
    called_url = str(sess.get.call_args[0][0])
    assert "api/get/all" in called_url


async def test_get_devices_skips_login_when_session_valid() -> None:
    """Test get_devices skips login when session is still valid."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, host="192.168.1.100", base_path="/api/")

    # Set valid session
    client._last_login = datetime.now()

    # Mock _request_json_data
    data = {"getSRN": "12345"}
    client._request_json_data = AsyncMock(return_value=data)

    # Mock login
    client.login = AsyncMock()

    await client.get_devices("local")

    # Should NOT have called login because session is valid
    client.login.assert_not_called()


async def test_get_value_success() -> None:
    """Test get_value fetches single value successfully."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"getFLO": 0})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")
    client._last_login = datetime.now()  # Valid session

    result = await client.get_value("flo")

    # Should return the single value dict
    assert result == {"getFLO": 0}

    # Verify correct URL was called
    called_url = str(sess.get.call_args[0][0])
    assert "api/get/flo" in called_url


async def test_get_value_strips_get_prefix() -> None:
    """Test get_value strips 'get' prefix from key."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"getTMP": 25})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")
    client._last_login = datetime.now()  # Valid session

    # Pass key with 'get' prefix
    result = await client.get_value("getTMP")

    # Should return the value
    assert result == {"getTMP": 25}

    # Verify URL has normalized key without 'get' prefix
    called_url = str(sess.get.call_args[0][0])
    assert "api/get/tmp" in called_url


async def test_get_value_calls_login_when_needed() -> None:
    """Test get_value calls login when session is invalid."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, host="192.168.1.100", base_path="/api/")

    # No valid session
    client._last_login = None

    # Mock login
    client.login = AsyncMock()

    # Mock _request_json_data
    client._request_json_data = AsyncMock(return_value={"getAB": 1})

    await client.get_value("AB")

    # Should have called login
    client.login.assert_called_once()


async def test_get_value_missing_key_raises() -> None:
    """Test get_value raises exception when response missing expected key."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    # Response has wrong key
    mock_response.json = AsyncMock(return_value={"getSomeOtherKey": 123})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")
    client._last_login = datetime.now()  # Valid session

    # Should raise SyrConnectInvalidResponseError
    with pytest.raises(SyrConnectInvalidResponseError) as exc_info:
        await client.get_value("FLO")

    assert "Response missing expected key 'getFLO'" in str(exc_info.value)


async def test_get_value_skips_login_with_base_url() -> None:
    """Test get_value skips login when base_url is set (test mode)."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"getSRN": "12345"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    # Use base_url (test mode)
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Mock login to verify it's not called
    client.login = AsyncMock()

    await client.get_value("SRN")

    # Should NOT have called login in test mode
    client.login.assert_not_called()


async def test_validate_set_response_missing_key_on_login_raises() -> None:
    """When a login set-response is missing the expected key, raise SyrConnectInvalidResponseError."""
    client = SyrConnectJsonAPI(MagicMock(), base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectInvalidResponseError):
        client._validate_set_response({}, cmd="ADM", value="(2)f", device_id="login", is_login=True)


async def test_get_device_status_returns_none_on_invalid_payload() -> None:
    """get_device_status should return None when the payload cannot be parsed into a dict."""
    client = SyrConnectJsonAPI(MagicMock(), base_url="http://test:5333/api/")

    # Ensure no cached response
    client._cached_get_all = None

    # Patch _request_json_data to return None which will cause parsing to fail
    with patch.object(client, "_request_json_data", return_value=None):
        result = await client.get_device_status("device123")

    assert result is None


async def test_execute_http_get_401_auth_error() -> None:
    """Test _execute_http_get raises SyrConnectAuthError on 401/403."""
    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 401
    mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=401,
        message="Unauthorized",
    ))
    mock_response.text = AsyncMock(return_value="Unauthorized")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(SyrConnectAuthError):
        await client._execute_http_get("http://test:5333/api/auth")


def test_validate_set_response_missing_key_nonlogin_returns() -> None:
    """When response missing expected key for non-login, do not raise."""
    client = SyrConnectJsonAPI(MagicMock(), base_url="http://test:5333/api/")

    # Should not raise for non-login missing key
    client._validate_set_response({}, cmd="TEST", value="123", device_id="dev1", is_login=False)


async def test_login_skips_when_flag_false() -> None:
    """If _login_required is False, login() should skip network calls and mark session valid."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Pre-seed that login is known not required
    client._login_required = False

    # Call login - should not attempt network call and should set projects/_last_login
    result = await client.login()

    assert result is True
    assert client._login_required is False
    assert client.projects and client.projects[0]["id"] == "local"
    assert client._last_login is not None


def test_validate_set_response_unknown_status_on_login_raises() -> None:
    """When a login set-response returns an unexpected status, raise SyrConnectInvalidResponseError."""
    from custom_components.syr_connect.exceptions import SyrConnectInvalidResponseError

    client = SyrConnectJsonAPI(MagicMock(), base_url="http://test:5333/api/")

    # Provide response with expected key but unknown status and is_login=True
    resp_key = client._response_key_for("ADM", "(2)f")
    with pytest.raises(SyrConnectInvalidResponseError):
        client._validate_set_response({resp_key: "WEIRD"}, cmd="ADM", value="(2)f", device_id="login", is_login=True)


async def test_login_reraises_connection_error() -> None:
    """login() must re-raise SyrConnectConnectionError (line 367-369 coverage)."""
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Patch _execute_http_get to raise SyrConnectConnectionError directly
    with patch.object(
        client,
        "_execute_http_get",
        side_effect=SyrConnectConnectionError("network down"),
    ):
        with pytest.raises(SyrConnectConnectionError, match="network down"):
            await client.login()


async def test_get_device_status_skips_login_when_login_not_required() -> None:
    """get_device_status skips login when _login_required is False (line 453 coverage)."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, host="192.168.1.1", base_path="/api/")

    # Explicitly mark login as not required and session as expired
    client._login_required = False
    client._last_login = None

    client.login = AsyncMock()

    data = {"getSRN": "99999", "getFLO": "0"}
    with patch.object(client, "_request_json_data", return_value=data):
        status = await client.get_device_status("99999")

    # login must NOT have been called
    client.login.assert_not_called()
    assert status == data


async def test_get_value_skips_login_when_login_not_required() -> None:
    """get_value skips login when _login_required is False (line 593 coverage)."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, host="192.168.1.1", base_path="/api/")

    # Explicitly mark login as not required and session as expired
    client._login_required = False
    client._last_login = None

    client.login = AsyncMock()

    with patch.object(client, "_request_json_data", return_value={"getFLO": 42}):
        result = await client.get_value("getFLO")

    # login must NOT have been called
    client.login.assert_not_called()
    assert result == {"getFLO": 42}


async def test_set_device_status_rtm_strips_leading_zero_from_hour() -> None:
    """set_device_status strips leading zero from RTM hour (lines 649, 651-653 coverage)."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setRTM2:30": "OK"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # "02:30" -> leading zero stripped -> "2:30"
    result = await client.set_device_status("device1", "setRTM", "02:30")

    called_url = str(sess.get.call_args[0][0])
    assert "2%3A30" in called_url  # "2:30" URL-encoded, NOT "02:30"
    assert "02%3A30" not in called_url
    assert result is True


async def test_set_device_status_rtm_preserves_single_zero_hour() -> None:
    """set_device_status preserves '0' as hour when it is a single digit (lines 649, 651-653 coverage)."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setRTM0:15": "OK"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # "0:15" -> single-digit zero kept as-is
    result = await client.set_device_status("device1", "setRTM", "0:15")

    called_url = str(sess.get.call_args[0][0])
    assert "0%3A15" in called_url
    assert result is True


async def test_set_device_status_rtm_except_branch() -> None:
    """set_device_status handles unparseable RTM hour gracefully (lines 651-653 except branch)."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    # Value is unchanged ("0xyz:30") because int("0xyz") raises ValueError
    mock_response.json = AsyncMock(return_value={"setRTM0xyz:30": "OK"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # "0xyz:30" -> len("0xyz") > 1 and starts with "0", so int("0xyz") raises -> except branch
    result = await client.set_device_status("device1", "setRTM", "0xyz:30")

    assert result is True


async def test_get_devices_skips_login_when_login_not_required() -> None:
    """get_devices skips login when _login_required is False (line 453 coverage)."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, host="192.168.1.1", base_path="/api/")

    # Explicitly mark login as not required and session as expired
    client._login_required = False
    client._last_login = None

    client.login = AsyncMock()

    data = {"getSRN": "ABC123", "getFLO": "0"}
    with patch.object(client, "_request_json_data", return_value=data):
        devices = await client.get_devices("local")

    # login must NOT have been called
    client.login.assert_not_called()
    assert devices[0]["id"] == "ABC123"
