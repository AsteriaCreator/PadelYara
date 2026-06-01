import asyncio
import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from time import monotonic as time_monotonic
from zoneinfo import ZoneInfo

import httpx
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import analytics
from analytics import (
    track_booking_clicked,
    track_scraper_timeout,
    track_search_completed,
    track_search_failed,
)
from etennis_checker import DEFAULT_FALLBACK_MINUTES as ET_DEFAULT_FALLBACK

# Eversports venues can have 30-min or 60-min slots depending on the court
# (e.g. Traiskirchen Court 3 has 30-min slots), so check both offsets.
EV_DEFAULT_FALLBACK: list[int] = [30, 60]
from etennis_checker import check_etennis_venues
from etennis_checker import get_cached_entries as get_etennis_entries
from etennis_checker import get_cached_statuses as get_etennis_cached
from venues import load_venues
from weather import get_weather_for_hour


# Env var required on Render: EVERSPORTS_SERVICE_URL=https://<railway-service-url>
def _call_eversports_service(
    fid: int, cids: list[int], date_str: str, time_hhmm: str,
    venue_id: str = "unknown", booking_url: str = "",
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
        params = {
            "facility_id": fid,
            "court_ids":   ",".join(str(c) for c in cids),
            "date":        date_str,
            "time":        time_colon,
            "venue_id":    venue_id,
        }
        if booking_url:
            params["venue_url"] = booking_url
        r = httpx.get(
            f"{url.rstrip('/')}/check",
            params=params,
            timeout=60,  # /api/slot + CF cookie warmup max ~45s; DOM scrape removed
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
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        if isinstance(exc, httpx.TimeoutException):
            track_scraper_timeout(venue_id=venue_id, platform="Eversports", timeout_ms=elapsed_ms)
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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await analytics.lifespan_startup()
    yield


app = FastAPI(lifespan=lifespan)

_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
_allowed_origins = [
    _frontend_url,
    "https://neo-padel-checker.vercel.app",
]
# Also allow Vercel preview deployments for this project (neo-padel-checker-*)
_VERCEL_PREVIEW_PATTERN = r"https://neo-padel-checker-[a-z0-9-]+\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=_VERCEL_PREVIEW_PATTERN,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

VENUES = load_venues()
_ev_ids = [(v["id"], v["eversports_facility_id"], v["eversports_court_ids"])
           for v in VENUES if v.get("eversports_facility_id")]
print(f"[startup] Eversports venues with facility IDs: {_ev_ids}")
DEFAULT_VENUE_ID = "padelzone-traiskirchen"
VIENNA_TZ = ZoneInfo("Europe/Vienna")

_RUNNING: set[str] = set()   # tracks in-flight background checks
_RUNNING_LOCK = threading.Lock()

# ── Response cache (TTL) ─────────────────────────────────────────────────────
# key → (response_dict, stored_at_monotonic, ttl_seconds)
# No inflight coordination: the pending-first design means the FIRST response
# returns quickly (eTennis = pending, Eversports = real status). Inflight
# coordination was removed because it blocked all polls behind the first
# request's full Eversports scan (up to 60 s per venue × 8 venues).
_SEARCH_CACHE: dict[str, tuple[dict, float, float]] = {}
_SEARCH_LOCK = threading.Lock()
_SEARCH_CACHE_TTL_COMPLETE = 45   # s — no pending scrapes; safe to serve for 45 s
_SEARCH_CACHE_TTL_PENDING   = 8   # s — eTennis still scraping; absorbs burst but
                                  #     lets clients poll for real statuses quickly

# ── Eversports venue-level result cache ──────────────────────────────────────
# key → (status_string, stored_at_monotonic)
_EV_RESULT_CACHE: dict[str, tuple[str, float]] = {}
_EV_RESULT_LOCK = threading.Lock()
_EV_RESULT_TTL = 300  # s — match eTennis _TTL


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
    court_type: str | None,
    lat: float | None = None,
    lon: float | None = None,
    radius: float | None = None,
) -> list[dict]:
    result = VENUES

    if lat is not None and lon is not None and radius is not None:
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


def _build_venue_result(venue: dict) -> dict:
    return {
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
    }


ET_BATCH = 5  # eTennis venues checked per request (Render free-tier limit)

_MAX_FUTURE_DAYS = 42   # absolute ceiling: beyond this → 400
_FAR_FUTURE_DAYS = 14   # soft threshold: beyond this → allowed but with notice
_BOOKING_WINDOW_NOTICE = (
    "Viele Anbieter erlauben Buchungen nur bis 14 Tage im Voraus. "
    "Angezeigte Ergebnisse können daher unvollständig sein."
)


def _validate_date(date_str: str | None) -> tuple[str | None, JSONResponse | None]:
    """
    Validate the date query param before any cache or scraper work.

    Returns (date_bucket, error_response):
      - error_response is non-None → return it immediately to the client.
      - date_bucket: "normal" | "far_future" (only meaningful when error is None).
    """
    today = datetime.now(VIENNA_TZ).date()

    if date_str is None:
        return "normal", None

    try:
        search_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        print(json.dumps({"event": "invalid_date_format", "date": date_str}))
        return None, JSONResponse(
            status_code=400,
            content={"ok": False, "error": f"Ungültiges Datum: '{date_str}'. Erwartet: JJJJ-MM-TT."},
        )

    if search_date < today:
        print(json.dumps({"event": "search_date_in_past", "date": date_str, "today": str(today)}))
        return None, JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Suchen in der Vergangenheit sind nicht möglich."},
        )

    if search_date > today + timedelta(days=_MAX_FUTURE_DAYS):
        print(json.dumps({
            "event":    "search_date_beyond_max_window",
            "date":     date_str,
            "today":    str(today),
            "max_days": _MAX_FUTURE_DAYS,
        }))
        return None, JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Suchen sind maximal 6 Wochen im Voraus möglich."},
        )

    if search_date > today + timedelta(days=_FAR_FUTURE_DAYS):
        print(json.dumps({
            "event":     "search_date_far_future_allowed",
            "date":      date_str,
            "today":     str(today),
            "days_ahead": (search_date - today).days,
        }))
        return "far_future", None

    return "normal", None


