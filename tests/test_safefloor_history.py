"""Tests for the SafeFloor measurement history (GetSafeFloorStatistics -> external statistics)."""
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.syr_connect.api_json import SyrConnectJsonAPI
from custom_components.syr_connect.api_xml import SyrConnectXmlAPI
from custom_components.syr_connect.coordinator import SyrConnectDataUpdateCoordinator
from custom_components.syr_connect.exceptions import SyrConnectConnectionError
from custom_components.syr_connect.payload_builder import PayloadBuilder
from custom_components.syr_connect.response_parser import ResponseParser
from custom_components.syr_connect.safefloor_history import (
    SafeFloorHistoryState,
    async_import_safefloor_history,
    hourly_statistics,
    safefloor_statistic_id,
)

FIXTURES = Path(__file__).parent / "fixtures/xml"
DCLG = "7605aa61-73b8-ef11-800c-be3af2b6059f"
SERIAL = "123456789"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


# --- Payload ----------------------------------------------------------------------------------


def test_build_safefloor_statistics_payload() -> None:
    """The payload requests one measurement series with unit and adds the checksum."""
    fake_checksum = MagicMock()
    fake_checksum.compute_xml_checksum.return_value = "CHK"
    pb = PayloadBuilder("1.2.3", fake_checksum)

    with patch.object(PayloadBuilder, "_compute_locale_lang_reg", return_value=("de", "DE")):
        payload = pb.build_safefloor_statistics_payload("sess", DCLG, 1, "°C", 4)

    assert f'<col><dcl dclg="{DCLG}"><sh t="1" rtyp="4" lg="de" rg="DE" unit="°C"/></dcl></col>' in payload
    assert '<us ug="sess"/>' in payload
    assert payload.endswith('<cs v="CHK"/></sc>')


def test_build_safefloor_statistics_payload_escapes_values() -> None:
    """Values are XML-escaped."""
    fake_checksum = MagicMock()
    fake_checksum.compute_xml_checksum.return_value = "CHK"
    pb = PayloadBuilder("1.2.3", fake_checksum)

    payload = pb.build_safefloor_statistics_payload("s&1", "d<1>", 2, "%", 4)

    assert 'ug="s&amp;1"' in payload
    assert 'dclg="d&lt;1&gt;"' in payload
    assert 't="2"' in payload and 'unit="%"' in payload


# --- Parser -----------------------------------------------------------------------------------


def test_parse_safefloor_statistics_temperature() -> None:
    """Raw temperature measurements are returned as sorted (UTC timestamp, value) tuples."""
    result = ResponseParser.parse_safefloor_statistics_response(
        _fixture("SyrSafeFloor_GetSafeFloorStatistics_Temperature.xml")
    )

    assert len(result) == 9
    assert result[0] == (_utc("2026-09-26 14:45:27"), 14.6)
    assert result[-1] == (_utc("2026-09-28 14:45:27"), 15.8)
    assert result == sorted(result)


def test_parse_safefloor_statistics_humidity() -> None:
    """Humidity values come without decimals."""
    result = ResponseParser.parse_safefloor_statistics_response(
        _fixture("SyrSafeFloor_GetSafeFloorStatistics_Humidity.xml")
    )

    assert len(result) == 9
    assert result[3] == (_utc("2026-09-27 08:45:27"), 84.0)


def test_parse_safefloor_statistics_empty() -> None:
    """A request without unit returns an empty collection."""
    xml = '<?xml version="1.0" encoding="utf-8"?><sc><col /><cs v="0" /></sc>'
    assert ResponseParser.parse_safefloor_statistics_response(xml) == []


def test_parse_safefloor_statistics_error_message() -> None:
    """An API error message (e.g. unknown device) raises ValueError."""
    xml = (
        '<?xml version="1.0" encoding="utf-8"?><sc>'
        '<msg v="An error has occurred." hl="Error" mtid="1" /><cs v="CCC" /></sc>'
    )
    with pytest.raises(ValueError, match="An error has occurred"):
        ResponseParser.parse_safefloor_statistics_response(xml)


def test_parse_safefloor_statistics_invalid_xml() -> None:
    """Invalid XML raises ValueError."""
    with pytest.raises(ValueError, match="Invalid XML"):
        ResponseParser.parse_safefloor_statistics_response("<sc><col>")


