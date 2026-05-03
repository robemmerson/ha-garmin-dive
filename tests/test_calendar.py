"""Tests for the Garmin Dive calendar entity."""

from __future__ import annotations

from datetime import UTC, datetime

from custom_components.garmin_dive.calendar import GarminDiveCalendarEntity
from tests.conftest_helpers import make_data, make_fake_coordinator


async def test_calendar_event_for_each_dive(hass, load_fixture):
    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    cal = GarminDiveCalendarEntity(coord)

    start = datetime(2025, 6, 13, 0, 0, tzinfo=UTC)
    end = datetime(2025, 6, 16, 0, 0, tzinfo=UTC)
    events = await cal.async_get_events(hass, start, end)

    assert len(events) == 3
    e = next(ev for ev in events if "Alpha" in ev.summary)
    assert "Max depth" in e.description
    assert e.location == "UTC"


async def test_calendar_next_event(hass, load_fixture):
    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    cal = GarminDiveCalendarEntity(coord)
    # `event` returns the soonest upcoming or most-recent past event.
    assert cal.event is not None
