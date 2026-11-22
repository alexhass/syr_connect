"""Tests of the client of the local JSON API."""

from collections.abc import Callable

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001
from datetime import UTC, datetime, timedelta
import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlsplit

import aiohttp
import pytest

from custom_components.syr_connect.aiosyrconnect import (
    MODEL_SIGNATURES,
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectHTTPError,
    SyrConnectInvalidResponseError,
    SyrConnectJsonAPI,
)

# Logger of the library package
_LIBRARY_LOGGER = SyrConnectJsonAPI.__module__.rpartition(".")[0]

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "json"


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
async def test_json_client_parses_fixture(fixture: str, user_agent: str) -> None:
    """The answer of /get/all is the status of the device, unchanged."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://127.0.0.1:5333/trio/",
        user_agent=user_agent,
    )

    data = load_fixture(fixture)

    # Patch request_json_data to return fixture data
    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        status = await client.get_device_status("local")

    assert status == data


def test_init_with_base_url(user_agent: str) -> None:
    """Test initialization with explicit base_url."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://192.168.1.100:5333/trio/",
        user_agent=user_agent,
    )
    assert client._base_url == "http://192.168.1.100:5333/trio/"
    assert client._session is sess


def test_init_without_base_url(user_agent: str) -> None:
    """Test initialization without base_url (requires host and base_path)."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        user_agent=user_agent,
    )
    assert client._base_url is None
    assert client._host == "192.168.1.100"
    assert client._base_path == "/trio"


@pytest.mark.parametrize(
    ("name", "base_path"),
    [
        ("neosoft5000", "/neosoft"),
        ("pontosbase", "/pontos-base"),
        # A model without local API has no path, like a client without base_path
        ("safetplus", None),
    ],
)
def test_init_with_model_takes_its_base_path(
    name: str, base_path: str | None, user_agent: str
) -> None:
    """The model gives the local path of the JSON API; base_path is ignored with it."""
    model = next(signature for signature in MODEL_SIGNATURES if signature.name == name)

    client = SyrConnectJsonAPI(
        MagicMock(),
        host="192.168.1.100",
        base_path="/ignored",
        model=model,
        user_agent=user_agent,
    )

    assert client._base_path == base_path


def test_clear_value_is_decimal(user_agent: str) -> None:
    """The device acknowledges a notification or warning (setNOT, setWRN) with 255."""
    client = SyrConnectJsonAPI(MagicMock(), host="192.168.1.100", user_agent=user_agent)

    assert client.clear_value == 255


@pytest.mark.parametrize("login_required", [None, True, False])
def test_login_required_is_the_stored_value(
    login_required: bool | None, user_agent: str
) -> None:
    """Whether the device needs ADM is unknown until the caller passes a stored value."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        host="192.168.1.100",
        login_required=login_required,
        user_agent=user_agent,
    )

    assert client.login_required is login_required


def test_build_base_url_with_explicit_base_url(user_agent: str) -> None:
    """Test _build_base_url returns explicit base_url when set."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
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
    host: str, expected: str, user_agent: str
) -> None:
    """IPv6 literals are bracketed; IPv4 and hostnames are left untouched."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        host=host,
        base_path="/trio",
        user_agent=user_agent,
    )
    assert client._build_base_url() == expected


def test_construct_url_with_ipv6_host_is_parseable(user_agent: str) -> None:
    """The final request URL keeps host and port apart for IPv6 devices."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        host="fe80::1",
        base_path="/trio",
        user_agent=user_agent,
    )

    url = urlsplit(client._construct_url("get", "all"))

    assert url.hostname == "fe80::1"
    assert url.port == 5333
    assert url.path == "/trio/get/all"


def test_build_base_url_without_ip_or_base_path(user_agent: str) -> None:
    """Test _build_base_url returns None when host or base_path missing."""
    sess = MagicMock()

    # Missing both
    client = SyrConnectJsonAPI(sess, user_agent=user_agent)
    assert client._build_base_url() is None

    # Missing base_path
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        user_agent=user_agent,
    )
    assert client._build_base_url() is None

    # Missing host
    client = SyrConnectJsonAPI(
        sess,
        base_path="/trio",
        user_agent=user_agent,
    )
    assert client._build_base_url() is None


def test_build_base_url_constructs_url(user_agent: str) -> None:
    """Test _build_base_url constructs URL from host and base_path."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.50",
        base_path="/trio",
        user_agent=user_agent,
    )
    result = client._build_base_url()
    assert result == "http://192.168.1.50:5333/trio"


