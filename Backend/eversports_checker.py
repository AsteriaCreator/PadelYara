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

_BOOKING_HOURS = 2  # minimum booking window to check


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


def _parse_status(html: str, date_str: str, target_hour: int) -> str:
    """
    Parse /api/booking/calendar/update HTML response.

    A venue is 'free' when at least one court has its entire
    [target_hour:00, target_hour + 2h) window covered by consecutive
    free slots.  Any gap or 'booked' slot within the window -> that court
    is skipped.

    Returns 'free', 'busy', or 'unknown'.
    """
    soup = BeautifulSoup(html, "html.parser")
    tbody = soup.find("tbody", attrs={"data-date": date_str})
    if not tbody:
        return "unknown"

    # Collect slots per court: {court_id: [(start_min, end_min, state)]}
    by_court: dict[str, list[tuple[int, int, str]]] = {}
    for td in tbody.find_all(
        attrs={"data-start": True, "data-state": True, "data-court": True}
    ):
        start = _parse_hhmm(td.get("data-start", ""))
        end   = _parse_hhmm(td.get("data-end", ""))
        if start < 0:
            continue
        if end <= start:        # fallback: assume 60-min slot
            end = start + 60
        court = td["data-court"]
        state = td["data-state"]
        by_court.setdefault(court, []).append((start, end, state))

    if not by_court:
        return "unknown"

    window_start = target_hour * 60
    window_end   = window_start + _BOOKING_HOURS * 60

    for court, slots in by_court.items():
        # Slots that start within the 2-hour window
        window = [(s, e, st) for s, e, st in slots
                  if window_start <= s < window_end]
        if not window:
            continue
        if not all(st == "free" for _, _, st in window):
            continue

        # Verify the free slots cover the full window without gaps
        window.sort(key=lambda x: x[0])
        coverage = window_start
        for s, e, _ in window:
            if s > coverage:
                break       # gap before this slot
            coverage = max(coverage, e)

        if coverage >= window_end:
            return "free"

    return "busy"


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
    cookies_accepted: list[bool],   # mutable flag shared across calls
) -> tuple[str, str, str | None]:
    date_str = dt.strftime("%Y-%m-%d")
    url      = f"{venue['booking_url']}?date={date_str}"
    page     = None

    try:
        page = await ctx.new_page()
        calendar_html: list[str] = []

        async def on_response(resp):
            if "/api/booking/calendar/update" in resp.url and resp.status == 200:
                try:
                    calendar_html.append(await resp.text())
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            await page.goto(url, wait_until="load", timeout=45_000)
        except Exception:
            pass    # load timeout is fine; the page HTML is still usable

        # Accept cookies once — they persist in the shared browser context
        if not cookies_accepted[0]:
            clicked = await _accept_cookies(page)
            if clicked:
                cookies_accepted[0] = True
                await asyncio.sleep(2)  # give the page time to reload calendar

        # Wait up to 20 s for the intercepted calendar response
        for _ in range(20):
            if calendar_html:
                break
            await asyncio.sleep(1)

        # Fallback: trigger calendar update via JS if page didn't fire it
        if not calendar_html:
            try:
                await page.evaluate(
                    "() => { if (typeof updateCalendar === 'function') updateCalendar(); }"
                )
                for _ in range(10):
                    if calendar_html:
                        break
                    await asyncio.sleep(1)
            except Exception:
                pass

        if not calendar_html:
            return venue["id"], "unknown", "no calendar response"

        status = _parse_status(calendar_html[-1], date_str, dt.hour)
        return venue["id"], status, None

    except Exception as exc:
        return venue["id"], "unknown", str(exc)
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def _run(venues: list[dict], dt: datetime) -> dict[str, str]:
    async with async_playwright() as pw:
        # Prefer system Chrome/Edge; headless Playwright Chromium is blocked by Cloudflare
        browser = None
        for channel in ("chrome", "msedge", None):
            try:
                kwargs: dict = {
                    "headless": False,
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
            r = await _check_one(ctx, venue, dt, cookies_accepted)
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
        if entry and now - entry["timestamp"] < _TTL:
            print(f"[Eversports] cache hit:  {venue['id']} -> {entry['status']}")
            cached[venue["id"]] = entry["status"]
        elif venue["id"] in _COOLDOWN and now - _COOLDOWN[venue["id"]] < _COOLDOWN_TTL:
            print(f"[Eversports] cooldown:   {venue['id']}")
            cached[venue["id"]] = "unknown"
        else:
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

    # Sequential venue checks -> longer timeout than eTennis
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
