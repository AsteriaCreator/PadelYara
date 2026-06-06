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
