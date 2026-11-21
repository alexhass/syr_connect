"""Tests of the XML API client."""

# The unit tests in this module check private helpers and attributes directly.
# ruff: noqa: SLF001

import asyncio
from datetime import UTC, datetime
import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from custom_components.syr_connect.aiosyrconnect import (
    API_SERVICES,
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectDeviceNotFoundError,
    SyrConnectInvalidResponseError,
    SyrConnectLoginFailedError,
    SyrConnectSessionExpiredError,
    SyrConnectStatistic,
    SyrConnectXmlAPI,
)

# Logger of the library package
_LIBRARY_LOGGER = SyrConnectXmlAPI.__module__.rpartition(".")[0]

# Measurement history series of a SafeFloor: temperature and humidity
_STATISTICS = (
    SyrConnectStatistic(
        key="getCEL",
        method="GetSafeFloorStatistics",
        rtyp=4,
        t=1,
        unit="°C",
    ),
    SyrConnectStatistic(
        key="getHMD",
        method="GetSafeFloorStatistics",
        rtyp=4,
        t=2,
        unit="%",
    ),
)

_SYR_SERVICE = API_SERVICES["de.consoft.syr.connect"]


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock aiohttp session."""
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def api_client(mock_session: MagicMock, user_agent: str) -> SyrConnectXmlAPI:
    """Create an API client instance that knows the devices of the tests.

    The tests address the devices "SN1" and "device1" by their serial number, as if an
    earlier device list had reported their device collections "dclg1" and
    "dclg-device1".
    """
    api = SyrConnectXmlAPI(
        mock_session,
        "test@example.com",
        "testpassword",
        service=_SYR_SERVICE,
        user_agent=user_agent,
    )
    api._dclg_by_serial = {"SN1": "dclg1", "device1": "dclg-device1"}
    return api


def test_clear_value_is_hexadecimal_text(api_client: SyrConnectXmlAPI) -> None:
    """The cloud acknowledges a notification or warning (setNOT, setWRN) with "FF"."""
    assert api_client.clear_value == "FF"


def test_request_urls_and_app_identity_come_from_the_service(
    mock_session: MagicMock,
    user_agent: str,
) -> None:
    """The URLs, the app name and the bundle identifier are those of the service."""
    svc = API_SERVICES["de.consoft.gc.conel.connect"]
    api = SyrConnectXmlAPI(
        mock_session,
        "test@example.com",
        "testpassword",
        service=svc,
        user_agent=user_agent,
    )

    assert (
        api._device_list_url
        == "https://api.conelclearpro.de/WebServices/SyrControlWebServiceTest2.asmx/GetProjectDeviceCollections"
    )
    assert api._device_get_status_url.startswith(
        "https://api.conelclearpro.de/WebServices/"
    )
    assert api.payload_builder.app_name == "CLEAR PRO"
    assert api.payload_builder.app_version.endswith("-de.consoft.gc.conel.connect")


def test_crypt_values_select_the_login_response_key(
    mock_session: MagicMock, user_agent: str
) -> None:
    """The login response is decrypted with the key and IV of the service."""
    svc = API_SERVICES["de.consoft.rwc.connect"]
    api = SyrConnectXmlAPI(
        mock_session,
        "test@example.com",
        "testpassword",
        service=svc,
        user_agent=user_agent,
    )

    assert (
        api.encryption.key.hex()
        == "ecb1552e674668f493c8be1792cfc299ec335d34fe6a9289729a0daf7c210b17"
    )
    assert api.encryption.iv.hex() == "2482879480e5c67a09888a7526f33a70"


async def test_login_does_not_log_payload(
    mock_session: MagicMock, caplog: pytest.LogCaptureFixture, user_agent: str
) -> None:
    """The login payload is not logged, only its size, so the password never reaches the log."""
    api = SyrConnectXmlAPI(
        mock_session,
        "user@example.com",
        "s3cr3t!",
        service=_SYR_SERVICE,
        user_agent=user_agent,
        language="en-DE",
    )
    caplog.set_level("DEBUG", logger=SyrConnectXmlAPI.__module__)

    with (
        patch.object(
            api.http_client, "post", side_effect=aiohttp.ClientError("offline")
        ),
        pytest.raises(SyrConnectConnectionError),
    ):
        await api.login()

    assert "Login payload prepared (" in caplog.text
    assert "<usr" not in caplog.text
    assert "s3cr3t!" not in caplog.text


def test_language_is_passed_to_payload_builder_and_http_client(
    mock_session: MagicMock,
    user_agent: str,
) -> None:
    """The locale reaches the login/statistics payloads and the Accept-Language header."""
    api = SyrConnectXmlAPI(
        mock_session,
        "test@example.com",
        "testpassword",
        service=_SYR_SERVICE,
        user_agent=user_agent,
        language="en-DE",
    )

    assert api.payload_builder.app_version.startswith("App-3.9.7-en-DE-iOS-")
    assert api.payload_builder._compute_locale_lang_reg() == ("en", "DE")
    assert api.http_client._build_accept_language() == "en-DE,en;q=0.9"


def test_user_agent_of_the_caller_is_sent(
    api_client: SyrConnectXmlAPI,
    user_agent: str,
) -> None:
    """The client sends the User-Agent of the caller."""
    assert api_client.http_client.user_agent == user_agent


def test_language_defaults(api_client: SyrConnectXmlAPI) -> None:
    """Without a locale, the app version, payloads and header all fall back to en-US."""
    assert api_client.payload_builder.app_version.startswith("App-3.9.7-en-US-iOS-")
    assert api_client.payload_builder._compute_locale_lang_reg() == ("en", "US")
    assert api_client.http_client._build_accept_language() == "en-US,en;q=0.9"


INVALID_TOKEN_XML = (
    Path(__file__).parent.parent
    / "fixtures/xml/SyrTestDevice_InvalidSessionResponse.xml"
).read_text(encoding="utf-8")


async def test_session_valid_check(api_client: SyrConnectXmlAPI) -> None:
    """A session is usable as soon as a token from a login exists; there is no client-side expiry."""
    assert not api_client.is_session_valid()

    api_client.session_data = "test_session"
    assert api_client.is_session_valid()


async def test_parallel_first_requests_log_in_only_once(
    api_client: SyrConnectXmlAPI,
) -> None:
    """Without a token yet, parallel requests share one login instead of each logging in."""

    async def _login() -> Any:
        await asyncio.sleep(0)  # let the other tasks reach the lock meanwhile
        api_client.session_data = "new"
        return True

    with patch.object(api_client, "login", side_effect=_login) as login:
        await asyncio.gather(*(api_client._ensure_session() for _ in range(5)))

    assert login.await_count == 1
    assert api_client.session_data == "new"


async def test_parallel_rejections_relogin_only_once(
    api_client: SyrConnectXmlAPI,
) -> None:
    """When parallel requests get the token rejected at the same time, only one logs in again."""

    api_client.session_data = "old"

    async def _login() -> Any:
        await asyncio.sleep(0)
        api_client.session_data = "new"
        return True

    with patch.object(api_client, "login", side_effect=_login) as login:
        await asyncio.gather(*(api_client._relogin("old") for _ in range(5)))

    assert login.await_count == 1
    assert api_client.session_data == "new"


@pytest.mark.parametrize("rejected", [True, False], ids=["rejected-token", "no-token"])
async def test_parallel_requests_share_a_failed_login(
    api_client: SyrConnectXmlAPI, rejected: bool
) -> None:
    """A failed login is not repeated by the requests that waited for it; the next request tries again."""
    api_client.session_data = "old" if rejected else ""
    error = SyrConnectLoginFailedError("Login rejected.")

    async def _login() -> Any:
        await asyncio.sleep(0)  # let the other tasks reach the lock meanwhile
        raise error

    def _request() -> Any:
        return api_client._relogin("old") if rejected else api_client._ensure_session()

    with patch.object(api_client, "login", side_effect=_login) as login:
        results = await asyncio.gather(
            *(_request() for _ in range(5)), return_exceptions=True
        )
        assert login.await_count == 1
        assert results == [error] * 5

        # The next request logs in again
        with pytest.raises(SyrConnectLoginFailedError):
            await _request()
        assert login.await_count == 2


@pytest.mark.parametrize(
    ("method", "args", "parser"),
    [
        ("get_devices", ("project1",), "parse_device_list_response"),
        ("get_device_status", ("SN1",), "parse_device_status_response"),
        ("set_device_status", ("SN1", [("setAB", "2")]), None),
        (
            "get_statistics",
            ("SN1", _STATISTICS[0]),
            "parse_statistics_response",
        ),
    ],
)
async def test_rejected_token_relogs_in_and_retries_once(
    api_client: SyrConnectXmlAPI, method: Any, args: Any, parser: str | None
) -> None:
    """The real "invalid token" answer triggers one re-login and a retry with the new token."""
    api_client.session_data = "old"
    posted_payloads: list[str] = []

    async def _post(_url: Any, data: Any, **_kw: Any) -> Any:
        posted_payloads.append(data["xml"])
        return INVALID_TOKEN_XML if len(posted_payloads) == 1 else "<sc><ok /></sc>"

    async def _login() -> Any:
        api_client.session_data = "new"
        return True

    with (
        patch.object(api_client.http_client, "post", side_effect=_post),
        patch.object(api_client, "login", side_effect=_login) as login,
    ):
        if parser:
            result: Any = [] if method == "get_devices" else {}

            def _parse(xml: str) -> Any:
                # The real parsers detect a rejected token first
                api_client.response_parser.raise_if_session_expired(xml)
                return result

            with patch.object(api_client.response_parser, parser, side_effect=_parse):
                await getattr(api_client, method)(*args)
        else:
            await getattr(api_client, method)(*args)

    login.assert_awaited_once()
    assert len(posted_payloads) == 2
    assert 'ug="old"' in posted_payloads[0]
    assert 'ug="new"' in posted_payloads[1]


async def test_rejected_token_twice_raises_session_expired(
    api_client: SyrConnectXmlAPI,
) -> None:
    """If the new token is rejected as well, no loop: SyrConnectSessionExpiredError (a connection error)."""

    api_client.session_data = "old"

    async def _login() -> Any:
        api_client.session_data = "new"
        return True

    with (
        patch.object(
            api_client.http_client, "post", return_value=INVALID_TOKEN_XML
        ) as post,
        patch.object(api_client, "login", side_effect=_login) as login,
        pytest.raises(SyrConnectSessionExpiredError) as excinfo,
    ):
        await api_client.get_device_status("SN1")

    assert isinstance(excinfo.value, SyrConnectConnectionError)
    login.assert_awaited_once()
    assert post.await_count == 2


async def test_valid_response_does_not_relogin(api_client: SyrConnectXmlAPI) -> None:
    """A normal answer is used as is, without any login."""
    api_client.session_data = "token"

    with (
        patch.object(
            api_client.http_client, "post", return_value="<sc><ok /></sc>"
        ) as post,
        patch.object(api_client, "login") as login,
        patch.object(
            api_client.response_parser,
            "parse_device_status_response",
            return_value={"getFLO": "5"},
        ),
    ):
        assert await api_client.get_device_status("SN1") == {"getFLO": "5"}

    login.assert_not_called()
    post.assert_awaited_once()


async def test_login_success(api_client: SyrConnectXmlAPI) -> None:
    """Test successful login."""
    mock_response = """<?xml version="1.0"?><sc><api>encrypted_data</api></sc>"""

    with (
        patch.object(api_client.http_client, "post", return_value=mock_response),
        patch.object(
            api_client.response_parser,
            "parse_login_response",
            return_value=("encrypted", {"sc": {"suc": {"@v": "true"}}}),
        ),
        patch.object(
            api_client.encryption,
            "decrypt",
            return_value='<usr id="123"/><prs><pre id="p1" n="Project1"/></prs>',
        ),
        patch.object(
            api_client.response_parser,
            "parse_decrypted_login",
            return_value=("123", [{"id": "p1", "name": "Project1"}]),
        ),
    ):
        result = await api_client.login()

        assert result is True
        assert api_client.session_data == "123"
        assert len(api_client.projects) == 1


async def test_login_auth_error(api_client: SyrConnectXmlAPI) -> None:
    """Wrong password: <suc v="false"/> with the wrong-password text -> re-auth."""
    with (
        patch.object(
            api_client.http_client,
            "post",
            return_value='<sc><api>encrypted</api><suc v="false"/></sc>',
        ),
        patch.object(
            api_client.encryption,
            "decrypt",
            return_value='<msg hl="Fehler" v="Der Benutzername und das Passwort stimmen nicht überein." typ="1" />',
        ),
        pytest.raises(SyrConnectAuthError, match="Invalid credentials"),
    ):
        await api_client.login()


async def test_login_rejected_for_other_cause(api_client: SyrConnectXmlAPI) -> None:
    """<suc v="false"/> without the wrong-password text (outage, unknown user) -> no re-auth."""
    with (
        patch.object(
            api_client.http_client,
            "post",
            return_value='<sc><api>encrypted</api><suc v="false"/></sc>',
        ),
        patch.object(
            api_client.encryption,
            "decrypt",
            return_value='<msg hl="Fehler" v="Der Vorgang konnte nicht durchgeführt werden." typ="1" />',
        ),
        pytest.raises(SyrConnectLoginFailedError, match="Login rejected"),
    ):
        await api_client.login()

    assert not api_client.session_data


async def test_login_without_suc_is_rejected(api_client: SyrConnectXmlAPI) -> None:
    """Without <suc v="true"/> a login fails even if a session is present, as in the SYR app."""
    with (
        patch.object(
            api_client.http_client, "post", return_value="<sc><api>encrypted</api></sc>"
        ),
        patch.object(
            api_client.encryption,
            "decrypt",
            return_value='<usr id="123"/><prs><pre id="p1" n="P1"/></prs>',
        ),
        pytest.raises(SyrConnectLoginFailedError),
    ):
        await api_client.login()

    assert not api_client.session_data


async def test_login_connection_error(api_client: SyrConnectXmlAPI) -> None:
    """Test login with connection error."""
    with (
        patch.object(
            api_client.http_client,
            "post",
            side_effect=aiohttp.ClientError("Connection failed"),
        ),
        pytest.raises(SyrConnectConnectionError),
    ):
        await api_client.login()


async def test_get_device_status_with_valid_session(
    api_client: SyrConnectXmlAPI,
) -> None:
    """Test get_device_status uses existing valid session."""
    api_client.session_data = "valid_session"

    with (
        patch.object(api_client, "login", return_value=True) as mock_login,
        patch.object(api_client.http_client, "post", return_value="<sc></sc>"),
        patch.object(
            api_client.response_parser, "parse_device_status_response", return_value={}
        ),
    ):
        await api_client.get_device_status("device1")

        # Should NOT have called login
        mock_login.assert_not_called()


async def test_login_timeout_error(api_client: SyrConnectXmlAPI) -> None:
    """Test login with timeout error."""
    with (
        patch.object(
            api_client.http_client, "post", side_effect=TimeoutError("Request timeout")
        ),
        pytest.raises(SyrConnectConnectionError, match="Connection failed"),
    ):
        await api_client.login()


async def test_login_generic_exception(api_client: SyrConnectXmlAPI) -> None:
    """Test login with generic unexpected exception."""
    with (
        patch.object(
            api_client.http_client, "post", side_effect=RuntimeError("Unexpected error")
        ),
        pytest.raises(SyrConnectConnectionError, match="Login failed"),
    ):
        await api_client.login()


async def test_get_devices_exception_handling(api_client: SyrConnectXmlAPI) -> None:
    """Test get_devices exception is raised."""
    api_client.session_data = "valid_session"

    with (
        patch.object(
            api_client.http_client, "post", side_effect=RuntimeError("API error")
        ),
        pytest.raises(RuntimeError, match="API error"),
    ):
        await api_client.get_devices("project1")


async def test_get_devices_connection_client_error(
    api_client: SyrConnectXmlAPI,
) -> None:
    """Network client errors during get_devices should raise SyrConnectConnectionError."""
    api_client.session_data = "valid_session"

    with (
        patch.object(
            api_client.http_client,
            "post",
            side_effect=aiohttp.ClientError("Connection failed"),
        ),
        pytest.raises(SyrConnectConnectionError),
    ):
        await api_client.get_devices("project1")


async def test_get_devices_connection_timeout_error(
    api_client: SyrConnectXmlAPI,
) -> None:
    """Timeout errors during get_devices should raise SyrConnectConnectionError."""
    api_client.session_data = "valid_session"

    with (
        patch.object(
            api_client.http_client, "post", side_effect=TimeoutError("Request timeout")
        ),
        pytest.raises(SyrConnectConnectionError),
    ):
        await api_client.get_devices("project1")


async def test_get_device_status_returns_none(api_client: SyrConnectXmlAPI) -> None:
    """Test get_device_status returns None when parser returns None."""
    api_client.session_data = "valid_session"

    with (
        patch.object(api_client.http_client, "post", return_value="<sc></sc>"),
        patch.object(
            api_client.response_parser,
            "parse_device_status_response",
            return_value=None,
        ),
    ):
        result = await api_client.get_device_status("device1")

        assert result is None


async def test_get_device_status_exception_handling(
    api_client: SyrConnectXmlAPI,
) -> None:
    """Test get_device_status exception is raised."""
    api_client.session_data = "valid_session"

    with (
        patch.object(
            api_client.http_client, "post", side_effect=RuntimeError("Status error")
        ),
        pytest.raises(RuntimeError, match="Status error"),
    ):
        await api_client.get_device_status("device1")


async def test_set_device_status_boolean_false(api_client: SyrConnectXmlAPI) -> None:
    """Test set_device_status converts False to 0."""
    api_client.session_data = "valid_session"

    with (
        patch.object(
            api_client.payload_builder,
            "build_device_set_status_payload",
            return_value="<payload/>",
        ) as mock_build,
        patch.object(api_client.http_client, "post", return_value="<sc></sc>"),
    ):
        await api_client.set_device_status("device1", [("setSIR", False)])

        # Verify boolean False was converted to 0
        call_args = mock_build.call_args
        assert call_args[0][2] == [("setSIR", 0)]  # commands list with normalized value


async def test_set_device_status_boolean_true(api_client: SyrConnectXmlAPI) -> None:
    """Test set_device_status converts True to 1."""
    api_client.session_data = "valid_session"

    with (
        patch.object(
            api_client.payload_builder,
            "build_device_set_status_payload",
            return_value="<payload/>",
        ) as mock_build,
        patch.object(api_client.http_client, "post", return_value="<sc></sc>"),
    ):
        await api_client.set_device_status("device1", [("setSIR", True)])

        # Verify boolean True was converted to 1
        call_args = mock_build.call_args
        assert call_args[0][2] == [("setSIR", 1)]  # commands list with normalized value


async def test_set_device_status_exception_handling(
    api_client: SyrConnectXmlAPI,
) -> None:
    """Test set_device_status exception is raised."""
    api_client.session_data = "valid_session"

    with (
        patch.object(
            api_client.http_client, "post", side_effect=RuntimeError("Set error")
        ),
        pytest.raises(RuntimeError, match="Set error"),
    ):
        await api_client.set_device_status("device1", [("setSIR", 1)])


async def test_get_statistics_posts_series_to_its_method(
    api_client: SyrConnectXmlAPI,
) -> None:
    """The request goes to the method of the series and carries its attributes."""
    api_client.session_data = "valid_session"
    mock_stats = [(datetime(2026, 9, 26, 14, 45, 27, tzinfo=UTC), 52.0)]

    with (
        patch.object(
            api_client.http_client, "post", return_value="<sc></sc>"
        ) as mock_post,
        patch.object(
            api_client.response_parser,
            "parse_statistics_response",
            return_value=mock_stats,
        ),
    ):
        result = await api_client.get_statistics("device1", _STATISTICS[1])

    assert result == mock_stats
    url = mock_post.call_args.args[0]
    assert url == (
        "https://syrconnect.de/WebServices/SyrControlWebServiceTest2.asmx/"
        "GetSafeFloorStatistics"
    )
    payload = mock_post.call_args.args[1]["xml"]
    assert '<sh t="2" rtyp="4"' in payload
    assert 'unit="%"' in payload


async def test_get_statistics_exception_handling(api_client: SyrConnectXmlAPI) -> None:
    """Test get_statistics exception is raised."""
    api_client.session_data = "valid_session"

    with (
        patch.object(
            api_client.http_client, "post", side_effect=RuntimeError("Stats error")
        ),
        pytest.raises(RuntimeError, match="Stats error"),
    ):
        await api_client.get_statistics("device1", _STATISTICS[0])


async def test_login_with_parser_value_error(api_client: SyrConnectXmlAPI) -> None:
    """A malformed login answer is a connection problem, not rejected credentials (no re-auth)."""
    mock_response = """<?xml version="1.0"?><sc><api>encrypted_data</api></sc>"""

    with (
        patch.object(api_client.http_client, "post", return_value=mock_response),
        patch.object(
            api_client.response_parser,
            "parse_login_response",
            side_effect=ValueError("Invalid response structure"),
        ),
        pytest.raises(SyrConnectConnectionError, match="Invalid login response"),
    ):
        await api_client.login()


async def test_login_with_decryption_parser_error(api_client: SyrConnectXmlAPI) -> None:
    """A malformed decrypted answer is a connection problem, not rejected credentials (no re-auth)."""
    mock_response = """<?xml version="1.0"?><sc><api>encrypted_data</api></sc>"""

    with (
        patch.object(api_client.http_client, "post", return_value=mock_response),
        patch.object(
            api_client.response_parser,
            "parse_login_response",
            return_value=("encrypted", {"sc": {"suc": {"@v": "true"}}}),
        ),
        patch.object(api_client.encryption, "decrypt", return_value="<invalid>"),
        patch.object(
            api_client.response_parser,
            "parse_decrypted_login",
            side_effect=ValueError("Invalid decrypted data"),
        ),
        pytest.raises(SyrConnectConnectionError, match="Invalid login response"),
    ):
        await api_client.login()


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("get_device_status", ("SN1",)),
        ("set_device_status", ("SN1", [("setAB", "2")])),
        ("get_statistics", ("SN1", _STATISTICS[0])),
        ("get_raw_device_list", ("project1",)),
        ("get_raw_device_status", ("SN1",)),
    ],
)
async def test_network_errors_are_wrapped_in_connection_error(
    api_client: SyrConnectXmlAPI, method: Any, args: Any
) -> None:
    """Network errors become SyrConnectConnectionError, which the caller handles."""
    api_client.session_data = "valid_session"

    with (
        patch.object(
            api_client.http_client,
            "post",
            side_effect=aiohttp.ClientError("Request failed"),
        ),
        pytest.raises(SyrConnectConnectionError, match="Request failed") as excinfo,
    ):
        await getattr(api_client, method)(*args)

    assert isinstance(excinfo.value.__cause__, aiohttp.ClientError)


async def test_get_devices_adds_project_id(api_client: SyrConnectXmlAPI) -> None:
    """Test get_devices adds project_id to each device."""
    api_client.session_data = "valid_session"

    device_data = {
        "id": "device1",
        "name": "Test Device",
        "serial_number": "SN123",
        "dclg": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    }

    with (
        patch.object(api_client.http_client, "post", return_value="<sc></sc>"),
        patch.object(
            api_client.response_parser,
            "parse_device_list_response",
            return_value=[device_data],
        ),
    ):
        devices = await api_client.get_devices("project123")

        assert len(devices) == 1
        assert devices[0]["project_id"] == "project123"


async def test_set_device_status_non_boolean_value(
    api_client: SyrConnectXmlAPI,
) -> None:
    """Test set_device_status with non-boolean value (no conversion)."""
    api_client.session_data = "valid_session"

    with (
        patch.object(
            api_client.payload_builder,
            "build_device_set_status_payload",
            return_value="<payload/>",
        ) as mock_build,
        patch.object(api_client.http_client, "post", return_value="<sc></sc>"),
    ):
        await api_client.set_device_status("device1", [("setSV1", 10)])

        # Verify value is passed as-is (not converted)
        call_args = mock_build.call_args
        assert call_args[0][2] == [("setSV1", 10)]  # commands list with value unchanged


async def test_get_devices_with_device_already_has_id(
    api_client: SyrConnectXmlAPI,
) -> None:
    """Test get_devices when device already has 'id' field."""
    api_client.session_data = "valid_session"

    device_with_id = {
        "id": "EXISTING_ID",
        "name": "Test Device",
        "serial_number": "SN12345",
        "dclg": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    }

    with (
        patch.object(api_client.http_client, "post", return_value="<sc></sc>"),
        patch.object(
            api_client.response_parser,
            "parse_device_list_response",
            return_value=[device_with_id],
        ),
    ):
        devices = await api_client.get_devices("project1")

        assert len(devices) == 1
        # Should keep existing id, not overwrite with serial_number
        assert devices[0]["id"] == "EXISTING_ID"


_MAINTENANCE_PAGE = "<html><body>Wartungsarbeiten</body>"
_REQUESTS = [
    pytest.param("get_devices", ("project1",), id="device-list"),
    pytest.param("get_device_status", ("SN1",), id="status"),
    pytest.param("get_statistics", ("SN1", _STATISTICS[0]), id="statistics"),
]


@pytest.mark.parametrize(("method", "args"), _REQUESTS)
async def test_answer_without_xml_raises_invalid_response(
    api_client: SyrConnectXmlAPI, method: str, args: tuple[Any, ...]
) -> None:
    """An answer that is no XML, such as a maintenance page, is an unusable answer."""
    api_client.session_data = "token"

    with (
        patch.object(
            api_client.http_client,
            "post",
            return_value=_MAINTENANCE_PAGE,
        ),
        pytest.raises(SyrConnectInvalidResponseError, match="response: "),
    ):
        await getattr(api_client, method)(*args)


@pytest.mark.parametrize(("method", "args"), _REQUESTS)
async def test_failed_request_logs_at_debug_level_only(
    api_client: SyrConnectXmlAPI,
    caplog: pytest.LogCaptureFixture,
    method: str,
    args: tuple[Any, ...],
) -> None:
    """A timeout or a maintenance page is not logged above debug level; the caller decides what to log."""
    api_client.session_data = "token"

    with caplog.at_level(logging.DEBUG, logger=_LIBRARY_LOGGER):
        with (
            patch.object(
                api_client.http_client.session, "post", side_effect=TimeoutError()
            ),
            pytest.raises(SyrConnectConnectionError),
        ):
            await getattr(api_client, method)(*args)
        with (
            patch.object(
                api_client.http_client,
                "post",
                return_value=_MAINTENANCE_PAGE,
            ),
            pytest.raises(SyrConnectInvalidResponseError),
        ):
            await getattr(api_client, method)(*args)

    assert [r.getMessage() for r in caplog.records if r.levelno > logging.DEBUG] == []


async def test_failed_login_logs_at_debug_level_only(
    api_client: SyrConnectXmlAPI, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed login is not logged above debug level; the caller decides what the user sees."""
    with (
        caplog.at_level(logging.DEBUG, logger=_LIBRARY_LOGGER),
        patch.object(
            api_client.http_client.session, "post", side_effect=TimeoutError()
        ),
        pytest.raises(SyrConnectConnectionError, match="Connection failed"),
    ):
        await api_client.login()

    assert [r.getMessage() for r in caplog.records if r.levelno > logging.DEBUG] == []