def test_is_session_valid_no_last_login(user_agent: str) -> None:
    """Test is_session_valid returns False when session not started."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/",
        user_agent=user_agent,
    )
    assert client.is_session_valid() is False


def test_is_session_valid_expired(user_agent: str) -> None:
    """Test is_session_valid returns False when session expired."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/",
        user_agent=user_agent,
    )
    # Set last login to 31 minutes ago (expired, timeout is 30 min)
    client._last_login = datetime.now(UTC) - timedelta(minutes=31)
    assert client.is_session_valid() is False


def test_is_session_valid_active(user_agent: str) -> None:
    """Test is_session_valid returns True when session active."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/",
        user_agent=user_agent,
    )
    # Set last login to 10 minutes ago (still valid)
    client._last_login = datetime.now(UTC) - timedelta(minutes=10)
    assert client.is_session_valid() is True


async def test_login_no_base_url_raises(user_agent: str) -> None:
    """Test login raises ValueError when base URL cannot be built."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess, user_agent=user_agent
    )  # No host/base_path/base_url
    with pytest.raises(ValueError, match="Base URL not configured"):
        await client.login()


async def test_login_success(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test login makes GET request and updates session state."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"setADM(2)f": "OK"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        user_agent=user_agent,
    )

    result = await client.login()

    # Verify GET called with login URL pattern
    called_url = str(sess.get.call_args[0][0])
    assert "/set/ADM/(2)f" in called_url
    assert result is True
    assert client._last_login is not None
    assert len(client.projects) == 1


async def test_login_http_error(user_agent: str) -> None:
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
        user_agent=user_agent,
    )

    with pytest.raises(SyrConnectConnectionError):
        await client.login()


async def test_login_invalid_response_status(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test login raises exception when response status is not 'OK'."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"setADM(2)f": "ERROR"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        user_agent=user_agent,
    )

    with pytest.raises(
        SyrConnectAuthError, match="Login failed: Device returned status 'ERROR'"
    ):
        await client.login()

    # A rejected answer tells nothing about whether the device needs ADM
    assert client.login_required is None


async def test_login_missing_status_key(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test login raises exception when response is missing the status key."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"someOtherKey": "value"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        user_agent=user_agent,
    )

    with pytest.raises(
        SyrConnectAuthError, match="Login failed: Response missing expected key"
    ):
        await client.login()


async def test_login_mima_status(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test login raises exception when response status is MIMA."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"setADM(2)f": "MIMA"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        user_agent=user_agent,
    )

    with pytest.raises(
        SyrConnectAuthError,
        match="Login failed: Value .* is outside valid range for command ADM",
    ):
        await client.login()


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"setADM(2)f": "NSC"}, id="nsc"),
        pytest.param({"setADM(2)f": "ERROR: NSC"}, id="error-nsc"),
        pytest.param({"ADM(2)f": "ERROR: NSC"}, id="without-set-prefix"),
    ],
)
async def test_login_nsc_treated_as_not_required(
    user_agent: str,
    set_response_body: Callable[..., None],
    response: dict[str, str],
) -> None:
    """Test login treats an NSC answer to ADM like HTTP 404: ADM is not needed.

    The NeoSoft firmware NSR.1.82 answers {"setADM(2)f": "ERROR: NSC"}.
    """

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps(response))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/neosoft",
        user_agent=user_agent,
    )

    result = await client.login()

    assert result is True
    assert client.login_required is False
    assert client._last_login is not None
    assert client.projects == [{"id": "local", "name": "Local JSON API"}]


async def test_login_404_treated_as_not_required(user_agent: str) -> None:
    """Test login treats HTTP 404 as 'login not required' and sets flag."""

    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        user_agent=user_agent,
    )

    # Simulate _execute_http_get raising the HTTP error of a missing endpoint

    exc = SyrConnectHTTPError("Endpoint not found (HTTP 404)", status=404)
    with patch.object(client, "_execute_http_get", side_effect=exc):
        result = await client.login()

    assert result is True
    assert client._login_required is False


