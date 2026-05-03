"""Tests for the coordinator's data-assembly logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.garmin_dive.const import EVENT_NEW_DIVE
from custom_components.garmin_dive.coordinator import (
    CoordinatorData,
    GarminDiveCoordinator,
    build_data,
)
from custom_components.garmin_dive.photos import PhotoCache


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


async def test_build_data_with_photos_collects_gear_images(fake_api, tmp_path, load_fixture):
    """Gear images embedded in summary responses get downloaded to the cache."""
    summary_with_image = load_fixture("gear_summary")
    fake_api.get_gear_summary = AsyncMock(return_value=summary_with_image)
    fake_api.get_dive_photos = AsyncMock(return_value={"data": {"diveImages": {"items": []}}})

    cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")
    downloaded: list[str] = []

    async def fake_download(records, *, session):
        downloaded.extend(r.image_uuid for r in records)

    cache.download_records = fake_download  # type: ignore[assignment]

    data = await build_data(
        api=fake_api,
        current_user_date="2026-05-03",
        previous_gear_last_modified={},
        photo_cache=cache,
        http_session=MagicMock(),
        profile_id=106627261,
        year=2026,
    )
    assert "315aa699-ea9b-4323-8177-3d8a77b28e24" in downloaded
    assert any(g.photo_local_url for g in data.gear if g.gear_id == 247811)


async def test_coordinator_fires_new_dive_event(hass, fake_api):
    """When totalCount increases, fire garmin_dive_new_dive."""
    auth = MagicMock()
    auth.profile_id = 106627261

    coordinator = GarminDiveCoordinator(
        hass,
        api=fake_api,
        auth=auth,
        photo_cache=None,
        http_session=MagicMock(),
        scan_interval_minutes=120,
    )
    # Seed with a previous snapshot saying we knew of dives 23285230 and 23261609.
    coordinator._known_dive_ids = {23285230, 23261609}

    fired: list = []
    hass.bus.async_listen(EVENT_NEW_DIVE, lambda evt: fired.append(evt.data))

    await coordinator._async_update_data()
    await hass.async_block_till_done()

    new_ids = [d["dive"]["id"] for d in fired]
    assert 23285231 in new_ids  # the new dive id appearing this cycle
    assert 23285230 not in new_ids
    assert fired[0]["account_id"] == "106627261"
