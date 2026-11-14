"""Tests for the local JSON API client using fixtures."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001

from datetime import UTC, datetime, timedelta
import json
import logging
from pathlib import Path
from typing import Any, NoReturn, override
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.syr_connect.api_json import SyrConnectJsonAPI
from custom_components.syr_connect.exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectHTTPError,
    SyrConnectInvalidResponseError,
)
from homeassistant.const import __version__ as HA_VERSION

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "json"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture by file name."""
    path = FIXTURES_DIR / name
    with open(path, encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


@pytest.mark.parametrize(
    "fixture",
    [
        "SyrSafeTech_get_all.json",
        "SyrSafeTechV4_old_get_all.json",
        "SyrSafeTechV4_get_all.json",
        "SyrNeoSoft2500_get_all.json",
        "SyrNeoSoft5000_get_all.json",
    ],
)
async def test_json_client_parses_fixture(
    fixture: str, integration_version: str
) -> None:
    """The answer of /get/all is the status of the device, unchanged."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://127.0.0.1:5333/trio/",
        integration_version=integration_version,
    )

    data = load_fixture(fixture)

    # Patch request_json_data to return fixture data
    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        status = await client.get_device_status("local")

    assert status == data


def test_init_with_base_url(integration_version: str) -> None:
    """Test initialization with explicit base_url."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://192.168.1.100:5333/trio/",
        integration_version=integration_version,
    )
    assert client._base_url == "http://192.168.1.100:5333/trio/"
    assert client._session is sess


def test_init_without_base_url(integration_version: str) -> None:
    """Test initialization without base_url (requires host and base_path)."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        integration_version=integration_version,
    )
    assert client._base_url is None
    assert client._host == "192.168.1.100"
    assert client._base_path == "/trio"


def test_build_base_url_with_explicit_base_url(integration_version: str) -> None:
    """Test _build_base_url returns explicit base_url when set."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )
    result = client._build_base_url()
    assert result == "http://test:5333/trio/"


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("192.168.1.100", "http://192.168.1.100:5333/trio"),
        ("syr.local", "http://syr.local:5333/trio"),
        ("fe80::1", "http://[fe80::1]:5333/trio"),
        ("2001:db8::5", "http://[2001:db8::5]:5333/trio"),
        ("fd00::abcd", "http://[fd00::abcd]:5333/trio"),
    ],
)
def test_build_base_url_brackets_ipv6_host(
    host: str, expected: str, integration_version: str
) -> None:
    """IPv6 literals are bracketed; IPv4 and hostnames are left untouched."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        host=host,
        base_path="/trio",
        integration_version=integration_version,
    )
    assert client._build_base_url() == expected


def test_construct_url_with_ipv6_host_is_parseable(integration_version: str) -> None:
    """The final request URL keeps host and port apart for IPv6 devices."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        host="fe80::1",
        base_path="/trio",
        integration_version=integration_version,
    )

    url = client._construct_encoded_url("get", "all")

    assert url.host == "fe80::1"
    assert url.port == 5333
    assert url.path == "/trio/get/all"


def test_build_base_url_without_ip_or_base_path(integration_version: str) -> None:
    """Test _build_base_url returns None when host or base_path missing."""
    sess = MagicMock()

    # Missing both
    client = SyrConnectJsonAPI(sess, integration_version=integration_version)
    assert client._build_base_url() is None

    # Missing base_path
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        integration_version=integration_version,
    )
    assert client._build_base_url() is None

    # Missing host
    client = SyrConnectJsonAPI(
        sess,
        base_path="/trio",
        integration_version=integration_version,
    )
    assert client._build_base_url() is None


def test_build_base_url_constructs_url(integration_version: str) -> None:
    """Test _build_base_url constructs URL from host and base_path."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.50",
        base_path="/trio",
        integration_version=integration_version,
    )
    result = client._build_base_url()
    assert result == "http://192.168.1.50:5333/trio"


def test_is_session_valid_no_last_login(integration_version: str) -> None:
    """Test is_session_valid returns False when session not started."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/",
        integration_version=integration_version,
    )
    assert client.is_session_valid() is False


