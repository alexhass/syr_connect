"""Config flow for SYR Connect integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .api import SyrConnectAPI

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    _LOGGER.debug("Validating credentials for user: %s", data[CONF_USERNAME])
    session = async_get_clientsession(hass)
    api = SyrConnectAPI(session, data[CONF_USERNAME], data[CONF_PASSWORD])
    
    # Test authentication
    _LOGGER.debug("Testing API authentication...")
    await api.login()
    _LOGGER.info("API authentication successful for user: %s", data[CONF_USERNAME])
    
    return {"title": f"SYR Connect ({data[CONF_USERNAME]})"}


class SyrConnectOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for SYR Connect."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options for scan interval configuration.
        
        Args:
            user_input: User input data from the form
            
        Returns:
            FlowResult with the configuration entry or form
        """
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current scan interval with safe fallback
        current_scan_interval = DEFAULT_SCAN_INTERVAL
        if self.config_entry and self.config_entry.options:
            current_scan_interval = self.config_entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current_scan_interval,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=60,
                            max=600,
                            unit_of_measurement=UnitOfTime.SECONDS,
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                }
            ),
        )


class SyrConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SYR Connect."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler.
        
        Args:
            config_entry: The config entry to get options flow for
            
        Returns:
            The options flow handler instance
        """
        """Get the options flow for this handler."""
        return SyrConnectOptionsFlow()

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauth flow when credentials are invalid.
        
        Args:
            entry_data: The existing config entry data
            
        Returns:
            FlowResult to prompt user for new credentials
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth confirmation step.
        
        Args:
            user_input: User input data with new credentials
            
        Returns:
            FlowResult with updated config entry or form with errors
        """
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Get the existing config entry
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            
            if entry is None:
                return self.async_abort(reason="reauth_failed")
            
            try:
                # Validate new credentials
                await validate_input(self.hass, user_input)
                
                # Update the config entry with new credentials
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                
                # Reload the config entry
                await self.hass.config_entries.async_reload(entry.entry_id)
                
                return self.async_abort(reason="reauth_successful")
                
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Reauth validation failed: %s", err)
                errors["base"] = "invalid_auth"
        
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"username": self.context.get("username", "")},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step.
        
        Args:
            user_input: User input data containing username and password
            
        Returns:
            FlowResult with config entry or form with validation errors
        """
        errors: dict[str, str] = {}
        
        if user_input is not None:
            _LOGGER.debug("Processing config flow for user: %s", user_input[CONF_USERNAME])
            try:
                info = await validate_input(self.hass, user_input)
                _LOGGER.debug("Validation successful")
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Config flow validation failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                _LOGGER.debug("Setting unique ID: %s", user_input[CONF_USERNAME])
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                
                _LOGGER.info("Creating config entry: %s", info["title"])
                return self.async_create_entry(title=info["title"], data=user_input)
        else:
            _LOGGER.debug("Showing config form to user")

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
