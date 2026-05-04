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
    # Default: per-dive activity-service fallback returns nothing. Tests that
    # exercise the fallback override this.
    api.get_activity = AsyncMock(return_value={"metadataDTO": {"activityImages": []}})
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
        return {r.image_uuid: {"thumb", "medium", "large"} for r in records}

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
        # Pretend every photo's three sizes landed on disk.
        return {r.image_uuid: {"thumb", "medium", "large"} for r in records}

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
    # Telemetry: 3 Image entries, 1 Video; matched 2 dives; no unmatched eventDates.
    assert data.photo_stats.images_returned == 3
    assert data.photo_stats.videos_returned == 1
    assert data.photo_stats.matched_dives == 2
    assert data.photo_stats.unmatched_event_dates == []
    assert data.photo_stats.download_failures == []


async def test_build_data_skips_dive_photo_url_when_download_failed(
    fake_api, tmp_path, load_fixture
):
    """If the cache says a photo isn't on disk, no URL is surfaced for it."""
    fake_api.get_dive_photos = AsyncMock(return_value=load_fixture("dive_images_graphql"))

    cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")

    async def fake_download(records, *, session):
        # Simulate every download failing — empty cached-sizes set per uuid.
        return {r.image_uuid: set() for r in records}

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

    matched = next(d for d in data.dives if d.id == 10000001)
    assert matched.photo_count == 2  # eventDate match still recorded
    assert matched.photos == {"thumb": None, "medium": None, "large": None}
    # download_failures lists every uuid with no cached sizes (gear + dive).
    assert len(data.photo_stats.download_failures) >= 3


async def test_dive_photos_match_by_activity_id_when_dates_disagree(
    fake_api, tmp_path, load_fixture
):
    """Real-world: GraphQL `eventDate` and /dive/summary `startTime` disagree
    on format (naive vs aware datetimes). Matching by entityReferenceId →
    connectActivityId still binds the photos to the dive."""
    # Dive 10000001 has connectActivityId 99000001. Hand a GraphQL response
    # whose eventDate is naive and so cannot parse-equal the dive's
    # tz-aware startTime, but whose entityReferenceId points at the activity.
    photos_resp = {
        "data": {
            "playerProfile": {
                "__typename": "PlayerProfile",
                "playerProfileId": 999000111,
                "profileName": "rob",
                "medias": {
                    "__typename": "Page_Media",
                    "totalCount": 2,
                    "content": [
                        {
                            "__typename": "Image",
                            "imageUUID": "10000000-0000-4000-8000-000000000a01",
                            "eventDate": "2025-06-15T10:00:00.0",  # naive
                            "entityReferenceId": "99000001",  # connectActivityId
                            "versionedUrls": [
                                {
                                    "version": "MEDIUM_FEED",
                                    "url": "https://example.invalid/aaa-mdfd.jpeg?sig=t",
                                },
                                {
                                    "version": "LARGE",
                                    "url": "https://example.invalid/aaa-larg.jpeg?sig=t",
                                },
                            ],
                        },
                        {
                            "__typename": "Image",
                            "imageUUID": "10000000-0000-4000-8000-000000000a02",
                            "eventDate": "2025-06-15T10:00:00.0",
                            "entityReferenceId": "99000001",
                            "versionedUrls": [
                                {
                                    "version": "MEDIUM_FEED",
                                    "url": "https://example.invalid/bbb-mdfd.jpeg?sig=t",
                                }
                            ],
                        },
                    ],
                },
            }
        }
    }
    fake_api.get_dive_photos = AsyncMock(return_value=photos_resp)
    cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")

    async def fake_download(records, *, session):
        return {r.image_uuid: {"thumb", "medium", "large"} for r in records}

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
    dive = next(d for d in data.dives if d.id == 10000001)
    assert dive.photo_count == 2, "expected both photos bound via activity-id match"
    # Multi-photo: photos_all has both records with usable medium URLs.
    assert len(dive.photos_all) == 2
    assert all("/local/garmin_dive/abcd1234/" in (p["medium"] or "") for p in dive.photos_all)
    # Cover stays single-photo for backward compat with old dashboards.
    assert dive.photos["medium"] == dive.photos_all[0]["medium"]
    assert data.photo_stats.matched_by_activity_id >= 1
    # No fallback HTTP call was issued for this specific dive — the GraphQL
    # activity-id index already covered it.
    fallback_aids = {call.kwargs["activity_id"] for call in fake_api.get_activity.call_args_list}
    assert 99000001 not in fallback_aids