async def test_login_factory_treated_as_required(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test login treats response 'FACTORY' as 'login required'."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"setADM(2)f": "FACTORY"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/safe-tec",
        user_agent=user_agent,
    )

    result = await client.login()

    assert result is True
    assert client._login_required is True
    assert client._last_login is not None
    assert client.projects and client.projects[0]["id"] == "local"


async def test_login_factory_without_set_prefix(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test login accepts response key without 'set' prefix (e.g. Floorsensor firmware).

    Some devices return {"ADM(2)f":"FACTORY"} instead of {"setADM(2)f":"FACTORY"}.
    """
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"ADM(2)f": "FACTORY"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        user_agent=user_agent,
    )

    result = await client.login()

    assert result is True
    assert client._login_required is True
    assert client._last_login is not None
    assert client.projects and client.projects[0]["id"] == "local"


async def test_get_device_status_does_not_call_login_if_not_required(
    user_agent: str,
) -> None:
    """Ensure get_device_status skips login when login not required."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        user_agent=user_agent,
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


async def test_request_json_data_no_base_url_raises(user_agent: str) -> None:
    """Test request_json_data raises ValueError when base URL not configured."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess, user_agent=user_agent
    )  # No host/base_path/base_url
    with pytest.raises(ValueError, match="Base URL not configured"):
        await client.request_json_data("/get/all")


async def test_request_json_data_non_dict_raises(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test request_json_data raises SyrConnectInvalidResponseError when response is not a dict."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps(["not", "a", "dict"]))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with pytest.raises(
        SyrConnectInvalidResponseError, match="API returned unexpected payload"
    ):
        await client.request_json_data("/get/all")


async def test_request_json_data_http_error(user_agent: str) -> None:
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
        user_agent=user_agent,
    )

    with pytest.raises(SyrConnectConnectionError):
        await client.request_json_data("/get/all")


async def test_request_json_data_success(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test request_json_data returns dict on success."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"getAB": "value", "getCD": "123"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    result = await client.request_json_data("/get/all")

    assert result == {"getAB": "value", "getCD": "123"}


async def test_get_device_status_calls_login(user_agent: str) -> None:
    """Test get_device_status calls login when session invalid and no cached data."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        user_agent=user_agent,
    )

    # Mock login
    client.login = AsyncMock()  # type: ignore[method-assign]

    data = {"getAB": "value", "getCD": "123"}
    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        status = await client.get_device_status("device1")

    # Verify login was called (no cached data)
    client.login.assert_called_once()
    assert status == data


async def test_set_device_status_no_base_url_raises(user_agent: str) -> None:
    """Test set_device_status raises ValueError when base URL not configured."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess, user_agent=user_agent
    )  # No host/base_path/base_url

    with pytest.raises(ValueError, match="Base URL not configured"):
        await client.set_device_status("device1", [("setAB", "true")])


async def test_set_device_status_strips_set_prefix(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test set_device_status strips 'set' prefix from command."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    result = await client.set_device_status("device1", [("setAB", "true")])

    # Verify URL contains "/set/ab/true" (not "/set/setAB/true")
    called_url = str(sess.get.call_args[0][0])
    assert "/set/ab/true" in called_url
    assert "/set/setAB/" not in called_url
    assert result is True


@pytest.mark.parametrize(
    ("command", "path"), [("clrALA", "/clr/ala"), ("clrALM", "/clr/alm")]
)
async def test_set_device_status_sends_clr_command_to_clr_endpoint(
    user_agent: str, set_response_body: Callable[..., None], command: str, path: str
) -> None:
    """A clr command clears the alarm via the /clr/ endpoint, before the next command."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"setAB1": "OK"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    result = await client.set_device_status("device1", [(command, ""), ("setAB", 1)])

    called_urls = [urlsplit(str(c.args[0])).path for c in sess.get.call_args_list]
    assert called_urls == [f"/trio{path}", "/trio/set/ab/1"]
    assert result is True


