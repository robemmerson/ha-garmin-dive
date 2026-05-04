# Dive Travel Story dashboard

A trip-themed Lovelace dashboard for `ha-garmin-dive`: every dive is grouped
by **(country, year)** and surfaced as a hero-image tile. Tap a tile and the
view replaces itself with that destination's dives + a combined photo album.

This folder lives on a side branch (`experiment/dashboard-travel-story`) and
is **not** intended to be merged into `main` — it's a personal dashboard
config kept here for safekeeping.

## What's in here

| File | Purpose |
|---|---|
| `helpers.yaml` | `input_text` storage + scripts + the `sensor.garmin_dive_destinations` template sensor that does all the grouping work. |
| `dashboard.yaml` | The Lovelace view. Slim — just reads `sensor.garmin_dive_destinations` and renders. |
| `README.md` | This file. |

## Requirements

- `ha-garmin-dive` ≥ **0.3.5** (PR #33 must be live — the dashboard reads
  `dive.photos_all` for the multi-photo gallery).
- HACS frontend cards: **`auto-entities`**, **`mushroom`**, **`card-mod`**.
  (`browser_mod` not needed — the destination detail replaces the grid
  in-place via a conditional card, no popup library required.)

## Install

1. **Helpers + sensor**: copy the contents of `helpers.yaml` into your
   `configuration.yaml` (or split across `inputs.yaml` / `scripts.yaml` /
   `templates.yaml` if you `!include` separately). Restart HA so the
   `template:` sensor registers.

2. **Verify the aggregator**: in *Developer Tools → States*, search for
   `sensor.garmin_dive_destinations`. Its state is the trip count, and the
   `destinations` attribute is a list of `{key, country, year, dive_count,
   rob_count, ana_count, hero_url}`. Looks empty? See "Troubleshooting".

3. **Dashboard**: in *Settings → Dashboards → Edit dashboard → Raw editor*,
   paste the contents of `dashboard.yaml` as a single view. (Or drop it as
   one entry in your `views:` list.)

4. **Account UUIDs**: the YAML hardcodes Rob's and Ana's `dive_log_year`
   sensor entity IDs. If yours differ, search/replace these two strings in
   both YAML files:
   - `60bc41f5_d81c_4c75_adcb_7e9581ed44e3` (Rob)
   - `180ace30_1ef0_455e_bb55_4cefc6cc73e2` (Ana)

## Adding a country

`sensor.garmin_dive_destinations` derives country from each dive's
**timezone** field (`Asia/Bangkok` → Thailand, `Africa/Cairo` → Egypt, etc).
The map lives in `helpers.yaml` under `attributes.tz_map` and ships with
~50 dive-friendly zones pre-populated.

If a destination shows up as **`Unknown — <some-timezone>`**, take that
timezone string and add a row to the `tz_map` in `helpers.yaml`:

```yaml
tz_map: >-
  {{
    {
      ...
      'Pacific/Tarawa': 'Kiribati',     # add me
      ...
    } | to_json
  }}
```

Then *Developer Tools → YAML → Reload Template Entities*.

## Pinning the hero image

Auto-pick is "first photo with a `medium` URL across the trip's dives". To
override:

```yaml
service: script.garmin_dive_pin_hero
data:
  destination_key: thailand-2024
  image_uuid: f515da19-70dd-427e-9d23-5335acacd041
```

(Find image UUIDs in *Developer Tools → States* on the relevant
`dive_log_year` sensor — the `dives[].photos_all[].medium` URLs contain
the UUID.)

To unpin:

```yaml
service: script.garmin_dive_pin_hero
data:
  destination_key: thailand-2024
  image_uuid: ""
```

Pins persist across HA restarts (stored in `input_text.garmin_dive_hero_pins`
as JSON).

## Troubleshooting

**No tiles render.** Check `sensor.garmin_dive_destinations` state — if it's
0, the underlying `dive_log_year` sensors haven't loaded. Wait for one
coordinator refresh cycle (default 2 hours, or hit the *Refresh* button on
either Garmin Dive device).

**Country says `Unknown — <tz>`.** Add the TZ to the `tz_map` (above).

**A destination has no hero image.** Either (a) none of the dives in that
trip have any photos yet, or (b) photos haven't downloaded to the cache yet.
Open the diagnostics download from the integration and look at the
`photos.matched_dives` / `photos.activity_fallback_matched` counters.

**Tile heights jumping around.** The 160px height is set in `card_mod`
inside the auto-entities template — adjust the `height: 160px;` in
`dashboard.yaml` to taste.

**Detail page is empty for a destination I clicked.** Likely a
`destination_key` mismatch caused by a country-name change in `tz_map` —
re-clicking the tile after the reload fixes it (the key is recomputed from
the current map every render).