def test_is_session_valid_expired(integration_version: str) -> None:
    """Test is_session_valid returns False when session expired."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/",
        integration_version=integration_version,
    )
    # Set last login to 31 minutes ago (expired, timeout is 30 min)
    client._last_login = datetime.now(UTC) - timedelta(minutes=31)
    assert client.is_session_valid() is False


def test_is_session_valid_active(integration_version: str) -> None:
    """Test is_session_valid returns True when session active."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/",
        integration_version=integration_version,
    )
    # Set last login to 10 minutes ago (still valid)
    client._last_login = datetime.now(UTC) - timedelta(minutes=10)
    assert client.is_session_valid() is True


async def test_login_no_base_url_raises(integration_version: str) -> None:
    """Test login raises ValueError when base URL cannot be built."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess, integration_version=integration_version
    )  # No host/base_path/base_url
    with pytest.raises(ValueError, match="Base URL not configured"):
        await client.login()


async def test_login_success(integration_version: str) -> None:
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
        base_path="/trio",
        integration_version=integration_version,
    )

    result = await client.login()

    # Verify GET called with login URL pattern
    called_url = str(sess.get.call_args[0][0])
    assert "/set/ADM/(2)f" in called_url
    assert result is True
    assert client._last_login is not None
    assert len(client.projects) == 1


async def test_login_http_error(integration_version: str) -> None:
    """Test login raises exception on HTTP error."""

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
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        integration_version=integration_version,
    )

    with pytest.raises(SyrConnectConnectionError):
        await client.login()


async def test_login_invalid_response_status(integration_version: str) -> None:
    """Test login raises exception when response status is not 'OK'."""

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
        base_path="/trio",
        integration_version=integration_version,
    )

    with pytest.raises(
        SyrConnectAuthError, match="Login failed: Device returned status 'ERROR'"
    ):
        await client.login()


async def test_login_missing_status_key(integration_version: str) -> None:
    """Test login raises exception when response is missing the status key."""

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
        base_path="/trio",
        integration_version=integration_version,
    )

    with pytest.raises(
        SyrConnectAuthError, match="Login failed: Response missing expected key"
    ):
        await client.login()


async def test_login_mima_status(integration_version: str) -> None:
    """Test login raises exception when response status is MIMA."""

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
        base_path="/trio",
        integration_version=integration_version,
    )

    with pytest.raises(
        SyrConnectAuthError,
        match="Login failed: Value .* is outside valid range for command ADM",
    ):
        await client.login()


async def test_login_nsc_status(integration_version: str) -> None:
    """Test login raises exception when response status is NSC."""

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
        base_path="/trio",
        integration_version=integration_version,
    )

    with pytest.raises(
        SyrConnectAuthError, match="Login failed: Command .* does not exist"
    ):
        await client.login()


async def test_login_404_treated_as_not_required(integration_version: str) -> None:
    """Test login treats HTTP 404 as 'login not required' and sets flag."""

    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        integration_version=integration_version,
    )

    # Simulate _execute_http_get raising a connection error for 404 endpoint

    exc = SyrConnectHTTPError("Endpoint not found (HTTP 404)", status=404)
    with patch.object(client, "_execute_http_get", side_effect=exc):
        result = await client.login()

    assert result is True
    assert client._login_required is False


async def test_login_factory_treated_as_required(integration_version: str) -> None:
    """Test login treats response 'FACTORY' as 'login required'."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setADM(2)f": "FACTORY"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/safe-tec",
        integration_version=integration_version,
    )

    result = await client.login()

    assert result is True
    assert client._login_required is True
    assert client._last_login is not None
    assert client.projects and client.projects[0]["id"] == "local"


async def test_login_factory_without_set_prefix(integration_version: str) -> None:
    """Test login accepts response key without 'set' prefix (e.g. Floorsensor firmware).

    Some devices return {"ADM(2)f":"FACTORY"} instead of {"setADM(2)f":"FACTORY"}.
    """
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"ADM(2)f": "FACTORY"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        integration_version=integration_version,
    )

    result = await client.login()

    assert result is True
    assert client._login_required is True
    assert client._last_login is not None
    assert client.projects and client.projects[0]["id"] == "local"


