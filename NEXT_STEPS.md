# Next Steps

_Last updated: 2026-06-01_

## Current state (verified 2026-06-01)

- Eversports scraper: **working** — returns `free`/`busy` for all tested venues
- eTennis scraper: **working** — returns `free`/`busy`/`no_slot` after background pass
- Backend: **single Railway service** at `https://neo-padel-checker-backend-production.up.railway.app`
- Frontend: **Vercel** pointing directly to Railway (Render retired)
- Architecture: consolidated — eTennis + Eversports in one `app.py` on Railway

## Infrastructure completed

- ✅ Merged `consolidate-railway-backend` → `main`
- ✅ Render retired — no longer in traffic path
- ✅ Vercel `VITE_API_URL` updated to Railway URL
- ✅ Railway tracks `main` branch, auto-deploys on push

## Ready to do next

### Option A — Further UX improvements
Location search, radius UX, result display improvements.

### Option B — MongoDB venue management
`Backend/venues_mongo.py` and `Backend/main.py` are stubs ready for this.
Would allow adding/editing venues without a Railway redeploy.
CSV is fine for now.

### Option C — Verify remaining Eversports venues end-to-end
Some venues may not have been smoke-tested since the consolidation.
Quick check: search with `lat/lon/radius` for a date/time with expected availability.

### Option D — Clean up Render
Log into Render and delete/suspend the old `neopadelchecker` service.
It's no longer receiving traffic but may still be billing.

## Constraints (do not change)

- Do NOT split backend into microservices again
- Do NOT rewrite working scraper systems
- Do NOT introduce Render back into the architecture
- Eversports async code must use `run_coroutine_threadsafe` (not `_run_async`)
- `RAILWAY_ENVIRONMENT` gates Eversports — do not remove this guard
