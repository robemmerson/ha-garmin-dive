# Home Assistant Garmin Dive Integration — Design Spec

**Date:** 2026-05-03
**Status:** Draft for review
**Repo:** `ha-garmin-dive` (HACS-installable custom component)

> **Deviation note (added during implementation):** §3.1 / §4 / §5 reference the `garth` library. `garth` was [deprecated](https://github.com/matin/garth/discussions/222) in 2026 because Garmin's TLS-fingerprinting changes broke its mobile-auth flow. Implementation switched to [`ha-garmin`](https://pypi.org/project/ha-garmin/) (used by `cyberjunky/home-assistant-garmin_connect`), which uses `curl_cffi` to impersonate a browser. The architecture is otherwise unchanged: get a Connect bearer via `ha-garmin`, exchange to `DIVE_MOBILE_IOS_DI` audience, drive `gcs.garmin.com` from there. See plan T9 / T23 / T24 for the up-to-date code.

## 1. Goals & non-goals

### Goals

- Surface Garmin Dive data in Home Assistant for one-or-more Garmin accounts.
- Power a yearly **dive timeline dashboard** — a horizontally scrollable strip of cards, one per dive, with stats and photos.
- Track personal **diving gear** (regulators, transmitters, lights, cameras, etc.) with service-due reminders and lifetime usage stats.
- Coexist cleanly with the existing HACS Garmin Connect integration (which owns body battery / sleep / steps / stress / wellness data) — this integration only fetches dive-specific data.
- Distribute via HACS with full validation (hassfest, HACS validate), tests, and a release pipeline.

### Non-goals (YAGNI)

- Generic Garmin Connect data already covered by the existing HACS integration.
- Decompression-model / dive-readiness daily metrics. Possible follow-up.
- Writing back to Garmin (creating dives, editing tags, updating gear).
- Per-dive depth/time-series profiles (would require parsing `.fit` files).
- Live during-dive data — there is none; the watch uploads on surface.

## 2. User context

- Two HA users / two Garmin accounts: **Rob** (Descent Mk2i + Descent T1 transmitter) and **Ana** (Descent Mk2s).
- ~20 dives/year, almost always concentrated in 1–2 trips.
- Dashboard intent: a yearly timeline of dive cards with photos, plus a gear-status panel.

## 3. External APIs (from captured iOS Dive app traffic, app v3.4.1)

### 3.1 Authentication

- Login: Garmin SSO (`sso.garmin.com`) → Connect OAuth1 → OAuth2 token exchange. Out of scope for this spec — handled by `garth` library, identical to the existing HACS Garmin Connect integration.
- Dive-scope token: `POST https://connectapi.garmin.com/oauth-service/oauth/exchange/user/2.0` with body `audience=DIVE_MOBILE_IOS_DI`. Returns a bearer scoped to `DIVE_API_READ DIVE_API_WRITE CONNECT_READ CONNECT_WRITE …`. Used as `Authorization: bearer …` against `gcs.garmin.com`.
- Refresh: `POST https://diauth.garmin.com/di-oauth2-service/oauth/token` with `grant_type=refresh_token&refresh_token=…&client_id=DIVE_MOBILE_IOS_DI`. Access token TTL ≈ 24h, refresh token TTL ≈ 30d.

### 3.2 Dive REST endpoints (`gcs.garmin.com`)

| Endpoint | Returns |
|---|---|
| `GET /diving/v1/dive/summary?requestedPage=0&resultsPerPage=100` | `totalCount` + paginated dive activities. Per-dive: `id`, `connectActivityId`, `name`, `diveType`, `number`, `startTime`, `timezone`, `totalTime`, `maxDepth`, `bottomTime`, `surfaceInterval`, `diveTags[]`, `gases[]`, `entryLoc.{latitude,longitude}` (some dives), `activitySource`, `contentVisibility`. |
| `GET /diving/v1/dive/devices` | List of dive computers + transmitters: `productDisplayName`, `partNumber`, `serialNumber`, `type` (`DIVE_COMPUTER`/`TRANSMITTER`), `gearTrackingStatus`, `imageUrl`, `antChannelId` for transmitters. |
| `GET /diving/v1/dive/tags` | `{ TAG_NAME: count }` for ~22 tag types (RECREATIONAL, DEEP, NIGHT, WARM_WATER, COLD_WATER, WRECK, etc.) |
| `GET /diving/v1/gear/summary?current-user-date=YYYY-MM-DD&gear-types=BCD&gear-types=…&gear-types=OTHER` | Lightweight list of all gear: `gearId`, `name`, `type`, `dateOfFirstUse`, `status`, basic `stats`, primary `image` with expiring S3 URLs. |
| `GET /diving/v1/gear/{gearId}?current-user-date=YYYY-MM-DD` | Full gear: `brand`, `model`, `serialNumber`, service record (`dueIndicator`, `lastServiceDate`, `serviceIntervalDays`, `lastServicedBy`, `nextServiceDate`, `nextServiceDueIndicator`), purchase record (`purchasePrice`, `purchaseCurrency`, `purchasedFrom`, `purchaseDate`), `gearField` (type-specific fields, e.g. regulator type/connector, light bulb/lumens), `media.images[]`. |

### 3.3 GraphQL (`POST gcs.garmin.com/diving/graphql/query`)

JSON body: `{ operationName, query, variables, extensions }`.

- `DiveReadinessByDate` — observed; returns `null` when no recent dive. Out of scope for v1.
- Dive photos operation — observed in user-pasted response (operation name not in capture; the response includes `__typename:"Image"`, `imageUUID`, `eventDate`, `entityReferenceId`, `owner.{profileName,playerProfileId}`, `versionedUrls[]` with sizes `SMALL_THUMBNAIL` / `MEDIUM_FEED` / `LARGE` and S3 pre-signed URLs (`X-Amz-Expires=86399`)). Operation name to be discovered at implementation time via Burp capture of the Photos screen. **Implementation must be resilient to operation rename** by treating the GQL call site as a single function with a constant pinned at the top of `api.py`.

### 3.4 Gear types enum

`BCD, BOOTS, BUOY, CAMERA, CERTIFICATION, CUTTING_TOOL, DIVE_COMPUTER, EXPOSURE_SUIT, FIN, GLOVE, HOOD, LIGHT, MASK, REBREATHER, REGULATOR, SCOOTER, SLATE, SNORKEL, SPEAR, SPOOL, TANK, TRANSMITTER, UNDERGARMENT, WEIGHT, OTHER`

## 4. Architecture

```
HA config entry (one per Garmin account)
        │
        ▼
GarminDiveAuth ── garth ──► Garmin SSO + OAuth1→OAuth2 exchange
        │   ├─ Connect bearer
        │   └─ Dive bearer (audience=DIVE_MOBILE_IOS_DI, used against gcs.garmin.com)
        ▼
GarminDiveClient ── HTTP / GraphQL ──► gcs.garmin.com / diauth.garmin.com / connectapi.garmin.com
        │
        ▼
GarminDiveCoordinator (DataUpdateCoordinator, default 2h)
        │  • dive summary (resultsPerPage=100)
        │  • dive devices, dive tags
        │  • gear summary, gear detail (delta-fetch by lastModifiedTs)
        │  • dive images (GraphQL)
        │  • photo cache reconciler
        ▼
PhotoCache ── writes ──► config/www/garmin_dive/<account>/<imageUUID>_<size>.jpg
        ▼
Entities (sensor / binary_sensor / calendar / button) registered against
HA device for the account + sub-devices for each dive computer + each gear item
```

### 4.1 Module boundaries

| Module | Responsibility | Depends on |
|---|---|---|
| `auth.py` | `GarminDiveAuth`: garth login/MFA, audience exchange, token refresh, persistence to entry data, reauth signalling. | `garth`, HA config entries |
| `api.py` | `GarminDiveClient`: typed REST + GraphQL methods. No HA imports. Single point of HTTP I/O. | `aiohttp`, `auth.py` |
| `photos.py` | `PhotoCache`: download + dedupe by UUID, idempotent writes, expiry-aware refresh of GraphQL signed URLs. | `aiohttp`, `pathlib` |
| `gear.py` | Gear-specific transforms: list → diff vs last-cycle state → list of gear IDs needing detail fetch. Pure functions. | nothing |
| `coordinator.py` | `GarminDiveCoordinator(DataUpdateCoordinator)`: orchestrates one refresh cycle. | `api.py`, `photos.py`, `gear.py` |
| `entity.py` | `GarminDiveAccountEntity`, `GarminDiveDeviceEntity` base classes — handle `device_info`, unique IDs, availability. | HA helpers |
| `sensor.py` / `binary_sensor.py` / `calendar.py` / `button.py` | Platform modules; thin `from_data(...)` factories. | `entity.py`, `coordinator.py` |
| `config_flow.py` | `async_step_user`, `async_step_mfa`, `async_step_reauth`, options flow. | `auth.py` |
| `diagnostics.py` | `async_get_config_entry_diagnostics` with token redaction. | none |

`api.py` and `auth.py` deliberately have no HA dependencies so they can be exercised under plain pytest without the HA event loop.

## 5. Authentication & config flow

### 5.1 Initial login

1. `async_step_user`: form fields `email`, `password`. Calls `garth.login(...)` in a thread executor.
2. If `garth` raises `NeedMFAException`, advance to `async_step_mfa` with a `code` field. Re-call login with the code.
3. On success: persist garth's `oauth1_token` + `oauth2_token` (Connect) to `entry.data` under a `garth_session` key. Immediately request a Dive-scoped token (`audience=DIVE_MOBILE_IOS_DI`) and store under `dive_token`. Resolve the user's `profile_id` via `/userprofile-service/socialProfile/v2` and use it as the unique-ID source for the config entry (`unique_id=str(profile_id)`).
4. Friendly title: "Garmin Dive — &lt;displayName&gt;".

### 5.2 Token lifecycle

- `GarminDiveAuth.get_dive_token()` returns the cached token, eagerly refreshing within a 5-min skew of `expires_in`.
- A 401 from any API call triggers one forced refresh + retry. A second 401 raises `ConfigEntryAuthFailed`, kicking the reauth flow.

### 5.3 Reauth

- `async_step_reauth_confirm`: prompts for password (and MFA if challenged) without removing the entry, preserving entity IDs and history.

### 5.4 Options flow

| Option | Default | Range |
|---|---|---|
| `scan_interval_minutes` | 120 | 5–360 |
| `photo_cache_enabled` | true | bool |
| `history_scope` | `current_year_plus_one` | `current_year` / `current_year_plus_one` / `all_time` |
| `max_cache_age_days` | 0 (never evict) | 0–3650 |

### 5.5 Multi-account

- One config entry per Garmin account; one `garth.Client` per entry; no shared mutable state. Two parallel coordinators run independently.

## 6. Data flow / refresh

### 6.1 Coordinator cycle

Each tick (default 2 h; configurable 5 min – 6 h via options flow; manual `button.refresh` is the trip-day path) fans out the calls in parallel:

1. `GET /diving/v1/dive/summary?requestedPage=0&resultsPerPage=100` — single call returns `totalCount` and the entire activity list (a 68-dive locker fits in one response). Pagination loop only kicks in if `totalCount > pageSize` and `history_scope == all_time`.
2. `GET /diving/v1/dive/devices` — cheap.
3. `GET /diving/v1/dive/tags` — cheap.
4. `GET /diving/v1/gear/summary?current-user-date=<today>&gear-types=…` — list of all gear.
5. **Delta-fetch** `GET /diving/v1/gear/{gearId}` only for gear items whose `lastModifiedTs` differs from the version held in coordinator state. On first run after install, all gear items are fetched once.
6. `POST /diving/graphql/query` for the dive-photos operation — only invoked when (a) there are dives whose photo metadata is unknown, or (b) photo metadata is older than 12h.

Total: 4 unconditional calls + ≤ K conditional calls (K ≈ 0 in steady state, ≈ N gear items on first install).

### 6.2 Caching & change detection

- `total_dives` mismatch since last cycle ⇒ re-render dive entities, fire `garmin_dive_new_dive` events for newly-seen `dive.id` values.
- Gear items where `dueIndicator` flipped to `DUE` or `OVERDUE` ⇒ fire `garmin_dive_service_due`.
- Coordinator stores last-known state in `entry.runtime_data` (HA 2024.10+ pattern).

### 6.3 Failure handling

- Network/timeout: bubble as `UpdateFailed`; HA marks entities unavailable; next cycle retries.
- 401: forced token refresh + one retry (see §5.2).
- 5xx with `Retry-After`: respect header up to 5 min, otherwise back off via HA's coordinator default behaviour.

## 7. Entity model

### 7.1 Device tree

Each Garmin account is a top-level HA Device. Dive computers (from `/dive/devices`) and gear items (from `/gear/summary`) are sub-devices linked via `via_device`.

```
Garmin Dive — Rob
├── Descent Mk2i              (DIVE_COMPUTER, serial 3403334227, image from Garmin CDN)
├── Descent T1                (TRANSMITTER, serial 3399109144, ANT channel 356952664)
├── Apeks Double Gauge SPG    (REGULATOR, serviced 2025-04-04, due 2027-04-04)
├── Atomic B2 Regulator       (REGULATOR, DIN, piston, serial 1CA0062)
├── LetonPower Sealion L24    (LIGHT, photography, HID, 12000 lumen)
├── Miflex Hose Extension     (OTHER, 15cm)
├── Underwater iPhone Housing (CAMERA)
└── Deep Diver                (CERTIFICATION)
```

### 7.2 Account-level entities

| Platform | Entity (suffix) | State | Notes |
|---|---|---|---|
| `sensor` | `last_dive` | dive name | attributes: full last-dive payload incl. depth, bottom_time, total_time, gases, tags, photo URLs, connect_url |
| `sensor` | `total_dives` | int | from `summary.totalCount` |
| `sensor` | `current_year_dives` | int | rolling-evaluated; resets at midnight 1 Jan local time |
| `sensor` | `dives_by_tag` | int (sum) | attributes: per-tag counts |
| `sensor` | `last_dive_max_depth` | float | `device_class=distance`, `native_unit_of_measurement="m"`; HA auto-converts to feet for users on imperial. |
| `sensor` | `last_dive_bottom_time` | float, minutes | `device_class=duration`, `native_unit_of_measurement="min"` |
| `sensor` | `last_dive_surface_interval` | float, hours | `device_class=duration`, `native_unit_of_measurement="h"` |
| `sensor` | `dive_log_year` | int (count this year) | **The big one.** `attributes.dives = [{id, name, start, end, timezone, max_depth, average_depth, bottom_time, total_time, surface_interval, tags, gases, location:{lat,lng}|null, photos:{thumb,medium,large}, connect_url, dive_computer}, …]`. Powers the horizontally-scrolling year timeline. (See §13 for the `average_depth` source.) |
| `sensor` | `gear_count` | int | attributes: per-type breakdown (REGULATOR=2, LIGHT=1, …) |
| `binary_sensor` | `new_dive_available` | on/off | latches on after `total_dives` increments; cleared on next refresh after acknowledgment via service call |
| `binary_sensor` | `service_due` | on/off | on whenever any gear has `dueIndicator ∈ {DUE, OVERDUE}` |
| `calendar` | `garmin_dives` | next event | one calendar event per dive: `start = startTime`, `end = startTime + totalTime`, `summary = name`, `description` = stats markdown, `location` = timezone city |
| `button` | `refresh` | — | forces an immediate coordinator refresh |

### 7.3 Per-dive-computer entities (sub-devices)

| Platform | Entity | Source |
|---|---|---|
| `sensor` | `gear_tracking_status` | `gearTrackingStatus` |
| `sensor` (diagnostic) | `serial_number` | `serialNumber` |
| `sensor` (diagnostic) | `part_number` | `partNumber` |

`device_info` includes `model`, `manufacturer="Garmin"`, `configuration_url=https://connect.garmin.com/modern/devices/<serialNumber>` (best-effort), `entity_picture` from Garmin's `imageUrl`.

### 7.4 Per-gear-item entities (sub-devices)

| Platform | Entity | Notes |
|---|---|---|
| `sensor` | `service_status` | `dueIndicator`: `not_due` / `due` / `overdue`. Skipped when no `serviceIntervalDays`. |
| `sensor` | `days_until_service` | `(nextServiceDate - today).days`. Skipped when no service record. |
| `sensor` | `next_service_date` | timestamp class. Skipped when no service record. |
| `sensor` | `last_service_date` | diagnostic. |
| `sensor` | `dives_with` | `stats.numAssociatedDives` |
| `sensor` | `total_dive_time` | `stats.totalAssociatedDiveTime` (seconds → hours) |
| `sensor` (diagnostic) | `purchase_date` | from `purchaseDate` |
| `sensor` (diagnostic) | `purchase_price` | with `purchaseCurrency` unit |

`device_info` includes `manufacturer = brand`, `model = model`, `serial_number = serialNumber`, `entity_picture` = locally-cached `MEDIUM_FEED` image when available.

### 7.5 Events

| Event | Payload | Trigger |
|---|---|---|
| `garmin_dive_new_dive` | `{ account_id, profile_id, dive }` | a new dive id appeared in `/dive/summary` |
| `garmin_dive_service_due` | `{ account_id, profile_id, gear }` | a gear `dueIndicator` flipped to `DUE` or `OVERDUE` |

## 8. Photo cache

- **Path:** `config/www/garmin_dive/<account_short>/<imageUUID>_<size>.<ext>` where `<account_short>` = first 8 chars of profile_id, `<size>` ∈ `{thumb, medium, large}` mapping from `SMALL_THUMBNAIL`/`MEDIUM_FEED`/`LARGE`, `<ext>` from URL filename (`.jpeg`/`.png`).
- **HA URL:** `/local/garmin_dive/<account_short>/<imageUUID>_<size>.<ext>` — stable, never expires.
- **Download path:** at coordinator-cycle end, for each `(imageUUID, size)` pair without a local file, download from the (still-fresh) Garmin signed URL via the shared `aiohttp` session.
- **Concurrency:** capped at 2 concurrent downloads (`asyncio.Semaphore(2)`) to be polite to S3.
- **Idempotency:** skip if file exists. Photos are immutable once uploaded.
- **Eviction:** none by default. Optional `max_cache_age_days` option for opt-in pruning.
- **Disable path:** when `photo_cache_enabled=false`, attribute URLs fall back to live signed Garmin URLs (which work for ≤24h post-fetch).
- **Failure:** download failures log a warning, do not fail the cycle. Next cycle retries.
- **Storage estimate:** ~5 photos/dive × ~20 dives/year × ~500KB × 3 sizes ≈ ~150MB/year/account.

## 9. Repository layout

```
ha-garmin-dive/
├── .github/
│   ├── workflows/
│   │   ├── validate.yml         # hassfest + HACS Validate (run on push/PR)
│   │   ├── lint.yml             # ruff (lint+format), mypy, codespell
│   │   ├── test.yml             # pytest with pytest-homeassistant-custom-component, py3.12 + py3.13 matrix
│   │   └── release.yml          # tag-triggered: bump manifest version, zip, attach to GH release
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   └── feature_request.yml
│   ├── dependabot.yml
│   └── CODEOWNERS
├── custom_components/
│   └── garmin_dive/
│       ├── __init__.py          # async_setup_entry / async_unload_entry / async_migrate_entry
│       ├── manifest.json
│       ├── const.py
│       ├── auth.py
│       ├── api.py
│       ├── photos.py
│       ├── gear.py
│       ├── coordinator.py
│       ├── entity.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── calendar.py
│       ├── button.py
│       ├── config_flow.py
│       ├── diagnostics.py
│       ├── services.yaml
│       ├── strings.json
│       ├── icons.json
│       └── translations/en.json
├── tests/
│   ├── conftest.py
│   ├── fixtures/                # JSON fixtures sanitised from Burp captures
│   │   ├── dive_summary.json
│   │   ├── dive_devices.json
│   │   ├── dive_tags.json
│   │   ├── gear_summary.json
│   │   ├── gear_detail_regulator.json
│   │   ├── gear_detail_light.json
│   │   ├── gear_detail_transmitter.json
│   │   └── dive_images_graphql.json
│   ├── test_api.py
│   ├── test_auth.py
│   ├── test_config_flow.py
│   ├── test_coordinator.py
│   ├── test_gear.py
│   ├── test_photos.py
│   └── test_sensor.py
├── docs/
│   └── superpowers/specs/
│       └── 2026-05-03-ha-garmin-dive-design.md   ← this file
├── hacs.json
├── info.md
├── README.md
├── LICENSE                      # MIT
├── pyproject.toml               # ruff/mypy/pytest config
├── requirements_dev.txt
├── .pre-commit-config.yaml
└── .gitignore
```

### 9.1 `manifest.json` highlights

```json
{
  "domain": "garmin_dive",
  "name": "Garmin Dive",
  "version": "0.1.0",
  "codeowners": ["@robemmerson"],
  "config_flow": true,
  "documentation": "https://github.com/robemmerson/ha-garmin-dive",
  "issue_tracker": "https://github.com/robemmerson/ha-garmin-dive/issues",
  "iot_class": "cloud_polling",
  "integration_type": "hub",
  "requirements": ["garth>=0.5.0"]
}
```

### 9.2 `hacs.json`

```json
{
  "name": "Garmin Dive",
  "render_readme": true,
  "homeassistant": "2026.1.0"
}
```

## 10. CI / release pipeline

- **`validate.yml`** — runs `home-assistant/actions/hassfest@master` and `hacs/action@main` (`category: integration`). Required for HACS listing.
- **`lint.yml`** — ruff (lint + format check), mypy strict on `custom_components/garmin_dive`, codespell.
- **`test.yml`** — matrix: py3.12, py3.13. Installs `pytest-homeassistant-custom-component` to spin up an HA stub; tests run config flow, coordinator, gear/photo modules against fixtures.
- **`release.yml`** — triggers on `v*` tag push: extracts version, syncs `manifest.json`, builds zip of `custom_components/garmin_dive/`, attaches to GitHub release. HACS picks it up via the GitHub release feed.
- **`dependabot.yml`** — weekly updates for `pip` and `github-actions`.
- **`CODEOWNERS`** — required by hassfest.

## 11. Tests

- **Unit (no HA):** `api.py`, `auth.py`, `gear.py`, `photos.py` against captured JSON fixtures with `aresponses`/`aiohttp` test utilities.
- **Integration (HA stub):** config flow happy path + MFA + reauth; coordinator → entities for each platform; gear-detail delta-fetch; photo cache idempotency; service-due event firing.
- **Snapshot tests** for entity state dicts (using `syrupy`) — guards against accidental drift.
- All HTTP fixtures captured from this Burp session, with tokens / serials / signed URLs / personal data scrubbed by a `tests/scripts/scrub.py` helper.

## 12. Implementation phasing

Phase boundaries are guidance for the writing-plans pass; the integration ships as one PR.

1. Skeleton + auth (config flow, garth wrapper, audience exchange, reauth) — boot to a working but data-less integration.
2. API client + coordinator — fetch summary/devices/tags + build account-level sensors.
3. Calendar entity + `dive_log_year` rich sensor.
4. Photo cache (REST + GraphQL).
5. Gear list + gear detail + per-gear sub-devices and sensors.
6. Events (`new_dive`, `service_due`) + button + diagnostics + service calls.
7. CI workflows, README with dashboard examples (calendar card + auto-entities scrolling cards), HACS metadata, release pipeline.

## 13. Open questions / things to confirm during implementation

- **Dive-photos GraphQL operation name.** Capture from the Photos screen during phase 4.
- **`average_depth` source.** Not present in `/dive/summary`. Likely available via a per-dive detail endpoint (probable shape: `GET /diving/v1/dive/activity/{id}` or via a `DiveActivity` GraphQL operation) — to be discovered by capturing the Dive Detail screen during phase 3. Fetch is per-new-dive only (one extra call per dive added since last cycle); steady-state cost is zero. If no field surfaces it directly, fall back to omitting `average_depth` (do **not** estimate from `max_depth` — would mislead divers).
- **`dive.activitySource` mapping to a specific dive computer.** Inspect `/dive/summary` payloads with both Mk2i and Mk2s data; if the source field doesn't disambiguate, the per-dive-computer device entities stay limited to identity/tracking sensors and dive metrics remain on the account.
- **Gear `lastModifiedTs` granularity.** Confirm whether the gear summary endpoint returns `lastModifiedTs` (the captured payload showed it on detail responses but not in summary). If summary lacks it, fall back to fetching detail every cycle for a small constant N (≤ ~10 items expected).

## 14. Acceptance criteria

- Two HA users can each add their Garmin account; integration creates one device per account plus sub-devices for each dive computer and gear item.
- Restart-stable: tokens persist; entities reappear with same IDs.
- `sensor.dive_log_year` exposes a rich attribute list usable by `auto-entities` + a markdown / mushroom card to render the year-of-dives card strip described in §2.
- `calendar.garmin_dives_<account>` shows each dive as an event in the HA calendar card.
- Service-due gear surfaces via the binary sensor and the `garmin_dive_service_due` event.
- New dives within the polling window fire `garmin_dive_new_dive`.
- HACS validation, hassfest, lint, and tests all green in CI.
