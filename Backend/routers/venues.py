import json
import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from venues_mongo import load_venues, get_venue_detail

router = APIRouter()

_BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
_SUGGEST_TO = "mayer.conny@gmail.com"


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


class SuggestBody(BaseModel):
    picks: dict[str, str] = {}
    free_text: str = ""


@router.post("/api/venues/{slug}/suggest")
async def suggest_venue_info(slug: str, body: SuggestBody):
    """Community suggestion: send field picks + free text to Cornelia via Brevo."""
    if not body.picks and not body.free_text.strip():
        raise HTTPException(status_code=422, detail="Nothing to send")

    lines = [f"Anlage: {slug}"]
    for key, val in body.picks.items():
        lines.append(f"{key}: {val}")
    if body.free_text.strip():
        lines.append(f"\nSonstiges: {body.free_text.strip()}")

    payload = {
        "sender": {"name": "Yara", "email": "yara@adventure-it.at"},
        "to": [{"email": _SUGGEST_TO}],
        "subject": f"PadelYara: Info zu {slug}",
        "textContent": "\n".join(lines),
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers={"api-key": _BREVO_API_KEY, "Content-Type": "application/json"},
            timeout=10,
        )
    if resp.status_code >= 400:
        print(json.dumps({"event": "brevo_suggest_error", "status": resp.status_code, "body": resp.text}))
        raise HTTPException(status_code=502, detail="Mail delivery failed")
    return {"ok": True}
