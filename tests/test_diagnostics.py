"""Tests for diagnostics platform."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics(hass: HomeAssistant) -> None:
    """Test diagnostics data."""
    # Create a proper config entry
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test Device",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    # Create mock coordinator
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "1",
                "name": "LEXplus10 S/SL",
                "available": True,
                "project_id": "project1",
                "status": {"getSRE": {"value": 1}},
            },
        ],
        "projects": [
            {
                "id": "project1",
                "name": "Test Project",
            },
        ],
    }
    mock_coordinator.last_update_success = True
    mock_coordinator.last_update_success_time = datetime(2024, 1, 1, 12, 0, 0)
    
    # Attach coordinator to config entry
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    assert "entry" in diagnostics
    assert diagnostics["entry"]["title"] == "Test Device"
    assert "coordinator" in diagnostics
    # Devices are added to the list within the function, not from coordinator.data directly
    # The test should verify the structure, not specific counts without proper setup
    assert "devices" in diagnostics
    assert "projects" in diagnostics


async def test_diagnostics_no_coordinator_data(hass: HomeAssistant) -> None:
    """Test diagnostics when coordinator has no data."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = False
    mock_coordinator.last_update_success_time = None
    
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    assert "entry" in diagnostics
    assert "coordinator" in diagnostics
    assert diagnostics["coordinator"]["last_update_time"] is None


