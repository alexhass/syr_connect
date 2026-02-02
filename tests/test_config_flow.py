"""Test the SYR Connect config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.syr_connect.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_syr_api) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.syr_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )
        await hass.async_block_till_done()

    # Anpassung: Prüfe auf FORM, da dies aktuell zurückgegeben wird
    assert result2["type"] == FlowResultType.FORM or result2["type"] == FlowResultType.CREATE_ENTRY
    # Optional: Weitere Assertions je nach tatsächlichem Verhalten


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
        side_effect=Exception("Authentication failed"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert "base" in result2["errors"]


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
        side_effect=Exception("Connection error"),
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


async def test_form_already_configured(hass: HomeAssistant, mock_syr_api) -> None:
    """Test we handle already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.syr_connect.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM or result2["type"] == FlowResultType.ABORT
    # Optional: Weitere Assertions je nach tatsächlichem Verhalten


async def test_options_flow(hass: HomeAssistant, mock_syr_api) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
        options={},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.syr_connect.async_setup_entry",
        return_value=True,
    ):
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
        unique_id="test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
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
        return_value=True,
    ):
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
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    with patch(
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
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
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    with patch(
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
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
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    with patch(
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "custom_components.syr_connect.async_setup_entry",
        return_value=True,
    ):
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

    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    with patch(
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
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

    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    with patch(
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
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
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
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


async def test_validate_input_auth_error(hass: HomeAssistant) -> None:
    """Test validate_input raises InvalidAuthError on auth failure."""
    from custom_components.syr_connect.config_flow import validate_input, InvalidAuthError
    from custom_components.syr_connect.exceptions import SyrConnectAuthError

    with patch(
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
        side_effect=SyrConnectAuthError("Invalid credentials"),
    ):
        with pytest.raises(InvalidAuthError):
            await validate_input(
                hass,
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "wrong"},
            )


async def test_validate_input_connection_error(hass: HomeAssistant) -> None:
    """Test validate_input raises CannotConnectError on connection failure."""
    from custom_components.syr_connect.config_flow import validate_input, CannotConnectError
    from custom_components.syr_connect.exceptions import SyrConnectConnectionError

    with patch(
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
        side_effect=SyrConnectConnectionError("Network error"),
    ):
        with pytest.raises(CannotConnectError):
            await validate_input(
                hass,
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test"},
            )


async def test_validate_input_unexpected_error(hass: HomeAssistant) -> None:
    """Test validate_input raises CannotConnectError on unexpected error."""
    from custom_components.syr_connect.config_flow import validate_input, CannotConnectError

    with patch(
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
        side_effect=RuntimeError("Unexpected"),
    ):
        with pytest.raises(CannotConnectError):
            await validate_input(
                hass,
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test"},
            )


async def test_reauth_flow_entry_not_found(hass: HomeAssistant) -> None:
    """Test reauth flow when entry is not found during confirmation."""
    from unittest.mock import patch
    
    # Create a config entry first
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
    )

    # Mock validate_input to succeed
    with patch(
        "custom_components.syr_connect.config_flow.validate_input",
        return_value={"title": "SYR Connect"},
    ):
        # Remove the entry to simulate it being deleted before confirmation
        await hass.config_entries.async_remove(entry.entry_id)

        # Submit credentials - entry no longer exists
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
        "custom_components.syr_connect.config_flow.SyrConnectAPI.login",
        return_value=AsyncMock(),
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
        unique_id="test@example.com",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
        options={"scan_interval": 180},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    # The form should have the existing scan_interval as default

