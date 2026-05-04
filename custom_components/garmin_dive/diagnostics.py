"""Diagnostics for Garmin Dive — redacts every token and PII field."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

REDACT = {
    "dive_access_token",
    "dive_refresh_token",
    "session_path",
    "profile_id",
    "userName",
    "garminGUID",
    "displayName",
    "fullName",
    "email",
    "password",
    "url",  # signed S3 URLs
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coord = entry.runtime_data
    snapshot: dict[str, Any] = {"entry_data": async_redact_data(dict(entry.data), REDACT)}
    if coord and coord.data:
        snapshot["data"] = {
            "total_dives": coord.data.total_dives,
            "dives_count": len(coord.data.dives),
            "devices_count": len(coord.data.devices),
            "gear_count": len(coord.data.gear),
            "tags": coord.data.dive_tags,
        }
        ps = coord.data.photo_stats
        snapshot["photos"] = {
            "images_returned": ps.images_returned,
            "videos_returned": ps.videos_returned,
            "other_returned": ps.other_returned,
            "matched_dives": ps.matched_dives,
            "unmatched_event_dates": ps.unmatched_event_dates,
            "download_failures": ps.download_failures,
            "per_dive": [
                {
                    "id": d.id,
                    "start_time": d.start_time,
                    "photo_count": d.photo_count,
                    "has_thumb_url": d.photos.get("thumb") is not None,
                    "has_medium_url": d.photos.get("medium") is not None,
                    "has_large_url": d.photos.get("large") is not None,
                }
                for d in coord.data.dives
            ],
        }
    return snapshot
