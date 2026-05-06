"""
eTennis availability checker — production module.
Called by app.py; not a standalone server.
"""

import asyncio
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

VIENNA_TZ = ZoneInfo("Europe/Vienna")

_CACHE: dict[str, dict] = {}
_TTL = 300  # seconds

_COOLDOWN: dict[str, float] = {}  # venue_id → timestamp of last unknown
_COOLDOWN_TTL = 60  # seconds

_RUNNING: dict[str, threading.Event] = {}  # scrape key → completion event
_RUNNING_LOCK = threading.Lock()


def _cache_key(venue_id: str, dt: datetime) -> str:
    return f"{venue_id}*{dt.strftime('%Y-%m-%d')}*{dt.strftime('%H:00')}"


def _scrape_key(venue_ids: list[str], dt: datetime) -> str:
    """Stable key for a set of venues at a given date+hour, used to deduplicate in-flight scrapes."""
    return "|".join(sorted(venue_ids)) + f"@{dt.strftime('%Y-%m-%dT%H:00')}"


def _page_url(booking_url: str, date) -> str:
    # Use Vienna midnight — eTennis slot data-begin values are also Vienna-based
    ts = int(datetime(date.year, date.month, date.day, tzinfo=VIENNA_TZ).timestamp())
    return f"{booking_url}&t={ts}"


def _target_ts(date, hour: int) -> int:
    return int(datetime(date.year, date.month, date.day, hour, tzinfo=VIENNA_TZ).timestamp())


async def _check_one(browser, venue: dict, dt: datetime) -> tuple[str, str, str | None]:
    url       = _page_url(venue["booking_url"], dt.date())
    target_ts = _target_ts(dt.date(), dt.hour)
    vid       = venue["id"]
    page      = None
    print(f"[eTennis] {vid}  loading: {url[:100]}  target_ts={target_ts}")
    try:
        page = await browser.new_page()
        await page.goto(url, wait_until="commit", timeout=30_000)
        title = await page.title()
        print(f"[eTennis] {vid}  page loaded, title={title!r}")

        try:
            await page.wait_for_selector(".slot[data-begin]", timeout=10_000)
        except Exception as sel_exc:
            # Selector not found — log what the page actually contains
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
            return vid, "unknown", f"selector timeout: {sel_exc}"

        result = await page.evaluate(
            """(ts) => {
                const slots    = [...document.querySelectorAll('.slot[data-begin]')];
                const matching = slots.filter(s => {
                    const begin = parseInt(s.dataset.begin);
                    const size  = parseFloat(s.dataset.size || '1');
                    return begin <= ts && ts < begin + size * 3600;
                });
                const avCount = matching.filter(s => s.classList.contains('av')).length;
                return {
                    total:    slots.length,
                    matching: matching.length,
                    avCount:  avCount,
                    status:   matching.length === 0 ? 'no_slot'
                              : avCount > 0 ? 'free' : 'busy'
                };
            }""",
            target_ts,
        )
        print(
            f"[eTennis] {vid}"
            f"  total_slots={result['total']}"
            f"  matching={result['matching']}"
            f"  av={result['avCount']}"
            f"  result={result['status']}"
        )
        return vid, result["status"], None
    except Exception as exc:
        print(f"[eTennis] {vid}  exception: {exc}")
        return vid, "unknown", str(exc)
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def _run(venues: list[dict], dt: datetime) -> dict[str, str]:
    async with async_playwright() as pw:
        browser = None
        try:
            browser = await pw.chromium.launch(headless=True)
        except Exception as exc:
            print(f"[eTennis] browser launch failed: {exc}")
            return {v["id"]: "unknown" for v in venues}

        out: dict[str, str] = {}
        try:
            for venue in venues:
                vid, status, err = await _check_one(browser, venue, dt)
                if err:
                    print(f"[eTennis] {vid} error: {err}")
                out[vid] = status
        finally:
            try:
                await browser.close()
            except Exception:
                pass
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

    scrape_key = _scrape_key([v["id"] for v in to_fetch], dt)

    with _RUNNING_LOCK:
        if scrape_key in _RUNNING:
            existing_event = _RUNNING[scrape_key]
            in_flight = True
        else:
            done_event = threading.Event()
            _RUNNING[scrape_key] = done_event
            in_flight = False

    if in_flight:
        print(f"[eTennis] scrape in-flight for {scrape_key[:60]} — waiting up to 15s")
        existing_event.wait(timeout=15)
        now2 = time.time()
        waited: dict[str, str] = {}
        for venue in to_fetch:
            key = _cache_key(venue["id"], dt)
            entry = _CACHE.get(key)
            if entry and now2 - entry["timestamp"] < _TTL:
                waited[venue["id"]] = entry["status"]
            else:
                waited[venue["id"]] = "unknown"
        return {**cached, **waited}

    fresh: dict[str, str] = {}

    def _run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            fresh.update(loop.run_until_complete(_run(to_fetch, dt)))
        except Exception as exc:
            print(f"[eTennis] thread-level error: {exc}")
        finally:
            loop.close()

    t = threading.Thread(target=_run_in_thread, daemon=True)
    t.start()
    t.join(timeout=120)

    store_ts = time.time()  # fresh timestamp after join — avoids stale-cooldown bug
    for venue_id, status in fresh.items():
        print(f"[eTennis] fetched:    {venue_id} -> {status}")
        if status == "unknown":
            _COOLDOWN[venue_id] = store_ts
        else:
            _CACHE[_cache_key(venue_id, dt)] = {"status": status, "timestamp": store_ts}
            _COOLDOWN.pop(venue_id, None)

    # Venues not returned by scraper (thread timeout) → unknown + cooldown
    for venue in to_fetch:
        if venue["id"] not in fresh:
            print(f"[eTennis] no result: {venue['id']} -> unknown (timeout)")
            _COOLDOWN[venue["id"]] = store_ts

    # Signal completion AFTER cache is populated so waiting callers see fresh data
    with _RUNNING_LOCK:
        _RUNNING.pop(scrape_key, None)
    done_event.set()

    return {**cached, **fresh}
