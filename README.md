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

> **Note (v0.1):** Per-dive photo URLs are populated as `null` until a follow-up release wires the Dive Photos GraphQL operation (see spec §13 — operation name TBD). The `or "/local/garmin_dive/placeholder.png"` fallback above keeps the cards rendering with a placeholder image. **Gear photos** are wired and work today via the `entity_picture` on each gear sub-device.

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

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_dev.txt
pre-commit install
pytest
```

## License

MIT — see `LICENSE`.
