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

from .const import (
    _SYR_CONNECT_API_JSON_SCAN_INTERVAL_MINIMUM,
    _SYR_CONNECT_API_SCAN_INTERVAL_MAXIMUM,
    _SYR_CONNECT_API_XML_SCAN_INTERVAL_MINIMUM,
    _SYR_CONNECT_SCAN_INTERVAL_CONF,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_LOGIN_REQUIRED,
    CONF_MODEL,
    DOMAIN,
)
from .helpers import get_default_scan_interval_for_entry, is_valid_host
from .models import MODEL_SIGNATURES

_LOGGER = logging.getLogger(__name__)

# Schema for Cloud/XML API configuration (username + password)
STEP_CLOUD_XML_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

# Get list of models that support local JSON API (have base_path)
# Sort by display_name to ensure first item in list matches first item shown in UI
LOCAL_API_MODELS = sorted(
    [
        (
            sig["name"],
            f"{sig['manufacturer']} {sig['display_name']}",
        )
        for sig in MODEL_SIGNATURES
        if sig.get("base_path") is not None
    ],
    key=lambda x: x[1],  # Sort by display_name
)

# Schema for Local/JSON API configuration (host + model)
STEP_LOCAL_JSON_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODEL): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=name, label=display)
                    for name, display in LOCAL_API_MODELS
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_HOST): str,
    }
)


