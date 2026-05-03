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
