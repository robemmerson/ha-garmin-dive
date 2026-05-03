"""Authentication for Garmin Dive: ha-garmin wrapper + DIVE audience exchange + token refresh."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from ha_garmin import GarminAuth, GarminMFARequired

from .const import TOKEN_REFRESH_SKEW_SECONDS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api import GarminDiveClient


MfaProvider = Callable[[], Awaitable[str]]


class GarminDiveAuth:
    """Holds an ha-garmin session + a separately-managed DIVE-scoped token pair."""

    def __init__(self, *, ha_auth: GarminAuth, api: GarminDiveClient) -> None:
        self._ha = ha_auth
        self._api = api
        self._dive_access_token: str | None = None
        self._dive_refresh_token: str | None = None
        self._dive_expires_at: float = 0.0
        self._profile_id: int | None = None
        self._profile_display_name: str | None = None
        self._session_path: str | None = None

    # --- Login / MFA --------------------------------------------------------

    async def login(
        self,
        *,
        hass: HomeAssistant,
        email: str,
        password: str,
        mfa_provider: MfaProvider | None = None,
    ) -> dict[str, Any]:
        """Run ha-garmin.login (in executor), handle MFA, exchange to DIVE scope, fetch profile."""
        try:
            await hass.async_add_executor_job(self._ha.login, email, password)
        except GarminMFARequired:
            if mfa_provider is None:
                raise
            code = await mfa_provider()
            await hass.async_add_executor_job(self._ha.complete_mfa, code)

        connect_token = self._ha.di_token  # Connect-API bearer
        token_resp = await self._api.exchange_dive_audience(connect_bearer=connect_token)
        self._apply_dive_token(token_resp)

        profile = await self._api.get_social_profile(connect_bearer=connect_token)
        self._profile_id = int(profile["profileId"])
        self._profile_display_name = profile.get("displayName") or profile.get("fullName")

        return profile

    # --- Token access -------------------------------------------------------

    async def get_dive_token(self) -> str:
        """Return a Dive bearer, refreshing if within the skew window."""
        if (
            self._dive_access_token
            and self._dive_expires_at - time.time() > TOKEN_REFRESH_SKEW_SECONDS
        ):
            return self._dive_access_token
        return await self._refresh()

    async def _refresh(self) -> str:
        if not self._dive_refresh_token:
            raise RuntimeError("No Dive refresh token available; reauth required")
        token_resp = await self._api.refresh_dive_token(refresh_token=self._dive_refresh_token)
        self._apply_dive_token(token_resp)
        assert self._dive_access_token is not None
        return self._dive_access_token

    def _apply_dive_token(self, resp: dict[str, Any]) -> None:
        self._dive_access_token = resp["access_token"]
        self._dive_refresh_token = resp["refresh_token"]
        self._dive_expires_at = time.time() + int(resp["expires_in"])

    # --- Persistence --------------------------------------------------------

    async def save_ha_garmin_session(self, hass: HomeAssistant, session_path: str) -> None:
        """Persist the upstream ha-garmin session JSON to ``session_path``."""
        await hass.async_add_executor_job(self._ha.save_session, session_path)
        self._session_path = session_path

    async def load_ha_garmin_session(self, hass: HomeAssistant, session_path: str) -> bool:
        """Load a previously saved ha-garmin session. Returns True on success."""
        ok = await hass.async_add_executor_job(self._ha.load_session, session_path)
        if ok:
            self._session_path = session_path
        return bool(ok)

    def serialize(self) -> dict[str, Any]:
        """Return a JSON-friendly dict suitable for storing in `entry.data`."""
        return {
            "dive_access_token": self._dive_access_token,
            "dive_refresh_token": self._dive_refresh_token,
            "dive_expires_at": self._dive_expires_at,
            "profile_id": self._profile_id,
            "profile_display_name": self._profile_display_name,
            "session_path": self._session_path,
        }

    @classmethod
    def from_entry_data(
        cls,
        data: dict[str, Any],
        *,
        ha_auth: GarminAuth,
        api: GarminDiveClient,
    ) -> GarminDiveAuth:
        auth = cls(ha_auth=ha_auth, api=api)
        auth._dive_access_token = data.get("dive_access_token")
        auth._dive_refresh_token = data.get("dive_refresh_token")
        auth._dive_expires_at = float(data.get("dive_expires_at") or 0)
        auth._profile_id = data.get("profile_id")
        auth._profile_display_name = data.get("profile_display_name")
        auth._session_path = data.get("session_path")
        return auth

    @property
    def profile_id(self) -> int | None:
        return self._profile_id

    @property
    def profile_display_name(self) -> str | None:
        return self._profile_display_name

    @property
    def session_path(self) -> str | None:
        return self._session_path
