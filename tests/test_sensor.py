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


async def test_dive_log_year_attribute_shape(hass, load_fixture):
    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = DiveLogYearSensor(coord)

    attrs = sensor.extra_state_attributes
    dives = attrs["dives"]
    # Surfaces every dive regardless of year; the recorder skips the
    # `dives` attribute via `_unrecorded_attributes` so size is irrelevant.
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
    assert "dives" in DiveLogYearSensor._unrecorded_attributes


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


async def test_descent_in_both_lists_yields_one_device(hass, load_fixture):
    """Issue #18: a Descent shows up in /dive/devices AND /gear, and Garmin's
    serial fields match. The integration must surface this as ONE HA device
    that carries both gear-derived and computer-derived sensors."""
    serial = "1000000099"
    gear_summary = [
        {
            "gearId": 555001,
            "name": "Descent T1",
            "type": "TRANSMITTER",
            "dateOfFirstUse": "2022-01-01",
            "status": "ACTIVE",
            "creationTs": "2022-01-01T00:00:00Z",
            "lastModifiedTs": "2023-01-01T00:00:00Z",
            "stats": {"numAssociatedDives": 36, "totalAssociatedDiveTime": 108558.86},
        }
    ]
    gear_details = {
        555001: {
            "gearId": 555001,
            "name": "Descent T1",
            "type": "TRANSMITTER",
            "brand": "Garmin",
            "model": "Descent T1",
            "serialNumber": serial,
            "purchaseDate": "2022-01-01",
            "stats": {"numAssociatedDives": 36, "totalAssociatedDiveTime": 108558.86},
        }
    }
    devices = [
        {
            "imageUrl": "https://example.invalid/t1.png",
            "productDisplayName": "Descent T1",
            "serialNumber": int(serial),
            "antChannelId": 10100200,
            "type": "TRANSMITTER",
            "gearTrackingStatus": "TRACKED",
            "deviceDismissed": False,
        }
    ]
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        devices=devices,
        gear_summary=gear_summary,
        gear_details=gear_details,
    )
    coord = make_fake_coordinator(hass=hass, data=data)

    entities = build_gear_entities(coord) + build_dive_computer_entities(coord)
    descent_entities = [
        e for e in entities if "555001" in (e.unique_id or "") or serial in (e.unique_id or "")
    ]
    assert descent_entities, "expected entities for the Descent T1"

    # Every entity for the Descent must hang off the SAME HA device (i.e. the
    # set of identifier-tuples on each entity's device_info must overlap with
    # all others), so HA's device registry merges them into a single entry.
    identifier_sets = [frozenset(e.device_info["identifiers"]) for e in descent_entities]
    common = set.intersection(*(set(s) for s in identifier_sets))
    assert common, (
        "Descent T1 entities point at disjoint device identifiers — "
        f"HA will create duplicate devices. Sets: {identifier_sets}"
    )


async def test_t1_dedup_by_ant_channel_when_serials_differ(hass, load_fixture):
    """Real-world bug: a Descent T1 in /gear/{id} carries a *printed* /
    short serialNumber (e.g. \"09144\") while /dive/devices reports the
    full numeric serial (e.g. \"3399109144\"). The two refer to the same
    physical T1 — proven by a shared `antChannelId`. We must merge them.
    """
    gear_summary = [
        {
            "gearId": 555002,
            "name": "Descent T1",
            "type": "TRANSMITTER",
            "dateOfFirstUse": "2022-07-29",
            "status": "ACTIVE",
            "creationTs": "2022-07-29T00:00:00Z",
            "lastModifiedTs": "2023-01-01T00:00:00Z",
            "stats": {"numAssociatedDives": 36, "totalAssociatedDiveTime": 108558.86},
        }
    ]
    gear_details = {
        555002: {
            "gearId": 555002,
            "name": "Descent T1",
            "type": "TRANSMITTER",
            "brand": "Garmin",
            "model": "Descent T1",
            "serialNumber": "09144",  # short / printed serial
            "antChannelId": 12345678,
            "purchaseDate": "2022-07-29",
            "stats": {"numAssociatedDives": 36, "totalAssociatedDiveTime": 108558.86},
        }
    }
    devices = [
        {
            "imageUrl": "https://example.invalid/t1.png",
            "productDisplayName": "Descent T1",
            "serialNumber": 3399109144,  # full numeric serial — disagrees with gear
            "antChannelId": 12345678,  # …but antChannelId agrees
            "type": "TRANSMITTER",
            "gearTrackingStatus": "TRACKED",
            "deviceDismissed": False,
        }
    ]
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        devices=devices,
        gear_summary=gear_summary,
        gear_details=gear_details,
    )
    coord = make_fake_coordinator(hass=hass, data=data)

    entities = build_gear_entities(coord) + build_dive_computer_entities(coord)
    descent_entities = [
        e
        for e in entities
        if "555002" in (e.unique_id or "") or "3399109144" in (e.unique_id or "")
    ]
    assert descent_entities, "expected entities for the Descent T1"

    identifier_sets = [frozenset(e.device_info["identifiers"]) for e in descent_entities]
    common = set.intersection(*(set(s) for s in identifier_sets))
    assert common, (
        "Descent T1 entities point at disjoint device identifiers — "
        f"HA will create duplicate devices. Sets: {identifier_sets}"
    )


async def test_dive_devices_duplicates_dedup_by_ant_channel(hass, load_fixture):
    """Garmin's /dive/devices sometimes returns the same physical transmitter
    twice (one cached entry without serial, one live with serial — or two
    live entries with different stale serials). We de-dup by antChannelId so
    the duplicate entry doesn't manifest as a duplicate HA device."""
    devices = [
        {
            "productDisplayName": "Descent T1",
            "antChannelId": 12345678,
            "type": "TRANSMITTER",
            "gearTrackingStatus": "TRACKED",
            "deviceDismissed": False,
        },
        {
            "productDisplayName": "Descent T1",
            "serialNumber": 3399109144,
            "antChannelId": 12345678,
            "type": "TRANSMITTER",
            "gearTrackingStatus": "TRACKED",
            "deviceDismissed": False,
        },
        {
            "productDisplayName": "Descent T1",
            "serialNumber": 9999999999,  # stale duplicate, same antChannelId
            "antChannelId": 12345678,
            "type": "TRANSMITTER",
            "gearTrackingStatus": "TRACKED",
            "deviceDismissed": False,
        },
    ]
    data = make_data(summary=load_fixture("dive_summary_full"), devices=devices)
    coord = make_fake_coordinator(hass=hass, data=data)
    entities = build_dive_computer_entities(coord)
    serials = [e._serial for e in entities if hasattr(e, "_serial")]
    # Exactly one set of dive-computer entities should be emitted, not three.
    assert len(set(serials)) == 1, f"expected one Descent T1, got serials={serials}"
