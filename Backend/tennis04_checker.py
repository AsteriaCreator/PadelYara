"""
tennis04 availability checker — production module.
Called by app.py; not a standalone server.

tennis04 exposes a fully public JSON API (no auth, plain requests.get):

  1. GET /a/{club_id}/courtgroups
       Nested list: top-level groups each holding a `courtGroups` array.
       Pick the group whose name contains "padel". It gives the court list
       (`courts[].id`) and opening hours (`hourFrom` / `hourUntil`).

  2. GET /a/{club_id}/bookings?datefrom=D&dateto=D&courtgroup={uuid}&useAccountingColors=false
       Array of BOOKED slots: {start, end, resourceId, ...}.  start/end are
       naive Vienna-local ISO strings ("2026-06-08T20:00:00").
       NOTE: `useAccountingColors` is REQUIRED — omitting it returns 404.

Availability logic:
  A padel court is FREE at the requested time T when no booking on that court
  covers T (start <= T < end). The venue is:
    - "free"    if >= 1 court is free at T
    - "busy"    if all courts are booked at T
    - "no_slot" if T is outside the courtgroup's opening hours
    - "unknown" if the API call or parsing failed

This mirrors the public surface of etennis_checker.py (check_*_venues,
get_cached_statuses, get_cached_entries) so app.py can wire it in symmetrically.
Unlike eTennis/Eversports this needs no browser — plain HTTP, so checks run in
a small thread pool with no Playwright semaphore.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests as _requests

from analytics import track_scraper_timeout
from availability import venue_free_durations

VIENNA_TZ = ZoneInfo("Europe/Vienna")
_BASE = "https://app.tennis04.com"
_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*"}
_HTTP_TIMEOUT = 12  # seconds per request

DEFAULT_FALLBACK_MINUTES: list[int] = [30, 60]

# Availability result cache, keyed per venue/date/hour:minute.
_CACHE: dict[str, dict] = {}
_TTL = 300  # seconds

_COOLDOWN: dict[str, float] = {}  # venue_id → timestamp of last unknown
_COOLDOWN_TTL = 60  # seconds

_RUNNING: set[str] = set()  # scrape keys currently in-flight
_RUNNING_LOCK = threading.Lock()

# Courtgroup metadata (court list + opening hours) is essentially static, so
# cache it in-process for an hour to avoid re-fetching the large courtgroups
# payload on every availability check.
_CG_CACHE: dict[str, tuple[dict, float]] = {}
_CG_TTL = 3600  # seconds

_CONCURRENCY = 5  # max venues checked in parallel (plain HTTP — cheap)
_PER_VENUE_TIMEOUT = 25  # seconds — two HTTP GETs (courtgroups + bookings) + buffer


def _cache_key(venue_id: str, dt: datetime) -> str:
    return f"{venue_id}*{dt.strftime('%Y-%m-%d')}*{dt.strftime('%H:%M')}"


def _scrape_key(venue_ids: list[str], dt: datetime) -> str:
    """Stable key for a set of venues at a given date+hour+minute, used to deduplicate in-flight scrapes."""
    return "|".join(sorted(venue_ids)) + f"@{dt.strftime('%Y-%m-%dT%H:%M')}"


def _parse_date(iso: str):
    """Parse a tennis04 date/datetime string to a date, or None."""
    try:
        return datetime.fromisoformat(iso).date()
    except (ValueError, TypeError):
        return None


def _fetch_courtgroup_meta(club_id: int, courtgroup_id: str) -> dict | None:
    """
    Return {"courts": [str, ...], "hour_from": int, "hour_until": int,
            "default_duration_min": int, "seasons": [(id, begin_date, end_date|None)]}
    for the padel courtgroup, or None on failure.

    Cached in-process for _CG_TTL. The courtgroup is matched by the exact UUID
    stored in MongoDB; if that is missing we fall back to the first group whose
    name contains "padel".
    """
    ck = f"{club_id}*{courtgroup_id}"
    now = time.time()
    cached = _CG_CACHE.get(ck)
    if cached and now - cached[1] < _CG_TTL:
        return cached[0]

    try:
        r = _requests.get(f"{_BASE}/a/{club_id}/courtgroups", headers=_HEADERS, timeout=_HTTP_TIMEOUT)
        r.raise_for_status()
        groups = r.json()
    except Exception as exc:
        print(f"[tennis04] courtgroups fetch failed club={club_id}: {exc}")
        return None

    target = None
    for top in groups:
        for g in top.get("courtGroups", []) or []:
            if courtgroup_id and g.get("id") == courtgroup_id:
                target = g
                break
            if not courtgroup_id and "padel" in (g.get("name") or "").lower():
                target = g
        if target:
            break

    if target is None:
        print(f"[tennis04] no padel courtgroup found club={club_id} cg={courtgroup_id!r}")
        return None

    seasons = []
    for s in target.get("seasons", []) or []:
        sid = s.get("id")
        if sid is None:
            continue
        seasons.append((sid, _parse_date(s.get("seasonBegin")), _parse_date(s.get("seasonEnd"))))

    meta = {
        "courts":               [str(c["id"]) for c in target.get("courts", []) or []],
        "hour_from":            int(target.get("hourFrom") or 0),
        "hour_until":           int(target.get("hourUntil") or 24),
        "default_duration_min": int(target.get("defaultDurationMinutes") or 60),
        "seasons":              seasons,
    }
    _CG_CACHE[ck] = (meta, now)
    return meta


def _season_for(meta: dict, day) -> int | None:
    """Pick the season id whose range covers `day`; else the open-ended one; else the last."""
    seasons = meta.get("seasons") or []
    if not seasons:
        return None
    for sid, begin, end in seasons:
        if begin and begin <= day and (end is None or day <= end):
            return sid
    for sid, begin, end in seasons:
        if end is None:
            return sid
    return seasons[-1][0]


def _iso_time(iso: str):
    """Extract the time component from a tennis04 tariff datetime ('1900-01-01T16:00:00')."""
    try:
        return datetime.fromisoformat(iso).time()
    except (ValueError, TypeError):
        return None


def _fetch_tariff(club_id: int, courtgroup_id: str, season_id: int) -> tuple[int, list] | None:
    """
    Return (price_unit_minutes, tariff_groups) from the pricelegend endpoint, or
    None on failure. Cached in-process for _CG_TTL (prices are static per season).
    """
    ck = f"price*{club_id}*{courtgroup_id}*{season_id}"
    now = time.time()
    cached = _CG_CACHE.get(ck)
    if cached and now - cached[1] < _CG_TTL:
        return cached[0]
    try:
        r = _requests.get(
            f"{_BASE}/a/{club_id}/courtgroups/{courtgroup_id}/pricelegend",
            params={"seasonId": season_id, "ts": str(int(time.time() * 1000))},
            headers=_HEADERS, timeout=_HTTP_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        print(f"[tennis04] pricelegend fetch failed club={club_id}: {exc}")
        return None
    result = (int(data.get("priceUnit") or 60), data.get("tariffTable") or [])
    _CG_CACHE[ck] = (result, now)
    return result


def _price_at(meta: dict, club_id: int, courtgroup_id: str, dt: datetime) -> int | None:
    """
    Per-hour guest price (EUR, rounded) for the requested weekday + time, or None.

    Prefers the "Gast" (guest) tariff group — the public, non-member rate —
    falling back to the cheapest non-zero rate across all groups (member groups
    are often €0 and would otherwise be misleading).
    """
    season_id = _season_for(meta, dt.date())
    if season_id is None:
        return None
    tariff = _fetch_tariff(club_id, courtgroup_id, season_id)
    if not tariff:
        return None
    price_unit, groups = tariff
    wd = dt.isoweekday()  # 1=Mon..7=Sun, matches tennis04 weekDay
    t = dt.time()

    def _matches(p: dict) -> bool:
        if p.get("weekDay") != wd:
            return False
        bt, et = _iso_time(p.get("beginTime")), _iso_time(p.get("endTime"))
        return bt is not None and et is not None and bt <= t < et

    guest = [g for g in groups if "gast" in (g.get("group") or "").lower()]
    candidate_groups = guest if guest else groups
    prices = [
        p["price"]
        for g in candidate_groups
        for p in g.get("prices", []) or []
        if _matches(p) and p.get("price")
    ]
    if not prices:
        return None
    per_hour = min(prices) * (60 / price_unit) if price_unit else min(prices)
    return round(per_hour)


def _fetch_bookings(club_id: int, courtgroup_id: str, date) -> list[dict] | None:
    """Fetch the day's booked slots for the padel courtgroup. None on failure."""
    date_str = date.strftime("%Y-%m-%d")
    params = {
        "datefrom":           date_str,
        "dateto":             date_str,
        "courtgroup":         courtgroup_id,
        "useAccountingColors": "false",  # REQUIRED — omitting it 404s
        "ts":                 str(int(time.time() * 1000)),
    }
    try:
        r = _requests.get(
            f"{_BASE}/a/{club_id}/bookings", params=params, headers=_HEADERS, timeout=_HTTP_TIMEOUT
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"[tennis04] bookings fetch failed club={club_id}: {exc}")
        return None


