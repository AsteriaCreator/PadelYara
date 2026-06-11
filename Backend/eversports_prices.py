"""
Eversports price scraper.

POSTs to /api/booking/calendar/update (no CF block, no CSRF needed when
sport[] params are included) and parses td[data-price] from the HTML.
No Playwright — just a curl_cffi POST, same pattern as eversports_service.py.

Padel sport params are global constants on Eversports:
  sport[id]=978  sport[slug]=padel  sport[uuid]=b388f5e3-...

Usage in app.py:
    import eversports_prices
    # at startup:
    eversports_prices.init_mongo(os.getenv("MONGODB_URI"))
    await eversports_prices.load_cache_from_mongo()
    # triggered lazily on first search with Eversports venues:
    price = eversports_prices.get_price(venue_id, "2026-06-10", "1800")
"""

import asyncio
import re
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from curl_cffi.requests import AsyncSession

VIENNA_TZ = ZoneInfo("Europe/Vienna")

_TTL            = 43_200   # 12 h in-memory TTL
_MONGO_TTL      = 86_400   # 24 h — discard MongoDB entries older than this
_STAGGER_SECS   = 30       # delay between venues
_CAL_URL        = "https://www.eversports.at/api/booking/calendar/update"

# Padel sport constants — same across all Eversports padel venues
_PADEL_SPORT = {
    "sport[id]":   "978",
    "sport[slug]": "padel",
    "sport[name]": "Padel",
    "sport[uuid]": "b388f5e3-69de-11e8-bdc6-02bd505aa7b2",
}

# In-memory cache: venue_id → {"slots": [{date, start, price}], "scraped_at": monotonic}
_PRICE_CACHE: dict[str, dict] = {}
_PRICE_LOCK  = threading.Lock()

# Prevent spawning duplicate refresh tasks
_refresh_running = False
_refresh_lock    = asyncio.Lock()

# MongoDB — initialised by init_mongo()
_mongo_db = None


def init_mongo(uri: str) -> None:
    """Call once at startup with the MONGODB_URI."""
    global _mongo_db  # noqa: PLW0603
    if not uri:
        print("[ev-prices] MONGODB_URI not set — price cache will not persist across restarts")
        return
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        _mongo_db = AsyncIOMotorClient(uri)["padel_checker"]
        print("[ev-prices] MongoDB client initialised for price cache persistence")
    except Exception as exc:
        print(f"[ev-prices] MongoDB init failed: {exc} — prices will not persist")


async def load_cache_from_mongo() -> None:
    """
    Load persisted price data from MongoDB into _PRICE_CACHE on startup.
    Skips entries older than _MONGO_TTL seconds so stale prices don't survive forever.
    """
    if _mongo_db is None:
        return
    try:
        col = _mongo_db["eversports_price_cache"]
        cutoff = datetime.now(timezone.utc).timestamp() - _MONGO_TTL
        loaded = 0
        async for doc in col.find({}):
            scraped_at_dt = doc.get("scraped_at")
            if scraped_at_dt is None:
                continue
            # motor returns datetime objects (naive UTC or timezone-aware)
            if hasattr(scraped_at_dt, "timestamp"):
                scraped_ts = scraped_at_dt.timestamp()
            else:
                continue
            if scraped_ts < cutoff:
                continue  # too old
            venue_id = doc.get("venue_id")
            slots    = doc.get("slots", [])
            if not venue_id or not slots:
                continue
            # Convert wall-clock age to monotonic for in-memory TTL check
            age_secs = datetime.now(timezone.utc).timestamp() - scraped_ts
            with _PRICE_LOCK:
                _PRICE_CACHE[venue_id] = {
                    "slots":      slots,
                    "scraped_at": time.monotonic() - age_secs,
                }
            loaded += 1
        print(f"[ev-prices] loaded {loaded} venue price entries from MongoDB")
    except Exception as exc:
        print(f"[ev-prices] load_cache_from_mongo failed: {exc}")


async def _save_venue_to_mongo(venue_id: str, slots: list[dict]) -> None:
    """Upsert scraped price slots for one venue into MongoDB."""
    if _mongo_db is None:
        return
    try:
        col = _mongo_db["eversports_price_cache"]
        await col.update_one(
            {"venue_id": venue_id},
            {"$set": {
                "venue_id":   venue_id,
                "scraped_at": datetime.now(timezone.utc),
                "slots":      slots,
            }},
            upsert=True,
        )
    except Exception as exc:
        print(f"[ev-prices] _save_venue_to_mongo failed  venue={venue_id}  error={exc}")


