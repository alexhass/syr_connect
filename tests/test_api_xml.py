"""Test the SYR Connect API client."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from custom_components.syr_connect.api_xml import SyrConnectXmlAPI
from custom_components.syr_connect.exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
)


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def api_client(mock_session):
    """Create an API client instance."""
    return SyrConnectXmlAPI(mock_session, "test@example.com", "testpassword")


async def test_login_logs_payload_with_locale_but_without_password(mock_session, caplog):
    """The login payload is logged (to check lng/reg), with the password masked."""
    api = SyrConnectXmlAPI(mock_session, "user@example.com", "s3cr3t!", language="en-DE")
    caplog.set_level("DEBUG", logger="custom_components.syr_connect.api_xml")

    with patch.object(api.http_client, "post", side_effect=aiohttp.ClientError("offline")), \
         pytest.raises(SyrConnectConnectionError):
        await api.login()

    assert 'lng="en" reg="DE"' in caplog.text
    assert '<usr n="user@example.com" v="***"' in caplog.text
    assert "s3cr3t!" not in caplog.text


def test_language_is_passed_to_payload_builder_and_http_client(mock_session):
    """The locale reaches the login/statistics payloads and the Accept-Language header."""
    api = SyrConnectXmlAPI(mock_session, "test@example.com", "testpassword", language="en-DE")

    assert api.payload_builder.app_version.startswith("App-3.9.7-en-DE-iOS-")
    assert api.payload_builder._compute_locale_lang_reg() == ("en", "DE")
    assert api.http_client._build_accept_language() == "en-DE,en;q=0.9"


def test_language_defaults(api_client):
    """Without a locale, the app version, payloads and header all fall back to en-US."""
    assert api_client.payload_builder.app_version.startswith("App-3.9.7-en-US-iOS-")
    assert api_client.payload_builder._compute_locale_lang_reg() == ("en", "US")
    assert api_client.http_client._build_accept_language() == "en-US,en;q=0.9"


INVALID_TOKEN_XML = (Path(__file__).parent / "fixtures/xml/SyrTestDevice_InvalidSessionResponse.xml").read_text(encoding="utf-8")


async def test_session_valid_check(api_client):
    """A session is usable as soon as a token from a login exists; there is no client-side expiry."""
    assert not api_client.is_session_valid()

    api_client.session_data = "test_session"
    assert api_client.is_session_valid()


async def test_parallel_first_requests_log_in_only_once(api_client):
    """Without a token yet, parallel requests share one login instead of each logging in."""
    import asyncio

    async def _login():
        await asyncio.sleep(0)  # let the other tasks reach the lock meanwhile
        api_client.session_data = "new"
        return True

    with patch.object(api_client, "login", side_effect=_login) as login:
        await asyncio.gather(*(api_client._ensure_session() for _ in range(5)))

    assert login.await_count == 1
    assert api_client.session_data == "new"


async def test_parallel_rejections_relogin_only_once(api_client):
    """When parallel requests get the token rejected at the same time, only one logs in again."""
    import asyncio

    api_client.session_data = "old"

    async def _login():
        await asyncio.sleep(0)
        api_client.session_data = "new"
        return True

    with patch.object(api_client, "login", side_effect=_login) as login:
        await asyncio.gather(*(api_client._relogin("old") for _ in range(5)))

    assert login.await_count == 1
    assert api_client.session_data == "new"


@pytest.mark.parametrize(
    ("method", "args", "parser"),
    [
        ("get_devices", ("project1",), "parse_device_list_response"),
        ("get_device_status", ("dclg1",), "parse_device_status_response"),
        ("set_device_status", ("dclg1", [("setAB", "2")]), None),
        ("get_statistics", ("dclg1", "water"), "parse_statistics_response"),
    ],
)
async def test_rejected_token_relogs_in_and_retries_once(api_client, method, args, parser):
    """The real "invalid token" answer triggers one re-login and a retry with the new token."""
    api_client.session_data = "old"
    posted_payloads: list[str] = []

    async def _post(_url, data, **_kw):
        posted_payloads.append(data["xml"])
        return INVALID_TOKEN_XML if len(posted_payloads) == 1 else "<sc><ok /></sc>"

    async def _login():
        api_client.session_data = "new"
        return True

    with patch.object(api_client.http_client, "post", side_effect=_post), \
         patch.object(api_client, "login", side_effect=_login) as login:
        if parser:
            with patch.object(api_client.response_parser, parser, return_value=[] if method == "get_devices" else {}):
                await getattr(api_client, method)(*args)
        else:
            await getattr(api_client, method)(*args)

    login.assert_awaited_once()
    assert len(posted_payloads) == 2
    assert 'ug="old"' in posted_payloads[0]
    assert 'ug="new"' in posted_payloads[1]


async def test_rejected_token_twice_raises_session_expired(api_client):
    """If the new token is rejected as well, no loop: SyrConnectSessionExpiredError (a connection error)."""
    from custom_components.syr_connect.exceptions import SyrConnectSessionExpiredError

    api_client.session_data = "old"

    async def _login():
        api_client.session_data = "new"
        return True

    with patch.object(api_client.http_client, "post", return_value=INVALID_TOKEN_XML) as post, \
         patch.object(api_client, "login", side_effect=_login) as login:
        with pytest.raises(SyrConnectSessionExpiredError) as excinfo:
            await api_client.get_device_status("dclg1")

    assert isinstance(excinfo.value, SyrConnectConnectionError)
    login.assert_awaited_once()
    assert post.await_count == 2


async def test_valid_response_does_not_relogin(api_client):
    """A normal answer is used as is, without any login."""
    api_client.session_data = "token"

    with patch.object(api_client.http_client, "post", return_value="<sc><ok /></sc>") as post, \
         patch.object(api_client, "login") as login, \
         patch.object(api_client.response_parser, "parse_device_status_response", return_value={"getFLO": "5"}):
        assert await api_client.get_device_status("dclg1") == {"getFLO": "5"}

    login.assert_not_called()
    post.assert_awaited_once()


async def test_login_success(api_client):
    """Test successful login."""
    mock_response = """<?xml version="1.0"?><sc><api>encrypted_data</api></sc>"""

    with patch.object(api_client.http_client, 'post', return_value=mock_response), \
         patch.object(api_client.response_parser, 'parse_login_response', return_value=("encrypted", {})), \
         patch.object(api_client.encryption, 'decrypt', return_value='<usr id="123"/><prs><pre id="p1" n="Project1"/></prs>'), \
         patch.object(api_client.response_parser, 'parse_decrypted_login', return_value=("123", [{"id": "p1", "name": "Project1"}])):

        result = await api_client.login()

        assert result is True
        assert api_client.session_data == "123"
        assert len(api_client.projects) == 1


async def test_login_auth_error(api_client):
    """Wrong credentials: valid encrypted answer whose decrypted content has no session -> re-auth."""
    with patch.object(api_client.http_client, 'post', return_value="<sc><api>encrypted</api></sc>"),          patch.object(api_client.response_parser, 'parse_login_response', return_value=("encrypted", {})),          patch.object(api_client.encryption, 'decrypt', return_value='<prs><pre id="p1" n="P1"/></prs>'):
        with pytest.raises(SyrConnectAuthError, match="Invalid credentials"):
            await api_client.login()


async def test_login_connection_error(api_client):
    """Test login with connection error."""
    with patch.object(api_client.http_client, 'post', side_effect=aiohttp.ClientError("Connection failed")):
        with pytest.raises(SyrConnectConnectionError):
            await api_client.login()


async def test_get_device_status_with_valid_session(api_client):
    """Test get_device_status uses existing valid session."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client, 'login', return_value=True) as mock_login, \
         patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_status_response', return_value={}):

        await api_client.get_device_status("device1")

        # Should NOT have called login
        mock_login.assert_not_called()


