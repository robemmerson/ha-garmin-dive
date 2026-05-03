"""Tests for the refresh button."""

from __future__ import annotations

from unittest.mock import AsyncMock

from custom_components.garmin_dive.button import RefreshButton
from tests.conftest_helpers import make_fake_coordinator


async def test_press_calls_async_request_refresh(hass):
    coord = make_fake_coordinator(hass=hass)
    coord.async_request_refresh = AsyncMock()
    btn = RefreshButton(coord)
    await btn.async_press()
    coord.async_request_refresh.assert_awaited_once()
