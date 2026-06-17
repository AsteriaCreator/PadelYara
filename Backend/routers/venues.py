from fastapi import APIRouter, HTTPException

from venues_mongo import load_venues, get_venue_detail

router = APIRouter()


@router.get("/api/venues")
async def get_venues():
    """Static venue list for the Padelrevier map — no scraping, served from the
    load_venues() cache. Returns only what the map needs (name, address, coords,
    links), filtered to venues that actually have coordinates to place a pin."""
    venues = await load_venues()
    out = [
        {
            "id":          v["id"],
            "name":        v["name"],
            "operator":    v.get("operator", ""),
            "address":     v.get("address", ""),
            "court_type":  v["court_type"],
            "platform":    v.get("platform", ""),
            "booking_url": v.get("booking_url", ""),
            "public_url":  v.get("public_url", ""),
            "lat":         v["lat"],
            "lon":         v["lon"],
        }
        for v in venues
        if v.get("lat") is not None and v.get("lon") is not None
    ]
    return {"venues": out, "count": len(out)}


@router.get("/api/venues/{slug}")
async def get_venue_detail_endpoint(slug: str):
    """Full detail for one venue (Court-Detailseite). Amenities + cross-links to
    same-operator / same-city venues. 404 if the slug is unknown or inactive."""
    detail = await get_venue_detail(slug)
    if not detail:
        raise HTTPException(status_code=404, detail="Venue not found")
    return detail
