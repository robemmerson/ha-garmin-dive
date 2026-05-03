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
    fake_api.get_dive_photos = AsyncMock(
        return_value={"data": {"playerProfile": {"medias": {"content": []}}}}
    )

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
        profile_id=999000111,
        year=2026,
    )
    assert "00000000-0000-4000-8000-000000000003" in downloaded
    assert any(g.photo_local_url for g in data.gear if g.gear_id == 247811)


async def test_build_data_attaches_dive_photos_by_event_date(fake_api, tmp_path, load_fixture):
    """Photos with eventDate matching a dive's startTime are attached to the dive."""
    fake_api.get_dive_photos = AsyncMock(return_value=load_fixture("dive_images_graphql"))

    cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")

    async def fake_download(records, *, session):
        return None

    cache.download_records = fake_download  # type: ignore[assignment]

    data = await build_data(
        api=fake_api,
        current_user_date="2026-05-03",
        previous_gear_last_modified={},
        photo_cache=cache,
        http_session=MagicMock(),
        profile_id=999000111,
        year=2026,
    )

    # Two photos share startTime "2025-06-15T10:00:00+00:00" — that dive is id 10000001.
    dive_with_photos = next(d for d in data.dives if d.id == 10000001)
    assert dive_with_photos.photo_count == 2
    assert dive_with_photos.photos["medium"] is not None
    assert "/local/garmin_dive/abcd1234/" in dive_with_photos.photos["medium"]
    # One photo at "2025-06-14T11:30:00+00:00" → dive 10000003.
    other_dive = next(d for d in data.dives if d.id == 10000003)
    assert other_dive.photo_count == 1
    # The remaining dive has no matching photo.
    no_photo_dive = next(d for d in data.dives if d.id == 10000002)
    assert no_photo_dive.photo_count == 0
    assert no_photo_dive.photos == {"thumb": None, "medium": None, "large": None}


async def test_coordinator_fires_new_dive_event(hass, fake_api):
    """When totalCount increases, fire garmin_dive_new_dive."""
    auth = MagicMock()
    auth.profile_id = 999000111

    coordinator = GarminDiveCoordinator(
        hass,
        api=fake_api,
        auth=auth,
        photo_cache=None,
        http_session=MagicMock(),
        scan_interval_minutes=120,
    )
    # Seed with a previous snapshot saying we knew of dives 10000001 and 10000003.
    coordinator._known_dive_ids = {10000001, 10000003}

    fired: list = []
    hass.bus.async_listen(EVENT_NEW_DIVE, lambda evt: fired.append(evt.data))

    await coordinator._async_update_data()
    await hass.async_block_till_done()

    new_ids = [d["dive"]["id"] for d in fired]
    assert 10000002 in new_ids  # the new dive id appearing this cycle
    assert 10000001 not in new_ids
    assert fired[0]["account_id"] == "999000111"
