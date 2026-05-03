"""DataUpdateCoordinator for ha-garmin-dive (DTO + build_data orchestration)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .gear import GearSnapshot, needs_detail_fetch

if TYPE_CHECKING:
    from .api import GarminDiveClient


@dataclass(slots=True)
class Dive:
    raw: dict[str, Any]

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
class CoordinatorData:
    total_dives: int
    dives: list[Dive]
    devices: list[DiveDevice]
    dive_tags: dict[str, int]
    gear: list[GearItem]
    gear_snapshot: GearSnapshot = field(default_factory=GearSnapshot)


async def build_data(
    *,
    api: GarminDiveClient,
    current_user_date: str,
    previous_gear_last_modified: dict[int, str],
    results_per_page: int = 100,
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

    # Conditional gear-detail fetches.
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
                continue
            detail_by_id[int(result["gearId"])] = result

    gear_items = [
        GearItem(
            summary_raw=item,
            detail_raw=detail_by_id.get(int(item["gearId"])),
        )
        for item in gear_summary
    ]

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
        dives=[Dive(raw=d) for d in summary["diveActivities"]],
        devices=[DiveDevice(raw=d) for d in devices_raw],
        dive_tags=tags,
        gear=gear_items,
        gear_snapshot=snapshot,
    )
