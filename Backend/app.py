import asyncio
import math
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from etennis_checker import check_etennis_venues
from etennis_checker import get_cached_statuses as get_etennis_cached
from eversports_checker import check_eversports_venues
from eversports_checker import get_cached_statuses as get_eversports_cached
from venues import load_venues
from weather import get_weather_cached, get_weather_for_hour


def _run_async(coro):
    """Run an async coroutine from any thread using a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VENUES = load_venues()
DEFAULT_VENUE_ID = "padelzone-traiskirchen"
VIENNA_TZ = ZoneInfo("Europe/Vienna")

_RUNNING: set[str] = set()   # tracks in-flight background checks
_RUNNING_LOCK = threading.Lock()
_SCRAPER_SEM = threading.Semaphore(1)  # only one Playwright browser at a time on Render

_EVERSPORTS_STATUS_MAP: dict[str, str] = {
    "free": "free",
    "busy": "busy",
    # "unknown" falls through to "platform_check_required"
}


def _run_key(platform: str, dt: datetime) -> str:
    return f"{platform}*{dt.strftime('%Y-%m-%d')}*{dt.hour:02d}"

_INDOOR_TYPES  = {"indoor", "indoor+outdoor"}
_OUTDOOR_TYPES = {"outdoor", "indoor+outdoor"}


def _parse_datetime(date_str: str | None, time_str: str | None) -> tuple[datetime, str | None]:
    now = datetime.now(VIENNA_TZ).replace(minute=0, second=0, microsecond=0)

    if date_str is None and time_str is None:
        return now, None
    if date_str is None:
        date_str = now.strftime("%Y-%m-%d")
    if time_str is None:
        time_str = now.strftime("%H:00")

    try:
        dt = datetime.strptime(f"{date_str}T{time_str}", "%Y-%m-%dT%H:%M")
    except ValueError:
        return now, f"invalid format — expected date=YYYY-MM-DD, time=HH:MM, got '{date_str}' '{time_str}'"

    return dt.replace(tzinfo=VIENNA_TZ), None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _filter_venues(
    region: str | None,
    court_type: str | None,
    lat: float | None = None,
    lon: float | None = None,
    radius: float | None = None,
) -> list[dict]:
    result = VENUES

    if region:
        result = [v for v in result if v["region"] == region]
    elif lat is not None and lon is not None and radius is not None:
        with_dist = []
        for v in result:
            if v["lat"] is not None and v["lon"] is not None:
                dist = _haversine_km(lat, lon, v["lat"], v["lon"])
                if dist <= radius:
                    with_dist.append({**v, "distance_km": round(dist, 1)})
        result = with_dist

    if court_type and court_type != "both" and court_type != "all":
        allowed = _INDOOR_TYPES if court_type == "indoor" else _OUTDOOR_TYPES
        result = [v for v in result if v["court_type"] in allowed]

    return result


def _fetch_venue_weather(venue: dict, dt: datetime) -> dict:
    base = {
        "id":          venue["id"],
        "name":        venue["name"],
        "region":      venue["region"],
        "court_type":  venue["court_type"],
        "platform":    venue["platform"],
        "priority":    venue["priority"],
        "booking_url": venue["booking_url"],
        "distance_km": venue.get("distance_km"),
        "status":      "unknown",
        "error":       None,
        "weather":     None,
    }

    if venue["lat"] is None or venue["lon"] is None:
        base["error"] = "no_coordinates"
        return base

    async def _get():
        async with httpx.AsyncClient() as client:
            return await get_weather_cached(client, venue["lat"], venue["lon"], dt)

    weather = _run_async(_get())
    if weather is None:
        base["error"] = "weather_unavailable"
    else:
        base["weather"] = weather

    return base


@app.get("/api/search")
def search(
    date:       str | None   = Query(default=None),
    time:       str | None   = Query(default=None),
    region:     str | None   = Query(default=None),
    court_type: str | None   = Query(default=None),
    lat:        float | None = Query(default=None),
    lon:        float | None = Query(default=None),
    radius:     float | None = Query(default=None),
):
    dt, parse_error = _parse_datetime(date, time)
    if parse_error:
        return JSONResponse(status_code=400, content={"ok": False, "error": parse_error})

    venues = _filter_venues(region, court_type, lat, lon, radius)
    if not venues:
        return {"ok": True, "results": [], "date": dt.strftime("%Y-%m-%d"), "time": dt.strftime("%H:%M"), "availability_pending": False}

    results = [None] * len(venues)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_fetch_venue_weather, v, dt): i for i, v in enumerate(venues)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    # ── Phase 2: eTennis — serve cached, background-fetch the rest ───────
    etennis_venues = [v for v in venues if v["platform"] == "eTennis"]
    if etennis_venues:
        cached = get_etennis_cached(etennis_venues, dt)
        for result in results:
            if result["id"] in cached:
                result["status"] = cached[result["id"]]
        to_fetch = [v for v in etennis_venues if v["id"] not in cached]
        key = _run_key("eTennis", dt)
        if to_fetch and key not in _RUNNING:
            _RUNNING.add(key)
            def _et_bg(vv=to_fetch, d=dt, k=key):
                with _SCRAPER_SEM:
                    try:
                        check_etennis_venues(vv, d)
                    finally:
                        _RUNNING.discard(k)
            threading.Thread(target=_et_bg, daemon=True).start()

    # ── Phase 3: Eversports — map checker result; unknown → platform_check_required ──
    eversports_venues = [v for v in venues if v["platform"] == "Eversports"]
    if eversports_venues:
        ev_cached = get_eversports_cached(eversports_venues, dt)
        ev_cached_ids = set(ev_cached)
        for result in results:
            if result["platform"] != "Eversports":
                continue
            if result["id"] in ev_cached_ids:
                raw = ev_cached[result["id"]]
                result["status"] = _EVERSPORTS_STATUS_MAP.get(raw, "platform_check_required")
            else:
                result["status"] = "pending"

        ev_to_fetch = [v for v in eversports_venues if v["id"] not in ev_cached_ids]
        ev_key = _run_key("Eversports", dt)
        with _RUNNING_LOCK:
            ev_should_start = bool(ev_to_fetch) and ev_key not in _RUNNING
            if ev_should_start:
                _RUNNING.add(ev_key)
        if ev_should_start:
            def _ev_bg(vv=ev_to_fetch, d=dt, k=ev_key):
                with _SCRAPER_SEM:
                    try:
                        check_eversports_venues(vv, d)
                    finally:
                        with _RUNNING_LOCK:
                            _RUNNING.discard(k)
            threading.Thread(target=_ev_bg, daemon=True).start()

    with _RUNNING_LOCK:
        availability_pending = any(
            _run_key(p, dt) in _RUNNING for p in ("eTennis", "Eversports")
        )

    if lat is not None:
        results.sort(key=lambda v: v.get("distance_km") or float("inf"))
    else:
        results.sort(key=lambda v: v["priority"])

    return {
        "ok":                   True,
        "results":              results,
        "date":                 dt.strftime("%Y-%m-%d"),
        "time":                 dt.strftime("%H:%M"),
        "availability_pending": availability_pending,
    }


@app.get("/api/weather-test")
def weather_test(
    venue_id: str | None = Query(default=None),
    date:     str | None = Query(default=None),
    time:     str | None = Query(default=None),
):
    vid = venue_id or DEFAULT_VENUE_ID

    venue = next((v for v in VENUES if v["id"] == vid), None)
    if venue is None:
        return JSONResponse(status_code=404, content={"error": "venue_not_found", "venue_id": vid})

    if venue["lat"] is None or venue["lon"] is None:
        return JSONResponse(status_code=422, content={"error": "no_coordinates", "venue_id": vid})

    dt, parse_error = _parse_datetime(date, time)
    if parse_error:
        return JSONResponse(status_code=400, content={"error": "invalid_params", "detail": parse_error})

    async def _get():
        async with httpx.AsyncClient() as client:
            return await get_weather_for_hour(client, venue["lat"], venue["lon"], dt)

    weather = _run_async(_get())
    if weather is None:
        return JSONResponse(status_code=502, content={"error": "weather_unavailable", "venue_id": vid})

    return {
        "venue_id":       venue["id"],
        "venue_name":     venue["name"],
        "lat":            venue["lat"],
        "lon":            venue["lon"],
        "requested_time": dt.strftime("%Y-%m-%dT%H:%M"),
        "weather":        weather,
    }


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    # reload=False: avoids conflicts with Playwright's Chrome subprocess
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
