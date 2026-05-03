"""End-to-end integration smoke tests.

These tests stitch together the auth, API client, and coordinator layers
(with the HTTP boundary mocked via aresponses) and assert that real-shaped
Garmin payloads flow all the way through `build_data()` and produce a
populated `CoordinatorData`.

This is the proof-of-life test that protects against any single layer's
mocks drifting from the others.
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from custom_components.garmin_dive.api import GarminDiveClient
from custom_components.garmin_dive.auth import GarminDiveAuth
from custom_components.garmin_dive.coordinator import build_data


@pytest.fixture
async def http_client():
    async with aiohttp.ClientSession() as session:
        yield session


async def test_authenticated_pipeline_returns_full_coordinator_data(
    aresponses: ResponsesMockServer,
    http_client: aiohttp.ClientSession,
    load_fixture,
):
    """Auth pre-loaded with a DIVE token. API client signs every call with it.
    `build_data` fans out the 4 unconditional requests + 0 conditional gear
    detail (because previous map matches everything) and returns a populated
    CoordinatorData.

    This proves end-to-end:
      - the auth-injection contract holds (every call carries `bearer test-dive`)
      - the JSON parsers in the api layer wire correctly into DTOs
      - the coordinator's gear delta logic correctly skips refetch
    """
    captured_authz: list[str] = []

    async def _capture_summary(request):
        captured_authz.append(request.headers.get("Authorization", ""))
        return aresponses.Response(status=200, text=json.dumps(load_fixture("dive_summary_full")))

    async def _capture_devices(request):
        captured_authz.append(request.headers.get("Authorization", ""))
        return aresponses.Response(status=200, text=json.dumps(load_fixture("dive_devices")))

    async def _capture_tags(request):
        captured_authz.append(request.headers.get("Authorization", ""))
        return aresponses.Response(status=200, text=json.dumps(load_fixture("dive_tags")))

    async def _capture_gear(request):
        captured_authz.append(request.headers.get("Authorization", ""))
        return aresponses.Response(status=200, text=json.dumps(load_fixture("gear_summary")))

    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/dive/summary",
        "GET",
        _capture_summary,
        match_querystring=False,
    )
    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/dive/devices",
        "GET",
        _capture_devices,
    )
    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/dive/tags",
        "GET",
        _capture_tags,
    )
    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/gear/summary",
        "GET",
        _capture_gear,
        match_querystring=False,
    )

    # Wire a real GarminDiveAuth with a pre-set DIVE token (bypasses login)
    auth = GarminDiveAuth(ha_auth=MagicMock(), api=MagicMock())
    auth._dive_access_token = "test-dive"
    auth._dive_refresh_token = "test-refresh"
    auth._dive_expires_at = time.time() + 3600  # well above skew

    api = GarminDiveClient(session=http_client, get_token=auth.get_dive_token)

    # Seed previous_gear_last_modified so needs_detail_fetch returns the empty
    # set (no detail fetches), proving the delta path is exercised.
    summary_fixture = load_fixture("gear_summary")
    previous = {int(item["gearId"]): item.get("lastModifiedTs", "") for item in summary_fixture}

    data = await build_data(
        api=api,
        current_user_date="2026-05-03",
        previous_gear_last_modified=previous,
    )

    # Real data flowed through every layer
    assert data.total_dives == 68, "summary.totalCount surfaced"
    assert len(data.dives) == 3, "all 3 dives populated"
    assert data.dives[0].name == "Elphinstone (South side)", "DTO accessor works"
    assert data.dive_tags["RECREATIONAL"] == 45, "tags surfaced"
    assert {d.product_display_name for d in data.devices} == {
        "Descent MK2i",
        "Descent T1",
    }, "devices surfaced"
    assert {g.gear_id for g in data.gear} == {141548, 247811, 463947}, "gear surfaced"

    # Auth contract: every captured call carried the DIVE bearer
    assert all(a == "bearer test-dive" for a in captured_authz), captured_authz
    assert len(captured_authz) == 4, "exactly 4 unconditional calls fired"


async def test_token_refresh_on_skew_propagates_to_api_calls(
    aresponses: ResponsesMockServer,
    http_client: aiohttp.ClientSession,
):
    """If the access token is within the skew window, the auth refreshes via
    diauth.garmin.com BEFORE the API call goes out — and the new bearer is on
    the wire."""
    # diauth refresh endpoint returns a rotated token
    aresponses.add(
        "diauth.garmin.com",
        "/di-oauth2-service/oauth/token",
        "POST",
        aresponses.Response(
            status=200,
            text=json.dumps(
                {
                    "access_token": "rotated-bearer",
                    "refresh_token": "rotated-refresh",
                    "expires_in": 86399,
                    "token_type": "bearer",
                    "refresh_token_expires_in": 2591999,
                    "scope": "DIVE_API_READ",
                    "jti": "test",
                }
            ),
        ),
    )

    captured: list[str] = []

    async def _capture(request):
        captured.append(request.headers["Authorization"])
        return aresponses.Response(status=200, text=json.dumps({"DEEP": 1}))

    aresponses.add("gcs.garmin.com", "/diving/v1/dive/tags", "GET", _capture)

    auth = GarminDiveAuth(ha_auth=MagicMock(), api=MagicMock())
    auth._dive_access_token = "stale-bearer"
    auth._dive_refresh_token = "stale-refresh"
    auth._dive_expires_at = time.time() + 60  # within skew → must refresh

    # The auth's _api needs to be a real GarminDiveClient pointing at the same
    # mock server so _refresh calls api.refresh_dive_token() via diauth.
    async def _noop_token() -> str:
        return ""  # never called on the refresh_dive_token path

    refresh_api = GarminDiveClient(session=http_client, get_token=_noop_token)
    auth._api = refresh_api

    # API client used for the actual data call
    data_api = GarminDiveClient(session=http_client, get_token=auth.get_dive_token)

    tags = await data_api.get_dive_tags()
    assert tags == {"DEEP": 1}
    assert captured == ["bearer rotated-bearer"], (
        f"expected the rotated bearer on the wire, got {captured}"
    )
    assert auth._dive_access_token == "rotated-bearer"
    assert auth._dive_refresh_token == "rotated-refresh"
