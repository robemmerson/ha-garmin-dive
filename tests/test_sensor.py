"""Tests for account-level sensors."""

from __future__ import annotations

import pytest
from freezegun import freeze_time

from custom_components.garmin_dive.sensor import (
    CurrentYearDivesSensor,
    DiveLogYearSensor,
    DivesByTagSensor,
    GearCountSensor,
    LastDiveMaxDepthSensor,
    LastDiveSensor,
    TotalDivesSensor,
)
from tests.conftest_helpers import make_data, make_fake_coordinator


@freeze_time("2026-05-03T12:00:00")
async def test_last_dive_state_and_attributes(hass, load_fixture):
    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = LastDiveSensor(coord)

    assert sensor.native_value == "Elphinstone (South side)"
    attrs = sensor.extra_state_attributes
    assert attrs["max_depth"] == pytest.approx(26.373)
    assert attrs["bottom_time_minutes"] == pytest.approx(2747.59 / 60)
    assert attrs["connect_url"] == "https://connect.garmin.com/modern/activity/20180546488"


async def test_total_and_current_year_dives(hass, load_fixture):
    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    assert TotalDivesSensor(coord).native_value == 68
    # All fixture dives are in 2025; current year (frozen 2026-05-03) is 2026 -> 0.
    with freeze_time("2026-05-03"):
        assert CurrentYearDivesSensor(coord).native_value == 0


async def test_last_dive_depth_uses_distance_device_class(hass, load_fixture):
    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = LastDiveMaxDepthSensor(coord)
    assert sensor.native_value == pytest.approx(26.373)
    assert sensor.device_class == "distance"
    assert sensor.native_unit_of_measurement == "m"


async def test_handles_empty_dive_list(hass):
    data = make_data(summary={"totalCount": 0, "diveActivities": []})
    coord = make_fake_coordinator(hass=hass, data=data)
    assert LastDiveSensor(coord).native_value is None
    assert TotalDivesSensor(coord).native_value == 0


async def test_dive_log_year_attribute_shape(hass, load_fixture):
    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = DiveLogYearSensor(coord)

    attrs = sensor.extra_state_attributes
    dives = attrs["dives"]
    assert len(dives) == 3
    first = dives[0]
    assert {
        "id",
        "name",
        "start",
        "end",
        "timezone",
        "max_depth",
        "average_depth",
        "bottom_time",
        "total_time",
        "surface_interval",
        "tags",
        "gases",
        "location",
        "photos",
        "connect_url",
        "dive_computer",
    } <= set(first.keys())
    assert first["connect_url"] == "https://connect.garmin.com/modern/activity/20180546488"
    # average_depth is unknown today (spec §13) -> None.
    assert first["average_depth"] is None


async def test_dives_by_tag_state_and_attrs(hass, load_fixture):
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        tags=load_fixture("dive_tags"),
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = DivesByTagSensor(coord)
    assert sensor.native_value == 45 + 34 + 8 + 5 + 3 + 3 + 1
    assert sensor.extra_state_attributes["RECREATIONAL"] == 45


async def test_gear_count_state_and_breakdown(hass, load_fixture):
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = GearCountSensor(coord)
    assert sensor.native_value == 3
    breakdown = sensor.extra_state_attributes["by_type"]
    assert breakdown["REGULATOR"] == 1
    assert breakdown["LIGHT"] == 1
    assert breakdown["CERTIFICATION"] == 1