def _search_cache_key(
    date: str | None, time_str: str | None, lat: float | None, lon: float | None,
    radius: float | None, court_type: str | None, et_offset: int,
) -> str:
    return f"{date}|{time_str}|{lat}|{lon}|{radius}|{court_type}|{et_offset}"


def _ev_result_key(venue_id: str, date_str: str, time_hhmm: str) -> str:
    return f"{venue_id}*{date_str}*{time_hhmm}"


def _purge_ev_result_cache() -> None:
    """Evict expired entries. Must be called with _EV_RESULT_LOCK held."""
    now_t = time_monotonic()
    expired = [k for k, (_, ts) in _EV_RESULT_CACHE.items() if now_t - ts >= _EV_RESULT_TTL]
    for k in expired:
        del _EV_RESULT_CACHE[k]


def _purge_search_cache() -> None:
    """Evict expired entries. Must be called with _SEARCH_LOCK held."""
    now_t = time_monotonic()
    expired = [k for k, (_, ts, ttl) in _SEARCH_CACHE.items() if now_t - ts >= ttl]
    for k in expired:
        del _SEARCH_CACHE[k]


def _call_eversports_cached(
    fid: int, cids: list[int], date_str: str, time_hhmm: str,
    venue_id: str = "unknown", booking_url: str = "",
) -> str:
    """TTL-cached wrapper around _call_eversports_service (5-min cache per venue+time)."""
    key = _ev_result_key(venue_id, date_str, time_hhmm)
    now_t = time_monotonic()
    with _EV_RESULT_LOCK:
        entry = _EV_RESULT_CACHE.get(key)
        if entry is not None:
            status, ts = entry
            age = now_t - ts
            if age < _EV_RESULT_TTL:
                print(json.dumps({
                    "event":    "ev_cache_hit",
                    "venue_id": venue_id,
                    "status":   status,
                    "age_s":    round(age, 1),
                }))
                return status
            del _EV_RESULT_CACHE[key]
    status = _call_eversports_service(fid, cids, date_str, time_hhmm, venue_id, booking_url)
    # Cache only structurally stable statuses:
    #   "free"    — a confirmed open slot; stable within the TTL window.
    #   "no_slot" — no slot starts at this exact time; structural, very stable.
    # Do NOT cache "busy" — a booked slot can be cancelled and become free
    # within the TTL window, which would cause stale "busy" results (regression).
    # Do NOT cache platform_check_required / failures — they prevent Railway retries.
    if status in ("free", "no_slot"):
        with _EV_RESULT_LOCK:
            if len(_EV_RESULT_CACHE) > 500:
                _purge_ev_result_cache()
            _EV_RESULT_CACHE[key] = (status, time_monotonic())
    return status


