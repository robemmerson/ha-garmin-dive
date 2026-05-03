"""Config and options flow for Garmin Dive."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import voluptuous as vol
from ha_garmin import GarminAuth
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GarminDiveClient
from .auth import GarminDiveAuth
from .const import (
    CONF_HISTORY_SCOPE,
    CONF_MAX_CACHE_AGE_DAYS,
    CONF_PHOTO_CACHE_ENABLED,
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_HISTORY_SCOPE,
    DEFAULT_MAX_CACHE_AGE_DAYS,
    DEFAULT_PHOTO_CACHE_ENABLED,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    HISTORY_SCOPE_CHOICES,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

MFA_SCHEMA = vol.Schema({vol.Required("mfa_code"): str})


class GarminDiveConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._email: str | None = None
        self._password: str | None = None
        self._auth: GarminDiveAuth | None = None
        self._mfa_future: asyncio.Future[str] | None = None
        self._login_task: asyncio.Task | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

        self._email = user_input[CONF_EMAIL]
        self._password = user_input[CONF_PASSWORD]
        return await self._start_login()

    async def async_step_mfa(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="mfa", data_schema=MFA_SCHEMA)
        if self._mfa_future is None or self._login_task is None:
            return self.async_abort(reason="unknown_error")
        self._mfa_future.set_result(user_input["mfa_code"])
        try:
            profile = await self._login_task
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Garmin login after MFA failed: %s", err)
            return self.async_show_form(
                step_id="mfa",
                data_schema=MFA_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        return await self._finalize(profile)

    async def _start_login(self) -> ConfigFlowResult:
        ha_auth = GarminAuth()
        api = GarminDiveClient(
            session=async_get_clientsession(self.hass),
            get_token=lambda: asyncio.sleep(0, result=""),  # not used during login
        )
        self._auth = GarminDiveAuth(ha_auth=ha_auth, api=api)

        loop = asyncio.get_running_loop()
        self._mfa_future = loop.create_future()

        async def mfa_provider() -> str:
            assert self._mfa_future is not None
            return await self._mfa_future

        async def run_login() -> dict[str, Any]:
            return await self._auth.login(
                hass=self.hass,
                email=self._email,
                password=self._password,
                mfa_provider=mfa_provider,
            )

        self._login_task = asyncio.create_task(run_login())

        # Race: either login completes synchronously (no MFA) or blocks on the
        # mfa_provider future.
        try:
            done, _ = await asyncio.wait(
                [self._login_task],
                timeout=4.0,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if done:
                profile = self._login_task.result()  # re-raises if task failed
                return await self._finalize(profile)
            # Still pending => login is blocked on mfa_provider
            return self.async_show_form(step_id="mfa", data_schema=MFA_SCHEMA)
        except Exception as err:
            _LOGGER.exception("Garmin login failed: %s", err)
            if not self._login_task.done():
                self._login_task.cancel()
            return self.async_show_form(
                step_id="user",
                data_schema=USER_SCHEMA,
                errors={"base": "invalid_auth"},
            )

    async def _finalize(self, profile: dict[str, Any]) -> ConfigFlowResult:
        assert self._auth is not None
        profile_id = str(profile["profileId"])
        await self.async_set_unique_id(profile_id)
        self._abort_if_unique_id_configured()

        # Persist the upstream ha-garmin session (refresh tokens etc.) under
        # config/.storage/ so reauth doesn't always require the password.
        session_path = self.hass.config.path(".storage", f"{DOMAIN}_{profile_id}_session.json")
        Path(session_path).parent.mkdir(parents=True, exist_ok=True)
        await self._auth.save_ha_garmin_session(self.hass, session_path)

        title = (
            f"Garmin Dive — {profile.get('displayName') or profile.get('fullName') or profile_id}"
        )
        return self.async_create_entry(title=title, data=self._auth.serialize())

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        self._email = entry_data.get("email")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm", data_schema=USER_SCHEMA)
        return await self.async_step_user(user_input)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return GarminDiveOptionsFlow(config_entry)


class GarminDiveOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL_MINUTES,
                    default=opts.get(CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES),
                ): vol.All(int, vol.Range(min=5, max=360)),
                vol.Required(
                    CONF_PHOTO_CACHE_ENABLED,
                    default=opts.get(CONF_PHOTO_CACHE_ENABLED, DEFAULT_PHOTO_CACHE_ENABLED),
                ): bool,
                vol.Required(
                    CONF_HISTORY_SCOPE,
                    default=opts.get(CONF_HISTORY_SCOPE, DEFAULT_HISTORY_SCOPE),
                ): vol.In(HISTORY_SCOPE_CHOICES),
                vol.Required(
                    CONF_MAX_CACHE_AGE_DAYS,
                    default=opts.get(CONF_MAX_CACHE_AGE_DAYS, DEFAULT_MAX_CACHE_AGE_DAYS),
                ): vol.All(int, vol.Range(min=0, max=3650)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
