import asyncio

from fastapi import APIRouter, HTTPException, Query

import tournaments_mongo
from padel_austria_player import analyze_player
from yara_urteil_prompt import generate_urteil, UrteilUnavailable, DISCLAIMER
import urteil_mongo

router = APIRouter()


def _slug_from(value: str) -> str:
    """Accept a full padel-austria.at profile URL or a bare slug; return the slug."""
    v = value.strip().rstrip("/")
    if "/players/" in v:
        v = v.split("/players/", 1)[1].split("/")[0].split("?")[0]
    return v.lower()


@router.get("/api/urteil")
async def get_urteil(
    profile: str = Query(..., description="padel-austria.at profile URL or player slug"),
):
    """
    Yaras Urteil: scrape + analyse a player's tournament profile, then have Yara
    deliver a two-part verdict (Beobachtungen + Urteil). Rules live in
    yara_urteil_prompt.py. Returns the facts even if the AI verdict is unavailable.
    """
    slug = _slug_from(profile)
    if not slug or "/" in slug or " " in slug:
        raise HTTPException(status_code=400, detail="Ungültiges Profil.")

    facts = await asyncio.to_thread(analyze_player, slug)
    if facts is None:
        raise HTTPException(status_code=404, detail="Profil nicht gefunden.")

    try:
        upcoming = await tournaments_mongo.get_tournaments_for_player(slug)
    except Exception:
        upcoming = []

    result: dict = {
        "slug": slug,
        "facts": facts,
        "upcoming": upcoming,
        "disclaimer": DISCLAIMER,
        "ai_available": True,
        "beobachtungen": [],
        "urteil": None,
    }
    try:
        verdict = await asyncio.to_thread(generate_urteil, facts)
        result["beobachtungen"] = verdict["beobachtungen"]
        result["urteil"] = verdict["urteil"]
    except UrteilUnavailable as e:
        result["ai_available"] = False
        result["ai_error"] = str(e)

    await urteil_mongo.log_urteil({
        "slug": slug,
        "profile": profile,
        "player_name": facts.get("player", {}).get("name"),
        "facts": facts,
        "beobachtungen": result["beobachtungen"],
        "urteil": result["urteil"],
        "ai_available": result["ai_available"],
    })
    return result
