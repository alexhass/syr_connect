"""Tests for the diagnostics."""

# The unit tests in this module check private helpers directly.
# ruff: noqa: SLF001

from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.syr_connect import diagnostics as diag
from custom_components.syr_connect.api_json import SyrConnectJsonAPI
from custom_components.syr_connect.const import (
    API_TYPE_JSON,
    API_TYPE_XML,
    CONF_API_TYPE,
    CONF_HOST,
    CONF_MODEL,
    CONF_SERVICE,
    DOMAIN,
)
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.diagnostics import (
    async_get_config_entry_diagnostics,
    mask_mac_value,
    mask_srn_value,
)
from custom_components.syr_connect.exceptions import (
    SyrConnectConnectionError,
    SyrConnectHTTPError,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

_SYR_CONNECT_TEST_DEVICE_LIST_XML = (
    '<sc><prs><pr pg="p1" pn="Haus+Mustermann" com="Max+Mustermann" /></prs>'
    '<dvs><d dclg="dclg1" sn="206AAA67890" /></dvs></sc>'
)
_SYR_CONNECT_TEST_STATUS_XML = (
    '<sc><dvs><d dclg="dclg1" sn="206AAA67890">'
    '<c n="getSRN" v="206AAA67890" /><c n="getWIP" v="192.168.1.20" />'
    "</d></dvs></sc>"
)
_SYR_CONNECT_TEST_REDACTED_DEVICE_LIST_XML = (
    '<sc><prs><pr pg="p1" pn="My+Project" com="Firstname+Lastname" /></prs>'
    '<dvs><d dclg="dclg1" sn="206AAA12345" /></dvs></sc>'
)
_SYR_CONNECT_TEST_REDACTED_STATUS_XML = (
    '<sc><dvs><d dclg="dclg1" sn="206AAA12345">'
    '<c n="getSRN" v="206AAA12345" /><c n="getWIP" v="***REDACTED_GETWIP***" />'
    "</d></dvs></sc>"
)
# NeoSoft 2500: its model offers the local JSON API at "/neosoft"
_SYR_CONNECT_TEST_NEOSOFT_DEVICE: Any = {
    "id": "dev1",
    "name": "Device 1",
    "status": {"getSRN": "206AAA12345", "getWIP": "192.168.1.100"},
}


def _entry(api_type: str = API_TYPE_XML, **data: Any) -> MockConfigEntry:
    """Return a config entry whose title and data contain the account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SYR Connect (test@example.com)",
        data={
            CONF_API_TYPE: api_type,
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "secret123",
            **data,
        },
    )


def _coordinator(
    data: dict[str, Any] | None = None, *, api: Any = None, session: Any = None
) -> MagicMock:
    """Return a coordinator stand-in with the given data, API client and HTTP session."""
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.data = data
    coordinator.last_update_success = True
    coordinator.last_update_success_time = None
    coordinator.api = api
    coordinator._session = session
    return coordinator


def _xml_api(
    responses: list[Any], devices: list[dict[str, Any]] | None = None
) -> MagicMock:
    """Return a cloud API client with one project, answering with the given responses."""
    api = MagicMock()
    api.is_session_valid.return_value = True
    api.login = AsyncMock()
    api.projects = [{"id": "p1", "name": "Haus Mustermann"}]
    api.session_data = "sess"
    api.device_list_url = "https://example.invalid/list"
    api.device_get_status_url = "https://example.invalid/status"
    api.http_client.post = AsyncMock(side_effect=responses)
    api.payload_builder.build_device_get_list_payload.return_value = "<list/>"
    api.payload_builder.build_device_get_status_payload.side_effect = (
        lambda _session, device_id: f"<status {device_id}/>"
    )
    api.response_parser.parse_device_list_response.return_value = (
        [{"id": "206AAA67890", "dclg": "dclg1"}] if devices is None else devices
    )
    return api


def _json_api(status: dict[str, Any] | None = None) -> MagicMock:
    """Return a local API client with one device reporting the given status."""
    api = MagicMock(spec=SyrConnectJsonAPI)
    api.is_session_valid.return_value = True
    api.login = AsyncMock()
    api.get_devices = AsyncMock(return_value=[{"id": "206AAA67890"}])
    api.get_device_status = AsyncMock(
        return_value={"getSRN": "206AAA67890", "getIPA": "192.168.1.20", "getFLO": "5"}
        if status is None
        else status
    )
    return api


# --- mask_mac_value / mask_srn_value -------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("aa:bb:cc:dd:ee:ff", "AA:BB:CC:XX:XX:XX", id="colon"),
        pytest.param("aa-bb-cc-dd-ee-ff", "AA-BB-CC-XX-XX-XX", id="hyphen"),
        pytest.param("aabbccddeeff", "AA:BB:CC:XX:XX:XX", id="no-separator"),
        pytest.param(" aa:bb:cc:dd:ee:ff ", "AA:BB:CC:XX:XX:XX", id="whitespace"),
        pytest.param("00:11:22:33:44", "00:11:22:33:44", id="five-octets"),
        pytest.param("ZZ:ZZ:ZZ:ZZ:ZZ:ZZ", "ZZ:ZZ:ZZ:ZZ:ZZ:ZZ", id="no-hex"),
        pytest.param("", "", id="empty"),
        pytest.param(None, None, id="none"),
        pytest.param(123, 123, id="number"),
    ],
)
def test_mask_mac_value(value: Any, expected: Any) -> None:
    """The vendor part of a MAC address is kept, the device part is replaced by XX."""
    assert mask_mac_value(value) == expected


def test_mask_mac_value_last_char_replace() -> None:
    """The replacement for the last character tells a second address apart."""
    assert (
        mask_mac_value("aa:bb:cc:dd:ee:ff", last_char_replace="Y")
        == "AA:BB:CC:XX:XX:XY"
    )
    # An address that is not masked is not changed either
    assert mask_mac_value("00:11:22:33:44", last_char_replace="Y") == "00:11:22:33:44"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("206AAA67890", "206AAA12345", id="serial"),
        pytest.param("123456789", "123456789", id="other-format"),
        pytest.param("206aaa67890", "206aaa67890", id="lowercase"),
        pytest.param(None, None, id="none"),
        pytest.param(5, 5, id="number"),
    ],
)
def test_mask_srn_value(value: Any, expected: Any) -> None:
    """A serial number keeps its prefix, the last five digits become 12345."""
    assert mask_srn_value(value) == expected


# --- _redact_xml / _redact_device_list_xml / _redact_json_payload ----------------


def test_redact_xml() -> None:
    """Token, serial numbers, addresses and the redacted keys are replaced in a text."""
    xml = (
        '<sc><us ug="SECRET_TOKEN" />   '
        '<d sn="206AAA67890" getSRN="206AAA67890" getIPA="10.0.0.5">\n'
        '  <c n="getSRN" v="206AAA67890" /><c n="getMAC" v="aa:bb:cc:dd:ee:ff" />'
        '<c n="getMAC1" v="aa:bb:cc:dd:ee:ff" /><c n="getMAC2" v="aa:bb:cc:dd:ee:ff" />'
        '<c n="getWIP" v="192.168.1.20" /><c n="getFLO" v="5" />'
        "note getWFC: MyWifi mail user@example.com ip 8.8.8.8</d></sc> "
    )

    assert diag._redact_xml(xml) == (
        '<sc><us ug="***" />'
        '<d sn="206AAA12345" getSRN="206AAA12345" getIPA="***REDACTED_GETIPA***">'
        '<c n="getSRN" v="206AAA12345" /><c n="getMAC" v="AA:BB:CC:XX:XX:XX" />'
        '<c n="getMAC1" v="AA:BB:CC:XX:XX:XX" /><c n="getMAC2" v="AA:BB:CC:XX:XX:XY" />'
        '<c n="getWIP" v="***REDACTED_GETWIP***" /><c n="getFLO" v="5" />'
        "note getWFC: ***REDACTED_GETWFC*** mail ***REDACTED_USERNAME*** "
        "ip ***REDACTED_IP***</d></sc>"
    )


@pytest.mark.parametrize("value", ["", None, 5])
def test_redact_xml_without_text(value: Any) -> None:
    """An empty value or one that is no text gives an empty text."""
    assert diag._redact_xml(value) == ""


def test_redact_xml_mac2_attribute() -> None:
    """The second MAC address ends with Y as attribute too; an empty one stays empty."""
    assert diag._redact_xml(
        '<d getMAC1="aa-bb-cc-dd-ee-ff" getMAC2="aa-bb-cc-dd-ee-ff" />'
    ) == ('<d getMAC1="AA-BB-CC-XX-XX-XX" getMAC2="AA-BB-CC-XX-XX-XY" />')
    assert diag._redact_xml('<c n="getMAC2" v="" />') == '<c n="getMAC2" v="" />'


def test_redact_xml_keeps_other_serial_format() -> None:
    """A value that is no SYR serial number stays, in sn="..." as for getSRN."""
    assert diag._redact_xml('<d sn="123456789" />') == '<d sn="123456789" />'


def test_redact_xml_skips_empty_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty key in the list of redacted keys is skipped."""
    monkeypatch.setattr(diag, "_SYR_CONNECT_DIAGNOSTICS_TO_REDACT", {"", "getIPA"})

    assert diag._redact_xml('<d getIPA="10.0.0.5" />') == (
        '<d getIPA="***REDACTED_GETIPA***" />'
    )


def test_redact_device_list_xml() -> None:
    """Names, address and phone numbers of the project are replaced, empty ones stay empty."""
    xml = (
        '<sc><prs><pr pg="8625a6fc" pn="Haus+Mustermann" com="Max+Mustermann" '
        'adr="Musterweg+12" zip="54321" rsd="Musterstadt" rg="Deutschland" '
        'pho="%2b49+30+1234567" fax="" cph="%2b49+170+1234567" '
        'url="mustermann.example" /></prs>'
        '<col><dcl dclg="0b09f7ce" ali="Mustermann+Keller" /></col>'
        '<dvs><d dg="cf36f6a5" sn="206AAA67890" sbt="2" /></dvs></sc>'
    )

    # The country and the device name stay
    assert diag._redact_device_list_xml(xml) == (
        '<sc><prs><pr pg="8625a6fc" pn="My+Project" com="Firstname+Lastname" '
        'adr="Street+1" zip="12345" rsd="City" rg="Deutschland" '
        'pho="0123456789" fax="" cph="0123456789" '
        'url="example.com" /></prs>'
        '<col><dcl dclg="0b09f7ce" ali="Mustermann+Keller" /></col>'
        '<dvs><d dg="cf36f6a5" sn="206AAA12345" sbt="2" /></dvs></sc>'
    )


def test_redact_json_payload() -> None:
    """Redacted keys and the whole serial number are removed from a local payload."""
    payload = {"getSRN": "206AAA67890", "getIPA": "192.168.1.20", "getFLO": "5"}

    assert diag._redact_json_payload(payload) == {
        "getSRN": "**REDACTED**",
        "getIPA": "**REDACTED**",
        "getFLO": "5",
    }
    # The payload of the device is not changed
    assert payload["getSRN"] == "206AAA67890"
    assert diag._redact_json_payload(["no", "dict"]) == ["no", "dict"]


# --- _mask_sensitive / _redact_obj ----------------------------------------------


def test_mask_sensitive() -> None:
    """Serial numbers and MAC addresses are masked in nested data, also in other keys."""
    data = {
        "getSRN": "206AAA67890",
        "getMAC": "aa:bb:cc:dd:ee:ff",
        "getMAC1": "11-22-33-44-55-66",
        "getMAC2": "aa:bb:cc:dd:ee:ff",
        "id": "501AAA54321",
        "name": "Keller",
        "devices": [{"getSRN": 5, "status": {"getMAC": "aa:bb:cc:dd:ee:ff"}}],
        "count": 1,
    }

    assert diag._mask_sensitive(data) == {
        "getSRN": "206AAA12345",
        "getMAC": "AA:BB:CC:XX:XX:XX",
        "getMAC1": "11-22-33-XX-XX-XX",
        "getMAC2": "AA:BB:CC:XX:XX:XY",
        "id": "501AAA12345",
        "name": "Keller",
        "devices": [{"getSRN": 5, "status": {"getMAC": "AA:BB:CC:XX:XX:XX"}}],
        "count": 1,
    }


def test_redact_obj() -> None:
    """Redacted keys match in any letter case; other texts lose addresses; raw_xml stays."""
    data = {
        "raw_xml": {"p1": "already redacted 10.0.0.5"},
        "GETIPA": "10.0.0.5",
        "password": "secret123",
        "names": ["Keller at 10.0.0.5", 5],
        "nothing": None,
    }

    assert diag._redact_obj(data) == {
        "raw_xml": {"p1": "already redacted 10.0.0.5"},
        "GETIPA": "***REDACTED_GETIPA***",
        "password": "***REDACTED_PASSWORD***",
        "names": ["Keller at ***REDACTED_IP***", 5],
        "nothing": None,
    }


# --- _collect_raw_xml -----------------------------------------------------------


async def test_collect_raw_xml() -> None:
    """The device list and the status of every device are fetched and redacted."""
    api = _xml_api([_SYR_CONNECT_TEST_DEVICE_LIST_XML, _SYR_CONNECT_TEST_STATUS_XML])

    result = await diag._collect_raw_xml(_coordinator(api=api))

    assert result == {
        "p1": {
            "device_list": _SYR_CONNECT_TEST_REDACTED_DEVICE_LIST_XML,
            "devices": {"dclg1": _SYR_CONNECT_TEST_REDACTED_STATUS_XML},
        }
    }
    assert api.http_client.post.await_args_list == [
        call("https://example.invalid/list", {"xml": "<list/>"}),
        call("https://example.invalid/status", {"xml": "<status dclg1/>"}),
    ]
    api.payload_builder.build_device_get_list_payload.assert_called_once_with(
        "sess", "p1"
    )
    # The devices are read from the response as the cloud sent it
    api.response_parser.parse_device_list_response.assert_called_once_with(
        _SYR_CONNECT_TEST_DEVICE_LIST_XML
    )
    api.login.assert_not_awaited()


async def test_collect_raw_xml_logs_in_without_session() -> None:
    """Without a valid session the client logs in first."""
    api = _xml_api([_SYR_CONNECT_TEST_DEVICE_LIST_XML], devices=[])
    api.is_session_valid.return_value = False

    result = await diag._collect_raw_xml(_coordinator(api=api))

    api.login.assert_awaited_once()
    assert result == {
        "p1": {
            "device_list": _SYR_CONNECT_TEST_REDACTED_DEVICE_LIST_XML,
            "devices": {},
        }
    }


@pytest.mark.parametrize("case", ["no_api", "login_fails", "no_projects"])
async def test_collect_raw_xml_without_usable_session(case: str) -> None:
    """Without an API client, a login or projects there is no raw XML."""
    api: MagicMock | None = _xml_api([])
    assert api is not None
    if case == "login_fails":
        api.is_session_valid.return_value = False
        api.login.side_effect = SyrConnectConnectionError("down")
    elif case == "no_projects":
        api.projects = []
    post = api.http_client.post
    if case == "no_api":
        api = None

    assert await diag._collect_raw_xml(_coordinator(api=api)) == {}
    post.assert_not_awaited()


async def test_collect_raw_xml_skips_project_without_id() -> None:
    """A project without an id is not requested."""
    api = _xml_api([])
    api.projects = [{"name": "No id"}]

    assert await diag._collect_raw_xml(_coordinator(api=api)) == {}
    api.http_client.post.assert_not_awaited()


async def test_collect_raw_xml_failed_device_list_request() -> None:
    """A failed request leaves an empty device list for the project."""
    api = _xml_api([SyrConnectConnectionError("down")], devices=[])

    assert await diag._collect_raw_xml(_coordinator(api=api)) == {
        "p1": {"device_list": "", "devices": {}}
    }


async def test_collect_raw_xml_unparsable_device_list() -> None:
    """A device list that cannot be parsed is kept, without device status."""
    api = _xml_api([_SYR_CONNECT_TEST_DEVICE_LIST_XML])
    api.response_parser.parse_device_list_response.side_effect = ValueError("broken")

    assert await diag._collect_raw_xml(_coordinator(api=api)) == {
        "p1": {
            "device_list": _SYR_CONNECT_TEST_REDACTED_DEVICE_LIST_XML,
            "devices": {},
        }
    }
    assert api.http_client.post.await_count == 1


async def test_collect_raw_xml_device_ids_and_failed_status() -> None:
    """The status is fetched by dclg or id; a failing device does not stop the others."""
    devices = [
        {"dclg": "bad"},
        {"id": "only-id"},
        {"name": "neither dclg nor id"},
        {"dclg": "offline"},
    ]
    api = _xml_api(
        [
            _SYR_CONNECT_TEST_DEVICE_LIST_XML,
            "<sc><ok /></sc>",
            SyrConnectConnectionError("down"),
        ],
        devices=devices,
    )

    def _status_payload(_session: str, device_id: str) -> str:
        if device_id == "bad":
            raise RuntimeError("payload cannot be built")
        return f"<status {device_id}/>"

    api.payload_builder.build_device_get_status_payload.side_effect = _status_payload

    result = await diag._collect_raw_xml(_coordinator(api=api))

    # "bad" raised, "offline" got no answer
    assert result["p1"]["devices"] == {"only-id": "<sc><ok /></sc>", "offline": ""}


async def test_collect_raw_xml_unexpected_error() -> None:
    """An unexpected error is reported instead of raised."""
    api = _xml_api([])
    type(api).projects = PropertyMock(side_effect=RuntimeError("boom"))

    assert await diag._collect_raw_xml(_coordinator(api=api)) == {
        "error": "failed to collect raw xml for all projects"
    }


# --- _collect_raw_json_local_entry ----------------------------------------------


async def test_collect_raw_json_local_entry() -> None:
    """The status of the local device is stored under its id of the coordinator data."""
    api = _json_api()
    coordinator = _coordinator({"devices": [{"id": "206AAA67890"}]}, api=api)

    assert await diag._collect_raw_json_local_entry(coordinator) == {
        "206AAA67890": {
            "getSRN": "**REDACTED**",
            "getIPA": "**REDACTED**",
            "getFLO": "5",
        }
    }
    api.get_devices.assert_awaited_once_with("local")
    api.get_device_status.assert_awaited_once_with("206AAA67890")
    api.login.assert_not_awaited()


@pytest.mark.parametrize("data", [None, {"devices": []}])
async def test_collect_raw_json_local_entry_without_coordinator_device(
    data: dict[str, Any] | None,
) -> None:
    """Without a device in the coordinator data the status is stored as "local_device"."""
    coordinator = _coordinator(data, api=_json_api({"getFLO": "5"}))

    assert await diag._collect_raw_json_local_entry(coordinator) == {
        "local_device": {"getFLO": "5"}
    }


async def test_collect_raw_json_local_entry_failed_login_still_fetches() -> None:
    """A failed login does not stop the request of the status."""
    api = _json_api({"getFLO": "5"})
    api.is_session_valid.return_value = False
    api.login.side_effect = SyrConnectConnectionError("down")

    assert await diag._collect_raw_json_local_entry(_coordinator(api=api)) == {
        "local_device": {"getFLO": "5"}
    }
    api.login.assert_awaited_once()


@pytest.mark.parametrize("case", ["no_devices", "devices_fail", "status_fails"])
async def test_collect_raw_json_local_entry_fetch_fails(case: str) -> None:
    """Without an answer of the device an error is reported."""
    api = _json_api()
    if case == "no_devices":
        api.get_devices.return_value = []
    elif case == "devices_fail":
        api.get_devices.side_effect = SyrConnectConnectionError("down")
    else:
        api.get_device_status.side_effect = SyrConnectConnectionError("down")

    assert await diag._collect_raw_json_local_entry(_coordinator(api=api)) == {
        "error": "failed to fetch JSON data from device"
    }


async def test_collect_raw_json_local_entry_other_api() -> None:
    """Without a local API client nothing is collected."""
    assert await diag._collect_raw_json_local_entry(_coordinator(api=MagicMock())) == {}
    assert await diag._collect_raw_json_local_entry(_coordinator()) == {}


async def test_collect_raw_json_local_entry_unexpected_error() -> None:
    """An unexpected error is reported instead of raised."""
    with patch.object(diag, "_redact_json_payload", side_effect=RuntimeError("boom")):
        result = await diag._collect_raw_json_local_entry(_coordinator(api=_json_api()))

    assert result == {"error": "failed to collect raw json for JSON API"}


# --- _fetch_local_device_json ---------------------------------------------------


async def test_fetch_local_device_json(integration_version: str) -> None:
    """A cloud device is asked at its IP address with the base path of its model."""
    session = MagicMock()
    with patch.object(diag, "SyrConnectJsonAPI") as mock_api_class:
        api = mock_api_class.return_value
        api.is_session_valid.return_value = True
        api.login = AsyncMock()
        api.get_device_status = AsyncMock(
            return_value={"getSRN": "206AAA67890", "getFLO": "5"}
        )

        result = await diag._fetch_local_device_json(
            session, _SYR_CONNECT_TEST_NEOSOFT_DEVICE, "/neosoft", integration_version
        )

    assert result == ("dev1", {"getSRN": "**REDACTED**", "getFLO": "5"})
    mock_api_class.assert_called_once_with(
        session,
        host="192.168.1.100",
        base_path="/neosoft",
        integration_version=integration_version,
    )
    api.get_device_status.assert_awaited_once_with("dev1")
    api.login.assert_not_awaited()


@pytest.mark.parametrize(
    ("status", "host"),
    [
        pytest.param(
            {"getWIP": "192.168.1.1", "getEIP": "192.168.1.2", "getIPA": "192.168.1.3"},
            "192.168.1.1",
            id="wifi-first",
        ),
        pytest.param(
            {"getWIP": "", "getEIP": "192.168.1.2", "getIPA": "192.168.1.3"},
            "192.168.1.2",
            id="ethernet",
        ),
        pytest.param({"getIPA": "192.168.1.3"}, "192.168.1.3", id="generic"),
    ],
)
async def test_fetch_local_device_json_address(
    status: dict[str, str], host: str, integration_version: str
) -> None:
    """The address is the Wi-Fi, then the Ethernet, then the generic IP address."""
    with patch.object(diag, "SyrConnectJsonAPI") as mock_api_class:
        mock_api_class.return_value.get_device_status = AsyncMock(return_value={})

        await diag._fetch_local_device_json(
            MagicMock(),
            cast(Any, {"id": "dev1", "status": status}),
            "/trio",
            integration_version,
        )

    assert mock_api_class.call_args.kwargs["host"] == host


@pytest.mark.parametrize(
    "ip",
    [
        None,
        "",
        "0.0.0.0",
        "::",
        "8.8.8.8",
        "2001:4860:4860::8888",
        "device.example.com",
        "127.0.0.1",
        "::1",
        "169.254.1.2",
        "fe80::1",
    ],
)
async def test_fetch_local_device_json_skips_other_addresses(
    ip: str | None, integration_version: str
) -> None:
    """The IP address comes from the cloud: only private LAN addresses are contacted.

    Missing, public, loopback, link-local and unspecified addresses and host names are not.
    """
    with patch.object(diag, "SyrConnectJsonAPI") as mock_api_class:
        result = await diag._fetch_local_device_json(
            MagicMock(),
            cast(Any, {"id": "dev1", "status": {"getWIP": ip}}),
            "/trio",
            integration_version,
        )

    assert result == ("dev1", None)
    mock_api_class.assert_not_called()


@pytest.mark.parametrize(
    ("device", "device_id"),
    [
        pytest.param({"dclg": "dclg1"}, "dclg1", id="dclg"),
        pytest.param({}, "unknown", id="neither"),
    ],
)
async def test_fetch_local_device_json_device_id(
    device: dict[str, Any], device_id: str, integration_version: str
) -> None:
    """A device without an id is named by its dclg, else "unknown"."""
    result = await diag._fetch_local_device_json(
        MagicMock(), cast(Any, device), "/trio", integration_version
    )

    assert result == (device_id, None)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(SyrConnectHTTPError("Endpoint not found", status=404), id="http"),
        pytest.param(RuntimeError("boom"), id="unexpected"),
    ],
)
async def test_fetch_local_device_json_failed_login_still_fetches(
    error: Exception, integration_version: str
) -> None:
    """A device that answers the login with an error is still fetched."""
    with patch.object(diag, "SyrConnectJsonAPI") as mock_api_class:
        api = mock_api_class.return_value
        api.is_session_valid.return_value = False
        api.login = AsyncMock(side_effect=error)
        api.get_device_status = AsyncMock(return_value={"getFLO": "5"})

        result = await diag._fetch_local_device_json(
            MagicMock(), _SYR_CONNECT_TEST_NEOSOFT_DEVICE, "/trio", integration_version
        )

    assert result == ("dev1", {"getFLO": "5"})


