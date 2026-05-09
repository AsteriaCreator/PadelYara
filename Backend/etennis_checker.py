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

from playwright.async_api import async_playwright

VIENNA_TZ = ZoneInfo("Europe/Vienna")

_CACHE: dict[str, dict] = {}
_TTL = 300  # seconds

_COOLDOWN: dict[str, float] = {}  # venue_id → timestamp of last unknown
_COOLDOWN_TTL = 60  # seconds

_RUNNING: set[str] = set()  # scrape keys currently in-flight
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


def _store_result(venue_id: str, status: str, dt: datetime) -> None:
    """Write one venue result to cache immediately — called per-venue as scraping completes."""
    store_ts = time.time()
    print(f"[eTennis] cached: {venue_id} -> {status}")
    if status == "unknown":
        _COOLDOWN[venue_id] = store_ts
    else:
        _CACHE[_cache_key(venue_id, dt)] = {"status": status, "timestamp": store_ts}
        _COOLDOWN.pop(venue_id, None)


async def _check_one(browser, venue: dict, dt: datetime) -> tuple[str, str, str | None]:
    url       = _page_url(venue["booking_url"], dt.date())
    target_ts = _target_ts(dt.date(), dt.hour)
    vid       = venue["id"]
    page      = None
    t0        = time.monotonic()
    print(f"[eTennis] {vid}  loading: {url[:100]}  target_ts={target_ts}")
    try:
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        title = await page.title()
        print(f"[eTennis] {vid}  page loaded, title={title!r}")

        try:
            await page.wait_for_selector(".slot[data-begin]", state="attached", timeout=20_000)
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
                const diagSlots = slots.slice(0, 5).map(s => ({
                    rawBegin:    s.dataset.begin,
                    parsedBegin: parseInt(s.dataset.begin),
                    dataSize:    s.dataset.size,
                    className:   s.className,
                }));
                return {
                    total:      slots.length,
                    matching:   matching.length,
                    avCount:    avCount,
                    status:     matching.length === 0 ? 'no_slot'
                                : avCount > 0 ? 'free' : 'busy',
                    diagSlots:  diagSlots,
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
        print(json.dumps({
            "event":          "etennis_scrape_result",
            "venue_id":       vid,
            "date":           dt.strftime("%Y-%m-%d"),
            "time":           dt.strftime("%H:%M"),
            "status":         result["status"],
            "total_slots":    result["total"],
            "matching_slots": result["matching"],
            "duration_ms":    round((time.monotonic() - t0) * 1000),
        }))
        # --- temporary diagnostic ---
        target_human = datetime.fromtimestamp(target_ts, tz=VIENNA_TZ).isoformat()
        print(f"[eTennis diag] {vid}  target_ts={target_ts}  ({target_human})")
        for i, slot in enumerate(result.get("diagSlots", [])):
            raw     = slot["rawBegin"]
            parsed  = slot["parsedBegin"]
            size    = slot.get("dataSize", "?")
            cls     = slot["className"]
            try:
                as_sec = datetime.fromtimestamp(parsed, tz=VIENNA_TZ).isoformat()
            except Exception:
                as_sec = "overflow"
            norm_ms = parsed // 1000 if parsed > 1_000_000_000_000 else None
            as_ms   = datetime.fromtimestamp(norm_ms, tz=VIENNA_TZ).isoformat() if norm_ms else "n/a"
            print(
                f"[eTennis diag]   slot[{i}]"
                f"  raw={raw!r}"
                f"  parsed={parsed}"
                f"  size={size!r}"
                f"  class={cls!r}"
                f"  as_sec={as_sec}"
                f"  norm_ms={norm_ms}  as_ms={as_ms}"
            )
        # --- end diagnostic ---
        return vid, result["status"], None
    except Exception as exc:
        print(f"[eTennis] {vid}  exception: {exc}")
        print(json.dumps({
            "event":       "etennis_scrape_result",
            "venue_id":    vid,
            "date":        dt.strftime("%Y-%m-%d"),
            "time":        dt.strftime("%H:%M"),
            "status":      "unknown",
            "duration_ms": round((time.monotonic() - t0) * 1000),
            "error":       f"{type(exc).__name__}: {exc}",
        }))
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
                _store_result(vid, status, dt)  # write to cache immediately, don't wait for full batch
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

    # Key covers ALL input venues so the in-flight check still matches even after
    # some venues have been individually cached (to_fetch shrinks; key must not).
    scrape_key = _scrape_key([v["id"] for v in venues], dt)

    with _RUNNING_LOCK:
        if scrape_key in _RUNNING:
            print(f"[eTennis] scrape in-flight — returning {len(cached)} cached so far")
            return cached  # partial results; caller marks the rest as pending
        _RUNNING.add(scrape_key)

    def _run_in_thread():
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