async def test_set_device_status_value_conversion(api_client):
    """Test set_device_status converts boolean to int."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>') as mock_post:
        await api_client.set_device_status("device1", [("setSIR", 0)])

        # Verify the payload contains '1' not 'True'
        call_args = mock_post.call_args
        assert '1' in str(call_args)


async def test_login_timeout_error(api_client):
    """Test login with timeout error."""
    with patch.object(api_client.http_client, 'post', side_effect=TimeoutError("Request timeout")):
        with pytest.raises(SyrConnectConnectionError, match="Connection failed"):
            await api_client.login()


async def test_login_generic_exception(api_client):
    """Test login with generic unexpected exception."""
    with patch.object(api_client.http_client, 'post', side_effect=RuntimeError("Unexpected error")):
        with pytest.raises(SyrConnectConnectionError, match="Login failed"):
            await api_client.login()


async def test_get_devices_exception_handling(api_client):
    """Test get_devices exception is raised."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.http_client, 'post', side_effect=RuntimeError("API error")):
        with pytest.raises(RuntimeError, match="API error"):
            await api_client.get_devices("project1")


async def test_get_devices_connection_client_error(api_client):
    """Network client errors during get_devices should raise SyrConnectConnectionError."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.http_client, 'post', side_effect=aiohttp.ClientError("Connection failed")):
        with pytest.raises(SyrConnectConnectionError):
            await api_client.get_devices("project1")


async def test_get_devices_connection_timeout_error(api_client):
    """Timeout errors during get_devices should raise SyrConnectConnectionError."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.http_client, 'post', side_effect=TimeoutError("Request timeout")):
        with pytest.raises(SyrConnectConnectionError):
            await api_client.get_devices("project1")


