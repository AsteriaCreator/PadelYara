"""
eTennis availability checker — production module.
Called by app.py; not a standalone server.
"""

import asyncio
import json
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests as _requests
from bs4 import BeautifulSoup as _BS
from playwright.async_api import async_playwright

from analytics import track_scraper_timeout

VIENNA_TZ = ZoneInfo("Europe/Vienna")

DEFAULT_FALLBACK_MINUTES: list[int] = [30, 60]

_CACHE: dict[str, dict] = {}
_TTL = 300  # seconds

_COOLDOWN: dict[str, float] = {}  # venue_id → timestamp of last unknown
_COOLDOWN_TTL = 60  # seconds

_RUNNING: set[str] = set()  # scrape keys currently in-flight
_RUNNING_LOCK = threading.Lock()
_PLAYWRIGHT_SEM = threading.Semaphore(1)  # one Playwright browser at a time on Render


def _cache_key(venue_id: str, dt: datetime) -> str:
    return f"{venue_id}*{dt.strftime('%Y-%m-%d')}*{dt.strftime('%H:%M')}"


def _scrape_key(venue_ids: list[str], dt: datetime) -> str:
    """Stable key for a set of venues at a given date+hour+minute, used to deduplicate in-flight scrapes."""
    return "|".join(sorted(venue_ids)) + f"@{dt.strftime('%Y-%m-%dT%H:%M')}"


def _page_url(booking_url: str, date) -> str:
    # Use Vienna midnight — eTennis slot data-begin values are also Vienna-based
    ts = int(datetime(date.year, date.month, date.day, tzinfo=VIENNA_TZ).timestamp())
    return f"{booking_url}&t={ts}"


def _target_ts(date, hour: int, minute: int = 0) -> int:
    return int(datetime(date.year, date.month, date.day, hour, minute, tzinfo=VIENNA_TZ).timestamp())


def _http_scrape(
    url: str,
    target_ts: int,
    fallback_offsets: list[int] = (),
) -> tuple[str, str | None, int | None]:
    """
    HTTP fallback for server-rendered slot pages (e.g. reservierung.padel4fun.at).
    Used when Playwright fails (timeout, crash) on Render's resource-constrained env.

    Returns (status, error, next_free_ts).
    Slot matching uses EXACT start-time comparison (begin == target_ts).
    A slot that merely contains the target time (range-based overlap) is NOT a match —
    only slots whose start timestamp equals the requested time count.
    If the primary slot is not free, fallback_offsets are scanned to find the nearest
    free slot, returned as a Unix timestamp in next_free_ts.
    """
    try:
        r = _requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = _BS(r.text, "html.parser")
        slots = soup.select(".slot[data-begin]")
        if not slots:
            return "unknown", "http_fallback: no .slot[data-begin] found", None
        # Build a map of begin_ts → is_available for fast offset lookups
        slot_map: dict[int, bool] = {}
        for s in slots:
            try:
                begin = int(s["data-begin"])
                slot_map[begin] = "av" in (s.get("class") or [])
            except (ValueError, KeyError):
                continue
        if target_ts not in slot_map:
            primary_status = "no_slot"
        else:
            primary_status = "free" if slot_map[target_ts] else "busy"
        # Find next free slot in fallback window
        next_free_ts: int | None = None
        if primary_status != "free":
            for offset in fallback_offsets:
                fb_ts = target_ts + offset * 60
                if slot_map.get(fb_ts):          # True = available
                    next_free_ts = fb_ts
                    break
        return primary_status, None, next_free_ts
    except Exception as exc:
        return "unknown", f"http_fallback: {exc}", None


def _store_result(
    venue_id: str,
    status: str,
    dt: datetime,
    next_free_ts: int | None = None,
) -> None:
    """Write one venue result to cache immediately — called per-venue as scraping completes."""
    store_ts = time.time()
    print(f"[eTennis] cached: {venue_id} -> {status}")
    if status == "unknown":
        _COOLDOWN[venue_id] = store_ts
    else:
        entry: dict = {"status": status, "timestamp": store_ts}
        if next_free_ts is not None:
            entry["next_free_ts"] = next_free_ts
        _CACHE[_cache_key(venue_id, dt)] = entry
        _COOLDOWN.pop(venue_id, None)