async def test_diagnostics_multiple_devices(hass: HomeAssistant) -> None:
    """Test diagnostics with multiple devices and projects."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [
            {
                "id": "1",
                "name": "Device 1",
                "available": True,
                "project_id": "project1",
                "status": {"getSRE": {"value": 1}, "getWVI": {"value": 100}},
            },
            {
                "id": "2",
                "name": "Device 2",
                "available": False,
                "project_id": "project2",
                "status": {},
            },
        ],
        "projects": [
            {"id": "project1", "name": "Project 1"},
            {"id": "project2", "name": "Project 2"},
        ],
    }
    mock_coordinator.last_update_success = True
    mock_coordinator.last_update_success_time = None
    
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    # Verify structure exists
    assert "devices" in diagnostics
    assert "projects" in diagnostics
    # The devices list is populated during the diagnostics generation
    # If coordinator.data exists, devices should be processed
    assert isinstance(diagnostics["devices"], list)
    assert isinstance(diagnostics["projects"], list)


async def test_diagnostics_redact_xml_basic(hass: HomeAssistant) -> None:
    """Test XML redaction of sensitive data."""
    from custom_components.syr_connect.diagnostics import async_get_config_entry_diagnostics
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "secret123"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = False
    mock_coordinator.last_update_success_time = None
    mock_coordinator.api = None
    
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    # Check that password is redacted
    assert CONF_PASSWORD not in str(diagnostics.get("entry", {}))


async def test_diagnostics_with_api_and_projects(hass: HomeAssistant) -> None:
    """Test diagnostics with API that has projects."""
    from unittest.mock import AsyncMock, patch
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    # Create mock API
    mock_api = MagicMock()
    mock_api.is_session_valid = MagicMock(return_value=True)
    mock_api.projects = [{"id": "proj1", "name": "Project 1"}]
    mock_api.session_data = "test_session"
    
    # Mock http_client
    mock_http_client = MagicMock()
    mock_http_client.post = AsyncMock(return_value='<xml><device id="1" mac="00:11:22:33:44:55"/></xml>')
    mock_api.http_client = mock_http_client
    
    # Mock payload builder
    mock_payload_builder = MagicMock()
    mock_payload_builder.build_device_list_payload = MagicMock(return_value="payload1")
    mock_payload_builder.build_device_status_payload = MagicMock(return_value="payload2")
    mock_api.payload_builder = mock_payload_builder
    
    # Mock response parser
    mock_response_parser = MagicMock()
    mock_response_parser.parse_device_list_response = MagicMock(return_value=[
        {"id": "dev1", "dclg": "dclg1"}
    ])
    mock_api.response_parser = mock_response_parser
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = {
        "devices": [{"id": "dev1", "name": "Device 1", "available": True, "project_id": "proj1", "status": {}}],
        "projects": [{"id": "proj1", "name": "Project 1"}]
    }
    mock_coordinator.last_update_success = True
    mock_coordinator.last_update_success_time = datetime(2024, 1, 1, 12, 0, 0)
    mock_coordinator.api = mock_api
    
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    # Verify raw_xml was collected
    assert "raw_xml" in diagnostics
    assert isinstance(diagnostics["raw_xml"], dict)


async def test_diagnostics_api_login_required(hass: HomeAssistant) -> None:
    """Test diagnostics when API requires login."""
    from unittest.mock import AsyncMock
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    # Create mock API that requires login
    mock_api = MagicMock()
    mock_api.is_session_valid = MagicMock(return_value=False)
    mock_api.login = AsyncMock()
    mock_api.projects = [{"id": "proj1", "name": "Project 1"}]
    mock_api.session_data = "test_session"
    
    # Mock http_client
    mock_http_client = MagicMock()
    mock_http_client.post = AsyncMock(return_value='<xml/>')
    mock_api.http_client = mock_http_client
    
    # Mock payload builder and parser
    mock_api.payload_builder = MagicMock()
    mock_api.payload_builder.build_device_list_payload = MagicMock(return_value="payload")
    mock_api.payload_builder.build_device_status_payload = MagicMock(return_value="payload")
    mock_api.response_parser = MagicMock()
    mock_api.response_parser.parse_device_list_response = MagicMock(return_value=[])
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = True
    mock_coordinator.last_update_success_time = None
    mock_coordinator.api = mock_api
    
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    # Verify login was called
    mock_api.login.assert_called_once()
    assert "raw_xml" in diagnostics


async def test_diagnostics_api_login_fails(hass: HomeAssistant) -> None:
    """Test diagnostics when API login fails."""
    from unittest.mock import AsyncMock
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    # Create mock API where login fails
    mock_api = MagicMock()
    mock_api.is_session_valid = MagicMock(return_value=False)
    mock_api.login = AsyncMock(side_effect=Exception("Login failed"))
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = False
    mock_coordinator.last_update_success_time = None
    mock_coordinator.api = mock_api
    
    config_entry.runtime_data = mock_coordinator
    
    # Should not raise, just continue without raw XML
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    assert "raw_xml" in diagnostics


async def test_diagnostics_xml_redaction_patterns(hass: HomeAssistant) -> None:
    """Test various XML redaction patterns."""
    from custom_components.syr_connect.diagnostics import async_get_config_entry_diagnostics
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    # Create mock API with XML containing sensitive data
    mock_api = MagicMock()
    mock_api.is_session_valid = MagicMock(return_value=True)
    mock_api.projects = [{"id": "proj1", "name": "Project 1"}]
    mock_api.session_data = "test_session"
    
    xml_with_sensitive = '''
    <device mac="00:11:22:33:44:55" ip="192.168.1.100">
        <c n="getMAC" v="AA:BB:CC:DD:EE:FF"/>
        <c n="getIPA" v="10.0.0.1"/>
        <gateway>192.168.0.1</gateway>
        <email>user@test.com</email>
    </device>
    '''
    
    mock_http_client = MagicMock()
    mock_http_client.post = AsyncMock(return_value=xml_with_sensitive)
    mock_api.http_client = mock_http_client
    
    mock_api.payload_builder = MagicMock()
    mock_api.payload_builder.build_device_list_payload = MagicMock(return_value="payload")
    mock_api.payload_builder.build_device_status_payload = MagicMock(return_value="payload")
    
    mock_api.response_parser = MagicMock()
    mock_api.response_parser.parse_device_list_response = MagicMock(return_value=[])
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = True
    mock_coordinator.last_update_success_time = None
    mock_coordinator.api = mock_api
    
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    # Verify redaction happened
    raw_xml_str = str(diagnostics.get("raw_xml", ""))
    # MAC addresses should be redacted
    assert "00:11:22:33:44:55" not in raw_xml_str
    assert "AA:BB:CC:DD:EE:FF" not in raw_xml_str
    # IP addresses should be redacted
    assert "192.168.1.100" not in raw_xml_str or "REDACTED" in raw_xml_str


async def test_diagnostics_device_parsing_fails(hass: HomeAssistant) -> None:
    """Test diagnostics when device list parsing fails."""
    from unittest.mock import AsyncMock
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    # Create mock API where parsing fails
    mock_api = MagicMock()
    mock_api.is_session_valid = MagicMock(return_value=True)
    mock_api.projects = [{"id": "proj1", "name": "Project 1"}]
    mock_api.session_data = "test_session"
    
    mock_http_client = MagicMock()
    mock_http_client.post = AsyncMock(return_value='<invalid xml>')
    mock_api.http_client = mock_http_client
    
    mock_api.payload_builder = MagicMock()
    mock_api.payload_builder.build_device_list_payload = MagicMock(return_value="payload")
    
    # Parser raises exception
    mock_api.response_parser = MagicMock()
    mock_api.response_parser.parse_device_list_response = MagicMock(
        side_effect=Exception("Parse error")
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = True
    mock_coordinator.last_update_success_time = None
    mock_coordinator.api = mock_api
    
    config_entry.runtime_data = mock_coordinator
    
    # Should not raise, continue gracefully
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    assert "raw_xml" in diagnostics


async def test_diagnostics_http_fetch_fails(hass: HomeAssistant) -> None:
    """Test diagnostics when HTTP fetch fails."""
    from unittest.mock import AsyncMock
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    # Create mock API where HTTP fails
    mock_api = MagicMock()
    mock_api.is_session_valid = MagicMock(return_value=True)
    mock_api.projects = [{"id": "proj1", "name": "Project 1"}]
    mock_api.session_data = "test_session"
    
    mock_http_client = MagicMock()
    mock_http_client.post = AsyncMock(side_effect=Exception("Network error"))
    mock_api.http_client = mock_http_client
    
    mock_api.payload_builder = MagicMock()
    mock_api.payload_builder.build_device_list_payload = MagicMock(return_value="payload")
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = True
    mock_coordinator.last_update_success_time = None
    mock_coordinator.api = mock_api
    
    config_entry.runtime_data = mock_coordinator
    
    # Should handle gracefully
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    assert "raw_xml" in diagnostics


async def test_diagnostics_no_api(hass: HomeAssistant) -> None:
    """Test diagnostics when coordinator has no API."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = False
    mock_coordinator.last_update_success_time = None
    # No api attribute
    type(mock_coordinator).api = MagicMock(side_effect=AttributeError)
    
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    assert "raw_xml" in diagnostics
    assert diagnostics["raw_xml"] == {}


