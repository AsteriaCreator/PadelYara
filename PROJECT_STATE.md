# PadelYara – Project State

## Current Product State

Public MVP is live and functional.

Core flow:
- location input
- radius search
- date/time search
- play-duration filter (1 / 1.5 / 2 h, multi-select, default 2 h)
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
- FastAPI — entry point `Backend/app.py` (107 lines); routes split into `Backend/routers/`
- Docker deploy on Railway
- Playwright installed in container
- Handles both eTennis scraping and Eversports scraping in-process
- MongoDB venue source — db `padel_checker`, collection `venues`, loaded via `venues_mongo.py` (`load_venues()`)
- Open-Meteo weather integration
- `RAILWAY_ENVIRONMENT` env var gates Eversports (auto-set by Railway)

Backend module structure (post 2026-06-17 router split):
- `app.py` — FastAPI app, CORS, lifespan, router includes
- `state.py` — shared globals (VENUES, _main_loop, _ev_ids)
- `auth.py` — admin token auth dependency
- `scheduler.py` — background jobs (tournament scrape, opening hours)
- `routers/search.py` — /api/search + caching/scraper orchestration
- `routers/analytics.py`, `routers/tournaments.py`, `routers/venues.py`, `routers/weather.py`, `routers/subscribers.py`, `routers/urteil.py`, `routers/admin.py`

Availability Providers:
- eTennis → Playwright scraper (in-process)
- Eversports → `check_eversports_slot()` called directly (no HTTP hop); uses curl_cffi + Playwright CF bypass

---

## Important Infrastructure

Frontend (Vercel):
https://www.padelyara.at  (primary live domain; padelyara.com redirects here. Also reachable at neo-padel-checker.vercel.app)

Backend (Railway):
https://neo-padel-checker-backend-production.up.railway.app
- Single Docker service — `Backend/Dockerfile`, config in `railway.json`
- Start command: `sh -c 'python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}'`
- Up to 8 GB RAM available; Playwright runs in-process (eTennis + Eversports)

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

## Turnierjäger (live)

Standalone section at `/turnierjaeger` with three sub-tabs (TurnierjagerNav):
- **TURNIERE** (`/turnierjaeger`) — tournament discovery + filtering
- **MEINE JAGD** (`/turnierjaeger/meine`) — upcoming registered tournaments + GEMERKT (bookmarks, replaces old /merkliste)
- **SPIELANALYSE** (`/turnierjaeger/spielanalyse`) — player stats page, **hidden from nav** (accessible by direct URL only)

### TURNIERE
- Scraper: `Backend/padel_austria_scraper.py` — BeautifulSoup, paginates all pages of padel-austria.at/tournaments
- Storage: MongoDB `tournaments` collection (separate from venues)
- API: `GET /api/tournaments` with filter params (bundesland, category, competition, weekday, show_full, show_closed)
- Scheduler: APScheduler in `Backend/scheduler.py` (started from lifespan in app.py), runs daily at 06:00 Vienna time
- Frontend: `src/pages/TurnierjagerPage.tsx` + `src/components/TournamentCard.tsx`
- Filter state persisted in localStorage

Data model fields: source, source_id, source_url, title, venue_name, bundesland, starts_at, ends_at, weekday, category, competition, participants_current, participants_max, participants_waitlist, registration_opens_at, registration_closes_at, status, first_seen_at, last_seen_at

### MEINE JAGD (`src/pages/TurnierjagerMinePage.tsx`)
- Profile setup: player name search (slug saved to localStorage) to identify the user's upcoming tournaments
- BEVORSTEHEND tab: upcoming tournaments from DB filtered by slug
- GEMERKT tab: bookmarks (previously a separate /merkliste page, now merged here)
- "SPIELANALYSE →" link to view own stats
- `src/hooks/useMerkliste.ts` + `src/hooks/useMyProfile.ts`

### SPIELANALYSE (`src/pages/SpielanalysePage.tsx`) — hidden from nav, live at direct URL
- Player search by name (autocomplete from tournament DB)
- Public profiles at `/turnierjaeger/spielanalyse/:slug` — loaded directly via history endpoint (no search needed)
- Stats: APN, Punkte, Platz, Matches W/L (from padel-austria.at header)
- Category progression chart, partner stats table (filtered by all active filters), full match history
- All filters (category, competition, year, partner) apply to both history list AND partner stats
- History supplemented with match-derived entries for tournaments missing from the points table (points table only shows ranking-contributing entries)
- History sorted newest-first
- Partner names link to their own `/spielanalyse/:slug` page
- "Kommt bald" placeholder for Yaras Urteil AI verdict section
- Attribution footer: "Daten von padel-austria.at · keine dauerhafte Speicherung"
- Hidden from nav intentionally — too powerful before Yara is established; re-add SPIELANALYSE to TABS in `TurnierjagerNav.tsx` when ready to launch

### Redirects (old URLs → new)
- `/turnierjaeger/merkliste` → `/turnierjaeger/meine`
- `/turnierjaeger/meine/:slug` → `/turnierjaeger/spielanalyse/:slug`
- `/urteil` → `/turnierjaeger/spielanalyse`

Phase 2 (not yet built): email notifications, Jagdaufträge (saved search orders), registration reminders.

