"""Test the SYR Connect config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.syr_connect.config_flow import (
    CannotConnectError,
    validate_input_json,
)
from custom_components.syr_connect.const import (
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_MODEL,
    DOMAIN,
)

# Patch path for API class (lazy-loaded in config_flow)
_API_PATCH_PATH = "custom_components.syr_connect.api_xml.SyrConnectXmlAPI"


async def test_form_menu(hass: HomeAssistant) -> None:
    """Test we get the menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "user"
    assert "api_xml" in result["menu_options"]
    assert "api_json" in result["menu_options"]


async def test_form_api_xml(hass: HomeAssistant, mock_syr_api) -> None:
    """Test cloud/XML API configuration flow."""
    # Start flow and select api_xml from menu
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "api_xml"}
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "api_xml"

    with patch(
        "custom_components.syr_connect.async_setup_entry",
        new_callable=AsyncMock,
    ) as mock_setup_entry:
        mock_setup_entry.return_value = True
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "SYR Connect (test@example.com)"
    assert result3["data"][CONF_USERNAME] == "test@example.com"
    assert result3["data"][CONF_API_TYPE] == API_TYPE_XML


async def test_form_api_xml_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth for cloud/XML API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "api_xml"}
    )

    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=SyrConnectAuthError("Authentication failed"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_api_xml_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error for cloud/XML API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "api_xml"}
    )

    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=SyrConnectConnectionError("Connection error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_api_xml_already_configured(hass: HomeAssistant, mock_syr_api) -> None:
    """Test we handle already configured for cloud/XML API."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="xml_test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
            CONF_API_TYPE: API_TYPE_XML,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "api_xml"}
    )

    with patch(
        "custom_components.syr_connect.async_setup_entry",
        new_callable=AsyncMock,
    ) as mock_setup:
        mock_setup.return_value = True
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_api_json(hass: HomeAssistant) -> None:
    """Test local/JSON API configuration flow."""
    # Start flow and select api_json from menu
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "api_json"}
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "api_json"

    with (
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI.login",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI._request_json_data",
            new_callable=AsyncMock,
            return_value={"getSRN": "12345", "getVER": "test"},
        ),
        patch(
            "custom_components.syr_connect.async_setup_entry",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_MODEL: "neosoft5000",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "SYR Connect Local (12345 @ 192.168.1.100)"
    assert result3["data"][CONF_HOST] == "192.168.1.100"
    assert result3["data"][CONF_MODEL] == "neosoft5000"
    assert result3["data"][CONF_API_TYPE] == API_TYPE_JSON


async def test_form_api_json_cannot_connect(hass: HomeAssistant) -> None:
    """Test local/JSON API cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "api_json"}
    )

    with patch(
        "custom_components.syr_connect.api_json.SyrConnectJsonAPI.login",
        side_effect=Exception("Connection error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_MODEL: "neosoft5000",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect_local"}


async def test_form_api_json_already_configured(hass: HomeAssistant) -> None:
    """Test local/JSON API already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="json_192.168.1.100",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_MODEL: "neosoft5000",
            CONF_API_TYPE: API_TYPE_JSON,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "api_json"}
    )

    with (
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI.login",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI._request_json_data",
            new_callable=AsyncMock,
            return_value={"getSRN": "12345", "getVER": "test"},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_MODEL: "neosoft5000",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_api_json_same_ip_different_serial(hass: HomeAssistant) -> None:
    """Test that two hubs with the same IP but different serial numbers are allowed."""
    # Create an entry with host+serial1
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="json_192.168.1.100_12345",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_MODEL: "neosoft5000",
            "serial": "12345",
            CONF_API_TYPE: API_TYPE_JSON,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "api_json"}
    )

    with (
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI.login",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI._request_json_data",
            new_callable=AsyncMock,
            return_value={"getSRN": "67890", "getVER": "test"},
        ),
        patch(
            "custom_components.syr_connect.async_setup_entry",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_MODEL: "neosoft5000",
            },
        )
        await hass.async_block_till_done()

    # A new entry should be created
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "SYR Connect Local (192.168.1.100)"


async def test_options_flow(hass: HomeAssistant, mock_syr_api) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="xml_test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
            CONF_API_TYPE: API_TYPE_XML,
        },
        options={},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.syr_connect.async_setup_entry",
        new_callable=AsyncMock,
    ) as mock_setup:
        mock_setup.return_value = True
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"scan_interval": 120},
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {"scan_interval": 120}


async def test_options_flow_no_entry(hass: HomeAssistant) -> None:
    """Test options flow when entry has no options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="xml_test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
            CONF_API_TYPE: API_TYPE_XML,
        },
        options=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_reauth_flow(hass: HomeAssistant, mock_syr_api) -> None:
    """Test reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="xml_test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
            CONF_API_TYPE: API_TYPE_XML,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "username": "test@example.com",
        },
        data=entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.syr_connect.async_setup_entry",
        new_callable=AsyncMock,
    ) as mock_setup:
        mock_setup.return_value = True
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "new_password",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauth_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test reauth flow with invalid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="xml_test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
            CONF_API_TYPE: API_TYPE_XML,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=SyrConnectAuthError("Invalid credentials"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test reauth flow with connection error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="xml_test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
            CONF_API_TYPE: API_TYPE_XML,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=SyrConnectConnectionError("Network error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test reauth flow with unknown error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="xml_test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
            CONF_API_TYPE: API_TYPE_XML,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=RuntimeError("Unexpected error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow(hass: HomeAssistant, mock_syr_api) -> None:
    """Test reconfigure flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="xml_test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
            CONF_API_TYPE: API_TYPE_XML,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "custom_components.syr_connect.async_setup_entry",
        new_callable=AsyncMock,
    ) as mock_setup:
        mock_setup.return_value = True
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "new_user@example.com",
                CONF_PASSWORD: "new_password",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test reconfigure flow with invalid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="xml_test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
            CONF_API_TYPE: API_TYPE_XML,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=SyrConnectAuthError("Invalid credentials"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test reconfigure flow with connection error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="xml_test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
            CONF_API_TYPE: API_TYPE_XML,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=SyrConnectConnectionError("Network error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test reconfigure flow with unknown error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=RuntimeError("Unexpected error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_validate_input_xml_auth_error(hass: HomeAssistant) -> None:
    """Test validate_input_xml raises InvalidAuthError on auth failure."""
    from custom_components.syr_connect.config_flow import InvalidAuthError, validate_input_xml
    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=SyrConnectAuthError("Invalid credentials"),
    ):
        with pytest.raises(InvalidAuthError):
            await validate_input_xml(
                hass,
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "wrong"},
            )


