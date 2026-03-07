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
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    result = await client.set_device_status("device1", "setAB", "true")

    # Verify URL contains "/set/AB/true" (not "/set/setAB/true")
    called_url = str(sess.get.call_args[0][0])
    assert "/set/AB/true" in called_url
    assert "/set/setAB/" not in called_url
    assert result is True


async def test_set_device_status_success() -> None:
    """Test set_device_status returns True on success."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
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
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    result = await client.set_device_status("device1", "AB", "true")

    # Verify URL contains "/set/AB/true"
    called_url = str(sess.get.call_args[0][0])
    assert "/set/AB/true" in called_url
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
    assert "Command 'getXYZ' does not exist (NSC error)" in caplog.text


async def test_request_json_data_logs_mima_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test _request_json_data logs warning when response contains MIMA error code."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setPRF9": "MIMA", "getABC": "value"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with caplog.at_level(logging.WARNING):
        result = await client._request_json_data("/set/prf9/invalid")

    assert result == {"setPRF9": "MIMA", "getABC": "value"}
    assert "Value for 'setPRF9' is outside valid range (MIMA error)" in caplog.text


async def test_set_device_status_logs_nsc_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test set_device_status logs warning when response contains NSC error code."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setINVALID": "NSC"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with caplog.at_level(logging.WARNING):
        result = await client.set_device_status("device1", "INVALID", "value")

    assert result is True
    assert "Command 'setINVALID' does not exist (NSC error)" in caplog.text


async def test_set_device_status_logs_mima_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test set_device_status logs warning when response contains MIMA error code."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setPRF9": "mima"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with caplog.at_level(logging.WARNING):
        result = await client.set_device_status("device1", "PRF9", "999")

    assert result is True
    assert "Value for 'setPRF9' is outside valid range (MIMA error)" in caplog.text


async def test_set_device_status_url_encodes_special_characters() -> None:
    """Test set_device_status URL-encodes special characters in command and value."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Test with time value containing colon (e.g., "02:15")
    result = await client.set_device_status("device1", "RTM", "02:15")

    # Verify URL contains URL-encoded value (%3A for colon)
    called_url = sess.get.call_args[0][0]
    assert "/set/RTM/02%3A15" in called_url
    assert result is True

    # Test with value containing slash
    result2 = await client.set_device_status("device1", "CMD", "value/with/slash")
    called_url2 = sess.get.call_args[0][0]
    assert "%2F" in called_url2  # slash should be encoded
    assert result2 is True


async def test_validate_response_errors_case_insensitive() -> None:
    """Test _validate_response_errors handles case-insensitive error codes."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Should not raise any exceptions, just log warnings
    client._validate_response_errors({"key1": "nsc"}, "http://test")
    client._validate_response_errors({"key2": "NSC"}, "http://test")
    client._validate_response_errors({"key3": "Nsc"}, "http://test")
    client._validate_response_errors({"key4": "mima"}, "http://test")
    client._validate_response_errors({"key5": "MIMA"}, "http://test")
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


async def test_get_devices_uses_custom_device_name() -> None:
    """Test that get_devices uses custom device name if provided."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/", device_name="My Custom Device")

    data = {"getSRN": "12345", "getOther": "value"}
    with patch.object(client, "_request_json_data", return_value=data):
        devices = await client.get_devices("local")

    assert len(devices) == 1
    assert devices[0]["id"] == "12345"  # Real serial
    assert devices[0]["name"] == "My Custom Device"  # Custom name


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

