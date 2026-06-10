# PadelYara

Padel Court Aggregator für Österreich – freie Zeiten, echte Preise, sofort buchbar.

**Live:** [padelyara.at](https://padelyara.at)

## Stack

- **Frontend:** React + TypeScript + Vite, deployed via Vercel
- **Backend:** FastAPI (Python), deployed via Railway (Docker)
- **Database:** MongoDB Atlas

## Local Development

```bash
npm install
npm run dev        # Frontend on localhost:5173
npm run backend    # Backend on localhost:8000
```

Backend requires a `.env` with `MONGODB_URI`.

## Architecture

See [PROJECT_STATE.md](PROJECT_STATE.md) for architecture, infrastructure, deployment config, and known constraints.

## Scrapers

- **eTennis:** Playwright-based scraper (`Backend/etennis_checker.py`)
- **Eversports:** curl_cffi fast path + Playwright CF cookie warmup (`Backend/eversports_service.py`)

Venues are stored in MongoDB Atlas (db: `padel_checker`, collection: `venues`).