async def test_get_device_status_does_not_call_login_if_not_required(
    integration_version: str,
) -> None:
    """Ensure get_device_status skips login when login not required."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        integration_version=integration_version,
    )

    # Mark that login is known not required
    client._login_required = False
    client.login = AsyncMock()  # type: ignore[method-assign]

    data = {"getAB": "value"}
    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        status = await client.get_device_status("device1")

    # Verify login was NOT called
    client.login.assert_not_called()
    assert status == data


async def test_request_json_data_no_base_url_raises(integration_version: str) -> None:
    """Test request_json_data raises ValueError when base URL not configured."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess, integration_version=integration_version
    )  # No host/base_path/base_url
    with pytest.raises(ValueError, match="Base URL not configured"):
        await client.request_json_data("/get/all")


async def test_request_json_data_non_dict_raises(integration_version: str) -> None:
    """Test request_json_data raises SyrConnectInvalidResponseError when response is not a dict."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value=["not", "a", "dict"])
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(
        SyrConnectInvalidResponseError, match="API returned unexpected payload"
    ):
        await client.request_json_data("/get/all")


async def test_request_json_data_http_error(integration_version: str) -> None:
    """Test request_json_data raises exception on HTTP error."""

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
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(SyrConnectConnectionError):
        await client.request_json_data("/get/all")


async def test_request_json_data_success(integration_version: str) -> None:
    """Test request_json_data returns dict on success."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"getAB": "value", "getCD": "123"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    result = await client.request_json_data("/get/all")

    assert result == {"getAB": "value", "getCD": "123"}


async def test_get_device_status_calls_login(integration_version: str) -> None:
    """Test get_device_status calls login when session invalid and no cached data."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        integration_version=integration_version,
    )

    # Mock login
    client.login = AsyncMock()  # type: ignore[method-assign]

    data = {"getAB": "value", "getCD": "123"}
    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        status = await client.get_device_status("device1")

    # Verify login was called (no cached data)
    client.login.assert_called_once()
    assert status == data


async def test_get_device_status_exception_returns_none(
    integration_version: str,
) -> None:
    """Test get_device_status returns None on exception."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Mock request_json_data to raise exception
    with patch.object(
        client,
        "request_json_data",
        new=AsyncMock(side_effect=ValueError("Network error")),
    ):
        status = await client.get_device_status("device1")

    assert status is None


async def test_set_device_status_no_base_url_raises(integration_version: str) -> None:
    """Test set_device_status raises ValueError when base URL not configured."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess, integration_version=integration_version
    )  # No host/base_path/base_url

    with pytest.raises(ValueError, match="Base URL not configured"):
        await client.set_device_status("device1", [("setAB", "true")])


async def test_set_device_status_strips_set_prefix(integration_version: str) -> None:
    """Test set_device_status strips 'set' prefix from command."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    result = await client.set_device_status("device1", [("setAB", "true")])

    # Verify URL contains "/set/ab/true" (not "/set/setAB/true")
    called_url = str(sess.get.call_args[0][0])
    assert "/set/ab/true" in called_url
    assert "/set/setAB/" not in called_url
    assert result is True


async def test_set_device_status_success(integration_version: str) -> None:
    """Test set_device_status returns True when response status is OK."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setXY123": "OK"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    result = await client.set_device_status("device1", [("XY", "123")])

    assert result is True


async def test_set_device_status_http_error(integration_version: str) -> None:
    """Test set_device_status raises exception on HTTP error."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 403
    mock_response.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=403, message="Forbidden"
        )
    )
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(SyrConnectAuthError):
        await client.set_device_status("device1", [("AB", "false")])


async def test_get_device_status_skips_login_with_base_url(
    integration_version: str,
) -> None:
    """Test get_device_status skips login when explicit base_url provided."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Mark session as valid to verify login still not called
    client._last_login = datetime.now(UTC)
    client.login = AsyncMock()  # type: ignore[method-assign]

    data = {"getAB": "value"}
    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        status = await client.get_device_status("device1")

    # Verify login was NOT called even though we could
    client.login.assert_not_called()
    assert status == {"getAB": "value"}


async def test_request_json_data_logs_nsc_error(
    caplog: pytest.LogCaptureFixture,
    integration_version: str,
) -> None:
    """Test request_json_data logs warning when response contains NSC error code."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"getXYZ": "NSC", "getABC": "value"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with caplog.at_level(logging.WARNING):
        result = await client.request_json_data("/get/all")

    assert result == {"getXYZ": "NSC", "getABC": "value"}
    assert "JSON API: 'getXYZ' Command does not exist (NSC error)" in caplog.text


