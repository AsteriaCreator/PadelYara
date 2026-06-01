# Infrastructure

## Production URLs

Frontend (Vercel)
https://neo-padel-checker.vercel.app

Backend (Railway) — single consolidated service
https://neo-padel-checker-backend-production.up.railway.app

## Deployment

Frontend:
- Auto deploy from `main` via Vercel
- `VITE_API_URL` → Railway backend URL

Backend:
- Single Railway service (Docker)
- Dockerfile at `Backend/Dockerfile`
- Start command (in `railway.json`):
  `sh -c 'python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}'`
- Playwright installed in base image
- Auto deploys from `main` on push

## Important Files

Backend entry:
Backend/app.py

eTennis scraper:
Backend/etennis_checker.py

Eversports checker (in-process, no HTTP hop):
Backend/eversports_service.py

Venue source:
Padel_Venues.csv

Railway config:
railway.json

## Performance

Railway:
- Up to 8 GB RAM available
- Playwright runs in-process for both eTennis and Eversports
- Eversports uses curl_cffi fast path + Playwright CF cookie warmup

## Known Constraints

- Eversports Cloudflare bypass only works from Railway egress IPs
- `RAILWAY_ENVIRONMENT` env var controls whether Eversports runs (auto-set by Railway)
- Locally Eversports returns `platform_check_required` immediately (by design)
- Pending responses return fast; final statuses resolve in background

## Retired Services

- Render (`https://neopadelchecker.onrender.com`) — deleted 2026-06-01
- Old Railway Eversports microservice — consolidated into main `app.py`