@pytest.mark.parametrize(
    ("method", "args", "fixture"),
    [
        pytest.param(
            "get_devices",
            ("project1",),
            "SyrSafeFloor_GetProjectDeviceCollections.xml",
            id="device-list",
        ),
        pytest.param(
            "get_device_status",
            ("SN1",),
            "SyrSafeFloor_GetDeviceCollectionStatus.xml",
            id="status",
        ),
        pytest.param(
            "get_statistics",
            ("SN1", _STATISTICS[0]),
            "SyrSafeFloor_GetSafeFloorStatistics_Temperature.xml",
            id="statistics",
        ),
        pytest.param(
            "set_device_status",
            ("SN1", [("setAB", "2")]),
            "SyrSafeFloor_GetDeviceCollectionStatus.xml",
            id="set",
        ),
    ],
)
async def test_each_answer_is_parsed_once(
    api_client: SyrConnectXmlAPI, method: str, args: tuple[Any, ...], fixture: str
) -> None:
    """An answer is parsed once, also for the check of a rejected token."""
    api_client.session_data = "token"
    xml = (Path(__file__).parent.parent / "fixtures/xml" / fixture).read_text(
        encoding="utf-8"
    )
    parse_xml = api_client.response_parser.parse_xml

    with (
        patch.object(api_client.http_client, "post", return_value=xml),
        patch.object(
            api_client.response_parser, "parse_xml", wraps=parse_xml
        ) as mock_parse,
    ):
        await getattr(api_client, method)(*args)

    mock_parse.assert_called_once_with(xml)


