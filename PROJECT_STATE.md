# Project State

_Last updated: 2026-05-09_

## Services

### Frontend — Vercel
- Status: **working**
- Deployment: automatic on push to `main`

### Backend — Render
- Status: **working**
- Entry point: `Backend/app.py` (via `render.yaml`: `uvicorn app:app --host 0.0.0.0 --port $PORT --app-dir Backend`)
- `Backend/main.py` and `Backend/venues_mongo.py` are **not** used by Render — ignore them

### Eversports Microservice — Railway
- Status: **working**
- Entry point: `Backend/eversports_service.py`
- Builder: **Dockerfile** (`Backend/Dockerfile`) — configured via `railway.json` at repo root
- Base image: `mcr.microsoft.com/playwright/python:v1.44.0-jammy` (Chromium baked into image)
- Start command: `sh -c 'python -m uvicorn eversports_service:app --host 0.0.0.0 --port ${PORT:-8000}'`
  - Must use `sh -c` wrapper — Railway does not shell-expand `$PORT` in `startCommand` directly
  - Must use `python -m uvicorn` — `uvicorn` binary is not in PATH on the Playwright image

## Eversports Cloudflare Bypass

- `eversports_service.py` first attempts `curl_cffi` (TLS fingerprint spoofing)
- On Cloudflare 403, falls back to **Playwright Chromium** (full browser, bypasses JS challenge)
- Fallback confirmed working from Railway IPs
- Verified venues: **Traiskirchen**, **Arena 27**, **Achtersee**

## Endpoints (Railway microservice)

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness check — returns `{"ok": true, "service": "eversports-service"}` |
| `POST /check` | Check slot availability — returns `{"status": "free"\|"busy"\|"platform_check_required", "slots_count": N}` |
| `GET /diag` | Full diagnostic JSON (debug use) |

## Venue Data

### Production source
- **File:** `Padel_Venues.csv` (repo root)
- **Loader:** `Backend/venues.py` → `load_venues()` reads the CSV at `Path(__file__).parent.parent / "Padel_Venues.csv"`
- **Loaded once at startup** — Render must be redeployed after any CSV change for it to take effect

### MongoDB
- `Backend/venues_mongo.py` exists but is only imported by `main.py`, which Render does not run
- MongoDB is **not** the production venue source

### Key CSV columns for Eversports venues
| Column | Description |
|--------|-------------|
| `eversports_slug` | Facility slug used in public URL |
| `eversports_facility_id` | Numeric facility ID for `/api/slot` calls |
| `eversports_court_ids` | Pipe-separated numeric court IDs (e.g. `91337\|91338\|91339`) |

### Recently fixed venues (commit `b82c327`)
| Venue | facility_id | court_ids |
|-------|------------|-----------|
| Padelzone Wr. Neustadt Arena 27 | 77873 | 91337–91343 |
| Padelzone Wr. Neustadt Achtersee | 83836 | 112892–112895 |

Achtersee slug also corrected: `padelzone-wiener-neustadt-or-achtersee`

## Structured Logging

Both Render and Railway emit structured JSON logs per request:

```json
// Render (app.py) — Eversports service call result
{"event": "eversports_service_result", "venue_id": "...", "facility_id": 77873, "status": "free", "slots_count": 3, "duration_ms": 1240}

// Railway (eversports_service.py) — check result
{"event": "railway_check_result", "facility_id": 77873, "courts": [91337, ...], "status": "free", "slots_count": 3, "duration_ms": 980}
```

## Deployment Notes

- `railway.json` must live at the **repo root** — Railway ignores it elsewhere
- `Backend/Dockerfile` build context is the **repo root** (not `Backend/`); COPY paths use `Backend/` prefix
- `.gitignore` rule `Backend/*.json` would catch `Backend/railway.json` — keep `railway.json` at repo root only
- Render redeploy is required after every CSV edit (venues load once at startup, not per-request)
