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


async def test_get_dive_devices(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/dive/devices",
        "GET",
        aresponses.Response(status=200, text=__import__("json").dumps(load_fixture("dive_devices"))),
    )
    devices = await client.get_dive_devices()
    assert isinstance(devices, list)
    assert devices[0]["productDisplayName"] == "Descent MK2i"


async def test_get_dive_tags(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/dive/tags",
        "GET",
        aresponses.Response(status=200, text=__import__("json").dumps(load_fixture("dive_tags"))),
    )
    tags = await client.get_dive_tags()
    assert tags["RECREATIONAL"] == 45


async def test_get_gear_summary_passes_all_gear_types(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    captured_qs: list[tuple[str, str]] = []

    async def handler(request):
        captured_qs.extend(request.query.items())
        return aresponses.Response(
            status=200,
            text=__import__("json").dumps(load_fixture("gear_summary")),
        )

    aresponses.add("gcs.garmin.com", "/diving/v1/gear/summary", "GET", handler)
    result = await client.get_gear_summary(current_user_date="2026-05-03")
    assert isinstance(result, list)
    assert any(item["gearId"] == 247811 for item in result)
    # Every gear type should have been sent as a `gear-types` query param.
    types_sent = {v for k, v in captured_qs if k == "gear-types"}
    assert "REGULATOR" in types_sent
    assert "OTHER" in types_sent
    assert len(types_sent) >= 25


async def test_get_gear_detail(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/gear/141548",
        "GET",
        aresponses.Response(
            status=200,
            text=__import__("json").dumps(load_fixture("gear_detail_regulator")),
        ),
    )
    detail = await client.get_gear_detail(gear_id=141548, current_user_date="2026-05-03")
    assert detail["brand"] == "Atomic Aquatics"
    assert detail["nextServiceDate"] == "2027-04-04"