async def test_request_json_data_logs_mima_error(
    caplog: pytest.LogCaptureFixture,
    integration_version: str,
) -> None:
    """Test request_json_data logs warning when response contains MIMA error code."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    # Use a GET key (not SET) to test warning logging for error codes
    mock_response.json = AsyncMock(return_value={"getPRF": "MIMA", "getABC": "value"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with caplog.at_level(logging.WARNING):
        result = await client.request_json_data("/get/all")

    assert result == {"getPRF": "MIMA", "getABC": "value"}
    assert "JSON API: 'getPRF' Value is outside valid range (MIMA error)" in caplog.text


async def test_set_device_status_raises_on_nsc_error(integration_version: str) -> None:
    """Test set_device_status raises SyrConnectInvalidResponseError when response contains NSC error code."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setINVALIDvalue": "NSC"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(
        SyrConnectInvalidResponseError, match="Command INVALID does not exist"
    ):
        await client.set_device_status("device1", [("INVALID", "value")])


async def test_set_device_status_raises_on_mima_error(integration_version: str) -> None:
    """Test set_device_status raises SyrConnectInvalidResponseError when response contains MIMA error code."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setPRF9999": "MIMA"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(
        SyrConnectInvalidResponseError,
        match="Value 999 is outside valid range for command PRF9",
    ):
        await client.set_device_status("device1", [("PRF9", "999")])


async def test_set_device_status_sends_special_characters_unencoded(
    integration_version: str,
) -> None:
    """Colons and slashes of a value are sent as they are, the firmware decodes nothing."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setRTM02:15": "OK"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Test with time value containing colon (e.g., "02:15")
    result = await client.set_device_status("device1", [("RTM", "02:15")])

    # Verify URL contains literal colon (not percent-encoded) because device
    # firmware does not decode %3A and rejects encoded values.
    called_url = str(sess.get.call_args[0][0])
    assert "/set/rtm/02:15" in called_url
    assert result is True

    # Test with value containing slash - also sent without encoding
    mock_response.json = AsyncMock(return_value={"setCMDvalue/with/slash": "OK"})
    result2 = await client.set_device_status("device1", [("CMD", "value/with/slash")])
    called_url2 = str(sess.get.call_args[0][0])
    assert "value/with/slash" in called_url2
    assert result2 is True


async def test_set_device_status_missing_response_key(
    caplog: pytest.LogCaptureFixture,
    integration_version: str,
) -> None:
    """Test set_device_status handles missing response key gracefully."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"someOtherKey": "OK"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with caplog.at_level(logging.WARNING):
        result = await client.set_device_status("device1", [("TEST", "123")])

    # Should not raise exception, just log warning and return True
    assert result is True
    assert "Response missing expected key 'setTEST123'" in caplog.text


async def test_set_device_status_unknown_status_code(
    caplog: pytest.LogCaptureFixture,
    integration_version: str,
) -> None:
    """Test set_device_status handles unknown status codes gracefully."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"setUNKNOWN42": "WEIRD"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with caplog.at_level(logging.WARNING):
        result = await client.set_device_status("device1", [("UNKNOWN", "42")])

    # Should not raise exception, just log warning and return True
    assert result is True
    assert "Unexpected status 'WEIRD'" in caplog.text


def test_strip_set_prefix_and_cases(integration_version: str) -> None:
    """Test strip set prefix and cases."""
    sess = MagicMock()
    api = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    assert api._strip_set_prefix("setRTM") == "RTM"
    assert api._strip_set_prefix("RTM") == "RTM"
    assert api._strip_set_prefix("setAB") == "AB"
    assert api._strip_set_prefix("setadm") == "adm"


def test_normalize_cmd_for_url(integration_version: str) -> None:
    """Test normalize cmd for url."""
    sess = MagicMock()
    api = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # ADM is special and must remain uppercase
    assert api._normalize_cmd_for_url("ADM") == "ADM"
    assert api._normalize_cmd_for_url("adm") == "ADM"

    # Other commands should be lowercased for URL usage
    assert api._normalize_cmd_for_url("RTM") == "rtm"
    assert api._normalize_cmd_for_url("prf9") == "prf9"


