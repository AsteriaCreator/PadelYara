import asyncio
import copy
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from time import monotonic as time_monotonic
from typing import TypedDict
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import analytics
from analytics import (
    track_booking_clicked,
    track_pageview,
    track_scraper_timeout,
    track_search_completed,
    track_search_failed,
)
from etennis_checker import DEFAULT_FALLBACK_MINUTES as ET_DEFAULT_FALLBACK
import eversports_prices
from availability import parse_durations, match_durations, SELECTABLE_DURATIONS
from etennis_checker import check_etennis_venues
from etennis_checker import get_cached_entries as get_etennis_entries
from etennis_checker import get_cached_statuses as get_etennis_cached
from tennis04_checker import check_tennis04_venues
from tennis04_checker import get_cached_entries as get_tennis04_entries
from tennis04_checker import get_cached_statuses as get_tennis04_cached
from eversports_service import check_eversports_slot
from distance import filter_by_radius
from venues_mongo import load_venues
import opening_hours
from weather import get_weather_for_hour
import state

router = APIRouter()

VIENNA_TZ = ZoneInfo("Europe/Vienna")

# Eversports venues can have 30-min or 60-min slots depending on the court
# (e.g. Traiskirchen Court 3 has 30-min slots), so check both offsets.
EV_DEFAULT_FALLBACK: list[int] = [30, 60]

# Dedicated event loop for Eversports' Playwright (Chromium) calls.
# Eversports launches a browser subprocess. On Windows, `uvicorn --reload` runs the
# app under a SelectorEventLoop (uvicorn forces this for its subprocess reloader), and
# a SelectorEventLoop cannot spawn subprocesses -> NotImplementedError. On Linux
# (Railway/production) the main loop spawns subprocesses fine, so we keep using it.
# Prices use curl_cffi (no subprocess), so they stay on the main loop regardless.
_ev_loop: asyncio.AbstractEventLoop | None = None
_ev_loop_lock = threading.Lock()


def _get_ev_loop() -> asyncio.AbstractEventLoop:
    """Loop to run Eversports Playwright coroutines on.

    Linux/prod: the main loop (unchanged). Windows: a dedicated ProactorEventLoop in
    its own thread, since uvicorn's --reload main loop is a SelectorEventLoop that
    can't launch the Chromium subprocess. All Eversports browser work shares this one
    loop, so the lazily-created `_cf_lock` stays bound to a single loop.
    """
    global _ev_loop
    if sys.platform != "win32":
        return state._main_loop
    if _ev_loop is None:
        with _ev_loop_lock:
            if _ev_loop is None:
                loop = asyncio.ProactorEventLoop()
                threading.Thread(
                    target=loop.run_forever, daemon=True, name="eversports-pw-loop"
                ).start()
                _ev_loop = loop
    return _ev_loop


class VenueResult(TypedDict):
    venue_id:            str
    name:                str
    court_type:          str
    platform:            str
    booking_url:         str
    distance_km:         float | None
    availability_status: str
    error:               str | None


_RUNNING: set[str] = set()   # tracks in-flight background checks
_RUNNING_LOCK = threading.Lock()

# Statuses that mean a venue has not yet been checked and needs a background
# check. Defined as a named constant so gaps can't silently creep in when new
# status values are introduced.
_EV_UNCHECKED  = {None, "pending", "unknown"}
_EV_BUSY_TTL   = 60   # s — busy can flip free if a booking is cancelled; re-check sooner
_EV_FAILED_TTL = 30   # s — cache platform_check_required briefly so it surfaces immediately
                      #      instead of retrying as pending forever; retried after 30 s

# ── Scraper / task timeouts ───────────────────────────────────────────────────
_EV_COROUTINE_TIMEOUT  = 18   # s — slot-check coroutine via thread-safe future (non-Playwright path)
_EV_PLAYWRIGHT_TIMEOUT = 30   # s — full Playwright Eversports scrape (cold browser can be slow)
_GEO_IP_TIMEOUT        = 3.0  # s — IP geolocation HTTP call (fire-and-forget; failure is silent)
_WEATHER_TIMEOUT       = 2.0  # s — weather task; capped low so it never delays search response

