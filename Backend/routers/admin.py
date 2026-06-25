import time

from fastapi import APIRouter, Query

import eversports_prices
from eversports_service import check_eversports_slot

router = APIRouter()


@router.get("/api/price-cache")
async def price_cache_check():
    """Diagnostic: show current Eversports price cache status."""
    import eversports_prices as _ep
    with _ep._PRICE_LOCK:
        return {
            venue_id: {
                "slot_count":  len(entry["slots"]),
                "prices":      sorted(set(s["price"] for s in entry["slots"])),
                "dates":       sorted(set(s["date"]  for s in entry["slots"])),
                "age_minutes": round((time.monotonic() - entry["scraped_at"]) / 60, 1),
            }
            for venue_id, entry in _ep._PRICE_CACHE.items()
        }



@router.get("/check")
async def check_compat(
    facility_id: int        = Query(...),
    court_ids:   str        = Query(...),
    date:        str        = Query(...),
    time:        str        = Query(...),
    venue_url:   str        = Query(default=""),
    venue_id:    str        = Query(default=""),
):
    """Compatibility shim — keeps the legacy frontend→backend HTTP contract working."""
    return await check_eversports_slot(
        facility_id=facility_id,
        court_ids=court_ids,
        date=date,
        time=time,
        venue_url=venue_url,
        venue_id=venue_id,
    )
