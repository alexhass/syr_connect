"""Config flow for SYR Connect integration."""

import logging
from typing import Any, override

import probatio

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .aiosyrconnect import (
    API_SERVICES,
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectInvalidResponseError,
    SyrConnectJsonAPI,
    SyrConnectLoginFailedError,
    SyrConnectXmlAPI,
)
from .const import (
    _SYR_CONNECT_API_JSON_SCAN_INTERVAL_MINIMUM,
    _SYR_CONNECT_API_SCAN_INTERVAL_MAXIMUM,
    _SYR_CONNECT_API_XML_SCAN_INTERVAL_MINIMUM,
    _SYR_CONNECT_SCAN_INTERVAL_CONF,
    _SYR_CONNECT_SERVICE_DEFAULT,
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_LOGIN_REQUIRED,
    CONF_MODEL,
    CONF_SERVICE,
    DOMAIN,
)
from .helpers.device import get_local_serial
from .helpers.integration import (
    build_user_agent,
    get_api_locale,
    get_default_scan_interval_for_entry,
    get_integration_version,
    host_has_port,
    is_valid_host,
)
from .helpers.registry import build_entry_unique_id
from .models import MODELS, detect_model

_LOGGER = logging.getLogger(__name__)

# Version whose migration identifies local entries by the serial number of their
# device; an older local entry is still identified by its host
_SYR_CONNECT_CONFIG_FLOW_LOCAL_SERIAL_VERSION = 12


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuthError(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class HostInvalidError(HomeAssistantError):
    """Error to indicate the host field value is invalid."""


class HostWithPortError(HostInvalidError):
    """Error to indicate the host field contains a port, which is not allowed (fixed port 5333)."""


# Schema for Cloud/XML API initial setup (backend selector + username + password)
STEP_CLOUD_XML_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            CONF_SERVICE, default=_SYR_CONNECT_SERVICE_DEFAULT
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=svc.cf_bundle_identifier, label=svc.display_name
                    )
                    for svc in sorted(
                        API_SERVICES.values(),
                        key=lambda s: s.display_name.casefold(),
                    )
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)

# Schema for reauth (backend already set — only credentials needed)
_STEP_REAUTH_XML_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)

# Get list of models that support local JSON API (have base_path)
# Sort by display_name to ensure first item in list matches first item shown in UI
LOCAL_API_MODELS = sorted(
    [
        (
            sig.name,
            f"{sig.manufacturer} {sig.display_name}",
        )
        for sig in MODELS
        if sig.base_path is not None
    ],
    key=lambda x: x[1].casefold(),  # Sort by display_name (case-insensitive)
)

# Schema for Local/JSON API configuration (host + model)
STEP_LOCAL_JSON_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_MODEL): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=name, label=display)
                    for name, display in LOCAL_API_MODELS
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        probatio.Required(CONF_HOST): str,
    }
)


def _entry_title(api_type: str, data: dict[str, Any]) -> str:
    """Return the title a new config entry gets for the given connection data.

    Args:
        api_type: API type of the entry
        data: Entry data with the service and username (cloud) or the host (local)

    Returns:
        "<service> (<username>)" for the cloud, "SYR Connect Local (<host>)" for a
        local device
    """
    if api_type == API_TYPE_JSON:
        return f"SYR Connect Local ({data[CONF_HOST]})"
    service = API_SERVICES[data[CONF_SERVICE]]
    return f"{service.display_name} ({data[CONF_USERNAME]})"