# ── Response cache (TTL) ─────────────────────────────────────────────────────
# key → (response_dict, stored_at_monotonic, ttl_seconds)
_SEARCH_CACHE: dict[str, tuple[dict, float, float]] = {}
_SEARCH_LOCK = threading.Lock()
_SEARCH_CACHE_TTL_COMPLETE = 45   # s — no pending scrapes; safe to serve for 45 s
_SEARCH_CACHE_TTL_PENDING   = 3   # s — short so polls every ~3 s see fresh EV results

# ── Eversports venue-level result cache ──────────────────────────────────────
# key → (status_string, stored_at_monotonic, ttl)
_EV_RESULT_CACHE: dict[str, tuple[str, float]] = {}
_EV_RESULT_LOCK = threading.Lock()
_EV_RESULT_TTL = 300  # s — match eTennis _TTL

# Parallel cache of the BASE (single-slot) status' free_durations, same key/lock.
_EV_FREE_CACHE: dict[str, tuple[list[int], float]] = {}

_INDOOR_TYPES  = {"indoor", "indoor+outdoor"}
_OUTDOOR_TYPES = {"outdoor", "indoor+outdoor"}

ET_BATCH = 5  # eTennis venues checked per request (backend resource limit)

_MAX_FUTURE_DAYS = 42   # absolute ceiling: beyond this → 400
_FAR_FUTURE_DAYS = 14   # soft threshold: beyond this → allowed but with notice
_BOOKING_WINDOW_NOTICE = (
    "Viele Anbieter erlauben Buchungen nur bis 14 Tage im Voraus. "
    "Angezeigte Ergebnisse können daher unvollständig sein."
)

_BOT_UA_MARKERS = ("headlesschrome", "headless", "playwright", "puppeteer", "selenium", "bot/", "crawler", "spider")

# ── IP → country (DSGVO-safe: only country name stored, never the IP) ─────────
_geo_cache: dict[str, str | None] = {}  # simple in-process cache, reset on restart


def _run_key(platform: str, dt: datetime) -> str:
    return f"{platform}*{dt.strftime('%Y-%m-%d')}*{dt.hour:02d}"


def _apply_duration_filter(result: dict, base_status: str, free_durs: list[int] | None, wanted: list[int] | None) -> None:
    """
    Core duration-filter logic shared by every availability path.
    Writes availability_status (and matched_duration_h / available_durations_h) onto result.
    Callers may set additional fields (price, fallback ts, etc.) after this call.
    """
    if wanted and free_durs is not None and base_status in ("free", "busy"):
        matched = match_durations(free_durs, wanted)
        if matched:
            result["availability_status"] = "free"
            result["matched_duration_h"] = max(matched) / 60
            return
        # Requested length not free. Other selectable lengths that ARE free here
        # get an "other_duration" badge (amber "Nur 1 Std / 2 Std frei") instead
        # of a misleading "Belegt" — the court itself is available, just not for
        # the requested block length.
        other = [d for d in SELECTABLE_DURATIONS if d in set(free_durs)]
        if other:
            result["availability_status"] = "other_duration"
            result["available_durations_h"] = [d / 60 for d in other]
        else:
            result["availability_status"] = "busy"
    else:
        result["availability_status"] = base_status


def _apply_cached_entry(result: dict, status: str, entry: dict, wanted: list[int] | None = None) -> None:
    """
    Write a cached availability status plus its optional detail fields onto a
    result. Shared by the eTennis and tennis04 phases.

    Duration awareness: when `wanted` is given AND the checker reported
    `free_durations`, venues are checked for continuous-block availability.
    The fallback points at the next time a requested duration actually opens up.
    Without a duration filter, the legacy single-slot behaviour applies.
    """
    free_durs = entry.get("free_durations")
    duration_filter_active = bool(wanted and free_durs is not None and status in ("free", "busy"))
    _apply_duration_filter(result, status, free_durs, wanted)
    shown = result["availability_status"]
    if duration_filter_active and shown == "busy":
        # Duration-aware fallback: point at the next time a requested length opens.
        wanted_set = set(wanted)  # type: ignore[arg-type]
        for fb in entry.get("fallback_durations", []):
            if wanted_set & set(fb.get("durations", [])):
                result["next_available_time"] = fb["ts"]
                break
    elif not duration_filter_active and shown != "free":
        # Legacy single-slot fallback: next time any slot is free.
        nft = entry.get("next_free_ts")
        if nft is not None:
            result["next_available_time"] = nft
    price = entry.get("price_eur")
    if price is not None:
        result["price_eur"] = price
    dur = entry.get("slot_duration_h")
    if dur is not None:
        result["slot_duration_h"] = dur


