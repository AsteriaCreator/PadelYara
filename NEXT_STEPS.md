# Next Steps

_Last updated: 2026-05-16_

## Current state (verified 2026-05-16)

- Eversports scraper: **working** — returns `free`/`busy` for all tested venues
- eTennis scraper: **working** — returns `free`/`busy`/`no_slot` after background pass
- Render backend: **working** at `https://neopadelchecker.onrender.com`
- Railway Eversports service: **working** at `https://neo-padel-checker-backend-production.up.railway.app`
- Region-based personal mode: fully functional

## Ready to do next

### Option A — Public location search (recommended first)
The `/api/search` endpoint already accepts `lat`/`lon`/`radius` for location-based queries.
The frontend just needs a location input field wired to geocoding + those params.
This unlocks the app for anyone, not just personal-mode regions.

### Option B — MongoDB venue management
`Backend/venues_mongo.py` and `Backend/main.py` are stubs ready for this.
Would allow adding/editing venues without a Render redeploy.
Do this **after** Option A is decided — CSV is fine for personal mode.

### Option C — Verify remaining Wien Sued Eversports venues
`padelzone-wien-c-c-wienerberg` (facility_id 77636) has not been tested end-to-end.
Quick smoke test: `GET /api/search?region=Wien%20Sued&date=TOMORROW&time=18:00`

## Constraints (do not change)

- Do NOT rewrite the app
- Do NOT change scraper logic
- Do NOT change deployment branches (`main` for Render, `claude/affectionate-goodall-0ededf` for Railway)
- Preserve current region-based personal mode
- Do NOT start MongoDB migration until Option A is decided
