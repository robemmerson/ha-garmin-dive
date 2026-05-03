"""Tests for binary sensors."""

from __future__ import annotations

from custom_components.garmin_dive.binary_sensor import (
    NewDiveAvailableBinarySensor,
    ServiceDueBinarySensor,
)
from tests.conftest_helpers import make_data, make_fake_coordinator


async def test_service_due_on_when_any_gear_due(hass, load_fixture):
    detail = load_fixture("gear_detail_regulator").copy()
    detail["dueIndicator"] = "DUE"
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
        gear_details={141548: detail},
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = ServiceDueBinarySensor(coord)
    assert sensor.is_on is True


async def test_service_due_off_when_all_not_due(hass, load_fixture):
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
        gear_details={141548: load_fixture("gear_detail_regulator")},
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = ServiceDueBinarySensor(coord)
    assert sensor.is_on is False


async def test_new_dive_available_latches_until_acknowledged(hass, load_fixture):
    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    coord._latest_dive_acknowledged_id = None
    sensor = NewDiveAvailableBinarySensor(coord)
    assert sensor.is_on is True
    coord._latest_dive_acknowledged_id = 23285230  # latest dive id
    assert sensor.is_on is False
