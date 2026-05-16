"""HTTP client for Garmin Dive APIs (no Home Assistant imports here)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from .const import (
    APP_USER_AGENT,
    APP_X_APP_VER,
    APP_X_LANG,
    DIVE_OAUTH_AUDIENCE,
    DIVE_OAUTH_CLIENT_ID,
    GEAR_TYPES,
    HOST_CONNECT_API,
    HOST_DIAUTH,
    HOST_GCS,
    PATH_ACTIVITY,
    PATH_DIVE_DEVICES,
    PATH_DIVE_SUMMARY,
    PATH_DIVE_TAGS,
    PATH_GEAR_DETAIL,
    PATH_GEAR_SUMMARY,
    PATH_GRAPHQL,
    PATH_OAUTH_EXCHANGE,
    PATH_OAUTH_TOKEN,
    PATH_SOCIAL_PROFILE_V2,
)

GetTokenFn = Callable[[], Awaitable[str]]


class GarminDiveTokenRefreshError(Exception):
    """The diauth token endpoint rejected a refresh_token grant.

    Carries the HTTP status and (truncated) response body so callers can
    distinguish a dead/rotated refresh token (`invalid_grant`, HTTP 400) from
    a transient server-side failure (5xx) and react accordingly.
    """

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        # Keep a bounded slice — the OAuth error JSON is tiny; this guards
        # against a proxy returning a huge HTML error page.
        self.body = body[:500]
        super().__init__(f"diauth refresh returned HTTP {status}: {self.body}")

    @property
    def is_invalid_grant(self) -> bool:
        """True when the refresh token is expired/revoked/already-rotated.

        Per RFC 6749 §5.2 the endpoint returns HTTP 400 with an
        ``{"error": "invalid_grant"}`` body in this case.
        """
        return self.status == 400 and "invalid_grant" in self.body


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

    async def get_gear_detail(self, *, gear_id: int, current_user_date: str) -> dict[str, Any]:
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
        # The `year` arg is unused: PlayerProfile returns the player's full
        # photo timeline, which the coordinator filters by dive eventDate.
        # Kept for signature stability with the rest of the build_data path.
        del year
        query = (
            "query PlayerProfile($playerId: Long!) { "
            "playerProfile(playerId: $playerId) { "
            "__typename "
            "playerProfileId "
            "profileName "
            "medias { "
            "__typename totalCount "
            "content { "
            "__typename "
            "... on Image { "
            "imageUUID inappropriateReviewStatus timezone eventDate "
            "associatedEntityType associatedEntityName entityReferenceId "
            "owner { __typename profileName playerProfileId } "
            "versionedUrls { __typename key url urlExpiration version } "
            "} } } } }"
        )
        return await self.graphql(
            operation_name="PlayerProfile",
            query=query,
            variables={"playerId": profile_id},
        )

    async def get_activity(self, *, activity_id: int) -> dict[str, Any]:
        """Per-activity Connect REST endpoint.

        Used as a fallback photo source when the bulk PlayerProfile GraphQL
        query doesn't return images for a dive (which happens — Garmin's two
        services have inconsistent coverage). The Dive bearer carries
        `CONNECT_READ`, so it authenticates against connectapi.garmin.com.
        """
        return await self._request(
            "GET",
            HOST_CONNECT_API,
            PATH_ACTIVITY.format(activity_id=activity_id),
        )

    # ----- Auxiliary auth + identity calls ----------------------------------

    async def exchange_dive_audience(self, *, connect_bearer: str) -> dict[str, Any]:
        """Exchange the Connect OAuth2 token for a DIVE-scoped one."""
        async with self._session.post(
            f"{HOST_CONNECT_API}{PATH_OAUTH_EXCHANGE}",
            data={"audience": DIVE_OAUTH_AUDIENCE},
            headers={
                "Authorization": f"bearer {connect_bearer}",
                "Accept": "application/json",
                "User-Agent": APP_USER_AGENT,
                "X-App-Ver": APP_X_APP_VER,
                "X-Lang": APP_X_LANG,
            },
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def refresh_dive_token(self, *, refresh_token: str) -> dict[str, Any]:
        """Use the Dive-scoped refresh token to mint a new Dive access token."""
        async with self._session.post(
            f"{HOST_DIAUTH}{PATH_OAUTH_TOKEN}",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": DIVE_OAUTH_CLIENT_ID,
            },
            headers={
                "Accept": "application/json",
                "User-Agent": APP_USER_AGENT,
                "X-App-Ver": APP_X_APP_VER,
                "X-Lang": APP_X_LANG,
            },
        ) as resp:
            if resp.status >= 400:
                # Capture the OAuth error body before raising — raise_for_status
                # would discard it, and that body is the only signal telling us
                # whether to reauth (invalid_grant) or just retry (5xx).
                raise GarminDiveTokenRefreshError(resp.status, await resp.text())
            return await resp.json(content_type=None)

    async def get_social_profile(self, *, connect_bearer: str) -> dict[str, Any]:
        async with self._session.get(
            f"{HOST_CONNECT_API}{PATH_SOCIAL_PROFILE_V2}",
            headers={
                "Authorization": f"bearer {connect_bearer}",
                "Accept": "application/json",
                "User-Agent": APP_USER_AGENT,
                "X-App-Ver": APP_X_APP_VER,
                "X-Lang": APP_X_LANG,
            },
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)