async def _check_one(
    browser,
    venue: dict,
    dt: datetime,
    fallback_offsets: list[int] = (),
) -> tuple[str, str, str | None, int | None]:
    """
    Scrape one eTennis venue at the given datetime.

    Returns (venue_id, status, error, next_free_ts) where:
      - status:       "free" | "busy" | "no_slot" | "unknown"
      - error:        non-None when something went wrong
      - next_free_ts: Unix timestamp of the nearest free fallback slot,
                      or None if primary is free or no fallback found.

    fallback_offsets are checked in a single JS pass over the already-loaded DOM —
    no extra page loads or browser sessions.
    """
    url       = _page_url(venue["booking_url"], dt.date())
    target_ts = _target_ts(dt.date(), dt.hour, dt.minute)
    vid       = venue["id"]
    page      = None
    t0        = time.monotonic()
    try:
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        try:
            await page.wait_for_selector(".slot[data-begin]", state="attached", timeout=20_000)
        except Exception as sel_exc:
            # Selector not found — log what the page actually contains
            try:
                diag = await page.evaluate(
                    """() => ({
                        slotCount:      document.querySelectorAll('.slot').length,
                        dataBeginCount: document.querySelectorAll('[data-begin]').length,
                        bodySnippet:    document.body?.innerText?.slice(0, 200) || ''
                    })"""
                )
                print(
                    f"[eTennis] {vid}  .slot[data-begin] not found"
                    f"  .slot={diag['slotCount']}"
                    f"  [data-begin]={diag['dataBeginCount']}"
                    f"  body={diag['bodySnippet']!r:.120}"
                    f"  error={sel_exc}"
                )
            except Exception:
                print(f"[eTennis] {vid}  .slot[data-begin] not found, diag eval also failed: {sel_exc}")
            print(f"[eTennis] {vid}  selector timeout — trying HTTP fallback")
            status, fallback_err, next_free_ts = await asyncio.to_thread(
                _http_scrape, url, target_ts, fallback_offsets
            )
            print(f"[eTennis] {vid}  HTTP fallback: {status}  err={fallback_err!r}  next_free_ts={next_free_ts}")
            return vid, status, fallback_err, next_free_ts

        result = await page.evaluate(
            """([ts, fallbackOffsets]) => {
                const slots    = [...document.querySelectorAll('.slot[data-begin]')];
                // Exact start-time match only.
                const matching = slots.filter(s => parseInt(s.dataset.begin) === ts);
                const avCount  = matching.filter(s => s.classList.contains('av')).length;
                const sampleBegins = slots.slice(0, 8).map(s => parseInt(s.dataset.begin));
                const status   = matching.length === 0 ? 'no_slot'
                                 : avCount > 0 ? 'free' : 'busy';

                // Single-pass fallback scan: find the nearest free slot among offsets.
                let nextFreeTs = null;
                if (status !== 'free') {
                    for (const offsetMin of fallbackOffsets) {
                        const fbTs    = ts + offsetMin * 60;
                        const fbSlots = slots.filter(s => parseInt(s.dataset.begin) === fbTs);
                        const fbFree  = fbSlots.filter(s => s.classList.contains('av'));
                        if (fbFree.length > 0) {
                            nextFreeTs = fbTs;
                            break;
                        }
                    }
                }

                return {
                    total:        slots.length,
                    matching:     matching.length,
                    avCount:      avCount,
                    sampleBegins: sampleBegins,
                    status:       status,
                    nextFreeTs:   nextFreeTs,
                };
            }""",
            [target_ts, list(fallback_offsets)],
        )
        print(json.dumps({
            "event":          "etennis_scrape_result",
            "venue_id":       vid,
            "date":           dt.strftime("%Y-%m-%d"),
            "time":           dt.strftime("%H:%M"),
            "target_ts":      target_ts,
            "status":         result["status"],
            "total_slots":    result["total"],
            "matching_slots": result["matching"],
            "sample_begins":  result["sampleBegins"],
            "next_free_ts":   result["nextFreeTs"],
            "duration_ms":    round((time.monotonic() - t0) * 1000),
        }))
        return vid, result["status"], None, result["nextFreeTs"]
    except Exception as exc:
        print(f"[eTennis] {vid}  exception: {exc} — trying HTTP fallback")
        try:
            status, fallback_err, next_free_ts = await asyncio.to_thread(
                _http_scrape, url, target_ts, fallback_offsets
            )
            print(f"[eTennis] {vid}  HTTP fallback: {status}  err={fallback_err!r}")
            print(json.dumps({
                "event":        "etennis_scrape_result",
                "venue_id":     vid,
                "date":         dt.strftime("%Y-%m-%d"),
                "time":         dt.strftime("%H:%M"),
                "status":       status,
                "next_free_ts": next_free_ts,
                "duration_ms":  round((time.monotonic() - t0) * 1000),
                "via":          "http_fallback",
            }))
            return vid, status, fallback_err, next_free_ts
        except Exception as fallback_exc:
            print(f"[eTennis] {vid}  HTTP fallback also failed: {fallback_exc}")
        print(json.dumps({
            "event":       "etennis_scrape_result",
            "venue_id":    vid,
            "date":        dt.strftime("%Y-%m-%d"),
            "time":        dt.strftime("%H:%M"),
            "status":      "unknown",
            "duration_ms": round((time.monotonic() - t0) * 1000),
            "error":       f"{type(exc).__name__}: {exc}",
        }))
        return vid, "unknown", str(exc), None
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