async def validate_input_xml(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
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
    _LOGGER.debug("Validating XML API credentials for user: %s", data[CONF_USERNAME])
    session = async_get_clientsession(hass)

    # The schema only offers services of API_SERVICES
    svc = API_SERVICES[data[CONF_SERVICE]]

    api = SyrConnectXmlAPI(
        session,
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        service=svc,
        user_agent=build_user_agent(get_integration_version(hass)),
        language=get_api_locale(hass.config.language, hass.config.country),
        # The tzo of the login is the offset of the Home Assistant time zone
        local_now=dt_util.now,
    )

    # Test authentication. Failures are logged at debug level only: the form shows them.
    _LOGGER.debug("Testing XML API authentication...")
    try:
        await api.login()
    except (SyrConnectAuthError, SyrConnectLoginFailedError) as err:
        # The cloud answers an unknown username like an outage (SyrConnectLoginFailedError);
        # while setting up, wrong credentials are the likely cause
        _LOGGER.debug("XML API: authentication failed: %s", err)
        raise InvalidAuthError from err
    except SyrConnectConnectionError as err:
        _LOGGER.debug("XML API: connection failed: %s", err)
        raise CannotConnectError from err

    _LOGGER.debug(
        "XML API: authentication successful for user: %s", data[CONF_USERNAME]
    )

    return {"title": _entry_title(API_TYPE_XML, data)}


async def _async_validate_json_device(api: SyrConnectJsonAPI) -> str:
    """Log in to the local device and check that it answers like a SYR device.

    Args:
        api: JSON API client for the device

    Returns:
        The serial number of the device

    Raises:
        CannotConnectError: If the device returns no usable data
    """
    await api.login()

    # Use the public API methods to retrieve devices and status. This
    # avoids calling private methods and keeps encapsulation intact.
    # get_devices() always returns the one device of the local API.
    devices = await api.get_devices("local")

    # Fetch full status for the device. get_device_status() will reuse the
    # cached /get/all response set by get_devices(), avoiding an extra API call.
    data_result = await api.get_device_status(devices[0]["id"])
    if not data_result:
        _LOGGER.debug("JSON API: returned empty status from get_device_status()")
        raise CannotConnectError

    # Verify this is a SYR device by checking for serial number fields and extract serial
    serial = get_local_serial(data_result)
    if serial is None:
        _LOGGER.debug("JSON API: response missing getSRN/getFRN - not a SYR device?")
        raise CannotConnectError

    _LOGGER.debug(
        "JSON API: Successfully validated SYR device with serial %s and %d status keys",
        serial,
        len(data_result),
    )
    return serial


async def validate_input_json(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input for Local/JSON API.

    Args:
        hass: Home Assistant instance
        data: User input data with host, model, and device_name

    Returns:
        Dictionary with the title of the config entry, whether the device needs the
        ADM login and the serial number of the device

    Raises:
        CannotConnectError: If connection to API fails
    """
    host = data[CONF_HOST]

    # Use central helper for IP/hostname validation
    if not is_valid_host(host):
        # A port gets its own error, so the user is told to leave it out (host_no_port)
        if host_has_port(host):
            _LOGGER.debug("Host field must not include a port. Received: %s", host)
            raise HostWithPortError("Host must not include a port.")
        _LOGGER.debug(
            "Host field is not a valid IP address or hostname. Received: %s", host
        )
        raise HostInvalidError("Host must be a valid IP address or hostname.")

    model = detect_model({}, model=data[CONF_MODEL])

    _LOGGER.debug(
        "Validating JSON API connection to host: %s, model: %s", host, model.name
    )

    # The model gives the local path of the JSON API
    if model.base_path is None:
        _LOGGER.debug(
            "Selected model %s does not support local JSON API", data[CONF_MODEL]
        )
        raise CannotConnectError

    session = async_get_clientsession(hass)
    api = SyrConnectJsonAPI(
        session,
        host=host,
        model=model,
        user_agent=build_user_agent(get_integration_version(hass)),
    )

    # Test connection by attempting login and fetching device data via public API.
    # Failures are logged at debug level only: the form shows them.
    _LOGGER.debug("Testing JSON API connection...")
    try:
        serial = await _async_validate_json_device(api)
    except SyrConnectAuthError as err:
        _LOGGER.debug("JSON API: authentication failed: %s", err)
        raise InvalidAuthError from err
    except (SyrConnectConnectionError, SyrConnectInvalidResponseError) as err:
        # An empty answer or JSON that is no object: no SYR device at this address
        _LOGGER.debug("JSON API: connection failed: %s", err)
        raise CannotConnectError from err

    _LOGGER.info("JSON API: connection successful to host: %s", host)

    # Return whether the device required login so the config flow can persist it,
    # and the serial number for the unique_id of the entry
    return {
        "title": _entry_title(API_TYPE_JSON, data),
        "login_required": api.login_required,
        "serial": serial,
    }


class SyrConnectOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle options flow for SYR Connect."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options for scan interval configuration.

        Args:
            user_input: User input data from the form

        Returns:
            FlowResult with the configuration entry or form
        """
        if user_input is not None:
            # Persist options (scan interval)
            options = dict(self.config_entry.options)

            # Scan interval
            if _SYR_CONNECT_SCAN_INTERVAL_CONF in user_input:
                options[_SYR_CONNECT_SCAN_INTERVAL_CONF] = user_input[
                    _SYR_CONNECT_SCAN_INTERVAL_CONF
                ]

            return self.async_create_entry(title="", data=options)

        # Compute current scan interval with centralized helper
        current_scan_interval = get_default_scan_interval_for_entry(self.config_entry)

        # Build schema for options: scan interval only
        schema_dict: dict = {
            probatio.Optional(
                _SYR_CONNECT_SCAN_INTERVAL_CONF,
                default=current_scan_interval,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    # Minimum depends on API type: JSON devices can poll faster
                    min=(
                        _SYR_CONNECT_API_JSON_SCAN_INTERVAL_MINIMUM
                        if self.config_entry.data.get(CONF_API_TYPE) == API_TYPE_JSON
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
            data_schema=probatio.Schema(schema_dict),
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SYR Connect."""

    VERSION = 12

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SyrConnectOptionsFlow:
        """Get the options flow for this handler.

        Args:
            config_entry: The config entry to get options flow for

        Returns:
            The options flow handler instance
        """
        return SyrConnectOptionsFlow()

    @staticmethod
    def _strip_whitespace(user_input: dict[str, Any]) -> dict[str, Any]:
        """Return the user input with leading/trailing whitespace removed from host and username.

        Such whitespace usually comes from copy & paste, and neither a host nor a
        username of the cloud can contain it; it is removed instead of rejecting the
        input, and the cleaned value is what gets validated and saved (also in the
        unique_id). The password is kept as entered: whitespace can be part of it.
        Input without these fields is returned unchanged.
        """
        stripped = {
            key: value.strip()
            for key in (CONF_HOST, CONF_USERNAME)
            if isinstance(value := user_input.get(key), str)
        }
        return {**user_input, **stripped}

    def _unique_id_used_by_other_entry(
        self, entry: ConfigEntry, unique_id: str
    ) -> bool:
        """Return True if another config entry already uses this unique_id.

        Reauth and reconfigure may change the username or host. Without this check
        two entries could poll the same account or device.
        """
        return any(
            other.entry_id != entry.entry_id and other.unique_id == unique_id
            for other in self._async_current_entries(include_ignore=False)
        )

    @callback
    def _async_update_reload_and_abort(
        self,
        entry: ConfigEntry,
        api_type: str,
        new_data: dict[str, Any],
        serial: str | None,
    ) -> ConfigFlowResult:
        """Save the new connection data of an existing entry, reload it and finish the flow.

        Shared by reauth and reconfigure. A cloud entry stays with its account: the
        cloud has no account ID, so another username means another account, whose
        devices are not the devices of this entry; the flow aborts with "wrong_account"
        and the account is added as a new entry. Only the letter case of the username
        and whitespace around it (of older entries) may change. A local entry stays with its device: the host and the model may
        change, another serial number aborts with "wrong_device". A local entry of an
        older version, whose migration could not reach its device yet, gets the serial
        number of the device.
        The flow aborts with "already_configured" if another entry already uses the
        new unique_id. The title is built again from the new data, as at setup.

        Args:
            entry: The config entry to update
            api_type: API type of the entry
            new_data: Complete new entry data
            serial: Serial number of the local device, None for a cloud entry

        Returns:
            The abort result that ends the flow
        """
        if (
            api_type == API_TYPE_XML
            and str(new_data[CONF_USERNAME]).lower()
            != str(entry.data[CONF_USERNAME]).strip().lower()
        ):
            return self.async_abort(reason="wrong_account")
        new_unique_id = build_entry_unique_id(api_type, new_data, serial)
        if (
            api_type == API_TYPE_JSON
            and entry.version >= _SYR_CONNECT_CONFIG_FLOW_LOCAL_SERIAL_VERSION
            and entry.unique_id != new_unique_id
        ):
            return self.async_abort(reason="wrong_device")
        if self._unique_id_used_by_other_entry(entry, new_unique_id):
            return self.async_abort(reason="already_configured")
        return self.async_update_reload_and_abort(
            entry,
            data=new_data,
            unique_id=new_unique_id,
            title=_entry_title(api_type, new_data),
        )

    async def async_step_reauth(self, _entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth flow when credentials are invalid.

        Args:
            _entry_data: The existing config entry data (unused, the entry is read
                in async_step_reauth_confirm)

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
        entry = self._get_reauth_entry()

        # Determine API type for this entry (default to XML for backward compatibility)
        api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML)

        if user_input is not None:
            user_input = self._strip_whitespace(user_input)
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
                    serial = info["serial"]

                else:
                    # Default/XML flow — pass existing conf_service so the correct endpoint is tested
                    await validate_input_xml(
                        self.hass,
                        {
                            **user_input,
                            CONF_SERVICE: entry.data[CONF_SERVICE],
                        },
                    )
                    new_data = {
                        **entry.data,
                        CONF_API_TYPE: API_TYPE_XML,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    }
                    serial = None

                return self._async_update_reload_and_abort(
                    entry, api_type, new_data, serial
                )

            except CannotConnectError:
                errors["base"] = (
                    "cannot_connect_local"
                    if api_type == API_TYPE_JSON
                    else "cannot_connect"
                )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except HostWithPortError:
                errors[CONF_HOST] = "host_no_port"
            except HostInvalidError:
                errors[CONF_HOST] = "host_invalid"
            except Exception:
                _LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "unknown"

        # A local entry has no credentials: its own step asks for model and host
        if api_type == API_TYPE_JSON:
            return self.async_show_form(
                step_id="reauth_confirm_local",
                data_schema=STEP_LOCAL_JSON_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "host": str(entry.data.get(CONF_HOST, "")),
                },
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_STEP_REAUTH_XML_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "username": str(entry.data.get(CONF_USERNAME, "")),
            },
        )

    async def async_step_reauth_confirm_local(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth form of a local (JSON API) entry.

        The form has its own step for its own texts; the input is handled by
        `async_step_reauth_confirm` like the cloud credentials.

        Args:
            user_input: User input data with model and host

        Returns:
            FlowResult with updated config entry or form with errors
        """
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration.

        Args:
            user_input: User input data with new credentials or settings

        Returns:
            FlowResult with updated config entry or form with errors
        """
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        api_type = entry.data.get(CONF_API_TYPE, API_TYPE_XML)

        if user_input is not None:
            user_input = self._strip_whitespace(user_input)
            try:
                # Validate based on API type
                if api_type == API_TYPE_JSON:
                    info = await validate_input_json(self.hass, user_input)
                    new_data = {
                        CONF_API_TYPE: API_TYPE_JSON,
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_MODEL: user_input[CONF_MODEL],
                    }
                    # Whether the device needs the ADM login (/set/ADM/(2)f) before
                    # /get/all returns data. validate_input_json found it out while
                    # checking the device; storing it saves the client from trying
                    # the login again at every start. The value of the old data is
                    # not kept: the new host may be another device.
                    if info.get("login_required") is not None:
                        new_data[CONF_LOGIN_REQUIRED] = bool(info["login_required"])
                    serial = info["serial"]
                else:
                    # Use the existing configured service; do not allow changing it here.
                    service = entry.data[CONF_SERVICE]
                    await validate_input_xml(
                        self.hass, {**user_input, CONF_SERVICE: service}
                    )
                    new_data = {
                        CONF_API_TYPE: API_TYPE_XML,
                        CONF_SERVICE: service,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    }
                    serial = None

                return self._async_update_reload_and_abort(
                    entry, api_type, new_data, serial
                )

            except CannotConnectError:
                errors["base"] = (
                    "cannot_connect_local"
                    if api_type == API_TYPE_JSON
                    else "cannot_connect"
                )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except HostWithPortError:
                errors[CONF_HOST] = "host_no_port"
            except HostInvalidError:
                errors[CONF_HOST] = "host_invalid"
            except Exception:
                _LOGGER.exception("Unexpected error during reconfiguration")
                errors["base"] = "unknown"

        # Show appropriate form based on API type
        if api_type == API_TYPE_JSON:
            # Pre-fill with current values for JSON API
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=probatio.Schema(
                    {
                        probatio.Required(
                            CONF_MODEL,
                            default=entry.data.get(CONF_MODEL, ""),
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    selector.SelectOptionDict(value=name, label=display)
                                    for name, display in LOCAL_API_MODELS
                                ],
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        probatio.Required(
                            CONF_HOST,
                            default=entry.data.get(CONF_HOST, ""),
                        ): str,
                    }
                ),
                errors=errors,
            )
        # Pre-fill with current values for XML API
        # Do not allow changing the configured service here; only credentials may be updated.
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_USERNAME,
                        default=entry.data.get(CONF_USERNAME, ""),
                    ): str,
                    probatio.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - show menu to select API type.

        Returns:
            FlowResult with menu to choose between Cloud (XML) or Local (JSON) API
        """
        return self.async_show_menu(
            step_id="user",
            menu_options=["api_xml", "api_json"],
        )

    async def async_step_api_xml(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Cloud/XML API configuration (username + password).

        Args:
            user_input: User input data containing username and password

        Returns:
            FlowResult with config entry or form with validation errors
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = self._strip_whitespace(user_input)
            _LOGGER.debug(
                "Processing Cloud/XML API config flow for user: %s",
                user_input[CONF_USERNAME],
            )
            try:
                info = await validate_input_xml(self.hass, user_input)
                _LOGGER.debug("Validation successful")
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Cloud/XML API config flow")
                errors["base"] = "unknown"
            else:
                # Set unique ID based on username and API type
                unique_id = build_entry_unique_id(API_TYPE_XML, user_input)
                _LOGGER.debug("Setting unique ID: %s", unique_id)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                _LOGGER.debug("Creating Cloud/XML API config entry: %s", info["title"])
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

    async def async_step_api_json(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Local/JSON API configuration (host + model).

        Args:
            user_input: User input data containing host and model

        Returns:
            FlowResult with config entry or form with validation errors
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = self._strip_whitespace(user_input)
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
            except HostWithPortError:
                errors[CONF_HOST] = "host_no_port"
            except HostInvalidError:
                errors[CONF_HOST] = "host_invalid"
            except Exception:
                _LOGGER.exception("Unexpected error during Local/JSON API config flow")
                errors["base"] = "unknown"
            else:
                # Set unique ID based on the serial number of the device and API type
                unique_id = build_entry_unique_id(
                    API_TYPE_JSON, user_input, info["serial"]
                )
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