def test_parse_safefloor_statistics_skips_invalid_entries() -> None:
    """Entries with missing or invalid timestamp/value are skipped, decimal commas accepted."""
    xml = (
        "<sc><col><dcl><sh><sths>"
        '<sth dt="2026-09-27 02:45:27" v="15,1" />'
        '<sth dt="2026-09-26 20:45:27" v="" />'
        '<sth dt="invalid" v="14.0" />'
        '<sth v="14.0" />'
        '<sth dt="2026-09-26 14:45:27" v="nan" />'
        '<sth dt="2026-09-26 08:45:27" v="14.2" />'
        "</sths></sh></dcl></col></sc>"
    )
    assert ResponseParser.parse_safefloor_statistics_response(xml) == [
        (_utc("2026-09-26 08:45:27"), 14.2),
        (_utc("2026-09-27 02:45:27"), 15.1),
    ]


# --- API client -------------------------------------------------------------------------------


@pytest.fixture
def api_client() -> SyrConnectXmlAPI:
    """XML API client with a valid session."""
    client = SyrConnectXmlAPI(MagicMock(spec=aiohttp.ClientSession), "test@example.com", "testpassword")
    client.session_data = "test_session"
    client.session_expires_at = datetime.now(UTC) + timedelta(minutes=10)
    return client


async def test_api_get_safefloor_history(api_client: SyrConnectXmlAPI) -> None:
    """The API posts the payload to GetSafeFloorStatistics and parses the measurements."""
    xml = _fixture("SyrSafeFloor_GetSafeFloorStatistics_Temperature.xml")
    with patch.object(api_client.http_client, "post", AsyncMock(return_value=xml)) as mock_post:
        result = await api_client.get_safefloor_history(DCLG, 1, "°C")

    assert len(result) == 9
    url, data = mock_post.call_args.args
    assert url.endswith("/GetSafeFloorStatistics")
    assert 'rtyp="4"' in data["xml"] and 'unit="°C"' in data["xml"]


async def test_api_get_safefloor_history_uses_service_base_url() -> None:
    """The service base URL (e.g. CONEL CLEAR PRO) is used."""
    client = SyrConnectXmlAPI(
        MagicMock(spec=aiohttp.ClientSession),
        "test@example.com",
        "testpassword",
        api_base_url="https://api.conelclearpro.de/",
    )
    assert client._safefloor_get_statistics_url == (
        "https://api.conelclearpro.de/WebServices/SyrControlWebServiceTest2.asmx/GetSafeFloorStatistics"
    )


async def test_api_get_safefloor_history_connection_error(api_client: SyrConnectXmlAPI) -> None:
    """Network errors are raised as SyrConnectConnectionError."""
    with (
        patch.object(api_client.http_client, "post", AsyncMock(side_effect=aiohttp.ClientError("boom"))),
        pytest.raises(SyrConnectConnectionError),
    ):
        await api_client.get_safefloor_history(DCLG, 2, "%")


async def test_api_get_safefloor_history_relogin(api_client: SyrConnectXmlAPI) -> None:
    """An expired session is renewed first."""
    api_client.session_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    with (
        patch.object(api_client, "login", AsyncMock(return_value=True)) as mock_login,
        patch.object(api_client.http_client, "post", AsyncMock(return_value="<sc><col /></sc>")),
    ):
        assert await api_client.get_safefloor_history(DCLG, 1, "°C") == []
    mock_login.assert_awaited_once()


# --- Fetch state ------------------------------------------------------------------------------


def test_history_state_is_due() -> None:
    """Fetch on first run, on a new upload and after 24 h; wait 30 min after a failure."""
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    state = SafeFloorHistoryState()
    assert state.is_due("28.09.2026 14:55:43", now)

    state.mark_imported("28.09.2026 14:55:43", now)
    assert not state.is_due("28.09.2026 14:55:43", now + timedelta(hours=23))
    assert state.is_due("28.09.2026 14:55:43", now + timedelta(hours=24))
    assert state.is_due("02.10.2026 14:55:40", now + timedelta(minutes=1))

    state.mark_failed(now)
    assert not state.is_due("02.10.2026 14:55:40", now + timedelta(minutes=29))
    assert state.is_due("02.10.2026 14:55:40", now + timedelta(minutes=30))

    state.mark_imported("02.10.2026 14:55:40", now + timedelta(minutes=30))
    assert state.retry_at is None


def test_history_state_without_upload_marker() -> None:
    """Without getSRN timestamp the history is fetched once a day."""
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    state = SafeFloorHistoryState()
    state.mark_imported(None, now)
    assert not state.is_due(None, now + timedelta(hours=12))
    assert state.is_due(None, now + timedelta(hours=24))


# --- Statistics -------------------------------------------------------------------------------


