"""
Eversports availability checker — production module.
Called by app.py; not a standalone server.

Cloudflare blocks headless Playwright, so we use a headed browser with
AutomationControlled disabled and navigator.webdriver hidden.
Cookies are accepted once per browser session and persist across venues.
"""

import asyncio
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

VIENNA_TZ = ZoneInfo("Europe/Vienna")

_CACHE: dict[str, dict] = {}
_TTL = 300  # 5 minutes

_COOLDOWN: dict[str, float] = {}
_COOLDOWN_TTL = 60  # 1 minute

_RUNNING: set[str] = set()
_RUNNING_LOCK = threading.Lock()

# Set to True to bypass in-memory cache and print full slot-level debug logs.
DEBUG_MODE = False


def _cache_key(venue_id: str, dt: datetime) -> str:
    return f"{venue_id}*{dt.strftime('%Y-%m-%d')}*{dt.strftime('%H:00')}"


def _scrape_key(venue_ids: list[str], dt: datetime) -> str:
    return "|".join(sorted(venue_ids)) + f"@{dt.strftime('%Y-%m-%dT%H:00')}"


def _parse_hhmm(hhmm: str) -> int:
    """'HHMM' string -> minutes since midnight. Returns -1 on parse error."""
    try:
        s = hhmm.strip()
        return int(s[:2]) * 60 + int(s[2:4] if len(s) >= 4 else 0)
    except (ValueError, IndexError):
        return -1


def _parse_status(html: str, date_str: str, target_hour: int, venue_id: str = "?") -> tuple[str, int, int]:
    """
    Parse DOM HTML for slot availability.

    Exact matching: finds <td data-date=DATE data-start=HHMM ...> elements.
    - data-date must equal date_str exactly
    - data-start must equal target_hour as "HHMM" (e.g. 19:00 -> "1900")
    - If any court has that exact slot with data-state="free" -> "free"
    - If exact slots exist but none are free -> "busy"
    - If no exact slot found -> "unknown"

    Returns (status, total_slot_tds, matching_slot_tds).
    """
    soup = BeautifulSoup(html, "html.parser")
    target_start = f"{target_hour:02d}00"

    all_tds = soup.find_all(
        "td",
        attrs={"data-state": True, "data-start": True, "data-date": True, "data-court": True},
    )

    if DEBUG_MODE:
        print(
            f"[Eversports][DEBUG] {venue_id}"
            f"  total slot tds={len(all_tds)}"
            f"  looking for date={date_str}  start={target_start}"
        )
        for td in all_tds:
            print(
                f"[Eversports][DEBUG]   td:"
                f" date={td.get('data-date')}"
                f" start={td.get('data-start')}"
                f" end={td.get('data-end')}"
                f" state={td.get('data-state')}"
                f" court={td.get('data-court')}"
                f" title={td.get('data-original-title')!r}"
            )

    matching = [
        td for td in all_tds
        if td.get("data-date") == date_str and td.get("data-start") == target_start
    ]

    if DEBUG_MODE:
        print(
            f"[Eversports][DEBUG] {venue_id}"
            f"  exact matches for {date_str} {target_start}: {len(matching)}"
        )
        for td in matching:
            print(
                f"[Eversports][DEBUG]   MATCH:"
                f" state={td.get('data-state')}"
                f" court={td.get('data-court')}"
                f" title={td.get('data-original-title')!r}"
            )

    if not matching:
        if DEBUG_MODE:
            print(f"[Eversports][DEBUG] {venue_id}  -> no exact slot found -> unknown")
        return "unknown", len(all_tds), 0

    if any(td.get("data-state") == "free" for td in matching):
        if DEBUG_MODE:
            print(f"[Eversports][DEBUG] {venue_id}  -> RESULT: free")
        return "free", len(all_tds), len(matching)

    if DEBUG_MODE:
        print(f"[Eversports][DEBUG] {venue_id}  -> RESULT: busy")
    return "busy", len(all_tds), len(matching)


async def _accept_cookies(page) -> bool:
    """Poll for a cookie consent button and click it. Returns True if clicked."""
    selectors = [
        "button:has-text('Auswahl erlauben')",
        "button:has-text('Alle akzeptieren')",
        "button:has-text('Akzeptieren')",
        "button:has-text('Accept')",
    ]
    for _ in range(20):        # up to ~10 s
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=400):
                    await btn.click(timeout=2_000)
                    return True
            except Exception:
                pass
        await asyncio.sleep(0.5)
    return False


