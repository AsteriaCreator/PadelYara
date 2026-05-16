# Project State

_Last updated: 2026-05-16_

## Services

### Frontend — Vercel
- Status: **working**
- Deployment: automatic on push to `main`
- Env var: `VITE_API_URL=https://neopadelchecker.onrender.com`

### Backend — Render
- Status: **working** ✅ verified 2026-05-16
- URL: `https://neopadelchecker.onrender.com`
- Entry point: `Backend/app.py` (via `render.yaml`: `uvicorn app:app --host 0.0.0.0 --port $PORT --app-dir Backend`)
- Deploy branch: `main`
- Env vars required:
  - `EVERSPORTS_SERVICE_URL=https://neo-padel-checker-backend-production.up.railway.app`
  - `FRONTEND_URL` (CORS origin)
- `Backend/main.py` and `Backend/venues_mongo.py` are **not** used by Render — ignore them

### Eversports Microservice — Railway
- Status: **working** ✅ verified 2026-05-16
- URL: `https://neo-padel-checker-backend-production.up.railway.app`
- Entry point: `Backend/eversports_service.py`
- Deploy branch: `claude/affectionate-goodall-0ededf`
- Builder: **Dockerfile** (`Backend/Dockerfile`) — configured via `railway.json` at repo root
- Base image: `mcr.microsoft.com/playwright/python:v1.44.0-jammy` (Chromium baked into image)
- Start command: `sh -c 'python -m uvicorn eversports_service:app --host 0.0.0.0 --port ${PORT:-8000}'`
  - Must use `sh -c` wrapper — Railway does not shell-expand `$PORT` in `startCommand` directly
  - Must use `python -m uvicorn` — `uvicorn` binary is not in PATH on the Playwright image

## Scraper Verification — 2026-05-16

Full end-to-end pipeline test run against production. All three test cases passed.

| Test | Region param | Venue | Result |
|------|-------------|-------|--------|
| 1 | `Bad Voeslau` | `padelzone-traiskirchen` | `free` ✅ |
| 1 | `Bad Voeslau` | `padel-ebreichsdorf` | `free` ✅ |
| 2 | `NOE Sued` | `padelzone-wr-neustadt-arena-27` | `busy` ✅ |
| 2 | `NOE Sued` | `padelzone-wr-neustadt-achtersee` | `busy` ✅ |
| 2 | `NOE Sued` | `padelzone-sprungart` | `busy` ✅ |
| 3 | `Wien` | `padeldome-alte-donau-outdoor` (eTennis) | `busy` ✅ |
| 3 | `Wien` | `padelbase-wien` (eTennis) | `busy` ✅ |
| 3 | `Wien` | `racketworld-wien` (eTennis) | `busy` ✅ |
| 3 | `Wien` | `padeldome-suessenbrunn` (eTennis) | `busy` ✅ |
| 3 | `Wien` | `padeldome-alte-donau-indoor` (eTennis) | `busy` ✅ |
| 3 | `Wien` | `padel-union-wien` (eTennis) | `no_slot` ✅ |
| 3 | `Wien` | `padelzone-wien-floridsdorf` (Eversports) | `free` ✅ |
| 3 | `Wien` | `padelzone-wien-sportinsel` (Eversports) | `free` ✅ |

No code changes were needed — the pipeline works as deployed.

## Eversports Cloudflare Bypass

- Primary path (Railway): `/api/slot` via `curl_cffi` (TLS fingerprint) + cached `cf_clearance` cookie
  - Cookie is refreshed once per hour via Playwright Chromium
  - Subsequent requests within the hour are fast (<1s)
- Direct POST to `/api/booking/calendar/update` is blocked from Railway IPs (WAF) — not used
- Playwright DOM scrape removed from production path (too slow)
- Confirmed working venues: **Traiskirchen**, **Arena 27**, **Achtersee**, **Sprungart**, **Floridsdorf**, **Sportinsel**

## Region Format — IMPORTANT

The `region` query parameter to `/api/search` must match the **label** column from the CSV, not the slug/key.

| Correct (region_label) | Wrong (region_key) |
|------------------------|-------------------|
| `Bad Voeslau` | `bad-voeslau` |
| `Wien Sued` | `wien-sued` |
| `Wien` | `wien` |
| `NOE Sued` | `noe-sued` |

