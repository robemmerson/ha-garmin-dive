"""Tests for async_setup_entry and platform fan-out."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.garmin_dive  # noqa: F401  (registers package in sys.modules)
from custom_components.garmin_dive.const import DOMAIN


@pytest.fixture
def patched_auth():
    with patch("custom_components.garmin_dive.GarminDiveAuth") as cls:
        instance = cls.return_value
        instance.profile_id = 106627261
        instance.profile_display_name = "Rob"
        instance.session_path = None
        instance.get_dive_token = AsyncMock(return_value="dive-token")
        instance.load_ha_garmin_session = AsyncMock(return_value=True)
        cls.from_entry_data = MagicMock(return_value=instance)
        yield instance


@pytest.fixture
def patched_coordinator():
    with patch("custom_components.garmin_dive.GarminDiveCoordinator") as cls:
        instance = cls.return_value
        instance.async_config_entry_first_refresh = AsyncMock()
        instance.async_request_refresh = AsyncMock()
        instance.data = MagicMock()
        yield cls, instance


async def test_setup_entry_creates_runtime_data_and_loads_platforms(
    hass, patched_auth, patched_coordinator
):
    _cls, instance = patched_coordinator
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"profile_id": 106627261, "dive_access_token": "tok"},
        unique_id="106627261",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is instance


async def test_unload_entry_unloads_platforms(hass, patched_auth, patched_coordinator):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"profile_id": 106627261, "dive_access_token": "tok"},
        unique_id="106627261",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
