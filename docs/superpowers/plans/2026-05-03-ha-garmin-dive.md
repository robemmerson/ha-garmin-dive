# ha-garmin-dive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a HACS-installable Home Assistant integration that surfaces Garmin Dive activity + dive-gear data for one-or-more Garmin accounts, including a yearly dive timeline and locally-cached photos.

**Architecture:** Per Garmin account, a single `DataUpdateCoordinator` polls the Dive REST API + a GraphQL photo operation against `gcs.garmin.com`. Auth via `ha-garmin` (SSO + MFA-aware via `curl_cffi` TLS impersonation) + a `DIVE_MOBILE_IOS_DI` audience exchange. Photos cached to `config/www/garmin_dive/`. Each dive computer and gear item is registered as an HA sub-device under the account device.

**Tech Stack:** Python 3.13+, Home Assistant 2026.1+, `ha-garmin>=0.1.19` (replaces the deprecated `garth`), `aiohttp` (HA-provided), `pytest-homeassistant-custom-component`, `ruff`, `mypy`, `syrupy` (snapshots), GitHub Actions, HACS.

**Spec:** [`docs/superpowers/specs/2026-05-03-ha-garmin-dive-design.md`](../specs/2026-05-03-ha-garmin-dive-design.md)

---

## Notes for the implementing agent

- **All commits use Conventional Commits** (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `ci:`, `build:`).
- **Never add Claude attribution to commit messages** — author/co-author trailers about Claude are forbidden by the user's CLAUDE.md.
- **Never run `--no-verify`, `--no-gpg-sign`, or other hook/sign-bypassing flags.** If a hook fails, fix the underlying issue.
- **Frequent commits.** Commit after each task in the plan.
- **TDD where it applies:** every task that produces logic has a failing test first. Tasks that produce config files (manifest, YAML workflows) don't need TDD — their validation is the CI run.
- **Reference docs (open these tabs):**
  - HA Integration scaffold: <https://developers.home-assistant.io/docs/creating_integration_file_structure>
  - DataUpdateCoordinator: <https://developers.home-assistant.io/docs/integration_fetching_data>
  - Config flow: <https://developers.home-assistant.io/docs/config_entries_config_flow_handler>
  - Entity types: <https://developers.home-assistant.io/docs/core/entity>
  - HACS publishing: <https://www.hacs.xyz/docs/publish/integration>
  - hassfest: <https://developers.home-assistant.io/docs/creating_integration_manifest>
  - ha-garmin library: <https://pypi.org/project/ha-garmin/> (the active replacement for the deprecated [garth](https://github.com/matin/garth/discussions/222))
- **Working directory:** `/Users/rob.emmerson/git/ha-garmin-dive` (already initialised as a git repo with `main` branch).

---

## Task 1: Bootstrap project files (LICENSE, .gitignore, pyproject.toml, requirements_dev.txt)

**Files:**
- Create: `LICENSE`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `requirements_dev.txt`

- [ ] **Step 1: Write `LICENSE`** (MIT, 2026 Rob Emmerson)

```
MIT License

Copyright (c) 2026 Rob Emmerson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Editors
.vscode/
.idea/
*.swp
*.swo

# Home Assistant
.HA_VERSION
home-assistant.log*
config/.storage/
config/deps/

# OS
.DS_Store
Thumbs.db

# Local
.env
.venv/
venv/
```

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[project]
name = "ha-garmin-dive"
version = "0.1.0"
description = "Home Assistant integration for Garmin Dive activity and gear data"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.12"
authors = [{ name = "Rob Emmerson" }]

[tool.ruff]
target-version = "py312"
line-length = 100
extend-exclude = ["tests/fixtures"]

