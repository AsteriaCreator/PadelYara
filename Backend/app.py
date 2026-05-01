from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from etennis_checker import check_etennis_venues
from venues import load_venues
from weather import get_weather_cached, get_weather_for_hour

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


def _filter_venues(region: str | None, court_type: str | None) -> list[dict]:
    result = VENUES

    if region:
        result = [v for v in result if v["region"] == region]

    if court_type and court_type != "both":
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
        "status":      "unknown",
        "error":       None,
        "weather":     None,
    }

    if venue["lat"] is None or venue["lon"] is None:
        base["error"] = "no_coordinates"
        return base

    weather = get_weather_cached(venue["id"], venue["lat"], venue["lon"], dt)
    if weather is None:
        base["error"] = "weather_unavailable"
    else:
        base["weather"] = weather

    return base


@app.get("/api/search")
def search(
    date:       str | None = Query(default=None),
    time:       str | None = Query(default=None),
    region:     str | None = Query(default=None),
    court_type: str | None = Query(default=None),
):
    dt, parse_error = _parse_datetime(date, time)
    if parse_error:
        return JSONResponse(status_code=400, content={"ok": False, "error": parse_error})

    venues = _filter_venues(region, court_type)
    if not venues:
        return {"ok": True, "results": [], "date": dt.strftime("%Y-%m-%d"), "time": dt.strftime("%H:%M")}

    results = [None] * len(venues)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_fetch_venue_weather, v, dt): i for i, v in enumerate(venues)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    # ── Phase 2: eTennis availability ────────────────────────────────
    etennis_venues = [v for v in venues if v["platform"] == "eTennis"]
    if etennis_venues:
        try:
            availability = check_etennis_venues(etennis_venues, dt)
            for result in results:
                if result["id"] in availability:
                    result["status"] = availability[result["id"]]
        except Exception as exc:
            print(f"[eTennis] search phase error: {exc}")

    results.sort(key=lambda v: v["priority"])

    return {
        "ok":      True,
        "results": results,
        "date":    dt.strftime("%Y-%m-%d"),
        "time":    dt.strftime("%H:%M"),
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

    weather = get_weather_for_hour(venue["lat"], venue["lon"], dt)
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
    # reload=False: avoids conflicts with Playwright's Chrome subprocess
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=False)
