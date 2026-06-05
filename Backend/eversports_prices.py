"""
Eversports price scraper.

POSTs to /api/booking/calendar/update (no CF block, no CSRF needed when
sport[] params are included) and parses td[data-price] from the HTML.
No Playwright — just a curl_cffi POST, same pattern as eversports_service.py.

Padel sport params are global constants on Eversports:
  sport[id]=978  sport[slug]=padel  sport[uuid]=b388f5e3-...

Usage in app.py:
    import eversports_prices
    # triggered lazily on first search with Eversports venues
    price = eversports_prices.get_price(venue_id, "2026-06-10", "1800")
"""

import asyncio
import re
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from curl_cffi.requests import AsyncSession

VIENNA_TZ = ZoneInfo("Europe/Vienna")

_TTL            = 43_200   # 12 h
_STAGGER_SECS   = 30       # delay between venues
_CAL_URL        = "https://www.eversports.at/api/booking/calendar/update"

# Padel sport constants — same across all Eversports padel venues
_PADEL_SPORT = {
    "sport[id]":   "978",
    "sport[slug]": "padel",
    "sport[name]": "Padel",
    "sport[uuid]": "b388f5e3-69de-11e8-bdc6-02bd505aa7b2",
}

# Cache: venue_id → {"slots": [{date, start, price}], "scraped_at": monotonic}
_PRICE_CACHE: dict[str, dict] = {}
_PRICE_LOCK  = threading.Lock()

# Prevent spawning duplicate refresh tasks
_refresh_running = False
_refresh_lock    = asyncio.Lock()


async def _fetch_venue_prices(venue: dict) -> list[dict]:
    """
    POST to /api/booking/calendar/update with padel sport params and parse
    td[data-price] from the returned HTML. Returns list of slot dicts.
    """
    vid         = venue["id"]
    facility_id = venue.get("eversports_facility_id")
    booking_url = venue.get("booking_url", "")
    slug        = booking_url.rstrip("/").split("/")[-1]

    if not facility_id:
        print(f"[ev-prices] skip  venue={vid}  reason=no_facility_id")
        return []

    date_str = datetime.now(VIENNA_TZ).strftime("%Y-%m-%d")

    post_data = {
        "facilityId":   str(facility_id),
        "facilitySlug": slug,
        "date":         date_str,
        "type":         "user",
        **_PADEL_SPORT,
    }

    print(f"[ev-prices] post_start  venue={vid}  facility={facility_id}  date={date_str}")
    try:
        async with AsyncSession(impersonate="chrome124") as session:
            r = await session.post(
                _CAL_URL,
                data=post_data,
                headers={
                    "Content-Type":     "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept":           "*/*",
                    "Accept-Language":  "de-AT,de;q=0.9,en;q=0.8",
                    "Origin":           "https://www.eversports.at",
                    "Referer":          booking_url,
                },
                timeout=20,
            )

        has_td = "<td" in r.text
        print(f"[ev-prices] post_response  venue={vid}  status={r.status_code}  has_td={has_td}  body[:80]={r.text[:80]!r}")

        if r.status_code != 200 or not has_td:
            return []

        # Parse td[data-date][data-start][data-price] elements
        slots: list[dict] = []
        for m in re.finditer(r"<td\b([^>]*)>", r.text, re.IGNORECASE):
            attrs = m.group(1)
            d  = re.search(r'data-date="([^"]*)"',  attrs)
            s  = re.search(r'data-start="([^"]*)"', attrs)
            p  = re.search(r'data-price="([^"]*)"', attrs)
            if d and s and p and p.group(1).isdigit():
                slots.append({
                    "date":  d.group(1),
                    "start": s.group(1),
                    "price": int(p.group(1)),
                })

        prices = sorted(set(sl["price"] for sl in slots))
        print(f"[ev-prices] parsed  venue={vid}  slots={len(slots)}  prices={prices}")
        return slots

    except Exception as exc:
        print(f"[ev-prices] post_exception  venue={vid}  error={exc}")
        return []


async def refresh_prices_async(venues: list[dict]) -> None:
    """
    Async background task — scrape prices for all stale Eversports venues
    with a stagger delay. Use asyncio.create_task() to run in background.
    Deduplication: only one refresh runs at a time.
    """
    global _refresh_running
    async with _refresh_lock:
        if _refresh_running:
            print("[ev-prices] refresh already in progress — skipping")
            return
        _refresh_running = True

    try:
        print(f"[ev-prices] refresh_start  total_venues={len(venues)}")
        ev_venues = [
            v for v in venues
            if v.get("platform") == "Eversports"
            and v.get("booking_url")
            and not v.get("issues")
            and v.get("eversports_facility_id")
        ]
        now = time.monotonic()
        stale = [
            v for v in ev_venues
            if not (
                (entry := _PRICE_CACHE.get(v["id"]))
                and now - entry["scraped_at"] < _TTL
            )
        ]
        print(f"[ev-prices] stale={[v['id'] for v in stale]}")

        for i, venue in enumerate(stale):
            if i > 0:
                await asyncio.sleep(_STAGGER_SECS)
            print(f"[ev-prices] scraping  venue={venue['id']}  {i+1}/{len(stale)}")
            slots = await _fetch_venue_prices(venue)
            if slots:
                with _PRICE_LOCK:
                    _PRICE_CACHE[venue["id"]] = {
                        "slots":      slots,
                        "scraped_at": time.monotonic(),
                    }
    finally:
        global _refresh_running
        _refresh_running = False
        print("[ev-prices] refresh_done")


def get_price(venue_id: str, date_str: str, time_hhmm: str) -> int | None:
    """
    Return the price (€) for venue at date+time, or None if unknown.
    1. Exact date + time match
    2. Same day-of-week + time (prices repeat weekly)
    """
    with _PRICE_LOCK:
        entry = _PRICE_CACHE.get(venue_id)
    if not entry:
        return None

    slots = entry["slots"]

    for s in slots:
        if s["date"] == date_str and s["start"] == time_hhmm:
            return s["price"]

    try:
        target_dow = datetime.strptime(date_str, "%Y-%m-%d").weekday()
        for s in slots:
            if datetime.strptime(s["date"], "%Y-%m-%d").weekday() == target_dow \
                    and s["start"] == time_hhmm:
                return s["price"]
    except (ValueError, KeyError):
        pass

    return None
