import asyncio
import copy
import json
import os
import secrets
import sys
from pathlib import Path

# Load .env from the Backend directory (local dev only; production uses real env vars)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from time import monotonic as time_monotonic
from typing import TypedDict
from zoneinfo import ZoneInfo

import httpx
import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

import sentry_sdk
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    traces_sample_rate=0.1,
    environment=os.environ.get("RAILWAY_ENVIRONMENT", "development"),
)

import analytics
from analytics import (
    track_booking_clicked,
    track_pageview,
    track_scraper_timeout,
    track_search_completed,
    track_search_failed,
)
import tournaments_mongo
from padel_austria_scraper import scrape_all as scrape_padel_austria
from padel_austria_player import analyze_player
from yara_urteil_prompt import generate_urteil, UrteilUnavailable, DISCLAIMER
import urteil_mongo
from etennis_checker import DEFAULT_FALLBACK_MINUTES as ET_DEFAULT_FALLBACK
import eversports_prices
from availability import parse_durations, match_durations

# Eversports venues can have 30-min or 60-min slots depending on the court
# (e.g. Traiskirchen Court 3 has 30-min slots), so check both offsets.
EV_DEFAULT_FALLBACK: list[int] = [30, 60]
from etennis_checker import check_etennis_venues
from etennis_checker import get_cached_entries as get_etennis_entries
from etennis_checker import get_cached_statuses as get_etennis_cached
from tennis04_checker import check_tennis04_venues
from tennis04_checker import get_cached_entries as get_tennis04_entries
from tennis04_checker import get_cached_statuses as get_tennis04_cached
from eversports_service import check_eversports_slot
from distance import filter_by_radius
from venues_mongo import load_venues, get_venue_detail
from weather import WeatherResult, get_weather_for_hour


class VenueResult(TypedDict):
    venue_id:            str
    name:                str
    court_type:          str
    platform:            str
    booking_url:         str
    distance_km:         float | None
    availability_status: str
    error:               str | None


def _call_eversports_service(
    fid: int, cids: list[int], date_str: str, time_hhmm: str,
    venue_id: str = "unknown", booking_url: str = "",
) -> str:
    """Call the Eversports checker directly (in-process). Falls back to platform_check_required."""
    # Skip locally unless a slot proxy is configured (proxy makes the check work
    # from any IP, so RAILWAY_ENVIRONMENT is no longer required in that case).
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
        # Must use run_coroutine_threadsafe (not _run_async) so that asyncio
        # primitives in eversports_service (e.g. _cf_lock) share the same
        # event loop they were created on, avoiding "bound to a different loop".
        coro = check_eversports_slot(
            facility_id=fid,
            court_ids=",".join(str(c) for c in cids),
            date=date_str,
            time=time_colon,
            venue_url=booking_url,
            venue_id=venue_id,
        )
        result = asyncio.run_coroutine_threadsafe(coro, _get_ev_loop()).result(timeout=18)
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



_main_loop: asyncio.AbstractEventLoop | None = None

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
        return _main_loop
    if _ev_loop is None:
        with _ev_loop_lock:
            if _ev_loop is None:
                loop = asyncio.ProactorEventLoop()
                threading.Thread(
                    target=loop.run_forever, daemon=True, name="eversports-pw-loop"
                ).start()
                _ev_loop = loop
    return _ev_loop


def _run_tournament_scrape(is_seed: bool = False) -> None:
    """Blocking scrape + upsert, intended to run in a thread.
    Upsert runs on the main event loop via run_coroutine_threadsafe to avoid
    motor being called from a different loop than the one it was created on.

    `is_seed` is True only for the initial import into an empty collection, so
    first_seen_at gets backdated instead of flagging the whole catalogue as NEU.
    """
    print("[tournaments] Starting daily scrape...")
    tournaments = scrape_padel_austria()
    if not tournaments:
        print("[tournaments] Scrape returned 0 tournaments — skipping upsert.")
        return
    if _main_loop is None:
        print("[tournaments] Main event loop not ready — skipping upsert.")
        return
    future = asyncio.run_coroutine_threadsafe(
        tournaments_mongo.upsert_tournaments(tournaments, is_seed=is_seed), _main_loop
    )
    try:
        stats = future.result(timeout=120)
        print(f"[tournaments] Upsert done: {stats}")
    except Exception as exc:
        print(f"[tournaments] Upsert failed: {exc}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _main_loop, VENUES, _ev_ids
    _main_loop = asyncio.get_running_loop()
    await analytics.lifespan_startup()
    await tournaments_mongo.ensure_indexes()
    eversports_prices.init_mongo(os.getenv("MONGODB_URI", ""))
    await eversports_prices.load_cache_from_mongo()
    VENUES = await load_venues()
    _ev_ids = [(v["id"], v["eversports_facility_id"], v["eversports_court_ids"])
               for v in VENUES if v.get("eversports_facility_id")]
    print(f"[startup] Loaded {len(VENUES)} venues from MongoDB")
    print(f"[startup] Eversports venues with facility IDs: {_ev_ids}")

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
    scheduler.start()
    print("[tournaments] Daily scraper scheduled at 06:00 Vienna time.")

    # Kick off a background price scrape at startup so stale venues populate
    # immediately after deploy — don't wait for the first user search.
    asyncio.create_task(eversports_prices.refresh_prices_async(VENUES))
    print("[startup] Eversports price refresh started in background.")

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
# Also allow Vercel preview deployments for this project (neo-padel-checker-*)
_VERCEL_PREVIEW_PATTERN = r"https://neo-padel-checker-[a-z0-9-]+\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=_VERCEL_PREVIEW_PATTERN,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Session-Id", "X-Admin-Token"],
)