async def test_fetch_local_device_json_not_reachable(
    caplog: pytest.LogCaptureFixture, integration_version: str
) -> None:
    """An unreachable device (login timeout) is logged in one line and not fetched again."""
    caplog.set_level("DEBUG", logger="custom_components.syr_connect.diagnostics")
    with patch.object(diag, "SyrConnectJsonAPI") as mock_api_class:
        api = mock_api_class.return_value
        api.is_session_valid.return_value = False
        api.login = AsyncMock(
            side_effect=SyrConnectConnectionError("Connection failed: TimeoutError()")
        )
        api.get_device_status = AsyncMock()

        result = await diag._fetch_local_device_json(
            MagicMock(), _SYR_CONNECT_TEST_NEOSOFT_DEVICE, "/trio", integration_version
        )

    assert result == ("dev1", None)
    api.get_device_status.assert_not_called()
    assert (
        "device dev1 is not reachable at 192.168.1.100: "
        "Connection failed: TimeoutError()"
    ) in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize("failing", ["status", "redaction"])
async def test_fetch_local_device_json_failure_gives_no_data(
    failing: str, integration_version: str
) -> None:
    """A failed request or redaction gives no data for the device."""
    with (
        patch.object(diag, "SyrConnectJsonAPI") as mock_api_class,
        patch.object(
            diag,
            "_redact_json_payload",
            side_effect=RuntimeError("boom") if failing == "redaction" else None,
        ),
    ):
        api = mock_api_class.return_value
        api.is_session_valid.return_value = True
        api.get_device_status = AsyncMock(
            side_effect=SyrConnectConnectionError("down")
            if failing == "status"
            else None,
            return_value={"getFLO": "5"},
        )

        result = await diag._fetch_local_device_json(
            MagicMock(), _SYR_CONNECT_TEST_NEOSOFT_DEVICE, "/trio", integration_version
        )

    assert result == ("dev1", None)


