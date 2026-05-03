"""Helpers for building a coordinator with a fake CoordinatorData."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from custom_components.garmin_dive.coordinator import (
    CoordinatorData,
    Dive,
    DiveDevice,
    GearItem,
)
from custom_components.garmin_dive.gear import GearSnapshot


def make_fake_coordinator(
    *,
    hass,
    profile_id: int = 999000111,
    profile_display_name: str = "test-user",
    data: CoordinatorData | None = None,
) -> Any:
    coord = MagicMock()
    coord.hass = hass
    coord.async_add_listener = MagicMock(return_value=lambda: None)
    coord.last_update_success = True
    auth = MagicMock()
    auth.profile_id = profile_id
    auth.profile_display_name = profile_display_name
    coord._auth = auth
    coord.data = data
    return coord


def make_data(
    *,
    summary: dict[str, Any],
    devices: list[dict[str, Any]] | None = None,
    tags: dict[str, int] | None = None,
    gear_summary: list[dict[str, Any]] | None = None,
    gear_details: dict[int, dict[str, Any]] | None = None,
) -> CoordinatorData:
    devices = devices or []
    tags = tags or {}
    gear_summary = gear_summary or []
    gear_details = gear_details or {}
    return CoordinatorData(
        total_dives=int(summary["totalCount"]),
        dives=[Dive(raw=d) for d in summary["diveActivities"]],
        devices=[DiveDevice(raw=d) for d in devices],
        dive_tags=tags,
        gear=[
            GearItem(summary_raw=g, detail_raw=gear_details.get(int(g["gearId"])))
            for g in gear_summary
        ],
        gear_snapshot=GearSnapshot(),
    )
