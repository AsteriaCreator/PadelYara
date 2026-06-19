import threading

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

import tournaments_mongo
from auth import _require_admin
from scheduler import _run_tournament_scrape

router = APIRouter()


@router.get("/api/tournaments")
async def get_tournaments(
    bundesland:  str = Query(default=""),
    bezirk:      str = Query(default=""),
    category:    str = Query(default=""),
    competition: str = Query(default=""),
    weekday:     str = Query(default=""),
    venue_name:  str = Query(default=""),
    show_full:   bool = Query(default=False),
    show_closed: bool = Query(default=False),
):
    """
    Return filtered tournament list from MongoDB.
    Multi-value params are comma-separated, e.g. bundesland=Wien,Tirol
    """
    def _split(s: str) -> list[str] | None:
        parts = [p.strip() for p in s.split(",") if p.strip()]
        return parts if parts else None

    tournaments = await tournaments_mongo.get_tournaments(
        bundesland=_split(bundesland),
        bezirk=_split(bezirk),
        category=_split(category),
        competition=_split(competition),
        weekday=_split(weekday),
        venue_name=_split(venue_name),
        show_full=show_full,
        show_closed=show_closed,
    )
    return {"tournaments": tournaments, "count": len(tournaments)}


@router.get("/api/tournaments/bezirke")
async def get_tournament_bezirke(bundesland: str = Query(default="")):
    """Return distinct Bezirk names for the filter, optionally scoped to a Bundesland."""
    bl = [p.strip() for p in bundesland.split(",") if p.strip()] if bundesland else None
    bezirke = await tournaments_mongo.get_bezirke(bundesland=bl)
    return {"bezirke": bezirke}


@router.get("/api/tournaments/venues")
async def get_tournament_venues(bundesland: str = Query(default="")):
    """Return distinct venue names for the Standort filter."""
    bl = [p.strip() for p in bundesland.split(",") if p.strip()] if bundesland else None
    venues = await tournaments_mongo.get_venues(bundesland=bl)
    return {"venues": venues}


@router.get("/api/tournaments/by-ids")
async def get_tournaments_by_ids(ids: str = Query(..., description="Comma-separated source_ids")):
    """Return specific tournaments by source_id list — used for shared Merkliste links."""
    id_list = [i.strip() for i in ids.split(",") if i.strip()][:50]
    tournaments = await tournaments_mongo.get_tournaments_by_ids(id_list)
    return {"tournaments": tournaments}


class ShareRequest(BaseModel):
    ids: list[str]

@router.post("/api/tournaments/share")
async def create_share(body: ShareRequest):
    """Create a short share code for a list of tournament source_ids."""
    ids = [i for i in body.ids if i][:50]
    if not ids:
        raise HTTPException(status_code=400, detail="No ids provided")
    code = await tournaments_mongo.create_share(ids)
    return {"code": code}

@router.get("/api/tournaments/share/{code}")
async def get_share(code: str):
    """Resolve a share code to a list of tournaments."""
    tournaments = await tournaments_mongo.get_share_tournaments(code.strip().lower())
    if not tournaments:
        raise HTTPException(status_code=404, detail="Share not found or expired")
    return {"tournaments": tournaments}


@router.get("/api/tournaments/players/search")
async def search_players(q: str = Query(default="", min_length=2)):
    """Search for players by name across tournament entries. Returns [{name, slug}]."""
    results = await tournaments_mongo.search_players(q.strip())
    return {"players": results}


@router.get("/api/tournaments/player")
async def get_player_tournaments(slug: str = Query(..., description="Player slug from padel-austria.at/players/<slug>")):
    """Return open/upcoming tournaments the player is registered for."""
    slug = slug.strip().lower()
    tournaments = await tournaments_mongo.get_tournaments_for_player(slug)
    return {"tournaments": tournaments, "player_slug": slug}


@router.post("/api/admin/scrape-tournaments", dependencies=[Depends(_require_admin)])
async def trigger_tournament_scrape():
    """Manually trigger a tournament scrape (admin only)."""
    threading.Thread(target=_run_tournament_scrape, daemon=True).start()
    return {"status": "scrape started"}
