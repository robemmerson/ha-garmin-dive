"""DataUpdateCoordinator for ha-garmin-dive (DTO + build_data orchestration)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, EVENT_NEW_DIVE, EVENT_SERVICE_DUE
from .gear import GearSnapshot, detect_service_status_flips, needs_detail_fetch
from .photos import PhotoCache, PhotoRecord

if TYPE_CHECKING:
    from .api import GarminDiveClient

_LOGGER = logging.getLogger(__name__)


def _empty_photos() -> dict[str, str | None]:
    return {"thumb": None, "medium": None, "large": None}


@dataclass(slots=True)
class Dive:
    raw: dict[str, Any]
    photos: dict[str, str | None] = field(default_factory=_empty_photos)
    photo_count: int = 0

    @property
    def id(self) -> int:
        return int(self.raw["id"])

    @property
    def name(self) -> str:
        return self.raw["name"]

    @property
    def start_time(self) -> str:
        return self.raw["startTime"]

    @property
    def total_time_seconds(self) -> float:
        return float(self.raw["totalTime"])

    @property
    def max_depth(self) -> float:
        return float(self.raw["maxDepth"])


@dataclass(slots=True)
class DiveDevice:
    raw: dict[str, Any]

    @property
    def product_display_name(self) -> str:
        return self.raw["productDisplayName"]

    @property
    def serial_number(self) -> int | None:
        sn = self.raw.get("serialNumber")
        return int(sn) if sn is not None else None

    @property
    def device_type(self) -> str:
        return self.raw["type"]


@dataclass(slots=True)
class GearItem:
    summary_raw: dict[str, Any]
    detail_raw: dict[str, Any] | None = None
    photo_local_url: str | None = None
    photo_thumb_url: str | None = None

    @property
    def gear_id(self) -> int:
        return int(self.summary_raw["gearId"])

    @property
    def name(self) -> str:
        return self.summary_raw["name"]

    @property
    def gear_type(self) -> str:
        return self.summary_raw["type"]

    @property
    def due_indicator(self) -> str | None:
        if self.detail_raw is not None:
            return self.detail_raw.get("dueIndicator")
        return self.summary_raw.get("dueIndicator")


@dataclass(slots=True)
class PhotoStats:
    """Per-refresh telemetry for the dive-photo pipeline (debug visibility)."""

    images_returned: int = 0
    videos_returned: int = 0
    other_returned: int = 0
    matched_dives: int = 0
    unmatched_event_dates: list[str] = field(default_factory=list)
    download_failures: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CoordinatorData:
    total_dives: int
    dives: list[Dive]
    devices: list[DiveDevice]
    dive_tags: dict[str, int]
    gear: list[GearItem]
    gear_snapshot: GearSnapshot = field(default_factory=GearSnapshot)
    photo_stats: PhotoStats = field(default_factory=PhotoStats)


async def build_data(
    *,
    api: GarminDiveClient,
    current_user_date: str,
    previous_gear_last_modified: dict[int, str],
    results_per_page: int = 100,
    photo_cache: PhotoCache | None = None,
    http_session: Any | None = None,
    profile_id: int | None = None,
    year: int | None = None,
) -> CoordinatorData:
    """One refresh cycle: fan out concurrent calls and assemble CoordinatorData."""
    # Fan out the 4 unconditional calls in parallel.
    summary_task = api.get_dive_summary(page=0, results_per_page=results_per_page)
    devices_task = api.get_dive_devices()
    tags_task = api.get_dive_tags()
    gear_summary_task = api.get_gear_summary(current_user_date=current_user_date)
    summary, devices_raw, tags, gear_summary = await asyncio.gather(
        summary_task, devices_task, tags_task, gear_summary_task
    )

    # Conditional gear-detail fetches. Per-item failures are tolerated so that
    # a transient 5xx on one gear item does not abort the whole refresh cycle.
    to_fetch = needs_detail_fetch(gear_summary, previous=previous_gear_last_modified)
    detail_by_id: dict[int, dict[str, Any]] = {}
    if to_fetch:
        raw_results = await asyncio.gather(
            *(
                api.get_gear_detail(gear_id=gid, current_user_date=current_user_date)
                for gid in to_fetch
            ),
            return_exceptions=True,
        )
        for result in raw_results:
            if isinstance(result, BaseException):
                _LOGGER.warning("gear-detail fetch failed: %s", result)
                continue
            detail_by_id[int(result["gearId"])] = result

    gear_items = [
        GearItem(
            summary_raw=item,
            detail_raw=detail_by_id.get(int(item["gearId"])),
        )
        for item in gear_summary
    ]
    dives = [Dive(raw=d) for d in summary["diveActivities"]]

    # Photo collection (optional path)
    photo_stats = PhotoStats()
    if photo_cache is not None and http_session is not None:
        records = list(_collect_gear_photo_records(gear_items))
        photos_by_event: dict[str, list[PhotoRecord]] = {}
        if profile_id is not None and year is not None:
            try:
                photos_resp = await api.get_dive_photos(profile_id=profile_id, year=year)
                photos_by_event = _build_dive_photo_index(photos_resp, stats=photo_stats)
                for recs in photos_by_event.values():
                    records.extend(recs)
            except Exception as err:  # pragma: no cover - logged
                _LOGGER.warning("Dive-photos GraphQL call failed: %s", err)
        cached_by_uuid: dict[str, set[str]] = {}
        if records:
            cached_by_uuid = await photo_cache.download_records(records, session=http_session)
            _attach_local_urls(gear_items, photo_cache, cached_by_uuid)
            photo_stats.download_failures = sorted(
                uuid for uuid, sizes in cached_by_uuid.items() if not sizes
            )
        if photos_by_event:
            _attach_dive_photos(
                dives, photos_by_event, photo_cache, cached_by_uuid, stats=photo_stats
            )
        _LOGGER.info(
            "Garmin Dive photos: returned=%d images / %d videos / %d other; "
            "matched=%d dives; unmatched event_dates=%d; download_failures=%d",
            photo_stats.images_returned,
            photo_stats.videos_returned,
            photo_stats.other_returned,
            photo_stats.matched_dives,
            len(photo_stats.unmatched_event_dates),
            len(photo_stats.download_failures),
        )

    # Capture the snapshot used as `previous` on the next cycle.
    snapshot = GearSnapshot(
        last_modified={
            int(g["gearId"]): g.get("lastModifiedTs", "")
            for g in gear_summary
            if "lastModifiedTs" in g
        },
        due_indicators={g.gear_id: ind for g in gear_items if (ind := g.due_indicator) is not None},
    )

    return CoordinatorData(
        total_dives=int(summary["totalCount"]),
        dives=dives,
        devices=[DiveDevice(raw=d) for d in devices_raw],
        dive_tags=tags,
        gear=gear_items,
        gear_snapshot=snapshot,
        photo_stats=photo_stats,
    )


def _collect_gear_photo_records(gear_items: list[GearItem]) -> Iterator[PhotoRecord]:
    for g in gear_items:
        # Summary-level image (single)
        img = g.summary_raw.get("image")
        if img:
            yield PhotoRecord.from_garmin_image(img)
        # Detail-level images (list of images)
        if g.detail_raw is not None:
            for img in g.detail_raw.get("media", {}).get("images", []) or []:
                yield PhotoRecord.from_garmin_image(img)


def _build_dive_photo_index(
    graphql_resp: dict[str, Any], *, stats: PhotoStats
) -> dict[str, list[PhotoRecord]]:
    """Group dive photos by `eventDate` (matches each dive's `startTime`).

    Records skipped/non-Image entries are folded into `stats` so callers can
    surface per-refresh telemetry.
    """
    by_event: dict[str, list[PhotoRecord]] = {}
    items = (
        graphql_resp.get("data", {}).get("playerProfile", {}).get("medias", {}).get("content") or []
    )
    for item in items:
        typename = item.get("__typename")
        if typename == "Image":
            stats.images_returned += 1
        elif typename == "Video":
            stats.videos_returned += 1
            continue
        else:
            stats.other_returned += 1
            continue
        event_date = item.get("eventDate")
        if not event_date or not item.get("imageUUID"):
            continue
        by_event.setdefault(event_date, []).append(PhotoRecord.from_garmin_image(item))
    return by_event


def _attach_dive_photos(
    dives: list[Dive],
    by_event: dict[str, list[PhotoRecord]],
    cache: PhotoCache,
    cached_by_uuid: dict[str, set[str]],
    *,
    stats: PhotoStats,
) -> None:
    """Attach local URLs for the first cached photo of each matching dive.

    Matching is on parsed datetimes so equivalent ISO strings (e.g. `+0300`
    vs `+03:00`) still match. URLs are only surfaced for sizes that are
    actually on disk, so the dashboard never gets a 404'ing `<img>` src.
    `dive.photo_count` reflects the matched-photo count regardless.
    """
    parsed_events: dict[datetime, str] = {}
    for ev_str in by_event:
        try:
            parsed_events[datetime.fromisoformat(ev_str)] = ev_str
        except ValueError:
            continue
    matched_event_dates: set[str] = set()
    for dive in dives:
        try:
            dive_dt = datetime.fromisoformat(dive.start_time)
        except ValueError:
            continue
        match = parsed_events.get(dive_dt)
        if match is None:
            continue
        matched_event_dates.add(match)
        records = by_event[match]
        if not records:
            continue
        dive.photo_count = len(records)
        # Pick the first record that has *any* size cached on disk so the
        # dashboard has a real URL to render.
        renderable = next(
            (r for r in records if cached_by_uuid.get(r.image_uuid)),
            None,
        )
        if renderable is None:
            continue
        cached_sizes = cached_by_uuid[renderable.image_uuid]
        urls: dict[str, str | None] = _empty_photos()
        for size in ("thumb", "medium", "large"):
            if size not in cached_sizes:
                continue
            entry = renderable.urls.get(size)
            if entry is None:
                continue
            _, ext = entry
            urls[size] = cache.local_url(image_uuid=renderable.image_uuid, size=size, ext=ext)
        dive.photos = urls
    stats.matched_dives = sum(1 for d in dives if d.photo_count > 0)
    stats.unmatched_event_dates = sorted(set(by_event) - matched_event_dates)


def _attach_local_urls(
    gear_items: list[GearItem],
    cache: PhotoCache,
    cached_by_uuid: dict[str, set[str]],
) -> None:
    for g in gear_items:
        img = g.summary_raw.get("image") or _first_image(g.detail_raw)
        if not img:
            continue
        record = PhotoRecord.from_garmin_image(img)
        cached_sizes = cached_by_uuid.get(record.image_uuid, set())
        if "medium" in record.urls and "medium" in cached_sizes:
            _, ext = record.urls["medium"]
            g.photo_local_url = cache.local_url(
                image_uuid=record.image_uuid, size="medium", ext=ext
            )
        if "thumb" in record.urls and "thumb" in cached_sizes:
            _, ext = record.urls["thumb"]
            g.photo_thumb_url = cache.local_url(image_uuid=record.image_uuid, size="thumb", ext=ext)


def _first_image(detail: dict[str, Any] | None) -> dict[str, Any] | None:
    if not detail:
        return None
    images = detail.get("media", {}).get("images") or []
    return images[0] if images else None


class GarminDiveCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Per-account refresh loop for the integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        api: GarminDiveClient,
        auth: Any,
        photo_cache: PhotoCache | None,
        http_session: Any,
        scan_interval_minutes: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self._api = api
        self._auth = auth
        self._photo_cache = photo_cache
        self._http_session = http_session
        self._known_dive_ids: set[int] = set()
        self._previous_due_indicators: dict[int, str] = {}
        self._previous_gear_last_modified: dict[int, str] = {}
        # Public: read by NewDiveAvailableBinarySensor and written by the
        # garmin_dive.acknowledge_new_dive service. Volatile — not persisted
        # across HA restarts in v0.1.
        self.latest_dive_acknowledged_id: int | None = None

    async def _async_update_data(self) -> CoordinatorData:
        try:
            data = await build_data(
                api=self._api,
                current_user_date=date.today().isoformat(),
                previous_gear_last_modified=self._previous_gear_last_modified,
                photo_cache=self._photo_cache,
                http_session=self._http_session,
                profile_id=self._auth.profile_id,
                year=date.today().year,
            )
        except Exception as err:
            raise UpdateFailed(f"Garmin Dive refresh failed: {err}") from err

        self._fire_event_diffs(data)
        self._previous_gear_last_modified = dict(data.gear_snapshot.last_modified)
        self._previous_due_indicators = dict(data.gear_snapshot.due_indicators)
        self._known_dive_ids = {d.id for d in data.dives}
        return data

    def _fire_event_diffs(self, data: CoordinatorData) -> None:
        # New dives — only fire if we had a prior set (skip first run)
        for dive in data.dives:
            if dive.id not in self._known_dive_ids and self._known_dive_ids:
                self.hass.bus.async_fire(
                    EVENT_NEW_DIVE,
                    {
                        "account_id": str(self._auth.profile_id),
                        "profile_id": self._auth.profile_id,
                        "dive": dive.raw,
                    },
                )

        # Service-due transitions
        if not self._previous_due_indicators:
            return  # don't fire on first run
        flips = detect_service_status_flips(
            self._previous_due_indicators, data.gear_snapshot.due_indicators
        )
        for gear_id, indicator in flips.items():
            gear = next((g for g in data.gear if g.gear_id == gear_id), None)
            if gear is not None:
                self.hass.bus.async_fire(
                    EVENT_SERVICE_DUE,
                    {
                        "account_id": str(self._auth.profile_id),
                        "profile_id": self._auth.profile_id,
                        "gear": gear.summary_raw,
                        "indicator": indicator,
                    },
                )
