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
SERVICEABLE_GEAR_TYPES: Final = frozenset({"REGULATOR", "BCD", "TRANSMITTER", "REBREATHER", "TANK"})

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