async def test_set_device_status_success(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test set_device_status returns True when response status is OK."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"setXY123": "OK"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    result = await client.set_device_status("device1", [("XY", "123")])

    assert result is True


async def test_set_device_status_http_error(user_agent: str) -> None:
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
        user_agent=user_agent,
    )

    with pytest.raises(SyrConnectAuthError):
        await client.set_device_status("device1", [("AB", "false")])


async def test_get_device_status_skips_login_with_base_url(
    user_agent: str,
) -> None:
    """Test get_device_status skips login when explicit base_url provided."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
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
    user_agent: str,
    set_response_body: Callable[..., None],
) -> None:
    """Test request_json_data logs warning when response contains NSC error code."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"getXYZ": "NSC", "getABC": "value"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with caplog.at_level(logging.WARNING):
        result = await client.request_json_data("/get/all")

    assert result == {"getXYZ": "NSC", "getABC": "value"}
    assert "JSON API: 'getXYZ' Command does not exist (NSC error)" in caplog.text


async def test_request_json_data_logs_mima_error(
    caplog: pytest.LogCaptureFixture,
    user_agent: str,
    set_response_body: Callable[..., None],
) -> None:
    """Test request_json_data logs warning when response contains MIMA error code."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    # Use a GET key (not SET) to test warning logging for error codes
    set_response_body(mock_response, json.dumps({"getPRF": "MIMA", "getABC": "value"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with caplog.at_level(logging.WARNING):
        result = await client.request_json_data("/get/all")

    assert result == {"getPRF": "MIMA", "getABC": "value"}
    assert "JSON API: 'getPRF' Value is outside valid range (MIMA error)" in caplog.text


async def test_set_device_status_raises_on_nsc_error(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test set_device_status raises SyrConnectInvalidResponseError when response contains NSC error code."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"setINVALIDvalue": "NSC"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with pytest.raises(
        SyrConnectInvalidResponseError, match="Command INVALID does not exist"
    ):
        await client.set_device_status("device1", [("INVALID", "value")])


async def test_set_device_status_raises_on_mima_error(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test set_device_status raises SyrConnectInvalidResponseError when response contains MIMA error code."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"setPRF9999": "MIMA"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with pytest.raises(
        SyrConnectInvalidResponseError,
        match="Value 999 is outside valid range for command PRF9",
    ):
        await client.set_device_status("device1", [("PRF9", "999")])


async def test_set_device_status_sends_special_characters_unencoded(
    user_agent: str,
    set_response_body: Callable[..., None],
) -> None:
    """Colons and slashes of a value are sent as they are, the firmware decodes nothing."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"setRTM02:15": "OK"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    # Test with time value containing colon (e.g., "02:15")
    result = await client.set_device_status("device1", [("RTM", "02:15")])

    # Verify URL contains literal colon (not percent-encoded) because device
    # firmware does not decode %3A and rejects encoded values.
    called_url = str(sess.get.call_args[0][0])
    assert "/set/rtm/02:15" in called_url
    assert result is True

    # Test with value containing slash - also sent without encoding
    set_response_body(mock_response, json.dumps({"setCMDvalue/with/slash": "OK"}))
    result2 = await client.set_device_status("device1", [("CMD", "value/with/slash")])
    called_url2 = str(sess.get.call_args[0][0])
    assert "value/with/slash" in called_url2
    assert result2 is True


@pytest.mark.parametrize(
    ("value", "sent"),
    [
        pytest.param(True, "true", id="bool-true"),
        pytest.param(False, "false", id="bool-false"),
        pytest.param("True", "true", id="text-true"),
        pytest.param("FALSE", "false", id="text-false"),
        pytest.param(1, "1", id="number"),
    ],
)
async def test_set_device_status_sends_booleans_in_lowercase(
    user_agent: str,
    set_response_body: Callable[..., None],
    value: Any,
    sent: str,
) -> None:
    """A boolean is sent in lowercase, as documented by SYR; other values unchanged."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({f"setBUZ{sent}": "OK"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    assert await client.set_device_status("device1", [("setBUZ", value)]) is True

    assert str(sess.get.call_args[0][0]) == f"http://test:5333/trio/set/buz/{sent}"


async def test_set_device_status_missing_response_key(
    caplog: pytest.LogCaptureFixture,
    user_agent: str,
    set_response_body: Callable[..., None],
) -> None:
    """Test set_device_status handles missing response key gracefully."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"someOtherKey": "OK"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with caplog.at_level(logging.WARNING):
        result = await client.set_device_status("device1", [("TEST", "123")])

    # Should not raise exception, just log warning and return True
    assert result is True
    assert "Response missing expected key 'setTEST123'" in caplog.text


