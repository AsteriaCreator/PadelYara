import asyncio
import json
import math
import os
import threading
import time
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
from venues import load_venues
from weather import get_weather_cached, get_weather_for_hour


# Env var required on Render: EVERSPORTS_SERVICE_URL=https://<railway-service-url>
def _call_eversports_service(
    fid: int, cids: list[int], date_str: str, time_hhmm: str, venue_id: str = "unknown"
) -> str:
    """Call the Railway Eversports microservice. Falls back to platform_check_required."""
    url = os.environ.get("EVERSPORTS_SERVICE_URL")
    if not url:
        return "platform_check_required"

    t0 = time.monotonic()
    time_colon = f"{time_hhmm[:2]}:{time_hhmm[2:]}"  # "1800" -> "18:00"

    def _log(status: str, error: str | None = None) -> None:
        entry: dict = {
            "event":       "eversports_service_result",
            "venue_id":    venue_id,
            "facility_id": fid,
            "date":        date_str,
            "time":        time_colon,
            "status":      status,
            "duration_ms": round((time.monotonic() - t0) * 1000),
        }
        if error:
            entry["error"] = error
        print(json.dumps(entry))

    try:
        r = httpx.get(
            f"{url.rstrip('/')}/check",
            params={
                "facility_id": fid,
                "court_ids": ",".join(str(c) for c in cids),
                "date": date_str,
                "time": time_colon,
            },
            timeout=15,
        )
        if r.status_code == 200:
            body = r.json()
            status = body.get("status", "platform_check_required")
            slots_count = body.get("slots_count")
            _log(status)
            print(json.dumps({
                "event":       "eversports_raw_response",
                "venue_id":    venue_id,
                "facility_id": fid,
                "date":        date_str,
                "time":        time_colon,
                "status":      status,
                "slots_count": slots_count,
            }))
            return status
        _log("platform_check_required", error=f"http_{r.status_code}")
        print(f"[Eversports service] HTTP {r.status_code} for facilityId={fid}")
        return "platform_check_required"
    except Exception as exc:
        _log("platform_check_required", error=f"{type(exc).__name__}: {exc}")
        print(f"[Eversports service] request failed: {type(exc).__name__}: {exc}")
        return "platform_check_required"


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
_ev_ids = [(v["id"], v["eversports_facility_id"], v["eversports_court_ids"])
           for v in VENUES if v.get("eversports_facility_id")]
print(f"[startup] Eversports venues with facility IDs: {_ev_ids}")
DEFAULT_VENUE_ID = "padelzone-traiskirchen"
VIENNA_TZ = ZoneInfo("Europe/Vienna")

_RUNNING: set[str] = set()   # tracks in-flight background checks
_RUNNING_LOCK = threading.Lock()
_SCRAPER_SEM = threading.Semaphore(1)  # only one Playwright browser at a time on Render


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
        "venue_id":            venue["id"],
        "name":                venue["name"],
        "region":              venue["region"],
        "court_type":          venue["court_type"],
        "platform":            venue["platform"],
        "priority":            venue["priority"],
        "booking_url":         venue["booking_url"],
        "distance_km":         venue.get("distance_km"),
        "availability_status": "unknown",
        "error":               None,
        "weather":             None,
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

    # In radius mode limit availability scraping to the 5 closest venues so
    # Render's free tier (512 MB, 0.1 CPU) doesn't launch too many browsers.
    if lat is not None:
        scrape_ids = {
            v["id"]
            for v in sorted(venues, key=lambda v: v.get("distance_km") or float("inf"))[:5]
        }
    else:
        scrape_ids = None  # region mode: scrape everything

    # ── Phase 2: eTennis — serve cached, background-fetch the rest ───────
    etennis_venues = [v for v in venues if v["platform"] == "eTennis"]
    if etennis_venues:
        cached = get_etennis_cached(etennis_venues, dt)
        print(f"[search] eTennis cache: {len(cached)}/{len(etennis_venues)} hits — {list(cached.items())}")
        for result in results:
            vid = result["venue_id"]
            if vid in cached:
                result["availability_status"] = cached[vid]
            elif result["platform"] == "eTennis":
                if scrape_ids is None or vid in scrape_ids:
                    result["availability_status"] = "pending"
                else:
                    result["availability_status"] = "not_checked"
        to_fetch = [v for v in etennis_venues
                    if v["id"] not in cached and (scrape_ids is None or v["id"] in scrape_ids)]
        if to_fetch:
            key = _run_key("eTennis", dt)
            with _RUNNING_LOCK:
                et_should_start = key not in _RUNNING
                if et_should_start:
                    _RUNNING.add(key)
            if et_should_start:
                print(f"[search] eTennis scraper starting: key={key} venues={[v['id'] for v in to_fetch]}")
                def _et_bg(vv=to_fetch, d=dt, k=key):
                    with _SCRAPER_SEM:
                        print(f"[search] eTennis scraper acquired semaphore: key={k}")
                        try:
                            check_etennis_venues(etennis_venues, d)
                            print(f"[search] eTennis scraper finished: key={k}")
                        finally:
                            with _RUNNING_LOCK:
                                _RUNNING.discard(k)
                threading.Thread(target=_et_bg, daemon=True).start()


    # ── Phase 3: Eversports — direct /api/slot check for venues with known IDs;
    #    all others fall back to platform_check_required immediately ────────────
    # scrape_ids gates eTennis only; Eversports API calls are cheap, no limit needed.
    _all_platforms = [(r["venue_id"], r["platform"]) for r in results]
    print(f"[Eversports API] Phase3 entry — all result platforms: {_all_platforms}")

    for result in results:
        if result["platform"] != "Eversports":
            continue
        venue = next((v for v in venues if v["id"] == result["venue_id"]), None)
        fid   = venue.get("eversports_facility_id") if venue else None
        cids  = venue.get("eversports_court_ids")   if venue else None
        print(f"[Eversports API] {result['venue_id']}  platform={result['platform']!r}  fid={fid!r}  court_ids={cids!r}")
        if fid and cids:
            time_hhmm = dt.strftime("%H%M")
            status = _call_eversports_service(fid, cids, dt.strftime("%Y-%m-%d"), time_hhmm, venue_id=result["venue_id"])
            print(f"[Eversports API] {result['venue_id']}  final_status={status}")
            result["availability_status"] = status
        else:
            issues = venue.get("issues", "") if venue else ""
            if issues == "phone_booking_only":
                print(f"[Eversports API] {result['venue_id']}  phone-only venue — not_checked")
                result["availability_status"] = "not_checked"
            else:
                print(f"[Eversports API] {result['venue_id']}  fid/cids missing — platform_check_required")
                result["availability_status"] = "platform_check_required"

    availability_pending = any(r["availability_status"] == "pending" for r in results)
    print(f"[search] availability_pending={availability_pending}")

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
    port = int(os.environ.get("PORT", 5000))
    # reload=False: avoids conflicts with Playwright's Chrome subprocess
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