def test_statistic_id() -> None:
    """Statistic IDs are valid external statistic IDs."""
    assert safefloor_statistic_id(SERIAL, "temperature") == "syr_connect:123456789_temperature"
    assert safefloor_statistic_id("43AAA12-x", "humidity") == "syr_connect:43aaa12_x_humidity"


def _row(start: str, mean: float, low: float, high: float) -> dict:
    return {"start": _utc(start), "mean": pytest.approx(mean), "min": low, "max": high}


def test_hourly_statistics_takes_over_the_hour_before() -> None:
    """Every hour from the first to the last measurement gets a row; hours without a measurement repeat the hour before."""
    rows = hourly_statistics([(_utc("2026-09-26 14:45:27"), 14.6), (_utc("2026-09-26 20:45:27"), 14.9)])
    assert [row["start"].hour for row in rows] == list(range(14, 21))
    assert rows[0] == _row("2026-09-26 14:00:00", 14.6, 14.6, 14.6)
    assert rows[5] == _row("2026-09-26 19:00:00", 14.6, 14.6, 14.6)
    # The hour of the second measurement gets exactly the measured value, nothing is mixed
    assert rows[6] == _row("2026-09-26 20:00:00", 14.9, 14.9, 14.9)


def test_hourly_statistics_several_measurements_within_an_hour() -> None:
    """Short measurement intervals: measurements of the same hour are combined, the next hour repeats the row."""
    rows = hourly_statistics([
        (_utc("2026-09-26 16:10:00"), 18.0),
        (_utc("2026-09-26 14:35:00"), 16.0),
        (_utc("2026-09-26 14:05:00"), 14.0),
    ])
    assert rows == [
        _row("2026-09-26 14:00:00", 15.0, 14.0, 16.0),
        _row("2026-09-26 15:00:00", 15.0, 14.0, 16.0),
        _row("2026-09-26 16:00:00", 18.0, 18.0, 18.0),
    ]


def test_hourly_statistics_single_and_no_measurement() -> None:
    """One measurement gives one row; no measurements, no rows."""
    assert hourly_statistics([(_utc("2026-09-26 14:45:27"), 14.6)]) == [_row("2026-09-26 14:00:00", 14.6, 14.6, 14.6)]
    assert hourly_statistics([]) == []


def test_import_without_measurements(hass: HomeAssistant) -> None:
    """Nothing is imported without measurements."""
    with patch("custom_components.syr_connect.safefloor_history.async_add_external_statistics") as mock_add:
        assert async_import_safefloor_history(hass, SERIAL, "Floor", "temperature", "°C", []) == 0
    mock_add.assert_not_called()


def test_import_metadata(hass: HomeAssistant) -> None:
    """Metadata describes an external mean statistic with unit and unit class."""
    measurements = ResponseParser.parse_safefloor_statistics_response(
        _fixture("SyrSafeFloor_GetSafeFloorStatistics_Humidity.xml")
    )
    with patch("custom_components.syr_connect.safefloor_history.async_add_external_statistics") as mock_add:
        assert async_import_safefloor_history(hass, SERIAL, "Floor", "humidity", "%", measurements) == 49

    _, metadata, statistics = mock_add.call_args.args
    assert metadata["statistic_id"] == "syr_connect:123456789_humidity"
    assert metadata["source"] == "syr_connect"
    assert metadata["name"] == "Floor humidity history"
    assert metadata["unit_of_measurement"] == "%"
    assert metadata["unit_class"] == "unitless"
    assert metadata["has_sum"] is False
    assert metadata["mean_type"] == StatisticMeanType.ARITHMETIC
    # 26.09. 14:00 (hour of the first measurement) to 28.09. 14:00 (hour of the last measurement)
    assert len(statistics) == 49
    assert statistics[0]["start"] == _utc("2026-09-26 14:00:00")
    assert statistics[-1]["start"] == _utc("2026-09-28 14:00:00")


# --- Coordinator ------------------------------------------------------------------------------


def _safefloor_device(dk: int = 120) -> dict:
    return {"id": SERIAL, "name": "Floor", "project_id": "project1", "dclg": DCLG, "dk": dk}


def _status(upload: str) -> dict:
    return {"getSRN": SERIAL, "getSRN_dt": upload, "getCEL": "158", "getHMD": "81", "dst": "3"}


