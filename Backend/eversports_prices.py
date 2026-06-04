"""
Eversports price scraper.

Uses Playwright to load each Eversports booking page and extract
data-price attributes from the server-rendered calendar HTML.
Runs once every 12 hours per venue in a background daemon thread.

Price data is server-rendered (not loaded via AJAX), so a plain page
load is enough — no CSRF or session dance needed.

Usage in app.py:
    import eversports_prices
    eversports_prices.refresh_prices(VENUES)     # call at startup
    price = eversports_prices.get_price(venue_id, "2026-06-10", "1800")
"""

import asyncio
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.async_api import TimeoutError as PWTimeout
from playwright.async_api import async_playwright

VIENNA_TZ = ZoneInfo("Europe/Vienna")

_TTL = 43_200           # 12 h — re-scrape each venue twice a day
_PW_TIMEOUT = 45_000    # ms — page load timeout

_PW_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
]
_PW_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Cache: venue_id → {"slots": [{date, start, price}], "scraped_at": monotonic}
_PRICE_CACHE: dict[str, dict] = {}
_PRICE_LOCK = threading.Lock()


async def _scrape_venue_async(venue: dict) -> list[dict]:
    """
    Open the booking page in headless Chromium and extract all
    td[data-date][data-start][data-price] elements from the DOM.

    Returns a list of {date, start, price} dicts, or [] on failure.
    """
    url  = venue.get("booking_url", "")
    vid  = venue["id"]
    if not url:
        return []

    print(json.dumps({"event": "ev_price_scrape_start", "venue_id": vid, "url": url}))
    t0 = time.monotonic()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=_PW_ARGS)
        try:
            context = await browser.new_context(
                user_agent=_PW_UA,
                viewport={"width": 1280, "height": 800},
                locale="de-AT",
                extra_http_headers={"Accept-Language": "de-AT,de;q=0.9,en;q=0.8"},
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=_PW_TIMEOUT)
            except Exception as exc:
                print(json.dumps({
                    "event": "ev_price_goto_failed", "venue_id": vid, "error": str(exc)
                }))
                return []

            # Wait for server-rendered price cells — no AJAX needed
            try:
                await page.wait_for_selector("td[data-price]", timeout=10_000)
            except PWTimeout:
                # Page loaded but no price cells — check if it's a CF challenge
                body_snippet = await page.evaluate(
                    "() => document.body?.innerText?.slice(0, 200) || ''"
                )
                print(json.dumps({
                    "event":        "ev_price_no_cells",
                    "venue_id":     vid,
                    "body_snippet": body_snippet,
                }))
                return []

            slots: list[dict] = await page.evaluate("""
                () => [...document.querySelectorAll(
                    'td[data-date][data-start][data-price]'
                )].map(td => ({
                    date:  td.dataset.date,
                    start: td.dataset.start,
                    price: parseInt(td.dataset.price),
                    state: td.dataset.state ?? null,
                })).filter(s => s.date && s.start && !isNaN(s.price))
            """)

            unique_prices = sorted(set(s["price"] for s in slots))
            print(json.dumps({
                "event":       "ev_price_scrape_done",
                "venue_id":    vid,
                "slot_count":  len(slots),
                "prices":      unique_prices,
                "duration_ms": round((time.monotonic() - t0) * 1000),
            }))
            return slots

        finally:
            try:
                await browser.close()
            except Exception:
                pass


_STAGGER_SECONDS = 30  # delay between venue scrapes
_ASYNC_SEM = asyncio.Semaphore(1)  # one Playwright browser at a time


async def _scrape_and_cache(venue: dict) -> None:
    async with _ASYNC_SEM:
        slots = await _scrape_venue_async(venue)
        if slots:
            with _PRICE_LOCK:
                _PRICE_CACHE[venue["id"]] = {
                    "slots":      slots,
                    "scraped_at": time.monotonic(),
                }


async def refresh_prices_async(venues: list[dict]) -> None:
    """
    Async background task — scrape all stale Eversports venues with a stagger
    delay.  Call via asyncio.create_task() so it runs in the main event loop.
    """
    print(json.dumps({"event": "ev_price_refresh_called", "venue_count": len(venues)}))
    ev_venues = [
        v for v in venues
        if v.get("platform") == "Eversports"
        and v.get("booking_url")
        and not v.get("issues")
    ]
    now = time.monotonic()
    stale = [
        v for v in ev_venues
        if not (
            (entry := _PRICE_CACHE.get(v["id"]))
            and now - entry["scraped_at"] < _TTL
        )
    ]
    print(json.dumps({"event": "ev_price_stale_venues", "stale": [v["id"] for v in stale]}))
    for i, venue in enumerate(stale):
        if i > 0:
            await asyncio.sleep(_STAGGER_SECONDS)
        print(json.dumps({
            "event": "ev_price_refresh_queued", "venue_id": venue["id"],
            "index": i, "total": len(stale),
        }))
        await _scrape_and_cache(venue)


def get_price(venue_id: str, date_str: str, time_hhmm: str) -> int | None:
    """
    Return the price (€) for venue at date+time, or None if unknown.

    Lookup order:
      1. Exact date + time match (most accurate)
      2. Same day-of-week + time from cached week (prices repeat weekly)
    """
    with _PRICE_LOCK:
        entry = _PRICE_CACHE.get(venue_id)
    if not entry:
        return None

    slots = entry["slots"]

    # 1. Exact match
    for s in slots:
        if s["date"] == date_str and s["start"] == time_hhmm:
            return s["price"]

    # 2. Same day-of-week + time
    try:
        target_dow = datetime.strptime(date_str, "%Y-%m-%d").weekday()
        for s in slots:
            if datetime.strptime(s["date"], "%Y-%m-%d").weekday() == target_dow \
                    and s["start"] == time_hhmm:
                return s["price"]
    except (ValueError, KeyError):
        pass

    return None
