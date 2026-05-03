"""Tests for account-level sensors."""

from __future__ import annotations

import pytest
from freezegun import freeze_time

from custom_components.garmin_dive.sensor import (
    CurrentYearDivesSensor,
    DiveLogYearSensor,
    DivesByTagSensor,
    GearCountSensor,
    GearDaysUntilServiceSensor,
    GearServiceStatusSensor,
    LastDiveMaxDepthSensor,
    LastDiveSensor,
    TotalDivesSensor,
    build_dive_computer_entities,
    build_gear_entities,
)
from tests.conftest_helpers import make_data, make_fake_coordinator


@freeze_time("2026-05-03T12:00:00")
async def test_last_dive_state_and_attributes(hass, load_fixture):
    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = LastDiveSensor(coord)

    assert sensor.native_value == "Test Site Alpha"
    attrs = sensor.extra_state_attributes
    assert attrs["max_depth"] == pytest.approx(26.373)
    assert attrs["bottom_time_minutes"] == pytest.approx(2747.59 / 60)
    assert attrs["connect_url"] == "https://connect.garmin.com/modern/activity/99000001"


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


@freeze_time("2026-05-03T12:00:00")
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
        "photo_count",
        "connect_url",
        "dive_computer",
    } <= set(first.keys())
    assert first["photos"] == {"thumb": None, "medium": None, "large": None}
    assert first["photo_count"] == 0
    assert first["connect_url"] == "https://connect.garmin.com/modern/activity/99000001"
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


async def test_per_gear_sensors(hass, load_fixture):
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
        gear_details={
            141548: load_fixture("gear_detail_regulator"),
            247811: load_fixture("gear_detail_light"),
        },
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    entities = build_gear_entities(coord)
    by_id = {(e.unique_id, type(e).__name__) for e in entities}
    assert any(uid.endswith("_141548_service_status") for uid, _ in by_id)
    # Light is non-serviceable -> no service_status sensor.
    assert not any(uid.endswith("_247811_service_status") for uid, _ in by_id)


async def test_gear_service_status_returns_due_indicator(hass, load_fixture):
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
        gear_details={141548: load_fixture("gear_detail_regulator")},
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = GearServiceStatusSensor(coord, gear_id=141548)
    assert sensor.native_value == "not_due"


@pytest.mark.parametrize(
    ("indicator", "expected"),
    [
        ("NOT_DUE", "not_due"),
        ("DUE", "due"),
        ("DUE_SOON", "due"),
        ("OVERDUE", "overdue"),
        ("PAST_DUE", "overdue"),
        ("OVERDUE_BY_30D", "overdue"),
        ("UNKNOWN_STATE", None),
        (None, None),
    ],
)
async def test_gear_service_status_maps_unknown_indicators(hass, load_fixture, indicator, expected):
    detail = dict(load_fixture("gear_detail_regulator"))
    if indicator is None:
        detail.pop("dueIndicator", None)
    else:
        detail["dueIndicator"] = indicator
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
        gear_details={141548: detail},
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = GearServiceStatusSensor(coord, gear_id=141548)
    assert sensor.native_value == expected


@freeze_time("2026-05-03")
async def test_gear_days_until_service(hass, load_fixture):
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
        gear_details={141548: load_fixture("gear_detail_regulator")},
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = GearDaysUntilServiceSensor(coord, gear_id=141548)
    # nextServiceDate=2027-01-01, today=2026-05-03 -> 243 days
    assert sensor.native_value == 243


async def test_dive_computer_sub_devices(hass, load_fixture):
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        devices=load_fixture("dive_devices"),
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    entities = build_dive_computer_entities(coord)
    # Three dive_devices entries -> two with serial numbers (anonymous T1
    # without serial is excluded as it's a duplicate/cached entry).
    serials = {e._serial for e in entities if hasattr(e, "_serial") and e._serial}
    assert "1000000001" in serials
    assert "1000000002" in serials