def _launch_bg_check(platform: str, dt: datetime, to_fetch: list[dict], check_fn) -> None:
    """
    Start one _RUNNING-deduplicated background thread running check_fn(to_fetch, dt).
    No-op when to_fetch is empty or an identical run is already in flight. Shared
    by the eTennis and tennis04 phases; log event names derive from the platform.
    """
    if not to_fetch:
        return
    key = _run_key(platform, dt)
    venue_ids = [v["id"] for v in to_fetch]
    with _RUNNING_LOCK:
        should_start = key not in _RUNNING
        if should_start:
            _RUNNING.add(key)
    if not should_start:
        print(json.dumps({"event": f"{platform.lower()}_bg_deduplicated", "key": key, "venues": venue_ids}))
        return
    print(json.dumps({"event": f"{platform.lower()}_bg_start", "key": key, "venues": venue_ids}))

    def _bg(vv=to_fetch, d=dt, k=key):
        try:
            check_fn(vv, d)
        finally:
            with _RUNNING_LOCK:
                _RUNNING.discard(k)

    threading.Thread(target=_bg, daemon=True).start()


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


async def _filter_venues(
    court_type: str | None,
    lat: float | None = None,
    lon: float | None = None,
    radius: float | None = None,
) -> list[dict]:
    result = await load_venues()

    if lat is not None and lon is not None and radius is not None:
        result = filter_by_radius(result, lat, lon, radius)

    if court_type and court_type != "both" and court_type != "all":
        allowed = _INDOOR_TYPES if court_type == "indoor" else _OUTDOOR_TYPES
        result = [v for v in result if v["court_type"] in allowed]

    return result


def _build_venue_result(venue: dict) -> VenueResult:
    return {
        "venue_id":            venue["id"],
        "name":                venue["name"],
        "operator":            venue.get("operator", ""),
        "court_type":          venue["court_type"],
        "platform":            venue["platform"],
        "booking_url":         venue["booking_url"],
        "public_url":          venue.get("public_url", ""),
        "distance_km":         venue.get("distance_km"),
        "availability_status": "unknown",
        "error":               None,
    }


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
    durations: list[int] | None = None,
) -> str:
    dur_key = ",".join(str(d) for d in durations) if durations else ""
    return f"{date}|{time_str}|{lat}|{lon}|{radius}|{court_type}|{et_offset}|{dur_key}"


def _ev_result_key(venue_id: str, date_str: str, time_hhmm: str) -> str:
    return f"{venue_id}*{date_str}*{time_hhmm}"


def _purge_ev_result_cache() -> None:
    """Evict expired entries. Must be called with _EV_RESULT_LOCK held."""
    now_t = time_monotonic()
    expired = [k for k, (_, ts, ttl) in _EV_RESULT_CACHE.items() if now_t - ts >= ttl]
    for k in expired:
        del _EV_RESULT_CACHE[k]
        _EV_FREE_CACHE.pop(k, None)


def _apply_ev_duration(result: dict, base_status: str, free_durs: list[int] | None, wanted: list[int] | None) -> None:
    """Apply the user's duration filter to an Eversports result (delegates to shared helper)."""
    _apply_duration_filter(result, base_status, free_durs, wanted)


def _purge_search_cache() -> None:
    """Evict expired entries. Must be called with _SEARCH_LOCK held."""
    now_t = time_monotonic()
    expired = [k for k, (_, ts, ttl) in _SEARCH_CACHE.items() if now_t - ts >= ttl]
    for k in expired:
        del _SEARCH_CACHE[k]