async def test_set_device_status_unknown_status_code(
    caplog: pytest.LogCaptureFixture,
    user_agent: str,
    set_response_body: Callable[..., None],
) -> None:
    """Test set_device_status handles unknown status codes gracefully."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"setUNKNOWN42": "WEIRD"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with caplog.at_level(logging.WARNING):
        result = await client.set_device_status("device1", [("UNKNOWN", "42")])

    # Should not raise exception, just log warning and return True
    assert result is True
    assert "Unexpected status 'WEIRD'" in caplog.text


def test_strip_set_prefix_and_cases(user_agent: str) -> None:
    """Test strip set prefix and cases."""
    sess = MagicMock()
    api = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    assert api._strip_set_prefix("setRTM") == "RTM"
    assert api._strip_set_prefix("RTM") == "RTM"
    assert api._strip_set_prefix("setAB") == "AB"
    assert api._strip_set_prefix("setadm") == "adm"


def test_normalize_cmd_for_url(user_agent: str) -> None:
    """Test normalize cmd for url."""
    sess = MagicMock()
    api = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    # ADM is special and must remain uppercase
    assert api._normalize_cmd_for_url("ADM") == "ADM"
    assert api._normalize_cmd_for_url("adm") == "ADM"

    # Other commands should be lowercased for URL usage
    assert api._normalize_cmd_for_url("RTM") == "rtm"
    assert api._normalize_cmd_for_url("prf9") == "prf9"


def test_response_key_for(user_agent: str) -> None:
    """Test response key for."""
    sess = MagicMock()
    api = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    assert api._response_key_for("rtm", "02:15") == "setRTM02:15"
    assert api._response_key_for("PRF9", "999") == "setPRF9999"


def test_build_set_url_keeps_value_and_lowercases_command(
    user_agent: str,
) -> None:
    """The value is sent unencoded; the command is lowercase, except ADM."""
    sess = MagicMock()
    api = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    # The colon of a time stays as it is
    url = api._build_set_url("RTM", "02:15")
    assert "/set/rtm/02:15" in str(url)

    url2 = api._build_set_url("ADM", "(2)f")
    # Parentheses are also sent as-is
    assert "/set/ADM/(2)f" in str(url2)


@pytest.mark.parametrize(
    ("value", "warning"),
    [
        pytest.param("NSC", "Command does not exist (NSC error)", id="nsc"),
        pytest.param("MIMA", "Value is outside valid range (MIMA error)", id="mima"),
        pytest.param("ADM", "ADM mode not set (ADM error)", id="adm"),
        pytest.param("ERROR: ADM", "ADM mode not set (ADM error)", id="error-adm"),
        # The codes are always uppercase: another case is an ordinary value
        pytest.param("nsc", None, id="lowercase"),
        pytest.param("Mima", None, id="mixed-case"),
        pytest.param("ERROR: adm", None, id="error-lowercase"),
        pytest.param("12:30", None, id="colon-without-code"),
    ],
)
async def test_validate_response_errors_only_uppercase_codes(
    caplog: pytest.LogCaptureFixture,
    user_agent: str,
    value: str,
    warning: str | None,
) -> None:
    """Only the uppercase error codes are warned about; no value rejects the answer."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with caplog.at_level(logging.WARNING):
        client._validate_response_errors({"getWFC": value}, "http://test")

    if warning is None:
        assert caplog.text == ""
    else:
        assert f"JSON API: 'getWFC' {warning} - URL: http://test" in caplog.text


