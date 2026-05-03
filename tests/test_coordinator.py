"""Tests for the coordinator's data-assembly logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.garmin_dive.coordinator import (
    CoordinatorData,
    build_data,
)


@pytest.fixture
def fake_api(load_fixture):
    api = MagicMock()
    api.get_dive_summary = AsyncMock(return_value=load_fixture("dive_summary_full"))
    api.get_dive_devices = AsyncMock(return_value=load_fixture("dive_devices"))
    api.get_dive_tags = AsyncMock(return_value=load_fixture("dive_tags"))
    api.get_gear_summary = AsyncMock(return_value=load_fixture("gear_summary"))
    api.get_gear_detail = AsyncMock(
        side_effect=[
            load_fixture("gear_detail_regulator"),
            load_fixture("gear_detail_light"),
        ]
    )
    return api


async def test_build_data_assembles_snapshot(fake_api):
    data = await build_data(
        api=fake_api,
        current_user_date="2026-05-03",
        previous_gear_last_modified={},
    )
    assert isinstance(data, CoordinatorData)
    assert data.total_dives == 68
    assert len(data.dives) == 3
    assert data.dive_tags["RECREATIONAL"] == 45
    assert {d.product_display_name for d in data.devices} == {
        "Descent MK2i",
        "Descent T1",
    }
    # Gear: 3 summary items, but our mocked side_effect only returns 2 details.
    # build_data should still surface all 3 with the summary baseline.
    assert {g.gear_id for g in data.gear} == {141548, 247811, 463947}


async def test_build_data_skips_detail_fetch_when_unchanged(fake_api, load_fixture):
    fake_api.get_gear_detail = AsyncMock()  # should not be called
    summary_with_ts = [dict(item) for item in load_fixture("gear_summary")]
    # Stub: every entry has a known lastModifiedTs and previous map matches it.
    for entry in summary_with_ts:
        entry.setdefault("lastModifiedTs", "2025-01-01T00:00:00Z")
        entry["lastModifiedTs"] = "2025-01-01T00:00:00Z"
    fake_api.get_gear_summary = AsyncMock(return_value=summary_with_ts)
    previous = {entry["gearId"]: "2025-01-01T00:00:00Z" for entry in summary_with_ts}

    await build_data(
        api=fake_api,
        current_user_date="2026-05-03",
        previous_gear_last_modified=previous,
    )
    fake_api.get_gear_detail.assert_not_awaited()
