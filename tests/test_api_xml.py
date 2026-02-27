"""Test the SYR Connect API client."""
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import pytest
import aiohttp

from custom_components.syr_connect.api_xml import SyrConnectAPI
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
    return SyrConnectAPI(mock_session, "test@example.com", "testpassword")


async def test_session_valid_check(api_client):
    """Test session validity checking."""
    # No session data
    assert not api_client.is_session_valid()
    
    # Has session but no expiry
    api_client.session_data = "test_session"
    assert not api_client.is_session_valid()
    
    # Has session with future expiry
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    assert api_client.is_session_valid()
    
    # Has session with past expiry
    api_client.session_expires_at = datetime.now() - timedelta(minutes=10)
    assert not api_client.is_session_valid()


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
        assert api_client.session_expires_at is not None


async def test_login_auth_error(api_client):
    """Test login with authentication error."""
    with patch.object(api_client.http_client, 'post', side_effect=ValueError("Invalid credentials")):
        with pytest.raises(SyrConnectAuthError):
            await api_client.login()


async def test_login_connection_error(api_client):
    """Test login with connection error."""
    with patch.object(api_client.http_client, 'post', side_effect=aiohttp.ClientError("Connection failed")):
        with pytest.raises(SyrConnectConnectionError):
            await api_client.login()


async def test_get_devices_with_expired_session(api_client):
    """Test get_devices re-authenticates on expired session."""
    api_client.session_data = "old_session"
    api_client.session_expires_at = datetime.now() - timedelta(minutes=1)
    
    with patch.object(api_client, 'login', return_value=True) as mock_login, \
         patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_list_response', return_value=[]):
        
        await api_client.get_devices("project1")
        
        # Should have called login due to expired session
        mock_login.assert_called_once()


async def test_get_device_status_with_valid_session(api_client):
    """Test get_device_status uses existing valid session."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    with patch.object(api_client, 'login', return_value=True) as mock_login, \
         patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_status_response', return_value={}):
        
        await api_client.get_device_status("device1")
        
        # Should NOT have called login
        mock_login.assert_not_called()


async def test_set_device_status_value_conversion(api_client):
    """Test set_device_status converts boolean to int."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>') as mock_post:
        await api_client.set_device_status("device1", "setSIR", 0)
        
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
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    with patch.object(api_client.http_client, 'post', side_effect=RuntimeError("API error")):
        with pytest.raises(RuntimeError, match="API error"):
            await api_client.get_devices("project1")


async def test_get_devices_id_fallback(api_client):
    """Test get_devices falls back to serial_number for id."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    device_without_id = {
        "name": "Test Device",
        "serial_number": "SN12345",
        "dclg": "DCLG123",
    }
    
    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_list_response', return_value=[device_without_id]):
        
        devices = await api_client.get_devices("project1")
        
        assert len(devices) == 1
        assert devices[0]['id'] == "SN12345"  # Should use serial_number as id


async def test_get_device_status_returns_none(api_client):
    """Test get_device_status returns None when parser returns None."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_status_response', return_value=None):
        
        result = await api_client.get_device_status("device1")
        
        assert result is None


async def test_get_device_status_exception_handling(api_client):
    """Test get_device_status exception is raised."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    with patch.object(api_client.http_client, 'post', side_effect=RuntimeError("Status error")):
        with pytest.raises(RuntimeError, match="Status error"):
            await api_client.get_device_status("device1")


async def test_set_device_status_with_expired_session(api_client):
    """Test set_device_status re-authenticates on expired session."""
    api_client.session_data = "old_session"
    api_client.session_expires_at = datetime.now() - timedelta(minutes=1)
    
    with patch.object(api_client, 'login', return_value=True) as mock_login, \
         patch.object(api_client.http_client, 'post', return_value='<sc></sc>'):
        
        await api_client.set_device_status("device1", "setSIR", 1)
        
        # Should have called login due to expired session
        mock_login.assert_called_once()


async def test_set_device_status_boolean_false(api_client):
    """Test set_device_status converts False to 0."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    with patch.object(api_client.payload_builder, 'build_set_status_payload', return_value="<payload/>") as mock_build, \
         patch.object(api_client.http_client, 'post', return_value='<sc></sc>'):
        
        await api_client.set_device_status("device1", "setSIR", False)
        
        # Verify boolean False was converted to 0
        call_args = mock_build.call_args
        assert call_args[0][3] == 0  # value parameter should be 0


async def test_set_device_status_boolean_true(api_client):
    """Test set_device_status converts True to 1."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    with patch.object(api_client.payload_builder, 'build_set_status_payload', return_value="<payload/>") as mock_build, \
         patch.object(api_client.http_client, 'post', return_value='<sc></sc>'):
        
        await api_client.set_device_status("device1", "setSIR", True)
        
        # Verify boolean True was converted to 1
        call_args = mock_build.call_args
        assert call_args[0][3] == 1  # value parameter should be 1


async def test_set_device_status_exception_handling(api_client):
    """Test set_device_status exception is raised."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    with patch.object(api_client.http_client, 'post', side_effect=RuntimeError("Set error")):
        with pytest.raises(RuntimeError, match="Set error"):
            await api_client.set_device_status("device1", "setSIR", 1)