async def test_validate_response_errors_ignores_non_string_values(
    user_agent: str,
) -> None:
    """Test _validate_response_errors ignores non-string values."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    # Should not raise exceptions for non-string values
    client._validate_response_errors({"key1": 123}, "http://test")
    client._validate_response_errors({"key2": None}, "http://test")
    client._validate_response_errors({"key3": []}, "http://test")
    client._validate_response_errors({"key4": {}}, "http://test")


async def test_get_devices_fetches_and_caches(user_agent: str) -> None:
    """Test that get_devices fetches /get/all and caches response."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
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
        # Device dict must include project_id, as in the device list of the XML client
        assert devices[0]["project_id"] == "local"


async def test_get_device_status_without_cache(user_agent: str) -> None:
    """Test that get_device_status fetches directly if no cached data."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    data = load_fixture("SyrSafeTechV4_old_get_all.json")

    with patch.object(client, "request_json_data", new=AsyncMock(return_value=data)):
        # Call get_device_status without calling get_devices first
        status = await client.get_device_status("local")

    assert status == data


@pytest.mark.parametrize(
    "data",
    [
        {"getFRN": "A25032111217", "getOther": "value"},
        {"getSRN": "", "getOther": "value"},
        {"getOther": "value"},
    ],
)
async def test_get_devices_without_serial_number_raises(
    user_agent: str, data: dict[str, str]
) -> None:
    """A device without getSRN is no SYR device; getFRN is no serial number."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with (
        patch.object(client, "request_json_data", new=AsyncMock(return_value=data)),
        pytest.raises(SyrConnectInvalidResponseError, match="getSRN"),
    ):
        await client.get_devices("local")


async def test_get_devices_calls_login_when_session_invalid(
    user_agent: str,
) -> None:
    """Test that get_devices calls login when session is invalid (no base_url)."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.1",
        base_path="/trio",
        user_agent=user_agent,
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


async def test_execute_http_get_404_error(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test _execute_http_get raises SyrConnectHTTPError (a connection error) on 404."""

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
    set_response_body(mock_response, "Endpoint not found")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with pytest.raises(SyrConnectConnectionError, match="Endpoint not found"):
        await client._execute_http_get("http://test:5333/trio/missing")


async def test_execute_http_get_does_not_follow_redirects(
    user_agent: str,
    set_response_body: Callable[..., None],
) -> None:
    """A redirect is not followed and fails the request."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 302
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"getSRN": "12345"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with pytest.raises(SyrConnectHTTPError, match="Redirect not followed") as excinfo:
        await client._execute_http_get("http://test:5333/trio/get/all")

    assert excinfo.value.status == 302
    assert sess.get.call_args.kwargs["allow_redirects"] is False
    mock_response.json.assert_not_called()


async def test_execute_http_get_sends_the_user_agent(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """The client sends the User-Agent of the caller, as for the cloud API."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"getSRN": "12345"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    await client._execute_http_get("http://test:5333/trio/get/all")

    assert sess.get.call_args.kwargs["headers"] == {"User-Agent": user_agent}


async def test_execute_http_get_timeout_error(user_agent: str) -> None:
    """Test _execute_http_get raises SyrConnectConnectionError on timeout."""

    sess = MagicMock()
    sess.get = MagicMock(side_effect=TimeoutError())

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with pytest.raises(
        SyrConnectConnectionError, match=r"Connection failed: TimeoutError\(\)"
    ):
        await client._execute_http_get("http://test:5333/trio/slow")


async def test_execute_http_get_client_error(user_agent: str) -> None:
    """Test _execute_http_get raises SyrConnectConnectionError on aiohttp.ClientError."""

    sess = MagicMock()
    sess.get = MagicMock(side_effect=aiohttp.ClientError("Connection refused"))

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with pytest.raises(SyrConnectConnectionError, match="Connection failed"):
        await client._execute_http_get("http://test:5333/trio/test")


async def test_execute_http_get_unexpected_error(user_agent: str) -> None:
    """Test _execute_http_get raises SyrConnectConnectionError on unexpected errors."""

    sess = MagicMock()
    sess.get = MagicMock(side_effect=RuntimeError("Unexpected error"))

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with pytest.raises(SyrConnectConnectionError, match="Unexpected error"):
        await client._execute_http_get("http://test:5333/trio/test")


