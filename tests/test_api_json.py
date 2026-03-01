"""Tests for the local JSON API client using fixtures."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
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
    """Ensure SyrConnectJsonAPI returns the JSON as status dict when _fetch_json is patched."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://127.0.0.1:5333/local/")

    data = load_fixture(fixture)

    # Patch _fetch_json to return fixture data
    with patch.object(client, "_fetch_json", return_value=data):
        status = await client.get_device_status("local")

    assert isinstance(status, dict)
    # Sanity check: fixture contains at least one getXXX key
    assert any(k.startswith("get") for k in status.keys())


async def test_get_devices_builds_device_entry_from_fixture() -> None:
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://127.0.0.1:5333/local/")

    data = load_fixture("SafeTech_get_all_v4.json")

    with patch.object(client, "_fetch_json", return_value=data):
        devices = await client.get_devices("local")

    assert isinstance(devices, list)
    assert len(devices) == 1
    dev = devices[0]
    assert "id" in dev and dev["id"]
    assert "name" in dev and dev["name"]


def test_init_with_base_url() -> None:
    """Test initialization with explicit base_url."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://192.168.1.100:5333/api/v1/")
    assert client._base_url == "http://192.168.1.100:5333/api/v1/"
    assert client._session is sess


def test_init_without_base_url() -> None:
    """Test initialization without base_url (requires ip and base_path)."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        ip="192.168.1.100",
        base_path="/api/v1/"
    )
    assert client._base_url is None
    assert client._ip == "192.168.1.100"
    assert client._base_path == "/api/v1/"


def test_build_base_url_with_explicit_base_url() -> None:
    """Test _build_base_url returns explicit base_url when set."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")
    result = client._build_base_url()
    assert result == "http://test:5333/api/"


def test_build_base_url_without_ip_or_base_path() -> None:
    """Test _build_base_url returns None when ip or base_path missing."""
    sess = MagicMock()

    # Missing both
    client = SyrConnectJsonAPI(sess)
    assert client._build_base_url() is None

    # Missing base_path
    client = SyrConnectJsonAPI(sess, ip="192.168.1.100")
    assert client._build_base_url() is None

    # Missing ip
    client = SyrConnectJsonAPI(sess, base_path="/api/v1/")
    assert client._build_base_url() is None


def test_build_base_url_constructs_url() -> None:
    """Test _build_base_url constructs URL from ip and base_path."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        ip="192.168.1.50",
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
    client = SyrConnectJsonAPI(sess)  # No ip/base_path/base_url
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
        ip="192.168.1.100",
        base_path="/api/v1/"
    )

    result = await client.login()

    # Verify GET called with login URL pattern
    called_url = sess.get.call_args[0][0]
    assert "/set/ADM/(2)f" in called_url
    assert result is True
    assert client._last_login is not None
    assert len(client.projects) == 1


async def test_login_http_error() -> None:
    """Test login raises exception on HTTP error."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientError("HTTP 401"))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        ip="192.168.1.100",
        base_path="/api/v1/"
    )

    with pytest.raises(aiohttp.ClientError):
        await client.login()


async def test_fetch_json_no_base_url_raises() -> None:
    """Test _fetch_json raises ValueError when base URL not configured."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess)  # No ip/base_path/base_url
    with pytest.raises(ValueError, match="Base URL not configured"):
        await client._fetch_json("get/all")


async def test_fetch_json_non_dict_raises() -> None:
    """Test _fetch_json raises ValueError when response is not a dict."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value=["not", "a", "dict"])
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(ValueError, match="JSON API returned unexpected payload"):
        await client._fetch_json("get/all")


async def test_fetch_json_http_error() -> None:
    """Test _fetch_json raises exception on HTTP error."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientError("HTTP 500"))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(aiohttp.ClientError):
        await client._fetch_json("get/all")


async def test_fetch_json_success() -> None:
    """Test _fetch_json returns dict on success."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"getAB": "value", "getCD": "123"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    result = await client._fetch_json("get/all")

    assert result == {"getAB": "value", "getCD": "123"}


async def test_get_devices_calls_login_when_needed() -> None:
    """Test get_devices calls login when session invalid and no explicit base_url."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        ip="192.168.1.100",
        base_path="/api/v1/"
    )

    # Mock login
    client.login = AsyncMock()

    data = {"getSRN": "12345", "getCNA": "TestDevice"}
    with patch.object(client, "_fetch_json", return_value=data):
        devices = await client.get_devices("project1")

    # Verify login was called
    client.login.assert_called_once()
    assert len(devices) == 1
    assert devices[0]["id"] == "12345"