async def test_activity_service_fallback_for_dives_missing_from_graphql(
    fake_api, tmp_path, load_fixture
):
    """When GraphQL doesn't return photos for a dive, the per-activity
    /activity-service endpoint is queried and its activityImages[] are
    ingested. All photos are surfaced, not just the first."""
    # GraphQL returns nothing.
    fake_api.get_dive_photos = AsyncMock(
        return_value={
            "data": {
                "playerProfile": {
                    "__typename": "PlayerProfile",
                    "playerProfileId": 999000111,
                    "profileName": "rob",
                    "medias": {"__typename": "Page_Media", "totalCount": 0, "content": []},
                }
            }
        }
    )

    # /activity-service returns 3 photos for connectActivityId 99000001 and
    # nothing for the others.
    def activity_resp(activity_id: int) -> dict:
        if activity_id != 99000001:
            return {"metadataDTO": {"activityImages": []}}
        return {
            "metadataDTO": {
                "activityImages": [
                    {
                        "imageId": f"f0{i}-0000-4000-8000-000000000abc",
                        "url": f"https://example.invalid/img{i}-larg.jpeg?sig=t",
                        "smallUrl": f"https://example.invalid/img{i}-smth.jpeg?sig=t",
                        "mediumUrl": f"https://example.invalid/img{i}-mdfd.jpeg?sig=t",
                    }
                    for i in range(3)
                ]
            }
        }

    fake_api.get_activity = AsyncMock(side_effect=lambda *, activity_id: activity_resp(activity_id))

    cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")

    async def fake_download(records, *, session):
        return {r.image_uuid: {"thumb", "medium", "large"} for r in records}

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

    dive = next(d for d in data.dives if d.connect_activity_id == 99000001)
    assert dive.photo_count == 3, "all three activity-service photos should be bound"
    assert len(dive.photos_all) == 3
    assert dive.photos["medium"] is not None
    # The fallback is fired for every dive missing from GraphQL.
    assert data.photo_stats.activity_fallback_attempted == len(data.dives)
    assert data.photo_stats.activity_fallback_matched == 1
    assert data.photo_stats.activity_fallback_errors == []


async def test_activity_service_fallback_skipped_when_graphql_already_has_photos(
    fake_api, tmp_path, load_fixture
):
    """If GraphQL already produced records for a dive (by activity-id), the
    integration must NOT issue a redundant /activity-service call."""
    photos_resp = {
        "data": {
            "playerProfile": {
                "__typename": "PlayerProfile",
                "medias": {
                    "__typename": "Page_Media",
                    "totalCount": 1,
                    "content": [
                        {
                            "__typename": "Image",
                            "imageUUID": "20000000-0000-4000-8000-000000000a01",
                            "eventDate": "2025-06-15T10:00:00+00:00",
                            "entityReferenceId": "99000001",
                            "versionedUrls": [
                                {
                                    "version": "MEDIUM_FEED",
                                    "url": "https://example.invalid/x-mdfd.jpeg?sig=t",
                                }
                            ],
                        }
                    ],
                },
            }
        }
    }
    fake_api.get_dive_photos = AsyncMock(return_value=photos_resp)
    fake_api.get_activity = AsyncMock(return_value={"metadataDTO": {"activityImages": []}})

    cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")
    cache.download_records = AsyncMock(  # type: ignore[assignment]
        return_value={"20000000-0000-4000-8000-000000000a01": {"medium"}}
    )

    data = await build_data(
        api=fake_api,
        current_user_date="2026-05-03",
        previous_gear_last_modified={},
        photo_cache=cache,
        http_session=MagicMock(),
        profile_id=999000111,
        year=2026,
    )
    # Only the dives the GraphQL pass DIDN'T cover should be fallback-fetched.
    fallback_aids = {call.kwargs["activity_id"] for call in fake_api.get_activity.call_args_list}
    assert 99000001 not in fallback_aids
    # Telemetry confirms the dive matched via activity-id.
    assert data.photo_stats.matched_by_activity_id == 1


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