Source: `Backend/venues.py:53` — `"region": row["region_label"].strip()`

The frontend (`src/constants.ts`) already sends labels. Only ad-hoc curl/PowerShell test commands need care — URL-encode spaces as `%20`.

## Endpoints

### Render backend (`/api/search`)
| Param | Type | Notes |
|-------|------|-------|
| `date` | `YYYY-MM-DD` | optional, defaults to now (Vienna TZ) |
| `time` | `HH:MM` | optional, defaults to current hour |
| `region` | string | use **label** format (see above) |
| `court_type` | `indoor`/`outdoor`/`all` | optional |
| `lat`, `lon`, `radius` | float | alternative to region (public mode) |

Response: `{"ok": true, "results": [...], "date": "...", "time": "...", "availability_pending": bool}`

`availability_status` values: `free` | `busy` | `no_slot` | `pending` | `not_checked` | `platform_check_required` | `phone_only`

### Railway microservice
| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness — `{"ok": true, "service": "eversports-service"}` |
| `GET /check` | Slot check — `{"status": "free"\|"busy"\|"platform_check_required", "slots_count": N}` |
| `GET /diag` | Raw slot diagnostic (debug) |

## Venue Data

### Production source
- **File:** `Padel_Venues.csv` (repo root)
- **Loader:** `Backend/venues.py` → `load_venues()` reads the CSV at `Path(__file__).parent.parent / "Padel_Venues.csv"`
- **Loaded once at startup** — Render must be redeployed after any CSV change

### Key CSV columns for Eversports venues
| Column | Description |
|--------|-------------|
| `region_label` | Human-readable region name — this is what `/api/search?region=` must match |
| `region_key` | URL slug — NOT used by the API |
| `eversports_facility_id` | Numeric facility ID for `/api/slot` calls |
| `eversports_court_ids` | Pipe-separated numeric court IDs (e.g. `91337\|91338\|91339`) |

### Active Eversports venues with verified IDs (as of 2026-05-16)
| Venue | facility_id | court_ids |
|-------|------------|-----------|
| Padelzone Traiskirchen | 79237 | 101686–101689 |
| Padelzone Wr. Neustadt Arena 27 | 77873 | 91337–91343 |
| Padelzone Wr. Neustadt Achtersee | 83836 | 112892–112895 |
| Padelzone Wien C&C Wienerberg | 77636 | 90282, 90283, 91073 |
| Padelzone Wien Floridsdorf | 78472 | 98662–98665, 99442–99445 |
| Padelzone Wien Sportinsel | 76509 | 84581, 84582 |
| Padelzone Sprungart | 80679 | 105796–105799 |
| Padel Ebreichsdorf | 82350 | 109328, 109329 |

## Structured Logging

Both services emit structured JSON logs per request:

```json
// Render (app.py) — Eversports service call result
{"event": "eversports_service_result", "venue_id": "...", "facility_id": 77873, "status": "free", "slots_count": 3, "duration_ms": 1240}

// Railway (eversports_service.py) — check result
{"event": "railway_check_result", "facility_id": 77873, "courts": [91337, ...], "status": "free", "slots_count": 3, "duration_ms": 980}
```

## Deployment Notes

- `railway.json` must live at the **repo root** — Railway ignores it elsewhere
- `Backend/Dockerfile` build context is the **repo root** (not `Backend/`); COPY paths use `Backend/` prefix
- Render redeploy required after any CSV edit (venues load once at startup)
- Render free tier sleeps after 15 min inactivity — first request may take 30–60s to wake

## Next Recommended Step

The pipeline is production-verified. Remaining work before a public MVP:

1. **Add a public/radius search mode UI** — `/api/search` already supports `lat`/`lon`/`radius`; the frontend just needs a location input wired up
2. **MongoDB venue management** — replace CSV with a database so venues can be added without a redeploy (`Backend/venues_mongo.py` and `Backend/main.py` are stubs ready for this)
3. **Eversports Wien Sued / C&C Wienerberg** — not yet included in Bad Voeslau / Wien Sued test runs; verify facility IDs work end-to-end

Do **not** start (2) until (1) is decided — the CSV approach is fine for personal mode.
