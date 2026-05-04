"""DataUpdateCoordinator for ha-garmin-dive (DTO + build_data orchestration)."""

from __future__ import annotations

import asyncio
import contextlib
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
    # Every photo bound to this dive, oldest-first. `photos` is the cover
    # (== photos_all[0] when populated) and stays for dashboards built on
    # the original single-photo shape.
    photos_all: list[dict[str, str | None]] = field(default_factory=list)
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

    @property
    def connect_activity_id(self) -> int | None:
        v = self.raw.get("connectActivityId")
        return int(v) if v is not None else None


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
    matched_by_activity_id: int = 0
    matched_by_event_date: int = 0
    unmatched_event_dates: list[str] = field(default_factory=list)
    download_failures: list[str] = field(default_factory=list)
    activity_fallback_attempted: int = 0
    activity_fallback_matched: int = 0
    activity_fallback_errors: list[str] = field(default_factory=list)


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
        await _run_photo_pipeline(
            api=api,
            dives=dives,
            gear_items=gear_items,
            photo_cache=photo_cache,
            http_session=http_session,
            profile_id=profile_id,
            year=year,
            stats=photo_stats,
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


@dataclass(slots=True)
class _PhotoIndex:
    """Photo records grouped both by activity-id and by eventDate.

    Activity-id matching is used first because `entityReferenceId` ↔
    `connectActivityId` is a stable integer join — no timezone-format
    fragility. eventDate is the historical fallback for the small subset of
    photos that don't carry `entityReferenceId`.
    """

    by_activity: dict[int, list[PhotoRecord]] = field(default_factory=dict)
    by_event: dict[str, list[PhotoRecord]] = field(default_factory=dict)


async def _run_photo_pipeline(
    *,
    api: GarminDiveClient,
    dives: list[Dive],
    gear_items: list[GearItem],
    photo_cache: PhotoCache,
    http_session: Any,
    profile_id: int | None,
    year: int | None,
    stats: PhotoStats,
) -> None:
    """End-to-end: GraphQL → activity-service fallback → cache → bind."""
    photo_index = _PhotoIndex()
    if profile_id is not None and year is not None:
        try:
            photos_resp = await api.get_dive_photos(profile_id=profile_id, year=year)
            photo_index = _build_dive_photo_index(photos_resp, stats=stats)
        except Exception as err:  # pragma: no cover - logged
            _LOGGER.warning("Dive-photos GraphQL call failed: %s", err)

    # Per-activity REST fallback for dives the GraphQL pass missed.
    # Garmin's two photo services have inconsistent coverage, so for any dive
    # still without a record we fetch /activity-service/activity/{id} once
    # per refresh and ingest its activityImages[] inline.
    await _augment_with_activity_fallback(api=api, dives=dives, index=photo_index, stats=stats)

    records: list[PhotoRecord] = list(_collect_gear_photo_records(gear_items))
    seen_uuids: set[str] = set()
    for recs in (*photo_index.by_activity.values(), *photo_index.by_event.values()):
        for r in recs:
            if r.image_uuid in seen_uuids:
                continue
            seen_uuids.add(r.image_uuid)
            records.append(r)
    cached_by_uuid: dict[str, set[str]] = {}
    if records:
        cached_by_uuid = await photo_cache.download_records(records, session=http_session)
        _attach_local_urls(gear_items, photo_cache, cached_by_uuid)
        stats.download_failures = sorted(
            uuid for uuid, sizes in cached_by_uuid.items() if not sizes
        )
    _attach_dive_photos(dives, photo_index, photo_cache, cached_by_uuid, stats=stats)
    _LOGGER.info(
        "Garmin Dive photos: returned=%d images / %d videos / %d other; "
        "matched=%d dives (by_activity=%d, by_event=%d); "
        "fallback attempted=%d matched=%d errors=%d; "
        "unmatched event_dates=%d; download_failures=%d",
        stats.images_returned,
        stats.videos_returned,
        stats.other_returned,
        stats.matched_dives,
        stats.matched_by_activity_id,
        stats.matched_by_event_date,
        stats.activity_fallback_attempted,
        stats.activity_fallback_matched,
        len(stats.activity_fallback_errors),
        len(stats.unmatched_event_dates),
        len(stats.download_failures),
    )


async def _augment_with_activity_fallback(
    *,
    api: GarminDiveClient,
    dives: list[Dive],
    index: _PhotoIndex,
    stats: PhotoStats,
) -> None:
    """For dives the GraphQL pass didn't touch, fetch the per-activity REST
    payload and ingest its `metadataDTO.activityImages[]`.

    One HTTP call per missed dive, fired in parallel. Per-dive failures are
    swallowed so a single 5xx never aborts the whole refresh; the failing
    activity ID is recorded in `stats.activity_fallback_errors` for
    diagnostics. We will retry on the next coordinator cycle.
    """
    targets = _select_fallback_targets(dives, index)
    if not targets:
        return
    stats.activity_fallback_attempted = len(targets)
    results = await asyncio.gather(
        *(api.get_activity(activity_id=d.connect_activity_id) for d in targets),  # type: ignore[arg-type]
        return_exceptions=True,
    )
    for dive, result in zip(targets, results, strict=True):
        _ingest_activity_fallback_result(dive, result, index, stats)


def _select_fallback_targets(dives: list[Dive], index: _PhotoIndex) -> list[Dive]:
    parsed_events: set[datetime] = set()
    for ev_str in index.by_event:
        try:
            parsed_events.add(datetime.fromisoformat(ev_str))
        except ValueError:
            continue
    targets: list[Dive] = []
    for dive in dives:
        aid = dive.connect_activity_id
        if aid is None or aid in index.by_activity:
            continue
        try:
            dive_dt: datetime | None = datetime.fromisoformat(dive.start_time)
        except ValueError:
            dive_dt = None
        if dive_dt is not None and dive_dt in parsed_events:
            continue  # GraphQL eventDate index already covers this dive
        targets.append(dive)
    return targets


def _ingest_activity_fallback_result(
    dive: Dive,
    result: Any,
    index: _PhotoIndex,
    stats: PhotoStats,
) -> None:
    if isinstance(result, BaseException):
        _LOGGER.warning(
            "Activity-service fallback failed for activity %s: %s",
            dive.connect_activity_id,
            result,
        )
        if dive.connect_activity_id is not None:
            stats.activity_fallback_errors.append(str(dive.connect_activity_id))
        return
    images = (((result or {}).get("metadataDTO") or {}).get("activityImages")) or []
    records = [PhotoRecord.from_activity_image(img) for img in images if img.get("imageId")]
    if not records:
        return
    if dive.connect_activity_id is not None:
        index.by_activity[dive.connect_activity_id] = records
    stats.activity_fallback_matched += 1


def _build_dive_photo_index(graphql_resp: dict[str, Any], *, stats: PhotoStats) -> _PhotoIndex:
    """Group GraphQL photo records into the two indexes used by the matcher.

    Records skipped/non-Image entries are folded into `stats` so callers can
    surface per-refresh telemetry.
    """
    index = _PhotoIndex()
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
        if not item.get("imageUUID"):
            continue
        record = PhotoRecord.from_garmin_image(item)
        ref_id = item.get("entityReferenceId")
        if ref_id is not None:
            # Non-numeric entityReferenceId falls through to the eventDate
            # index without complaint.
            with contextlib.suppress(TypeError, ValueError):
                index.by_activity.setdefault(int(ref_id), []).append(record)
        event_date = item.get("eventDate")
        if event_date:
            index.by_event.setdefault(event_date, []).append(record)
    return index


def _attach_dive_photos(
    dives: list[Dive],
    index: _PhotoIndex,
    cache: PhotoCache,
    cached_by_uuid: dict[str, set[str]],
    *,
    stats: PhotoStats,
) -> None:
    """Attach local URLs for every matched & cached photo on each dive.

    Match strategy:
      1. `entityReferenceId == connectActivityId` (integer equality, stable).
      2. Fall back to `eventDate == startTime` parsed as datetime.

    Every record matched this way gets surfaced on `dive.photos_all`. The
    first one with bytes on disk is also pinned as `dive.photos` (the
    cover, kept for dashboards built on the original single-photo shape).
    `dive.photo_count` reflects the total matched count — even if some
    sizes haven't been downloaded yet.
    """
    parsed_events: dict[datetime, str] = {}
    for ev_str in index.by_event:
        try:
            parsed_events[datetime.fromisoformat(ev_str)] = ev_str
        except ValueError:
            continue
    matched_event_dates: set[str] = set()
    for dive in dives:
        records: list[PhotoRecord] = []
        if dive.connect_activity_id is not None:
            recs = index.by_activity.get(dive.connect_activity_id)
            if recs:
                records = recs
                stats.matched_by_activity_id += 1
        if not records:
            try:
                dive_dt = datetime.fromisoformat(dive.start_time)
            except ValueError:
                dive_dt = None
            if dive_dt is not None:
                matched_ev = parsed_events.get(dive_dt)
                if matched_ev is not None:
                    matched_event_dates.add(matched_ev)
                    records = index.by_event[matched_ev]
                    if records:
                        stats.matched_by_event_date += 1
        if records:
            _bind_records_to_dive(dive, records, cache, cached_by_uuid)
    stats.matched_dives = sum(1 for d in dives if d.photo_count > 0)
    stats.unmatched_event_dates = sorted(set(index.by_event) - matched_event_dates)


def _bind_records_to_dive(
    dive: Dive,
    records: list[PhotoRecord],
    cache: PhotoCache,
    cached_by_uuid: dict[str, set[str]],
) -> None:
    """Set `dive.photos_all` (every record) and `dive.photos` (cover)."""
    dive.photo_count = len(records)
    all_urls: list[dict[str, str | None]] = []
    cover: dict[str, str | None] | None = None
    for record in records:
        cached_sizes = cached_by_uuid.get(record.image_uuid, set())
        urls: dict[str, str | None] = _empty_photos()
        for size in ("thumb", "medium", "large"):
            if size not in cached_sizes:
                continue
            entry = record.urls.get(size)
            if entry is None:
                continue
            _, ext = entry
            urls[size] = cache.local_url(image_uuid=record.image_uuid, size=size, ext=ext)
        all_urls.append(urls)
        if cover is None and any(urls.values()):
            cover = urls
    dive.photos_all = all_urls
    if cover is not None:
        dive.photos = cover


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
