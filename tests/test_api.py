"""Tests for GarminDiveClient HTTP behaviour."""

from __future__ import annotations

import json
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
        aresponses.Response(
            status=200, text=__import__("json").dumps(load_fixture("dive_devices"))
        ),
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


async def test_graphql_posts_operation_and_variables(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    captured: dict[str, Any] = {}

    async def handler(request):
        captured["body"] = await request.json()
        return aresponses.Response(
            status=200,
            text=json.dumps(load_fixture("dive_images_graphql")),
        )

    aresponses.add("gcs.garmin.com", "/diving/graphql/query", "POST", handler)
    query_str = (
        "query DiveImagesByDateRange("
        "$playerId: Long!, $start: LocalDate!, $end: LocalDate!) { ... }"
    )
    result = await client.graphql(
        operation_name="DiveImagesByDateRange",
        query=query_str,
        variables={"playerId": 106627261, "start": "2026-01-01", "end": "2026-12-31"},
    )
    assert captured["body"]["operationName"] == "DiveImagesByDateRange"
    assert captured["body"]["variables"]["playerId"] == 106627261
    assert "extensions" in captured["body"]
    expected_uuid = "3730581e-c80e-4c19-8513-cd403e1c72a5"
    assert result["data"]["diveImages"]["items"][0]["imageUUID"] == expected_uuid


async def test_get_dive_photos_by_year(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    aresponses.add(
        "gcs.garmin.com",
        "/diving/graphql/query",
        "POST",
        aresponses.Response(status=200, text=json.dumps(load_fixture("dive_images_graphql"))),
    )
    result = await client.get_dive_photos(profile_id=106627261, year=2025)
    assert result["data"]["diveImages"]["items"][0]["entityReferenceId"] == "23285230"