_PER_VENUE_TIMEOUT = 90  # seconds — comfortably above goto(30s) + selector(20s) + eval


async def _run(venues: list[dict], dt: datetime) -> dict[str, str]:
    t0 = time.monotonic()
    print(json.dumps({
        "event":  "etennis_scraper_start",
        "venues": [v["id"] for v in venues],
        "date":   dt.strftime("%Y-%m-%d"),
        "time":   dt.strftime("%H:%M"),
    }))

    async with async_playwright() as pw:
        browser = None
        try:
            browser = await pw.chromium.launch(headless=True)
        except Exception as exc:
            print(json.dumps({
                "event": "etennis_browser_launch_failed",
                "error": f"{type(exc).__name__}: {exc}",
            }))
            return {v["id"]: "unknown" for v in venues}

        out: dict[str, str] = {}
        try:
            for venue in venues:
                # Use venue-specific offsets if configured; fall back to module default.
                fb_offsets: list[int] = venue.get("slot_fallback_minutes") or DEFAULT_FALLBACK_MINUTES
                try:
                    vid, status, err, next_free_ts = await asyncio.wait_for(
                        _check_one(browser, venue, dt, fallback_offsets=fb_offsets),
                        timeout=_PER_VENUE_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    vid, status, err, next_free_ts = (
                        venue["id"], "unknown", f"timeout_{_PER_VENUE_TIMEOUT}s", None
                    )
                    timeout_ms = _PER_VENUE_TIMEOUT * 1000
                    print(json.dumps({
                        "event":      "etennis_scrape_timeout",
                        "venue_id":   vid,
                        "date":       dt.strftime("%Y-%m-%d"),
                        "time":       dt.strftime("%H:%M"),
                        "timeout_ms": timeout_ms,
                    }))
                    track_scraper_timeout(venue_id=vid, platform="eTennis", timeout_ms=timeout_ms)
                if err:
                    print(f"[eTennis] {vid} error: {err}")
                out[vid] = status
                # Cache primary result together with next_free_ts in one atomic write.
                # next_free_ts was found in the same JS evaluate pass — no extra scrapes.
                _store_result(vid, status, dt, next_free_ts=next_free_ts)

        finally:
            try:
                await browser.close()
            except Exception:
                pass

    print(json.dumps({
        "event":       "etennis_scraper_done",
        "statuses":    out,
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
            out[venue["id"]] = "unknown"  # maps to check_failed in main.py
    return out


def get_cached_entries(venues: list[dict], dt: datetime) -> dict[str, dict]:
    """
    Like get_cached_statuses but returns the full cache entry per venue_id.
    Each entry contains {"status": str, "timestamp": float} and optionally
    {"next_free_ts": int} when a nearby free fallback slot was found.
    Cooldown venues are excluded (they have no entry to return).
    """
    now = time.time()
    out: dict[str, dict] = {}
    for venue in venues:
        key = _cache_key(venue["id"], dt)
        entry = _CACHE.get(key)
        if entry and now - entry["timestamp"] < _TTL:
            out[venue["id"]] = entry
    return out


def check_etennis_venues(venues: list[dict], dt: datetime) -> dict[str, str]:
    """
    Returns {venue_id: "free" | "busy" | "unknown"} for every eTennis venue.
    Runs Playwright in a dedicated thread with its own event loop so it works
    safely inside Flask (avoids event-loop conflicts with werkzeug).
    Results are cached per venue/date/hour for _TTL seconds.
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
            print(f"[eTennis] cache hit:  {venue['id']} -> {entry['status']}")
            cached[venue["id"]] = entry["status"]
        elif venue["id"] in _COOLDOWN and now - _COOLDOWN[venue["id"]] < _COOLDOWN_TTL:
            print(f"[eTennis] cooldown skip: {venue['id']}")
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
            print(f"[eTennis] scrape in-flight — returning {len(cached)} cached so far")
            return cached  # partial results; caller marks the rest as pending
        _RUNNING.add(scrape_key)

    def _run_in_thread():
        with _PLAYWRIGHT_SEM:  # blocks until any concurrent Playwright browser finishes
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_run(to_fetch, dt))  # writes cache per-venue
            except Exception as exc:
                print(f"[eTennis] thread-level error: {exc}")
            finally:
                loop.close()
                # Any venue not yet cached (e.g. thread killed mid-run) → cooldown
                store_ts = time.time()
                for v in to_fetch:
                    if _cache_key(v["id"], dt) not in _CACHE and v["id"] not in _COOLDOWN:
                        print(f"[eTennis] no result: {v['id']} -> unknown (thread exit)")
                        _COOLDOWN[v["id"]] = store_ts
                with _RUNNING_LOCK:
                    _RUNNING.discard(scrape_key)

    threading.Thread(target=_run_in_thread, daemon=True).start()
    # Return immediately — _run_in_thread writes results as they arrive;
    # the next request reads them from cache via get_cached_statuses.
    return cached