async def test_get_raw_device_list_returns_the_answer_unparsed(
    api_client: SyrConnectXmlAPI,
) -> None:
    """The device list is returned as the cloud sends it, also a rejected token."""
    api_client.session_data = "valid_session"
    answer = '<sc><msg mtid="1" /></sc>'

    with patch.object(api_client.http_client, "post", return_value=answer) as post:
        assert await api_client.get_raw_device_list("project1") == answer

    url, data = post.call_args.args
    assert url == api_client._device_list_url
    assert data["xml"] == api_client.payload_builder.build_device_get_list_payload(
        "valid_session", "project1"
    )


async def test_get_raw_device_status_returns_the_answer_unparsed(
    api_client: SyrConnectXmlAPI,
) -> None:
    """The status of a device is returned as the cloud sends it."""
    api_client.session_data = "valid_session"

    with patch.object(api_client.http_client, "post", return_value="<sc />") as post:
        assert await api_client.get_raw_device_status("SN1") == "<sc />"

    url, data = post.call_args.args
    assert url == api_client._device_get_status_url
    assert data["xml"] == api_client.payload_builder.build_device_get_status_payload(
        "valid_session", "dclg1"
    )


async def test_get_raw_device_list_logs_in_first(api_client: SyrConnectXmlAPI) -> None:
    """Without a session token the client logs in before the request."""
    api_client.session_data = ""

    async def _login() -> bool:
        api_client.session_data = "new_session"
        return True

    with (
        patch.object(api_client, "login", side_effect=_login) as login,
        patch.object(api_client.http_client, "post", return_value="<sc />"),
    ):
        await api_client.get_raw_device_list("project1")

    login.assert_awaited_once()