async def _check_one(
    ctx,
    venue: dict,
    dt: datetime,
    cookies_accepted: list[bool],
    attempt: int = 1,
) -> tuple[str, str, str | None]:
    t0 = time.monotonic()
    date_str = dt.strftime("%Y-%m-%d")
    url = f"{venue['booking_url']}?date={date_str}"
    vid = venue["id"]
    page = None

    print(f"[Eversports] {vid}  attempt={attempt}  target={date_str} {dt.hour:02d}:00")

    # Event fires when /api/slot is first seen; last_time tracks the most recent hit
    slot_api_event = asyncio.Event()
    slot_api_last: list[float] = [0.0]
    slot_api_count: list[int] = [0]

    async def on_response(resp):
        # Accept any HTTP status — 304 Not Modified is a valid cached hit
        if "/api/slot" in resp.url:
            slot_api_last[0] = time.monotonic()
            slot_api_count[0] += 1
            slot_api_event.set()
            print(
                f"[Eversports] {vid}"
                f"  /api/slot #{slot_api_count[0]}"
                f"  status={resp.status}"
                f"  url={resp.url[:80]}"
            )

    try:
        page = await ctx.new_page()
        page.on("response", on_response)

        # /api/booking/calendar/update always returns all slots as state=free —
        # it is the opening-hours skeleton.  The real booking status arrives via
        # /api/slot whose response triggers JS to rewrite data-state in the DOM.
        try:
            await page.goto(url, wait_until="load", timeout=45_000)
        except Exception:
            pass    # load timeout is fine; the page HTML is still usable

        # Accept cookies once — they persist in the shared browser context
        if not cookies_accepted[0]:
            clicked = await _accept_cookies(page)
            if clicked:
                cookies_accepted[0] = True
                print(f"[Eversports] {vid}  cookies accepted, awaiting reload")
                try:
                    await page.wait_for_load_state("load", timeout=8_000)
                except Exception:
                    await asyncio.sleep(2)

        # Wait up to 25s for the first /api/slot response
        try:
            await asyncio.wait_for(slot_api_event.wait(), timeout=25.0)
        except asyncio.TimeoutError:
            # Fallback: if the browser used a cached response no network event fires,
            # but the DOM may already contain correct slot data — check before giving up.
            dom_html = await page.content()
            soup = BeautifulSoup(dom_html, "html.parser")
            fallback_tds = soup.find_all(
                "td",
                attrs={"data-state": True, "data-start": True, "data-date": True, "data-court": True},
            )
            elapsed = time.monotonic() - t0
            if fallback_tds:
                print(
                    f"[Eversports] {vid}"
                    f"  /api/slot never fired but DOM has {len(fallback_tds)} slots"
                    f"  (likely browser cache) — parsing anyway"
                    f"  elapsed={elapsed:.1f}s"
                )
                status, total, matched = _parse_status(dom_html, date_str, dt.hour, venue_id=vid)
                print(f"[Eversports] {vid}  slots={total} matches={matched} result={status} time={elapsed:.1f}s")
                return vid, status, None
            else:
                print(
                    f"[Eversports] {vid}"
                    f"  /api/slot never fired, no slots in DOM"
                    f"  elapsed={elapsed:.1f}s -> unknown"
                )
                return vid, "unknown", "slot API never fired"

        # Wait for "quiet": no new /api/slot calls for 1.5s, bounded at 6s from first.
        # This handles venues with multiple sequential /api/slot calls (one per court group).
        first_slot_time = slot_api_last[0]
        while True:
            await asyncio.sleep(0.2)
            since_last = time.monotonic() - slot_api_last[0]
            since_first = time.monotonic() - first_slot_time
            if since_last >= 1.5 or since_first >= 6.0:
                break

        dom_html = await page.content()
        elapsed = time.monotonic() - t0
        status, total, matched = _parse_status(dom_html, date_str, dt.hour, venue_id=vid)
        print(
            f"[Eversports] {vid}"
            f"  slots={total} matches={matched} result={status}"
            f"  api_calls={slot_api_count[0]} time={elapsed:.1f}s"
        )
        return vid, status, None

    except Exception as exc:
        elapsed = time.monotonic() - t0
        print(f"[Eversports] {vid}  exception after {elapsed:.1f}s: {exc}")
        return vid, "unknown", str(exc)
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def _check_one_with_retry(
    ctx,
    venue: dict,
    dt: datetime,
    cookies_accepted: list[bool],
) -> tuple[str, str, str | None]:
    """Run _check_one; if the first attempt returns 'unknown', retry once."""
    vid, status, err = await _check_one(ctx, venue, dt, cookies_accepted, attempt=1)
    if status == "unknown":
        print(f"[Eversports] {venue['id']}  first attempt unknown -> retrying")
        vid, status, err = await _check_one(ctx, venue, dt, cookies_accepted, attempt=2)
        print(f"[Eversports] {venue['id']}  retry result -> {status}")
    return vid, status, err


