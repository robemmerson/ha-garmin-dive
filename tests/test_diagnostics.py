"""Smoke test for diagnostics redaction."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.garmin_dive.diagnostics import (
    REDACT,
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redacts_tokens_and_session_path(hass):
    entry = MagicMock()
    entry.data = {
        "dive_access_token": "secret-access",
        "dive_refresh_token": "secret-refresh",
        "session_path": "/tmp/garmin_dive/106627261.json",
        "profile_id": 106627261,
        "profile_display_name": "Rob",
    }
    entry.runtime_data = None

    result = await async_get_config_entry_diagnostics(hass, entry)
    redacted = result["entry_data"]
    assert redacted["dive_access_token"] != "secret-access"
    assert redacted["dive_refresh_token"] != "secret-refresh"
    assert redacted["session_path"] != "/tmp/garmin_dive/106627261.json"


def test_redact_set_covers_known_secrets():
    """Sanity: every field we serialize from auth.py is in the REDACT set."""
    must_redact = {
        "dive_access_token",
        "dive_refresh_token",
        "session_path",
    }
    assert must_redact <= REDACT
