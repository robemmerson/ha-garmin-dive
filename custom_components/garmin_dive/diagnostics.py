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
    return snapshot