async def validate_input_xml(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input for Cloud/XML API.

    Args:
        hass: Home Assistant instance
        data: User input data with username and password

    Returns:
        Dictionary with title for the config entry

    Raises:
        CannotConnectError: If connection to API fails
        InvalidAuthError: If authentication fails
    """

    # Import here so tests can patch the API class via its module
    from .api_xml import SyrConnectXmlAPI
    from .exceptions import SyrConnectAuthError, SyrConnectConnectionError

    _LOGGER.debug("Validating XML API credentials for user: %s", data[CONF_USERNAME])
    session = async_get_clientsession(hass)
    api = SyrConnectXmlAPI(session, data[CONF_USERNAME], data[CONF_PASSWORD])

    # Test authentication
    _LOGGER.debug("Testing XML API authentication...")
    try:
        await api.login()
    except SyrConnectAuthError as err:
        _LOGGER.error("XML API: authentication failed: %s", err)
        raise InvalidAuthError from err
    except SyrConnectConnectionError as err:
        _LOGGER.error("XML API: connection failed: %s", err)
        raise CannotConnectError from err
    except Exception as err:
        _LOGGER.error("XML API: unexpected error during validation: %s", err)
        raise CannotConnectError from err

    _LOGGER.info("XML API: authentication successful for user: %s", data[CONF_USERNAME])

    return {"title": f"SYR Connect ({data[CONF_USERNAME]})"}


async def validate_input_json(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input for Local/JSON API.

    Args:
        hass: Home Assistant instance
        data: User input data with host, model, and device_name

    Returns:
        Dictionary with title for the config entry

    Raises:
        CannotConnectError: If connection to API fails
    """
    host = data[CONF_HOST]

    # Import here so tests can patch the API class via its module
    from .api_json import SyrConnectJsonAPI
    from .exceptions import SyrConnectAuthError, SyrConnectConnectionError

    # Use central helper for IP/hostname validation
    if not is_valid_host(host):
        _LOGGER.error("Host field is not a valid IP address or hostname. Received: %s", host)
        raise HostInvalidError("Host must be a valid IP address or hostname.")

    model = data[CONF_MODEL]

    _LOGGER.debug("Validating JSON API connection to host: %s, model: %s", host, model)

    # Get base_path for the selected model
    base_path = None
    for sig in MODEL_SIGNATURES:
        if sig["name"] == model:
            base_path = sig.get("base_path")
            break

    if base_path is None:
        _LOGGER.error("Selected model %s does not support local JSON API", model)
        raise CannotConnectError

    session = async_get_clientsession(hass)
    api = SyrConnectJsonAPI(session, host=host, base_path=base_path)

    # Test connection by attempting login and fetching device data via public API
    _LOGGER.debug("Testing JSON API connection...")
    try:
        await api.login()

        # Use the public API methods to retrieve devices and status. This
        # avoids calling private methods and keeps encapsulation intact.
        devices = await api.get_devices("local")
        if not devices:
            _LOGGER.error("JSON API: no devices returned from get_devices()")
            raise CannotConnectError

        # get_devices() returns a list of device dicts; take the first device
        device = devices[0]
        device_id = device.get("id")
        if not device_id:
            _LOGGER.error("JSON API: device entry missing id")
            raise CannotConnectError

        # Fetch full status for the device. get_device_status() will reuse the
        # cached /get/all response set by get_devices(), avoiding an extra API call.
        data_result = await api.get_device_status(device_id)
        if not data_result:
            _LOGGER.error("JSON API: returned empty status from get_device_status()")
            raise CannotConnectError

        # Verify this is a SYR device by checking for serial number fields and extract serial
        serial = data_result.get("getSRN") or data_result.get("getFRN")
        if not serial:
            _LOGGER.error("JSON API: response missing getSRN/getFRN - not a SYR device?")
            raise CannotConnectError

        _LOGGER.debug("JSON API: Successfully validated SYR device with serial %s and %d status keys", serial, len(data_result))

    except SyrConnectAuthError as err:
        _LOGGER.error("JSON API: authentication failed: %s", err)
        raise InvalidAuthError from err
    except SyrConnectConnectionError as err:
        _LOGGER.error("JSON API: connection failed: %s", err)
        raise CannotConnectError from err
    except Exception as err:
        _LOGGER.error("JSON API: unexpected error during validation: %s", err)
        raise CannotConnectError from err

    _LOGGER.info("JSON API: connection successful to host: %s", host)

    # Return whether the device required login so the config flow can persist it
    return {"title": f"SYR Connect Local ({host})", "login_required": api.login_required}


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuthError(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class HostInvalidError(HomeAssistantError):
    """Error to indicate the host field value is invalid."""


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
            # Persist options (scan interval and per-device toggles)
            entry = getattr(self, "_config_entry", None)
            options = dict(entry.options) if entry and entry.options else {}

            # Scan interval
            if _SYR_CONNECT_SCAN_INTERVAL_CONF in user_input:
                options[_SYR_CONNECT_SCAN_INTERVAL_CONF] = user_input[_SYR_CONNECT_SCAN_INTERVAL_CONF]

            return self.async_create_entry(title="", data=options)

        # Compute current scan interval with centralized helper
        entry = getattr(self, "_config_entry", None)
        current_scan_interval = get_default_scan_interval_for_entry(entry)

        # Build schema for options: scan interval only
        schema_dict: dict = {
            vol.Optional(
                _SYR_CONNECT_SCAN_INTERVAL_CONF,
                default=current_scan_interval,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    # Minimum depends on API type: JSON devices can poll faster
                    min=(
                        _SYR_CONNECT_API_JSON_SCAN_INTERVAL_MINIMUM
                        if (self._config_entry and self._config_entry.data.get(CONF_API_TYPE) == API_TYPE_JSON)
                        else _SYR_CONNECT_API_XML_SCAN_INTERVAL_MINIMUM
                    ),
                    max=_SYR_CONNECT_API_SCAN_INTERVAL_MAXIMUM,
                    unit_of_measurement=UnitOfTime.SECONDS,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SYR Connect."""

    VERSION = 2

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

    async def async_step_reauth(self, _entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth flow when credentials are invalid.

        Args:
            entry_data: The existing config entry data

        Returns:
            FlowResult to prompt user for new credentials
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reauth confirmation step.

        Args:
            user_input: User input data with new credentials

        Returns:
            FlowResult with updated config entry or form with errors
        """
        errors: dict[str, str] = {}

        # Get the existing config entry for API type determination
        entry_id = self.context.get("entry_id")
        entry = self.hass.config_entries.async_get_entry(entry_id) if entry_id is not None else None
        if entry is None and user_input is not None:
            return self.async_abort(reason="reauth_failed")

        # Determine API type for this entry (default to XML for backward compatibility)
        api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML) if entry else API_TYPE_XML

        if user_input is not None:
            # At this point, if we reached here after the check above, `entry` must not be None
            assert entry is not None
            try:
                # Validate and update based on API type
                if api_type == API_TYPE_JSON:
                    info = await validate_input_json(self.hass, user_input)

                    # Build new data preserving API type and login_required if present
                    new_data = {
                        **entry.data,
                        CONF_API_TYPE: API_TYPE_JSON,
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_MODEL: user_input[CONF_MODEL],
                    }
                    if "login_required" in info and info["login_required"] is not None:
                        new_data[CONF_LOGIN_REQUIRED] = bool(info["login_required"])

                    # Update entry
                    self.hass.config_entries.async_update_entry(entry, data=new_data)

                else:
                    # Default/XML flow
                    await validate_input_xml(self.hass, user_input)
                    new_data = {
                        **entry.data,
                        CONF_API_TYPE: API_TYPE_XML,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    }
                    self.hass.config_entries.async_update_entry(entry, data=new_data)

                # Reload the config entry
                await self.hass.config_entries.async_reload(entry.entry_id)

                return self.async_abort(reason="reauth_successful")

            except CannotConnectError:
                errors["base"] = "cannot_connect_local" if api_type == API_TYPE_JSON else "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except HomeAssistantError as err:
                # Host validation errors for JSON
                if api_type == API_TYPE_JSON:
                    if "port" in str(err).lower():
                        errors[CONF_HOST] = "host_no_port"
                    else:
                        errors[CONF_HOST] = "host_invalid"
                else:
                    errors["base"] = "unknown"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during reauth: %s", err)
                errors["base"] = "unknown"

        # Show appropriate form based on API type
        if api_type == API_TYPE_JSON:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_LOCAL_JSON_DATA_SCHEMA,
                errors=errors,
                description_placeholders={"host": str(entry.data.get(CONF_HOST, "")) if entry else ""},
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_CLOUD_XML_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"username": str(self.context.get("username", ""))},
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reconfiguration of the integration.

        Args:
            user_input: User input data with new credentials or settings

        Returns:
            FlowResult with updated config entry or form with errors
        """
        errors: dict[str, str] = {}
        entry_id = self.context.get("entry_id")
        entry = self.hass.config_entries.async_get_entry(entry_id) if entry_id is not None else None

        if user_input is not None:
            # Check if entry still exists during submission
            if entry is None:
                return self.async_abort(reason="reconfigure_failed")

            # `entry` is guaranteed to be non-None beyond this point
            assert entry is not None
            try:
                # Determine API type from current entry
                api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML)

                # Validate based on API type
                if api_type == API_TYPE_JSON:
                    await validate_input_json(self.hass, user_input)
                    new_data = {
                        CONF_API_TYPE: API_TYPE_JSON,
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_MODEL: user_input[CONF_MODEL],
                    }
                else:
                    await validate_input_xml(self.hass, user_input)
                    new_data = {
                        CONF_API_TYPE: API_TYPE_XML,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    }

                # Update the config entry
                self.hass.config_entries.async_update_entry(entry, data=new_data)

                # Reload the config entry
                await self.hass.config_entries.async_reload(entry.entry_id)

                return self.async_abort(reason="reconfigure_successful")

            except CannotConnectError:
                # Use appropriate error message based on API type
                api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML) if entry else API_TYPE_XML
                errors["base"] = "cannot_connect_local" if api_type == API_TYPE_JSON else "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except HomeAssistantError as err:
                if "port" in str(err).lower():
                    errors[CONF_HOST] = "host_no_port"
                else:
                    errors[CONF_HOST] = "host_invalid"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during reconfiguration: %s", err)
                errors["base"] = "unknown"

        # Determine API type from entry (or default to XML if entry is None)
        api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML) if entry else API_TYPE_XML

        # Show appropriate form based on API type
        if api_type == API_TYPE_JSON:
            # Pre-fill with current values for JSON API (or empty if entry is None)
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_MODEL,
                            default=entry.data.get(CONF_MODEL, "") if entry else ""
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    selector.SelectOptionDict(value=name, label=display)
                                    for name, display in LOCAL_API_MODELS
                                ],
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        vol.Required(
                            CONF_HOST,
                            default=entry.data.get(CONF_HOST, "") if entry else ""
                        ): str,
                    }
                ),
                errors=errors,
            )
        else:
            # Pre-fill with current username for XML API (or empty if entry is None)
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_USERNAME,
                            default=entry.data.get(CONF_USERNAME, "") if entry else ""
                        ): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                errors=errors,
            )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step - show menu to select API type.

        Returns:
            FlowResult with menu to choose between Cloud (XML) or Local (JSON) API
        """
        return self.async_show_menu(
            step_id="user",
            menu_options=["api_xml", "api_json"],
        )

    async def async_step_api_xml(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle Cloud/XML API configuration (username + password).

        Args:
            user_input: User input data containing username and password

        Returns:
            FlowResult with config entry or form with validation errors
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Processing Cloud/XML API config flow for user: %s", user_input[CONF_USERNAME])
            try:
                info = await validate_input_xml(self.hass, user_input)
                _LOGGER.debug("Validation successful")
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during Cloud/XML API config flow: %s", err)
                errors["base"] = "unknown"
            else:
                # Set unique ID based on username and API type
                unique_id = f"{API_TYPE_XML}_{user_input[CONF_USERNAME]}"
                _LOGGER.debug("Setting unique ID: %s", unique_id)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                _LOGGER.info("Creating Cloud/XML API config entry: %s", info["title"])
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        **user_input,
                        CONF_API_TYPE: API_TYPE_XML,
                    },
                )
        else:
            _LOGGER.debug("Showing Cloud/XML API config form to user")

        return self.async_show_form(
            step_id="api_xml",
            data_schema=STEP_CLOUD_XML_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_api_json(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle Local/JSON API configuration (host + model).

        Args:
            user_input: User input data containing host and model

        Returns:
            FlowResult with config entry or form with validation errors
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug(
                "Processing Local/JSON API config flow for host: %s, model: %s",
                user_input[CONF_HOST],
                user_input[CONF_MODEL],
            )
            try:
                info = await validate_input_json(self.hass, user_input)
                _LOGGER.debug("Validation successful")
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect_local"
            except HostInvalidError:
                errors[CONF_HOST] = "host_invalid"
            except HomeAssistantError as err:
                if "port" in str(err).lower():
                    errors[CONF_HOST] = "host_no_port"
                else:
                    errors["base"] = "unknown"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during Local/JSON API config flow: %s", err)
                errors["base"] = "unknown"
            else:
                # Set unique ID based on host and API type
                unique_id = f"{API_TYPE_JSON}_{user_input[CONF_HOST]}"
                _LOGGER.debug("Setting unique ID: %s", unique_id)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                _LOGGER.info("Creating Local/JSON API config entry: %s", info["title"])
                entry_data = {
                    **user_input,
                    CONF_API_TYPE: API_TYPE_JSON,
                }
                # Persist login_required flag if available (hidden config)
                if "login_required" in info and info["login_required"] is not None:
                    entry_data[CONF_LOGIN_REQUIRED] = bool(info["login_required"])

                return self.async_create_entry(
                    title=info["title"],
                    data=entry_data,
                )
        else:
            _LOGGER.debug("Showing Local/JSON API config form to user")

        return self.async_show_form(
            step_id="api_json",
            data_schema=STEP_LOCAL_JSON_DATA_SCHEMA,
            errors=errors,
        )