# --- _collect_raw_json_cloud_devices --------------------------------------------


async def test_collect_raw_json_cloud_devices(
    hass: HomeAssistant, integration_version: str
) -> None:
    """Only devices whose model offers the local API are asked; no answer, no entry."""
    session = MagicMock()
    silent = {**_SYR_CONNECT_TEST_NEOSOFT_DEVICE, "id": "dev2"}
    data = {
        "devices": [
            _SYR_CONNECT_TEST_NEOSOFT_DEVICE,
            # LEX Plus 10 S: no local API
            {"id": "lex", "status": {"getCNA": "LEXplus10S", "getWIP": "192.168.1.5"}},
            silent,
            "no device",
        ]
    }

    async def _fetch(
        _session: Any, device: dict[str, Any], _base_path: str, _version: str
    ) -> tuple[str, Any]:
        return device["id"], {"getFLO": "5"} if device["id"] == "dev1" else None

    with patch.object(diag, "_fetch_local_device_json", side_effect=_fetch) as fetch:
        result = await diag._collect_raw_json_cloud_devices(
            hass, _coordinator(data, session=session)
        )

    assert result == {"dev1": {"getFLO": "5"}}
    assert fetch.await_args_list == [
        call(
            session, _SYR_CONNECT_TEST_NEOSOFT_DEVICE, "/neosoft", integration_version
        ),
        call(session, silent, "/neosoft", integration_version),
    ]


