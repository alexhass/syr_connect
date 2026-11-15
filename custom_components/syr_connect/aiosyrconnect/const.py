"""Constants of the SYR Connect APIs: URLs, keys, client identity and cloud services."""

from .models import SyrConnectService

# Largest response body the cloud or a device may send. Real answers stay far below it;
# the limit keeps a broken or hostile server from filling the memory.
RESPONSE_SIZE_MAXIMUM = 1024 * 1024  # bytes

# Interval in minutes after which the local JSON API sends ADM again before /get/all, for
# devices that need it. Assumed; the device itself is not known to leave ADM mode. The XML
# (cloud) API has no client-side timeout; it logs in again when the server rejects the token.
JSON_SESSION_TIMEOUT_MINUTES = 30

# Paths of the XML API, relative to the api_base_url of the service
XML_LOGIN_URL = "WebServices/Api/SyrApiService.svc/REST/GetProjects"
XML_DEVICE_GET_LIST_URL = (
    "WebServices/SyrControlWebServiceTest2.asmx/GetProjectDeviceCollections"
)
XML_DEVICE_GET_STATUS_URL = (
    "WebServices/SyrControlWebServiceTest2.asmx/GetDeviceCollectionStatus"
)
XML_DEVICE_SET_STATUS_URL = (
    "WebServices/SyrControlWebServiceTest2.asmx/SetDeviceCollectionStatus"
)
# Path of the device web services; the statistics method of a device family is appended
XML_DEVICE_SERVICE_PATH = "WebServices/SyrControlWebServiceTest2.asmx/"

# Encryption of the login response
# Key and IV that crypt_key and crypt_vector of every service are encrypted with
XML_SECURE_KEY = "v6XrGwdRGjcUNlM5BPYEPDEWExpNB4jWdmlMjtGljZ4="
XML_SECURE_VECTOR = "4zfS5TBSqLpnRlKwOZt/CQ=="

# Keys of the request checksum (see xml_checksum)
XML_CHECKSUM_KEY1 = "L8KZG4F5DSM6ANBV3CXY7W2ER1T9H0UP"
XML_CHECKSUM_KEY2 = "KHGK5X29LVNZU56T"

# Client identity sent in the XML payloads, e.g. in the app version string
# "App-3.9.7-de-DE-iOS-iPhone-27.0.0-de.consoft.syr.connect". The values come from a real
# capture of the SYR app; do not "correct" them. CF = Core Foundation (iOS framework).
CLIENT_OS_LANGUAGE = "en-US"  # Default; callers pass their own locale
CLIENT_OS_NAME = "iOS"
CLIENT_OS_VERSION = "27.0.0"
CLIENT_OS_MODEL = "iPhone"
CLIENT_CF_BUNDLE_VERSION = "3.9.7"