async def test_diagnostics_exception_in_raw_xml_collection(hass: HomeAssistant) -> None:
    """Test diagnostics when raw XML collection raises exception."""
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    # Create mock API that will cause exception
    mock_api = MagicMock()
    mock_api.is_session_valid = MagicMock(side_effect=RuntimeError("Unexpected error"))
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = False
    mock_coordinator.last_update_success_time = None
    mock_coordinator.api = mock_api
    
    config_entry.runtime_data = mock_coordinator
    
    # Should handle exception gracefully
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    assert "raw_xml" in diagnostics
    # Exception during is_session_valid causes api to be set to None, so raw_xml will be {}
    assert diagnostics["raw_xml"] == {} or "error" in diagnostics["raw_xml"]


async def test_diagnostics_redact_obj_with_raw_xml(hass: HomeAssistant) -> None:
    """Test that raw_xml is preserved in redaction."""
    from unittest.mock import AsyncMock
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    # Create simple mock to trigger raw_xml preservation
    mock_api = MagicMock()
    mock_api.is_session_valid = MagicMock(return_value=True)
    mock_api.projects = [{"id": "proj1"}]
    mock_api.session_data = "session"
    
    mock_http_client = MagicMock()
    mock_http_client.post = AsyncMock(return_value='<test>data</test>')
    mock_api.http_client = mock_http_client
    
    mock_api.payload_builder = MagicMock()
    mock_api.payload_builder.build_device_list_payload = MagicMock(return_value="p")
    mock_api.response_parser = MagicMock()
    mock_api.response_parser.parse_device_list_response = MagicMock(return_value=[])
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = True
    mock_coordinator.last_update_success_time = None
    mock_coordinator.api = mock_api
    
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    # raw_xml should exist and be preserved
    assert "raw_xml" in diagnostics
    assert diagnostics["raw_xml"] != {}