async def test_collect_raw_json_cloud_devices_without_session(
    hass: HomeAssistant,
) -> None:
    """Without the HTTP session of the coordinator an error is reported."""
    coordinator = _coordinator({"devices": [_SYR_CONNECT_TEST_NEOSOFT_DEVICE]})

    assert await diag._collect_raw_json_cloud_devices(hass, coordinator) == {
        "error": "no http session available on coordinator"
    }


async def test_collect_raw_json_cloud_devices_without_data(hass: HomeAssistant) -> None:
    """Without coordinator data there is nothing to ask."""
    coordinator = _coordinator(session=MagicMock())

    assert await diag._collect_raw_json_cloud_devices(hass, coordinator) == {}


async def test_collect_raw_json_cloud_devices_failing_device(
    hass: HomeAssistant,
) -> None:
    """A device whose request raises is left out."""
    coordinator = _coordinator(
        {"devices": [_SYR_CONNECT_TEST_NEOSOFT_DEVICE]}, session=MagicMock()
    )

    with patch.object(
        diag, "_fetch_local_device_json", side_effect=RuntimeError("boom")
    ):
        assert await diag._collect_raw_json_cloud_devices(hass, coordinator) == {}


async def test_collect_raw_json_cloud_devices_unexpected_error(
    hass: HomeAssistant,
) -> None:
    """An unexpected error is reported instead of raised."""
    coordinator = _coordinator(
        {"devices": [_SYR_CONNECT_TEST_NEOSOFT_DEVICE]}, session=MagicMock()
    )

    with patch.object(
        diag, "get_integration_version", side_effect=RuntimeError("boom")
    ):
        assert await diag._collect_raw_json_cloud_devices(hass, coordinator) == {
            "error": "failed to collect raw json for devices"
        }