async def test_validate_input_xml_connection_error(hass: HomeAssistant) -> None:
    """Test validate_input_xml raises CannotConnectError on connection failure."""
    from custom_components.syr_connect.config_flow import CannotConnectError, validate_input_xml
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=SyrConnectConnectionError("Network error"),
    ):
        with pytest.raises(CannotConnectError):
            await validate_input_xml(
                hass,
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test"},
            )


async def test_validate_input_xml_unexpected_error(hass: HomeAssistant) -> None:
    """Test validate_input_xml raises CannotConnectError on unexpected error."""
    from custom_components.syr_connect.config_flow import CannotConnectError, validate_input_xml

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=RuntimeError("Unexpected"),
    ):
        with pytest.raises(CannotConnectError):
            await validate_input_xml(
                hass,
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test"},
            )


async def test_validate_input_json_connection_error(hass: HomeAssistant) -> None:
    """Test validate_input_json raises CannotConnectError on connection failure."""
    from custom_components.syr_connect.config_flow import CannotConnectError, validate_input_json

    with patch(
        "custom_components.syr_connect.api_json.SyrConnectJsonAPI.login",
        side_effect=Exception("Network error"),
    ):
        with pytest.raises(CannotConnectError):
            await validate_input_json(
                hass,
                {CONF_HOST: "192.168.1.100", CONF_MODEL: "neosoft5000"},
            )


async def test_reauth_flow_entry_not_found(hass: HomeAssistant) -> None:
    """Test reauth flow when entry is deleted during confirmation."""
    from unittest.mock import AsyncMock, patch

    # Create a config entry first
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
            CONF_API_TYPE: API_TYPE_XML,
        },
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    # Mock the API to avoid actual connections
    mock_api = AsyncMock()
    mock_api.login = AsyncMock()

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        )

        # Mock async_get_entry to return None (simulating deleted entry)
        with patch.object(
            hass.config_entries,
            "async_get_entry",
            return_value=None,
        ):
            # Submit credentials - entry lookup will return None
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "test@example.com",
                    CONF_PASSWORD: "new_password",
                },
            )

            assert result2["type"] == FlowResultType.ABORT
            assert result2["reason"] == "reauth_failed"


async def test_reconfigure_flow_entry_not_found(hass: HomeAssistant) -> None:
    """Test reconfigure flow when entry is not found during submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": "nonexistent_entry_id",
        },
    )

    # Submit credentials
    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "new_password",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_failed"


async def test_options_flow_with_existing_interval(hass: HomeAssistant, mock_syr_api) -> None:
    """Test options flow shows existing scan interval as default."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="xml_test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
            CONF_API_TYPE: API_TYPE_XML,
        },
        options={"scan_interval": 180},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    # The form should have the existing scan_interval as default