async def test_get_devices_uses_get_frn_fallback() -> None:
    """Test get_devices uses getFRN when getSRN missing."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    data = {"getFRN": "67890", "getCNA": "Device"}
    with patch.object(client, "_fetch_json", return_value=data):
        devices = await client.get_devices("project1")

    assert len(devices) == 1
    assert devices[0]["id"] == "67890"


async def test_get_devices_fallback_device_id_and_name() -> None:
    """Test get_devices uses fallback values for id and name."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Provide data with no getSRN, getFRN, getCNA, getVER
    data = {"getOtherKey": "value"}
    with patch.object(client, "_fetch_json", return_value=data):
        devices = await client.get_devices("project1")

    assert len(devices) == 1
    # Should fall back to "local_device"
    assert devices[0]["id"] == "local_device"
    assert devices[0]["name"] == "local_device"


async def test_get_device_status_calls_login() -> None:
    """Test get_device_status calls login when session invalid."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        ip="192.168.1.100",
        base_path="/api/v1/"
    )

    client.login = AsyncMock()

    data = {"getAB": "on", "getCD": "123"}
    with patch.object(client, "_fetch_json", return_value=data):
        status = await client.get_device_status("device1")

    client.login.assert_called_once()
    assert status == {"getAB": "on", "getCD": "123"}


async def test_get_device_status_exception_returns_none() -> None:
    """Test get_device_status returns None on exception."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Mock _fetch_json to raise exception
    with patch.object(client, "_fetch_json", side_effect=Exception("Network error")):
        status = await client.get_device_status("device1")

    assert status is None


async def test_set_device_status_no_base_url_raises() -> None:
    """Test set_device_status raises ValueError when base URL not configured."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess)  # No ip/base_path/base_url

    with pytest.raises(ValueError, match="Base URL not configured"):
        await client.set_device_status("device1", "setAB", "on")


async def test_set_device_status_strips_set_prefix() -> None:
    """Test set_device_status strips 'set' prefix from command."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    result = await client.set_device_status("device1", "setAB", "on")

    # Verify URL contains "set/AB/on" (not "set/setAB/on")
    called_url = sess.get.call_args[0][0]
    assert "set/AB/on" in called_url
    assert "set/setAB/" not in called_url
    assert result is True


async def test_set_device_status_success() -> None:
    """Test set_device_status returns True on success."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    result = await client.set_device_status("device1", "XY", "123")

    assert result is True


async def test_set_device_status_http_error() -> None:
    """Test set_device_status raises exception on HTTP error."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientError("HTTP 403"))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    with pytest.raises(aiohttp.ClientError):
        await client.set_device_status("device1", "AB", "off")


async def test_get_devices_skips_login_with_base_url() -> None:
    """Test get_devices skips login when explicit base_url provided."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Mock login as a spy to verify it's not called
    client.login = AsyncMock()

    data = {"getSRN": "123", "getCNA": "Device"}
    with patch.object(client, "_fetch_json", return_value=data):
        devices = await client.get_devices("project1")

    # Verify login was NOT called
    client.login.assert_not_called()
    assert len(devices) == 1


async def test_get_device_status_skips_login_with_base_url() -> None:
    """Test get_device_status skips login when explicit base_url provided."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    # Mark session as valid to verify login still not called
    client._last_login = datetime.now()
    client.login = AsyncMock()

    data = {"getAB": "value"}
    with patch.object(client, "_fetch_json", return_value=data):
        status = await client.get_device_status("device1")

    # Verify login was NOT called even though we could
    client.login.assert_not_called()
    assert status == {"getAB": "value"}


async def test_get_devices_with_get_ver_name_fallback() -> None:
    """Test get_devices uses getVER for name when getCNA missing."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    data = {"getSRN": "12345", "getVER": "v1.2.3"}
    with patch.object(client, "_fetch_json", return_value=data):
        devices = await client.get_devices("project1")

    assert len(devices) == 1
    assert devices[0]["name"] == "v1.2.3"


def test_build_base_url_strips_trailing_slash() -> None:
    """Test _build_base_url adds slash after stripping existing one."""
    sess = MagicMock()
    # Test with trailing slash
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/v1/")
    assert client._build_base_url() == "http://test:5333/api/v1/"

    # Test without trailing slash
    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/v1")
    assert client._build_base_url() == "http://test:5333/api/v1/"


def test_build_base_url_strips_slashes_from_base_path() -> None:
    """Test _build_base_url strips leading/trailing slashes from base_path."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        ip="192.168.1.100",
        base_path="api/v1"  # No slashes
    )
    result = client._build_base_url()
    assert result == "http://192.168.1.100:5333/api/v1/"


async def test_set_device_status_command_without_set_prefix() -> None:
    """Test set_device_status handles command without 'set' prefix correctly."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(sess, base_url="http://test:5333/api/")

    result = await client.set_device_status("device1", "AB", "on")

    # Verify URL contains "set/AB/on"
    called_url = sess.get.call_args[0][0]
    assert "set/AB/on" in called_url
    assert result is True