# --- async_get_config_entry_diagnostics -----------------------------------------


async def test_diagnostics_cloud_entry(hass: HomeAssistant) -> None:
    """The diagnostics of a cloud entry: entry, coordinator, devices, projects and raw data."""
    data = {
        "devices": [
            {
                "id": "206AAA67890",
                "name": "LEX Plus 10 S",
                "dclg": "dclg1",
                "available": True,
                "project_id": "p1",
                "status": {
                    "getCNA": "LEXplus10S",
                    "getVER": "1.2.3",
                    "getFIR": "SLPS",
                    "getMAC": "aa:bb:cc:dd:ee:ff",
                    "getFLO": "100",
                },
            },
        ],
        "projects": [
            {"id": "p1", "name": "Haus Mustermann"},
            {"id": "p2", "name": ""},
        ],
        "service": None,
    }
    api = _xml_api([_SYR_CONNECT_TEST_DEVICE_LIST_XML, _SYR_CONNECT_TEST_STATUS_XML])
    coordinator = _coordinator(data, api=api, session=MagicMock())
    coordinator.last_update_success_time = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    entry = _entry()
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result == {
        "entry": {
            "title": "SYR Connect (***REDACTED_USERNAME***)",
            "version": 1,
            "options": {},
            "service": None,
            "model": None,
        },
        "coordinator": {
            "last_update_success": True,
            "last_update_time": "2026-11-14T12:00:00+00:00",
        },
        "devices": [
            {
                "id": "206AAA12345",
                "name": "LEX Plus 10 S",
                "available": True,
                "project_id": "p1",
                "manufacturer": "SYR",
                "model": "LEX Plus 10 S Connect",
                # LEX Plus 10 S has no local access
                "base_path": None,
                "sw_version": "1.2.3",
                "hw_version": "SLPS",
                "api_type": API_TYPE_XML,
                "status_count": 5,
                "status_keys": ["getCNA", "getFIR", "getFLO", "getMAC", "getVER"],
                "dclg": "dclg1",
            }
        ],
        # Project names are entered by the user (often an address) and replaced
        "projects": [{"id": "p1", "name": "My Project"}, {"id": "p2", "name": ""}],
        "raw_xml": {
            "p1": {
                "device_list": _SYR_CONNECT_TEST_REDACTED_DEVICE_LIST_XML,
                "devices": {"dclg1": _SYR_CONNECT_TEST_REDACTED_STATUS_XML},
            }
        },
        "raw_json": {},
    }
    assert "secret123" not in str(result)
    assert "test@example.com" not in str(result)