VENUES: list[dict] = []
_ev_ids: list[tuple] = []
DEFAULT_VENUE_ID = "padelzone-traiskirchen"
VIENNA_TZ = ZoneInfo("Europe/Vienna")

_RUNNING: set[str] = set()   # tracks in-flight background checks
_RUNNING_LOCK = threading.Lock()

# Statuses that mean a venue has not yet been checked and needs a background
# check. Defined as a named constant so gaps can't silently creep in when new
# status values are introduced.
_EV_UNCHECKED  = {None, "pending", "unknown"}
_EV_BUSY_TTL   = 60   # s — busy can flip free if a booking is cancelled; re-check sooner
_EV_FAILED_TTL = 30   # s — cache platform_check_required briefly so it surfaces immediately
                      #      instead of retrying as pending forever; retried after 30 s

# ── Response cache (TTL) ─────────────────────────────────────────────────────
# key → (response_dict, stored_at_monotonic, ttl_seconds)
# No inflight coordination: the pending-first design means the FIRST response
# returns quickly (eTennis = pending, Eversports = real status). Inflight
# coordination was removed because it blocked all polls behind the first
# request's full Eversports scan (up to 60 s per venue × 8 venues).
_SEARCH_CACHE: dict[str, tuple[dict, float, float]] = {}
_SEARCH_LOCK = threading.Lock()
_SEARCH_CACHE_TTL_COMPLETE = 45   # s — no pending scrapes; safe to serve for 45 s
_SEARCH_CACHE_TTL_PENDING   = 3   # s — short so polls every ~3 s see fresh EV results
                                  #     lets clients poll for real statuses quickly

# ── Eversports venue-level result cache ──────────────────────────────────────
# key → (status_string, stored_at_monotonic)
_EV_RESULT_CACHE: dict[str, tuple[str, float]] = {}
_EV_RESULT_LOCK = threading.Lock()
_EV_RESULT_TTL = 300  # s — match eTennis _TTL


def _run_key(platform: str, dt: datetime) -> str:
    return f"{platform}*{dt.strftime('%Y-%m-%d')}*{dt.hour:02d}"


def _apply_cached_entry(result: dict, status: str, entry: dict, wanted: list[int] | None = None) -> None:
    """
    Write a cached availability status plus its optional detail fields onto a
    result. Shared by the eTennis and tennis04 phases, whose checker modules
    expose the same cache-entry shape ({status, next_free_ts?, price_eur?,
    slot_duration_h?, free_durations?, fallback_durations?}).

    Duration awareness: when `wanted` (the durations the user selected, in
    minutes) is given AND the checker reported `free_durations`, a venue that is
    single-slot "free" but cannot host any requested duration continuously is
    downgraded to "busy", and the fallback points at the next time a requested
    duration actually opens up. Checkers that don't yet report free_durations
    (or requests without a duration filter) keep the legacy single-slot
    behaviour. next_available_time is only set for non-free statuses.
    """
    free_durs = entry.get("free_durations")
    if wanted and free_durs is not None and status in ("free", "busy"):
        matched = match_durations(free_durs, wanted)
        if matched:
            result["availability_status"] = "free"
            result["matched_duration_h"] = max(matched) / 60
        else:
            # The requested length doesn't fit at T — even if a single slot is
            # free. Point at the next offset whose free durations include one of
            # the requested lengths (duration-aware fallback).
            result["availability_status"] = "busy"
            wanted_set = set(wanted)
            for fb in entry.get("fallback_durations", []):
                if wanted_set & set(fb.get("durations", [])):
                    result["next_available_time"] = fb["ts"]
                    break
    else:
        result["availability_status"] = status
        if status != "free":
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


ET_BATCH = 5  # eTennis venues checked per request (backend resource limit)

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
    # Cache only structurally stable statuses:
    #   "free"    — a confirmed open slot; stable within the TTL window.
    #   "no_slot" — no slot starts at this exact time; structural, very stable.
    # Do NOT cache "busy" — a booked slot can be cancelled and become free
    # within the TTL window, which would cause stale "busy" results (regression).
    # Do NOT cache platform_check_required / failures — they prevent Railway retries.
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


# ── IP → country (DSGVO-safe: only country name stored, never the IP) ─────────