def test_parse_device_list(api_client: SyrConnectXmlAPI) -> None:
    """The devices are read from a raw device list answer."""
    xml = (
        Path(__file__).parent.parent
        / "fixtures/xml/SyrSafeTechPlus_GetProjectDeviceCollections.xml"
    ).read_text(encoding="utf-8")

    devices = api_client.parse_device_list(xml)

    assert devices == api_client.response_parser.parse_device_list_response(xml)
    assert devices


@pytest.mark.parametrize("user_agent", [None, "", "   "])
def test_empty_user_agent_is_rejected(user_agent: str | None) -> None:
    """The XML API client does not send an empty User-Agent."""
    with pytest.raises(ValueError, match="user_agent is required"):
        SyrConnectXmlAPI(
            MagicMock(), "user", "secret", service=_SYR_SERVICE, user_agent=user_agent
        )


def test_missing_user_agent_is_rejected() -> None:
    """A caller that passes no User-Agent gets a ValueError."""
    with pytest.raises(ValueError, match="user_agent is required"):
        SyrConnectXmlAPI(MagicMock(), "user", "secret", service=_SYR_SERVICE)


async def test_device_requests_use_the_dclg_of_the_device_list(
    mock_session: MagicMock, user_agent: str
) -> None:
    """The caller addresses a device by its serial number, the request carries its dclg."""
    api = SyrConnectXmlAPI(
        mock_session, "user", "secret", service=_SYR_SERVICE, user_agent=user_agent
    )
    api.session_data = "token"
    device_list = (
        '<sc><prs><pr pg="p1"/></prs>'
        '<dvs><d dclg="0b09f7ce-41a0-4085-9e69-fa8827a32b6f" sn="123456789"/></dvs></sc>'
    )

    with patch.object(api.http_client, "post", return_value=device_list):
        [device] = await api.get_devices("p1")
    assert device["id"] == "123456789"

    with patch.object(api.http_client, "post", return_value="<sc></sc>") as post:
        await api.set_device_status("123456789", [("setAB", "2")])
    assert (
        'dclg="0b09f7ce-41a0-4085-9e69-fa8827a32b6f"' in post.call_args.args[1]["xml"]
    )


def test_parse_device_list_remembers_the_dclg(
    mock_session: MagicMock, user_agent: str
) -> None:
    """A device list parsed for diagnostics makes its devices known as well."""
    api = SyrConnectXmlAPI(
        mock_session, "user", "secret", service=_SYR_SERVICE, user_agent=user_agent
    )
    api.parse_device_list(
        '<sc><prs><pr pg="p1"/></prs><dvs><d dclg="abc" sn="SN1"/></dvs></sc>'
    )

    assert api._dclg("SN1") == "abc"


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("get_device_status", ("SN-unknown",)),
        ("get_raw_device_status", ("SN-unknown",)),
        ("set_device_status", ("SN-unknown", [("setAB", "2")])),
        ("get_statistics", ("SN-unknown", _STATISTICS[0])),
    ],
)
async def test_unknown_device_raises_before_any_request(
    api_client: SyrConnectXmlAPI, method: str, args: tuple[Any, ...]
) -> None:
    """A device that is in no device list fetched so far cannot be addressed."""
    with (
        patch.object(api_client.http_client, "post") as post,
        pytest.raises(SyrConnectDeviceNotFoundError, match="SN-unknown"),
    ):
        await getattr(api_client, method)(*args)

    post.assert_not_called()
