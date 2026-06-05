import os
import time

from motor.motor_asyncio import AsyncIOMotorClient

_client: AsyncIOMotorClient | None = None

_COURT_TYPE_MAP = {"indoor_outdoor": "indoor+outdoor"}
_PLATFORM_MAP = {"etennis": "eTennis", "eversports": "Eversports", "other": "Andere"}

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
        "region":          doc.get("region_label", "") or doc.get("region", ""),
        "region_key":      doc.get("region_key", ""),
        "court_type":      _COURT_TYPE_MAP.get(court_type, court_type),
        "platform":        _PLATFORM_MAP.get(platform_raw, doc.get("platform", "")),
        "priority":        int(doc.get("priority", 0) or 0),
        "booking_url":     doc.get("booking_url", ""),
        "lat":             float(lat) if lat is not None else None,
        "lon":             float(lon) if lon is not None else None,
        "platform_id":            doc.get("platform_id") or doc.get("etennis_id") or None,
        "eversports_slug":        doc.get("eversports_slug") or None,
        "eversports_facility_id": doc.get("eversports_facility_id") or None,
        "eversports_court_ids":   list(doc.get("eversports_court_ids") or []),
        "courts":                 list(doc.get("courts") or []),
        "issues":                 doc.get("issues") or None,
        "slot_fallback_minutes":  list(doc.get("slot_fallback_minutes") or []),
    }


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
