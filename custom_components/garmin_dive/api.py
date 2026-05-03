"""HTTP client for Garmin Dive APIs (no Home Assistant imports here)."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from .const import (
    APP_USER_AGENT,
    APP_X_APP_VER,
    APP_X_LANG,
    HOST_GCS,
    PATH_DIVE_SUMMARY,
)

GetTokenFn = Callable[[], Awaitable[str]]


class GarminDiveClient:
    """Async HTTP client for the Dive REST + GraphQL endpoints on gcs.garmin.com."""

    def __init__(self, session: aiohttp.ClientSession, get_token: GetTokenFn) -> None:
        self._session = session
        self._get_token = get_token

    async def _request(
        self,
        method: str,
        host: str,
        path: str,
        *,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
        json_body: Any = None,
    ) -> Any:
        token = await self._get_token()
        headers = {
            "Authorization": f"bearer {token}",
            "Accept": "application/json",
            "User-Agent": APP_USER_AGENT,
            "X-App-Ver": APP_X_APP_VER,
            "X-Lang": APP_X_LANG,
        }
        async with self._session.request(
            method,
            f"{host}{path}",
            params=params,
            json=json_body,
            headers=headers,
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def get_dive_summary(
        self, *, page: int = 0, results_per_page: int = 100
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            HOST_GCS,
            PATH_DIVE_SUMMARY,
            params={"requestedPage": page, "resultsPerPage": results_per_page},
        )