def test_response_key_for(integration_version: str) -> None:
    """Test response key for."""
    sess = MagicMock()
    api = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    assert api._response_key_for("rtm", "02:15") == "setRTM02:15"
    assert api._response_key_for("PRF9", "999") == "setPRF9999"


def test_build_set_url_keeps_value_and_lowercases_command(
    integration_version: str,
) -> None:
    """The value is sent unencoded; the command is lowercase, except ADM."""
    sess = MagicMock()
    api = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # All values are now sent WITHOUT percent-encoding
    url = api._build_set_url("RTM", "02:15")
    assert "/set/rtm/02:15" in str(url)

    url2 = api._build_set_url("ADM", "(2)f")
    # Parentheses are also sent as-is
    assert "/set/ADM/(2)f" in str(url2)


async def test_validate_response_errors_case_sensitive(
    integration_version: str,
) -> None:
    """Test _validate_response_errors requires exact uppercase error codes.

    Uppercase codes should log warnings; any non-uppercase variant
    should raise SyrConnectInvalidResponseError.
    """

    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

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


async def test_validate_response_errors_accepts_error_colon_variant(
    caplog: pytest.LogCaptureFixture,
    integration_version: str,
) -> None:
    """Test _validate_response_errors accepts 'ERROR: CODE' variants and logs warnings."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with caplog.at_level(logging.WARNING):
        client._validate_response_errors({"getXYZ": "ERROR: NSC"}, "http://test")

    assert "JSON API: 'getXYZ' Command does not exist (NSC error)" in caplog.text


async def test_validate_response_errors_handles_split_value_error(
    caplog: pytest.LogCaptureFixture,
    integration_version: str,
) -> None:
    """Test _validate_response_errors handles ValueError from split() gracefully."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    class BadSplit(str):
        __slots__ = ()

        @override
        def split(self, sep: Any = None, maxsplit: Any = -1) -> NoReturn:
            raise ValueError("split failed")

    with caplog.at_level(logging.WARNING):
        client._validate_response_errors(
            {"getXYZ": BadSplit("ERROR: NSC")}, "http://test"
        )

    # Because split failed, code becomes '' and no NSC warning should be logged
    assert "Command does not exist (NSC error)" not in caplog.text


async def test_validate_response_errors_ignores_non_string_values(
    integration_version: str,
) -> None:
    """Test _validate_response_errors ignores non-string values."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Should not raise exceptions for non-string values
    client._validate_response_errors({"key1": 123}, "http://test")
    client._validate_response_errors({"key2": None}, "http://test")
    client._validate_response_errors({"key3": []}, "http://test")
    client._validate_response_errors({"key4": {}}, "http://test")


async def test_get_devices_fetches_and_caches(integration_version: str) -> None:
    """Test that get_devices fetches /get/all and caches response."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    data = load_fixture("SyrSafeTechV4_old_get_all.json")

    # Mock request_json_data to track calls
    fetch_call_count = 0
    original_data = data.copy()

    async def mock_fetch(path: str, timeout: int = 10) -> dict[str, Any]:
        nonlocal fetch_call_count
        fetch_call_count += 1
        return original_data

    with patch.object(
        client, "request_json_data", new=AsyncMock(side_effect=mock_fetch)
    ):
        # Call get_devices - should fetch /get/all
        devices = await client.get_devices("local")
        assert len(devices) == 1
        assert fetch_call_count == 1

        # Response should be cached
        assert client._cached_get_all == original_data

        # Second call to get_device_status should use cache
        status = await client.get_device_status(devices[0]["id"])
        assert status == original_data
        # Should still be 1 because cache was used
        assert fetch_call_count == 1
        # Device dict must include project_id for compatibility with platforms
        assert devices[0]["project_id"] == "local"


