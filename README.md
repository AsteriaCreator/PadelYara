# PadelYara

Padel court aggregator for Austria. Answers "where can I play right now?" — free slots, real prices, direct booking links.

**Live:** [padelyara.at](https://www.padelyara.at)

---

## What it does

- Search by location + radius + date/time + play duration (1 / 1.5 / 2 h)
- Aggregates availability from three platforms: eTennis, Eversports, tennis04
- Returns real-time slot status (free / busy / other duration available)
- Weather forecast for outdoor courts
- Turnierjäger: tournament listing scraped daily from padel-austria.at
- Padelrevier: interactive venue map of all Austrian padel courts

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + TypeScript + Vite + Tailwind CSS v4 |
| Backend | FastAPI (Python 3.10) + Playwright + curl_cffi |
| Database | MongoDB Atlas (`padel_checker`) |
| Frontend deploy | Vercel |
| Backend deploy | Railway (Docker) |
| Error tracking | Sentry |
| CI | GitHub Actions (typecheck + lint on every push) |

---

## Local Development

```bash
npm install
npm run dev        # Frontend → http://localhost:5173
npm run backend    # Backend  → http://localhost:8000
```

Both must be running — the frontend's API calls will fail without the backend.

Backend requires a `Backend/.env` with at minimum:

```
MONGODB_URI=...
```

See `Backend/.env.example` for all variables.

> **Note:** Eversports availability only works from Railway IPs (Cloudflare bypass). Locally, Eversports venues return `platform_check_required`. eTennis and tennis04 work locally.

---

## Backend structure

`Backend/app.py` is the entry point. It creates the FastAPI app, registers middleware, and includes routers. Business logic is split into focused modules:

```
Backend/
  app.py              — app creation, CORS, lifespan, router includes
  state.py            — shared globals (VENUES, _main_loop)
  auth.py             — admin token auth dependency
  scheduler.py        — background jobs (tournament scrape, opening hours refresh)
  routers/
    search.py         — /api/search + all caching and scraper orchestration
    analytics.py      — /api/analytics* (admin)
    tournaments.py    — /api/tournaments*
    venues.py         — /api/venues* (Padelrevier map)
    weather.py        — /api/weather
    subscribers.py    — /api/subscribe, /api/confirm
    urteil.py         — /api/urteil (Yara's Urteil)
    admin.py          — diagnostic endpoints
```

---

## Scraper architecture

Three scrapers run in-process on the single Railway service:

**eTennis** (`Backend/etennis_checker.py`) — Playwright. One shared browser, semaphore-controlled concurrency (~2 parallel checks). Pending-first: the API responds immediately with `pending` while scraping runs in a background thread.

**Eversports** (`Backend/eversports_service.py`) — curl_cffi fast path with Playwright Cloudflare cookie warmup. Only works from Railway IPs. Results cached per venue/date/time (5 min TTL).

**tennis04** (`Backend/tennis04_checker.py`) — Plain HTTP, no browser needed.

All three use the same pending-first pattern: fast initial response, background threads fill in real statuses, frontend polls until settled. See [Scrapers.md](Scrapers.md) for internals.

---

## Testing

```bash
cd Backend
pytest test_search_api.py -v
```

Integration tests against the live `/api/search` endpoint. Tests auto-skip when the backend isn't running. They test the full stack including scraper logic — unit tests with mocked scrapers would not catch the class of bugs that actually occur (timing, Cloudflare, slot grid mismatches).

---

## Key docs

| File | Purpose |
|------|---------|
| [PROJECT_STATE.md](PROJECT_STATE.md) | Architecture decisions, infrastructure, constraints |
| [Scrapers.md](Scrapers.md) | Scraper internals, performance model, failure modes |
| [YarasUrteil.md](YarasUrteil.md) | Spec for the Yara's Urteil player analysis feature |
| [SEO.md](SEO.md) | SEO implementation log |
| [CLAUDE.md](CLAUDE.md) | AI assistant context (stack, working rules, gotchas) |