async def test_get_devices_id_fallback(api_client):
    """Test get_devices falls back to serial_number for id."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    device_without_id = {
        "name": "Test Device",
        "serial_number": "SN12345",
        "dclg": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    }

    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_list_response', return_value=[device_without_id]):

        devices = await api_client.get_devices("project1")

        assert len(devices) == 1
        assert devices[0]['id'] == "SN12345"  # Should use serial_number as id


async def test_get_device_status_returns_none(api_client):
    """Test get_device_status returns None when parser returns None."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_status_response', return_value=None):

        result = await api_client.get_device_status("device1")

        assert result is None


async def test_get_device_status_exception_handling(api_client):
    """Test get_device_status exception is raised."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.http_client, 'post', side_effect=RuntimeError("Status error")):
        with pytest.raises(RuntimeError, match="Status error"):
            await api_client.get_device_status("device1")


async def test_set_device_status_boolean_false(api_client):
    """Test set_device_status converts False to 0."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.payload_builder, 'build_device_set_status_payload', return_value="<payload/>") as mock_build, \
         patch.object(api_client.http_client, 'post', return_value='<sc></sc>'):

        await api_client.set_device_status("device1", [("setSIR", False)])

        # Verify boolean False was converted to 0
        call_args = mock_build.call_args
        assert call_args[0][2] == [("setSIR", 0)]  # commands list with normalized value


async def test_set_device_status_boolean_true(api_client):
    """Test set_device_status converts True to 1."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.payload_builder, 'build_device_set_status_payload', return_value="<payload/>") as mock_build, \
         patch.object(api_client.http_client, 'post', return_value='<sc></sc>'):

        await api_client.set_device_status("device1", [("setSIR", True)])

        # Verify boolean True was converted to 1
        call_args = mock_build.call_args
        assert call_args[0][2] == [("setSIR", 1)]  # commands list with normalized value


async def test_set_device_status_exception_handling(api_client):
    """Test set_device_status exception is raised."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.http_client, 'post', side_effect=RuntimeError("Set error")):
        with pytest.raises(RuntimeError, match="Set error"):
            await api_client.set_device_status("device1", [("setSIR", 1)])


async def test_get_statistics_water(api_client):
    """Test get_statistics for water statistics."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    mock_stats = {"daily": "100", "weekly": "700", "monthly": "3000"}

    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_statistics_response', return_value=mock_stats):

        result = await api_client.get_statistics("device1", "water")

        assert result == mock_stats


async def test_get_statistics_salt(api_client):
    """Test get_statistics for salt statistics."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    mock_stats = {"consumed": "50", "remaining": "150"}

    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_statistics_response', return_value=mock_stats):

        result = await api_client.get_statistics("device1", "salt")

        assert result == mock_stats


