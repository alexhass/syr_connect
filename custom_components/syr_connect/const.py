"""Constants for the SYR Connect integration."""

DOMAIN = "syr_connect"

# Configuration keys
CONF_API_TYPE = "api_type"
CONF_HOST = "host"
CONF_MODEL = "model"
CONF_LOGIN_REQUIRED = "login_required"
CONF_SERVICE = "service"

# API type values
API_TYPE_XML = "xml"
API_TYPE_JSON = "json"

# Service of the SYR Connect app itself: preselected for a new account, and the service
# of the entries made before the service could be chosen
_SYR_CONNECT_SERVICE_DEFAULT = "de.consoft.syr.connect"

_SYR_CONNECT_SCAN_INTERVAL_CONF = "scan_interval"
_SYR_CONNECT_API_XML_SCAN_INTERVAL_DEFAULT = 60  # seconds
_SYR_CONNECT_API_JSON_SCAN_INTERVAL_DEFAULT = 60  # seconds
_SYR_CONNECT_API_XML_SCAN_INTERVAL_MINIMUM = 60  # seconds
_SYR_CONNECT_API_JSON_SCAN_INTERVAL_MINIMUM = 10  # seconds
_SYR_CONNECT_API_SCAN_INTERVAL_MAXIMUM = 600  # seconds


# Numbers of the leak protection profiles. Every profile has the same settings, keyed
# by the setting with the number appended: getPA1-getPA8, getPN1-getPN8, ...
_SYR_CONNECT_LEAK_PROTECTION_PROFILES = range(1, 9)