_geo_cache: dict[str, str | None] = {}  # simple in-process cache, reset on restart


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
        async with httpx.AsyncClient(timeout=3.0) as client:
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/search")
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
    # Cache key covers every dimension that affects results.
    # No inflight coordination: requests run independently. Cache hits return
    # immediately; misses proceed through the full pipeline. This preserves the
    # pending-first architecture where the first response is fast (eTennis
    # pending + Eversports real status) and polls pick up updated statuses.
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
    # Weather has a 2 s timeout so it never holds up the response.
    _weather_client = httpx.AsyncClient()
    _weather_task = (
        asyncio.create_task(get_weather_for_hour(_weather_client, lat, lon, dt))
        if lat is not None and lon is not None else None
    )

    # In radius mode paginate eTennis scraping so the backend's constrained
    # tier never launches more than ET_BATCH browsers at once.
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
                _apply_cached_entry(result, cached[vid], entries.get(vid, {}), wanted_durations)
            elif result["platform"] == "eTennis":
                result["availability_status"] = "pending" if vid in scrape_ids else "not_checked"
        to_fetch = [v for v in etennis_venues
                    if v["id"] not in cached and v["id"] in scrape_ids]
        _launch_bg_check("eTennis", dt, to_fetch, check_etennis_venues)

    # ── Phase 2.5: tennis04 — plain-HTTP public API, serve cached + bg-fetch ──
    #    Only on the initial load (et_offset == 0): like Eversports these venues
    #    appear in the first response and "Mehr Ergebnisse" calls reuse them.
    #    Checks run in a background thread (pending-first) so the response is fast.
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
                # Venues lacking tennis04 IDs can't be checked online.
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

    # ── Phase 3: Eversports — only on the initial load (et_offset == 0).
    #    On "Mehr Ergebnisse" calls the frontend already has Eversports results;
    #    skip the Railway round-trips to avoid redundant work.
    #    Checks run in a background thread (same pattern as eTennis) so the
    #    response returns immediately with "pending"; polls fill in the real status.
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

            def _run(time_str: str, date_str: str) -> str:
                coro = check_eversports_slot(
                    facility_id=fid,
                    court_ids=",".join(str(c) for c in cids),
                    date=date_str,
                    time=time_str,
                    venue_url=booking_url,
                    venue_id=result["venue_id"],
                )
                try:
                    ev_result = asyncio.run_coroutine_threadsafe(coro, _get_ev_loop()).result(timeout=30)
                    return ev_result
                except Exception as exc:
                    print(json.dumps({"event": "eversports_thread_error", "venue_id": result["venue_id"], "error": str(exc)}))
                    return {"status": "platform_check_required", "slots_count": 0}

            ev_result = _run(f"{time_hhmm[:2]}:{time_hhmm[2:]}", date_str_ev)
            status = ev_result.get("status", "platform_check_required")
            if status in ("free", "no_slot", "busy", "platform_check_required"):
                ttl = (_EV_BUSY_TTL   if status == "busy"
                       else _EV_FAILED_TTL if status == "platform_check_required"
                       else _EV_RESULT_TTL)
                with _EV_RESULT_LOCK:
                    if len(_EV_RESULT_CACHE) > 500:
                        _purge_ev_result_cache()
                    _EV_RESULT_CACHE[_ev_result_key(result["venue_id"], date_str_ev, time_hhmm)] = (status, time_monotonic(), ttl)
            result["availability_status"] = status
            live_price = ev_result.get("price_eur")
            if live_price is None:
                live_price = eversports_prices.get_price(result["venue_id"], date_str_ev, time_hhmm)
            if live_price is not None:
                result["price_eur"] = live_price
            if ev_result.get("slot_duration_h") is not None:
                result["slot_duration_h"] = ev_result["slot_duration_h"]
            if status in ("busy", "no_slot"):
                fb_offsets = venue.get("slot_fallback_minutes") or EV_DEFAULT_FALLBACK
                for offset_min in fb_offsets:
                    dt_fb     = dt + timedelta(minutes=offset_min)
                    fb_result = _run(dt_fb.strftime("%H:%M"), dt_fb.strftime("%Y-%m-%d"))
                    fb_status = fb_result.get("status", "platform_check_required")
                    print(json.dumps({
                        "event":      "eversports_fallback_result",
                        "venue_id":   result["venue_id"],
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
                        break

        ev_results = [r for r in results if r["platform"] == "Eversports"]
        if ev_results:
            # Price refresh is best-effort — only kick it off when no refresh is
            # already running. Crucially, _refresh_running does NOT gate the
            # availability check below: the two are independent. A slow price
            # refresh (up to ~6 min with staggering) must never block scrapers.
            if not eversports_prices._refresh_running:
                asyncio.create_task(eversports_prices.refresh_prices_async(await load_venues()))
            # Serve already-cached statuses immediately.
            now_t = time_monotonic()
            with _EV_RESULT_LOCK:
                for r in ev_results:
                    key = _ev_result_key(r["venue_id"], date_str_ev, time_hhmm)
                    entry = _EV_RESULT_CACHE.get(key)
                    if entry is not None:
                        status, ts, ttl = entry
                        if now_t - ts < ttl:
                            r["availability_status"] = status
                            cached_price = (
                                eversports_prices.get_price(r["venue_id"], date_str_ev, time_hhmm)
                                or eversports_prices.get_any_price(r["venue_id"], date_str_ev)
                            )
                            if cached_price is not None:
                                r["price_eur"] = cached_price

            # Mark remaining uncached results as pending; kick off async tasks.
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

    # Await weather now — scraper threads have been running during the setup
    # above, so this wait overlaps with useful work rather than blocking cold.
    search_weather = None
    if _weather_task is not None:
        try:
            search_weather = await asyncio.wait_for(_weather_task, timeout=2.0)
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

    # Store in response cache. Pending responses use a shorter TTL so clients
    # can poll for real statuses once eTennis scraping completes.
    search_ttl = _SEARCH_CACHE_TTL_PENDING if availability_pending else _SEARCH_CACHE_TTL_COMPLETE
    with _SEARCH_LOCK:
        if len(_SEARCH_CACHE) > 100:
            _purge_search_cache()
        _SEARCH_CACHE[cache_key] = (copy.deepcopy(response), time_monotonic(), search_ttl)

    return response


# ── Admin auth ───────────────────────────────────────────────────────────────
_ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
_api_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)

async def _require_admin(token: str = Security(_api_key_header)):
    # Constant-time compare to avoid leaking the token via timing.
    if not _ADMIN_TOKEN or not token or not secrets.compare_digest(token, _ADMIN_TOKEN):
        raise HTTPException(status_code=403, detail="Forbidden")


# ── Analytics endpoints ───────────────────────────────────────────────────────

@app.get("/api/analytics", dependencies=[Depends(_require_admin)])
async def get_analytics(exclude_sessions: str | None = Query(default=None)):
    from analytics import _DB_NAME, _COLLECTION
    from motor.motor_asyncio import AsyncIOMotorClient
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise HTTPException(status_code=503, detail="Analytics not configured")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5_000)
    col = client[_DB_NAME][_COLLECTION]

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    hours_elapsed = int((now - today_start).total_seconds())
    yesterday_window_end = yesterday_start + timedelta(seconds=hours_elapsed)

    # Base filter: optionally exclude one or more owner sessions (comma-separated).
    # None is included in $nin so it replaces the {"$ne": None} checks below
    # without accidentally letting null-session events leak back in.
    _ids = [s for s in (exclude_sessions or "").split(",") if s]
    _excl: dict = {"session_id": {"$nin": _ids + [None]}} if _ids else {}

    async def _session_count(start, end):
        pipeline = [
            {"$match": {"timestamp": {"$gte": start, "$lt": end}, "session_id": {"$exists": True, "$ne": None}, **_excl}},
            {"$group": {"_id": "$session_id"}},
            {"$count": "count"},
        ]
        r = await col.aggregate(pipeline).to_list(1)
        return r[0]["count"] if r else 0

    async def _event_breakdown(start, end):
        # Page views are tracked separately (see pageviews_*) and excluded here
        # so the "Actions" breakdown stays about product events only.
        pipeline = [
            {"$match": {"timestamp": {"$gte": start, "$lt": end}, "event": {"$ne": "pageview"}, **_excl}},
            {"$group": {"_id": "$event", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        rows = await col.aggregate(pipeline).to_list(20)
        return {r["_id"]: r["count"] for r in rows}

    # "Total Actions" / breakdown exclude pageviews; pageviews counted on their own.
    _no_pv = {"event": {"$ne": "pageview"}}
    today_total      = await col.count_documents({"timestamp": {"$gte": today_start}, **_no_pv, **_excl})
    today_sessions   = await _session_count(today_start, now)
    today_breakdown  = await _event_breakdown(today_start, now)
    today_pageviews  = await col.count_documents({"timestamp": {"$gte": today_start}, "event": "pageview", **_excl})
    yday_total       = await col.count_documents({"timestamp": {"$gte": yesterday_start, "$lt": yesterday_window_end}, **_no_pv, **_excl})
    yday_sessions    = await _session_count(yesterday_start, yesterday_window_end)
    yday_breakdown   = await _event_breakdown(yesterday_start, yesterday_window_end)
    yday_pageviews   = await col.count_documents({"timestamp": {"$gte": yesterday_start, "$lt": yesterday_window_end}, "event": "pageview", **_excl})

    returning_pipeline = [
        {"$match": {"session_id": {"$exists": True, "$ne": None}, **_excl}},
        {"$group": {"_id": "$session_id", "first_seen": {"$min": "$timestamp"}, "last_seen": {"$max": "$timestamp"}}},
        {"$match": {"first_seen": {"$lt": today_start}, "last_seen": {"$gte": today_start}}},
        {"$count": "count"},
    ]
    ret_r = await col.aggregate(returning_pipeline).to_list(1)
    returning_sessions = ret_r[0]["count"] if ret_r else 0

    avg_today_r = await col.aggregate([
        {"$match": {"timestamp": {"$gte": today_start}, "response_ms": {"$exists": True}, **_excl}},
        {"$group": {"_id": None, "avg_ms": {"$avg": "$response_ms"}}},
    ]).to_list(1)
    avg_yday_r = await col.aggregate([
        {"$match": {"timestamp": {"$gte": yesterday_start, "$lt": yesterday_window_end}, "response_ms": {"$exists": True}, **_excl}},
        {"$group": {"_id": None, "avg_ms": {"$avg": "$response_ms"}}},
    ]).to_list(1)
    avg_ms       = round(avg_today_r[0]["avg_ms"]) if avg_today_r else None
    avg_ms_yday  = round(avg_yday_r[0]["avg_ms"])  if avg_yday_r  else None

    def _delta(a, b):
        if b is None or b == 0:
            return None
        return round(((a - b) / b) * 100)

    return {
        "total_events_today":      today_total,
        "pageviews_today":         today_pageviews,
        "unique_sessions_today":   today_sessions,
        "returning_sessions_today": returning_sessions,
        "new_sessions_today":      today_sessions - returning_sessions,
        "avg_response_ms":         avg_ms,
        "event_breakdown_today":   today_breakdown,
        "deltas": {
            "total_events":    _delta(today_total,    yday_total),
            "pageviews":       _delta(today_pageviews, yday_pageviews),
            "unique_sessions": _delta(today_sessions, yday_sessions),
            "avg_response_ms": _delta(avg_ms, avg_ms_yday) if avg_ms and avg_ms_yday else None,
            "events_by_type":  {
                evt: _delta(today_breakdown.get(evt, 0), yday_breakdown.get(evt, 0))
                for evt in set(list(today_breakdown) + list(yday_breakdown))
            },
        },
    }


@app.get("/api/analytics/trends", dependencies=[Depends(_require_admin)])
async def get_analytics_trends(exclude_sessions: str | None = Query(default=None)):
    from analytics import _DB_NAME, _COLLECTION
    from motor.motor_asyncio import AsyncIOMotorClient
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise HTTPException(status_code=503, detail="Analytics not configured")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5_000)
    col = client[_DB_NAME][_COLLECTION]

    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]

    _ids = [s for s in (exclude_sessions or "").split(",") if s]
    _excl: dict = {"session_id": {"$nin": _ids + [None]}} if _ids else {}

    event_rows = await col.aggregate([
        {"$match": {"timestamp": {"$gte": seven_days_ago}, "event": {"$ne": "pageview"}, **_excl}},
        {"$group": {"_id": {
            "date":  {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
            "event": "$event",
        }, "count": {"$sum": 1}}},
        {"$sort": {"_id.date": 1}},
    ]).to_list(500)

    pageview_rows = await col.aggregate([
        {"$match": {"timestamp": {"$gte": seven_days_ago}, "event": "pageview", **_excl}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]).to_list(100)

    session_rows = await col.aggregate([
        {"$match": {"timestamp": {"$gte": seven_days_ago}, "session_id": {"$exists": True, "$ne": None}, **_excl}},
        {"$group": {"_id": {
            "date":    {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
            "session": "$session_id",
        }}},
        {"$group": {"_id": "$_id.date", "unique_sessions": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]).to_list(100)

    events_by_date: dict = {d: {} for d in dates}
    all_event_types: set = set()
    for row in event_rows:
        d, e = row["_id"]["date"], row["_id"]["event"]
        if d in events_by_date:
            events_by_date[d][e] = row["count"]
            all_event_types.add(e)

    sessions_by_date = {r["_id"]: r["unique_sessions"] for r in session_rows}
    pageviews_by_date = {r["_id"]: r["count"] for r in pageview_rows}

    return {
        "dates":                    dates,
        "event_types":              sorted(all_event_types),
        "events_by_date":           events_by_date,
        "unique_sessions_by_date":  {d: sessions_by_date.get(d, 0) for d in dates},
        "pageviews_by_date":        {d: pageviews_by_date.get(d, 0) for d in dates},
    }


@app.get("/api/analytics/insights", dependencies=[Depends(_require_admin)])
async def get_analytics_insights(exclude_sessions: str | None = Query(default=None)):
    """Popular search locations, peak hours, and device breakdown — last 30 days."""
    from analytics import _DB_NAME, _COLLECTION
    from motor.motor_asyncio import AsyncIOMotorClient
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise HTTPException(status_code=503, detail="Analytics not configured")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5_000)
    col = client[_DB_NAME][_COLLECTION]

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    _ids = [s for s in (exclude_sessions or "").split(",") if s]
    _excl: dict = {"session_id": {"$nin": _ids + [None]}} if _ids else {}
    base_match = {
        "event": "search_completed",
        "timestamp": {"$gte": thirty_days_ago},
        **_excl,
    }

    # Top 10 search locations (last 30 days)
    location_rows = await col.aggregate([
        {"$match": {**base_match, "search_location": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$search_location", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)

    # Searches by hour of day (Vienna time, last 30 days)
    hour_rows = await col.aggregate([
        {"$match": base_match},
        {"$addFields": {"hour_vienna": {"$hour": {"date": "$timestamp", "timezone": "Europe/Vienna"}}}},
        {"$group": {"_id": "$hour_vienna", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]).to_list(24)

    # Device breakdown (last 30 days)
    device_rows = await col.aggregate([
        {"$match": {**base_match, "device_type": {"$exists": True}}},
        {"$group": {"_id": "$device_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]).to_list(10)

    # Pageview-based insights (last 30 days). Separate match: event = "pageview".
    pv_match = {"event": "pageview", "timestamp": {"$gte": thirty_days_ago}, **_excl}

    # Top 10 referrer domains (where visitors come from). Internal (same-site)
    # navigations carry referrer_host = null and are excluded; "direct" is kept.
    referrer_rows = await col.aggregate([
        {"$match": {**pv_match, "referrer_host": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$referrer_host", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)

    # Top 10 most-viewed pages
    page_rows = await col.aggregate([
        {"$match": {**pv_match, "path": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$path", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)

    # Top countries by pageviews (last 30 days)
    country_rows = await col.aggregate([
        {"$match": {**pv_match, "country": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$country", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 15},
    ]).to_list(15)

    # Most booked venues (last 30 days)
    venue_rows = await col.aggregate([
        {"$match": {"event": "booking_clicked", "timestamp": {"$gte": thirty_days_ago}, **_excl}},
        {"$group": {"_id": "$venue_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)

    # Zero-results searches by location (last 30 days) — demand without coverage
    zero_rows = await col.aggregate([
        {"$match": {"event": "search_completed", "timestamp": {"$gte": thirty_days_ago}, "results_count": 0, **_excl}},
        {"$group": {"_id": "$search_location", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)
    zero_total = await col.count_documents({
        "event": "search_completed", "timestamp": {"$gte": thirty_days_ago},
        "results_count": 0, **_excl,
    })

    # 30-day conversion: searches → booking clicks
    searches_30d = await col.count_documents(
        {"event": "search_completed", "timestamp": {"$gte": thirty_days_ago}, **_excl}
    )
    bookings_30d = await col.count_documents(
        {"event": "booking_clicked", "timestamp": {"$gte": thirty_days_ago}, **_excl}
    )

    # Fill all 24 hours with 0 for missing hours
    hours_map = {r["_id"]: r["count"] for r in hour_rows}
    hourly = [{"hour": h, "count": hours_map.get(h, 0)} for h in range(24)]

    return {
        "top_locations":         [{"location": r["_id"], "count": r["count"]} for r in location_rows],
        "hourly_searches":       hourly,
        "device_breakdown":      {r["_id"]: r["count"] for r in device_rows},
        "top_referrers":         [{"referrer": r["_id"], "count": r["count"]} for r in referrer_rows],
        "top_pages":             [{"path": r["_id"], "count": r["count"]} for r in page_rows],
        "top_countries":         [{"country": r["_id"], "count": r["count"]} for r in country_rows],
        "top_venues":            [{"venue": r["_id"], "count": r["count"]} for r in venue_rows],
        "zero_results_locations":[{"location": r["_id"] or "Ort nicht angegeben", "count": r["count"]} for r in zero_rows],
        "zero_results_total":    zero_total,
        "searches_30d":          searches_30d,
        "bookings_30d":          bookings_30d,
    }


class BookingClickBody(BaseModel):
    venue_id:   str
    platform:   str
    session_id: str | None = None


@app.post("/api/booking-click")
async def booking_click(body: BookingClickBody):
    """Record booking intent. Frontend fires-and-forgets; opens the booking URL itself."""
    track_booking_clicked(venue_id=body.venue_id, platform=body.platform, session_id=body.session_id)
    return {"ok": True}


class PageviewBody(BaseModel):
    path:          str
    referrer_host: str | None = None
    session_id:    str | None = None


_BOT_UA_MARKERS = ("headlesschrome", "headless", "playwright", "puppeteer", "selenium", "bot/", "crawler", "spider")


@app.post("/api/pageview")
async def pageview(body: PageviewBody, request: Request, background_tasks: BackgroundTasks):
    """Record a first-party, cookieless page view. Fire-and-forget from the frontend.
    Country is resolved from the client IP in a background task so it never delays the response.
    Only the country name is stored — the IP is never persisted (DSGVO-safe)."""
    ua = request.headers.get("user-agent", "").lower()
    if any(m in ua for m in _BOT_UA_MARKERS):
        return {"ok": True}  # silently drop headless/bot pageviews

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


# ── Google Search Console ─────────────────────────────────────────────────────

@app.get("/api/analytics/search-console", dependencies=[Depends(_require_admin)])
async def get_search_console():
    """Fetch last 28 days of Search Console data: top queries, pages, countries."""
    import json as _json
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise HTTPException(status_code=503, detail="GOOGLE_SERVICE_ACCOUNT_JSON not configured")

    try:
        info = _json.loads(raw)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Auth error: {exc}")

    site = "https://www.padelyara.at/"

    def _query(dimensions, row_limit=10):
        body = {
            "startDate": (datetime.now(timezone.utc) - timedelta(days=28)).strftime("%Y-%m-%d"),
            "endDate":   datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "dimensions": dimensions,
            "rowLimit": row_limit,
        }
        try:
            resp = svc.searchanalytics().query(siteUrl=site, body=body).execute()
            return resp.get("rows", [])
        except Exception:
            return []

    query_rows   = _query(["query"], 15)
    page_rows    = _query(["page"], 10)
    country_rows = _query(["country"], 10)
    date_rows    = _query(["date"], 28)

    def _fmt(rows, key):
        return [
            {
                key: r["keys"][0],
                "clicks":      r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr":         round(r.get("ctr", 0) * 100, 1),
                "position":    round(r.get("position", 0), 1),
            }
            for r in rows
        ]

    return {
        "top_queries":   _fmt(query_rows, "query"),
        "top_pages":     _fmt(page_rows, "page"),
        "top_countries": _fmt(country_rows, "country"),
        "daily":         [{"date": r["keys"][0], "clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0)} for r in date_rows],
    }


class SubscribeBody(BaseModel):
    email: str


@app.get("/api/subscribers/count", dependencies=[Depends(_require_admin)])
async def subscribers_count():
    from venues_mongo import _get_db
    db = _get_db()
    count = await db["subscribers"].count_documents({})
    return {"count": count}


@app.post("/api/subscribe")
async def subscribe(body: SubscribeBody):
    import re
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return JSONResponse(status_code=422, content={"ok": False, "error": "invalid_email"})
    from venues_mongo import _get_db
    db = _get_db()
    existing = await db["subscribers"].find_one({"email": email})
    if existing:
        return {"ok": True, "already": True}
    await db["subscribers"].insert_one({
        "email": email,
        "subscribed_at": datetime.now(timezone.utc).isoformat(),
    })
    print(json.dumps({"event": "subscriber_added", "email": email}))
    return {"ok": True, "already": False}


@app.get("/api/weather")
async def weather_endpoint(
    lat:  float = Query(),
    lon:  float = Query(),
    date: str | None = Query(default=None),
    time: str | None = Query(default=None),
):
    dt, parse_error = _parse_datetime(date, time)
    if parse_error:
        return JSONResponse(status_code=400, content={"error": parse_error})

    async with httpx.AsyncClient() as client:
        weather = await get_weather_for_hour(client, lat, lon, dt)
    if weather is None:
        return JSONResponse(status_code=502, content={"error": "weather_unavailable"})
    return weather


@app.get("/api/weather-test")
async def weather_test(
    venue_id: str | None = Query(default=None),
    date:     str | None = Query(default=None),
    time:     str | None = Query(default=None),
):
    vid = venue_id or DEFAULT_VENUE_ID

    venue = next((v for v in await load_venues() if v["id"] == vid), None)
    if venue is None:
        return JSONResponse(status_code=404, content={"error": "venue_not_found", "venue_id": vid})

    if venue["lat"] is None or venue["lon"] is None:
        return JSONResponse(status_code=422, content={"error": "no_coordinates", "venue_id": vid})

    dt, parse_error = _parse_datetime(date, time)
    if parse_error:
        return JSONResponse(status_code=400, content={"error": "invalid_params", "detail": parse_error})

    async with httpx.AsyncClient() as client:
        weather = await get_weather_for_hour(client, venue["lat"], venue["lon"], dt)
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


@app.get("/api/price-cache")
async def price_cache_check():
    """Diagnostic: show current Eversports price cache status."""
    import eversports_prices as _ep
    with _ep._PRICE_LOCK:
        return {
            venue_id: {
                "slot_count":  len(entry["slots"]),
                "prices":      sorted(set(s["price"] for s in entry["slots"])),
                "dates":       sorted(set(s["date"]  for s in entry["slots"])),
                "age_minutes": round((time.monotonic() - entry["scraped_at"]) / 60, 1),
            }
            for venue_id, entry in _ep._PRICE_CACHE.items()
        }


@app.get("/api/env-check")
async def env_check():
    """Temporary diagnostic: confirm which env vars the running process sees."""
    import eversports_service as _ev
    return {
        "EVERSPORTS_CALENDAR_PROXY": os.environ.get("EVERSPORTS_CALENDAR_PROXY"),
        "EVERSPORTS_SLOT_PROXY_set": bool(os.environ.get("EVERSPORTS_SLOT_PROXY")),
        "_CALENDAR_PROXY_URL_at_import": _ev._CALENDAR_PROXY_URL,
        "runtime_read": os.environ.get("EVERSPORTS_CALENDAR_PROXY"),
    }


@app.get("/check")
async def check_compat(
    facility_id: int        = Query(...),
    court_ids:   str        = Query(...),
    date:        str        = Query(...),
    time:        str        = Query(...),
    venue_url:   str        = Query(default=""),
    venue_id:    str        = Query(default=""),
):
    """Compatibility shim — keeps the legacy frontend→backend HTTP contract working."""
    return await check_eversports_slot(
        facility_id=facility_id,
        court_ids=court_ids,
        date=date,
        time=time,
        venue_url=venue_url,
        venue_id=venue_id,
    )


@app.get("/api/tournaments")
async def get_tournaments(
    bundesland:  str = Query(default=""),
    bezirk:      str = Query(default=""),
    category:    str = Query(default=""),
    competition: str = Query(default=""),
    weekday:     str = Query(default=""),
    venue_name:  str = Query(default=""),
    show_full:   bool = Query(default=False),
    show_closed: bool = Query(default=False),
):
    """
    Return filtered tournament list from MongoDB.
    Multi-value params are comma-separated, e.g. bundesland=Wien,Tirol
    """
    def _split(s: str) -> list[str] | None:
        parts = [p.strip() for p in s.split(",") if p.strip()]
        return parts if parts else None

    tournaments = await tournaments_mongo.get_tournaments(
        bundesland=_split(bundesland),
        bezirk=_split(bezirk),
        category=_split(category),
        competition=_split(competition),
        weekday=_split(weekday),
        venue_name=_split(venue_name),
        show_full=show_full,
        show_closed=show_closed,
    )
    return {"tournaments": tournaments, "count": len(tournaments)}


@app.get("/api/tournaments/bezirke")
async def get_tournament_bezirke(bundesland: str = Query(default="")):
    """Return distinct Bezirk names for the filter, optionally scoped to a Bundesland."""
    bl = [p.strip() for p in bundesland.split(",") if p.strip()] if bundesland else None
    bezirke = await tournaments_mongo.get_bezirke(bundesland=bl)
    return {"bezirke": bezirke}


@app.get("/api/tournaments/venues")
async def get_tournament_venues(bundesland: str = Query(default="")):
    """Return distinct venue names for the Standort filter."""
    bl = [p.strip() for p in bundesland.split(",") if p.strip()] if bundesland else None
    venues = await tournaments_mongo.get_venues(bundesland=bl)
    return {"venues": venues}


@app.get("/api/tournaments/player")
async def get_player_tournaments(slug: str = Query(..., description="Player slug from padel-austria.at/players/<slug>")):
    """Return open/upcoming tournaments the player is registered for."""
    slug = slug.strip().lower()
    tournaments = await tournaments_mongo.get_tournaments_for_player(slug)
    return {"tournaments": tournaments, "player_slug": slug}


def _slug_from(value: str) -> str:
    """Accept a full padel-austria.at profile URL or a bare slug; return the slug."""
    v = value.strip().rstrip("/")
    if "/players/" in v:
        v = v.split("/players/", 1)[1].split("/")[0].split("?")[0]
    return v.lower()


@app.get("/api/urteil")
async def get_urteil(
    profile: str = Query(..., description="padel-austria.at profile URL or player slug"),
):
    """
    Yaras Urteil: scrape + analyse a player's tournament profile, then have Yara
    deliver a two-part verdict (Beobachtungen + Urteil). Rules live in
    yara_urteil_prompt.py. Returns the facts even if the AI verdict is unavailable.
    """
    slug = _slug_from(profile)
    if not slug or "/" in slug or " " in slug:
        raise HTTPException(status_code=400, detail="Ungültiges Profil.")

    facts = await asyncio.to_thread(analyze_player, slug)
    if facts is None:
        raise HTTPException(status_code=404, detail="Profil nicht gefunden.")

    # Ausblick: upcoming tournaments the player is already registered for.
    try:
        upcoming = await tournaments_mongo.get_tournaments_for_player(slug)
    except Exception:
        upcoming = []

    result: dict = {
        "slug": slug,
        "facts": facts,
        "upcoming": upcoming,
        "disclaimer": DISCLAIMER,
        "ai_available": True,
        "beobachtungen": [],
        "urteil": None,
    }
    try:
        verdict = await asyncio.to_thread(generate_urteil, facts)
        result["beobachtungen"] = verdict["beobachtungen"]
        result["urteil"] = verdict["urteil"]
    except UrteilUnavailable as e:
        result["ai_available"] = False
        result["ai_error"] = str(e)

    # Record the search + verdict for accountability (best-effort, never blocks).
    await urteil_mongo.log_urteil({
        "slug": slug,
        "profile": profile,
        "player_name": facts.get("player", {}).get("name"),
        "facts": facts,
        "beobachtungen": result["beobachtungen"],
        "urteil": result["urteil"],
        "ai_available": result["ai_available"],
    })
    return result


@app.get("/api/venues")
async def get_venues():
    """Static venue list for the Padelrevier map — no scraping, served from the
    load_venues() cache. Returns only what the map needs (name, address, coords,
    links), filtered to venues that actually have coordinates to place a pin."""
    venues = await load_venues()
    out = [
        {
            "id":          v["id"],
            "name":        v["name"],
            "operator":    v.get("operator", ""),
            "address":     v.get("address", ""),
            "court_type":  v["court_type"],
            "platform":    v.get("platform", ""),
            "booking_url": v.get("booking_url", ""),
            "public_url":  v.get("public_url", ""),
            "lat":         v["lat"],
            "lon":         v["lon"],
        }
        for v in venues
        if v.get("lat") is not None and v.get("lon") is not None
    ]
    return {"venues": out, "count": len(out)}


# Court-Detailseite endpoint (venue detail by slug)
@app.get("/api/venues/{slug}")
async def get_venue_detail_endpoint(slug: str):
    """Full detail for one venue (Court-Detailseite). Amenities + cross-links to
    same-operator / same-city venues. 404 if the slug is unknown or inactive."""
    detail = await get_venue_detail(slug)
    if not detail:
        raise HTTPException(status_code=404, detail="Venue not found")
    return detail


@app.post("/api/admin/scrape-tournaments", dependencies=[Depends(_require_admin)])
async def trigger_tournament_scrape():
    """Manually trigger a tournament scrape (admin only)."""
    threading.Thread(target=_run_tournament_scrape, daemon=True).start()
    return {"status": "scrape started"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # reload=False: avoids conflicts with Playwright's Chrome subprocess
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