async def test_get_statistics_exception_handling(api_client):
    """Test get_statistics exception is raised."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.http_client, 'post', side_effect=RuntimeError("Stats error")):
        with pytest.raises(RuntimeError, match="Stats error"):
            await api_client.get_statistics("device1", "water")


async def test_login_with_parser_value_error(api_client):
    """A malformed login answer is a connection problem, not rejected credentials (no re-auth)."""
    mock_response = """<?xml version="1.0"?><sc><api>encrypted_data</api></sc>"""

    with patch.object(api_client.http_client, 'post', return_value=mock_response), \
         patch.object(api_client.response_parser, 'parse_login_response', side_effect=ValueError("Invalid response structure")):

        with pytest.raises(SyrConnectConnectionError, match="Invalid login response"):
            await api_client.login()


async def test_login_with_decryption_parser_error(api_client):
    """A malformed decrypted answer is a connection problem, not rejected credentials (no re-auth)."""
    mock_response = """<?xml version="1.0"?><sc><api>encrypted_data</api></sc>"""

    with patch.object(api_client.http_client, 'post', return_value=mock_response), \
         patch.object(api_client.response_parser, 'parse_login_response', return_value=("encrypted", {})), \
         patch.object(api_client.encryption, 'decrypt', return_value='<invalid>'), \
         patch.object(api_client.response_parser, 'parse_decrypted_login', side_effect=ValueError("Invalid decrypted data")):

        with pytest.raises(SyrConnectConnectionError, match="Invalid login response"):
            await api_client.login()


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("get_device_status", ("dclg1",)),
        ("set_device_status", ("dclg1", [("setAB", "2")])),
        ("get_statistics", ("dclg1", "water")),
    ],
)
async def test_network_errors_are_wrapped_in_connection_error(api_client, method, args):
    """Network errors after all retries become SyrConnectConnectionError, which the entities handle."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.http_client, "post", side_effect=aiohttp.ClientError("Request failed after 3 attempts")):
        with pytest.raises(SyrConnectConnectionError, match="Request failed after 3 attempts") as excinfo:
            await getattr(api_client, method)(*args)

    assert isinstance(excinfo.value.__cause__, aiohttp.ClientError)


async def test_get_devices_adds_project_id(api_client):
    """Test get_devices adds project_id to each device."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    device_data = {
        "id": "device1",
        "name": "Test Device",
        "serial_number": "SN123",
        "dclg": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    }

    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_list_response', return_value=[device_data]):

        devices = await api_client.get_devices("project123")

        assert len(devices) == 1
        assert devices[0]['project_id'] == "project123"


async def test_get_statistics_default_type(api_client):
    """Test get_statistics with default statistic_type parameter."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    mock_stats = {"daily": "100"}

    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_statistics_response', return_value=mock_stats):

        # Call without explicit statistic_type (should default to "water")
        result = await api_client.get_statistics("device1")

        assert result == mock_stats


async def test_set_device_status_non_boolean_value(api_client):
    """Test set_device_status with non-boolean value (no conversion)."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    with patch.object(api_client.payload_builder, 'build_device_set_status_payload', return_value="<payload/>") as mock_build, \
         patch.object(api_client.http_client, 'post', return_value='<sc></sc>'):

        await api_client.set_device_status("device1", [("setSV1", 10)])

        # Verify value is passed as-is (not converted)
        call_args = mock_build.call_args
        assert call_args[0][2] == [("setSV1", 10)]  # commands list with value unchanged


async def test_get_devices_with_device_already_has_id(api_client):
    """Test get_devices when device already has 'id' field."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)

    device_with_id = {
        "id": "EXISTING_ID",
        "name": "Test Device",
        "serial_number": "SN12345",
        "dclg": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    }

    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_list_response', return_value=[device_with_id]):

        devices = await api_client.get_devices("project1")

        assert len(devices) == 1
        # Should keep existing id, not overwrite with serial_number
        assert devices[0]['id'] == "EXISTING_ID"
