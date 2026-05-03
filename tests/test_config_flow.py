"""Tests for the Garmin Dive config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

import custom_components.garmin_dive.config_flow  # noqa: F401 — ensures correct custom_components is in sys.modules before patch() runs


@pytest.fixture
def social_profile_payload(load_fixture):
    return load_fixture("social_profile_v2")


async def test_user_step_happy_path(hass, social_profile_payload):
    """Login succeeds without MFA."""
    with patch("custom_components.garmin_dive.config_flow.GarminDiveAuth") as mock_cls:
        instance = mock_cls.return_value
        instance.login = AsyncMock(return_value=social_profile_payload)
        instance.serialize = MagicMock(return_value={"profile_id": 106627261})
        instance.save_ha_garmin_session = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            "garmin_dive", context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": "test@example.invalid", "password": "secret"},
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"].startswith("Garmin Dive")
        assert result["data"]["profile_id"] == 106627261


async def test_user_step_invalid_credentials(hass):
    with patch("custom_components.garmin_dive.config_flow.GarminDiveAuth") as mock_cls:
        instance = mock_cls.return_value
        instance.login = AsyncMock(side_effect=Exception("Bad credentials"))

        result = await hass.config_entries.flow.async_init(
            "garmin_dive", context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": "x@example.invalid", "password": "wrong"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_unique_id_is_profile_id(hass, social_profile_payload):
    with patch("custom_components.garmin_dive.config_flow.GarminDiveAuth") as mock_cls:
        instance = mock_cls.return_value
        instance.login = AsyncMock(return_value=social_profile_payload)
        instance.serialize = MagicMock(return_value={"profile_id": 106627261})
        instance.save_ha_garmin_session = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            "garmin_dive", context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": "test@example.invalid", "password": "secret"},
        )
        entry = result["result"]
        assert entry.unique_id == "106627261"