async def _create_coordinator(
    hass: HomeAssistant, entry, device: dict, status: dict, history: AsyncMock
) -> tuple[SyrConnectDataUpdateCoordinator, MagicMock]:
    with patch("custom_components.syr_connect.coordinator.SyrConnectXmlAPI") as mock_api_class:
        mock_api = MagicMock()
        mock_api.session_data = "test_session"
        mock_api.projects = [{"id": "project1", "name": "Test Project"}]
        mock_api.is_session_valid = MagicMock(return_value=True)
        mock_api.get_devices = AsyncMock(side_effect=lambda _pid: [dict(device)])
        mock_api.get_device_status = AsyncMock(return_value=status)
        mock_api.get_safefloor_history = history
        mock_api_class.return_value = mock_api
        coordinator = SyrConnectDataUpdateCoordinator(
            hass,
            MagicMock(),
            {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password"},
            60,
        )
    coordinator.config_entry = entry
    return coordinator, mock_api


async def test_coordinator_imports_history_once_per_upload(
    hass: HomeAssistant, setup_in_progress_config_entry
) -> None:
    """History is fetched on the first update and again only after a new upload."""
    hass.config.components.add("recorder")
    measurements = [(_utc("2026-09-28 14:45:27"), 15.8)]
    history = AsyncMock(return_value=measurements)
    status = _status("28.09.2026 14:55:43")
    coordinator, mock_api = await _create_coordinator(
        hass, setup_in_progress_config_entry, _safefloor_device(), status, history
    )

    with patch("custom_components.syr_connect.coordinator.async_import_safefloor_history", return_value=1) as mock_import:
        await coordinator.async_config_entry_first_refresh()
        assert history.await_count == 2
        assert [c.args[1:3] for c in history.await_args_list] == [(1, "°C"), (2, "%")]
        assert [c.args[1:5] for c in mock_import.call_args_list] == [
            (SERIAL, "Floor", "temperature", "°C"),
            (SERIAL, "Floor", "humidity", "%"),
        ]

        # Same upload -> nothing to do
        await coordinator.async_refresh()
        assert history.await_count == 2

        # New upload -> fetch again
        mock_api.get_device_status.return_value = _status("02.10.2026 14:55:40")
        await coordinator.async_refresh()
        assert history.await_count == 4
        assert coordinator.last_update_success


async def test_coordinator_history_failure_does_not_fail_update(
    hass: HomeAssistant, setup_in_progress_config_entry
) -> None:
    """A failing history fetch is logged, retried later and keeps the regular update working."""
    hass.config.components.add("recorder")
    history = AsyncMock(side_effect=SyrConnectConnectionError("cloud down"))
    coordinator, _ = await _create_coordinator(
        hass, setup_in_progress_config_entry, _safefloor_device(), _status("28.09.2026 14:55:43"), history
    )

    with patch("custom_components.syr_connect.coordinator.async_import_safefloor_history") as mock_import:
        await coordinator.async_config_entry_first_refresh()
        assert coordinator.last_update_success
        assert coordinator.data["devices"][0]["status"]["getCEL"] == "158"
        assert history.await_count == 1
        mock_import.assert_not_called()

        # Within the retry delay nothing is fetched
        await coordinator.async_refresh()
        assert history.await_count == 1

        # After the retry delay it is fetched again
        state = coordinator._safefloor_history[SERIAL]
        state.retry_at = datetime.now(UTC) - timedelta(seconds=1)
        history.side_effect = None
        history.return_value = []
        await coordinator.async_refresh()
        assert history.await_count == 3
        assert state.retry_at is None


@pytest.mark.parametrize(
    ("dk", "recorder_loaded"),
    [(140, True), (120, False)],
    ids=["not_safefloor", "no_recorder"],
)
async def test_coordinator_skips_history(
    hass: HomeAssistant, setup_in_progress_config_entry, dk: int, recorder_loaded: bool
) -> None:
    """Other devices and installations without recorder are not affected."""
    if recorder_loaded:
        hass.config.components.add("recorder")
    history = AsyncMock(return_value=[])
    coordinator, _ = await _create_coordinator(
        hass, setup_in_progress_config_entry, _safefloor_device(dk), _status("28.09.2026 14:55:43"), history
    )

    await coordinator.async_config_entry_first_refresh()

    history.assert_not_awaited()


async def test_coordinator_history_skipped_for_json_api(hass: HomeAssistant) -> None:
    """The local JSON API has no cloud history."""
    hass.config.components.add("recorder")
    coordinator = MagicMock(spec=SyrConnectDataUpdateCoordinator)
    coordinator.hass = hass
    coordinator.api = MagicMock(spec=SyrConnectJsonAPI)
    coordinator._safefloor_history = {}
    device = _safefloor_device() | {"status": _status("28.09.2026 14:55:43")}

    await SyrConnectDataUpdateCoordinator._async_update_safefloor_history(coordinator, device)

    assert coordinator._safefloor_history == {}