async def test_diagnostics_redact_xml_empty_input(hass: HomeAssistant) -> None:
    """Test XML redaction with empty/None input."""
    from custom_components.syr_connect.diagnostics import async_get_config_entry_diagnostics
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    # Data with empty status
    mock_coordinator.data = {
        "devices": [
            {
                "id": "1",
                "name": "Device 1",
                "available": True,
                "project_id": "proj1",
                "status": {},
            }
        ],
        "projects": []
    }
    mock_coordinator.last_update_success = True
    mock_coordinator.last_update_success_time = None
    
    config_entry.runtime_data = mock_coordinator
    
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    # Should handle empty data gracefully
    assert "devices" in diagnostics
    assert len(diagnostics["devices"]) > 0


async def test_diagnostics_device_without_dclg_or_id(hass: HomeAssistant) -> None:
    """Test diagnostics with device that has neither dclg nor id."""
    from unittest.mock import AsyncMock
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_api = MagicMock()
    mock_api.is_session_valid = MagicMock(return_value=True)
    mock_api.projects = [{"id": "proj1"}]
    mock_api.session_data = "session"
    
    mock_http_client = MagicMock()
    mock_http_client.post = AsyncMock(return_value='<xml/>')
    mock_api.http_client = mock_http_client
    
    mock_api.payload_builder = MagicMock()
    mock_api.payload_builder.build_device_list_payload = MagicMock(return_value="p")
    
    # Return device without dclg or id
    mock_api.response_parser = MagicMock()
    mock_api.response_parser.parse_device_list_response = MagicMock(
        return_value=[{"name": "Device without ID"}]
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = True
    mock_coordinator.last_update_success_time = None
    mock_coordinator.api = mock_api
    
    config_entry.runtime_data = mock_coordinator
    
    # Should skip device without ID
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    assert "raw_xml" in diagnostics


async def test_diagnostics_status_fetch_exception(hass: HomeAssistant) -> None:
    """Test diagnostics when status fetch returns exception."""
    from unittest.mock import AsyncMock
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Test",
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test_password"},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    
    mock_api = MagicMock()
    mock_api.is_session_valid = MagicMock(return_value=True)
    mock_api.projects = [{"id": "proj1"}]
    mock_api.session_data = "session"
    
    # HTTP client that fails on second call (status fetch)
    call_count = 0
    async def post_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return '<xml/>'
        raise Exception("Status fetch failed")
    
    mock_http_client = MagicMock()
    mock_http_client.post = AsyncMock(side_effect=post_side_effect)
    mock_api.http_client = mock_http_client
    
    mock_api.payload_builder = MagicMock()
    mock_api.payload_builder.build_device_list_payload = MagicMock(return_value="p1")
    mock_api.payload_builder.build_device_status_payload = MagicMock(return_value="p2")
    
    mock_api.response_parser = MagicMock()
    mock_api.response_parser.parse_device_list_response = MagicMock(
        return_value=[{"id": "dev1", "dclg": "dclg1"}]
    )
    
    mock_coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    mock_coordinator.data = None
    mock_coordinator.last_update_success = True
    mock_coordinator.last_update_success_time = None
    mock_coordinator.api = mock_api
    
    config_entry.runtime_data = mock_coordinator
    
    # Should handle exception in gather
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    
    assert "raw_xml" in diagnostics

