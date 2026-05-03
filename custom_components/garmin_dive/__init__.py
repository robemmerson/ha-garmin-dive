"""Garmin Dive integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

import aiohttp
from ha_garmin import GarminAuth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GarminDiveClient
from .auth import GarminDiveAuth
from .const import (
    CONF_PHOTO_CACHE_ENABLED,
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_PHOTO_CACHE_ENABLED,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DIVE_OAUTH_CLIENT_ID,
    DOMAIN,
    HOST_DIAUTH,
    PATH_OAUTH_REVOKE,
    PLATFORMS,
)
from .coordinator import GarminDiveCoordinator
from .photos import PhotoCache

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garmin Dive from a config entry."""
    session = async_get_clientsession(hass)

    # Construct the API + auth pair. The API takes a get_token closure that
    # delegates to the auth's get_dive_token method.
    ha_auth = GarminAuth()
    auth: GarminDiveAuth | None = None

    async def _get_token() -> str:
        assert auth is not None
        return await auth.get_dive_token()

    api = GarminDiveClient(session=session, get_token=_get_token)
    auth = GarminDiveAuth.from_entry_data(dict(entry.data), ha_auth=ha_auth, api=api)

    # Re-load the persisted ha-garmin session so reauth (or DIVE-token
    # refresh fallback) doesn't always require re-typing the password.
    if auth.session_path:
        try:
            await auth.load_ha_garmin_session(hass, auth.session_path)
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.warning("Failed to reload ha-garmin session: %s", err)

    # Photo cache (config/www/garmin_dive/<account_short>/...)
    photo_cache: PhotoCache | None = None
    if entry.options.get(CONF_PHOTO_CACHE_ENABLED, DEFAULT_PHOTO_CACHE_ENABLED):
        www_dir = Path(hass.config.path("www"))
        await hass.async_add_executor_job(lambda: www_dir.mkdir(parents=True, exist_ok=True))
        account_short = str(auth.profile_id)
        photo_cache = PhotoCache(www_dir=www_dir, account_short=account_short)

    coordinator = GarminDiveCoordinator(
        hass,
        api=api,
        auth=auth,
        photo_cache=photo_cache,
        http_session=session,
        scan_interval_minutes=entry.options.get(
            CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
        ),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services on the first entry only.
    if not hass.services.has_service(DOMAIN, "refresh"):

        async def _service_refresh(call: ServiceCall) -> None:
            for e in hass.config_entries.async_entries(DOMAIN):
                if hasattr(e, "runtime_data"):
                    await e.runtime_data.async_request_refresh()

        async def _service_acknowledge(call: ServiceCall) -> None:
            for e in hass.config_entries.async_entries(DOMAIN):
                if hasattr(e, "runtime_data") and e.runtime_data.data and e.runtime_data.data.dives:
                    e.runtime_data.latest_dive_acknowledged_id = e.runtime_data.data.dives[0].id
                    e.runtime_data.async_update_listeners()

        hass.services.async_register(DOMAIN, "refresh", _service_refresh)
        hass.services.async_register(DOMAIN, "acknowledge_new_dive", _service_acknowledge)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Garmin Dive config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        # When the last entry goes away, drop the global services so they
        # can't be invoked against a stale runtime_data.
        remaining = [
            e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id
        ]
        if not remaining:
            hass.services.async_remove(DOMAIN, "refresh")
            hass.services.async_remove(DOMAIN, "acknowledge_new_dive")
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Future-proof migration handler."""
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Revoke OAuth tokens server-side and clean up persisted state on entry removal."""
    # 1. Revoke the DIVE refresh token if present
    refresh_token = entry.data.get("dive_refresh_token")
    if refresh_token:
        session = async_get_clientsession(hass)
        try:
            async with session.post(
                f"{HOST_DIAUTH}{PATH_OAUTH_REVOKE}",
                data={
                    "token": refresh_token,
                    "token_type_hint": "refresh_token",
                    "client_id": DIVE_OAUTH_CLIENT_ID,
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 400:
                    _LOGGER.warning(
                        "Token revocation returned HTTP %s;"
                        " tokens may remain valid until natural expiry",
                        resp.status,
                    )
        except Exception as err:  # pragma: no cover - best-effort
            _LOGGER.warning("Token revocation failed: %s", type(err).__name__)

    # 2. Remove the persisted ha-garmin session file if present
    session_path = entry.data.get("session_path")
    if session_path:

        def _unlink_if_exists() -> None:
            p = Path(session_path)
            if p.exists():
                p.unlink()

        try:
            await hass.async_add_executor_job(_unlink_if_exists)
        except Exception as err:  # pragma: no cover - best-effort
            _LOGGER.warning("Failed to remove session file: %s", type(err).__name__)
