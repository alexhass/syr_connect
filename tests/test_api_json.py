"""Tests for the local JSON API client using fixtures."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.syr_connect.api_json import SyrConnectJsonAPI

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "json"


def load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize(
    "fixture",
    [
        "SafeTech_get_all.json",
        "SafeTech_get_all_v4.json",
        "SafeTech_get_all_v4_copy.json",
        "NeoSoft2500_get_all.json",
    ],
)
async def test_json_client_parses_fixture(fixture: str) -> None:
    """Ensure SyrConnectJsonAPI returns the JSON as status dict when _fetch_json is patched."""
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://127.0.0.1:5333/local/")

    data = load_fixture(fixture)

    # Patch the internal fetcher to return our fixture data
    client._fetch_json = lambda path, timeout=10: data

    status = await client.get_device_status("local")
    assert isinstance(status, dict)
    # Sanity check: fixture contains at least one getXXX key
    assert any(k.startswith("get") for k in status.keys())


async def test_get_devices_builds_device_entry_from_fixture() -> None:
    sess = MagicMock()
    client = SyrConnectJsonAPI(sess, base_url="http://127.0.0.1:5333/local/")

    data = load_fixture("SafeTech_get_all_v4.json")
    client._fetch_json = lambda path, timeout=10: data

    devices = await client.get_devices("local")
    assert isinstance(devices, list)
    assert len(devices) == 1
    dev = devices[0]
    assert "id" in dev and dev["id"]
    assert "name" in dev and dev["name"]