# Cloud services, keyed by cf_bundle_identifier. Brands of the same cloud share its
# base URL and keys.
API_SERVICES: dict[str, SyrConnectService] = {
    "de.consoft.syr.connect": SyrConnectService(
        api_app_name="SYR Connect",
        api_base_url="https://syrconnect.de/",
        cf_bundle_identifier="de.consoft.syr.connect",
        website_url="https://syrconnect.de/",
        crypt_key="TQh4nNlMG04Po2HyOgiL1064MK5mMOvkrMucUCBALIZKA4sIcgJ+pjj2Y1g3n+45",
        crypt_vector="bPOhrL7NhCZwb1E4CFEpzq1Ds6iTUpMF5XRpHwqDJNo=",
        display_name="SYR Connect",
    ),
    "de.consoft.gc.conel.connect": SyrConnectService(
        api_app_name="CLEAR PRO",
        api_base_url="https://api.conelclearpro.de/",
        cf_bundle_identifier="de.consoft.gc.conel.connect",
        website_url="https://conelclearpro.de/",
        crypt_key="TQh4nNlMG04Po2HyOgiL1064MK5mMOvkrMucUCBALIZKA4sIcgJ+pjj2Y1g3n+45",
        crypt_vector="bPOhrL7NhCZwb1E4CFEpzq1Ds6iTUpMF5XRpHwqDJNo=",
        display_name="CONEL CLEAR PRO",
    ),
    "de.consoft.gsh.comfort.connect": SyrConnectService(
        api_app_name="comfort CONNECT",
        api_base_url="https://syrconnect.de/",
        cf_bundle_identifier="de.consoft.gsh.comfort.connect",
        website_url="https://syrconnect.de/",
        crypt_key="TQh4nNlMG04Po2HyOgiL1064MK5mMOvkrMucUCBALIZKA4sIcgJ+pjj2Y1g3n+45",
        crypt_vector="bPOhrL7NhCZwb1E4CFEpzq1Ds6iTUpMF5XRpHwqDJNo=",
        display_name="Sanibel comfort CONNECT",
    ),
    "de.consoft.isg.concept.connect": SyrConnectService(
        api_app_name="concept CONNECT",
        api_base_url="https://syrconnect.de/",
        cf_bundle_identifier="de.consoft.isg.concept.connect",
        website_url="https://syrconnect.de/",
        crypt_key="TQh4nNlMG04Po2HyOgiL1064MK5mMOvkrMucUCBALIZKA4sIcgJ+pjj2Y1g3n+45",
        crypt_vector="bPOhrL7NhCZwb1E4CFEpzq1Ds6iTUpMF5XRpHwqDJNo=",
        display_name="concept CONNECT",
    ),
    "de.consoft.sanitaerunion.ditech.connect": SyrConnectService(
        api_app_name="DITECH Geräte",
        api_base_url="https://syrconnect.de/",
        cf_bundle_identifier="de.consoft.sanitaerunion.ditech.connect",
        website_url="https://syrconnect.de/",
        crypt_key="TQh4nNlMG04Po2HyOgiL1064MK5mMOvkrMucUCBALIZKA4sIcgJ+pjj2Y1g3n+45",
        crypt_vector="bPOhrL7NhCZwb1E4CFEpzq1Ds6iTUpMF5XRpHwqDJNo=",
        display_name="DITECH Haustechnik",
    ),
    "de.consoft.isg.optima.connect": SyrConnectService(
        api_app_name="optima CONNECT",
        api_base_url="https://syrconnect.de/",
        cf_bundle_identifier="de.consoft.isg.optima.connect",
        website_url="https://syrconnect.de/",
        crypt_key="TQh4nNlMG04Po2HyOgiL1064MK5mMOvkrMucUCBALIZKA4sIcgJ+pjj2Y1g3n+45",
        crypt_vector="bPOhrL7NhCZwb1E4CFEpzq1Ds6iTUpMF5XRpHwqDJNo=",
        display_name="Optima CONNECT",
    ),
    "de.consoft.rwc.connect": SyrConnectService(
        api_app_name="RwcMultisafe",
        api_base_url="https://rwcmultisafe.com/",
        cf_bundle_identifier="de.consoft.rwc.connect",
        website_url="https://rwcmultisafe.com/",
        crypt_key="/Kw4BYbtziKm86EgdCvydMB1wc0ewZ8Da2ySHuUatZDWtWlLllF5ICV6/rS03/ii",
        crypt_vector="fSsr1qI0JFuCXbxLHdBT/R0AbFDQNvKGimWmrmGNVvU=",
        display_name="RWC MultiSafe",
    ),
    "de.consoft.polygonvatro.connect": SyrConnectService(
        api_app_name="POLYGONVATRO Connect",
        api_base_url="https://polygonvatro-connect.de/",
        cf_bundle_identifier="de.consoft.polygonvatro.connect",
        website_url="https://polygonvatro-connect.de/",
        crypt_key="yNKCPje+GkPWJ/wvQC71JcH6ee2Q1hhSORbi1Der+uV/oFXOr0U6qZzB9ysysFBq",
        crypt_vector="CqBWdQ1PJSqhhWV4sGAFkJxuuBvtjdav+/ScxgBnYH0=",
        display_name="POLYGONVATRO Connect",
    ),
}

# Service of the SYR Connect app itself, the default for a new account
DEFAULT_CF_BUNDLE_IDENTIFIER = "de.consoft.syr.connect"
