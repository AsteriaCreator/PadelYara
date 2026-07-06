import time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

import eversports_prices
from eversports_service import check_eversports_slot
from auth import _require_admin

router = APIRouter()


class MySessionsBody(BaseModel):
    sessions: list[str] = []


@router.get("/api/admin/my-sessions", dependencies=[Depends(_require_admin)])
async def get_my_sessions():
    """Return the server-stored list of owner session IDs to exclude from analytics."""
    from venues_mongo import _get_db
    db = _get_db()
    doc = await db["admin_settings"].find_one({"_id": "my_sessions"})
    return {"sessions": doc.get("sessions", []) if doc else []}


@router.post("/api/admin/my-sessions", dependencies=[Depends(_require_admin)])
async def save_my_sessions(body: MySessionsBody):
    """Persist the list of owner session IDs server-side."""
    from venues_mongo import _get_db
    db = _get_db()
    sessions = body.sessions
    await db["admin_settings"].update_one(
        {"_id": "my_sessions"},
        {"$set": {"sessions": sessions}},
        upsert=True,
    )
    return {"ok": True, "sessions": sessions}


@router.post("/api/admin/test-alert-email", dependencies=[Depends(_require_admin)])
async def send_test_alert_email(email: str = Query(...)):
    """Send a test Jagd-Alarm notification to the given email using real tournament data."""
    from venues_mongo import _get_db
    from routers.tournament_alerts import _send_notification_email
    db = _get_db()
    alert = await db["tournament_alerts"].find_one({"email": email.strip().lower()})
    if not alert:
        return {"ok": False, "error": "no subscription found for this email"}
    sample = await db["tournaments"].find(
        {}, {"title": 1, "start_date": 1, "category": 1, "competition": 1, "bundesland": 1, "venue_name": 1, "registration_closes_at": 1, "source_id": 1, "_id": 0}
    ).sort("first_seen_at", -1).limit(3).to_list(length=3)
    await _send_notification_email(email, alert.get("unsubscribe_token", ""), sample, alert.get("filters", {}))
    return {"ok": True, "sent_to": email, "tournaments": len(sample)}


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