async def test_diagnostics_without_coordinator_data(hass: HomeAssistant) -> None:
    """Without coordinator data the diagnostics have no devices and projects."""
    entry = _entry()
    entry.runtime_data = _coordinator()

    assert await async_get_config_entry_diagnostics(hass, entry) == {
        "entry": {
            "title": "SYR Connect (***REDACTED_USERNAME***)",
            "version": 1,
            "options": {},
            "service": None,
            "model": None,
        },
        "coordinator": {"last_update_success": True, "last_update_time": None},
        "devices": [],
        "projects": [],
        "raw_xml": {},
        "raw_json": {"error": "no http session available on coordinator"},
    }


async def test_diagnostics_local_entry(hass: HomeAssistant) -> None:
    """A local entry has no raw XML; its raw JSON loses addresses and serial number."""
    status = {
        "getSRN": "112AAA12345",
        "getVER": "Safe-Tech-2.0.5",
        "getFIR": "FW_ST_01",
        "getWIP": "192.168.1.100",
        "getMAC1": "11:22:33:44:55:66",
        "getMAC2": "aa:bb:cc:dd:ee:ff",
        "getCNO": "CNO1234567890AB",
        "getFLO": "5",
    }
    data = {
        "devices": [
            {
                "id": "112AAA12345",
                "name": "SafeTech Plus Connect",
                "available": True,
                "status": status,
            }
        ],
        "projects": [],
    }
    entry = _entry(
        API_TYPE_JSON, **{CONF_MODEL: "safetechplus", CONF_HOST: "192.168.1.100"}
    )
    entry.runtime_data = _coordinator(data, api=_json_api(dict(status)))

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["model"] == "safetechplus"
    assert result["raw_xml"] == {}
    assert result["raw_json"] == {
        "112AAA12345": {
            "getSRN": "**REDACTED**",
            "getVER": "Safe-Tech-2.0.5",
            "getFIR": "FW_ST_01",
            "getWIP": "**REDACTED**",
            "getMAC1": "11:22:33:XX:XX:XX",
            "getMAC2": "AA:BB:CC:XX:XX:XY",
            "getCNO": "**REDACTED**",
            "getFLO": "5",
        }
    }
    assert result["devices"] == [
        {
            "id": "112AAA12345",
            "name": "SafeTech Plus Connect",
            "available": True,
            "project_id": None,
            "manufacturer": "SYR",
            "model": "SafeTech Plus Connect",
            "base_path": "/trio",
            "sw_version": "Safe-Tech-2.0.5",
            "hw_version": "FW_ST_01",
            "api_type": API_TYPE_JSON,
            # Only the sensors a SafeTech Plus gets; getFIR is not in its allowlist
            "status_count": 6,
            "status_keys": [
                "getFLO",
                "getMAC1",
                "getMAC2",
                "getSRN",
                "getVER",
                "getWIP",
            ],
        }
    ]
    # The code number on the device label registers the device to an account
    assert "CNO1234567890AB" not in str(result)
    assert "192.168.1.100" not in str(result)


