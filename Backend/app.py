import asyncio
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env from the Backend directory (local dev only; production uses real env vars)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import sentry_sdk
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    traces_sample_rate=0.1,
    environment=os.environ.get("RAILWAY_ENVIRONMENT", "development"),
)

import analytics
import tournaments_mongo
import eversports_prices
from venues_mongo import load_venues
import state
from scheduler import _run_tournament_scrape, _run_opening_hours_refresh

from routers import search, analytics as analytics_router, tournaments, venues, weather, subscribers, urteil, admin, tournament_alerts


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state._main_loop = asyncio.get_running_loop()
    await analytics.lifespan_startup()
    await tournaments_mongo.ensure_indexes()
    await tournaments_mongo.ensure_share_index()
    eversports_prices.init_mongo(os.getenv("MONGODB_URI", ""))
    await eversports_prices.load_cache_from_mongo()
    state.VENUES = await load_venues()
    state._ev_ids = [(v["id"], v["eversports_facility_id"], v["eversports_court_ids"])
                    for v in state.VENUES if v.get("eversports_facility_id")]
    print(f"[startup] Loaded {len(state.VENUES)} venues from MongoDB")
    print(f"[startup] Eversports venues with facility IDs: {state._ev_ids}")

    # Seed tournament data on first deploy if collection is empty
    count = await tournaments_mongo.count_tournaments()
    if count == 0:
        print("[tournaments] Collection empty — running initial scrape in background.")
        threading.Thread(target=_run_tournament_scrape, kwargs={"is_seed": True}, daemon=True).start()

    # Daily scraper at 06:00 Vienna time
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    scheduler = BackgroundScheduler(timezone="Europe/Vienna")
    scheduler.add_job(_run_tournament_scrape, CronTrigger(hour=6, minute=0))
    # Weekly: auto-learn Eversports opening hours via Gemini + Google Search.
    scheduler.add_job(_run_opening_hours_refresh, CronTrigger(day_of_week="mon", hour=4, minute=0))
    scheduler.start()
    print("[tournaments] Daily scraper scheduled at 06:00 Vienna time.")
    print("[opening_hours] Weekly Eversports hours refresh scheduled Mon 04:00.")

    # Kick off a background price scrape at startup
    asyncio.create_task(eversports_prices.refresh_prices_async(state.VENUES))
    print("[startup] Eversports price refresh started in background.")

    print(f"[mem] resident memory after startup load: {state.rss_mb():.0f} MB")

    yield
    scheduler.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)

_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
_allowed_origins = [
    _frontend_url,
    "https://neo-padel-checker.vercel.app",
    "https://www.padelyara.at",
    "https://padelyara.at",
    "https://www.padelyara.com",
    "https://padelyara.com",
]
_VERCEL_PREVIEW_PATTERN = r"https://neo-padel-checker-[a-z0-9-]+\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=_VERCEL_PREVIEW_PATTERN,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Session-Id", "X-Admin-Token"],
)

app.include_router(search.router)
app.include_router(analytics_router.router)
app.include_router(tournaments.router)
app.include_router(venues.router)
app.include_router(weather.router)
app.include_router(subscribers.router)
app.include_router(urteil.router)
app.include_router(admin.router)
app.include_router(tournament_alerts.router)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # reload=False: avoids conflicts with Playwright's Chrome subprocess
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