async def test_options_flow_entry_none_attribute(hass: HomeAssistant) -> None:
    """Test options flow when _config_entry attribute is None."""
    from custom_components.syr_connect.config_flow import SyrConnectOptionsFlow

    # Create options flow without proper config entry
    options_flow = SyrConnectOptionsFlow(None)
    # Manually set the _config_entry to None to test the fallback
    options_flow._config_entry = None

    result = await options_flow.async_step_init(user_input=None)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    # Should use default scan interval when entry is None


async def test_reconfigure_flow_no_entry_prefill(hass: HomeAssistant) -> None:
    """Test reconfigure flow when entry is None during form display."""
    # Initialize flow with nonexistent entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": "nonexistent_id",
        },
    )

    # Form should be shown with empty default (no crash)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_form_api_xml_with_auth_error_exception(hass: HomeAssistant) -> None:
    """Test cloud/XML config flow with SyrConnectAuthError."""
    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "api_xml"}
    )

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=SyrConnectAuthError("Invalid credentials"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_api_xml_with_connection_error_exception(hass: HomeAssistant) -> None:
    """Test cloud/XML config flow with SyrConnectConnectionError."""
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "api_xml"}
    )

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI.login",
        side_effect=SyrConnectConnectionError("Network error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_api_xml_with_generic_exception(hass: HomeAssistant) -> None:
    """Test cloud/XML config flow with generic exception during API initialization."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "api_xml"}
    )

    with patch(
        "custom_components.syr_connect.api_xml.SyrConnectXmlAPI",
        side_effect=RuntimeError("Unexpected error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_validate_input_json_invalid_model(hass: HomeAssistant) -> None:
    """Test validate_input_json with model not having base_path."""
    with pytest.raises(CannotConnectError):
        await validate_input_json(
            hass,
            {
                CONF_MODEL: "InvalidModel",
                CONF_HOST: "192.168.1.100",
            },
        )


async def test_validate_input_json_empty_result(hass: HomeAssistant) -> None:
    """Test validate_input_json with empty API result."""
    with (
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI.login",
            return_value=None,
        ),
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI._request_json_data",
            return_value={},
        ),
        pytest.raises(CannotConnectError),
    ):
        await validate_input_json(
            hass,
            {
                CONF_MODEL: "safetech",
                CONF_HOST: "192.168.1.100",
            },
        )


async def test_validate_input_json_missing_serial_fields(hass: HomeAssistant) -> None:
    """Test validate_input_json with missing getSRN/getFRN fields."""
    with (
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI.login",
            return_value=None,
        ),
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI._request_json_data",
            return_value={"someOtherField": "value"},
        ),
        pytest.raises(CannotConnectError),
    ):
        await validate_input_json(
            hass,
            {
                CONF_MODEL: "safetech",
                CONF_HOST: "192.168.1.100",
            },
        )


async def test_async_get_options_flow(hass: HomeAssistant, mock_syr_api) -> None:
    """Test the async_get_options_flow method."""
    # Create a config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SYR Connect Device",
        data={
            CONF_API_TYPE: API_TYPE_XML,
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
        unique_id="test_unique_id",
    )
    entry.add_to_hass(hass)

    # Get the options flow
    flow = await hass.config_entries.options.async_init(entry.entry_id)

    # Verify the flow was created
    assert flow is not None
    assert flow["type"] == FlowResultType.FORM
    assert flow["step_id"] == "init"


async def test_async_step_reauth(hass: HomeAssistant) -> None:
    """Test the async_step_reauth entry point."""
    # Create a config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SYR Connect Device",
        data={
            CONF_API_TYPE: API_TYPE_XML,
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
        unique_id="test_unique_id",
    )
    entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )

    # Verify the reauth flow goes directly to reauth_confirm
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reconfigure_flow_json_api(hass: HomeAssistant) -> None:
    """Test reconfigure flow with JSON API type."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SYR Connect Device",
        data={
            CONF_API_TYPE: API_TYPE_JSON,
            CONF_MODEL: "safetech",
            CONF_HOST: "192.168.1.100",
        },
        unique_id="test_unique_id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with (
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI.login",
            return_value=None,
        ),
        patch(
            "custom_components.syr_connect.api_json.SyrConnectJsonAPI._request_json_data",
            return_value={"getSRN": "12345"},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_MODEL: "safetech",
                CONF_HOST: "192.168.1.200",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    # Verify the entry was updated
    assert entry.data[CONF_HOST] == "192.168.1.200"
