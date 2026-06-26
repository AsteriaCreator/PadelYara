import os
import re
import time
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

_client: AsyncIOMotorClient | None = None

_COURT_TYPE_MAP = {"indoor_outdoor": "indoor+outdoor"}
_PLATFORM_MAP = {"etennis": "eTennis", "eversports": "Eversports", "tennis04": "tennis04", "other": "Andere"}

_venues_cache: list[dict] | None = None
_venues_cache_ts: float = 0.0
_VENUES_TTL = 300  # 5 minutes


def _get_db():
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI", "")
        if not uri:
            raise RuntimeError("MONGODB_URI not set — copy Backend/.env.example to Backend/.env")
        _client = AsyncIOMotorClient(uri)
    return _client["padel_checker"]


def _normalize(doc: dict) -> dict:
    court_type = doc.get("court_type", "")
    platform_raw = doc.get("platform", "").lower()
    lat = doc.get("lat")
    lon = doc.get("lon")
    return {
        "id":              str(doc.get("id") or doc.get("_id", "")),
        "name":            doc.get("name", ""),
        "operator":        doc.get("operator", ""),
        "address":         doc.get("address", ""),
        "court_type":      _COURT_TYPE_MAP.get(court_type, court_type),
        "platform":        _PLATFORM_MAP.get(platform_raw, doc.get("platform", "")),
        "priority":        int(doc.get("priority", 0) or 0),
        "booking_url":     doc.get("booking_url", ""),
        "public_url":      doc.get("public_url", ""),
        "lat":             float(lat) if lat is not None else None,
        "lon":             float(lon) if lon is not None else None,
        "platform_id":            doc.get("platform_id") or doc.get("etennis_id") or None,
        "eversports_slug":        doc.get("eversports_slug") or None,
        "eversports_facility_id": doc.get("eversports_facility_id") or None,
        "eversports_court_ids":   list(doc.get("eversports_court_ids") or []),
        "tennis04_club_id":       doc.get("tennis04_club_id") or None,
        "tennis04_courtgroup_id": doc.get("tennis04_courtgroup_id") or None,
        "courts":                 list(doc.get("courts") or []),
        "issues":                 doc.get("issues") or None,
        "slot_fallback_minutes":  list(doc.get("slot_fallback_minutes") or []),
        "opening_hours":          doc.get("opening_hours") or None,
    }