async def test_get_device_status_without_cache(integration_version: str) -> None:
    """Test that get_device_status fetches directly if no cached data."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    data = load_fixture("SyrSafeTechV4_old_get_all.json")

    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        # Call get_device_status without calling get_devices first
        status = await client.get_device_status("local")

    assert status == data


async def test_get_devices_uses_frn_fallback(integration_version: str) -> None:
    """Test that get_devices uses getFRN when getSRN is missing."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    data = {"getFRN": "67890", "getOther": "value"}  # No getSRN
    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        devices = await client.get_devices("local")

    assert len(devices) == 1
    assert devices[0]["id"] == "67890"  # Uses getFRN
    assert devices[0]["name"] == "67890"  # Falls back to device_id
    assert devices[0]["project_id"] == "local"


async def test_get_devices_uses_local_device_fallback(integration_version: str) -> None:
    """Test that get_devices uses 'local_device' when no serial available."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    data = {"getOther": "value"}  # No getSRN or getFRN
    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        devices = await client.get_devices("local")

    assert len(devices) == 1
    assert devices[0]["id"] == "local_device"
    assert devices[0]["name"] == "local_device"
    assert devices[0]["project_id"] == "local"


async def test_get_devices_calls_login_when_session_invalid(
    integration_version: str,
) -> None:
    """Test that get_devices calls login when session is invalid (no base_url)."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.1",
        base_path="/trio",
        integration_version=integration_version,
    )

    # Mock login
    client.login = AsyncMock()  # type: ignore[method-assign]

    data = {"getSRN": "12345", "getOther": "value"}
    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        devices = await client.get_devices("local")

    # Should have called login because session is invalid
    client.login.assert_called_once()
    assert len(devices) == 1
    assert devices[0]["id"] == "12345"
    assert devices[0]["project_id"] == "local"


async def test_execute_http_get_404_error(integration_version: str) -> None:
    """Test _execute_http_get raises SyrConnectConnectionError on 404."""

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

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(SyrConnectConnectionError, match="Endpoint not found"):
        await client._execute_http_get("http://test:5333/trio/missing")


async def test_execute_http_get_does_not_follow_redirects(
    integration_version: str,
) -> None:
    """A redirect is not followed and fails the request."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 302
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"getSRN": "12345"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(SyrConnectHTTPError, match="Redirect not followed") as excinfo:
        await client._execute_http_get("http://test:5333/trio/get/all")

    assert excinfo.value.status == 302
    assert sess.get.call_args.kwargs["allow_redirects"] is False
    mock_response.json.assert_not_called()


async def test_execute_http_get_sends_the_user_agent(integration_version: str) -> None:
    """The User-Agent names the integration and Home Assistant, as for the cloud API."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"getSRN": "12345"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    await client._execute_http_get("http://test:5333/trio/get/all")

    assert sess.get.call_args.kwargs["headers"] == {
        "User-Agent": f"syr_connect/{integration_version} HomeAssistant/{HA_VERSION}"
    }


async def test_execute_http_get_timeout_error(integration_version: str) -> None:
    """Test _execute_http_get raises SyrConnectConnectionError on timeout."""

    sess = MagicMock()
    sess.get = MagicMock(side_effect=TimeoutError())

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(
        SyrConnectConnectionError, match=r"Connection failed: TimeoutError\(\)"
    ):
        await client._execute_http_get("http://test:5333/trio/slow")


async def test_execute_http_get_client_error(integration_version: str) -> None:
    """Test _execute_http_get raises SyrConnectConnectionError on aiohttp.ClientError."""

    sess = MagicMock()
    sess.get = MagicMock(side_effect=aiohttp.ClientError("Connection refused"))

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(SyrConnectConnectionError, match="Connection failed"):
        await client._execute_http_get("http://test:5333/trio/test")


async def test_execute_http_get_unexpected_error(integration_version: str) -> None:
    """Test _execute_http_get raises SyrConnectConnectionError on unexpected errors."""

    sess = MagicMock()
    sess.get = MagicMock(side_effect=RuntimeError("Unexpected error"))

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(SyrConnectConnectionError, match="Unexpected error"):
        await client._execute_http_get("http://test:5333/trio/test")


async def test_execute_http_get_logs_error_response_body(
    caplog: pytest.LogCaptureFixture,
    integration_version: str,
) -> None:
    """Test _execute_http_get logs error response body for debugging."""

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

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with caplog.at_level(logging.DEBUG), pytest.raises(SyrConnectConnectionError):
        await client._execute_http_get("http://test:5333/trio/error")

    assert "Error response: 'Server encountered an error'" in caplog.text


