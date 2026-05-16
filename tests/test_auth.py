"""Tests for GarminDiveAuth."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from ha_garmin import GarminMFARequired

from custom_components.garmin_dive.api import GarminDiveTokenRefreshError
from custom_components.garmin_dive.auth import GarminDiveAuth, GarminDiveAuthExpired


def _token_response(access: str = "dive-access", expires_in: int = 86399) -> dict:
    return {
        "access_token": access,
        "refresh_token": "dive-refresh",
        "token_type": "bearer",
        "expires_in": expires_in,
        "refresh_token_expires_in": 2591999,
        "scope": "DIVE_API_READ DIVE_API_WRITE",
        "jti": "test-jti",
    }


# Helper: run a sync function as if it were submitted to a thread pool, for tests.
def _run_sync(fn, *args, **kwargs):
    fut = asyncio.get_running_loop().create_future()
    try:
        fut.set_result(fn(*args, **kwargs))
    except Exception as e:
        fut.set_exception(e)
    return fut


async def test_login_calls_ha_garmin_then_exchanges_dive_audience():
    """Successful login (no MFA): calls ha_garmin.login, exchanges for Dive audience."""
    fake_ha = MagicMock()
    fake_ha.login = MagicMock(return_value=MagicMock())  # AuthResult, ignored
    fake_ha.di_token = "connect-access"

    api = MagicMock()
    api.exchange_dive_audience = AsyncMock(return_value=_token_response())
    api.get_social_profile = AsyncMock(
        return_value={"profileId": 999000111, "displayName": "test-user"}
    )

    auth = GarminDiveAuth(ha_auth=fake_ha, api=api)
    profile = await auth.login(
        hass=MagicMock(async_add_executor_job=_run_sync),
        email="test@example.invalid",
        password="secret",
    )

    fake_ha.login.assert_called_once_with("test@example.invalid", "secret")
    api.exchange_dive_audience.assert_awaited_once_with(connect_bearer="connect-access")
    assert profile["profileId"] == 999000111
    assert auth.profile_id == 999000111
    assert auth.profile_display_name == "test-user"
    assert (await auth.get_dive_token()) == "dive-access"


async def test_login_handles_mfa_via_provider():
    """When ha_garmin raises GarminMFARequired, login awaits the mfa_provider."""
    fake_ha = MagicMock()
    fake_ha.login = MagicMock(side_effect=GarminMFARequired("MFA required"))
    fake_ha.complete_mfa = MagicMock(return_value=MagicMock())
    fake_ha.di_token = "connect-access"

    api = MagicMock()
    api.exchange_dive_audience = AsyncMock(return_value=_token_response())
    api.get_social_profile = AsyncMock(return_value={"profileId": 1, "displayName": "X"})

    async def mfa_provider() -> str:
        return "123456"

    auth = GarminDiveAuth(ha_auth=fake_ha, api=api)
    await auth.login(
        hass=MagicMock(async_add_executor_job=_run_sync),
        email="x@example.invalid",
        password="secret",
        mfa_provider=mfa_provider,
    )

    fake_ha.login.assert_called_once()
    fake_ha.complete_mfa.assert_called_once_with("123456")


async def test_get_dive_token_refreshes_when_within_skew():
    api = MagicMock()
    api.refresh_dive_token = AsyncMock(return_value=_token_response(access="rotated"))

    auth = GarminDiveAuth(ha_auth=MagicMock(), api=api)
    auth._dive_access_token = "expiring"
    auth._dive_refresh_token = "rt"
    auth._dive_expires_at = time.time() + 60  # within 5-min skew

    token = await auth.get_dive_token()
    api.refresh_dive_token.assert_awaited_once_with(refresh_token="rt")
    assert token == "rotated"


async def test_get_dive_token_caches_when_fresh():
    api = MagicMock()
    api.refresh_dive_token = AsyncMock()

    auth = GarminDiveAuth(ha_auth=MagicMock(), api=api)
    auth._dive_access_token = "fresh"
    auth._dive_refresh_token = "rt"
    auth._dive_expires_at = time.time() + 36000  # well above skew

    token = await auth.get_dive_token()
    assert token == "fresh"
    api.refresh_dive_token.assert_not_awaited()


async def test_serialize_round_trip():
    auth = GarminDiveAuth(ha_auth=MagicMock(), api=MagicMock())
    auth._dive_access_token = "a"
    auth._dive_refresh_token = "r"
    auth._dive_expires_at = 1234567890
    auth._profile_id = 999000111
    auth._profile_display_name = "test-user"
    auth._session_path = "/tmp/garmin_dive/999000111.json"

    data = auth.serialize()
    assert data["dive_access_token"] == "a"
    assert data["dive_refresh_token"] == "r"
    assert data["dive_expires_at"] == 1234567890
    assert data["profile_id"] == 999000111
    assert data["profile_display_name"] == "test-user"
    assert data["session_path"] == "/tmp/garmin_dive/999000111.json"


async def test_refresh_raises_auth_expired_when_unrecoverable():
    """No Dive refresh token AND a dead Connect session => GarminDiveAuthExpired."""
    fake_ha = MagicMock()
    fake_ha.refresh_session = AsyncMock(return_value=False)
    fake_ha.di_token = None  # Connect session also gone

    auth = GarminDiveAuth(ha_auth=fake_ha, api=MagicMock())
    auth._dive_access_token = None
    auth._dive_refresh_token = None
    auth._dive_expires_at = 0

    with pytest.raises(GarminDiveAuthExpired, match="reauthentication required"):
        await auth.get_dive_token()


async def test_invalid_grant_recovers_via_connect_reexchange():
    """A 400 invalid_grant on refresh re-mints the DIVE token from the Connect session."""
    fake_ha = MagicMock()
    fake_ha.refresh_session = AsyncMock(return_value=True)
    fake_ha.di_token = "connect-bearer"

    api = MagicMock()
    api.refresh_dive_token = AsyncMock(
        side_effect=GarminDiveTokenRefreshError(400, '{"error":"invalid_grant"}')
    )
    api.exchange_dive_audience = AsyncMock(return_value=_token_response(access="reexchanged"))

    auth = GarminDiveAuth(ha_auth=fake_ha, api=api)
    auth._dive_access_token = "stale"
    auth._dive_refresh_token = "dead-rt"
    auth._dive_expires_at = time.time() + 60  # within skew -> forces refresh

    token = await auth.get_dive_token()
    assert token == "reexchanged"
    api.exchange_dive_audience.assert_awaited_once_with(connect_bearer="connect-bearer")


async def test_transient_refresh_error_is_reraised_not_reexchanged():
    """A 5xx from diauth is transient: propagate it, don't burn the Connect session."""
    fake_ha = MagicMock()
    fake_ha.refresh_session = AsyncMock()

    api = MagicMock()
    api.refresh_dive_token = AsyncMock(
        side_effect=GarminDiveTokenRefreshError(503, "Service Unavailable")
    )
    api.exchange_dive_audience = AsyncMock()

    auth = GarminDiveAuth(ha_auth=fake_ha, api=api)
    auth._dive_access_token = "stale"
    auth._dive_refresh_token = "rt"
    auth._dive_expires_at = time.time() + 60

    with pytest.raises(GarminDiveTokenRefreshError):
        await auth.get_dive_token()
    api.exchange_dive_audience.assert_not_awaited()


