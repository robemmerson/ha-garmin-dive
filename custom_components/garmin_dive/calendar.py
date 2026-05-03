"""Calendar entity exposing each dive as a calendar event."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import GarminDiveAccountEntity

if TYPE_CHECKING:
    from .coordinator import Dive, GarminDiveCoordinator


def _dive_to_event(d: Dive) -> CalendarEvent:
    raw = d.raw
    start = datetime.fromisoformat(raw["startTime"])
    end = start + timedelta(seconds=float(raw["totalTime"]))
    description_lines = [
        f"Max depth: {raw.get('maxDepth')} m",
        f"Bottom time: {round((raw.get('bottomTime') or 0) / 60)} min",
        f"Total time: {round((raw.get('totalTime') or 0) / 60)} min",
    ]
    if raw.get("diveTags"):
        description_lines.append("Tags: " + ", ".join(raw["diveTags"]))
    if cid := raw.get("connectActivityId"):
        description_lines.append(
            f"Garmin Connect: https://connect.garmin.com/modern/activity/{cid}"
        )
    return CalendarEvent(
        start=start,
        end=end,
        summary=raw["name"],
        description="\n".join(description_lines),
        location=raw.get("timezone") or "",
    )


class GarminDiveCalendarEntity(GarminDiveAccountEntity, CalendarEntity):
    _attr_translation_key = "dives"
    _attr_icon = "mdi:calendar-blank-outline"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_calendar_dives"

    @property
    def event(self) -> CalendarEvent | None:
        if not self.coordinator.data or not self.coordinator.data.dives:
            return None
        return _dive_to_event(self.coordinator.data.dives[0])

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        if not self.coordinator.data:
            return []
        result: list[CalendarEvent] = []
        for d in self.coordinator.data.dives:
            ev = _dive_to_event(d)
            if ev.end >= start_date and ev.start <= end_date:
                result.append(ev)
        return result


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GarminDiveCoordinator = entry.runtime_data
    async_add_entities([GarminDiveCalendarEntity(coordinator)])
