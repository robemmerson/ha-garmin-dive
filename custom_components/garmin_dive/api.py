"""HTTP client for Garmin Dive APIs (no Home Assistant imports here)."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from .const import (
    APP_USER_AGENT,
    APP_X_APP_VER,
    APP_X_LANG,
    GEAR_TYPES,
    HOST_GCS,
    PATH_DIVE_DEVICES,
    PATH_DIVE_SUMMARY,
    PATH_DIVE_TAGS,
    PATH_GEAR_DETAIL,
    PATH_GEAR_SUMMARY,
    PATH_GRAPHQL,
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

    async def get_dive_devices(self) -> list[dict[str, Any]]:
        return await self._request("GET", HOST_GCS, PATH_DIVE_DEVICES)

    async def get_dive_tags(self) -> dict[str, int]:
        return await self._request("GET", HOST_GCS, PATH_DIVE_TAGS)

    async def get_gear_summary(self, *, current_user_date: str) -> list[dict[str, Any]]:
        # The iOS app sends every supported gear type as a separate `gear-types`
        # query param. Build the param list as ordered tuples to preserve repeats.
        params: list[tuple[str, Any]] = [("current-user-date", current_user_date)]
        params.extend(("gear-types", t) for t in GEAR_TYPES)
        return await self._request("GET", HOST_GCS, PATH_GEAR_SUMMARY, params=params)

    async def get_gear_detail(
        self, *, gear_id: int, current_user_date: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            HOST_GCS,
            PATH_GEAR_DETAIL.format(gear_id=gear_id),
            params={"current-user-date": current_user_date},
        )

    # ----- GraphQL ----------------------------------------------------------

    async def graphql(
        self,
        *,
        operation_name: str,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        body = {
            "extensions": {"clientLibrary": {"name": "ha-garmin-dive", "version": "0.1.0"}},
            "operationName": operation_name,
            "query": query,
            "variables": variables,
        }
        return await self._request("POST", HOST_GCS, PATH_GRAPHQL, json_body=body)

    async def get_dive_photos(self, *, profile_id: int, year: int) -> dict[str, Any]:
        # Operation name is provisional; refine when capturing the Photos
        # screen during phase 4 (spec §13). The query string below is a
        # plausible shape consistent with the captured response.
        query = (
            "query DiveImagesByDateRange("
            "$playerId: Long!, $start: LocalDate!, $end: LocalDate!) { "
            "diveImages(playerId: $playerId, startDate: $start, endDate: $end) "
            "{ __typename items { __typename imageUUID inappropriateReviewStatus "
            "timezone eventDate associatedEntityType associatedEntityName "
            "entityReferenceId owner { __typename profileName playerProfileId } "
            "versionedUrls { __typename key url urlExpiration version } } } }"
        )
        return await self.graphql(
            operation_name="DiveImagesByDateRange",
            query=query,
            variables={
                "playerId": profile_id,
                "start": f"{year}-01-01",
                "end": f"{year}-12-31",
            },
        )