async def test_execute_http_get_logs_error_response_body(
    caplog: pytest.LogCaptureFixture,
    user_agent: str,
    set_response_body: Callable[..., None],
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
    set_response_body(mock_response, "Server encountered an error")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with caplog.at_level(logging.DEBUG), pytest.raises(SyrConnectConnectionError):
        await client._execute_http_get("http://test:5333/trio/error")

    assert "Error response: 'Server encountered an error'" in caplog.text


async def test_execute_http_get_logs_error_response_read_failure(
    caplog: pytest.LogCaptureFixture,
    user_agent: str,
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
    mock_response.content_length = None
    mock_response.content.iter_chunked = MagicMock(
        side_effect=aiohttp.ClientPayloadError("Cannot read response")
    )
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with caplog.at_level(logging.DEBUG), pytest.raises(SyrConnectConnectionError):
        await client._execute_http_get("http://test:5333/trio/error")

    # Should log that it couldn't read the error response
    assert "Could not read error response" in caplog.text


@pytest.mark.parametrize(
    ("body", "error", "message"),
    [
        pytest.param(
            "x" * (1024 * 1024 + 1),
            SyrConnectConnectionError,
            "Response exceeds the limit of 1048576 bytes",
            id="too-large",
        ),
        pytest.param(
            '{"getSRN": ',
            SyrConnectConnectionError,
            "Unexpected error",
            id="broken-json",
        ),
        pytest.param(
            "  ",
            SyrConnectInvalidResponseError,
            "API returned unexpected payload type",
            id="empty",
        ),
    ],
)
async def test_execute_http_get_unusable_body(
    user_agent: str,
    set_response_body: Callable[..., None],
    body: str,
    error: type[Exception],
    message: str,
) -> None:
    """A body that is too large, no JSON or empty fails the request."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, body)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with pytest.raises(error, match=message):
        await client._execute_http_get("http://test:5333/trio/get/all")


async def test_execute_http_get_reraises_invalid_response_error(
    user_agent: str,
    set_response_body: Callable[..., None],
) -> None:
    """Test _execute_http_get re-raises SyrConnectInvalidResponseError without wrapping."""

    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps([]))  # Returns list instead of dict
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    # The error should be raised as-is, not wrapped
    with pytest.raises(SyrConnectInvalidResponseError, match="unexpected payload type"):
        await client._execute_http_get("http://test:5333/trio/test")


async def test_construct_url_no_base_url_raises(
    user_agent: str,
) -> None:
    """Test _construct_url raises ValueError when base URL is not configured."""
    sess = MagicMock()
    # Create client without base_url, host, or base_path
    client = SyrConnectJsonAPI(sess, user_agent=user_agent)

    with pytest.raises(ValueError, match="Base URL not configured"):
        client._construct_url("test", "path")


async def test_get_device_status_with_cached_response(user_agent: str) -> None:
    """Test get_device_status uses cached response from previous get_devices call."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
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


async def test_login_clears_cached_data(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test login clears any cached _get_all data from previous session."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"setADM(2)f": "OK"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        user_agent=user_agent,
    )

    # Set some cached data
    client._cached_get_all = {"getSRN": "old_data"}

    # Login should clear the cache
    await client.login()

    assert client._cached_get_all is None


async def test_construct_url_keeps_special_characters(
    user_agent: str,
) -> None:
    """The parts of a URL are not percent-encoded, the firmware does not decode them."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    assert str(client._construct_url("set", "ADM", "(2)f")) == (
        "http://test:5333/trio/set/ADM/(2)f"
    )
    assert str(client._construct_url("set", "rtm", "02:30")) == (
        "http://test:5333/trio/set/rtm/02:30"
    )


async def test_request_json_data_strips_leading_slash(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
    """Test request_json_data strips leading slash from path."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"key": "value"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    # Call with leading slash
    await client.request_json_data("/get/all")

    # URL should not have double slashes
    called_url = str(sess.get.call_args[0][0])
    assert "trio//get" not in called_url
    assert "trio/get/all" in called_url


async def test_request_json_data_without_leading_slash(
    user_agent: str,
    set_response_body: Callable[..., None],
) -> None:
    """Test request_json_data works with path without leading slash."""
    sess = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    set_response_body(mock_response, json.dumps({"key": "value"}))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    # Call without leading slash
    await client.request_json_data("get/all")

    # URL should be correct
    called_url = str(sess.get.call_args[0][0])
    assert "trio/get/all" in called_url


async def test_get_devices_skips_login_when_session_valid(
    user_agent: str,
) -> None:
    """Test get_devices skips login when session is still valid."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.100",
        base_path="/trio",
        user_agent=user_agent,
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
    user_agent: str,
) -> None:
    """When a login set-response is missing the expected key, raise SyrConnectInvalidResponseError."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with pytest.raises(SyrConnectInvalidResponseError):
        client._validate_set_response(
            {}, cmd="ADM", value="(2)f", serial_number="login", is_login=True
        )


async def test_execute_http_get_401_auth_error(
    user_agent: str, set_response_body: Callable[..., None]
) -> None:
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
    set_response_body(mock_response, "Unauthorized")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    sess.get = MagicMock(return_value=mock_response)

    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with pytest.raises(SyrConnectAuthError):
        await client._execute_http_get("http://test:5333/trio/auth")


def test_validate_set_response_missing_key_nonlogin_returns(
    user_agent: str,
) -> None:
    """When response missing expected key for non-login, do not raise."""
    client = SyrConnectJsonAPI(
        MagicMock(),
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    # Should not raise for non-login missing key
    client._validate_set_response(
        {}, cmd="TEST", value="123", serial_number="dev1", is_login=False
    )


async def test_login_skips_when_flag_false(user_agent: str) -> None:
    """If _login_required is False, login() should skip network calls and mark session valid."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
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
    user_agent: str,
) -> None:
    """When a login set-response returns an unexpected status, raise SyrConnectInvalidResponseError."""

    client = SyrConnectJsonAPI(
        MagicMock(),
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    # Provide response with expected key but unknown status and is_login=True
    resp_key = client._response_key_for("ADM", "(2)f")
    with pytest.raises(SyrConnectInvalidResponseError):
        client._validate_set_response(
            {resp_key: "WEIRD"},
            cmd="ADM",
            value="(2)f",
            serial_number="login",
            is_login=True,
        )


async def test_login_reraises_connection_error(user_agent: str) -> None:
    """login() must re-raise SyrConnectConnectionError."""

    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
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
    user_agent: str,
) -> None:
    """get_devices skips login when _login_required is False."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(
        sess,
        host="192.168.1.1",
        base_path="/trio",
        user_agent=user_agent,
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


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(TimeoutError(), SyrConnectConnectionError, id="timeout"),
        pytest.param(
            aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=500, message="Error"
            ),
            SyrConnectHTTPError,
            id="http-500",
        ),
    ],
)
async def test_failed_request_logs_at_debug_level_only(
    caplog: pytest.LogCaptureFixture,
    user_agent: str,
    error: Exception,
    expected: type[Exception],
) -> None:
    """A failed request is not logged above debug level; the caller decides what to log."""
    sess = MagicMock()
    sess.get = MagicMock(side_effect=error)
    client = SyrConnectJsonAPI(
        sess,
        base_url="http://test:5333/trio/",
        user_agent=user_agent,
    )

    with (
        caplog.at_level(logging.DEBUG, logger=_LIBRARY_LOGGER),
        pytest.raises(expected),
    ):
        await client.request_json_data("get/all")

    assert [r.getMessage() for r in caplog.records if r.levelno > logging.DEBUG] == []


@pytest.mark.parametrize("user_agent", [None, "", "   "])
def test_empty_user_agent_is_rejected(user_agent: str | None) -> None:
    """The JSON API client does not send an empty User-Agent."""
    with pytest.raises(ValueError, match="user_agent is required"):
        SyrConnectJsonAPI(MagicMock(), host="192.0.2.1", user_agent=user_agent)


def test_missing_user_agent_is_rejected() -> None:
    """A caller that passes no User-Agent gets a ValueError."""
    with pytest.raises(ValueError, match="user_agent is required"):
        SyrConnectJsonAPI(MagicMock(), host="192.0.2.1")
