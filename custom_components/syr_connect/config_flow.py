"""Config flow for SYR Connect integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_xml import SyrConnectAPI
from .const import _SYR_CONNECT_SCAN_INTERVAL_CONF, _SYR_CONNECT_SCAN_INTERVAL_DEFAULT, DOMAIN
from .exceptions import SyrConnectAuthError, SyrConnectConnectionError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Args:
        hass: Home Assistant instance
        data: User input data with username and password

    Returns:
        Dictionary with title for the config entry

    Raises:
        CannotConnectError: If connection to API fails
        InvalidAuthError: If authentication fails
    """
    _LOGGER.debug("Validating credentials for user: %s", data[CONF_USERNAME])
    session = async_get_clientsession(hass)
    api = SyrConnectAPI(session, data[CONF_USERNAME], data[CONF_PASSWORD])

    # Test authentication
    _LOGGER.debug("Testing API authentication...")
    try:
        await api.login()
    except SyrConnectAuthError as err:
        _LOGGER.error("Authentication failed: %s", err)
        raise InvalidAuthError from err
    except SyrConnectConnectionError as err:
        _LOGGER.error("Connection failed: %s", err)
        raise CannotConnectError from err
    except Exception as err:
        _LOGGER.error("Unexpected error during validation: %s", err)
        raise CannotConnectError from err

    _LOGGER.info("API authentication successful for user: %s", data[CONF_USERNAME])

    return {"title": f"SYR Connect ({data[CONF_USERNAME]})"}


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuthError(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class SyrConnectOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for SYR Connect."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow handler and store the config entry."""
        # Avoid assigning to the read-only `config_entry` property; store privately.
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options for scan interval configuration.

        Args:
            user_input: User input data from the form

        Returns:
            FlowResult with the configuration entry or form
        """
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current scan interval with safe fallback
        entry = getattr(self, "_config_entry", None)
        current_scan_interval = (
            entry.options.get(_SYR_CONNECT_SCAN_INTERVAL_CONF, _SYR_CONNECT_SCAN_INTERVAL_DEFAULT)
            if entry and entry.options
            else _SYR_CONNECT_SCAN_INTERVAL_DEFAULT
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        _SYR_CONNECT_SCAN_INTERVAL_CONF,
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

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SYR Connect."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SyrConnectOptionsFlow:
        """Get the options flow for this handler.

        Args:
            config_entry: The config entry to get options flow for

        Returns:
            The options flow handler instance
        """
        return SyrConnectOptionsFlow(config_entry)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth flow when credentials are invalid.

        Args:
            entry_data: The existing config entry data

        Returns:
            FlowResult to prompt user for new credentials
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during reauth: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"username": str(self.context.get("username", ""))},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration.

        Args:
            user_input: User input data with new credentials

        Returns:
            FlowResult with updated config entry or form with errors
        """
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            if entry is None:
                return self.async_abort(reason="reconfigure_failed")

            try:
                # Validate new credentials
                await validate_input(self.hass, user_input)

                # Update the config entry with new credentials
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

                # Reload the config entry
                await self.hass.config_entries.async_reload(entry.entry_id)

                return self.async_abort(reason="reconfigure_successful")

            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during reconfiguration: %s", err)
                errors["base"] = "unknown"

        # Pre-fill with current username
        current_data = {}
        if entry:
            current_data = {
                CONF_USERNAME: entry.data.get(CONF_USERNAME, ""),
            }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=current_data.get(CONF_USERNAME, "")): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during config flow: %s", err)
                errors["base"] = "unknown"
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
