"""Tests for account-level sensors."""

from __future__ import annotations

import pytest
from freezegun import freeze_time

from custom_components.garmin_dive.sensor import (
    CurrentYearDivesSensor,
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
