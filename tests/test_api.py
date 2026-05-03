"""Tests for GarminDiveClient HTTP behaviour."""
from __future__ import annotations

from typing import Any

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from custom_components.garmin_dive.api import GarminDiveClient


@pytest.fixture
async def client(load_fixture):
    """Yield a GarminDiveClient backed by a fresh aiohttp session."""
    async with aiohttp.ClientSession() as session:
        async def get_token() -> str:
            return "test-token"

        yield GarminDiveClient(session=session, get_token=get_token)


async def test_get_dive_summary_returns_decoded_json(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture: Any
):
    fixture = load_fixture("dive_summary_one")
    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/dive/summary",
        "GET",
        aresponses.Response(status=200, text=__import__("json").dumps(fixture)),
        match_querystring=False,
    )
    result = await client.get_dive_summary(page=0, results_per_page=1)
    assert result["totalCount"] == 68
    assert result["diveActivities"][0]["name"] == "Elphinstone (South side)"


async def test_get_dive_summary_sends_bearer_and_app_headers(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture: Any
):
    captured: dict[str, str] = {}

    async def handler(request):
        captured.update(request.headers)
        return aresponses.Response(status=200, text="{}")

    aresponses.add("gcs.garmin.com", "/diving/v1/dive/summary", "GET", handler)
    await client.get_dive_summary(page=0, results_per_page=1)
    assert captured["Authorization"] == "bearer test-token"
    assert captured["X-App-Ver"] == "3.4"
    assert captured["X-Lang"] == "en"
    assert captured["Accept"] == "application/json"
    assert captured["User-Agent"].startswith("Dive/3.4")
