"""Pure logic for gear list/diff/derived helpers."""

from __future__ import annotations

from datetime import date

from custom_components.garmin_dive.gear import (
    GearSnapshot,
    days_until_service,
    detect_service_status_flips,
    is_serviceable,
    needs_detail_fetch,
)


def test_needs_detail_fetch_first_run_picks_up_everything():
    summary = [
        {"gearId": 1, "lastModifiedTs": "2025-01-01T00:00:00Z"},
        {"gearId": 2, "lastModifiedTs": "2025-01-02T00:00:00Z"},
    ]
    assert needs_detail_fetch(summary, previous={}) == {1, 2}


def test_needs_detail_fetch_only_returns_changed():
    summary = [
        {"gearId": 1, "lastModifiedTs": "2025-01-01T00:00:00Z"},
        {"gearId": 2, "lastModifiedTs": "2025-02-01T00:00:00Z"},
    ]
    previous = {1: "2025-01-01T00:00:00Z", 2: "2025-01-02T00:00:00Z"}
    assert needs_detail_fetch(summary, previous=previous) == {2}


def test_needs_detail_fetch_summary_without_lastmodifiedts_falls_back_to_full_refresh():
    """Spec §13: if summary lacks lastModifiedTs we re-fetch all (small N)."""
    summary = [{"gearId": 1}, {"gearId": 2}]
    assert needs_detail_fetch(summary, previous={1: "x"}) == {1, 2}


def test_detect_service_status_flips():
    previous = {141548: "NOT_DUE", 247811: "NOT_DUE"}
    current = {141548: "DUE", 247811: "NOT_DUE", 999: "OVERDUE"}
    flips = detect_service_status_flips(previous, current)
    # 141548 went NOT_DUE -> DUE. 999 is new and started at OVERDUE.
    assert flips == {141548: "DUE", 999: "OVERDUE"}


def test_detect_service_status_flips_ignores_clearing():
    """Going DUE -> NOT_DUE shouldn't fire an event."""
    previous = {1: "DUE"}
    current = {1: "NOT_DUE"}
    assert detect_service_status_flips(previous, current) == {}


def test_is_serviceable():
    assert is_serviceable("REGULATOR") is True
    assert is_serviceable("BCD") is True
    assert is_serviceable("LIGHT") is False
    assert is_serviceable("CERTIFICATION") is False


def test_days_until_service_normal():
    assert days_until_service(next_service_date="2026-06-03", today=date(2026, 5, 3)) == 31


def test_days_until_service_overdue_returns_negative():
    assert days_until_service(next_service_date="2026-04-03", today=date(2026, 5, 3)) == -30


def test_days_until_service_returns_none_when_missing():
    assert days_until_service(next_service_date=None, today=date(2026, 5, 3)) is None


def test_gearsnapshot_round_trip():
    snap = GearSnapshot(last_modified={1: "ts"}, due_indicators={1: "DUE"})
    assert snap.last_modified[1] == "ts"
    assert snap.due_indicators[1] == "DUE"
