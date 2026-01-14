"""Test the SYR Connect API client."""
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import pytest
import aiohttp

from syr_connect.api import SyrConnectAPI
from syr_connect.exceptions import (
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectSessionExpiredError,
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
    assert not api_client._is_session_valid()
    
    # Has session but no expiry
    api_client.session_data = "test_session"
    assert not api_client._is_session_valid()
    
    # Has session with future expiry
    api_client.session_expires_at = datetime.now() + timedelta(minutes=10)
    assert api_client._is_session_valid()
    
    # Has session with past expiry
    api_client.session_expires_at = datetime.now() - timedelta(minutes=10)
    assert not api_client._is_session_valid()


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