@app.get("/api/search")
def search(
    date:       str | None   = Query(default=None),
    time:       str | None   = Query(default=None),
    court_type: str | None   = Query(default=None),
    lat:        float | None = Query(default=None),
    lon:        float | None = Query(default=None),
    radius:     float | None = Query(default=None),
    et_offset:  int          = Query(default=0),
):
    t0 = time_monotonic()

    # ── Date validation — runs before cache, inflight, or any scraper work ────
    date_bucket, date_error = _validate_date(date)
    if date_error is not None:
        return date_error

    # ── Phase 0: response cache ───────────────────────────────────────────────
    # Cache key covers every dimension that affects results.
    # No inflight coordination: requests run independently. Cache hits return
    # immediately; misses proceed through the full pipeline. This preserves the
    # pending-first architecture where the first response is fast (eTennis
    # pending + Eversports real status) and polls pick up updated statuses.
    cache_key = _search_cache_key(date, time, lat, lon, radius, court_type, et_offset)

    with _SEARCH_LOCK:
        cached_entry = _SEARCH_CACHE.get(cache_key)
        if cached_entry is not None:
            resp, cached_at, cached_ttl = cached_entry
            age = time_monotonic() - cached_at
            if age < cached_ttl:
                print(json.dumps({"event": "cache_hit", "cache_key": cache_key, "age_s": round(age, 1)}))
                return resp
            del _SEARCH_CACHE[cache_key]
            print(json.dumps({"event": "cache_expired", "cache_key": cache_key, "age_s": round(age, 1)}))

    print(json.dumps({"event": "cache_miss", "cache_key": cache_key}))

    # ── Phase 1: datetime + venue filtering ──────────────────────────────────
    dt, parse_error = _parse_datetime(date, time)
    if parse_error:
        track_search_failed(reason="invalid_datetime", court_type=court_type)
        return JSONResponse(status_code=400, content={"ok": False, "error": parse_error})

    venues = _filter_venues(court_type, lat, lon, radius)
    if not venues:
        return {"ok": True, "results": [], "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M"), "availability_pending": False, "has_more": False}

    results = [_build_venue_result(v) for v in venues]

    if not results:
        return {"ok": True, "results": [], "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M"), "availability_pending": False, "has_more": False}

    # Fetch weather once for the search location (one request, no per-venue calls)
    search_weather = None
    if lat is not None and lon is not None:
        async def _get_weather():
            async with httpx.AsyncClient() as client:
                return await get_weather_for_hour(client, lat, lon, dt)
        search_weather = _run_async(_get_weather())

    # In radius mode paginate eTennis scraping so Render's free tier
    # (0.1 CPU, 512 MB) never launches more than ET_BATCH browsers at once.
    # et_offset lets the frontend request successive batches ("Mehr Ergebnisse").
    et_by_dist = sorted(
        [v for v in venues if v["platform"] == "eTennis"],
        key=lambda v: v.get("distance_km") or float("inf"),
    )
    batch      = et_by_dist[et_offset : et_offset + ET_BATCH]
    scrape_ids = {v["id"] for v in batch}
    has_more   = len(et_by_dist) > et_offset + ET_BATCH

    # ── Phase 2: eTennis — serve cached, background-fetch the rest ───────────
    etennis_venues = [v for v in venues if v["platform"] == "eTennis"]
    if etennis_venues:
        cached  = get_etennis_cached(etennis_venues, dt)   # dict[str, str] — for status + to_fetch logic
        entries = get_etennis_entries(etennis_venues, dt)  # dict[str, dict] — for next_free_ts
        print(json.dumps({
            "event":      "etennis_cache_check",
            "hits":       len(cached),
            "total":      len(etennis_venues),
            "statuses":   dict(cached),
        }))
        for result in results:
            vid = result["venue_id"]
            if vid in cached:
                result["availability_status"] = cached[vid]
                # Propagate next_free_ts only when the primary slot is not free.
                # Guard: if the scraper cached a free result, next_free_ts should
                # already be absent, but this explicit check makes the invariant
                # bulletproof against race conditions or future cache changes.
                if cached[vid] != "free":
                    nft = entries.get(vid, {}).get("next_free_ts")
                    if nft is not None:
                        result["next_available_time"] = nft
            elif result["platform"] == "eTennis":
                if vid in scrape_ids:
                    result["availability_status"] = "pending"
                else:
                    result["availability_status"] = "not_checked"
        to_fetch = [v for v in etennis_venues
                    if v["id"] not in cached and v["id"] in scrape_ids]
        if to_fetch:
            key = _run_key("eTennis", dt)
            with _RUNNING_LOCK:
                et_should_start = key not in _RUNNING
                if et_should_start:
                    _RUNNING.add(key)
            if et_should_start:
                print(json.dumps({
                    "event":  "etennis_bg_start",
                    "key":    key,
                    "venues": [v["id"] for v in to_fetch],
                }))
                def _et_bg(vv=to_fetch, d=dt, k=key):
                    try:
                        check_etennis_venues(vv, d)
                    finally:
                        with _RUNNING_LOCK:
                            _RUNNING.discard(k)
                threading.Thread(target=_et_bg, daemon=True).start()
            else:
                print(json.dumps({
                    "event":  "etennis_bg_deduplicated",
                    "key":    key,
                    "venues": [v["id"] for v in to_fetch],
                }))

    # ── Phase 3: Eversports — only on the initial load (et_offset == 0).
    #    On "Mehr Ergebnisse" calls the frontend already has Eversports results;
    #    skip the Railway round-trips to avoid redundant work.
    #    All venue checks run in parallel — latency is bounded by the slowest
    #    single Railway round-trip, not N × RTT.
    if et_offset == 0:
        ev_venue_map = {v["id"]: v for v in venues}
        time_hhmm    = dt.strftime("%H%M")
        date_str_ev  = dt.strftime("%Y-%m-%d")

        def _check_ev(result: dict) -> None:
            venue = ev_venue_map.get(result["venue_id"])
            fid   = venue.get("eversports_facility_id") if venue else None
            cids  = venue.get("eversports_court_ids")   if venue else None
            if not (fid and cids):
                issues = (venue.get("issues", "") if venue else "")
                status = "not_checked" if issues == "phone_booking_only" else "platform_check_required"
                print(json.dumps({
                    "event":    "eversports_skip",
                    "venue_id": result["venue_id"],
                    "reason":   "phone_only" if issues == "phone_booking_only" else "no_fid_cids",
                }))
                result["availability_status"] = status
                return
            booking_url = venue.get("booking_url", "") if venue else ""
            status = _call_eversports_cached(
                fid, cids, date_str_ev, time_hhmm,
                venue_id=result["venue_id"], booking_url=booking_url,
            )
            result["availability_status"] = status
            # Fallback: if the exact requested slot is busy/no_slot, scan nearby
            # offsets to find the next free slot. Uses venue-specific config when
            # present, otherwise the module default covers mixed 30/60/90-min patterns.
            # The primary status check (busy/no_slot) ensures this never runs for
            # venues where 18:00 is already free.
            if status in ("busy", "no_slot"):
                fb_offsets = venue.get("slot_fallback_minutes") or EV_DEFAULT_FALLBACK
                for offset_min in fb_offsets:
                        dt_fb    = dt + timedelta(minutes=offset_min)
                        fb_status = _call_eversports_cached(
                            fid, cids,
                            dt_fb.strftime("%Y-%m-%d"),
                            dt_fb.strftime("%H%M"),
                            venue_id=result["venue_id"],
                            booking_url=booking_url,
                        )
                        print(json.dumps({
                            "event":      "eversports_fallback_result",
                            "venue_id":   result["venue_id"],
                            "date":       dt_fb.strftime("%Y-%m-%d"),
                            "time":       dt_fb.strftime("%H:%M"),
                            "offset_min": offset_min,
                            "primary":    status,
                            "fallback":   fb_status,
                        }))
                        if fb_status == "free":
                            result["next_available_time"] = int(
                                dt_fb.replace(tzinfo=VIENNA_TZ).timestamp()
                            )
                            break
                        if fb_status not in ("busy", "no_slot"):
                            break  # unknown / platform_check_required — stop scanning

        ev_results = [r for r in results if r["platform"] == "Eversports"]
        if ev_results:
            with ThreadPoolExecutor(max_workers=len(ev_results)) as pool:
                ev_futures = [pool.submit(_check_ev, r) for r in ev_results]
                for f in as_completed(ev_futures):
                    try:
                        f.result()
                    except Exception as exc:
                        print(json.dumps({"event": "eversports_thread_error", "error": str(exc)}))

    # ── Generic fallback label pass — applies to both eTennis and Eversports ──
    # Converts next_available_time (Unix ts) → display fields for the frontend.
    for result in results:
        nft = result.get("next_available_time")
        if nft is None:
            continue
        # Hard invariant: never show a "next slot" label when the exact requested
        # time is already free. This is the final firewall — upstream logic should
        # never set next_available_time on a free result, but stale cache entries
        # or race conditions could theoretically cause it. Strip and skip.
        if result.get("availability_status") == "free":
            result.pop("next_available_time", None)
            continue
        dt_next = datetime.fromtimestamp(nft, tz=VIENNA_TZ)
        fb_time = dt_next.strftime("%H:%M")
        result["time_adjusted"]    = True
        result["matched_time"]     = fb_time
        result["requested_time"]   = dt.strftime("%H:%M")
        result["adjustment_label"] = f"Nächster Slot ab {fb_time}"
        print(json.dumps({
            "event":      "fallback_label_applied",
            "venue_id":   result["venue_id"],
            "platform":   result["platform"],
            "primary":    result["availability_status"],
            "next_slot":  fb_time,
        }))

    # Strip not_checked venues — frontend only shows results that were actually scraped.
    # On load-more calls also strip non-eTennis (Eversports already in first response).
    if et_offset > 0:
        results = [r for r in results
                   if r["platform"] == "eTennis"
                   and r.get("availability_status") != "not_checked"]
    else:
        results = [r for r in results if r.get("availability_status") != "not_checked"]

    availability_pending = any(r["availability_status"] == "pending" for r in results)
    response_ms = round((time_monotonic() - t0) * 1000)
    print(json.dumps({
        "event":       "search_done",
        "results":     len(results),
        "pending":     availability_pending,
        "has_more":    has_more,
        "response_ms": response_ms,
    }))
    track_search_completed(
        radius=radius,
        court_type=court_type,
        results_count=len(results),
        response_ms=response_ms,
    )

    results.sort(key=lambda v: v.get("distance_km") or float("inf"))

    response = {
        "ok":                   True,
        "results":              results,
        "date":                 dt.strftime("%Y-%m-%d"),
        "time":                 dt.strftime("%H:%M"),
        "availability_pending": availability_pending,
        "has_more":             has_more,
        "weather":              search_weather,
    }
    if date_bucket == "far_future":
        response["booking_window_notice"] = _BOOKING_WINDOW_NOTICE

    # Store in response cache. Pending responses use a shorter TTL so clients
    # can poll for real statuses once eTennis scraping completes.
    search_ttl = _SEARCH_CACHE_TTL_PENDING if availability_pending else _SEARCH_CACHE_TTL_COMPLETE
    with _SEARCH_LOCK:
        if len(_SEARCH_CACHE) > 100:
            _purge_search_cache()
        _SEARCH_CACHE[cache_key] = (response, time_monotonic(), search_ttl)

    return response


class BookingClickBody(BaseModel):
    venue_id: str
    platform: str


@app.post("/api/booking-click")
async def booking_click(body: BookingClickBody):
    """Record booking intent. Frontend fires-and-forgets; opens the booking URL itself."""
    track_booking_clicked(venue_id=body.venue_id, platform=body.platform)
    return {"ok": True}


@app.get("/api/weather")
def weather_endpoint(
    lat:  float = Query(),
    lon:  float = Query(),
    date: str | None = Query(default=None),
    time: str | None = Query(default=None),
):
    dt, parse_error = _parse_datetime(date, time)
    if parse_error:
        return JSONResponse(status_code=400, content={"error": parse_error})

    async def _get():
        async with httpx.AsyncClient() as client:
            return await get_weather_for_hour(client, lat, lon, dt)

    weather = _run_async(_get())
    if weather is None:
        return JSONResponse(status_code=502, content={"error": "weather_unavailable"})
    return weather


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