def _call_eversports_service(
    fid: int, cids: list[int], date_str: str, time_hhmm: str,
    venue_id: str = "unknown", booking_url: str = "",
) -> str:
    """Call the Eversports checker directly (in-process). Falls back to platform_check_required."""
    _has_proxy = bool(os.environ.get("EVERSPORTS_SLOT_PROXY"))
    if not os.environ.get("RAILWAY_ENVIRONMENT") and not _has_proxy:
        return "platform_check_required"
    t0 = time.monotonic()
    time_colon = f"{time_hhmm[:2]}:{time_hhmm[2:]}"  # "1800" -> "18:00"

    def _log(status: str, error: str | None = None) -> None:
        entry: dict = {
            "event":       "eversports_check_result",
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
        coro = check_eversports_slot(
            facility_id=fid,
            court_ids=",".join(str(c) for c in cids),
            date=date_str,
            time=time_colon,
            venue_url=booking_url,
            venue_id=venue_id,
        )
        result = asyncio.run_coroutine_threadsafe(coro, _get_ev_loop()).result(timeout=_EV_COROUTINE_TIMEOUT)
        status = result.get("status", "platform_check_required")
        slots_count = result.get("slots_count")
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
    except Exception as exc:
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        track_scraper_timeout(venue_id=venue_id, platform="Eversports", timeout_ms=elapsed_ms)
        _log("platform_check_required", error=f"{type(exc).__name__}: {exc}")
        print(f"[Eversports] direct call failed: {type(exc).__name__}: {exc}")
        return "platform_check_required"


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
            status, ts, ttl = entry
            age = now_t - ts
            if age < ttl:
                print(json.dumps({
                    "event":    "ev_cache_hit",
                    "venue_id": venue_id,
                    "status":   status,
                    "age_s":    round(age, 1),
                }))
                return status
            del _EV_RESULT_CACHE[key]
    status = _call_eversports_service(fid, cids, date_str, time_hhmm, venue_id, booking_url)
    if status in ("free", "no_slot", "busy", "platform_check_required"):
        ttl = (_EV_BUSY_TTL   if status == "busy"
               else _EV_FAILED_TTL if status == "platform_check_required"
               else _EV_RESULT_TTL)
        with _EV_RESULT_LOCK:
            if len(_EV_RESULT_CACHE) > 500:
                _purge_ev_result_cache()
            _EV_RESULT_CACHE[key] = (status, time_monotonic(), ttl)
    return status


def _device_type(user_agent: str) -> str:
    ua = user_agent.lower()
    if any(k in ua for k in ("iphone", "android", "mobile", "blackberry", "windows phone")):
        return "mobile"
    if any(k in ua for k in ("ipad", "tablet")):
        return "tablet"
    return "desktop"


def _client_ip(request: Request) -> str | None:
    """Best-effort real client IP from X-Forwarded-For (Railway sets this)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


async def _get_country(ip: str | None) -> str | None:
    """Resolve an IP to a country name via ip-api.com (free, server-side only).
    Returns None for private/loopback IPs and on any error. Result is cached."""
    if not ip:
        return None
    if ip in ("127.0.0.1", "::1", "localhost") or ip.startswith("192.168.") or ip.startswith("10."):
        return None
    if ip in _geo_cache:
        return _geo_cache[ip]
    try:
        async with httpx.AsyncClient(timeout=_GEO_IP_TIMEOUT) as client:
            r = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country"},
            )
            data = r.json()
            country = data.get("country") if data.get("status") == "success" else None
    except Exception:
        country = None
    if len(_geo_cache) < 5000:  # cap memory; restart clears it anyway
        _geo_cache[ip] = country
    return country


@router.get("/health")
async def health():
    """Liveness probe — Railway and uptime monitors call this to confirm the process is up."""
    return {"status": "ok"}


@router.get("/api/search")
async def search(
    date:            str | None   = Query(default=None),
    time:            str | None   = Query(default=None),
    court_type:      str | None   = Query(default=None),
    lat:             float | None = Query(default=None),
    lon:             float | None = Query(default=None),
    radius:          float | None = Query(default=None),
    et_offset:       int          = Query(default=0),
    search_location: str | None   = Query(default=None),
    durations:       str | None   = Query(default=None),
    request:         Request      = None,
):
    """Search for padel court availability. Fans out to Eversports, eTennis, and Tennis04
    scrapers in parallel. Returns immediate results plus an availability_pending flag when
    slow scrapers are still running (frontend polls until settled)."""
    t0 = time_monotonic()
    ua = request.headers.get("user-agent", "").lower() if request else ""
    _is_bot = any(m in ua for m in _BOT_UA_MARKERS)
    session_id:  str | None = (request.headers.get("X-Session-Id") or None) if request else None
    device_type: str        = _device_type(request.headers.get("user-agent", "")) if request else "desktop"

    # ── Date validation — runs before cache, inflight, or any scraper work ────
    date_bucket, date_error = _validate_date(date)
    if date_error is not None:
        return date_error

    # ── Phase 0: response cache ───────────────────────────────────────────────
    wanted_durations = parse_durations(durations)
    cache_key = _search_cache_key(date, time, lat, lon, radius, court_type, et_offset, wanted_durations)

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
        if not _is_bot:
            track_search_failed(reason="invalid_datetime", court_type=court_type, session_id=session_id)
        return JSONResponse(status_code=400, content={"ok": False, "error": parse_error})

    venues = await _filter_venues(court_type, lat, lon, radius)
    if not venues:
        return {"ok": True, "results": [], "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M"), "availability_pending": False, "has_more": False}

    results = [_build_venue_result(v) for v in venues]

    if not results:
        return {"ok": True, "results": [], "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M"), "availability_pending": False, "has_more": False}

    # Start weather fetch concurrently — don't block scraper setup behind it.
    _weather_client = httpx.AsyncClient()
    _weather_task = (
        asyncio.create_task(get_weather_for_hour(_weather_client, lat, lon, dt))
        if lat is not None and lon is not None else None
    )

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
        cached  = get_etennis_cached(etennis_venues, dt)
        entries = get_etennis_entries(etennis_venues, dt)
        print(json.dumps({
            "event":      "etennis_cache_check",
            "hits":       len(cached),
            "total":      len(etennis_venues),
            "statuses":   dict(cached),
        }))
        for result in results:
            vid = result["venue_id"]
            if vid in cached:
                _apply_cached_entry(result, cached[vid], entries.get(vid, {}), wanted_durations)
            elif result["platform"] == "eTennis":
                result["availability_status"] = "pending" if vid in scrape_ids else "not_checked"
        to_fetch = [v for v in etennis_venues
                    if v["id"] not in cached and v["id"] in scrape_ids]
        _launch_bg_check("eTennis", dt, to_fetch, check_etennis_venues)

    # ── Phase 2.5: tennis04 ──
    if et_offset == 0:
        t04_venues = [v for v in venues if v["platform"] == "tennis04"]
        if t04_venues:
            t04_map     = {v["id"]: v for v in t04_venues}
            cached_t04  = get_tennis04_cached(t04_venues, dt)
            entries_t04 = get_tennis04_entries(t04_venues, dt)
            print(json.dumps({
                "event":    "tennis04_cache_check",
                "hits":     len(cached_t04),
                "total":    len(t04_venues),
                "statuses": dict(cached_t04),
            }))
            for result in results:
                if result["platform"] != "tennis04":
                    continue
                vid   = result["venue_id"]
                venue = t04_map.get(vid)
                if venue is None or not venue.get("tennis04_club_id"):
                    issues = (venue.get("issues", "") if venue else "")
                    result["availability_status"] = (
                        "phone_only" if issues == "phone_booking_only" else "unknown"
                    )
                    continue
                if vid in cached_t04:
                    _apply_cached_entry(result, cached_t04[vid], entries_t04.get(vid, {}), wanted_durations)
                else:
                    result["availability_status"] = "pending"
            to_fetch_t04 = [v for v in t04_venues
                            if v["id"] not in cached_t04 and v.get("tennis04_club_id")]
            _launch_bg_check("tennis04", dt, to_fetch_t04, check_tennis04_venues)

    # ── Phase 3: Eversports ──
    if et_offset == 0:
        ev_venue_map = {v["id"]: v for v in venues}
        time_hhmm    = dt.strftime("%H%M")
        date_str_ev  = dt.strftime("%Y-%m-%d")

        def _check_ev_sync(result: dict) -> None:
            """Run one Eversports venue check from a background thread."""
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
            ev_open_min, ev_close_min = opening_hours.day_window_min(
                venue.get("opening_hours") if venue else None, dt.weekday()
            )

            def _run(time_str: str, date_str: str) -> str:
                coro = check_eversports_slot(
                    facility_id=fid,
                    court_ids=",".join(str(c) for c in cids),
                    date=date_str,
                    time=time_str,
                    venue_url=booking_url,
                    venue_id=result["venue_id"],
                    open_min=ev_open_min,
                    close_min=ev_close_min,
                )
                try:
                    ev_result = asyncio.run_coroutine_threadsafe(coro, _get_ev_loop()).result(timeout=_EV_PLAYWRIGHT_TIMEOUT)
                    return ev_result
                except Exception as exc:
                    print(json.dumps({"event": "eversports_thread_error", "venue_id": result["venue_id"], "error": str(exc)}))
                    return {"status": "platform_check_required", "slots_count": 0}

            ev_result = _run(f"{time_hhmm[:2]}:{time_hhmm[2:]}", date_str_ev)
            base_status = ev_result.get("status", "platform_check_required")
            free_durs   = ev_result.get("free_durations")
            if base_status in ("free", "no_slot", "busy", "platform_check_required"):
                ttl = (_EV_BUSY_TTL   if base_status == "busy"
                       else _EV_FAILED_TTL if base_status == "platform_check_required"
                       else _EV_RESULT_TTL)
                with _EV_RESULT_LOCK:
                    if len(_EV_RESULT_CACHE) > 500:
                        _purge_ev_result_cache()
                    key = _ev_result_key(result["venue_id"], date_str_ev, time_hhmm)
                    _EV_RESULT_CACHE[key] = (base_status, time_monotonic(), ttl)
                    if free_durs is not None:
                        _EV_FREE_CACHE[key] = (free_durs, time_monotonic())
            _apply_ev_duration(result, base_status, free_durs, wanted_durations)
            live_price = ev_result.get("price_eur")
            if live_price is None:
                live_price = eversports_prices.get_price(result["venue_id"], date_str_ev, time_hhmm)
            if live_price is not None:
                result["price_eur"] = live_price
            if ev_result.get("slot_duration_h") is not None:
                result["slot_duration_h"] = ev_result["slot_duration_h"]
            if result.get("availability_status") == "busy":
                fb_offsets = venue.get("slot_fallback_minutes") or EV_DEFAULT_FALLBACK
                for offset_min in fb_offsets:
                    dt_fb     = dt + timedelta(minutes=offset_min)
                    fb_result = _run(dt_fb.strftime("%H:%M"), dt_fb.strftime("%Y-%m-%d"))
                    fb_status = fb_result.get("status", "platform_check_required")
                    fb_free   = fb_result.get("free_durations")
                    fits = fb_free is not None and bool(match_durations(fb_free, wanted_durations))
                    print(json.dumps({
                        "event":      "eversports_fallback_result",
                        "venue_id":   result["venue_id"],
                        "offset_min": offset_min,
                        "primary":    base_status,
                        "fallback":   fb_status,
                        "fits":       fits,
                    }))
                    if fits:
                        result["next_available_time"] = int(
                            dt_fb.replace(tzinfo=VIENNA_TZ).timestamp()
                        )
                        break
                    if fb_status not in ("busy", "no_slot", "free"):
                        break

        ev_results = [r for r in results if r["platform"] == "Eversports"]
        if ev_results:
            if not eversports_prices._refresh_running:
                asyncio.create_task(eversports_prices.refresh_prices_async(await load_venues()))
            now_t = time_monotonic()
            with _EV_RESULT_LOCK:
                for r in ev_results:
                    key = _ev_result_key(r["venue_id"], date_str_ev, time_hhmm)
                    entry = _EV_RESULT_CACHE.get(key)
                    if entry is not None:
                        status, ts, ttl = entry
                        if now_t - ts < ttl:
                            free_entry = _EV_FREE_CACHE.get(key)
                            free_durs  = free_entry[0] if free_entry else None
                            _apply_ev_duration(r, status, free_durs, wanted_durations)
                            cached_price = (
                                eversports_prices.get_price(r["venue_id"], date_str_ev, time_hhmm)
                                or eversports_prices.get_any_price(r["venue_id"], date_str_ev)
                            )
                            if cached_price is not None:
                                r["price_eur"] = cached_price

            ev_pending = []
            for r in ev_results:
                if r.get("availability_status") in _EV_UNCHECKED:
                    r["availability_status"] = "pending"
                    ev_pending.append(r)

            if not ev_pending and ev_results:
                print(json.dumps({
                    "event":    "eversports_bg_skipped",
                    "reason":   "all_cached",
                    "statuses": [r.get("availability_status") for r in ev_results],
                }))

            if ev_pending:
                ev_key = _run_key("Eversports", dt)
                with _RUNNING_LOCK:
                    ev_should_start = ev_key not in _RUNNING
                    if ev_should_start:
                        _RUNNING.add(ev_key)
                if ev_should_start:
                    print(json.dumps({
                        "event":  "eversports_bg_start",
                        "key":    ev_key,
                        "venues": [r["venue_id"] for r in ev_pending],
                    }))
                    def _ev_bg(pending=ev_pending, k=ev_key):
                        try:
                            with ThreadPoolExecutor(max_workers=min(len(pending), 6)) as pool:
                                futures = [pool.submit(_check_ev_sync, r) for r in pending]
                                for f in as_completed(futures):
                                    try:
                                        f.result()
                                    except Exception as exc:
                                        print(json.dumps({"event": "eversports_thread_error", "error": str(exc)}))
                        finally:
                            with _RUNNING_LOCK:
                                _RUNNING.discard(k)
                    threading.Thread(target=_ev_bg, daemon=True).start()
                else:
                    print(json.dumps({
                        "event":  "eversports_bg_deduplicated",
                        "key":    ev_key,
                        "venues": [r["venue_id"] for r in ev_pending],
                    }))

    # ── Generic fallback label pass ──
    for result in results:
        nft = result.get("next_available_time")
        if nft is None:
            continue
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
    if not _is_bot:
        track_search_completed(
            radius=radius,
            court_type=court_type,
            results_count=len(results),
            response_ms=response_ms,
            session_id=session_id,
            search_location=search_location,
            device_type=device_type,
        )

    results.sort(key=lambda v: v.get("distance_km") or float("inf"))

    search_weather = None
    if _weather_task is not None:
        try:
            search_weather = await asyncio.wait_for(_weather_task, timeout=_WEATHER_TIMEOUT)
        except Exception:
            pass
        finally:
            await _weather_client.aclose()

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

    search_ttl = _SEARCH_CACHE_TTL_PENDING if availability_pending else _SEARCH_CACHE_TTL_COMPLETE
    with _SEARCH_LOCK:
        if len(_SEARCH_CACHE) > 100:
            _purge_search_cache()
        _SEARCH_CACHE[cache_key] = (copy.deepcopy(response), time_monotonic(), search_ttl)

    return response


class BookingClickBody(BaseModel):
    venue_id:   str
    platform:   str
    session_id: str | None = None


@router.post("/api/booking-click")
async def booking_click(body: BookingClickBody):
    """Record booking intent. Frontend fires-and-forgets; opens the booking URL itself."""
    track_booking_clicked(venue_id=body.venue_id, platform=body.platform, session_id=body.session_id)
    return {"ok": True}


class PageviewBody(BaseModel):
    path:          str
    referrer_host: str | None = None
    session_id:    str | None = None


@router.post("/api/pageview")
async def pageview(body: PageviewBody, request: Request, background_tasks: BackgroundTasks):
    """Record a first-party, cookieless page view. Fire-and-forget from the frontend."""
    ua = request.headers.get("user-agent", "").lower()
    if any(m in ua for m in _BOT_UA_MARKERS):
        return {"ok": True}

    device_type = _device_type(request.headers.get("user-agent", ""))
    ip = _client_ip(request)

    async def _track():
        country = await _get_country(ip)
        track_pageview(
            path=body.path,
            referrer_host=body.referrer_host,
            device_type=device_type,
            country=country,
            session_id=body.session_id,
        )

    background_tasks.add_task(_track)
    return {"ok": True}