async def test_execute_http_get_logs_error_response_read_failure(
    caplog: pytest.LogCaptureFixture,
    integration_version: str,
) -> None:
    """Test _execute_http_get handles error when reading error response body."""

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

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with caplog.at_level(logging.DEBUG), pytest.raises(SyrConnectConnectionError):
        await client._execute_http_get("http://test:5333/trio/error")

    # Should log that it couldn't read the error response
    assert "Could not read error response" in caplog.text


async def test_execute_http_get_reraises_invalid_response_error(
    integration_version: str,
) -> None:
    """Test _execute_http_get re-raises SyrConnectInvalidResponseError without wrapping."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value=[])  # Returns list instead of dict
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # The error should be raised as-is, not wrapped
    with pytest.raises(SyrConnectInvalidResponseError, match="unexpected payload type"):
        await client._execute_http_get("http://test:5333/trio/test")


async def test_construct_encoded_url_no_base_url_raises(
    integration_version: str,
) -> None:
    """Test _construct_encoded_url raises ValueError when base URL is not configured."""
    sess = MagicMock()
    # Create client without base_url, host, or base_path
    client = SyrConnectJsonAPI(sess, integration_version=integration_version)

    with pytest.raises(ValueError, match="Base URL not configured"):
        client._construct_encoded_url("test", "path")


async def test_get_device_status_with_cached_response(integration_version: str) -> None:
    """Test get_device_status uses cached response from previous get_devices call."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Manually set cached response
    cached_data = {"getSRN": "12345", "getTemp": "25"}
    client._cached_get_all = cached_data

    # get_device_status should use the cached data without calling request_json_data
    with patch.object(
        client, "request_json_data", new_callable=AsyncMock
    ) as mock_request:
        status = await client.get_device_status("12345")

    # Should NOT have called request_json_data
    mock_request.assert_not_called()

    # Should return the cached data
    assert status == cached_data


async def test_request_json_data_returns_none_raises(integration_version: str) -> None:
    """Test request_json_data raises error when _execute_http_get returns None unexpectedly."""

    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Mock _execute_http_get to return None even though expect_json=True
    with (
        patch.object(client, "_execute_http_get", return_value=None),
        pytest.raises(SyrConnectInvalidResponseError, match="No data returned"),
    ):
        await client.request_json_data("/get/all")


async def test_login_clears_cached_data(integration_version: str) -> None:
    """Test login clears any cached _get_all data from previous session."""
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
        base_path="/trio",
        integration_version=integration_version,
    )

    # Set some cached data
    client._cached_get_all = {"getSRN": "old_data"}

    # Login should clear the cache
    await client.login()

    assert client._cached_get_all is None


async def test_construct_encoded_url_with_encode_false(
    integration_version: str,
) -> None:
    """Test _construct_encoded_url with encode=False preserves special characters."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Test with encode=False (used for login URL with parentheses)
    url = client._construct_encoded_url("set", "ADM", "(2)f", encode=False)

    # Should contain literal parentheses, not URL-encoded %28 and %29
    assert "(2)f" in str(url)
    assert "%28" not in str(url)
    assert "%29" not in str(url)


async def test_construct_encoded_url_with_encode_true(integration_version: str) -> None:
    """Test _construct_encoded_url with encode=True encodes special characters."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Test with encode=True (used for set commands with special chars)
    url = client._construct_encoded_url("set", "rtm", "02:30", encode=True)

    # Colon should be URL-encoded as %3A
    assert "02%3A30" in str(url)
    assert "02:30" not in str(url)


async def test_request_json_data_strips_leading_slash(integration_version: str) -> None:
    """Test request_json_data strips leading slash from path."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"key": "value"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Call with leading slash
    await client.request_json_data("/get/all")

    # URL should not have double slashes
    called_url = str(sess.get.call_args[0][0])
    assert "trio//get" not in called_url
    assert "trio/get/all" in called_url


async def test_request_json_data_without_leading_slash(
    integration_version: str,
) -> None:
    """Test request_json_data works with path without leading slash."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"key": "value"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Call without leading slash
    await client.request_json_data("get/all")

    # URL should be correct
    called_url = str(sess.get.call_args[0][0])
    assert "trio/get/all" in called_url