async def test_token_listener_fires_with_rotated_pair():
    """_apply_dive_token notifies the listener so rotated tokens can be persisted."""
    api = MagicMock()
    api.refresh_dive_token = AsyncMock(
        return_value={
            "access_token": "rotated",
            "refresh_token": "new-rt",
            "expires_in": 3600,
        }
    )
    auth = GarminDiveAuth(ha_auth=MagicMock(), api=api)
    auth._dive_access_token = "old"
    auth._dive_refresh_token = "old-rt"
    auth._dive_expires_at = time.time() + 60

    seen: list[dict] = []
    auth.set_token_listener(seen.append)

    await auth.get_dive_token()
    assert len(seen) == 1
    assert seen[0]["dive_access_token"] == "rotated"
    assert seen[0]["dive_refresh_token"] == "new-rt"


async def test_refresh_updates_expires_at():
    """A successful refresh advances _dive_expires_at by the new expires_in."""
    api = MagicMock()
    api.refresh_dive_token = AsyncMock(
        return_value={
            "access_token": "rotated",
            "refresh_token": "new-rt",
            "expires_in": 3600,
        }
    )
    auth = GarminDiveAuth(ha_auth=MagicMock(), api=api)
    auth._dive_access_token = "old"
    auth._dive_refresh_token = "rt"
    auth._dive_expires_at = time.time() + 60  # within skew

    before = time.time()
    await auth.get_dive_token()
    # _dive_expires_at should be around (before + 3600), give or take 5s.
    assert auth._dive_expires_at >= before + 3600 - 5
    assert auth._dive_expires_at <= before + 3600 + 5
    assert auth._dive_refresh_token == "new-rt"