async def test_diagnostics_device_without_status(hass: HomeAssistant) -> None:
    """A device without status is listed as unknown model without sensors."""
    data = {
        "devices": [
            {"id": "UNKNOWN01", "name": "Unknown", "available": False, "status": {}}
        ],
        "projects": [],
    }
    entry = _entry()
    entry.runtime_data = _coordinator(data, session=MagicMock())

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["devices"] == [
        {
            "id": "UNKNOWN01",
            "name": "Unknown",
            "available": False,
            "project_id": None,
            "manufacturer": "Unknown",
            "model": "Unknown model",
            "base_path": None,
            "sw_version": None,
            "hw_version": None,
            "api_type": API_TYPE_XML,
            "status_count": 0,
            "status_keys": [],
        }
    ]


async def test_diagnostics_service_branding(hass: HomeAssistant) -> None:
    """Diagnostics name the cloud service and the model names of that service."""
    data = {
        "devices": [
            {
                "id": "FLOOR01",
                "name": "Floor",
                "status": {"getVER": "Syr Floorsensor 2.23"},
            },
        ],
        "projects": [],
        "service": "de.consoft.gc.conel.connect",
    }
    entry = _entry(**{CONF_SERVICE: "de.consoft.gc.conel.connect"})
    entry.runtime_data = _coordinator(data, session=MagicMock())

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["service"] == "de.consoft.gc.conel.connect"
    assert result["devices"][0]["manufacturer"] == "CONEL"
    assert result["devices"][0]["model"] == "CLEAR PRO Floor Sensor"


async def test_diagnostics_cloud_device_with_local_api(
    hass: HomeAssistant, integration_version: str
) -> None:
    """A cloud device whose model offers the local API adds its local status."""
    entry = _entry()
    entry.runtime_data = _coordinator(
        {"devices": [_SYR_CONNECT_TEST_NEOSOFT_DEVICE], "projects": []},
        session=MagicMock(),
    )

    with patch.object(diag, "SyrConnectJsonAPI") as mock_api_class:
        api = mock_api_class.return_value
        api.is_session_valid.return_value = True
        api.get_device_status = AsyncMock(
            return_value={"getSRN": "206AAA12345", "getFLO": "5"}
        )

        result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["raw_json"] == {"dev1": {"getSRN": "**REDACTED**", "getFLO": "5"}}
    assert mock_api_class.call_args.kwargs == {
        "host": "192.168.1.100",
        "base_path": "/neosoft",
        "integration_version": integration_version,
    }