New dependency: `apscheduler==3.11.2`

---

## Padelrevier (live)

Standalone subpage at `/padelrevier` — interactive map of all active venues.

Architecture:
- API: `GET /api/venues` (in `routers/venues.py`) — lightweight, **no scraping**; returns each active venue's static info (name, address, lat/lon, court_type, platform, booking_url, public_url) from the cached `load_venues()`. Requires `address` in `venues_mongo._normalize()`.
- Frontend: `src/pages/PadelrevierPage.tsx` — Leaflet + react-leaflet + react-leaflet-cluster on dark CartoDB `dark_all` tiles. Tiles are brightened via a CSS filter (`src/index.css` → `.padelrevier-map .leaflet-tile`) because the raw tiles are near-black against the dark page.
- Austria highlight + region zoom: bundled simplified GeoJSON `src/data/austria-bundeslaender.json` (9 Bundesländer). Drawn as a lime overlay so Austria stands out; clicking a Bundesland chip fits the map to that region (`MapFit` + `useMap`).
- Filters: Bundesland (derived from the address PLZ via `src/data/plz.ts`, since the `region` field is empty on most venues) + Platztyp (Indoor/Outdoor; a both-courts venue matches either).
- Pin popup: name, address, court type, a "Details →" link to the venue detail page, "Zur Anlage", a Google Maps "Route" link, and "Verfügbarkeit prüfen" → jumps to the Court Finder pre-filled to that venue (passes the venue's lat/lon to bypass geocoding + a `venueId` that highlights/scrolls the matching result row).

New deps: `leaflet`, `react-leaflet`, `react-leaflet-cluster`, `@types/leaflet`. The MarkerCluster CSS imports (`MarkerCluster.css` + `MarkerCluster.Default.css`) are mandatory — without them the cluster bubbles render with no size and are invisible.

Note: this map page defeats automated screenshot capture (the Leaflet renderer stays busy, so Preview/Chrome CDP both time out) — verify map visuals on a real foreground browser; computed-style/JS-eval checks still work.

---

## Play-Duration Availability (live, 2026-06-13)

Search filters by how long you want to play, not just the start time — a venue is "Frei" only if a single court is free **continuously** for a selected duration.

- Shared block math: `Backend/availability.py`. Each scraper emits `free_durations` (duration-agnostic, cached per venue/date/time) + `fallback_durations`; `routers/search.py` intersects with the `durations` query param (minutes).
- Frontend: multi-select chips (`DURATION_OPTIONS`) + half-hour `TIME_SLOTS`; "2 Std frei" tag via `matched_duration_h`.
- "Andere Dauer" state: when the requested length isn't free but other selectable lengths are (e.g. a 60-min-grid venue can't sell 1.5 h), the API returns `availability_status: "other_duration"` + `available_durations_h` → amber "Nur 1 Std / 2 Std frei" instead of misleading "Belegt".
- Opening hours (Eversports only — its slot API can't see closing time): auto-learned via Gemini + Google Search grounding (`Backend/opening_hours.py`), weekly Mon 04:00 + first-deploy seed, throttled for the Gemini free tier; 07–23 default until learned. tennis04 / eTennis expose hours themselves.
- Every platform errs toward **Belegt**, never a false **Frei**, when grid/hours are ambiguous.

---

## Scrapers

Availability comes from three scrapers running in-process on the single Railway service:
eTennis (Playwright), Eversports (curl_cffi fast path + Playwright CF bypass), and tennis04 (plain HTTP).

**Strategy, performance tuning, constraints, fragile areas, per-platform internals, and the venue-onboarding pipeline all live in [Scrapers.md](Scrapers.md) — the single source of truth for scrapers.** Don't duplicate scraper internals here.

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
The old Render backend is retired (deleted 2026-06-01).
The old Railway Eversports microservice (separate service) is retired — code merged into the backend (now in `routers/search.py`).

Do not:
- build new UX around regions
- reintroduce Render as a backend
- split eTennis and Eversports into separate services again

Unless explicitly requested.

---

## Venue Data Source

Current production source:
- MongoDB Atlas — db `padel_checker`, collection `venues`, loaded at startup via `venues_mongo.py` `load_venues()` (cached 5 min).

`Padel_Venues.csv` is retained only as a backup/seed for the one-time `Backend/migrate_csv_to_mongo.py`; it is **no longer read by the running app**.

---

## Important Backend Files

Backend entry:
- `Backend/app.py` — app creation, CORS, lifespan, router includes (107 lines)
- `Backend/state.py` — shared mutable globals
- `Backend/auth.py` — admin auth dependency
- `Backend/scheduler.py` — APScheduler background jobs
- `Backend/routers/search.py` — /api/search, all caching + scraper orchestration

eTennis scraper:
- `Backend/etennis_checker.py`

Eversports checker (in-process):
- `Backend/eversports_service.py`

Venue source:
- MongoDB `venues` collection, via `Backend/venues_mongo.py`

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

- Prioritize production stability over theoretical optimizations; add features only after reliability holds.
- Don't rewrite working systems without a strong, measured reason.
- Scraper-specific rules (eTennis/Eversports separation, the async-loop requirement, fragility) live in [Scrapers.md](Scrapers.md).