async def test_get_devices_skips_login_when_session_valid(
    integration_version: str,
) -> None:
    """Test get_devices skips login when session is still valid."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        integration_version=integration_version,
    )

    # Set valid session
    client._last_login = datetime.now(UTC)

    # Mock request_json_data
    data = {"getSRN": "12345"}
    client.request_json_data = AsyncMock(return_value=data)  # type: ignore[method-assign]

    # Mock login
    client.login = AsyncMock()  # type: ignore[method-assign]

    devices = await client.get_devices("local")

    # Should NOT have called login because session is valid
    client.login.assert_not_called()
    assert devices[0]["project_id"] == "local"


async def test_validate_set_response_missing_key_on_login_raises(
    integration_version: str,
) -> None:
    """When a login set-response is missing the expected key, raise SyrConnectInvalidResponseError."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(SyrConnectInvalidResponseError):
        client._validate_set_response(
            {}, cmd="ADM", value="(2)f", device_id="login", is_login=True
        )


async def test_get_device_status_returns_none_on_invalid_payload(
    integration_version: str,
) -> None:
    """get_device_status should return None when the payload cannot be parsed into a dict."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Ensure no cached response
    client._cached_get_all = None

    # Patch request_json_data to return None which will cause parsing to fail
    with patch.object(client, "request_json_data", new=AsyncMock(return_value=None)):
        result = await client.get_device_status("device123")

    assert result is None


async def test_execute_http_get_401_auth_error(integration_version: str) -> None:
    """Test _execute_http_get raises SyrConnectAuthError on 401/403."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 401
    mock_response.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=401,
            message="Unauthorized",
        )
    )
    mock_response.text = AsyncMock(return_value="Unauthorized")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    with pytest.raises(SyrConnectAuthError):
        await client._execute_http_get("http://test:5333/trio/auth")


def test_validate_set_response_missing_key_nonlogin_returns(
    integration_version: str,
) -> None:
    """When response missing expected key for non-login, do not raise."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Should not raise for non-login missing key
    client._validate_set_response(
        {}, cmd="TEST", value="123", device_id="dev1", is_login=False
    )


async def test_login_skips_when_flag_false(integration_version: str) -> None:
    """If _login_required is False, login() should skip network calls and mark session valid."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Pre-seed that login is known not required
    client._login_required = False

    # Call login - should not attempt network call and should set projects/_last_login
    result = await client.login()

    assert result is True
    assert client._login_required is False
    assert client.projects and client.projects[0]["id"] == "local"
    assert client._last_login is not None


def test_validate_set_response_unknown_status_on_login_raises(
    integration_version: str,
) -> None:
    """When a login set-response returns an unexpected status, raise SyrConnectInvalidResponseError."""

    client = SyrConnectJsonAPI(
        MagicMock(),
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Provide response with expected key but unknown status and is_login=True
    resp_key = client._response_key_for("ADM", "(2)f")
    with pytest.raises(SyrConnectInvalidResponseError):
        client._validate_set_response(
            {resp_key: "WEIRD"},
            cmd="ADM",
            value="(2)f",
            device_id="login",
            is_login=True,
        )


async def test_login_reraises_connection_error(integration_version: str) -> None:
    """login() must re-raise SyrConnectConnectionError."""

    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        integration_version=integration_version,
    )

    # Patch _execute_http_get to raise SyrConnectConnectionError directly
    with (
        patch.object(
            client,
            "_execute_http_get",
            side_effect=SyrConnectConnectionError("network down"),
        ),
        pytest.raises(SyrConnectConnectionError, match="network down"),
    ):
        await client.login()


async def test_get_devices_skips_login_when_login_not_required(
    integration_version: str,
) -> None:
    """get_devices skips login when _login_required is False."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.1",
        base_path="/trio",
        integration_version=integration_version,
    )

    # Explicitly mark login as not required and session as expired
    client._login_required = False
    client._last_login = None

    client.login = AsyncMock()  # type: ignore[method-assign]

    data = {"getSRN": "ABC123", "getFLO": "0"}
    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        devices = await client.get_devices("local")

    # login must NOT have been called
    client.login.assert_not_called()
    assert devices[0]["id"] == "ABC123"
    assert devices[0]["project_id"] == "local"