async def test_get_statistics_water(api_client):
    """Test get_statistics for water statistics."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    mock_stats = {"daily": "100", "weekly": "700", "monthly": "3000"}
    
    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_statistics_response', return_value=mock_stats):
        
        result = await api_client.get_statistics("device1", "water")
        
        assert result == mock_stats


async def test_get_statistics_salt(api_client):
    """Test get_statistics for salt statistics."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    mock_stats = {"consumed": "50", "remaining": "150"}
    
    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_statistics_response', return_value=mock_stats):
        
        result = await api_client.get_statistics("device1", "salt")
        
        assert result == mock_stats


async def test_get_statistics_exception_handling(api_client):
    """Test get_statistics exception is raised."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    with patch.object(api_client.http_client, 'post', side_effect=RuntimeError("Stats error")):
        with pytest.raises(RuntimeError, match="Stats error"):
            await api_client.get_statistics("device1", "water")


async def test_login_with_parser_value_error(api_client):
    """Test login raises SyrConnectAuthError when parser raises ValueError."""
    mock_response = """<?xml version="1.0"?><sc><api>encrypted_data</api></sc>"""
    
    with patch.object(api_client.http_client, 'post', return_value=mock_response), \
         patch.object(api_client.response_parser, 'parse_login_response', side_effect=ValueError("Invalid response structure")):
        
        with pytest.raises(SyrConnectAuthError, match="Authentication failed"):
            await api_client.login()


async def test_login_with_decryption_parser_error(api_client):
    """Test login raises SyrConnectAuthError when decryption parsing fails."""
    mock_response = """<?xml version="1.0"?><sc><api>encrypted_data</api></sc>"""
    
    with patch.object(api_client.http_client, 'post', return_value=mock_response), \
         patch.object(api_client.response_parser, 'parse_login_response', return_value=("encrypted", {})), \
         patch.object(api_client.encryption, 'decrypt', return_value='<invalid>'), \
         patch.object(api_client.response_parser, 'parse_decrypted_login', side_effect=ValueError("Invalid decrypted data")):
        
        with pytest.raises(SyrConnectAuthError, match="Authentication failed"):
            await api_client.login()


async def test_get_devices_adds_project_id(api_client):
    """Test get_devices adds project_id to each device."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    device_data = {
        "id": "device1",
        "name": "Test Device",
        "serial_number": "SN123",
        "dclg": "DCLG123",
    }
    
    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_list_response', return_value=[device_data]):
        
        devices = await api_client.get_devices("project123")
        
        assert len(devices) == 1
        assert devices[0]['project_id'] == "project123"


async def test_get_device_status_with_expired_session(api_client):
    """Test get_device_status re-authenticates on expired session."""
    api_client.session_data = "old_session"
    api_client.session_expires_at = datetime.now() - timedelta(minutes=1)
    
    with patch.object(api_client, 'login', return_value=True) as mock_login, \
         patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_status_response', return_value={}):
        
        await api_client.get_device_status("device1")
        
        # Should have called login due to expired session
        mock_login.assert_called_once()


async def test_get_statistics_default_type(api_client):
    """Test get_statistics with default statistic_type parameter."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    mock_stats = {"daily": "100"}
    
    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_statistics_response', return_value=mock_stats):
        
        # Call without explicit statistic_type (should default to "water")
        result = await api_client.get_statistics("device1")
        
        assert result == mock_stats


async def test_set_device_status_non_boolean_value(api_client):
    """Test set_device_status with non-boolean value (no conversion)."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    with patch.object(api_client.payload_builder, 'build_set_status_payload', return_value="<payload/>") as mock_build, \
         patch.object(api_client.http_client, 'post', return_value='<sc></sc>'):
        
        await api_client.set_device_status("device1", "setSV1", 10)
        
        # Verify value is passed as-is (not converted)
        call_args = mock_build.call_args
        assert call_args[0][3] == 10  # value parameter should be 10


async def test_get_devices_with_device_already_has_id(api_client):
    """Test get_devices when device already has 'id' field."""
    api_client.session_data = "valid_session"
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    
    device_with_id = {
        "id": "EXISTING_ID",
        "name": "Test Device",
        "serial_number": "SN12345",
        "dclg": "DCLG123",
    }
    
    with patch.object(api_client.http_client, 'post', return_value='<sc></sc>'), \
         patch.object(api_client.response_parser, 'parse_device_list_response', return_value=[device_with_id]):
        
        devices = await api_client.get_devices("project1")
        
        assert len(devices) == 1
        # Should keep existing id, not overwrite with serial_number
        assert devices[0]['id'] == "EXISTING_ID"