def _parse_naive(iso: str) -> datetime | None:
    """Parse a tennis04 naive Vienna-local ISO string, dropping any tz info."""
    try:
        return datetime.fromisoformat(iso).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _free_courts_at(bookings: list[dict], courts: list[str], t_naive: datetime) -> list[str]:
    """Return the courts with no booking covering t_naive (start <= t < end)."""
    busy: set[str] = set()
    for b in bookings:
        rid = b.get("resourceId")
        if rid is None:
            continue
        rid = str(rid)
        if rid not in courts:
            continue
        start = _parse_naive(b.get("start"))
        end = _parse_naive(b.get("end"))
        if start is None or end is None:
            continue
        if start <= t_naive < end:
            busy.add(rid)
    return [c for c in courts if c not in busy]


def _target_ts(dt: datetime) -> int:
    """Unix timestamp for a Vienna-local wall-clock time."""
    return int(dt.replace(tzinfo=VIENNA_TZ).timestamp())


def _check_one(
    venue: dict,
    dt: datetime,
    fallback_offsets: list[int] = (),
) -> tuple[str, str, str | None, int | None, int | None, float | None, list[int], list[dict]]:
    """
    Check one tennis04 venue at the given datetime.

    Returns (venue_id, status, error, next_free_ts, price_eur, slot_duration_h,
             free_durations, fallback_durations):
      - status:             "free" | "busy" | "no_slot" | "unknown"
      - next_free_ts:       Unix ts of the nearest free fallback slot, or None
      - price_eur:          per-hour guest price (EUR, rounded), or None
      - slot_duration_h:    courtgroup default duration in hours, or None
      - free_durations:     bookable continuous durations (min) free at T
      - fallback_durations: [{ts, durations}] for the scanned fallback offsets
    """
    vid = venue["id"]
    vname = venue.get("name", vid)
    club_id = venue.get("tennis04_club_id")
    cg_id = venue.get("tennis04_courtgroup_id")
    t0 = time.monotonic()
    print(json.dumps({
        "event":      "tennis04_venue_start",
        "venue_id":   vid,
        "venue_name": vname,
        "date":       dt.strftime("%Y-%m-%d"),
        "time":       dt.strftime("%H:%M"),
    }))

    if not club_id:
        return vid, "unknown", "missing tennis04_club_id", None, None, None, [], []

    meta = _fetch_courtgroup_meta(int(club_id), cg_id or "")
    if not meta or not meta["courts"]:
        return vid, "unknown", "courtgroup_meta_unavailable", None, None, None, [], []

    bookings = _fetch_bookings(int(club_id), cg_id or "", dt.date())
    if bookings is None:
        return vid, "unknown", "bookings_unavailable", None, None, None, [], []

    courts = meta["courts"]
    duration_h = (meta["default_duration_min"] / 60) if meta["default_duration_min"] else None
    price_eur = _price_at(meta, int(club_id), cg_id or "", dt)

    # ── Continuous-block model: per-court busy intervals (minutes since midnight) ─
    # so we can answer "which durations are free starting at T?", not just the
    # single-slot free/busy. grid_min is the courtgroup's booking step; the venue
    # closes default_duration after the last valid start hour (hour_until).
    grid_min  = int(meta["default_duration_min"] or 60)
    open_min  = int(meta["hour_from"]) * 60
    close_min = int(meta["hour_until"]) * 60 + grid_min
    courts_busy: dict[str, list[tuple[int, int]]] = {c: [] for c in courts}
    for b in bookings:
        rid = b.get("resourceId")
        if rid is None:
            continue
        rid = str(rid)
        if rid not in courts_busy:
            continue
        bs = _parse_naive(b.get("start"))
        be = _parse_naive(b.get("end"))
        if bs is None or be is None:
            continue
        start_min = bs.hour * 60 + bs.minute
        # Use the full datetime delta so a slot ending at/after midnight is sane.
        end_min = start_min + int((be - bs).total_seconds() // 60)
        courts_busy[rid].append((start_min, end_min))

    def _free_durs_at(d: datetime) -> list[int]:
        return venue_free_durations(
            courts_busy, d.hour * 60 + d.minute, grid_min, open_min, close_min
        )

    def _status_at(d: datetime) -> str:
        # hour_until is the last valid START hour (inclusive): a slot at hourUntil
        # runs until hourUntil + defaultDurationMinutes/60, i.e. the venue closes
        # after that. Using < would wrongly reject the last valid start time.
        if not (meta["hour_from"] <= d.hour <= meta["hour_until"]):
            return "no_slot"
        return "free" if _free_courts_at(bookings, courts, d.replace(tzinfo=None)) else "busy"

    status = _status_at(dt)
    free_durations = _free_durs_at(dt)

    # Single-pass fallback scan: nearest free slot among the configured offsets.
    # Only consider candidates on the SAME calendar day — we fetched bookings for
    # dt.date() only, so a post-midnight candidate would be checked against the
    # wrong day's bookings (and is outside opening hours anyway).
    # We record each offset's free_durations so app.py can pick the next time a
    # *requested* duration opens up (duration-aware fallback), not just any slot.
    next_free_ts: int | None = None
    fallback_durations: list[dict] = []
    if status != "free":
        for offset_min in fallback_offsets:
            fb_dt = dt + timedelta(minutes=offset_min)
            if fb_dt.date() != dt.date():
                continue
            fb_durs = _free_durs_at(fb_dt)
            fallback_durations.append({"ts": _target_ts(fb_dt), "durations": fb_durs})
            if next_free_ts is None and _status_at(fb_dt) == "free":
                next_free_ts = _target_ts(fb_dt)

    print(json.dumps({
        "event":          "tennis04_scrape_result",
        "venue_id":       vid,
        "venue_name":     vname,
        "date":           dt.strftime("%Y-%m-%d"),
        "time":           dt.strftime("%H:%M"),
        "status":         status,
        "courts":         len(courts),
        "bookings":       len(bookings),
        "next_free_ts":   next_free_ts,
        "price_eur":      price_eur,
        "duration_h":     duration_h,
        "free_durations": free_durations,
        "duration_ms":    round((time.monotonic() - t0) * 1000),
    }))
    return vid, status, None, next_free_ts, price_eur, duration_h, free_durations, fallback_durations


def _store_result(
    venue_id: str,
    status: str,
    dt: datetime,
    next_free_ts: int | None = None,
    price_eur: int | None = None,
    slot_duration_h: float | None = None,
    free_durations: list[int] | None = None,
    fallback_durations: list[dict] | None = None,
) -> None:
    """Write one venue result to cache immediately — called per-venue as checks complete."""
    store_ts = time.time()
    print(f"[tennis04] cached: {venue_id} -> {status}")
    if status == "unknown":
        _COOLDOWN[venue_id] = store_ts
    else:
        entry: dict = {"status": status, "timestamp": store_ts}
        if next_free_ts is not None:
            entry["next_free_ts"] = next_free_ts
        if price_eur is not None:
            entry["price_eur"] = price_eur
        if slot_duration_h is not None:
            entry["slot_duration_h"] = slot_duration_h
        if free_durations is not None:
            entry["free_durations"] = free_durations
        if fallback_durations:
            entry["fallback_durations"] = fallback_durations
        _CACHE[_cache_key(venue_id, dt)] = entry
        _COOLDOWN.pop(venue_id, None)


def _run(venues: list[dict], dt: datetime) -> dict[str, str]:
    t0 = time.monotonic()
    print(json.dumps({
        "event":       "tennis04_scraper_start",
        "venues":      [v["id"] for v in venues],
        "venue_count": len(venues),
        "concurrency": _CONCURRENCY,
        "date":        dt.strftime("%Y-%m-%d"),
        "time":        dt.strftime("%H:%M"),
    }))

    out: dict[str, str] = {}

    def fetch_one(venue: dict) -> None:
        vid = venue["id"]
        vname = venue.get("name", vid)
        fb_offsets = venue.get("slot_fallback_minutes") or DEFAULT_FALLBACK_MINUTES
        t_venue = time.monotonic()
        try:
            vid, status, err, next_free_ts, price_eur, slot_duration_h, free_durations, fallback_durations = _check_one(
                venue, dt, fallback_offsets=fb_offsets
            )
        except Exception as exc:
            status, err, next_free_ts, price_eur, slot_duration_h, free_durations, fallback_durations = "unknown", str(exc), None, None, None, [], []
            print(json.dumps({
                "event":      "tennis04_scrape_error",
                "venue_id":   vid,
                "venue_name": vname,
                "error":      f"{type(exc).__name__}: {exc}",
            }))
        if err and "timeout" not in err:
            print(f"[tennis04] {vid} error: {err}")
        out[vid] = status
        _store_result(vid, status, dt, next_free_ts=next_free_ts, price_eur=price_eur,
                      slot_duration_h=slot_duration_h, free_durations=free_durations,
                      fallback_durations=fallback_durations)

    with ThreadPoolExecutor(max_workers=min(_CONCURRENCY, len(venues))) as pool:
        futures = {pool.submit(fetch_one, v): v for v in venues}
        # Iterate in submission order with a real per-venue deadline. (as_completed
        # would only yield already-finished futures, so result(timeout=) there can
        # never actually time out.) Workers run concurrently; while we block on a
        # slow one the rest keep going, so total wait stays ~_PER_VENUE_TIMEOUT.
        for fut, venue in futures.items():
            try:
                fut.result(timeout=_PER_VENUE_TIMEOUT)
            except Exception as exc:
                vid = venue["id"]
                if vid not in out:
                    out[vid] = "unknown"
                    _store_result(vid, "unknown", dt)
                track_scraper_timeout(venue_id=vid, platform="tennis04", timeout_ms=_PER_VENUE_TIMEOUT * 1000)
                print(json.dumps({
                    "event":      "tennis04_scrape_timeout",
                    "venue_id":   vid,
                    "error":      f"{type(exc).__name__}: {exc}",
                }))

    print(json.dumps({
        "event":       "tennis04_scraper_done",
        "statuses":    out,
        "venue_count": len(venues),
        "duration_ms": round((time.monotonic() - t0) * 1000),
    }))
    return out


def get_cached_statuses(venues: list[dict], dt: datetime) -> dict[str, str]:
    """Return cached/cooldown statuses without fetching anything."""
    now = time.time()
    out: dict[str, str] = {}
    for venue in venues:
        key = _cache_key(venue["id"], dt)
        entry = _CACHE.get(key)
        if entry and now - entry["timestamp"] < _TTL:
            out[venue["id"]] = entry["status"]
        elif venue["id"] in _COOLDOWN and now - _COOLDOWN[venue["id"]] < _COOLDOWN_TTL:
            out[venue["id"]] = "unknown"
    return out


def get_cached_entries(venues: list[dict], dt: datetime) -> dict[str, dict]:
    """
    Like get_cached_statuses but returns the full cache entry per venue_id.
    Each entry contains {"status": str, "timestamp": float} and optionally
    {"next_free_ts": int} / {"slot_duration_h": float}. Cooldown venues excluded.
    """
    now = time.time()
    out: dict[str, dict] = {}
    for venue in venues:
        key = _cache_key(venue["id"], dt)
        entry = _CACHE.get(key)
        if entry and now - entry["timestamp"] < _TTL:
            out[venue["id"]] = entry
    return out


def check_tennis04_venues(venues: list[dict], dt: datetime) -> dict[str, str]:
    """
    Returns {venue_id: "free" | "busy" | "no_slot" | "unknown"} for every
    tennis04 venue. Serves cached results immediately and runs uncached checks
    in a background thread (pending-first, same shape as check_etennis_venues).
    Results are cached per venue/date/hour:minute for _TTL seconds.
    """
    if not venues:
        return {}

    now = time.time()
    cached: dict[str, str] = {}
    to_fetch: list[dict] = []

    for venue in venues:
        key = _cache_key(venue["id"], dt)
        entry = _CACHE.get(key)
        if entry and now - entry["timestamp"] < _TTL:
            print(f"[tennis04] cache hit:  {venue['id']} -> {entry['status']}")
            cached[venue["id"]] = entry["status"]
        elif venue["id"] in _COOLDOWN and now - _COOLDOWN[venue["id"]] < _COOLDOWN_TTL:
            print(f"[tennis04] cooldown skip: {venue['id']}")
            cached[venue["id"]] = "unknown"
        else:
            to_fetch.append(venue)

    if not to_fetch:
        return cached

    # Key covers ALL input venues so the in-flight check still matches even after
    # some venues have been individually cached (to_fetch shrinks; key must not).
    scrape_key = _scrape_key([v["id"] for v in venues], dt)

    with _RUNNING_LOCK:
        if scrape_key in _RUNNING:
            print(f"[tennis04] scrape in-flight — returning {len(cached)} cached so far")
            return cached  # partial results; caller marks the rest as pending
        _RUNNING.add(scrape_key)

    def _run_in_thread():
        try:
            _run(to_fetch, dt)  # writes cache per-venue
        except Exception as exc:
            print(f"[tennis04] thread-level error: {exc}")
        finally:
            # Any venue not yet cached → cooldown so it isn't retried in a tight loop
            store_ts = time.time()
            for v in to_fetch:
                if _cache_key(v["id"], dt) not in _CACHE and v["id"] not in _COOLDOWN:
                    print(f"[tennis04] no result: {v['id']} -> unknown (thread exit)")
                    _COOLDOWN[v["id"]] = store_ts
            with _RUNNING_LOCK:
                _RUNNING.discard(scrape_key)

    threading.Thread(target=_run_in_thread, daemon=True).start()
    # Return immediately — _run_in_thread writes results as they arrive;
    # the next request reads them from cache via get_cached_statuses.
    return cached