async def _fetch_one_date(
    session, vid: str, facility_id: int, slug: str, booking_url: str, date_str: str
) -> list[dict]:
    """POST for a single date and parse price slots from the HTML.

    The caller must have already GETted the booking page in the same session
    so that Eversports session cookies are present — without them the API
    silently falls back to today's schedule regardless of the requested date.
    """
    post_data = {
        "facilityId":   str(facility_id),
        "facilitySlug": slug,
        "date":         date_str,
        "type":         "user",
        **_PADEL_SPORT,
    }
    raw_body = "&".join(f"{k}={v}" for k, v in post_data.items())
    print(f"[ev-prices] post_start  venue={vid}  facility={facility_id}  date={date_str}")
    r = await session.post(
        _CAL_URL,
        data=raw_body,
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
    has_td       = "<td" in r.text
    has_price_td = bool(re.search(r'<td[^>]*data-price', r.text, re.IGNORECASE))
    td_count     = r.text.count("<td")
    print(f"[ev-prices] post_response  venue={vid}  date={date_str}  status={r.status_code}  has_price_td={has_price_td}  td_count={td_count}")

    if r.status_code != 200 or not has_td:
        return []

    if not has_price_td:
        print(f"[ev-prices] no_price_td_in_post  venue={vid}  date={date_str}  trying GET fallback")
        r = await session.get(
            booking_url,
            headers={"Accept": "text/html,*/*", "Accept-Language": "de-AT,de;q=0.9,en;q=0.8"},
            timeout=20,
        )
        if r.status_code != 200:
            print(f"[ev-prices] get_fallback_failed  venue={vid}  status={r.status_code}")
            return []

    slots: list[dict] = []
    for m in re.finditer(r"<td\b([^>]*)>", r.text, re.IGNORECASE):
        attrs = m.group(1)
        d  = re.search(r'data-date=["\']([^"\']*)["\']',  attrs)
        s  = re.search(r'data-start=["\']([^"\']*)["\']', attrs)
        p  = re.search(r'data-price=["\']([^"\']*)["\']', attrs)
        if d and s and p and p.group(1).isdigit():
            slots.append({"date": d.group(1), "start": s.group(1), "price": int(p.group(1))})
    return slots


async def _fetch_venue_prices(venue: dict) -> list[dict]:
    """
    GET the booking page (to acquire session cookies), then POST to
    /api/booking/calendar/update for today's date.

    With a valid Eversports session cookie the API returns ~7 days of
    slots starting from the requested date — enough to cover all searches
    within the next week. Without cookies some venues (e.g. Ebreichsdorf)
    ignore the date parameter and only return today's schedule.
    """
    vid         = venue["id"]
    facility_id = venue.get("eversports_facility_id")
    booking_url = venue.get("booking_url", "")
    # Prefer the stored eversports_slug; fall back to parsing booking_url but
    # strip any query string first (e.g. "?sport=padel" breaks the calendar POST).
    slug = venue.get("eversports_slug") or booking_url.rstrip("/").split("/")[-1].split("?")[0]

    if not facility_id:
        print(f"[ev-prices] skip  venue={vid}  reason=no_facility_id")
        return []

    date_str = datetime.now(VIENNA_TZ).date().strftime("%Y-%m-%d")

    try:
        async with AsyncSession(impersonate="chrome124") as session:
            # GET the booking page first to acquire Eversports session cookies.
            # Without them the cal-post API ignores the date param and always
            # returns today's slots (confirmed for venues like Ebreichsdorf).
            print(f"[ev-prices] cookie_get  venue={vid}  url={booking_url}")
            await session.get(
                booking_url,
                headers={
                    "Accept":          "text/html,application/xhtml+xml,*/*",
                    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
                },
                timeout=15,
            )
            slots = await _fetch_one_date(session, vid, facility_id, slug, booking_url, date_str)

        dates = sorted(set(s["date"] for s in slots))
        prices = sorted(set(s["price"] for s in slots))
        print(f"[ev-prices] parsed  venue={vid}  slots={len(slots)}  dates={dates[0] if dates else '?'}..{dates[-1] if dates else '?'}  prices={prices}")
        return slots

    except Exception as exc:
        print(f"[ev-prices] post_exception  venue={vid}  error={exc}")
        return []


async def refresh_prices_async(venues: list[dict]) -> None:
    """
    Async background task — scrape prices for all stale Eversports venues
    with a stagger delay. Use asyncio.create_task() to run in background.
    Deduplication: only one refresh runs at a time.
    Persists each venue's prices to MongoDB after scraping.
    """
    global _refresh_running  # noqa: PLW0603
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
                # Persist to MongoDB so prices survive redeploys
                await _save_venue_to_mongo(venue["id"], slots)
    finally:
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


def get_any_price(venue_id: str, date_str: str) -> int | None:
    """
    Return a price for the venue on that date (any time), or None.
    Used as fallback when time is unavailable. Prefers exact date,
    then same day-of-week. Does NOT return arbitrary prices across days.
    """
    with _PRICE_LOCK:
        entry = _PRICE_CACHE.get(venue_id)
    if not entry:
        return None
    slots = entry["slots"]
    try:
        target_dow = datetime.strptime(date_str, "%Y-%m-%d").weekday()
    except ValueError:
        return None
    # Prefer slots on the exact date, then fall back to same day-of-week.
    for s in slots:
        if s["date"] == date_str:
            return s["price"]
    for s in slots:
        try:
            if datetime.strptime(s["date"], "%Y-%m-%d").weekday() == target_dow:
                return s["price"]
        except (ValueError, KeyError):
            pass
    return None
