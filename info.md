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
