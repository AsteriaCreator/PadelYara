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
from etennis_checker import check_etennis_venues
from etennis_checker import get_cached_statuses as get_etennis_cached
from eversports_checker import check_eversports_venues
from eversports_checker import get_cached_statuses as get_eversports_cached
from venues_mongo import load_venues
import httpx

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

# Raw scraper output → canonical availability_status
_SCRAPER_STATUS: dict[str, str] = {
    "free":    "free",
    "busy":    "busy",
    "unknown": "check_failed",
    "no_slot": "busy",        # no slot at this time = not bookable
}

# Canonical status → available bool (kept for backward-compat)
_STATUS_TO_AVAILABLE: dict[str, bool | None] = {
    "free":         True,
    "busy":         False,
    "check_failed": None,
    "pending":      None,
    "phone_only":   None,
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


async def _fetch_weather_async(client: httpx.AsyncClient, venue: dict, dt: datetime) -> dict:
    if venue.get("lat") is None or venue.get("lon") is None:
        return {**venue, "weather": None}
    weather = await get_weather_cached(client, venue["lat"], venue["lon"], dt)
    return {**venue, "weather": weather}


async def _fetch_platform_async(
    loop,
    venues: list[dict],
    dt: datetime,
    get_cached_fn,
    check_fn,
    label: str,
) -> dict[str, str]:
    """
    Generic two-phase availability fetch for a single platform.

    Phase 1: read cache (instant, no I/O).
    Phase 2: if any venues are uncached, fire the scraper in the background
             without blocking the response.

    Returns {venue_id: canonical_status} for venues already in cache only.
    Missing keys = not yet cached (caller marks those as "pending").
    """
    if not venues:
        return {}

    try:
        cached: dict[str, str] = await loop.run_in_executor(
            _executor, get_cached_fn, venues, dt
        )
    except Exception as exc:
        print(f"[{label}] cache read failed: {exc}")
        cached = {}

    if len(cached) < len(venues):
        bg = loop.run_in_executor(_executor, check_fn, venues, dt)
        bg.add_done_callback(lambda _: None)

    return {vid: _SCRAPER_STATUS.get(st, "check_failed") for vid, st in cached.items()}


async def _fetch_availability_async(venues: list[dict], dt: datetime) -> dict[str, str]:
    """
    Run eTennis and Eversports availability fetches in parallel.
    Both use the same non-blocking two-phase pattern:
      Phase 1 — instant cache read.
      Phase 2 — background scrape if cache is cold (never delays the response).

    Returns {venue_id: availability_status} for ALL venues:
      "free" | "busy" | "check_failed" | "pending" | "phone_only"
    """
    etennis_venues       = [v for v in venues if v["platform"] == "eTennis"]
    eversports_scrapeable = [v for v in venues if v["platform"] == "Eversports"
                              and v.get("issues") not in ("phone_only", "eversports_display_only")]

    loop = asyncio.get_running_loop()

    etennis_result, eversports_result = await asyncio.gather(
        _fetch_platform_async(loop, etennis_venues,        dt, get_etennis_cached,    check_etennis_venues,    "eTennis"),
        _fetch_platform_async(loop, eversports_scrapeable, dt, get_eversports_cached, check_eversports_venues, "Eversports"),
    )

    resolved = {**etennis_result, **eversports_result}

    # Assign explicit status to every venue
    out: dict[str, str] = {}
    for v in venues:
        vid = v["id"]
        if v.get("issues") == "phone_only":
            out[vid] = "phone_only"
        elif v.get("issues") == "eversports_display_only":
            out[vid] = "check_failed"
        else:
            out[vid] = resolved.get(vid, "pending")
    return out


def _build_result(venue: dict, status: str) -> dict:
    return {
        "venue_id":             venue["id"],
        "name":                 venue["name"],
        "platform":             venue["platform"],
        "distance_km":          venue.get("distance_km"),   # None in region mode
        "court_type":           venue["court_type"],
        "region":               venue.get("region"),
        "availability_status":  status,
        "available":            _STATUS_TO_AVAILABLE.get(status),  # backward-compat
        "booking_url":          venue["booking_url"],
        "weather":              venue.get("weather"),
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
    async with httpx.AsyncClient() as client:
        all_weather, availability = await asyncio.gather(
            asyncio.gather(*[_fetch_weather_async(client, v, dt) for v in venues]),
            _fetch_availability_async(venues, dt),
        )
    with_weather = list(all_weather)

    # Sort: personal mode → priority asc; public mode → distance asc
    if use_region:
        with_weather.sort(key=lambda v: v.get("priority", 0))
    else:
        with_weather.sort(key=lambda v: v.get("distance_km") or 0)

    results = [_build_result(v, availability[v["id"]]) for v in with_weather]
    return {
        "results":              results,
        "date":                 dt.strftime("%Y-%m-%d"),
        "time":                 dt.strftime("%H:%M"),
        "availability_pending": any(r["availability_status"] == "pending" for r in results),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=False)
