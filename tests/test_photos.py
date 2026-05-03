"""Tests for PhotoCache."""

from __future__ import annotations

from pathlib import Path

import aiohttp
from aresponses import ResponsesMockServer

from custom_components.garmin_dive.photos import (
    PhotoCache,
    PhotoRecord,
    version_to_size,
)


def test_version_to_size_mapping():
    assert version_to_size("SMALL_THUMBNAIL") == "thumb"
    assert version_to_size("MEDIUM_FEED") == "medium"
    assert version_to_size("LARGE") == "large"
    assert version_to_size("UNKNOWN") is None


async def test_resolve_path_uses_account_short_and_uuid(tmp_path: Path):
    cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")
    p = cache.resolve_path(
        image_uuid="00000000-0000-4000-8000-000000000001",
        size="medium",
        ext="jpeg",
    )
    expected = (
        tmp_path / "garmin_dive" / "abcd1234" / "00000000-0000-4000-8000-000000000001_medium.jpeg"
    )
    assert p == expected


async def test_local_url_for_size(tmp_path: Path):
    cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")
    url = cache.local_url(image_uuid="abc", size="medium", ext="jpeg")
    assert url == "/local/garmin_dive/abcd1234/abc_medium.jpeg"


async def test_download_records_writes_files_idempotently(
    aresponses: ResponsesMockServer, tmp_path: Path
):
    aresponses.add(
        "example.invalid",
        "/img1.jpeg",
        "GET",
        aresponses.Response(status=200, body=b"\xff\xd8\xff" + b"x" * 100),
    )
    record = PhotoRecord(
        image_uuid="fixture-aaa",
        urls={"medium": ("https://example.invalid/img1.jpeg", "jpeg")},
    )
    async with aiohttp.ClientSession() as session:
        cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")
        await cache.download_records([record], session=session)
    f = tmp_path / "garmin_dive" / "abcd1234" / "fixture-aaa_medium.jpeg"
    assert f.exists()
    assert f.read_bytes().startswith(b"\xff\xd8\xff")


async def test_download_records_skips_existing(tmp_path: Path):
    cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")
    # Pre-populate target file.
    target = tmp_path / "garmin_dive" / "abcd1234" / "uuid_medium.jpeg"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"existing")

    record = PhotoRecord(
        image_uuid="uuid",
        urls={"medium": ("https://example.invalid/never-called.jpeg", "jpeg")},
    )
    # No aresponses registration — if HTTP is hit, the test fails because
    # aresponses errors on unmocked calls.
    async with aiohttp.ClientSession() as session:
        await cache.download_records([record], session=session)
    assert target.read_bytes() == b"existing"


def test_extract_records_from_garmin_image_blob():
    blob = {
        "imageUUID": "abc",
        "versions": [
            {"version": "SMALL_THUMBNAIL", "url": "https://x/abc-smth.jpeg"},
            {"version": "MEDIUM_FEED", "url": "https://x/abc-mdfd.jpeg"},
            {"version": "LARGE", "url": "https://x/abc-larg.jpeg"},
        ],
    }
    record = PhotoRecord.from_garmin_image(blob)
    assert record.image_uuid == "abc"
    assert "thumb" in record.urls
    assert "medium" in record.urls
    assert "large" in record.urls
    assert record.urls["medium"][1] == "jpeg"
