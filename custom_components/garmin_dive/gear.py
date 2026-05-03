"""Pure helpers for gear list parsing, change detection, and derived fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .const import SERVICEABLE_GEAR_TYPES


@dataclass(slots=True)
class GearSnapshot:
    """A small persistent slice of gear state used for cycle-to-cycle diffs."""

    last_modified: dict[int, str] = field(default_factory=dict)
    due_indicators: dict[int, str] = field(default_factory=dict)


def needs_detail_fetch(summary: list[dict[str, Any]], *, previous: dict[int, str]) -> set[int]:
    """Return gear IDs whose detail should be fetched this cycle.

    A gear item needs detail re-fetch when:
      - it's new (not in `previous`), OR
      - its `lastModifiedTs` changed, OR
      - the summary entry doesn't carry `lastModifiedTs` at all (defensive
        fallback for an API change; see spec §13).
    """
    changed: set[int] = set()
    for item in summary:
        gid = int(item["gearId"])
        ts = item.get("lastModifiedTs")
        if ts is None or previous.get(gid) != ts:
            changed.add(gid)
    return changed


def detect_service_status_flips(
    previous: dict[int, str], current: dict[int, str]
) -> dict[int, str]:
    """Return gear IDs whose due indicator just transitioned to DUE or OVERDUE."""
    flips: dict[int, str] = {}
    for gid, indicator in current.items():
        if indicator not in {"DUE", "OVERDUE"}:
            continue
        if previous.get(gid) != indicator:
            flips[gid] = indicator
    return flips


def is_serviceable(gear_type: str) -> bool:
    return gear_type in SERVICEABLE_GEAR_TYPES


def days_until_service(*, next_service_date: str | None, today: date) -> int | None:
    if not next_service_date:
        return None
    target = date.fromisoformat(next_service_date)
    return (target - today).days
