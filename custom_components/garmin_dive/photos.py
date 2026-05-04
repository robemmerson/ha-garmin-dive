"""Local photo cache: resolves stable HA URLs from expiring Garmin S3 URLs."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp

from .const import PHOTO_CACHE_CONCURRENCY, PHOTO_CACHE_DIR_NAME

_LOGGER = logging.getLogger(__name__)

_VERSION_TO_SIZE: dict[str, str] = {
    "SMALL_THUMBNAIL": "thumb",
    "MEDIUM_FEED": "medium",
    "LARGE": "large",
}


def version_to_size(version: str) -> str | None:
    return _VERSION_TO_SIZE.get(version)


@dataclass(slots=True)
class PhotoRecord:
    """A single photo with one URL per requested size.

    `urls` maps size ('thumb'|'medium'|'large') to (url, ext) tuples.
    """

    image_uuid: str
    urls: dict[str, tuple[str, str]] = field(default_factory=dict)

    @classmethod
    def from_garmin_image(cls, blob: dict[str, Any]) -> PhotoRecord:
        urls: dict[str, tuple[str, str]] = {}
        for entry in blob.get("versions") or blob.get("versionedUrls") or []:
            size = version_to_size(entry.get("version") or "")
            url = entry.get("url")
            if not size or not url:
                continue
            ext = _ext_from_url(url)
            urls[size] = (url, ext)
        return cls(image_uuid=blob["imageUUID"], urls=urls)

    @classmethod
    def from_activity_image(cls, blob: dict[str, Any]) -> PhotoRecord:
        """Convert a Connect /activity-service `activityImages[]` entry.

        That endpoint flattens the per-size URLs into `smallUrl` / `mediumUrl`
        / `url` (large) instead of the GraphQL `versionedUrls[]` shape.
        """
        urls: dict[str, tuple[str, str]] = {}
        for size, key in (("thumb", "smallUrl"), ("medium", "mediumUrl"), ("large", "url")):
            url = blob.get(key)
            if not url:
                continue
            urls[size] = (url, _ext_from_url(url))
        return cls(image_uuid=blob["imageId"], urls=urls)


def _ext_from_url(url: str) -> str:
    m = re.search(r"\.([A-Za-z0-9]{2,5})(?:\?|$)", url)
    return m.group(1).lower() if m else "jpeg"


class PhotoCache:
    """Downloads + serves Garmin dive photos via HA's `/local/` static server."""

    def __init__(self, *, www_dir: Path, account_short: str) -> None:
        self._www = www_dir
        self._account_short = account_short
        self._semaphore = asyncio.Semaphore(PHOTO_CACHE_CONCURRENCY)

    # --- Path & URL helpers -------------------------------------------------

    def resolve_path(self, *, image_uuid: str, size: str, ext: str) -> Path:
        return self._www / PHOTO_CACHE_DIR_NAME / self._account_short / f"{image_uuid}_{size}.{ext}"

    def local_url(self, *, image_uuid: str, size: str, ext: str) -> str:
        return f"/local/{PHOTO_CACHE_DIR_NAME}/{self._account_short}/{image_uuid}_{size}.{ext}"

    # --- Download -----------------------------------------------------------

    async def download_records(
        self,
        records: list[PhotoRecord],
        *,
        session: aiohttp.ClientSession,
    ) -> dict[str, set[str]]:
        """Download each record's sizes and return per-uuid set of cached sizes.

        Result maps `image_uuid -> {sizes that exist on disk after this call}`.
        Always tolerant: a single failure never aborts the rest of the batch.
        """
        results = await asyncio.gather(
            *(self._download_one(r, session=session) for r in records),
            return_exceptions=True,
        )
        cached: dict[str, set[str]] = {}
        for record, outcome in zip(records, results, strict=True):
            if isinstance(outcome, BaseException):
                _LOGGER.warning("Photo download crashed for %s: %s", record.image_uuid, outcome)
                cached[record.image_uuid] = set()
                continue
            cached[record.image_uuid] = outcome
        return cached

    async def _download_one(
        self, record: PhotoRecord, *, session: aiohttp.ClientSession
    ) -> set[str]:
        cached_sizes: set[str] = set()
        for size, (url, ext) in record.urls.items():
            target = self.resolve_path(image_uuid=record.image_uuid, size=size, ext=ext)
            if await asyncio.to_thread(target.exists):
                cached_sizes.add(size)
                continue
            await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
            async with self._semaphore:
                try:
                    async with session.get(url) as resp:
                        resp.raise_for_status()
                        data = await resp.read()
                    await asyncio.to_thread(target.write_bytes, data)
                except (aiohttp.ClientError, TimeoutError, OSError) as err:
                    _LOGGER.warning(
                        "Failed to download photo %s/%s: %s",
                        record.image_uuid,
                        size,
                        err,
                    )
                    continue
                cached_sizes.add(size)
        return cached_sizes