[tool.ruff.lint]
select = [
    "E", "F", "W",      # pycodestyle + pyflakes
    "I",                # isort
    "B",                # bugbear
    "UP",               # pyupgrade
    "ASYNC",            # async checks
    "RUF",              # ruff-specific
    "SIM",              # simplify
    "TID",              # tidy imports
    "PL",               # pylint
]
ignore = [
    "PLR0913",  # too many args (HA entities legitimately take many)
    "PLR2004",  # magic numbers
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["PLR2004", "S101"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_configs = true
disallow_any_generics = true
disallow_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
files = ["custom_components/garmin_dive"]

[[tool.mypy.overrides]]
module = ["ha_garmin.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra --strict-markers"
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:homeassistant.*",
]
```

- [ ] **Step 4: Write `requirements_dev.txt`**

```
homeassistant>=2026.1.0
pytest>=8.0
pytest-asyncio>=0.23
pytest-homeassistant-custom-component>=0.13
pytest-cov>=5.0
syrupy>=4.6
aresponses>=3.0
ruff>=0.7
mypy>=1.10
codespell>=2.3
pre-commit>=3.7
ha-garmin>=0.1.19
```

- [ ] **Step 5: Commit**

```bash
git add LICENSE .gitignore pyproject.toml requirements_dev.txt
git commit -m "chore: bootstrap repo with license, gitignore, and dev tooling"
```

---

## Task 2: HACS metadata + README skeleton

**Files:**
- Create: `hacs.json`
- Create: `info.md`
- Create: `README.md`

- [ ] **Step 1: Write `hacs.json`**

```json
{
  "name": "Garmin Dive",
  "render_readme": true,
  "homeassistant": "2026.1.0",
  "country": ["GB", "US"]
}
```

- [ ] **Step 2: Write `info.md`** (shown on the HACS card)

```markdown
# Garmin Dive

Home Assistant integration for **Garmin Dive** activity and gear data.

Designed to coexist with the standard HACS Garmin Connect integration — this one only fetches dive-specific data (dive activities, gear, dive-photo gallery). Per-account device and sub-devices for each dive computer and gear item.

## Features

- Per-account: `last_dive`, `total_dives`, `current_year_dives`, `dives_by_tag`, depth/time stats
- `sensor.dive_log_year` rich-attribute sensor for building horizontally-scrolling dive timeline cards
- `calendar.garmin_dives` — every dive as a calendar event
- Per-gear-item sub-devices with service-status + lifetime-usage sensors
- `binary_sensor.service_due` flips on when any gear is due/overdue
- Photos cached locally so dashboards never hit expiring S3 URLs
- MFA-aware login via `ha-garmin`
- Multi-account ready

## Configuration

Settings → Devices & services → Add integration → "Garmin Dive". Sign in with email/password (and MFA code if your Garmin account has it enabled). Repeat for each Garmin account you want to track.

See README on GitHub for dashboard examples.
```

- [ ] **Step 3: Write `README.md` skeleton** (Task 43 fills the dashboard section)

```markdown
# ha-garmin-dive

Home Assistant integration for [Garmin Dive](https://www.garmin.com/en-GB/c/sports-fitness/diving/) activity and gear data, distributed via [HACS](https://www.hacs.xyz/).

## Status

Pre-1.0 — APIs reverse-engineered from the iOS Dive app v3.4.1.

## Installation

### HACS (recommended)

1. In HACS, open ⋮ → "Custom repositories".
2. Add `https://github.com/robemmerson/ha-garmin-dive` with category **Integration**.
3. Install **Garmin Dive**, restart Home Assistant.
4. Settings → Devices & services → Add integration → "Garmin Dive". Sign in. Repeat for each account.

### Manual

Copy `custom_components/garmin_dive/` into your HA config's `custom_components/` and restart.

## Configuration

Email + password. If your Garmin account has MFA, you'll be prompted for the code. Tokens are persisted in HA's config entry storage and refreshed automatically; if the refresh token expires (~30 days), HA prompts for re-auth.

### Options

| Option | Default | Range |
|---|---|---|
| Polling interval (minutes) | 120 | 5–360 |
| Photo cache enabled | true | boolean |
| History scope | current year + previous year | current year / current year + previous / all time |
| Max cache age (days) | 0 (never evict) | 0–3650 |

## Entities

(See `docs/superpowers/specs/2026-05-03-ha-garmin-dive-design.md` for the full table.)

## Dashboard

See the **Dashboard** section below — *populated in Task 43*.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_dev.txt
pre-commit install
pytest
```

## License

MIT — see `LICENSE`.
```

- [ ] **Step 4: Commit**

```bash
git add hacs.json info.md README.md
git commit -m "docs: add HACS metadata and README skeleton"
```

---

## Task 3: Integration manifest, const.py, and Python package skeleton

**Files:**
- Create: `custom_components/garmin_dive/__init__.py` (skeleton; expanded in Task 33)
- Create: `custom_components/garmin_dive/manifest.json`
- Create: `custom_components/garmin_dive/const.py`
- Create: `custom_components/__init__.py` (empty namespace marker for tests to import the package)

- [ ] **Step 1: Write `custom_components/__init__.py`** (empty file)

```python
```

- [ ] **Step 2: Write `custom_components/garmin_dive/manifest.json`**

```json
{
  "domain": "garmin_dive",
  "name": "Garmin Dive",
  "version": "0.1.0",
  "codeowners": ["@robemmerson"],
  "config_flow": true,
  "dependencies": [],
  "documentation": "https://github.com/robemmerson/ha-garmin-dive",
  "issue_tracker": "https://github.com/robemmerson/ha-garmin-dive/issues",
  "iot_class": "cloud_polling",
  "integration_type": "hub",
  "requirements": ["ha-garmin>=0.1.19"]
}
```

- [ ] **Step 3: Write `custom_components/garmin_dive/const.py`**

```python
"""Constants for the Garmin Dive integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "garmin_dive"

# --- Endpoint hosts ----------------------------------------------------------

HOST_DIAUTH: Final = "https://diauth.garmin.com"
HOST_CONNECT_API: Final = "https://connectapi.garmin.com"
HOST_GCS: Final = "https://gcs.garmin.com"

# --- OAuth -------------------------------------------------------------------

DIVE_OAUTH_AUDIENCE: Final = "DIVE_MOBILE_IOS_DI"
DIVE_OAUTH_CLIENT_ID: Final = "DIVE_MOBILE_IOS_DI"
TOKEN_REFRESH_SKEW_SECONDS: Final = 300  # refresh if within 5 min of expiry

# --- App identity (matches captured iOS Dive 3.4.1 traffic) ------------------

APP_USER_AGENT: Final = "Dive/3.4 (com.garmin.Dive; build:1; iOS 26.4.2) Alamofire/5.9.1"
APP_X_APP_VER: Final = "3.4"
APP_X_LANG: Final = "en"

# --- Dive REST paths ---------------------------------------------------------

PATH_DIVE_SUMMARY: Final = "/diving/v1/dive/summary"
PATH_DIVE_DEVICES: Final = "/diving/v1/dive/devices"
PATH_DIVE_TAGS: Final = "/diving/v1/dive/tags"
PATH_GEAR_SUMMARY: Final = "/diving/v1/gear/summary"
PATH_GEAR_DETAIL: Final = "/diving/v1/gear/{gear_id}"
PATH_GRAPHQL: Final = "/diving/graphql/query"

# --- Connect API paths -------------------------------------------------------

PATH_OAUTH_EXCHANGE: Final = "/oauth-service/oauth/exchange/user/2.0"
PATH_SOCIAL_PROFILE_V2: Final = "/userprofile-service/socialProfile/v2"

# --- diauth paths ------------------------------------------------------------

PATH_OAUTH_TOKEN: Final = "/di-oauth2-service/oauth/token"
PATH_OAUTH_REVOKE: Final = "/di-oauth2-service/token/revoke"

# --- Gear types (iOS app sends every type as a query param on /gear/summary) -

GEAR_TYPES: Final = (
    "BCD",
    "BOOTS",
    "BUOY",
    "CAMERA",
    "CERTIFICATION",
    "CUTTING_TOOL",
    "DIVE_COMPUTER",
    "EXPOSURE_SUIT",
    "FIN",
    "GLOVE",
    "HOOD",
    "LIGHT",
    "MASK",
    "REBREATHER",
    "REGULATOR",
    "SCOOTER",
    "SLATE",
    "SNORKEL",
    "SPEAR",
    "SPOOL",
    "TANK",
    "TRANSMITTER",
    "UNDERGARMENT",
    "WEIGHT",
    "OTHER",
)

# Gear types where service tracking is meaningful. CAMERA, LIGHT,
# CERTIFICATION, etc. typically have no service interval.
SERVICEABLE_GEAR_TYPES: Final = frozenset(
    {"REGULATOR", "BCD", "TRANSMITTER", "REBREATHER", "TANK"}
)

# --- Options keys ------------------------------------------------------------

CONF_SCAN_INTERVAL_MINUTES: Final = "scan_interval_minutes"
CONF_PHOTO_CACHE_ENABLED: Final = "photo_cache_enabled"
CONF_HISTORY_SCOPE: Final = "history_scope"
CONF_MAX_CACHE_AGE_DAYS: Final = "max_cache_age_days"

DEFAULT_SCAN_INTERVAL_MINUTES: Final = 120
DEFAULT_PHOTO_CACHE_ENABLED: Final = True
DEFAULT_HISTORY_SCOPE: Final = "current_year_plus_one"
DEFAULT_MAX_CACHE_AGE_DAYS: Final = 0

HISTORY_SCOPE_CHOICES: Final = ("current_year", "current_year_plus_one", "all_time")

# --- Photo cache -------------------------------------------------------------

PHOTO_CACHE_DIR_NAME: Final = "garmin_dive"  # placed under config/www/
PHOTO_CACHE_CONCURRENCY: Final = 2

# --- Events ------------------------------------------------------------------

EVENT_NEW_DIVE: Final = "garmin_dive_new_dive"
EVENT_SERVICE_DUE: Final = "garmin_dive_service_due"

# --- Platforms ---------------------------------------------------------------

PLATFORMS: Final = ("sensor", "binary_sensor", "calendar", "button")
```

- [ ] **Step 4: Write skeleton `custom_components/garmin_dive/__init__.py`** (Task 33 expands this)

```python
"""Garmin Dive integration for Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garmin Dive from a config entry. (skeleton; expanded later)."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Garmin Dive config entry. (skeleton; expanded later)."""
    return True
```

- [ ] **Step 5: Sanity check the package imports**

Run: `python -c "import sys; sys.path.insert(0, '.'); from custom_components.garmin_dive import const; print(const.DOMAIN)"`
Expected: `garmin_dive`

- [ ] **Step 6: Commit**

```bash
git add custom_components/
git commit -m "feat: add integration skeleton, manifest, and constants"
```

---

## Task 4: Test fixtures (scrubbed JSON from captured Burp traffic)

**Files:**
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Create: `tests/fixtures/dive_summary_one.json`
- Create: `tests/fixtures/dive_summary_full.json`
- Create: `tests/fixtures/dive_devices.json`
- Create: `tests/fixtures/dive_tags.json`
- Create: `tests/fixtures/gear_summary.json`
- Create: `tests/fixtures/gear_detail_regulator.json`
- Create: `tests/fixtures/gear_detail_light.json`
- Create: `tests/fixtures/gear_detail_transmitter.json`
- Create: `tests/fixtures/gear_detail_other.json`
- Create: `tests/fixtures/social_profile_v2.json`
- Create: `tests/fixtures/dive_images_graphql.json`

- [ ] **Step 1: Write `tests/__init__.py`** (empty file)

```python
```

- [ ] **Step 2: Write `tests/conftest.py`**

```python
"""Shared pytest fixtures for ha-garmin-dive."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    """Return a callable that loads a JSON fixture by name (without extension)."""

    def _load(name: str) -> Any:
        path = FIXTURES_DIR / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    return _load


# Enable HA test framework for tests that need a HomeAssistant instance.
pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow custom_components/garmin_dive to load in HA tests."""
    return
```

- [ ] **Step 3: Write `tests/fixtures/dive_summary_one.json`** (single dive, paginated request)

```json
{
  "totalCount": 68,
  "pageSize": 1,
  "pageNumber": 0,
  "diveActivities": [
    {
      "id": 23285230,
      "connectActivityId": 20180546488,
      "name": "Elphinstone (South side)",
      "diveType": "SINGLE_GAS",
      "number": 68,
      "excludedFromDLN": false,
      "startTime": "2025-08-26T09:01:37+03:00",
      "timezone": "Africa/Cairo",
      "totalTime": 2807.98,
      "maxDepth": 26.373,
      "bottomTime": 2747.59,
      "diveTags": ["RECREATIONAL", "TRAINING_CERTIFICATION", "WARM_WATER"],
      "activitySource": "GARMIN_DEVICE",
      "gases": [
        {
          "gasStatus": "BOTTOM_GAS",
          "gasType": "AIR",
          "percentOxygen": 21,
          "percentHelium": 0,
          "gasMode": "OPEN_CIRCUIT"
        }
      ],
      "surfaceInterval": 2743,
      "elasticsearchScore": -1.0,
      "contentVisibility": "PRIVATE",
      "connectPrivacy": { "typeId": 3, "typeKey": "subscribers" },
      "hasTSBData": false
    }
  ]
}
```

- [ ] **Step 4: Write `tests/fixtures/dive_summary_full.json`** (3 dives — covers different fields incl. `entryLoc`)

```json
{
  "totalCount": 68,
  "pageSize": 100,
  "pageNumber": 0,
  "diveActivities": [
    {
      "id": 23285230,
      "connectActivityId": 20180546488,
      "name": "Elphinstone (South side)",
      "diveType": "SINGLE_GAS",
      "number": 68,
      "excludedFromDLN": false,
      "startTime": "2025-08-26T09:01:37+03:00",
      "timezone": "Africa/Cairo",
      "totalTime": 2807.98,
      "maxDepth": 26.373,
      "bottomTime": 2747.59,
      "diveTags": ["RECREATIONAL", "TRAINING_CERTIFICATION", "WARM_WATER"],
      "activitySource": "GARMIN_DEVICE",
      "gases": [
        {
          "gasStatus": "BOTTOM_GAS",
          "gasType": "AIR",
          "percentOxygen": 21,
          "percentHelium": 0,
          "gasMode": "OPEN_CIRCUIT"
        }
      ],
      "surfaceInterval": 2743,
      "contentVisibility": "PRIVATE"
    },
    {
      "id": 23285231,
      "connectActivityId": 20180546492,
      "name": "Elphinstone (North side)",
      "diveType": "SINGLE_GAS",
      "entryLoc": { "latitude": 25.31160389073193, "longitude": 34.85996866598725 },
      "number": 67,
      "excludedFromDLN": false,
      "startTime": "2025-08-26T07:33:14+03:00",
      "timezone": "Africa/Cairo",
      "totalTime": 2619.22,
      "maxDepth": 33.492,
      "bottomTime": 2558.17,
      "diveTags": ["RECREATIONAL", "TRAINING_CERTIFICATION", "WARM_WATER"],
      "activitySource": "GARMIN_DEVICE",
      "gases": [
        {
          "gasStatus": "BOTTOM_GAS",
          "gasType": "AIR",
          "percentOxygen": 21,
          "percentHelium": 0,
          "gasMode": "OPEN_CIRCUIT"
        }
      ],
      "surfaceInterval": 68183,
      "contentVisibility": "PRIVATE"
    },
    {
      "id": 23261609,
      "connectActivityId": 20170276106,
      "name": "Dolphin House Dive 2",
      "diveType": "SINGLE_GAS",
      "entryLoc": { "latitude": 24.985758243128657, "longitude": 34.99630426056683 },
      "number": 66,
      "excludedFromDLN": false,
      "startTime": "2025-08-25T11:47:45+03:00",
      "timezone": "Africa/Cairo",
      "totalTime": 3005.39,
      "maxDepth": 15.363,
      "bottomTime": 2944.37,
      "diveTags": ["RECREATIONAL", "WARM_WATER"],
      "activitySource": "GARMIN_DEVICE",
      "gases": [
        {
          "gasStatus": "BOTTOM_GAS",
          "gasType": "AIR",
          "percentOxygen": 21,
          "percentHelium": 0,
          "gasMode": "OPEN_CIRCUIT"
        }
      ],
      "surfaceInterval": 2849,
      "contentVisibility": "PRIVATE"
    }
  ]
}
```

- [ ] **Step 5: Write `tests/fixtures/dive_devices.json`**

```json
[
  {
    "imageUrl": "https://example.invalid/mk2i.png",
    "productDisplayName": "Descent MK2i",
    "partNumber": "006-B3258-00",
    "deviceVersionPk": 904332,
    "serialNumber": 3403334227,
    "type": "DIVE_COMPUTER",
    "gearTrackingStatus": "TRACKED",
    "deviceDismissed": false
  },
  {
    "imageUrl": "https://example.invalid/t1.png",
    "productDisplayName": "Descent T1",
    "antChannelId": 356952664,
    "type": "TRANSMITTER",
    "gearTrackingStatus": "TRACKED",
    "deviceDismissed": false
  },
  {
    "imageUrl": "https://example.invalid/t1.png",
    "productDisplayName": "Descent T1",
    "serialNumber": 3399109144,
    "antChannelId": 356952664,
    "type": "TRANSMITTER",
    "gearTrackingStatus": "TRACKED",
    "deviceDismissed": false
  }
]
```

- [ ] **Step 6: Write `tests/fixtures/dive_tags.json`**

```json
{
  "DEEP": 5,
  "NIGHT": 1,
  "SPEARFISHING": 0,
  "WARM_WATER": 34,
  "FREE_DIVING": 0,
  "POOL": 0,
  "REBREATHER": 0,
  "RIVER_STREAM": 0,
  "WALL": 3,
  "COLD_WATER": 0,
  "SIDEMOUNT": 0,
  "WRECK": 0,
  "ICE": 0,
  "CAVE": 0,
  "DRIFT": 3,
  "TECHNICAL": 0,
  "SCIENTIFIC": 0,
  "MINE": 0,
  "COMMERCIAL": 0,
  "TRAINING_CERTIFICATION": 8,
  "RECREATIONAL": 45,
  "SEARCH_AND_RESCUE": 0
}
```

- [ ] **Step 7: Write `tests/fixtures/gear_summary.json`** (3 representative items)

```json
[
  {
    "gearId": 463947,
    "name": "Deep Diver",
    "type": "CERTIFICATION",
    "dateOfFirstUse": "2025-08-21",
    "status": "ACTIVE",
    "creationTs": "2025-08-22T10:45:48Z",
    "stats": { "numAssociatedDives": 3, "totalAssociatedDiveTime": 8794.561 }
  },
  {
    "gearId": 247811,
    "name": "Underwater iPhone Light",
    "type": "LIGHT",
    "dateOfFirstUse": "2024-04-06",
    "status": "ACTIVE",
    "creationTs": "2024-04-07T07:51:58Z",
    "image": {
      "imageUUID": "315aa699-ea9b-4323-8177-3d8a77b28e24",
      "inappropriateStatus": "PASSED_BY_ALGORITHM",
      "versions": [
        {
          "version": "SMALL_THUMBNAIL",
          "key": "315aa699-smth.jpeg",
          "url": "https://example.invalid/315aa699-smth.jpeg?sig=test",
          "expiresAt": "2026-05-04T02:02:32Z"
        },
        {
          "version": "MEDIUM_FEED",
          "key": "315aa699-mdfd.jpeg",
          "url": "https://example.invalid/315aa699-mdfd.jpeg?sig=test",
          "expiresAt": "2026-05-04T02:02:32Z"
        },
        {
          "version": "LARGE",
          "key": "315aa699-larg.jpeg",
          "url": "https://example.invalid/315aa699-larg.jpeg?sig=test",
          "expiresAt": "2026-05-04T02:02:32Z"
        }
      ]
    },
    "stats": { "numAssociatedDives": 17, "totalAssociatedDiveTime": 51103.05 }
  },
  {
    "gearId": 141548,
    "name": "Atomic B2 Regulator",
    "type": "REGULATOR",
    "dateOfFirstUse": "2023-04-05",
    "status": "ACTIVE",
    "creationTs": "2023-01-08T20:57:36Z",
    "lastModifiedTs": "2025-04-06T10:43:38Z",
    "stats": { "numAssociatedDives": 31, "totalAssociatedDiveTime": 95690.84 }
  }
]
```

- [ ] **Step 8: Write `tests/fixtures/gear_detail_regulator.json`**

```json
{
  "gearId": 141548,
  "name": "Atomic B2 Regulator",
  "type": "REGULATOR",
  "brand": "Atomic Aquatics",
  "model": "B2",
  "serialNumber": "1CA0062",
  "dueIndicator": "NOT_DUE",
  "lastServiceDate": "2025-04-04",
  "serviceIntervalDays": 730,
  "lastServicedBy": "Mike's Dive Store",
  "nextServiceDate": "2027-04-04",
  "nextServiceDueIndicator": "NOT_DUE",
  "dateOfFirstUse": "2023-04-05",
  "purchasePrice": 872.4,
  "purchaseCurrency": "GBP",
  "purchasedFrom": "Mike's Dive Store",
  "purchaseDate": "2022-12-28",
  "surfaceWeight": 1.1,
  "surfaceWeightUnit": "KILOGRAM",
  "status": "ACTIVE",
  "creationTs": "2023-01-08T20:57:36Z",
  "lastModifiedTs": "2025-04-06T10:43:38Z",
  "stats": { "numAssociatedDives": 31, "totalAssociatedDiveTime": 95690.84 },
  "gearField": {
    "fields": { "type": "PISTON", "connectorType": "DIN" },
    "type": "REGULATOR"
  },
  "media": { "images": [] }
}
```

- [ ] **Step 9: Write `tests/fixtures/gear_detail_light.json`**

```json
{
  "gearId": 247811,
  "name": "Underwater iPhone Light",
  "type": "LIGHT",
  "brand": "LetonPower",
  "model": "Sealion L24",
  "dateOfFirstUse": "2024-04-06",
  "purchasePrice": 158.0,
  "purchaseCurrency": "GBP",
  "purchasedFrom": "Amazon",
  "purchaseDate": "2024-03-23",
  "status": "ACTIVE",
  "creationTs": "2024-04-07T07:51:58Z",
  "lastModifiedTs": "2024-04-07T07:52:16Z",
  "stats": { "numAssociatedDives": 17, "totalAssociatedDiveTime": 51103.05 },
  "gearField": {
    "fields": { "type": "PHOTOGRAPHY", "bulb": "HID", "rechargeable": true, "lumenOutput": 12000 },
    "type": "LIGHT"
  },
  "media": { "images": [] }
}
```

- [ ] **Step 10: Write `tests/fixtures/gear_detail_transmitter.json`**

```json
{
  "gearId": 159147,
  "name": "Descent T1",
  "type": "TRANSMITTER",
  "desc": "Descent T1",
  "brand": "Garmin",
  "model": "Descent T1",
  "serialNumber": "09144",
  "antChannelId": 356952664,
  "dateOfFirstUse": "2022-08-20",
  "purchasedFrom": "Mike's Dive Store",
  "purchaseDate": "2022-07-29",
  "status": "ACTIVE",
  "creationTs": "2023-04-06T01:20:01Z",
  "lastModifiedTs": "2023-04-19T03:24:14Z",
  "stats": { "numAssociatedDives": 36, "totalAssociatedDiveTime": 108558.86 },
  "media": { "images": [] }
}
```

- [ ] **Step 11: Write `tests/fixtures/gear_detail_other.json`**

```json
{
  "gearId": 101272,
  "name": "Transmitter Hose Extension",
  "type": "OTHER",
  "brand": "Miflex",
  "model": "Carbon HD Hose",
  "size": "15cm/6in",
  "dueIndicator": "NOT_DUE",
  "lastServiceDate": "2025-04-04",
  "serviceIntervalDays": 730,
  "lastServicedBy": "Mike's Dive Store",
  "nextServiceDate": "2027-04-04",
  "nextServiceDueIndicator": "NOT_DUE",
  "dateOfFirstUse": "2022-08-02",
  "purchasePrice": 28.8,
  "purchaseCurrency": "GBP",
  "purchasedFrom": "Aquanauts Scuba Kingston",
  "purchaseDate": "2022-08-02",
  "status": "ACTIVE",
  "creationTs": "2022-08-03T11:41:32Z",
  "lastModifiedTs": "2025-04-06T10:44:07Z",
  "stats": { "numAssociatedDives": 31, "totalAssociatedDiveTime": 95690.84 },
  "media": { "images": [] }
}
```

- [ ] **Step 12: Write `tests/fixtures/social_profile_v2.json`**

```json
{
  "id": 400994503,
  "garminGUID": "00000000-0000-0000-0000-000000000000",
  "profileId": 106627261,
  "displayName": "test-display-name",
  "fullName": "Test User",
  "userName": "test@example.invalid",
  "profileImageType": "UPLOADED_PHOTO",
  "profileImageUrls": {},
  "userRoles": [
    "SCOPE_CONNECT_READ",
    "SCOPE_DIVE_API_READ",
    "SCOPE_DIVE_API_WRITE",
    "ROLE_DIVE_USER"
  ]
}
```

- [ ] **Step 13: Write `tests/fixtures/dive_images_graphql.json`** (placeholder shape based on user-pasted response; operation name TBD per spec §13)

```json
{
  "data": {
    "diveImages": {
      "__typename": "ImageList",
      "items": [
        {
          "__typename": "Image",
          "imageUUID": "3730581e-c80e-4c19-8513-cd403e1c72a5",
          "inappropriateReviewStatus": "PASSED_BY_ALGORITHM",
          "timezone": "Africa/Cairo",
          "eventDate": "2025-08-26T09:01:37+03:00",
          "associatedEntityType": "SINGLE_GAS",
          "associatedEntityName": null,
          "entityReferenceId": "23285230",
          "owner": {
            "__typename": "PlayerProfile",
            "profileName": "test-display-name",
            "playerProfileId": 106627261
          },
          "versionedUrls": [
            {
              "__typename": "ExpiringURL",
              "key": "3730581e-smth.jpeg",
              "url": "https://example.invalid/3730581e-smth.jpeg?sig=test",
              "urlExpiration": "2026-05-04T01:54:47Z",
              "version": "SMALL_THUMBNAIL"
            },
            {
              "__typename": "ExpiringURL",
              "key": "3730581e-mdfd.jpeg",
              "url": "https://example.invalid/3730581e-mdfd.jpeg?sig=test",
              "urlExpiration": "2026-05-04T01:54:47Z",
              "version": "MEDIUM_FEED"
            },
            {
              "__typename": "ExpiringURL",
              "key": "3730581e-larg.jpeg",
              "url": "https://example.invalid/3730581e-larg.jpeg?sig=test",
              "urlExpiration": "2026-05-04T01:54:47Z",
              "version": "LARGE"
            }
          ]
        }
      ]
    }
  }
}
```

- [ ] **Step 14: Verify fixture loader works**

Run: `python -c "import sys; sys.path.insert(0, '.'); import json; print(json.loads(open('tests/fixtures/dive_summary_one.json').read())['totalCount'])"`
Expected: `68`

- [ ] **Step 15: Commit**

```bash
git add tests/
git commit -m "test: add scrubbed Garmin Dive API fixtures"
```

---

## Task 5: API client — base + dive summary endpoint (TDD)

**Files:**
- Create: `custom_components/garmin_dive/api.py`
- Create: `tests/test_api.py`

The API client wraps an `aiohttp.ClientSession` and a callable that returns a fresh bearer token (so the auth module can inject token-refresh logic later). Methods are typed and return raw decoded JSON for now; richer typed models can be layered on later if needed.

- [ ] **Step 1: Write the failing test for `get_dive_summary`**

Append to `tests/test_api.py`:

```python
"""Tests for GarminDiveClient HTTP behaviour."""
from __future__ import annotations

from typing import Any

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from custom_components.garmin_dive.api import GarminDiveClient


@pytest.fixture
async def client(load_fixture):
    """Yield a GarminDiveClient backed by a fresh aiohttp session."""
    async with aiohttp.ClientSession() as session:
        async def get_token() -> str:
            return "test-token"

        yield GarminDiveClient(session=session, get_token=get_token)


async def test_get_dive_summary_returns_decoded_json(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture: Any
):
    fixture = load_fixture("dive_summary_one")
    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/dive/summary",
        "GET",
        aresponses.Response(status=200, text=__import__("json").dumps(fixture)),
        match_querystring=False,
    )
    result = await client.get_dive_summary(page=0, results_per_page=1)
    assert result["totalCount"] == 68
    assert result["diveActivities"][0]["name"] == "Elphinstone (South side)"


async def test_get_dive_summary_sends_bearer_and_app_headers(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture: Any
):
    captured: dict[str, str] = {}

    async def handler(request):
        captured.update(request.headers)
        return aresponses.Response(status=200, text="{}")

    aresponses.add("gcs.garmin.com", "/diving/v1/dive/summary", "GET", handler)
    await client.get_dive_summary(page=0, results_per_page=1)
    assert captured["Authorization"] == "bearer test-token"
    assert captured["X-App-Ver"] == "3.4"
    assert captured["X-Lang"] == "en"
    assert captured["Accept"] == "application/json"
    assert captured["User-Agent"].startswith("Dive/3.4")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'custom_components.garmin_dive.api'`

- [ ] **Step 3: Write minimal `api.py`**

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_api.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/api.py tests/test_api.py
git commit -m "feat(api): GarminDiveClient with dive-summary endpoint"
```

---

## Task 6: API client — dive devices, tags, gear summary, gear detail (TDD)

**Files:**
- Modify: `custom_components/garmin_dive/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Append failing tests to `tests/test_api.py`**

```python
async def test_get_dive_devices(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/dive/devices",
        "GET",
        aresponses.Response(status=200, text=__import__("json").dumps(load_fixture("dive_devices"))),
    )
    devices = await client.get_dive_devices()
    assert isinstance(devices, list)
    assert devices[0]["productDisplayName"] == "Descent MK2i"


async def test_get_dive_tags(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/dive/tags",
        "GET",
        aresponses.Response(status=200, text=__import__("json").dumps(load_fixture("dive_tags"))),
    )
    tags = await client.get_dive_tags()
    assert tags["RECREATIONAL"] == 45


async def test_get_gear_summary_passes_all_gear_types(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    captured_qs: list[tuple[str, str]] = []

    async def handler(request):
        captured_qs.extend(request.query.items())
        return aresponses.Response(
            status=200,
            text=__import__("json").dumps(load_fixture("gear_summary")),
        )

    aresponses.add("gcs.garmin.com", "/diving/v1/gear/summary", "GET", handler)
    result = await client.get_gear_summary(current_user_date="2026-05-03")
    assert isinstance(result, list)
    assert any(item["gearId"] == 247811 for item in result)
    # Every gear type should have been sent as a `gear-types` query param.
    types_sent = {v for k, v in captured_qs if k == "gear-types"}
    assert "REGULATOR" in types_sent
    assert "OTHER" in types_sent
    assert len(types_sent) >= 25


async def test_get_gear_detail(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    aresponses.add(
        "gcs.garmin.com",
        "/diving/v1/gear/141548",
        "GET",
        aresponses.Response(
            status=200,
            text=__import__("json").dumps(load_fixture("gear_detail_regulator")),
        ),
    )
    detail = await client.get_gear_detail(gear_id=141548, current_user_date="2026-05-03")
    assert detail["brand"] == "Atomic Aquatics"
    assert detail["nextServiceDate"] == "2027-04-04"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -v`
Expected: 4 new FAIL with AttributeError on missing methods

- [ ] **Step 3: Add methods to `api.py`**

Append the following imports + methods to `api.py`:

In the imports block:
```python
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
)
```

Add these methods inside `class GarminDiveClient`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/api.py tests/test_api.py
git commit -m "feat(api): add devices, tags, gear-summary, and gear-detail endpoints"
```

---

## Task 7: API client — GraphQL POST helper + dive-photos query (TDD)

**Files:**
- Modify: `custom_components/garmin_dive/api.py`
- Modify: `tests/test_api.py`

The exact GraphQL operation name for dive photos is unknown (spec §13); we ship a generic `graphql(operation_name, query, variables)` method and a thin `get_dive_photos(profile_id, start_date, end_date)` wrapper that the engineer updates with the operation name once captured. The wrapper is unit-tested with the captured response shape.

- [ ] **Step 1: Append failing tests**

```python
import json


async def test_graphql_posts_operation_and_variables(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    captured: dict[str, Any] = {}

    async def handler(request):
        captured["body"] = await request.json()
        return aresponses.Response(
            status=200,
            text=json.dumps(load_fixture("dive_images_graphql")),
        )

    aresponses.add("gcs.garmin.com", "/diving/graphql/query", "POST", handler)
    result = await client.graphql(
        operation_name="DiveImagesByDateRange",
        query="query DiveImagesByDateRange($playerId: Long!, $start: LocalDate!, $end: LocalDate!) { ... }",
        variables={"playerId": 106627261, "start": "2026-01-01", "end": "2026-12-31"},
    )
    assert captured["body"]["operationName"] == "DiveImagesByDateRange"
    assert captured["body"]["variables"]["playerId"] == 106627261
    assert "extensions" in captured["body"]
    assert result["data"]["diveImages"]["items"][0]["imageUUID"] == "3730581e-c80e-4c19-8513-cd403e1c72a5"


async def test_get_dive_photos_by_year(
    aresponses: ResponsesMockServer, client: GarminDiveClient, load_fixture
):
    aresponses.add(
        "gcs.garmin.com",
        "/diving/graphql/query",
        "POST",
        aresponses.Response(status=200, text=json.dumps(load_fixture("dive_images_graphql"))),
    )
    result = await client.get_dive_photos(profile_id=106627261, year=2025)
    assert result["data"]["diveImages"]["items"][0]["entityReferenceId"] == "23285230"
```

- [ ] **Step 2: Run tests to confirm failures**

Run: `pytest tests/test_api.py::test_graphql_posts_operation_and_variables tests/test_api.py::test_get_dive_photos_by_year -v`
Expected: FAIL on missing methods

- [ ] **Step 3: Add GraphQL helpers to `api.py`**

Add to imports:
```python
from .const import PATH_GRAPHQL
```

Add inside `class GarminDiveClient`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_api.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/api.py tests/test_api.py
git commit -m "feat(api): add GraphQL POST helper and dive-photos wrapper"
```

---

## Task 8: API client — Connect-side OAuth audience exchange + social profile (TDD)

**Files:**
- Modify: `custom_components/garmin_dive/api.py`
- Modify: `tests/test_api.py`

The Dive bearer is obtained by POSTing `audience=DIVE_MOBILE_IOS_DI` to `connectapi.garmin.com/oauth-service/oauth/exchange/user/2.0` using the **Connect** bearer (which `ha-garmin` provides as `auth.di_token`). We add this method to the API client because it's an HTTP call with a bearer; the auth module wires it.

- [ ] **Step 1: Append failing tests**

```python
async def test_exchange_dive_audience(
    aresponses: ResponsesMockServer
):
    """Exchange uses the Connect bearer, not the Dive one."""
    captured: dict[str, Any] = {}

    async def handler(request):
        captured["headers"] = dict(request.headers)
        captured["body"] = await request.text()
        return aresponses.Response(
            status=200,
            text=json.dumps({
                "access_token": "new-dive-token",
                "refresh_token": "new-dive-refresh",
                "token_type": "bearer",
                "expires_in": 86399,
                "refresh_token_expires_in": 2591999,
                "scope": "DIVE_API_READ DIVE_API_WRITE CONNECT_READ",
                "jti": "test-jti",
            }),
        )

    aresponses.add(
        "connectapi.garmin.com", "/oauth-service/oauth/exchange/user/2.0", "POST", handler
    )

    async with aiohttp.ClientSession() as session:
        async def get_token() -> str:
            return "should-not-be-called"

        api = GarminDiveClient(session=session, get_token=get_token)
        result = await api.exchange_dive_audience(connect_bearer="connect-bearer-xyz")
    assert captured["headers"]["Authorization"] == "bearer connect-bearer-xyz"
    assert "audience=DIVE_MOBILE_IOS_DI" in captured["body"]
    assert result["access_token"] == "new-dive-token"


async def test_get_social_profile(
    aresponses: ResponsesMockServer, load_fixture
):
    aresponses.add(
        "connectapi.garmin.com",
        "/userprofile-service/socialProfile/v2",
        "GET",
        aresponses.Response(status=200, text=json.dumps(load_fixture("social_profile_v2"))),
    )

    async with aiohttp.ClientSession() as session:
        async def get_token() -> str:
            return "should-not-be-called"

        api = GarminDiveClient(session=session, get_token=get_token)
        profile = await api.get_social_profile(connect_bearer="connect-bearer")
    assert profile["profileId"] == 106627261
    assert profile["userName"] == "test@example.invalid"


async def test_refresh_dive_token(aresponses: ResponsesMockServer):
    captured: dict[str, Any] = {}

    async def handler(request):
        captured["body"] = await request.text()
        captured["headers"] = dict(request.headers)
        return aresponses.Response(
            status=200,
            text=json.dumps({
                "access_token": "refreshed-dive-token",
                "refresh_token": "new-refresh-rotated",
                "token_type": "bearer",
                "expires_in": 86399,
                "refresh_token_expires_in": 2591999,
                "scope": "DIVE_API_READ",
                "jti": "test-jti",
            }),
        )

    aresponses.add("diauth.garmin.com", "/di-oauth2-service/oauth/token", "POST", handler)
    async with aiohttp.ClientSession() as session:
        async def get_token() -> str:
            return "unused"

        api = GarminDiveClient(session=session, get_token=get_token)
        result = await api.refresh_dive_token(refresh_token="dive-refresh-abc")
    assert "grant_type=refresh_token" in captured["body"]
    assert "refresh_token=dive-refresh-abc" in captured["body"]
    assert "client_id=DIVE_MOBILE_IOS_DI" in captured["body"]
    assert result["access_token"] == "refreshed-dive-token"
```

- [ ] **Step 2: Run tests to confirm failures**

Run: `pytest tests/test_api.py -v`
Expected: 3 new FAIL on missing methods

- [ ] **Step 3: Add the three methods to `api.py`**

Update imports:
```python
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
```

Add methods inside `class GarminDiveClient`:

```python
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
            resp.raise_for_status()
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_api.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/api.py tests/test_api.py
git commit -m "feat(api): audience exchange, social profile, and dive-token refresh"
```

---

## Task 9: Auth module — `GarminDiveAuth` (TDD)

**Files:**
- Create: `custom_components/garmin_dive/auth.py`
- Create: `tests/test_auth.py`

`GarminDiveAuth` wraps the upstream Garmin SSO library and layers our DIVE audience exchange on top.

**Library choice — `ha-garmin` (not garth).** The de facto Python SSO library for Garmin in 2026 is [`ha-garmin`](https://pypi.org/project/ha-garmin/) (used by `cyberjunky/home-assistant-garmin_connect`). `garth` was the previous standard but is **deprecated** as of 2026 — it cannot complete new logins because of Garmin's TLS-fingerprinting + Cloudflare changes. `ha-garmin` uses `curl_cffi` to impersonate a browser TLS fingerprint and re-implements the SSO + DI-OAuth flow.

`ha-garmin`'s public API:
- `GarminAuth()` — sync constructor (`is_cn: bool = False` for China region).
- `auth.login(email, password) -> AuthResult` — sync, blocks on network. Raises `GarminMFARequired` if 2FA prompt is required.
- `auth.complete_mfa(mfa_code) -> AuthResult` — sync, completes the partial login.
- `auth.di_token` — the Connect-API DI bearer (string).
- `auth.is_authenticated` — bool.
- `auth.save_session(path)` / `auth.load_session(path) -> bool` — JSON token-store persistence.
- `auth.refresh_session() -> bool` — refreshes the DI token using the saved refresh token.

Our `GarminDiveAuth` owns:
- the `ha_garmin.GarminAuth` instance (login + MFA + Connect tokens + their persistence).
- our own DIVE-scoped access/refresh token pair (separately managed because we audience-exchange to `DIVE_MOBILE_IOS_DI`).
- `get_dive_token()` (refresh-on-skew using our DIVE refresh token directly against `diauth.garmin.com`).
- `serialize()` / `from_entry_data()` for HA config-entry persistence.

It deliberately does no HTTP itself — it composes `GarminDiveClient` for the audience-exchange and DIVE-token-refresh HTTP calls. `ha-garmin` calls are wrapped in executor jobs because the library is synchronous.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for GarminDiveAuth."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.garmin_dive.auth import GarminDiveAuth


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


async def test_login_calls_ha_garmin_then_exchanges_dive_audience():
    """Successful login (no MFA): calls ha_garmin.login, exchanges for Dive audience."""
    fake_ha = MagicMock()
    fake_ha.login = MagicMock(return_value=MagicMock())  # AuthResult, ignored
    fake_ha.di_token = "connect-access"

    api = MagicMock()
    api.exchange_dive_audience = AsyncMock(return_value=_token_response())
    api.get_social_profile = AsyncMock(
        return_value={"profileId": 106627261, "displayName": "Rob"}
    )

    auth = GarminDiveAuth(ha_auth=fake_ha, api=api)
    profile = await auth.login(
        hass=MagicMock(async_add_executor_job=lambda fn, *a, **kw: _run_sync(fn, *a, **kw)),
        email="test@example.invalid",
        password="secret",
    )

    fake_ha.login.assert_called_once_with("test@example.invalid", "secret")
    api.exchange_dive_audience.assert_awaited_once_with(connect_bearer="connect-access")
    assert profile["profileId"] == 106627261
    assert auth.profile_id == 106627261
    assert auth.profile_display_name == "Rob"
    assert (await auth.get_dive_token()) == "dive-access"


async def test_login_handles_mfa_via_provider():
    """When ha_garmin raises GarminMFARequired, login awaits the mfa_provider."""
    from ha_garmin import GarminMFARequired

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
        hass=MagicMock(async_add_executor_job=lambda fn, *a, **kw: _run_sync(fn, *a, **kw)),
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
    auth._profile_id = 106627261
    auth._profile_display_name = "Rob"
    auth._session_path = "/tmp/garmin_dive/106627261.json"

    data = auth.serialize()
    assert data["dive_access_token"] == "a"
    assert data["dive_refresh_token"] == "r"
    assert data["dive_expires_at"] == 1234567890
    assert data["profile_id"] == 106627261
    assert data["profile_display_name"] == "Rob"
    assert data["session_path"] == "/tmp/garmin_dive/106627261.json"


# Helper: run a sync function as if it were submitted to a thread pool, for tests.
def _run_sync(fn, *args, **kwargs):
    import asyncio
    fut = asyncio.get_event_loop().create_future()
    try:
        fut.set_result(fn(*args, **kwargs))
    except Exception as e:
        fut.set_exception(e)
    return fut
```

- [ ] **Step 2: Run tests to confirm failures**

Run: `pytest tests/test_auth.py -v`
Expected: FAIL on missing module

- [ ] **Step 3: Write `auth.py`**

```python
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
        self._profile_display_name = (
            profile.get("displayName") or profile.get("fullName")
        )

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
        token_resp = await self._api.refresh_dive_token(
            refresh_token=self._dive_refresh_token
        )
        self._apply_dive_token(token_resp)
        assert self._dive_access_token is not None
        return self._dive_access_token

    def _apply_dive_token(self, resp: dict[str, Any]) -> None:
        self._dive_access_token = resp["access_token"]
        self._dive_refresh_token = resp["refresh_token"]
        self._dive_expires_at = time.time() + int(resp["expires_in"])

    # --- Persistence --------------------------------------------------------

    async def save_ha_garmin_session(
        self, hass: HomeAssistant, session_path: str
    ) -> None:
        """Persist the upstream ha-garmin session JSON to ``session_path``.

        The path is stored on the auth so it survives serialize/deserialize.
        """
        await hass.async_add_executor_job(self._ha.save_session, session_path)
        self._session_path = session_path

    async def load_ha_garmin_session(
        self, hass: HomeAssistant, session_path: str
    ) -> bool:
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_auth.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/auth.py tests/test_auth.py
git commit -m "feat(auth): GarminDiveAuth with ha-garmin wrap, audience exchange, token refresh"
```

---

## Task 10: Gear delta logic (pure functions, TDD)

**Files:**
- Create: `custom_components/garmin_dive/gear.py`
- Create: `tests/test_gear.py`

`gear.py` is intentionally pure — no HA imports, no I/O — so it's trivially testable. It computes:

- the set of gear IDs whose `lastModifiedTs` differs from a previously-known map, signalling a re-fetch is needed (delta-fetch path from spec §6.1);
- a "service-status flips" diff between two snapshots (drives the `garmin_dive_service_due` event from spec §7.5);
- helpers used by the sensor module (e.g. `days_until_service`, `is_serviceable`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gear.py`:

```python
"""Pure logic for gear list/diff/derived helpers."""
from __future__ import annotations

from datetime import date

import pytest

from custom_components.garmin_dive.gear import (
    GearSnapshot,
    days_until_service,
    detect_service_status_flips,
    is_serviceable,
    needs_detail_fetch,
)


def test_needs_detail_fetch_first_run_picks_up_everything():
    summary = [{"gearId": 1, "lastModifiedTs": "2025-01-01T00:00:00Z"},
               {"gearId": 2, "lastModifiedTs": "2025-01-02T00:00:00Z"}]
    assert needs_detail_fetch(summary, previous={}) == {1, 2}


def test_needs_detail_fetch_only_returns_changed():
    summary = [{"gearId": 1, "lastModifiedTs": "2025-01-01T00:00:00Z"},
               {"gearId": 2, "lastModifiedTs": "2025-02-01T00:00:00Z"}]
    previous = {1: "2025-01-01T00:00:00Z", 2: "2025-01-02T00:00:00Z"}
    assert needs_detail_fetch(summary, previous=previous) == {2}


def test_needs_detail_fetch_summary_without_lastmodifiedts_falls_back_to_full_refresh():
    """Spec §13: if summary lacks lastModifiedTs we re-fetch all (small N)."""
    summary = [{"gearId": 1}, {"gearId": 2}]
    assert needs_detail_fetch(summary, previous={1: "x"}) == {1, 2}


def test_detect_service_status_flips():
    previous = {141548: "NOT_DUE", 247811: "NOT_DUE"}
    current = {141548: "DUE", 247811: "NOT_DUE", 999: "OVERDUE"}
    flips = detect_service_status_flips(previous, current)
    # 141548 went NOT_DUE -> DUE. 999 is new and started at OVERDUE.
    assert flips == {141548: "DUE", 999: "OVERDUE"}


def test_detect_service_status_flips_ignores_clearing():
    """Going DUE -> NOT_DUE shouldn't fire an event."""
    previous = {1: "DUE"}
    current = {1: "NOT_DUE"}
    assert detect_service_status_flips(previous, current) == {}


def test_is_serviceable():
    assert is_serviceable("REGULATOR") is True
    assert is_serviceable("BCD") is True
    assert is_serviceable("LIGHT") is False
    assert is_serviceable("CERTIFICATION") is False


def test_days_until_service_normal():
    assert days_until_service(
        next_service_date="2026-06-03", today=date(2026, 5, 3)
    ) == 31


def test_days_until_service_overdue_returns_negative():
    assert days_until_service(
        next_service_date="2026-04-03", today=date(2026, 5, 3)
    ) == -30


def test_days_until_service_returns_none_when_missing():
    assert days_until_service(next_service_date=None, today=date(2026, 5, 3)) is None


def test_gearsnapshot_round_trip():
    snap = GearSnapshot(last_modified={1: "ts"}, due_indicators={1: "DUE"})
    assert snap.last_modified[1] == "ts"
    assert snap.due_indicators[1] == "DUE"
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/test_gear.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'custom_components.garmin_dive.gear'`

- [ ] **Step 3: Write `gear.py`**

```python
"""Pure helpers for gear list parsing, change detection, and derived fields."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .const import SERVICEABLE_GEAR_TYPES


@dataclass(slots=True)
class GearSnapshot:
    """A small persistent slice of gear state used for cycle-to-cycle diffs."""

    last_modified: dict[int, str] = field(default_factory=dict)
    due_indicators: dict[int, str] = field(default_factory=dict)


def needs_detail_fetch(
    summary: list[dict[str, Any]], *, previous: dict[int, str]
) -> set[int]:
    """Return gear IDs whose detail should be fetched this cycle.

    A gear item needs detail re-fetch when:
      - it's new (not in `previous`), OR
      - its `lastModifiedTs` changed, OR
      - the summary entry doesn't carry `lastModifiedTs` at all (defensive
        fallback for an API change; see spec §13).
    """
    changed: set[int] = set()
    for item in summary:
        gid = int(item["gearId"])
        ts = item.get("lastModifiedTs")
        if ts is None or previous.get(gid) != ts:
            changed.add(gid)
    return changed


def detect_service_status_flips(
    previous: dict[int, str], current: dict[int, str]
) -> dict[int, str]:
    """Return gear IDs whose due indicator just transitioned to DUE or OVERDUE."""
    flips: dict[int, str] = {}
    for gid, indicator in current.items():
        if indicator not in {"DUE", "OVERDUE"}:
            continue
        if previous.get(gid) != indicator:
            flips[gid] = indicator
    return flips


def is_serviceable(gear_type: str) -> bool:
    return gear_type in SERVICEABLE_GEAR_TYPES


def days_until_service(*, next_service_date: str | None, today: date) -> int | None:
    if not next_service_date:
        return None
    target = date.fromisoformat(next_service_date)
    return (target - today).days
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_gear.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/gear.py tests/test_gear.py
git commit -m "feat(gear): pure delta-fetch and service-status flip helpers"
```

---

## Task 11: PhotoCache (TDD)

**Files:**
- Create: `custom_components/garmin_dive/photos.py`
- Create: `tests/test_photos.py`

The cache is keyed by `imageUUID` and writes idempotently to `<www_dir>/garmin_dive/<account_short>/<imageUUID>_<size>.<ext>`. The Garmin response gives multiple `versionedUrls`; we map `SMALL_THUMBNAIL → thumb`, `MEDIUM_FEED → medium`, `LARGE → large`. Concurrency is bounded with `asyncio.Semaphore(2)`.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for PhotoCache."""
from __future__ import annotations

import asyncio
from pathlib import Path

import aiohttp
import pytest
from aresponses import ResponsesMockServer

from custom_components.garmin_dive.photos import PhotoCache, PhotoRecord, version_to_size


def test_version_to_size_mapping():
    assert version_to_size("SMALL_THUMBNAIL") == "thumb"
    assert version_to_size("MEDIUM_FEED") == "medium"
    assert version_to_size("LARGE") == "large"
    assert version_to_size("UNKNOWN") is None


async def test_resolve_path_uses_account_short_and_uuid(tmp_path: Path):
    cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")
    p = cache.resolve_path(
        image_uuid="3730581e-c80e-4c19-8513-cd403e1c72a5",
        size="medium",
        ext="jpeg",
    )
    assert p == tmp_path / "garmin_dive" / "abcd1234" / "3730581e-c80e-4c19-8513-cd403e1c72a5_medium.jpeg"


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
        image_uuid="3730581e",
        urls={"medium": ("https://example.invalid/img1.jpeg", "jpeg")},
    )
    async with aiohttp.ClientSession() as session:
        cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")
        await cache.download_records([record], session=session)
    f = tmp_path / "garmin_dive" / "abcd1234" / "3730581e_medium.jpeg"
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
    # No aresponses registration — if HTTP is hit, the test fails because aresponses errors on unmocked calls.
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
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/test_photos.py -v`
Expected: FAIL on missing module

- [ ] **Step 3: Write `photos.py`**

```python
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
    """A single photo with one URL per requested size."""

    image_uuid: str
    urls: dict[str, tuple[str, str]] = field(default_factory=dict)
    """Mapping of `size` ('thumb'|'medium'|'large') to `(url, ext)`."""

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


def _ext_from_url(url: str) -> str:
    m = re.search(r"\.([A-Za-z0-9]{2,5})(?:\?|$)", url)
    return (m.group(1).lower() if m else "jpeg")


class PhotoCache:
    """Downloads + serves Garmin dive photos via HA's `/local/` static server."""

    def __init__(self, *, www_dir: Path, account_short: str) -> None:
        self._www = www_dir
        self._account_short = account_short
        self._semaphore = asyncio.Semaphore(PHOTO_CACHE_CONCURRENCY)

    # --- Path & URL helpers -------------------------------------------------

    def resolve_path(self, *, image_uuid: str, size: str, ext: str) -> Path:
        return (
            self._www
            / PHOTO_CACHE_DIR_NAME
            / self._account_short
            / f"{image_uuid}_{size}.{ext}"
        )

    def local_url(self, *, image_uuid: str, size: str, ext: str) -> str:
        return f"/local/{PHOTO_CACHE_DIR_NAME}/{self._account_short}/{image_uuid}_{size}.{ext}"

    # --- Download -----------------------------------------------------------

    async def download_records(
        self,
        records: list[PhotoRecord],
        *,
        session: aiohttp.ClientSession,
    ) -> None:
        await asyncio.gather(
            *(self._download_one(r, session=session) for r in records),
            return_exceptions=False,
        )

    async def _download_one(
        self, record: PhotoRecord, *, session: aiohttp.ClientSession
    ) -> None:
        for size, (url, ext) in record.urls.items():
            target = self.resolve_path(image_uuid=record.image_uuid, size=size, ext=ext)
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            async with self._semaphore:
                try:
                    async with session.get(url) as resp:
                        resp.raise_for_status()
                        data = await resp.read()
                    target.write_bytes(data)
                except aiohttp.ClientError as err:  # pragma: no cover - logged
                    _LOGGER.warning(
                        "Failed to download photo %s/%s: %s", record.image_uuid, size, err
                    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_photos.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/photos.py tests/test_photos.py
git commit -m "feat(photos): local photo cache with idempotent downloads"
```

---

## Task 12: Coordinator — DTO + skeleton (TDD)

**Files:**
- Create: `custom_components/garmin_dive/coordinator.py`
- Create: `tests/test_coordinator.py`

The coordinator's job is to fan out the per-cycle calls and assemble a typed `CoordinatorData` snapshot consumed by every entity. We start with the DTO and a `_build_data` orchestration function that's testable in isolation (no HA `DataUpdateCoordinator` machinery yet — that's in Task 14).

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the coordinator's data-assembly logic."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.garmin_dive.coordinator import (
    CoordinatorData,
    GearItem,
    build_data,
)


@pytest.fixture
def fake_api(load_fixture):
    api = MagicMock()
    api.get_dive_summary = AsyncMock(return_value=load_fixture("dive_summary_full"))
    api.get_dive_devices = AsyncMock(return_value=load_fixture("dive_devices"))
    api.get_dive_tags = AsyncMock(return_value=load_fixture("dive_tags"))
    api.get_gear_summary = AsyncMock(return_value=load_fixture("gear_summary"))
    api.get_gear_detail = AsyncMock(side_effect=[
        load_fixture("gear_detail_regulator"),
        load_fixture("gear_detail_light"),
    ])
    return api


async def test_build_data_assembles_snapshot(fake_api):
    data = await build_data(
        api=fake_api,
        current_user_date="2026-05-03",
        previous_gear_last_modified={},
    )
    assert isinstance(data, CoordinatorData)
    assert data.total_dives == 68
    assert len(data.dives) == 3
    assert data.dive_tags["RECREATIONAL"] == 45
    assert {d.product_display_name for d in data.devices} == {"Descent MK2i", "Descent T1"}
    # Gear: 3 summary items, but our mocked side_effect only returns 2 details.
    # build_data should still surface all 3 with the summary baseline.
    assert {g.gear_id for g in data.gear} == {141548, 247811, 463947}


async def test_build_data_skips_detail_fetch_when_unchanged(fake_api, load_fixture):
    fake_api.get_gear_detail = AsyncMock()  # should not be called
    summary_with_ts = load_fixture("gear_summary").copy()
    # Stub: every entry has a known lastModifiedTs and previous map matches it.
    for entry in summary_with_ts:
        entry.setdefault("lastModifiedTs", "2025-01-01T00:00:00Z")
    fake_api.get_gear_summary = AsyncMock(return_value=summary_with_ts)
    previous = {entry["gearId"]: "2025-01-01T00:00:00Z" for entry in summary_with_ts}

    await build_data(
        api=fake_api,
        current_user_date="2026-05-03",
        previous_gear_last_modified=previous,
    )
    fake_api.get_gear_detail.assert_not_awaited()
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/test_coordinator.py -v`
Expected: FAIL on missing module

- [ ] **Step 3: Write `coordinator.py` (DTO + build_data only — full DataUpdateCoordinator wiring is Task 14)**

```python
"""DataUpdateCoordinator for ha-garmin-dive (DTO + build_data orchestration)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

from .gear import GearSnapshot, needs_detail_fetch

if TYPE_CHECKING:
    from .api import GarminDiveClient


@dataclass(slots=True)
class Dive:
    raw: dict[str, Any]

    @property
    def id(self) -> int:
        return int(self.raw["id"])

    @property
    def name(self) -> str:
        return self.raw["name"]

    @property
    def start_time(self) -> str:
        return self.raw["startTime"]

    @property
    def total_time_seconds(self) -> float:
        return float(self.raw["totalTime"])

    @property
    def max_depth(self) -> float:
        return float(self.raw["maxDepth"])


@dataclass(slots=True)
class DiveDevice:
    raw: dict[str, Any]

    @property
    def product_display_name(self) -> str:
        return self.raw["productDisplayName"]

    @property
    def serial_number(self) -> int | None:
        sn = self.raw.get("serialNumber")
        return int(sn) if sn is not None else None

    @property
    def device_type(self) -> str:
        return self.raw["type"]


@dataclass(slots=True)
class GearItem:
    summary_raw: dict[str, Any]
    detail_raw: dict[str, Any] | None = None

    @property
    def gear_id(self) -> int:
        return int(self.summary_raw["gearId"])

    @property
    def name(self) -> str:
        return self.summary_raw["name"]

    @property
    def gear_type(self) -> str:
        return self.summary_raw["type"]

    @property
    def due_indicator(self) -> str | None:
        if self.detail_raw is not None:
            return self.detail_raw.get("dueIndicator")
        return self.summary_raw.get("dueIndicator")


@dataclass(slots=True)
class CoordinatorData:
    total_dives: int
    dives: list[Dive]
    devices: list[DiveDevice]
    dive_tags: dict[str, int]
    gear: list[GearItem]
    gear_snapshot: GearSnapshot = field(default_factory=GearSnapshot)


async def build_data(
    *,
    api: GarminDiveClient,
    current_user_date: str,
    previous_gear_last_modified: dict[int, str],
    results_per_page: int = 100,
) -> CoordinatorData:
    """One refresh cycle: fan out concurrent calls and assemble CoordinatorData."""
    # Fan out the 4 unconditional calls in parallel.
    summary_task = api.get_dive_summary(page=0, results_per_page=results_per_page)
    devices_task = api.get_dive_devices()
    tags_task = api.get_dive_tags()
    gear_summary_task = api.get_gear_summary(current_user_date=current_user_date)
    summary, devices_raw, tags, gear_summary = await asyncio.gather(
        summary_task, devices_task, tags_task, gear_summary_task
    )

    # Conditional gear-detail fetches.
    to_fetch = needs_detail_fetch(gear_summary, previous=previous_gear_last_modified)
    detail_results: list[dict[str, Any]] = []
    if to_fetch:
        detail_results = await asyncio.gather(
            *(
                api.get_gear_detail(gear_id=gid, current_user_date=current_user_date)
                for gid in to_fetch
            )
        )
    detail_by_id: dict[int, dict[str, Any]] = {
        int(d["gearId"]): d for d in detail_results
    }

    gear_items = [
        GearItem(
            summary_raw=item,
            detail_raw=detail_by_id.get(int(item["gearId"])),
        )
        for item in gear_summary
    ]

    # Capture the snapshot used as `previous` on the next cycle.
    snapshot = GearSnapshot(
        last_modified={
            int(g["gearId"]): g.get("lastModifiedTs", "")
            for g in gear_summary
            if "lastModifiedTs" in g
        },
        due_indicators={
            g.gear_id: ind
            for g in gear_items
            if (ind := g.due_indicator) is not None
        },
    )

    return CoordinatorData(
        total_dives=int(summary["totalCount"]),
        dives=[Dive(raw=d) for d in summary["diveActivities"]],
        devices=[DiveDevice(raw=d) for d in devices_raw],
        dive_tags=tags,
        gear=gear_items,
        gear_snapshot=snapshot,
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_coordinator.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/coordinator.py tests/test_coordinator.py
git commit -m "feat(coordinator): CoordinatorData DTO and build_data orchestration"
```

---

## Task 13: Coordinator — photo fetch integration (TDD)

**Files:**
- Modify: `custom_components/garmin_dive/coordinator.py`
- Modify: `tests/test_coordinator.py`

Photos are an opt-in append on top of `build_data`: if the cache is provided we extract image records from gear-detail responses (and later from the GraphQL dive-photos call) and download them. Photos surface back into the snapshot so entities can pick stable URLs from `CoordinatorData`.

- [ ] **Step 1: Append failing test to `tests/test_coordinator.py`**

```python
async def test_build_data_with_photos_collects_gear_images(fake_api, tmp_path, load_fixture):
    """Gear images embedded in summary responses get downloaded to the cache."""
    from custom_components.garmin_dive.photos import PhotoCache

    summary_with_image = load_fixture("gear_summary")
    fake_api.get_gear_summary = AsyncMock(return_value=summary_with_image)
    fake_api.get_dive_photos = AsyncMock(return_value={"data": {"diveImages": {"items": []}}})

    cache = PhotoCache(www_dir=tmp_path, account_short="abcd1234")
    downloaded: list[str] = []

    async def fake_download(records, *, session):
        downloaded.extend(r.image_uuid for r in records)

    cache.download_records = fake_download  # type: ignore[assignment]

    data = await build_data(
        api=fake_api,
        current_user_date="2026-05-03",
        previous_gear_last_modified={},
        photo_cache=cache,
        http_session=MagicMock(),
        profile_id=106627261,
        year=2026,
    )
    assert "315aa699-ea9b-4323-8177-3d8a77b28e24" in downloaded
    assert any(g.photo_local_url for g in data.gear if g.gear_id == 247811)
```

- [ ] **Step 2: Run test to confirm failure**

Run: `pytest tests/test_coordinator.py::test_build_data_with_photos_collects_gear_images -v`
Expected: FAIL — `build_data() got an unexpected keyword argument 'photo_cache'`

- [ ] **Step 3: Extend `coordinator.py`**

Add at the top of the file (additional imports):

```python
import logging

from .photos import PhotoCache, PhotoRecord

_LOGGER = logging.getLogger(__name__)
```

Add these properties to `GearItem`:

```python
    photo_local_url: str | None = None
    photo_thumb_url: str | None = None
```

Replace the existing `build_data(...)` signature and body with:

```python
async def build_data(
    *,
    api: GarminDiveClient,
    current_user_date: str,
    previous_gear_last_modified: dict[int, str],
    results_per_page: int = 100,
    photo_cache: PhotoCache | None = None,
    http_session: Any | None = None,
    profile_id: int | None = None,
    year: int | None = None,
) -> CoordinatorData:
    summary_task = api.get_dive_summary(page=0, results_per_page=results_per_page)
    devices_task = api.get_dive_devices()
    tags_task = api.get_dive_tags()
    gear_summary_task = api.get_gear_summary(current_user_date=current_user_date)
    summary, devices_raw, tags, gear_summary = await asyncio.gather(
        summary_task, devices_task, tags_task, gear_summary_task
    )

    to_fetch = needs_detail_fetch(gear_summary, previous=previous_gear_last_modified)
    detail_results: list[dict[str, Any]] = []
    if to_fetch:
        detail_results = await asyncio.gather(
            *(
                api.get_gear_detail(gear_id=gid, current_user_date=current_user_date)
                for gid in to_fetch
            )
        )
    detail_by_id: dict[int, dict[str, Any]] = {
        int(d["gearId"]): d for d in detail_results
    }

    gear_items = [
        GearItem(
            summary_raw=item,
            detail_raw=detail_by_id.get(int(item["gearId"])),
        )
        for item in gear_summary
    ]

    # Photo collection (optional path)
    if photo_cache is not None and http_session is not None:
        records = list(_collect_gear_photo_records(gear_items))
        if profile_id is not None and year is not None:
            try:
                photos_resp = await api.get_dive_photos(profile_id=profile_id, year=year)
                records.extend(_collect_dive_photo_records(photos_resp))
            except Exception as err:  # pragma: no cover - logged
                _LOGGER.warning("Dive-photos GraphQL call failed: %s", err)
        if records:
            await photo_cache.download_records(records, session=http_session)
            _attach_local_urls(gear_items, photo_cache)

    snapshot = GearSnapshot(
        last_modified={
            int(g["gearId"]): g.get("lastModifiedTs", "")
            for g in gear_summary
            if "lastModifiedTs" in g
        },
        due_indicators={
            g.gear_id: ind
            for g in gear_items
            if (ind := g.due_indicator) is not None
        },
    )

    return CoordinatorData(
        total_dives=int(summary["totalCount"]),
        dives=[Dive(raw=d) for d in summary["diveActivities"]],
        devices=[DiveDevice(raw=d) for d in devices_raw],
        dive_tags=tags,
        gear=gear_items,
        gear_snapshot=snapshot,
    )


def _collect_gear_photo_records(gear_items: list[GearItem]):
    for g in gear_items:
        # Summary-level image (single)
        img = g.summary_raw.get("image")
        if img:
            yield PhotoRecord.from_garmin_image(img)
        # Detail-level images (list of images)
        if g.detail_raw is not None:
            for img in g.detail_raw.get("media", {}).get("images", []) or []:
                yield PhotoRecord.from_garmin_image(img)


def _collect_dive_photo_records(graphql_resp: dict[str, Any]):
    items = (
        graphql_resp.get("data", {})
        .get("diveImages", {})
        .get("items", [])
        or []
    )
    for item in items:
        yield PhotoRecord.from_garmin_image(item)


def _attach_local_urls(gear_items: list[GearItem], cache: PhotoCache) -> None:
    for g in gear_items:
        img = g.summary_raw.get("image") or _first_image(g.detail_raw)
        if not img:
            continue
        record = PhotoRecord.from_garmin_image(img)
        if "medium" in record.urls:
            _, ext = record.urls["medium"]
            g.photo_local_url = cache.local_url(
                image_uuid=record.image_uuid, size="medium", ext=ext
            )
        if "thumb" in record.urls:
            _, ext = record.urls["thumb"]
            g.photo_thumb_url = cache.local_url(
                image_uuid=record.image_uuid, size="thumb", ext=ext
            )


def _first_image(detail: dict[str, Any] | None) -> dict[str, Any] | None:
    if not detail:
        return None
    images = detail.get("media", {}).get("images") or []
    return images[0] if images else None
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_coordinator.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/coordinator.py tests/test_coordinator.py
git commit -m "feat(coordinator): integrate photo cache for gear and dive photos"
```

---

## Task 14: Coordinator — DataUpdateCoordinator wrapping (TDD)

**Files:**
- Modify: `custom_components/garmin_dive/coordinator.py`
- Modify: `tests/test_coordinator.py`

Now wrap `build_data` in HA's `DataUpdateCoordinator`. The wrapper holds the previous snapshot, fires events on diffs, and exposes `runtime_data`-style accessors.

- [ ] **Step 1: Append failing test**

```python
async def test_coordinator_fires_new_dive_event(hass, fake_api, load_fixture):
    """When totalCount increases, fire garmin_dive_new_dive."""
    from custom_components.garmin_dive.coordinator import GarminDiveCoordinator
    from custom_components.garmin_dive.const import EVENT_NEW_DIVE

    auth = MagicMock()
    auth.profile_id = 106627261

    coordinator = GarminDiveCoordinator(
        hass, api=fake_api, auth=auth, photo_cache=None,
        http_session=MagicMock(), scan_interval_minutes=120,
    )
    # Seed with a previous snapshot saying we knew of dives 23285230 and 23261609.
    coordinator._known_dive_ids = {23285230, 23261609}

    fired: list = []
    hass.bus.async_listen(EVENT_NEW_DIVE, lambda evt: fired.append(evt.data))

    await coordinator._async_update_data()
    await hass.async_block_till_done()

    new_ids = [d["dive"]["id"] for d in fired]
    assert 23285231 in new_ids  # the second Elphinstone
    assert 23285230 not in new_ids
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_coordinator.py::test_coordinator_fires_new_dive_event -v`
Expected: FAIL — `ImportError: cannot import name 'GarminDiveCoordinator'`

- [ ] **Step 3: Append `GarminDiveCoordinator` to `coordinator.py`**

Add at the top of the file:

```python
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, EVENT_NEW_DIVE, EVENT_SERVICE_DUE
from .gear import detect_service_status_flips
```

Append the class:

```python
class GarminDiveCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Per-account refresh loop for the integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        api: GarminDiveClient,
        auth: Any,
        photo_cache: PhotoCache | None,
        http_session: Any,
        scan_interval_minutes: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self._api = api
        self._auth = auth
        self._photo_cache = photo_cache
        self._http_session = http_session
        self._known_dive_ids: set[int] = set()
        self._previous_due_indicators: dict[int, str] = {}
        self._previous_gear_last_modified: dict[int, str] = {}

    async def _async_update_data(self) -> CoordinatorData:
        try:
            data = await build_data(
                api=self._api,
                current_user_date=date.today().isoformat(),
                previous_gear_last_modified=self._previous_gear_last_modified,
                photo_cache=self._photo_cache,
                http_session=self._http_session,
                profile_id=self._auth.profile_id,
                year=date.today().year,
            )
        except Exception as err:
            raise UpdateFailed(f"Garmin Dive refresh failed: {err}") from err

        self._fire_event_diffs(data)
        self._previous_gear_last_modified = dict(data.gear_snapshot.last_modified)
        self._previous_due_indicators = dict(data.gear_snapshot.due_indicators)
        self._known_dive_ids = {d.id for d in data.dives}
        return data

    def _fire_event_diffs(self, data: CoordinatorData) -> None:
        # New dives
        for dive in data.dives:
            if dive.id not in self._known_dive_ids and self._known_dive_ids:
                self.hass.bus.async_fire(
                    EVENT_NEW_DIVE,
                    {
                        "profile_id": self._auth.profile_id,
                        "dive": dive.raw,
                    },
                )

        # Service-due transitions
        flips = detect_service_status_flips(
            self._previous_due_indicators, data.gear_snapshot.due_indicators
        )
        if not self._previous_due_indicators:
            return  # don't fire on first run
        for gear_id, indicator in flips.items():
            gear = next((g for g in data.gear if g.gear_id == gear_id), None)
            if gear is not None:
                self.hass.bus.async_fire(
                    EVENT_SERVICE_DUE,
                    {
                        "profile_id": self._auth.profile_id,
                        "gear": gear.summary_raw,
                        "indicator": indicator,
                    },
                )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_coordinator.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/coordinator.py tests/test_coordinator.py
git commit -m "feat(coordinator): GarminDiveCoordinator with new-dive and service-due events"
```

---

## Task 15: Entity base classes

**Files:**
- Create: `custom_components/garmin_dive/entity.py`

No tests for this layer; it's pure scaffolding exercised through every platform test.

- [ ] **Step 1: Write `entity.py`**

```python
"""Base entity classes for ha-garmin-dive."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import GarminDiveCoordinator


class GarminDiveAccountEntity(CoordinatorEntity["GarminDiveCoordinator"]):
    """Entity attached to the per-account HA Device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._account_id = str(coordinator._auth.profile_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._account_id)},
            name=f"Garmin Dive — {coordinator._auth.profile_display_name}",
            manufacturer="Garmin",
            model="Dive",
            entry_type=None,
        )


class GarminDiveSubDeviceEntity(CoordinatorEntity["GarminDiveCoordinator"]):
    """Entity attached to a sub-device (dive computer or gear item)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GarminDiveCoordinator,
        *,
        sub_device_id: str,
        sub_device_name: str,
        manufacturer: str | None = None,
        model: str | None = None,
        serial_number: str | None = None,
        entity_picture: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._account_id = str(coordinator._auth.profile_id)
        self._sub_device_id = sub_device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._account_id}:{sub_device_id}")},
            via_device=(DOMAIN, self._account_id),
            name=sub_device_name,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
        )
        self._attr_entity_picture = entity_picture
```

- [ ] **Step 2: Lint + import sanity check**

Run: `python -c "import sys; sys.path.insert(0, '.'); from custom_components.garmin_dive import entity; print(entity.GarminDiveAccountEntity.__name__)"`
Expected: `GarminDiveAccountEntity`

- [ ] **Step 3: Commit**

```bash
git add custom_components/garmin_dive/entity.py
git commit -m "feat(entity): base classes for account-scoped and sub-device entities"
```

---

## Task 16: `sensor.py` — account-level basic sensors (TDD via snapshot)

**Files:**
- Create: `custom_components/garmin_dive/sensor.py`
- Create: `tests/test_sensor.py`
- Create: `tests/conftest_helpers.py` (small helpers reused across platform tests)

We'll build the sensor module incrementally. This task adds:
- `last_dive` (state = name; rich attributes)
- `total_dives` (int)
- `current_year_dives` (int)
- `last_dive_max_depth` (m, with `device_class=distance`)
- `last_dive_bottom_time` (min, `device_class=duration`)
- `last_dive_surface_interval` (h, `device_class=duration`)

`dive_log_year`, `gear_count`, `dives_by_tag` are added in Task 17. Per-gear sensors in Task 18, per-dive-computer in Task 19.

- [ ] **Step 1: Write `tests/conftest_helpers.py`**

```python
"""Helpers for building a coordinator with a fake CoordinatorData."""
from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

from custom_components.garmin_dive.coordinator import (
    CoordinatorData,
    Dive,
    DiveDevice,
    GearItem,
)
from custom_components.garmin_dive.gear import GearSnapshot


def make_fake_coordinator(
    *,
    hass,
    profile_id: int = 106627261,
    profile_display_name: str = "Rob",
    data: CoordinatorData | None = None,
) -> Any:
    coord = MagicMock()
    coord.hass = hass
    coord.async_add_listener = MagicMock(return_value=lambda: None)
    coord.last_update_success = True
    auth = MagicMock()
    auth.profile_id = profile_id
    auth.profile_display_name = profile_display_name
    coord._auth = auth
    coord.data = data
    return coord


def make_data(
    *,
    summary: dict[str, Any],
    devices: list[dict[str, Any]] | None = None,
    tags: dict[str, int] | None = None,
    gear_summary: list[dict[str, Any]] | None = None,
    gear_details: dict[int, dict[str, Any]] | None = None,
) -> CoordinatorData:
    devices = devices or []
    tags = tags or {}
    gear_summary = gear_summary or []
    gear_details = gear_details or {}
    return CoordinatorData(
        total_dives=int(summary["totalCount"]),
        dives=[Dive(raw=d) for d in summary["diveActivities"]],
        devices=[DiveDevice(raw=d) for d in devices],
        dive_tags=tags,
        gear=[GearItem(summary_raw=g, detail_raw=gear_details.get(int(g["gearId"]))) for g in gear_summary],
        gear_snapshot=GearSnapshot(),
    )
```

- [ ] **Step 2: Write the failing test**

```python
"""Tests for account-level sensors."""
from __future__ import annotations

from datetime import datetime

import pytest
from freezegun import freeze_time

from tests.conftest_helpers import make_data, make_fake_coordinator


@freeze_time("2026-05-03T12:00:00")
async def test_last_dive_state_and_attributes(hass, load_fixture):
    from custom_components.garmin_dive.sensor import LastDiveSensor

    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = LastDiveSensor(coord)

    assert sensor.native_value == "Elphinstone (South side)"
    attrs = sensor.extra_state_attributes
    assert attrs["max_depth"] == pytest.approx(26.373)
    assert attrs["bottom_time_minutes"] == pytest.approx(2747.59 / 60)
    assert attrs["connect_url"] == "https://connect.garmin.com/modern/activity/20180546488"


async def test_total_and_current_year_dives(hass, load_fixture):
    from custom_components.garmin_dive.sensor import (
        CurrentYearDivesSensor,
        TotalDivesSensor,
    )

    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    assert TotalDivesSensor(coord).native_value == 68
    # All fixture dives are in 2025; current year (frozen 2026-05-03) is 2026 -> 0.
    with freeze_time("2026-05-03"):
        assert CurrentYearDivesSensor(coord).native_value == 0


async def test_last_dive_depth_uses_distance_device_class(hass, load_fixture):
    from custom_components.garmin_dive.sensor import LastDiveMaxDepthSensor

    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = LastDiveMaxDepthSensor(coord)
    assert sensor.native_value == pytest.approx(26.373)
    assert sensor.device_class == "distance"
    assert sensor.native_unit_of_measurement == "m"


async def test_handles_empty_dive_list(hass):
    from custom_components.garmin_dive.sensor import LastDiveSensor, TotalDivesSensor

    data = make_data(summary={"totalCount": 0, "diveActivities": []})
    coord = make_fake_coordinator(hass=hass, data=data)
    assert LastDiveSensor(coord).native_value is None
    assert TotalDivesSensor(coord).native_value == 0
```

Add `freezegun>=1.4` to `requirements_dev.txt`:

```bash
echo "freezegun>=1.4" >> requirements_dev.txt
```

- [ ] **Step 3: Run tests to confirm failure**

Run: `pytest tests/test_sensor.py -v`
Expected: FAIL on missing module / classes

- [ ] **Step 4: Write `sensor.py` (account-level subset)**

```python
"""Garmin Dive sensor entities."""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import GarminDiveAccountEntity

if TYPE_CHECKING:
    from .coordinator import GarminDiveCoordinator, Dive


def _connect_url(connect_activity_id: int | None) -> str | None:
    if connect_activity_id is None:
        return None
    return f"https://connect.garmin.com/modern/activity/{connect_activity_id}"


def _last_dive(coordinator: GarminDiveCoordinator) -> Dive | None:
    if not coordinator.data or not coordinator.data.dives:
        return None
    return coordinator.data.dives[0]


class LastDiveSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "last_dive"
    _attr_icon = "mdi:diving-scuba"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_last_dive"

    @property
    def native_value(self) -> str | None:
        d = _last_dive(self.coordinator)
        return d.name if d else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        d = _last_dive(self.coordinator)
        if d is None:
            return None
        raw = d.raw
        return {
            "id": d.id,
            "connect_activity_id": raw.get("connectActivityId"),
            "connect_url": _connect_url(raw.get("connectActivityId")),
            "start_time": raw.get("startTime"),
            "timezone": raw.get("timezone"),
            "max_depth": raw.get("maxDepth"),
            "bottom_time_minutes": (raw["bottomTime"] / 60) if "bottomTime" in raw else None,
            "total_time_minutes": (raw["totalTime"] / 60) if "totalTime" in raw else None,
            "surface_interval_hours": (raw["surfaceInterval"] / 3600) if "surfaceInterval" in raw else None,
            "tags": raw.get("diveTags"),
            "gases": raw.get("gases"),
            "location": raw.get("entryLoc"),
            "dive_type": raw.get("diveType"),
        }


class TotalDivesSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "total_dives"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_total_dives"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.total_dives if self.coordinator.data else 0


class CurrentYearDivesSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "current_year_dives"
    _attr_icon = "mdi:calendar-month"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_current_year_dives"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        year = date.today().year
        return sum(
            1
            for d in self.coordinator.data.dives
            if datetime.fromisoformat(d.start_time).year == year
        )


class LastDiveMaxDepthSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "last_dive_max_depth"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:arrow-collapse-down"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_last_dive_max_depth"

    @property
    def native_value(self) -> float | None:
        d = _last_dive(self.coordinator)
        return d.max_depth if d else None


class LastDiveBottomTimeSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "last_dive_bottom_time"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_last_dive_bottom_time"

    @property
    def native_value(self) -> float | None:
        d = _last_dive(self.coordinator)
        if d is None:
            return None
        bt = d.raw.get("bottomTime")
        return bt / 60 if bt is not None else None


class LastDiveSurfaceIntervalSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "last_dive_surface_interval"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_last_dive_surface_interval"

    @property
    def native_value(self) -> float | None:
        d = _last_dive(self.coordinator)
        if d is None:
            return None
        si = d.raw.get("surfaceInterval")
        return si / 3600 if si is not None else None


# --- Platform setup --------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GarminDiveCoordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        LastDiveSensor(coordinator),
        TotalDivesSensor(coordinator),
        CurrentYearDivesSensor(coordinator),
        LastDiveMaxDepthSensor(coordinator),
        LastDiveBottomTimeSensor(coordinator),
        LastDiveSurfaceIntervalSensor(coordinator),
    ]
    async_add_entities(entities)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_sensor.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add custom_components/garmin_dive/sensor.py tests/test_sensor.py tests/conftest_helpers.py requirements_dev.txt
git commit -m "feat(sensor): account-level last-dive, totals, and depth/time sensors"
```

---

## Task 17: `sensor.py` — `dive_log_year`, `dives_by_tag`, `gear_count` (TDD)

**Files:**
- Modify: `custom_components/garmin_dive/sensor.py`
- Modify: `tests/test_sensor.py`

`dive_log_year` is the timeline-driving sensor — its `attributes.dives` list is exactly what the dashboard cards bind to.

- [ ] **Step 1: Append failing tests**

```python
async def test_dive_log_year_attribute_shape(hass, load_fixture):
    from custom_components.garmin_dive.sensor import DiveLogYearSensor

    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = DiveLogYearSensor(coord)

    attrs = sensor.extra_state_attributes
    dives = attrs["dives"]
    assert len(dives) == 3
    first = dives[0]
    assert {"id", "name", "start", "end", "timezone", "max_depth",
            "average_depth", "bottom_time", "total_time", "surface_interval",
            "tags", "gases", "location", "photos", "connect_url",
            "dive_computer"} <= set(first.keys())
    assert first["connect_url"] == "https://connect.garmin.com/modern/activity/20180546488"
    # average_depth is unknown today (spec §13) -> None.
    assert first["average_depth"] is None


async def test_dives_by_tag_state_and_attrs(hass, load_fixture):
    from custom_components.garmin_dive.sensor import DivesByTagSensor

    data = make_data(summary=load_fixture("dive_summary_full"), tags=load_fixture("dive_tags"))
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = DivesByTagSensor(coord)
    assert sensor.native_value == 45 + 34 + 8 + 5 + 3 + 3 + 1
    assert sensor.extra_state_attributes["RECREATIONAL"] == 45


async def test_gear_count_state_and_breakdown(hass, load_fixture):
    from custom_components.garmin_dive.sensor import GearCountSensor

    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = GearCountSensor(coord)
    assert sensor.native_value == 3
    breakdown = sensor.extra_state_attributes["by_type"]
    assert breakdown["REGULATOR"] == 1
    assert breakdown["LIGHT"] == 1
    assert breakdown["CERTIFICATION"] == 1
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_sensor.py -v`
Expected: 3 new FAIL on missing classes

- [ ] **Step 3: Append classes to `sensor.py`**

Add the imports needed:

```python
from datetime import datetime, timedelta, timezone
from collections import Counter
```

Append:

```python
class DiveLogYearSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "dive_log_year"
    _attr_icon = "mdi:timeline-clock"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_dive_log_year"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        year = date.today().year
        return sum(
            1
            for d in self.coordinator.data.dives
            if datetime.fromisoformat(d.start_time).year == year
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {"dives": []}
        dives_payload = [self._dive_to_card(d) for d in self.coordinator.data.dives]
        return {"dives": dives_payload}

    def _dive_to_card(self, d: Dive) -> dict[str, Any]:
        raw = d.raw
        gear_id_to_image = self._gear_image_lookup()
        photo_for_dive = self._photo_for_dive(d)
        start = datetime.fromisoformat(raw["startTime"])
        total_seconds = float(raw["totalTime"])
        end = (start + timedelta(seconds=total_seconds)).isoformat()
        return {
            "id": d.id,
            "name": d.name,
            "start": raw["startTime"],
            "end": end,
            "timezone": raw.get("timezone"),
            "max_depth": raw.get("maxDepth"),
            # average_depth: not present in /dive/summary; spec §13 leaves it
            # to a future per-dive detail call.
            "average_depth": None,
            "bottom_time": (raw.get("bottomTime") or 0) / 60,
            "total_time": total_seconds / 60,
            "surface_interval": (raw.get("surfaceInterval") or 0) / 3600,
            "tags": raw.get("diveTags") or [],
            "gases": raw.get("gases") or [],
            "location": raw.get("entryLoc"),
            "photos": photo_for_dive,
            "connect_url": _connect_url(raw.get("connectActivityId")),
            "dive_computer": raw.get("activitySource"),
        }

    def _gear_image_lookup(self) -> dict[int, str]:
        # Reserved for future: map gear_id -> local thumb URL when dive↔gear
        # association becomes available.
        return {}

    def _photo_for_dive(self, d: Dive) -> dict[str, str | None]:
        # Photos are matched by eventDate == startTime (per the captured
        # GraphQL response). The coordinator stores them on each dive in a
        # later iteration; for now we surface an empty placeholder so the
        # attribute shape is stable from day one.
        return {"thumb": None, "medium": None, "large": None}


class DivesByTagSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "dives_by_tag"
    _attr_icon = "mdi:tag-multiple"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_dives_by_tag"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        return sum(self.coordinator.data.dive_tags.values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self.coordinator.data.dive_tags) if self.coordinator.data else {}


class GearCountSensor(GarminDiveAccountEntity, SensorEntity):
    _attr_translation_key = "gear_count"
    _attr_icon = "mdi:bag-personal"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_gear_count"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.gear) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {"by_type": {}}
        return {"by_type": dict(Counter(g.gear_type for g in self.coordinator.data.gear))}
```

Update `async_setup_entry` to include the three new sensors:

```python
    entities: list[SensorEntity] = [
        LastDiveSensor(coordinator),
        TotalDivesSensor(coordinator),
        CurrentYearDivesSensor(coordinator),
        LastDiveMaxDepthSensor(coordinator),
        LastDiveBottomTimeSensor(coordinator),
        LastDiveSurfaceIntervalSensor(coordinator),
        DiveLogYearSensor(coordinator),
        DivesByTagSensor(coordinator),
        GearCountSensor(coordinator),
    ]
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_sensor.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/sensor.py tests/test_sensor.py
git commit -m "feat(sensor): dive_log_year timeline sensor, tag breakdown, gear count"
```

---

## Task 18: `sensor.py` — per-gear-item sensors (TDD)

**Files:**
- Modify: `custom_components/garmin_dive/sensor.py`
- Modify: `tests/test_sensor.py`

For each gear item we register: `service_status`, `days_until_service`, `next_service_date`, `last_service_date`, `dives_with`, `total_dive_time`, `purchase_date`, `purchase_price`. Service-related sensors are skipped when the item isn't serviceable (per `gear.is_serviceable`).

- [ ] **Step 1: Append failing tests**

```python
async def test_per_gear_sensors(hass, load_fixture):
    from custom_components.garmin_dive.sensor import (
        GearDivesWithSensor,
        GearServiceStatusSensor,
        build_gear_entities,
    )

    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
        gear_details={
            141548: load_fixture("gear_detail_regulator"),
            247811: load_fixture("gear_detail_light"),
        },
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    entities = build_gear_entities(coord)
    # Expected sensors per item: regulator -> 7 (status + days + next/last + dives_with + total + purchase_date), etc.
    by_id = {(e.unique_id, type(e).__name__) for e in entities}
    assert any(uid.endswith("_141548_service_status") for uid, _ in by_id)
    # Light is non-serviceable -> no service_status sensor.
    assert not any(uid.endswith("_247811_service_status") for uid, _ in by_id)


async def test_gear_service_status_returns_due_indicator(hass, load_fixture):
    from custom_components.garmin_dive.sensor import GearServiceStatusSensor

    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
        gear_details={141548: load_fixture("gear_detail_regulator")},
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = GearServiceStatusSensor(coord, gear_id=141548)
    assert sensor.native_value == "not_due"


@freeze_time("2026-05-03")
async def test_gear_days_until_service(hass, load_fixture):
    from custom_components.garmin_dive.sensor import GearDaysUntilServiceSensor

    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
        gear_details={141548: load_fixture("gear_detail_regulator")},
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = GearDaysUntilServiceSensor(coord, gear_id=141548)
    # nextServiceDate=2027-04-04, today=2026-05-03 -> 336 days
    assert sensor.native_value == 336
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_sensor.py -v`
Expected: FAIL on missing classes

- [ ] **Step 3: Append to `sensor.py`**

Add imports:

```python
from .entity import GarminDiveAccountEntity, GarminDiveSubDeviceEntity
from .gear import days_until_service, is_serviceable
```

Append the classes:

```python
class _GearEntityBase(GarminDiveSubDeviceEntity):
    """Common locator for gear sub-device sensors."""

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        item = next(g for g in coordinator.data.gear if g.gear_id == gear_id)
        detail = item.detail_raw or item.summary_raw
        manufacturer = detail.get("brand")
        model = detail.get("model")
        serial = detail.get("serialNumber")
        super().__init__(
            coordinator,
            sub_device_id=str(gear_id),
            sub_device_name=item.name,
            manufacturer=manufacturer,
            model=model,
            serial_number=str(serial) if serial else None,
            entity_picture=item.photo_local_url,
        )
        self._gear_id = gear_id

    def _detail(self) -> dict[str, Any]:
        item = next(
            g for g in self.coordinator.data.gear if g.gear_id == self._gear_id
        )
        return item.detail_raw or item.summary_raw


class GearServiceStatusSensor(_GearEntityBase, SensorEntity):
    _attr_translation_key = "gear_service_status"
    _attr_icon = "mdi:tools"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["not_due", "due", "overdue"]

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_unique_id = f"{self._account_id}_{gear_id}_service_status"

    @property
    def native_value(self) -> str | None:
        ind = self._detail().get("dueIndicator")
        return ind.lower() if ind else None


class GearDaysUntilServiceSensor(_GearEntityBase, SensorEntity):
    _attr_translation_key = "gear_days_until_service"
    _attr_native_unit_of_measurement = "d"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_unique_id = f"{self._account_id}_{gear_id}_days_until_service"

    @property
    def native_value(self) -> int | None:
        return days_until_service(
            next_service_date=self._detail().get("nextServiceDate"),
            today=date.today(),
        )


class GearDateSensor(_GearEntityBase, SensorEntity):
    """Generic date-valued gear sensor."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar"

    def __init__(
        self,
        coordinator: GarminDiveCoordinator,
        *,
        gear_id: int,
        translation_key: str,
        detail_field: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_translation_key = translation_key
        self._field = detail_field
        self._attr_unique_id = f"{self._account_id}_{gear_id}_{unique_suffix}"

    @property
    def native_value(self) -> date | None:
        v = self._detail().get(self._field)
        return date.fromisoformat(v) if v else None


class GearDivesWithSensor(_GearEntityBase, SensorEntity):
    _attr_translation_key = "gear_dives_with"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_unique_id = f"{self._account_id}_{gear_id}_dives_with"

    @property
    def native_value(self) -> int:
        stats = self._detail().get("stats", {}) or {}
        return int(stats.get("numAssociatedDives") or 0)


class GearTotalDiveTimeSensor(_GearEntityBase, SensorEntity):
    _attr_translation_key = "gear_total_dive_time"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_unique_id = f"{self._account_id}_{gear_id}_total_dive_time"

    @property
    def native_value(self) -> float:
        stats = self._detail().get("stats", {}) or {}
        seconds = float(stats.get("totalAssociatedDiveTime") or 0)
        return round(seconds / 3600, 3)


class GearPurchasePriceSensor(_GearEntityBase, SensorEntity):
    _attr_translation_key = "gear_purchase_price"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_entity_category = "diagnostic"
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: GarminDiveCoordinator, *, gear_id: int) -> None:
        super().__init__(coordinator, gear_id=gear_id)
        self._attr_unique_id = f"{self._account_id}_{gear_id}_purchase_price"
        currency = self._detail().get("purchaseCurrency") or "GBP"
        self._attr_native_unit_of_measurement = currency

    @property
    def native_value(self) -> float | None:
        v = self._detail().get("purchasePrice")
        return float(v) if v is not None else None


def build_gear_entities(coordinator: GarminDiveCoordinator) -> list[SensorEntity]:
    entities: list[SensorEntity] = []
    if not coordinator.data:
        return entities
    for item in coordinator.data.gear:
        gid = item.gear_id
        # Always-present sensors
        entities.append(GearDivesWithSensor(coordinator, gear_id=gid))
        entities.append(GearTotalDiveTimeSensor(coordinator, gear_id=gid))
        if "purchasePrice" in (item.detail_raw or {}):
            entities.append(GearPurchasePriceSensor(coordinator, gear_id=gid))
        if (item.detail_raw or {}).get("purchaseDate"):
            entities.append(
                GearDateSensor(
                    coordinator,
                    gear_id=gid,
                    translation_key="gear_purchase_date",
                    detail_field="purchaseDate",
                    unique_suffix="purchase_date",
                )
            )
        # Service-related sensors
        if is_serviceable(item.gear_type):
            entities.append(GearServiceStatusSensor(coordinator, gear_id=gid))
            if (item.detail_raw or {}).get("nextServiceDate"):
                entities.append(GearDaysUntilServiceSensor(coordinator, gear_id=gid))
                entities.append(
                    GearDateSensor(
                        coordinator,
                        gear_id=gid,
                        translation_key="gear_next_service_date",
                        detail_field="nextServiceDate",
                        unique_suffix="next_service_date",
                    )
                )
            if (item.detail_raw or {}).get("lastServiceDate"):
                entities.append(
                    GearDateSensor(
                        coordinator,
                        gear_id=gid,
                        translation_key="gear_last_service_date",
                        detail_field="lastServiceDate",
                        unique_suffix="last_service_date",
                    )
                )
    return entities
```

Update `async_setup_entry` to call `build_gear_entities`:

```python
    entities.extend(build_gear_entities(coordinator))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_sensor.py -v`
Expected: all green

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/sensor.py tests/test_sensor.py
git commit -m "feat(sensor): per-gear-item service, usage, and purchase sensors"
```

---

## Task 19: `sensor.py` — per-dive-computer sensors

**Files:**
- Modify: `custom_components/garmin_dive/sensor.py`
- Modify: `tests/test_sensor.py`

Each dive computer becomes an HA sub-device with diagnostic sensors (gear tracking status, serial, part number).

- [ ] **Step 1: Append failing test**

```python
async def test_dive_computer_sub_devices(hass, load_fixture):
    from custom_components.garmin_dive.sensor import build_dive_computer_entities

    data = make_data(
        summary=load_fixture("dive_summary_full"),
        devices=load_fixture("dive_devices"),
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    entities = build_dive_computer_entities(coord)
    # Three dive_devices entries -> two with serial numbers (anonymous T1
    # without serial is excluded as it's a duplicate/cached entry).
    serials = {e._serial for e in entities if hasattr(e, '_serial') and e._serial}
    assert "3403334227" in serials
    assert "3399109144" in serials
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_sensor.py -v`
Expected: FAIL on missing function

- [ ] **Step 3: Append classes to `sensor.py`**

```python
class _DiveComputerEntityBase(GarminDiveSubDeviceEntity):
    def __init__(self, coordinator: GarminDiveCoordinator, *, serial: str) -> None:
        device_match = next(
            d for d in coordinator.data.devices if d.serial_number and str(d.serial_number) == serial
        )
        super().__init__(
            coordinator,
            sub_device_id=f"device_{serial}",
            sub_device_name=device_match.product_display_name,
            manufacturer="Garmin",
            model=device_match.product_display_name,
            serial_number=serial,
            entity_picture=device_match.raw.get("imageUrl"),
        )
        self._serial = serial


class DiveComputerGearTrackingSensor(_DiveComputerEntityBase, SensorEntity):
    _attr_translation_key = "dive_computer_gear_tracking_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["tracked", "dismissed"]
    _attr_icon = "mdi:watch"

    def __init__(self, coordinator: GarminDiveCoordinator, *, serial: str) -> None:
        super().__init__(coordinator, serial=serial)
        self._attr_unique_id = f"{self._account_id}_device_{serial}_gear_tracking"

    @property
    def native_value(self) -> str | None:
        device = next(
            d for d in self.coordinator.data.devices
            if d.serial_number and str(d.serial_number) == self._serial
        )
        v = device.raw.get("gearTrackingStatus")
        return v.lower() if v else None


class DiveComputerSerialSensor(_DiveComputerEntityBase, SensorEntity):
    _attr_translation_key = "dive_computer_serial_number"
    _attr_entity_category = "diagnostic"
    _attr_icon = "mdi:identifier"

    def __init__(self, coordinator: GarminDiveCoordinator, *, serial: str) -> None:
        super().__init__(coordinator, serial=serial)
        self._attr_unique_id = f"{self._account_id}_device_{serial}_serial"

    @property
    def native_value(self) -> str:
        return self._serial


class DiveComputerPartNumberSensor(_DiveComputerEntityBase, SensorEntity):
    _attr_translation_key = "dive_computer_part_number"
    _attr_entity_category = "diagnostic"
    _attr_icon = "mdi:barcode"

    def __init__(self, coordinator: GarminDiveCoordinator, *, serial: str) -> None:
        super().__init__(coordinator, serial=serial)
        self._attr_unique_id = f"{self._account_id}_device_{serial}_part_number"

    @property
    def native_value(self) -> str | None:
        device = next(
            d for d in self.coordinator.data.devices
            if d.serial_number and str(d.serial_number) == self._serial
        )
        return device.raw.get("partNumber")


def build_dive_computer_entities(coordinator: GarminDiveCoordinator) -> list[SensorEntity]:
    entities: list[SensorEntity] = []
    if not coordinator.data:
        return entities
    seen: set[str] = set()
    for device in coordinator.data.devices:
        if device.serial_number is None:
            continue  # skip cached/duplicate entries without a serial
        serial = str(device.serial_number)
        if serial in seen:
            continue
        seen.add(serial)
        entities.append(DiveComputerGearTrackingSensor(coordinator, serial=serial))
        entities.append(DiveComputerSerialSensor(coordinator, serial=serial))
        if device.raw.get("partNumber"):
            entities.append(DiveComputerPartNumberSensor(coordinator, serial=serial))
    return entities
```

Wire into `async_setup_entry`:

```python
    entities.extend(build_dive_computer_entities(coordinator))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_sensor.py -v`
Expected: all green

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/sensor.py tests/test_sensor.py
git commit -m "feat(sensor): per-dive-computer sub-devices and diagnostic sensors"
```

---

## Task 20: Binary sensors — `service_due` + `new_dive_available`

**Files:**
- Create: `custom_components/garmin_dive/binary_sensor.py`
- Modify: `tests/test_sensor.py` (or create `tests/test_binary_sensor.py`)

`service_due` reflects gear state. `new_dive_available` is acknowledged via the `garmin_dive.acknowledge_new_dive` service (added in Task 28); for now it stays `on` until the next refresh after the user explicitly clears it.

- [ ] **Step 1: Write failing tests in a new file `tests/test_binary_sensor.py`**

```python
"""Tests for binary sensors."""
from __future__ import annotations

from custom_components.garmin_dive.coordinator import (
    CoordinatorData,
    GearItem,
)
from custom_components.garmin_dive.gear import GearSnapshot

from tests.conftest_helpers import make_data, make_fake_coordinator


async def test_service_due_on_when_any_gear_due(hass, load_fixture):
    from custom_components.garmin_dive.binary_sensor import ServiceDueBinarySensor

    detail = load_fixture("gear_detail_regulator").copy()
    detail["dueIndicator"] = "DUE"
    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
        gear_details={141548: detail},
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = ServiceDueBinarySensor(coord)
    assert sensor.is_on is True


async def test_service_due_off_when_all_not_due(hass, load_fixture):
    from custom_components.garmin_dive.binary_sensor import ServiceDueBinarySensor

    data = make_data(
        summary=load_fixture("dive_summary_full"),
        gear_summary=load_fixture("gear_summary"),
        gear_details={141548: load_fixture("gear_detail_regulator")},
    )
    coord = make_fake_coordinator(hass=hass, data=data)
    sensor = ServiceDueBinarySensor(coord)
    assert sensor.is_on is False


async def test_new_dive_available_latches_until_acknowledged(hass, load_fixture):
    from custom_components.garmin_dive.binary_sensor import NewDiveAvailableBinarySensor

    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    coord._latest_dive_acknowledged_id = None
    sensor = NewDiveAvailableBinarySensor(coord)
    assert sensor.is_on is True
    coord._latest_dive_acknowledged_id = 23285230  # latest dive id
    assert sensor.is_on is False
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_binary_sensor.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Write `binary_sensor.py`**

```python
"""Binary sensors for Garmin Dive."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import GarminDiveAccountEntity

if TYPE_CHECKING:
    from .coordinator import GarminDiveCoordinator


class ServiceDueBinarySensor(GarminDiveAccountEntity, BinarySensorEntity):
    _attr_translation_key = "service_due"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:wrench-clock"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_service_due"

    @property
    def is_on(self) -> bool:
        if not self.coordinator.data:
            return False
        return any(
            (g.detail_raw or g.summary_raw).get("dueIndicator") in {"DUE", "OVERDUE"}
            for g in self.coordinator.data.gear
        )


class NewDiveAvailableBinarySensor(GarminDiveAccountEntity, BinarySensorEntity):
    _attr_translation_key = "new_dive_available"
    _attr_device_class = BinarySensorDeviceClass.UPDATE
    _attr_icon = "mdi:diving-helmet"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_new_dive_available"

    @property
    def is_on(self) -> bool:
        if not self.coordinator.data or not self.coordinator.data.dives:
            return False
        latest = self.coordinator.data.dives[0].id
        ack = getattr(self.coordinator, "_latest_dive_acknowledged_id", None)
        return ack != latest


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GarminDiveCoordinator = entry.runtime_data
    async_add_entities(
        [
            ServiceDueBinarySensor(coordinator),
            NewDiveAvailableBinarySensor(coordinator),
        ]
    )
```

Add a default attribute to the coordinator. In `coordinator.py`, in `GarminDiveCoordinator.__init__`, add at the end:

```python
        self._latest_dive_acknowledged_id: int | None = None
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_binary_sensor.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/binary_sensor.py custom_components/garmin_dive/coordinator.py tests/test_binary_sensor.py
git commit -m "feat(binary_sensor): service_due and new_dive_available sensors"
```

---

## Task 21: Calendar entity (TDD)

**Files:**
- Create: `custom_components/garmin_dive/calendar.py`
- Create: `tests/test_calendar.py`

Each dive becomes a `CalendarEvent`. `start = startTime`; `end = startTime + totalTime`.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the Garmin Dive calendar entity."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest_helpers import make_data, make_fake_coordinator


async def test_calendar_event_for_each_dive(hass, load_fixture):
    from custom_components.garmin_dive.calendar import GarminDiveCalendarEntity

    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    cal = GarminDiveCalendarEntity(coord)

    start = datetime(2025, 8, 25, 0, 0, tzinfo=timezone.utc)
    end = datetime(2025, 8, 27, 0, 0, tzinfo=timezone.utc)
    events = await cal.async_get_events(hass, start, end)

    assert len(events) == 3
    e = next(ev for ev in events if "South side" in ev.summary)
    assert "Max depth" in e.description
    assert e.location == "Africa/Cairo"


async def test_calendar_next_event(hass, load_fixture):
    from custom_components.garmin_dive.calendar import GarminDiveCalendarEntity

    data = make_data(summary=load_fixture("dive_summary_full"))
    coord = make_fake_coordinator(hass=hass, data=data)
    cal = GarminDiveCalendarEntity(coord)
    # `event` returns the soonest upcoming or most-recent past event.
    assert cal.event is not None
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_calendar.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Write `calendar.py`**

```python
"""Calendar entity exposing each dive as a calendar event."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import GarminDiveAccountEntity

if TYPE_CHECKING:
    from .coordinator import GarminDiveCoordinator, Dive


def _dive_to_event(d: Dive) -> CalendarEvent:
    raw = d.raw
    start = datetime.fromisoformat(raw["startTime"])
    end = start + timedelta(seconds=float(raw["totalTime"]))
    description_lines = [
        f"Max depth: {raw.get('maxDepth')} m",
        f"Bottom time: {round((raw.get('bottomTime') or 0) / 60)} min",
        f"Total time: {round((raw.get('totalTime') or 0) / 60)} min",
    ]
    if raw.get("diveTags"):
        description_lines.append("Tags: " + ", ".join(raw["diveTags"]))
    if cid := raw.get("connectActivityId"):
        description_lines.append(
            f"Garmin Connect: https://connect.garmin.com/modern/activity/{cid}"
        )
    return CalendarEvent(
        start=start,
        end=end,
        summary=raw["name"],
        description="\n".join(description_lines),
        location=raw.get("timezone") or "",
    )


class GarminDiveCalendarEntity(GarminDiveAccountEntity, CalendarEntity):
    _attr_translation_key = "dives"
    _attr_icon = "mdi:calendar-blank-outline"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_calendar_dives"

    @property
    def event(self) -> CalendarEvent | None:
        if not self.coordinator.data or not self.coordinator.data.dives:
            return None
        return _dive_to_event(self.coordinator.data.dives[0])

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        if not self.coordinator.data:
            return []
        result: list[CalendarEvent] = []
        for d in self.coordinator.data.dives:
            ev = _dive_to_event(d)
            if ev.end >= start_date and ev.start <= end_date:
                result.append(ev)
        return result


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GarminDiveCoordinator = entry.runtime_data
    async_add_entities([GarminDiveCalendarEntity(coordinator)])
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_calendar.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/calendar.py tests/test_calendar.py
git commit -m "feat(calendar): expose each dive as a calendar event"
```

---

## Task 22: Button — manual refresh

**Files:**
- Create: `custom_components/garmin_dive/button.py`
- Create: `tests/test_button.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the refresh button."""
from __future__ import annotations

from unittest.mock import AsyncMock

from tests.conftest_helpers import make_fake_coordinator


async def test_press_calls_async_request_refresh(hass):
    from custom_components.garmin_dive.button import RefreshButton

    coord = make_fake_coordinator(hass=hass)
    coord.async_request_refresh = AsyncMock()
    btn = RefreshButton(coord)
    await btn.async_press()
    coord.async_request_refresh.assert_awaited_once()
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_button.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Write `button.py`**

```python
"""Manual refresh button."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import GarminDiveAccountEntity

if TYPE_CHECKING:
    from .coordinator import GarminDiveCoordinator


class RefreshButton(GarminDiveAccountEntity, ButtonEntity):
    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: GarminDiveCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GarminDiveCoordinator = entry.runtime_data
    async_add_entities([RefreshButton(coordinator)])
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_button.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/button.py tests/test_button.py
git commit -m "feat(button): manual refresh button"
```

---

## Task 23: Config flow — user step + MFA + reauth (TDD)

**Files:**
- Create: `custom_components/garmin_dive/config_flow.py`
- Create: `tests/test_config_flow.py`

`ha_garmin.GarminAuth.login` is synchronous, so we run it inside `hass.async_add_executor_job` (the work happens inside `GarminDiveAuth.login`). MFA is signalled by `ha_garmin` raising `GarminMFARequired`; our `GarminDiveAuth.login` accepts an async `mfa_provider` callable that resolves the user-entered code. The config flow plumbs that callable through an `asyncio.Future` so the user types the code in a separate `async_step_mfa` form.

- [ ] **Step 1: Write failing tests**

```python
"""Tests for the Garmin Dive config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def social_profile_payload(load_fixture):
    return load_fixture("social_profile_v2")


async def test_user_step_happy_path(hass, social_profile_payload):
    """Login succeeds without MFA."""
    with patch(
        "custom_components.garmin_dive.config_flow.GarminDiveAuth"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.login = AsyncMock(return_value=social_profile_payload)
        instance.serialize = MagicMock(return_value={"profile_id": 106627261})
        instance.save_ha_garmin_session = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            "garmin_dive", context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": "test@example.invalid", "password": "secret"},
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"].startswith("Garmin Dive")
        assert result["data"]["profile_id"] == 106627261


async def test_user_step_invalid_credentials(hass):
    with patch(
        "custom_components.garmin_dive.config_flow.GarminDiveAuth"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.login = AsyncMock(side_effect=Exception("Bad credentials"))

        result = await hass.config_entries.flow.async_init(
            "garmin_dive", context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": "x@example.invalid", "password": "wrong"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_unique_id_is_profile_id(hass, social_profile_payload):
    with patch(
        "custom_components.garmin_dive.config_flow.GarminDiveAuth"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.login = AsyncMock(return_value=social_profile_payload)
        instance.serialize = MagicMock(return_value={"profile_id": 106627261})
        instance.save_ha_garmin_session = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            "garmin_dive", context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": "test@example.invalid", "password": "secret"},
        )
        entry = result["result"]
        assert entry.unique_id == "106627261"
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_config_flow.py -v`
Expected: FAIL — `Integration garmin_dive not found` (config flow missing)

- [ ] **Step 3: Write `config_flow.py`**

```python
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

        self._email = user_input[CONF_EMAIL]
        self._password = user_input[CONF_PASSWORD]
        return await self._start_login()

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                step_id="mfa", data_schema=MFA_SCHEMA, errors={"base": "invalid_auth"}
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
                [self._login_task], timeout=4.0, return_when=asyncio.FIRST_COMPLETED
            )
            if done:
                profile = self._login_task.result()
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
        session_path = self.hass.config.path(
            ".storage", f"{DOMAIN}_{profile_id}_session.json"
        )
        Path(session_path).parent.mkdir(parents=True, exist_ok=True)
        await self._auth.save_ha_garmin_session(self.hass, session_path)

        title = (
            "Garmin Dive — "
            f"{profile.get('displayName') or profile.get('fullName') or profile_id}"
        )
        return self.async_create_entry(title=title, data=self._auth.serialize())

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_config_flow.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add custom_components/garmin_dive/config_flow.py tests/test_config_flow.py
git commit -m "feat(config_flow): user/MFA/reauth flow + options flow"
```

---

## Task 24: `__init__.py` — full setup_entry, services, runtime_data wiring

**Files:**
- Modify: `custom_components/garmin_dive/__init__.py`
- Create: `custom_components/garmin_dive/services.yaml`
- Modify: `tests/test_init.py` (new)

- [ ] **Step 1: Write failing init test**

```python
"""Tests for async_setup_entry and platform fan-out."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garmin_dive.const import DOMAIN


@pytest.fixture
def patched_auth(load_fixture):
    with patch("custom_components.garmin_dive.GarminDiveAuth") as cls:
        instance = cls.return_value
        instance.profile_id = 106627261
        instance.profile_display_name = "Rob"
        instance.get_dive_token = AsyncMock(return_value="dive-token")
        yield instance


@pytest.fixture
def patched_coordinator(load_fixture):
    with patch("custom_components.garmin_dive.GarminDiveCoordinator") as cls:
        instance = cls.return_value
        instance.async_config_entry_first_refresh = AsyncMock()
        instance.async_request_refresh = AsyncMock()
        instance.data = MagicMock()
        yield cls, instance


async def test_setup_entry_creates_runtime_data_and_loads_platforms(
    hass, patched_auth, patched_coordinator
):
    cls, instance = patched_coordinator
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"profile_id": 106627261, "dive_access_token": "tok"},
        unique_id="106627261",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is instance


async def test_unload_entry_unloads_platforms(hass, patched_auth, patched_coordinator):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"profile_id": 106627261, "dive_access_token": "tok"},
        unique_id="106627261",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/test_init.py -v`
Expected: FAIL — runtime_data not set

- [ ] **Step 3: Replace `__init__.py` with the full implementation**

```python
"""Garmin Dive integration for Home Assistant."""
from __future__ import annotations

import logging
from pathlib import Path

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
    DOMAIN,
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
    api = GarminDiveClient(
        session=session,
        get_token=lambda: auth.get_dive_token(),
    )
    ha_auth = GarminAuth()
    auth = GarminDiveAuth.from_entry_data(
        entry.data, ha_auth=ha_auth, api=api
    )

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
        www_dir.mkdir(parents=True, exist_ok=True)
        account_short = str(auth.profile_id)[:8]
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
                if hasattr(e, "runtime_data") and e.runtime_data.data:
                    if e.runtime_data.data.dives:
                        e.runtime_data._latest_dive_acknowledged_id = (
                            e.runtime_data.data.dives[0].id
                        )
                        e.runtime_data.async_update_listeners()

        hass.services.async_register(DOMAIN, "refresh", _service_refresh)
        hass.services.async_register(DOMAIN, "acknowledge_new_dive", _service_acknowledge)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Garmin Dive config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Future-proof migration handler."""
    return True
```

- [ ] **Step 4: Write `services.yaml`**

```yaml
refresh:
  name: Refresh
  description: Force an immediate refresh of all Garmin Dive accounts.

acknowledge_new_dive:
  name: Acknowledge new dive
  description: Mark the latest dive as seen so the new_dive_available binary sensor turns off.
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_init.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add custom_components/garmin_dive/__init__.py custom_components/garmin_dive/services.yaml tests/test_init.py
git commit -m "feat: full async_setup_entry, runtime_data, and services"
```

---

## Task 25: Diagnostics

**Files:**
- Create: `custom_components/garmin_dive/diagnostics.py`

- [ ] **Step 1: Write `diagnostics.py`**

```python
"""Diagnostics for Garmin Dive — redacts every token and PII field."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

REDACT = {
    "dive_access_token",
    "dive_refresh_token",
    "session_path",
    "profile_id",
    "userName",
    "garminGUID",
    "displayName",
    "fullName",
    "email",
    "password",
    "url",  # signed S3 URLs
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coord = entry.runtime_data
    snapshot: dict[str, Any] = {"entry_data": async_redact_data(dict(entry.data), REDACT)}
    if coord and coord.data:
        snapshot["data"] = {
            "total_dives": coord.data.total_dives,
            "dives_count": len(coord.data.dives),
            "devices_count": len(coord.data.devices),
            "gear_count": len(coord.data.gear),
            "tags": coord.data.dive_tags,
        }
    return snapshot
```

- [ ] **Step 2: Commit**

```bash
git add custom_components/garmin_dive/diagnostics.py
git commit -m "feat(diagnostics): redacted config-entry diagnostics"
```

---

## Task 26: `strings.json`, `translations/en.json`, `icons.json`

**Files:**
- Create: `custom_components/garmin_dive/strings.json`
- Create: `custom_components/garmin_dive/translations/en.json` (mirror of strings.json)
- Create: `custom_components/garmin_dive/icons.json`

- [ ] **Step 1: Write `strings.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Sign in to Garmin",
        "data": { "email": "Email", "password": "Password" }
      },
      "mfa": {
        "title": "Two-factor code",
        "description": "Enter the code from your authenticator app or text message.",
        "data": { "mfa_code": "Code" }
      },
      "reauth_confirm": {
        "title": "Re-authenticate",
        "data": { "email": "Email", "password": "Password" }
      }
    },
    "error": {
      "invalid_auth": "Invalid credentials.",
      "cannot_connect": "Failed to connect to Garmin.",
      "unknown_error": "Unexpected error."
    },
    "abort": {
      "already_configured": "This Garmin account is already configured."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Garmin Dive options",
        "data": {
          "scan_interval_minutes": "Polling interval (minutes)",
          "photo_cache_enabled": "Cache photos locally",
          "history_scope": "History scope",
          "max_cache_age_days": "Max cache age (days, 0 = never evict)"
        }
      }
    }
  },
  "entity": {
    "sensor": {
      "last_dive": { "name": "Last dive" },
      "total_dives": { "name": "Total dives" },
      "current_year_dives": { "name": "Dives this year" },
      "dives_by_tag": { "name": "Dives by tag" },
      "last_dive_max_depth": { "name": "Last dive max depth" },
      "last_dive_bottom_time": { "name": "Last dive bottom time" },
      "last_dive_surface_interval": { "name": "Last dive surface interval" },
      "dive_log_year": { "name": "Dive log (year)" },
      "gear_count": { "name": "Gear items" },
      "gear_service_status": { "name": "Service status" },
      "gear_days_until_service": { "name": "Days until service" },
      "gear_next_service_date": { "name": "Next service date" },
      "gear_last_service_date": { "name": "Last service date" },
      "gear_dives_with": { "name": "Dives with" },
      "gear_total_dive_time": { "name": "Total dive time" },
      "gear_purchase_date": { "name": "Purchase date" },
      "gear_purchase_price": { "name": "Purchase price" },
      "dive_computer_gear_tracking_status": { "name": "Gear tracking" },
      "dive_computer_serial_number": { "name": "Serial" },
      "dive_computer_part_number": { "name": "Part number" }
    },
    "binary_sensor": {
      "service_due": { "name": "Service due" },
      "new_dive_available": { "name": "New dive available" }
    },
    "calendar": {
      "dives": { "name": "Dives" }
    },
    "button": {
      "refresh": { "name": "Refresh" }
    }
  },
  "services": {
    "refresh": {
      "name": "Refresh",
      "description": "Force an immediate refresh of all Garmin Dive accounts."
    },
    "acknowledge_new_dive": {
      "name": "Acknowledge new dive",
      "description": "Clear the New Dive Available binary sensor."
    }
  }
}
```

- [ ] **Step 2: Mirror `strings.json` → `translations/en.json`**

```bash
mkdir -p custom_components/garmin_dive/translations
cp custom_components/garmin_dive/strings.json custom_components/garmin_dive/translations/en.json
```

- [ ] **Step 3: Write `icons.json`**

```json
{
  "entity": {
    "sensor": {
      "last_dive": { "default": "mdi:diving-scuba" },
      "total_dives": { "default": "mdi:counter" },
      "current_year_dives": { "default": "mdi:calendar-month" },
      "dives_by_tag": { "default": "mdi:tag-multiple" },
      "last_dive_max_depth": { "default": "mdi:arrow-collapse-down" },
      "last_dive_bottom_time": { "default": "mdi:timer-sand" },
      "last_dive_surface_interval": { "default": "mdi:timer" },
      "dive_log_year": { "default": "mdi:timeline-clock" },
      "gear_count": { "default": "mdi:bag-personal" },
      "gear_service_status": { "default": "mdi:tools" },
      "gear_days_until_service": { "default": "mdi:calendar-clock" },
      "gear_next_service_date": { "default": "mdi:calendar" },
      "gear_last_service_date": { "default": "mdi:calendar" },
      "gear_dives_with": { "default": "mdi:counter" },
      "gear_total_dive_time": { "default": "mdi:timer-outline" },
      "gear_purchase_date": { "default": "mdi:calendar" },
      "gear_purchase_price": { "default": "mdi:cash" },
      "dive_computer_gear_tracking_status": { "default": "mdi:watch" },
      "dive_computer_serial_number": { "default": "mdi:identifier" },
      "dive_computer_part_number": { "default": "mdi:barcode" }
    },
    "binary_sensor": {
      "service_due": { "default": "mdi:wrench-clock" },
      "new_dive_available": { "default": "mdi:diving-helmet" }
    },
    "calendar": {
      "dives": { "default": "mdi:calendar-blank-outline" }
    },
    "button": {
      "refresh": { "default": "mdi:refresh" }
    }
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add custom_components/garmin_dive/strings.json custom_components/garmin_dive/icons.json custom_components/garmin_dive/translations/
git commit -m "feat(i18n): strings, English translations, and icons"
```

---

## Task 27: Pre-commit + ruff configuration

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Write `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/codespell-project/codespell
    rev: v2.3.0
    hooks:
      - id: codespell
        args: [--skip, "tests/fixtures/*,*.json"]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: check-added-large-files
        args: [--maxkb=500]
```

- [ ] **Step 2: Run formatters once across the tree**

Run: `pre-commit run --all-files || true`
Then: `git add -u && git status`

(Some files will get auto-fixed; review the diff before committing.)

- [ ] **Step 3: Commit any formatting changes**

```bash
git add .pre-commit-config.yaml
# include any auto-fixes
git add -u
git commit -m "chore: add pre-commit with ruff, codespell, basic hooks"
```

---

## Task 28: GitHub Actions — `validate.yml`

**Files:**
- Create: `.github/workflows/validate.yml`

- [ ] **Step 1: Write `.github/workflows/validate.yml`**

```yaml
name: Validate

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: "0 0 * * *"

jobs:
  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master

  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: HACS Action
        uses: hacs/action@main
        with:
          category: integration
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "ci: add hassfest + HACS validation workflow"
```

---

## Task 29: GitHub Actions — `lint.yml` and `test.yml`

**Files:**
- Create: `.github/workflows/lint.yml`
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Write `.github/workflows/lint.yml`**

```yaml
name: Lint

on:
  push:
    branches: [main]
  pull_request:

jobs:
  ruff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check .
      - run: ruff format --check .

  mypy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements_dev.txt
      - run: mypy

  codespell:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: codespell-project/actions-codespell@v2
        with:
          skip: tests/fixtures/*,*.json
```

- [ ] **Step 2: Write `.github/workflows/test.yml`**

```yaml
name: Test

on:
  push:
    branches: [main]
  pull_request:

jobs:
  pytest:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements_dev.txt
      - run: pytest -v --cov=custom_components/garmin_dive --cov-report=term-missing
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/lint.yml .github/workflows/test.yml
git commit -m "ci: add lint and pytest workflows"
```

---

## Task 30: GitHub Actions — `release.yml`

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Write `.github/workflows/release.yml`**

```yaml
name: Release

on:
  release:
    types: [published]

jobs:
  release-zip:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Sync manifest version with release tag
        run: |
          VERSION="${GITHUB_REF_NAME#v}"
          python - <<PY
          import json, pathlib
          p = pathlib.Path("custom_components/garmin_dive/manifest.json")
          m = json.loads(p.read_text())
          m["version"] = "${VERSION}"
          p.write_text(json.dumps(m, indent=2) + "\n")
          PY

      - name: Zip integration
        run: |
          cd custom_components/garmin_dive
          zip -r ../../garmin_dive.zip .

      - name: Upload to release
        uses: softprops/action-gh-release@v2
        with:
          files: garmin_dive.zip
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: tag-driven release zip workflow"
```

---

## Task 31: dependabot, CODEOWNERS, ISSUE_TEMPLATE

**Files:**
- Create: `.github/CODEOWNERS`
- Create: `.github/dependabot.yml`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`

- [ ] **Step 1: Write `.github/CODEOWNERS`**

```
* @robemmerson
```

- [ ] **Step 2: Write `.github/dependabot.yml`**

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
```

- [ ] **Step 3: Write `.github/ISSUE_TEMPLATE/bug_report.yml`**

```yaml
name: Bug report
description: Something doesn't work as expected.
labels: [bug]
body:
  - type: textarea
    id: what
    attributes:
      label: What happened?
      description: Describe the problem.
    validations:
      required: true
  - type: input
    id: ha_version
    attributes:
      label: Home Assistant version
      placeholder: 2026.1.0
    validations:
      required: true
  - type: input
    id: integration_version
    attributes:
      label: ha-garmin-dive version
      placeholder: 0.1.0
    validations:
      required: true
  - type: textarea
    id: logs
    attributes:
      label: Relevant log output
      render: text
```

- [ ] **Step 4: Write `.github/ISSUE_TEMPLATE/feature_request.yml`**

```yaml
name: Feature request
description: Suggest an enhancement.
labels: [enhancement]
body:
  - type: textarea
    id: idea
    attributes:
      label: What would you like?
    validations:
      required: true
```

- [ ] **Step 5: Commit**

```bash
git add .github/
git commit -m "ci: dependabot, CODEOWNERS, and issue templates"
```

---

## Task 32: README — dashboard examples + finish HACS card

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the "Dashboard" placeholder with concrete examples**

Open `README.md` and replace the line `See the **Dashboard** section below — *populated in Task 43*.` with this block:

````markdown
## Dashboard

Two dashboard recipes that go well with this integration. Both assume entity IDs `sensor.garmin_dive_rob_dive_log_year` and `calendar.garmin_dive_rob_dives` — adjust to match your account names.

### Yearly dive timeline (horizontally scrolling cards)

Requires the [`auto-entities`](https://github.com/thomasloven/lovelace-auto-entities) and [`mushroom`](https://github.com/piitaya/lovelace-mushroom) custom cards.

```yaml
type: horizontal-stack
cards:
  - type: custom:auto-entities
    card:
      type: horizontal-stack
    card_param: cards
    filter:
      template: >
        {% set dives = state_attr('sensor.garmin_dive_rob_dive_log_year', 'dives') or [] %}
        {% for d in dives %}
          {{ {
            "type": "picture-elements",
            "image": d.photos.medium or "/local/garmin_dive/placeholder.png",
            "elements": [
              {
                "type": "state-label",
                "entity": "sensor.garmin_dive_rob_last_dive",
                "style": {"top": "10%", "left": "10%"}
              },
              {
                "type": "custom:mushroom-template-card",
                "primary": d.name,
                "secondary": "{{ '%.1f m' | format(d.max_depth) }} · {{ '%.0f min' | format(d.bottom_time) }}",
                "icon": "mdi:diving-scuba",
                "style": {"top": "70%", "left": "5%", "width": "90%"}
              }
            ]
          } }}
        {% endfor %}
```

(For a polished version with photo lightbox, see the wiki — link added once published.)

### Native HA Calendar card

```yaml
type: calendar
entities:
  - calendar.garmin_dive_rob_dives
  - calendar.garmin_dive_ana_dives
initial_view: dayGridMonth
```

### Service-due alert

```yaml
- alias: "Garmin Dive: gear service due notification"
  trigger:
    - platform: event
      event_type: garmin_dive_service_due
  action:
    - service: notify.mobile_app_robs_phone
      data:
        title: "Diving gear service due"
        message: "{{ trigger.event.data.gear.name }} is {{ trigger.event.data.indicator | lower }}"
```
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add dashboard examples and service-due automation recipe"
```

---

## Task 33: Final cross-check (lint, type-check, tests, hassfest local)

**Files:** none modified directly; this task verifies the whole repo passes the gates the CI will enforce.

- [ ] **Step 1: Activate dev environment**

Run:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_dev.txt
```

- [ ] **Step 2: Run ruff (lint + format)**

Run: `ruff check . && ruff format --check .`
Expected: no errors. If formatting drifts, run `ruff format .` and amend the most recent commit.

- [ ] **Step 3: Run mypy**

Run: `mypy`
Expected: no errors.

- [ ] **Step 4: Run pytest with coverage**

Run: `pytest -v --cov=custom_components/garmin_dive --cov-report=term-missing`
Expected: all tests pass; coverage ≥ 80%.

- [ ] **Step 5: Run hassfest locally**

Run:
```bash
docker run --rm -v "$(pwd):/github/workspace" -w /github/workspace ghcr.io/home-assistant/hassfest:latest --integration-path custom_components/garmin_dive
```
(If Docker isn't available, skip — CI will run it on push.)

- [ ] **Step 6: Push initial branch and confirm CI green**

```bash
git push -u origin main
```
Open the **Actions** tab on GitHub and confirm `Validate`, `Lint`, and `Test` all green.

If anything fails, fix and commit before declaring this task done.

---

## Self-review notes (already applied during plan authoring)

- **Spec coverage:** every section of `2026-05-03-ha-garmin-dive-design.md` maps to at least one task — auth (T8–9, T23), API (T5–8), gear delta (T10), photo cache (T11), coordinator (T12–14), entities (T15–22), config flow (T23), wiring (T24), diagnostics (T25), i18n (T26), CI (T27–31), docs (T32), gate (T33).
- **Type consistency:** the dataclass names (`CoordinatorData`, `Dive`, `DiveDevice`, `GearItem`, `GearSnapshot`, `PhotoCache`, `PhotoRecord`, `GarminDiveAuth`, `GarminDiveClient`, `GarminDiveCoordinator`) and method names (`build_data`, `needs_detail_fetch`, `detect_service_status_flips`, `is_serviceable`, `days_until_service`, `get_dive_token`, `get_dive_summary`, etc.) are used identically across all tasks that reference them.
- **No placeholders:** every code block is complete; every CLI command shows expected output where one exists.
- **Spec §13 open questions** are surfaced at the right point: dive-photos GraphQL operation in Task 7, `average_depth` source in Task 17 (set to `None` until discovered), gear `lastModifiedTs` fallback in Task 10.
- **Frequent commits:** each task ends with a commit using Conventional Commits, no Claude attribution, no `--no-verify`.

---

## Execution choice

Plan complete and saved to `docs/superpowers/plans/2026-05-03-ha-garmin-dive.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
