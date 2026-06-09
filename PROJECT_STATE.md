# PadelYara – Project State

## Current Product State

Public MVP is live and functional.

Core flow:
- location input
- radius search
- date/time search
- court type filtering
- weather integration
- booking deep links

Main goal:
Answer "Where can I play now/today?" as fast as possible.

---

## Current Product Direction

Main user flow:
- location
- radius
- nearby courts
- fast availability decisions

NOT region-first search.

Legacy region-based logic may still exist internally in some code paths, but it is deprecated and should not shape new architecture decisions.

---

## Active Architecture

Frontend:
- React 19
- Vite
- TypeScript
- Tailwind CSS v4
- Lives in repository root (no separate frontend/ directory)
- Deployed via Vercel
- `VITE_API_URL` points to Railway backend

Backend (single Railway service):
- FastAPI (`Backend/app.py`)
- Docker deploy on Railway
- Playwright installed in container
- Handles both eTennis scraping and Eversports scraping in-process
- CSV venue source (`Padel_Venues.csv`)
- Open-Meteo weather integration
- `RAILWAY_ENVIRONMENT` env var gates Eversports (auto-set by Railway)

Availability Providers:
- eTennis → Playwright scraper (in-process)
- Eversports → `check_eversports_slot()` called directly (no HTTP hop); uses curl_cffi + Playwright CF bypass

---

## Important Infrastructure

Frontend (Vercel):
https://neo-padel-checker.vercel.app

Backend (Railway):
https://neo-padel-checker-backend-production.up.railway.app

---

## API Search Modes

Primary public search mode:
- `lat`
- `lon`
- `radius`

Legacy/private mode:
- `region`

The public product should always prioritize location + radius architecture.

---

## Turnierjäger (Phase 1 — live)

Standalone subpage at `/turnierjaeger`.

Architecture:
- Scraper: `Backend/padel_austria_scraper.py` — BeautifulSoup, paginates all pages of padel-austria.at/tournaments
- Storage: MongoDB `tournaments` collection (separate from venues)
- API: `GET /api/tournaments` with filter params (bundesland, category, competition, weekday, show_full, show_closed)
- Scheduler: APScheduler inside app.py, runs daily at 06:00 Vienna time
- Frontend: `src/pages/TurnierjagerPage.tsx` + `src/components/TournamentCard.tsx`
- Filter state persisted in localStorage

Data model fields: source, source_id, source_url, title, venue_name, bundesland, starts_at, ends_at, weekday, category, competition, participants_current, participants_max, participants_waitlist, registration_opens_at, registration_closes_at, status, first_seen_at, last_seen_at

Phase 2 (not yet built): email notifications, Jagdaufträge (saved search orders), registration reminders.

New dependency: `apscheduler==3.11.2`

---

## Padelrevier (live)

Standalone subpage at `/padelrevier` — interactive map of all active venues.

Architecture:
- API: `GET /api/venues` (in `app.py`) — lightweight, **no scraping**; returns each active venue's static info (name, address, lat/lon, court_type, platform, booking_url, public_url) from the cached `load_venues()`. Requires `address` in `venues_mongo._normalize()`.
- Frontend: `src/pages/PadelrevierPage.tsx` — Leaflet + react-leaflet + react-leaflet-cluster on dark CartoDB `dark_all` tiles. Tiles are brightened via a CSS filter (`src/index.css` → `.padelrevier-map .leaflet-tile`) because the raw tiles are near-black against the dark page.
- Austria highlight + region zoom: bundled simplified GeoJSON `src/data/austria-bundeslaender.json` (9 Bundesländer). Drawn as a lime overlay so Austria stands out; clicking a Bundesland chip fits the map to that region (`MapFit` + `useMap`).
- Filters: Bundesland (derived from the address PLZ via `src/data/plz.ts`, since the `region` field is empty on most venues) + Platztyp (Indoor/Outdoor; a both-courts venue matches either).
- Pin popup: name, address, court type, a "Details →" link to the venue detail page, "Zur Anlage", a Google Maps "Route" link, and "Verfügbarkeit prüfen" → jumps to the Court Finder pre-filled to that venue (passes the venue's lat/lon to bypass geocoding + a `venueId` that highlights/scrolls the matching result row).

New deps: `leaflet`, `react-leaflet`, `react-leaflet-cluster`, `@types/leaflet`. The MarkerCluster CSS imports (`MarkerCluster.css` + `MarkerCluster.Default.css`) are mandatory — without them the cluster bubbles render with no size and are invisible.

Note: this map page defeats automated screenshot capture (the Leaflet renderer stays busy, so Preview/Chrome CDP both time out) — verify map visuals on a real foreground browser; computed-style/JS-eval checks still work.

---

## Current Scraper Strategy

### eTennis

- shared Playwright browser
- controlled concurrency: 2 venues parallel
- one page per venue
- aggressive early exit once slot state is known
- pending responses return immediately
- final status resolution optimized separately
- structured timing logs enabled

### Eversports

- `check_eversports_slot()` called directly in-process from `app.py`
- curl_cffi fast path (Chrome TLS fingerprint)
- Playwright CF cookie warmup fallback (~45s first time, then cached for 60 min)
- Only runs when `RAILWAY_ENVIRONMENT` is set — skipped locally to keep dev searches fast
- All asyncio coroutines share uvicorn's main event loop via `run_coroutine_threadsafe`

---

## eTennis Performance Strategy

Goals:
- fast pending response
- faster final status resolution
- stable memory usage
- avoid duplicate browser launches

Current implementation:
- shared browser per batch
- controlled concurrency via semaphore
- reduced timeout values
- per-venue duration logging
- total batch duration logging
- `_RUNNING` guard retained
- cache and cooldown behavior retained

---

## Production Verification

Production pipeline verified successfully:
- eTennis scraping works
- Eversports in-process call works
- availability statuses resolve correctly
- weather integration works
- structured logging active

Last verified:
2026-06-01

---

## Current Constraints

- Eversports CF bypass only works from Railway IPs — not from local dev
- Availability accuracy is more important than extra features
- Final slot resolution speed matters more than initial pending
- Do not add Playwright concurrency beyond what Railway RAM supports

---

## Deprecated / Legacy Concepts

The old region-based architecture is deprecated.
The old Render backend is retired.
The old Railway Eversports microservice (separate service) is retired — code merged into `app.py`.

Do not:
- build new UX around regions
- reintroduce Render as a backend
- split eTennis and Eversports into separate services again

Unless explicitly requested.

---

## Venue Data Source

Current production source:
- `Padel_Venues.csv`

CSV loading is currently stable and sufficient.

MongoDB migration remains optional and is not currently required for production stability.

---

## Important Backend Files

Backend entry:
- `Backend/app.py`

eTennis scraper:
- `Backend/etennis_checker.py`

Eversports checker (in-process):
- `Backend/eversports_service.py`

Venue source:
- `Padel_Venues.csv`

Railway config:
- `railway.json`

Docker build:
- `Backend/Dockerfile`

---

## Current Priorities

1. Scraper reliability
2. Production stability
3. Improve operational documentation
4. Remove deprecated region assumptions from code/comments/docs

---

## Important Development Rules

- Do not rewrite working scraper systems without strong reason
- Reuse proven scraping logic where possible
- Optimize reliability before adding features
- Keep Eversports and eTennis logic clearly separated in `eversports_service.py` vs `etennis_checker.py`
- Prioritize production stability over theoretical optimizations
- Eversports async code must run on uvicorn's main loop — use `run_coroutine_threadsafe`, not `_run_async`
