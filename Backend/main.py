"""
Padel Checker – public MVP entry point.
Replaces app.py for the refactored backend. app.py is kept as a backup.

Phase 1: availability is mocked (always true).
Phase 3/4 will wire in real scrapers.
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from distance import filter_by_radius
from etennis_checker import check_etennis_venues, get_cached_statuses
from venues_mongo import load_venues
from weather import get_weather_cached

VIENNA_TZ = ZoneInfo("Europe/Vienna")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_INDOOR_TYPES  = {"indoor", "indoor+outdoor"}
_OUTDOOR_TYPES = {"outdoor", "indoor+outdoor"}

_executor = ThreadPoolExecutor(max_workers=20)

# Maps eTennis scraper status strings to the API's boolean/null convention.
_ETENNIS_STATUS_MAP: dict[str, bool | None] = {
    "free":    True,
    "busy":    False,
    "unknown": None,
    "no_slot": None,
}


def _parse_datetime(
    date_str: str | None, time_str: str | None
) -> tuple[datetime, str | None]:
    now = datetime.now(VIENNA_TZ).replace(minute=0, second=0, microsecond=0)
    if date_str is None and time_str is None:
        return now, None
    date_str = date_str or now.strftime("%Y-%m-%d")
    time_str = time_str or now.strftime("%H:00")
    try:
        dt = datetime.strptime(f"{date_str}T{time_str}", "%Y-%m-%dT%H:%M")
        return dt.replace(tzinfo=VIENNA_TZ), None
    except ValueError:
        return now, "invalid format — expected date=YYYY-MM-DD, time=HH:MM"


def _filter_court_type(venues: list[dict], court_type: str | None) -> list[dict]:
    if not court_type or court_type == "all":
        return venues
    allowed = _INDOOR_TYPES if court_type == "indoor" else _OUTDOOR_TYPES
    return [v for v in venues if v["court_type"] in allowed]


async def _fetch_weather_async(venue: dict, dt: datetime) -> dict:
    """Fetch weather for one venue without blocking the event loop."""
    if venue.get("lat") is None or venue.get("lon") is None:
        return {**venue, "weather": None}
    loop = asyncio.get_running_loop()
    weather = await loop.run_in_executor(
        _executor, get_weather_cached, venue["id"], venue["lat"], venue["lon"], dt
    )
    return {**venue, "weather": weather}


async def _fetch_availability_async(venues: list[dict], dt: datetime) -> dict[str, bool | None]:
    """
    Two-phase availability:

    1. Fast path  — read whatever is already in the in-process cache (instant).
    2. Background — if any venues are missing, fire check_etennis_venues without
       awaiting it. The _RUNNING guard in etennis_checker prevents duplicate
       concurrent scrapes. The next request will get cache hits.

    The response is never delayed by scraping.
    """
    etennis_venues = [v for v in venues if v["platform"] == "eTennis"]
    if not etennis_venues:
        return {}

    loop = asyncio.get_running_loop()

    # Phase 1: instant dict lookup — no I/O, always sub-millisecond.
    try:
        cached_statuses: dict[str, str] = await loop.run_in_executor(
            _executor, get_cached_statuses, etennis_venues, dt
        )
    except Exception as exc:
        print(f"[availability] cache read failed: {exc}")
        cached_statuses = {}

    # Phase 2: kick off a background scrape for any venue not yet in cache.
    # check_etennis_venues handles cooldowns and the in-flight guard internally.
    if len(cached_statuses) < len(etennis_venues):
        bg = loop.run_in_executor(_executor, check_etennis_venues, etennis_venues, dt)
        bg.add_done_callback(lambda _: None)  # discard result; suppress warnings

    return {
        venue_id: _ETENNIS_STATUS_MAP.get(status)
        for venue_id, status in cached_statuses.items()
    }


def _build_result(venue: dict, available: bool | None) -> dict:
    return {
        "venue_id":    venue["id"],
        "name":        venue["name"],
        "platform":    venue["platform"],
        "distance_km": venue.get("distance_km"),   # None in region mode
        "court_type":  venue["court_type"],
        "region":      venue.get("region"),
        "available":   available,
        "booking_url": venue["booking_url"],
        "weather":     venue.get("weather"),
    }


@app.get("/api/search")
async def search(
    date:       str | None = Query(default=None),
    time:       str | None = Query(default=None),
    court_type: str | None = Query(default=None),
    # Personal mode
    region:     str | None = Query(default=None),
    # Public mode
    lat:        float | None = Query(default=None),
    lon:        float | None = Query(default=None),
    radius:     int   | None = Query(default=None),
):
    # ── Validate date/time ────────────────────────────────────────────────
    dt, parse_error = _parse_datetime(date, time)
    if parse_error:
        return JSONResponse(
            status_code=400,
            content={"detail": "invalid_parameter", "message": parse_error},
        )

    # ── Validate mode ─────────────────────────────────────────────────────
    # Either region (personal) or lat+lon+radius (public) must be supplied.
    use_region = region is not None
    use_radius = lat is not None and lon is not None and radius is not None

    if not use_region and not use_radius:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "missing_parameter",
                "message": "Provide region (personal mode) or lat+lon+radius (public mode)",
            },
        )

    if court_type and court_type not in ("indoor", "outdoor", "all"):
        return JSONResponse(
            status_code=400,
            content={"detail": "invalid_parameter", "message": "court_type must be indoor, outdoor, or all"},
        )

    # ── Load + filter venues ──────────────────────────────────────────────
    all_venues = await load_venues()
    venues = _filter_court_type(all_venues, court_type)

    if use_region:
        venues = [v for v in venues if v["region"] == region]
    else:
        venues = filter_by_radius(venues, lat, lon, radius)

    if not venues:
        return {
            "results": [],
            "date":    dt.strftime("%Y-%m-%d"),
            "time":    dt.strftime("%H:%M"),
        }

    # ── Fetch weather + availability in parallel ──────────────────────────
    # Weather: one task per venue. Availability: one task for all eTennis venues.
    # Both run concurrently so Playwright doesn't add to the weather latency.
    all_weather, availability = await asyncio.gather(
        asyncio.gather(*[_fetch_weather_async(v, dt) for v in venues]),
        _fetch_availability_async(venues, dt),
    )
    with_weather = list(all_weather)

    # Sort: personal mode → priority asc; public mode → distance asc
    if use_region:
        with_weather.sort(key=lambda v: v.get("priority", 0))
    else:
        with_weather.sort(key=lambda v: v.get("distance_km") or 0)

    # availability dict only contains eTennis venues; all others default to None.
    return {
        "results": [_build_result(v, availability.get(v["id"])) for v in with_weather],
        "date":    dt.strftime("%Y-%m-%d"),
        "time":    dt.strftime("%H:%M"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=5000, reload=False)