async def set_opening_hours(venue_id: str, hours: dict) -> bool:
    """Persist learned opening hours onto a venue document. Matches by the
    `id` field, falling back to `_id` (ObjectId) for legacy docs. Returns True
    when a document was matched."""
    db = _get_db()
    query: dict = {"id": venue_id}
    if await db["venues"].find_one(query, {"_id": 1}) is None:
        try:
            query = {"_id": ObjectId(venue_id)}
        except Exception:
            return False
    res = await db["venues"].update_one(
        query,
        {"$set": {
            "opening_hours": hours,
            "opening_hours_updated": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return res.matched_count > 0


def invalidate_venues_cache() -> None:
    """Force the next load_venues() to re-read from MongoDB. Used after a
    background job (e.g. opening-hours refresh) mutates venue documents."""
    global _venues_cache, _venues_cache_ts
    _venues_cache = None
    _venues_cache_ts = 0.0


async def load_venues() -> list[dict]:
    """Load active venues from MongoDB, cached for 5 minutes."""
    global _venues_cache, _venues_cache_ts
    now = time.time()
    if _venues_cache is not None and now - _venues_cache_ts < _VENUES_TTL:
        return _venues_cache

    db = _get_db()
    venues = []
    seen_ids: set[str] = set()
    async for doc in db["venues"].find({"active": True}):
        v = _normalize(doc)
        if v["id"] in seen_ids:
            print(f"[venues] duplicate id={v['id']!r} — skipping")
            continue
        seen_ids.add(v["id"])
        venues.append(v)

    _venues_cache = venues
    _venues_cache_ts = now
    return venues


# ── Venue detail page (GET /api/venues/{slug}) ────────────────────────────────
#
# New venue-detail amenity fields. All optional and tri-state where it matters:
#   bool True  → known to exist
#   bool False → known to NOT exist
#   None/absent → unknown (frontend shows "Noch unbekannt" + community prompt)
# Court counts are derived from the existing `courts` array when not set
# explicitly, so legacy venues get sensible numbers for free.


def _city_from_address(addr: str) -> str:
    """Extract the city from an Austrian address, e.g.
    'Brünner Straße 72, 1210 Wien' → 'Wien'. Returns '' if no 4-digit PLZ found."""
    m = re.search(r"\b\d{4}\s+([A-Za-zÄÖÜäöüß .\-]+)$", (addr or "").strip())
    return m.group(1).strip() if m else ""


def _court_counts(doc: dict) -> tuple[int | None, int | None, int | None]:
    """(total, indoor, outdoor) — derived from the `courts` array unless an
    explicit `num_courts` is stored. indoor/outdoor are None when zero."""
    courts = doc.get("courts") or []
    indoor = sum(1 for c in courts if "indoor" in (c.get("type") or ""))
    outdoor = sum(1 for c in courts if "outdoor" in (c.get("type") or ""))
    total = doc.get("num_courts")
    if total is None and courts:
        total = len(courts)
    # eTennis venues store num_courts but no per-court types — use the venue's
    # overall court_type for the indoor/outdoor split when we have no breakdown.
    if total and not indoor and not outdoor:
        ct = doc.get("court_type", "")
        if ct == "indoor":
            indoor = total
        elif ct == "outdoor":
            outdoor = total
    return (int(total) if total is not None else None, indoor or None, outdoor or None)


def _detail(doc: dict) -> dict:
    """Full venue payload for the detail page — base fields + amenities."""
    base = _normalize(doc)
    total, indoor, outdoor = _court_counts(doc)
    lat = base.get("lat")
    lon = base.get("lon")
    maps_url = doc.get("maps_id") or (
        f"https://www.google.com/maps?q={lat},{lon}" if lat is not None and lon is not None else None
    )
    base.update({
        "address":               doc.get("address", ""),
        "bezirk":                doc.get("bezirk") or None,
        "region_label":          doc.get("region_label") or None,
        "city":                  _city_from_address(doc.get("address", "")),
        "maps_url":              maps_url,
        "website_url":           doc.get("website_url") or None,
        "num_courts":            total,
        "indoor_count":          indoor,
        "outdoor_count":         outdoor,
        "klimaanlage":           doc.get("klimaanlage"),
        "changing_rooms":        doc.get("changing_rooms"),
        "showers":               doc.get("showers"),
        "reception":             doc.get("reception"),
        "reception_note":        doc.get("reception_note") or None,
        "parking":               doc.get("parking"),
        "parking_free":          doc.get("parking_free"),
        "parking_note":          doc.get("parking_note") or None,
        "public_transport":      doc.get("public_transport") or None,
        "rental_rackets":        doc.get("rental_rackets"),
        "rental_rackets_system": doc.get("rental_rackets_system") or None,
        "gastro":                doc.get("gastro"),
        "gastro_name":           doc.get("gastro_name") or None,
        "gastro_maps_url":       doc.get("gastro_maps_url") or None,
        "gastro_menu_url":       doc.get("gastro_menu_url") or None,
        "gastro_hours":          doc.get("gastro_hours") or None,
        "extras":                doc.get("extras") or None,
        # Cancellation policy (Stornobedingungen) — scraped venue text, shown
        # with a "no guarantee / may be outdated" disclaimer on the frontend.
        # cancellation_url always points somewhere the user can verify the
        # current terms: the Eversports sportpage, else the booking page.
        "cancellation_policy":   doc.get("cancellation_policy") or doc.get("cancellation_policy_scraped") or None,
        "cancellation_url":      _cancellation_url(doc),
        # Photo priority: own/community uploads (`photos`) win over scraped
        # Eversports/eTennis links (`photos_scraped`), so a manual upload is
        # never clobbered by the scraper.
        "photos":                list(doc.get("photos") or doc.get("photos_scraped") or []),
    })
    return base


def _cancellation_url(doc: dict) -> str | None:
    """Where the user can check the venue's current cancellation terms.
    Priority: explicit stored URL > Eversports sportpage (storno is inline there) >
    venue marketing website > booking calendar (last resort — not ideal but beats nothing)."""
    if doc.get("cancellation_url"):
        return doc["cancellation_url"]
    ev_slug = doc.get("eversports_slug")
    if ev_slug:
        return f"https://www.eversports.at/s/{ev_slug}"
    # website_url is a far better reference than the raw booking calendar
    return doc.get("website_url") or doc.get("booking_url") or doc.get("public_url") or None


def _related_card(v: dict) -> dict:
    """Compact venue shape for the 'Andere Anlagen' cross-links."""
    return {
        "id":         v["id"],
        "name":       v.get("name", ""),
        "operator":   v.get("operator", ""),
        "city":       _city_from_address(v.get("address", "")),
        "num_courts": (len(v.get("courts") or []) or None),
    }


async def get_venue_detail(slug: str) -> dict | None:
    """One active venue by slug (its `id`), with amenities and cross-links to
    other venues of the same operator chain / same city."""
    db = _get_db()
    doc = await db["venues"].find_one({"id": slug, "active": True})
    # Many venues (esp. eTennis) have no `id` field — the map then links them by
    # their _id hex, so fall back to an _id lookup or those detail pages 404.
    if not doc and ObjectId.is_valid(slug):
        doc = await db["venues"].find_one({"_id": ObjectId(slug), "active": True})
    if not doc:
        return None

    detail = _detail(doc)
    operator = (detail.get("operator") or "").strip()
    city = detail.get("city") or ""

    # Build cross-links from the cached venue list (cheap; refreshed every 5 min).
    same_operator: list[dict] = []
    same_city: list[dict] = []
    for v in await load_venues():
        if v["id"] == detail["id"]:
            continue
        v_op = (v.get("operator") or "").strip()
        if operator and v_op == operator:
            same_operator.append(_related_card(v))
        elif city and _city_from_address(v.get("address", "")) == city:
            same_city.append(_related_card(v))

    detail["related"] = {
        "operator":      operator,
        "city":          city,
        "same_operator": same_operator[:8],
        "same_city":     same_city[:8],
    }
    return detail