async def _run(venues: list[dict], dt: datetime) -> dict[str, str]:
    async with async_playwright() as pw:
        # Prefer system Chrome/Edge; headless Playwright Chromium is blocked by Cloudflare
        browser = None
        for channel in ("chrome", "msedge", None):
            try:
                kwargs: dict = {
                    "headless": True,
                    "args": ["--disable-blink-features=AutomationControlled"],
                }
                if channel:
                    kwargs["channel"] = channel
                browser = await pw.chromium.launch(**kwargs)
                break
            except Exception:
                pass

        if browser is None:
            return {v["id"]: "unknown" for v in venues}

        ctx = await browser.new_context(
            locale="de-AT",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            extra_http_headers={"Accept-Language": "de-AT,de;q=0.9,en;q=0.8"},
            viewport={"width": 1400, "height": 900},
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        cookies_accepted: list[bool] = [False]
        results = []
        for venue in venues:
            r = await _check_one_with_retry(ctx, venue, dt, cookies_accepted)
            results.append(r)

        await browser.close()

    out: dict[str, str] = {}
    for r in results:
        venue_id, status, err = r
        if err:
            print(f"[Eversports] {venue_id} error: {err}")
        out[venue_id] = status
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


def check_eversports_venues(venues: list[dict], dt: datetime) -> dict[str, str]:
    """
    Returns {venue_id: "free" | "busy" | "unknown"} for every Eversports venue.

    One browser session checks all venues sequentially so the cookie consent
    is accepted only once.  Results cached per venue/date/hour for 5 minutes.
    """
    if not venues:
        return {}

    now = time.time()
    cached: dict[str, str] = {}
    to_fetch: list[dict] = []

    for venue in venues:
        key   = _cache_key(venue["id"], dt)
        entry = _CACHE.get(key)
        if not DEBUG_MODE and entry and now - entry["timestamp"] < _TTL:
            print(f"[Eversports] cache hit:  {venue['id']} -> {entry['status']}")
            cached[venue["id"]] = entry["status"]
        elif not DEBUG_MODE and venue["id"] in _COOLDOWN and now - _COOLDOWN[venue["id"]] < _COOLDOWN_TTL:
            print(f"[Eversports] cooldown:   {venue['id']}")
            cached[venue["id"]] = "unknown"
        else:
            if DEBUG_MODE and entry:
                print(f"[Eversports][DEBUG] {venue['id']}  bypassing cache (DEBUG_MODE)")
            to_fetch.append(venue)

    if not to_fetch:
        return cached

    scrape_key = _scrape_key([v["id"] for v in to_fetch], dt)

    with _RUNNING_LOCK:
        if scrape_key in _RUNNING:
            print(f"[Eversports] scrape already in-flight for {scrape_key[:60]} — skipping")
            return {**cached, **{v["id"]: "unknown" for v in to_fetch}}
        _RUNNING.add(scrape_key)

    fresh: dict[str, str] = {}

    def _run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            fresh.update(loop.run_until_complete(_run(to_fetch, dt)))
        except Exception as exc:
            print(f"[Eversports] thread-level error: {exc}")
        finally:
            loop.close()
            with _RUNNING_LOCK:
                _RUNNING.discard(scrape_key)

    # Sequential venue checks + one retry per venue -> generous timeout
    t = threading.Thread(target=_run_in_thread, daemon=True)
    t.start()
    t.join(timeout=120 * len(to_fetch))

    store_ts = time.time()  # fresh timestamp after join — avoids stale-cooldown bug
    for venue_id, status in fresh.items():
        print(f"[Eversports] fetched:    {venue_id} -> {status}")
        if status == "unknown":
            _COOLDOWN[venue_id] = store_ts
        else:
            _CACHE[_cache_key(venue_id, dt)] = {"status": status, "timestamp": store_ts}

    # Any venue in to_fetch missing from fresh (thread crash / timeout) -> unknown + cooldown
    for venue in to_fetch:
        if venue["id"] not in fresh:
            print(f"[Eversports] no result:  {venue['id']} -> unknown (cooldown)")
            _COOLDOWN[venue["id"]] = store_ts
            fresh[venue["id"]] = "unknown"

    return {**cached, **fresh}
