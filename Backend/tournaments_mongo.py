"""
MongoDB access layer for the tournaments collection.

Each tournament document uses (source, source_id) as the unique key.
This design allows future sources (Sunset Padel, etc.) to coexist
without any schema changes.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

_client: AsyncIOMotorClient | None = None

BUNDESLAENDER = [
    "Wien", "Niederösterreich", "Oberösterreich", "Steiermark",
    "Tirol", "Kärnten", "Salzburg", "Vorarlberg", "Burgenland",
]

CATEGORIES = ["Newcomer", "Starter", "Advanced", "Expert", "Professional", "Elite"]

COMPETITIONS = ["Herren", "Damen", "Mixed", "Jugend", "Offener Bewerb"]

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def _get_db():
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI", "")
        if not uri:
            raise RuntimeError("MONGODB_URI not set")
        _client = AsyncIOMotorClient(uri)
    return _client["padel_checker"]


def _col():
    return _get_db()["tournaments"]


async def ensure_indexes() -> None:
    col = _col()
    await col.create_index([("source", 1), ("source_id", 1)], unique=True)
    await col.create_index([("starts_at", 1)])
    await col.create_index([("bundesland", 1)])
    await col.create_index([("bezirk", 1)])
    await col.create_index([("status", 1)])
    await col.create_index([("first_seen_at", 1)])
    await col.create_index([("entries.player_a_slug", 1)])
    await col.create_index([("entries.player_b_slug", 1)])


import re as _re


async def _build_venue_bezirk_cache() -> list[tuple[str, str | None]]:
    """
    Build a list of (normalized_combined_name, bezirk) pairs from the venues collection.
    Key = operator + " " + name, normalized (| and - replaced with space, lowercase).
    This prevents generic operator names ("Padelzone") from matching wrong venues.
    """
    db = _get_db()
    docs = await db["venues"].find(
        {"bezirk": {"$exists": True}},
        {"name": 1, "operator": 1, "bezirk": 1, "_id": 0}
    ).to_list(2000)
    pairs: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for d in docs:
        bezirk = d.get("bezirk")
        operator = (d.get("operator") or "").strip()
        name = (d.get("name") or "").strip()
        # Primary key: combined operator + name
        combined = _norm(f"{operator} {name}")
        if combined and combined not in seen:
            pairs.append((combined, bezirk))
            seen.add(combined)
        # Fallback keys: individual parts (only if they're specific enough — length > 6)
        for part in (operator, name):
            key = _norm(part)
            if key and len(key) > 6 and key not in seen:
                pairs.append((key, bezirk))
                seen.add(key)
    # Sort by length desc so longest (most specific) keys are tried first
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def _norm(s: str) -> str:
    """Normalize a venue name for matching: lowercase, replace separators with space, collapse."""
    return _re.sub(r"\s+", " ", _re.sub(r"[\|\-]", " ", s.lower())).strip()


def _fuzzy_bezirk(venue_name: str, pairs: list[tuple[str, str | None]]) -> str | None:
    """
    Fuzzy match a tournament venue_name against the venue DB.
    Tries bidirectional substring; takes the LONGEST (most specific) matching key.
    """
    if not venue_name or not pairs:
        return None
    vn = _norm(venue_name)

    best_len = 0
    best_bezirk: str | None = None
    for key, bezirk in pairs:
        if key in vn or vn in key:
            if len(key) > best_len:
                best_len = len(key)
                best_bezirk = bezirk

    return best_bezirk


async def upsert_tournaments(
    tournaments: list[dict[str, Any]], is_seed: bool = False
) -> dict[str, int]:
    """
    Upsert a list of tournament dicts.
    - Preserves first_seen_at on existing records.
    - Updates last_seen_at and all scraped fields on every run.
    - Enriches each tournament with `bezirk` from the venues collection.

    `first_seen_at` drives the "NEU" badge, so it must reflect when a tournament
    genuinely appeared to us. On a normal run that's "now". On a bulk `is_seed`
    import (empty collection), "now" would flag the entire back-catalogue as new,
    so we backdate it to the registration-open date (best estimate of when it
    became available), or ~30 days ago when that's unknown.

    Returns counts: {inserted, updated}.
    """
    col = _col()
    now = datetime.now(timezone.utc)
    seed_fallback = now - timedelta(days=30)
    inserted = 0
    updated = 0

    # Load venue → bezirk lookup once per scrape run
    venue_bezirk_pairs = await _build_venue_bezirk_cache()

    for t in tournaments:
        # Enrich with bezirk from venues collection using fuzzy matching
        t["bezirk"] = _fuzzy_bezirk(t.get("venue_name", ""), venue_bezirk_pairs)
        source = t["source"]
        source_id = t["source_id"]

        # Fields we always update from the scraper
        update_fields = {k: v for k, v in t.items() if k not in ("source", "source_id")}
        update_fields["last_seen_at"] = now

        # Detail-page dates come from a per-tournament fetch that can transiently
        # fail. Never overwrite a previously-stored registration date with None.
        for f in ("registration_opens_at", "registration_closes_at"):
            if update_fields.get(f) is None:
                update_fields.pop(f, None)

        # first_seen_at = now for genuine new sightings; backdated for seed imports
        # so the whole back-catalogue doesn't light up as NEU on first load.
        if is_seed:
            reg_opens = t.get("registration_opens_at")
            first_seen = reg_opens if isinstance(reg_opens, datetime) and reg_opens < now else seed_fallback
        else:
            first_seen = now

        result = await col.update_one(
            {"source": source, "source_id": source_id},
            {
                "$set": update_fields,
                "$setOnInsert": {
                    "source": source,
                    "source_id": source_id,
                    "first_seen_at": first_seen,
                },
            },
            upsert=True,
        )

        if result.upserted_id:
            inserted += 1
        else:
            updated += 1

    return {"inserted": inserted, "updated": updated}


def _sort_key(t: dict) -> tuple:
    """
    Sort order:
    1. Open tournaments with free spots (best)
    2. Open but full (waitlist available)
    3. Not open yet
    4. Closed / cancelled / unknown (worst)
    Within groups, sort by starts_at ascending.
    """
    status = t.get("status", "unknown")
    current = t.get("participants_current", 0)
    maximum = t.get("participants_max", 0)
    starts_at = t.get("starts_at") or datetime(9999, 1, 1, tzinfo=timezone.utc)

    if status == "open" and (maximum == 0 or current < maximum):
        group = 0
    elif status == "open":
        group = 1
    elif status == "not_open_yet":
        group = 2
    elif status == "full":
        group = 3
    elif status == "closed":
        group = 4
    else:
        group = 5

    return (group, starts_at)


async def get_tournaments(
    bundesland: list[str] | None = None,
    bezirk: list[str] | None = None,
    category: list[str] | None = None,
    competition: list[str] | None = None,
    weekday: list[str] | None = None,
    venue_name: list[str] | None = None,
    show_full: bool = True,
    show_closed: bool = False,
) -> list[dict]:
    """
    Query tournaments from MongoDB with optional filters.
    Returns sorted list of serializable tournament dicts.
    """
    col = _col()
    query: dict[str, Any] = {}

    if bundesland:
        query["bundesland"] = {"$in": bundesland}
    if bezirk:
        query["bezirk"] = {"$in": bezirk}
    if category:
        query["category"] = {"$in": category}
    if competition:
        query["competition"] = {"$in": competition}
    if weekday:
        query["weekday"] = {"$in": weekday}
    if venue_name:
        query["venue_name"] = {"$in": venue_name}
    if not show_full:
        # Exclude tournaments where participants_current >= participants_max AND status != open
        query["status"] = {"$nin": ["full"]}
    if not show_closed:
        existing_status_filter = query.get("status", {})
        if isinstance(existing_status_filter, dict) and "$nin" in existing_status_filter:
            existing_status_filter["$nin"].extend(["closed", "cancelled"])
        elif not existing_status_filter:
            query["status"] = {"$nin": ["closed", "cancelled"]}
        # Also hide tournaments whose start date has passed — scraper may not have
        # re-marked them as closed yet if they disappeared from the list.
        cutoff = datetime.utcnow() - timedelta(hours=12)
        query["$or"] = [
            {"starts_at": None},
            {"starts_at": {"$gte": cutoff}},
        ]

    cursor = col.find(query, {"_id": 0})
    docs = await cursor.to_list(length=2000)

    # Convert datetime fields to ISO strings for JSON serialization
    result = []
    for doc in docs:
        for field in ("starts_at", "ends_at", "first_seen_at", "last_seen_at",
                      "registration_opens_at", "registration_closes_at"):
            if isinstance(doc.get(field), datetime):
                doc[field] = doc[field].isoformat()
        result.append(doc)

    result.sort(key=_sort_key)
    return result


async def get_bezirke(bundesland: list[str] | None = None) -> list[str]:
    """Return sorted list of distinct Bezirk names, optionally filtered by Bundesland."""
    col = _col()
    query: dict = {"bezirk": {"$ne": None}}
    if bundesland:
        query["bundesland"] = {"$in": bundesland}
    bezirke = await col.distinct("bezirk", query)
    return sorted(b for b in bezirke if b)


async def get_venues(bundesland: list[str] | None = None) -> list[str]:
    """Return sorted list of distinct venue names, optionally filtered by bundesland."""
    col = _col()
    query = {}
    if bundesland:
        query["bundesland"] = {"$in": bundesland}
    venues = await col.distinct("venue_name", query)
    return sorted(v for v in venues if v)


async def count_tournaments() -> int:
    return await _col().count_documents({})


async def search_players(query: str) -> list[dict]:
    """
    Search for players by name across all tournament entries.
    Returns distinct [{name, slug}] pairs matching the query (case-insensitive).
    """
    if not query or len(query) < 2:
        return []
    col = _col()
    regex = {"$regex": _re.escape(query), "$options": "i"}
    pipeline = [
        {"$match": {
            "entries": {"$exists": True, "$ne": []},
            "$or": [
                {"entries.player_a_name": regex},
                {"entries.player_b_name": regex},
            ],
        }},
        {"$unwind": "$entries"},
        {"$facet": {
            "a": [
                {"$match": {"entries.player_a_name": regex}},
                {"$group": {"_id": "$entries.player_a_slug", "name": {"$first": "$entries.player_a_name"}}},
            ],
            "b": [
                {"$match": {"entries.player_b_name": regex}},
                {"$group": {"_id": "$entries.player_b_slug", "name": {"$first": "$entries.player_b_name"}}},
            ],
        }},
        {"$project": {"combined": {"$concatArrays": ["$a", "$b"]}}},
        {"$unwind": "$combined"},
        {"$group": {"_id": "$combined._id", "name": {"$first": "$combined.name"}}},
        {"$sort": {"name": 1}},
        {"$limit": 10},
    ]
    results = await col.aggregate(pipeline).to_list(10)
    return [{"slug": r["_id"], "name": r["name"]} for r in results if r.get("_id")]


async def get_tournaments_for_player(player_slug: str) -> list[dict]:
    """
    Return all open/upcoming tournaments where the player (identified by slug)
    appears in the entries list, with their partner info.
    """
    col = _col()
    query = {
        "status": {"$in": ["open", "not_open_yet", "full", "closed"]},
        "$or": [
            {"entries.player_a_slug": player_slug},
            {"entries.player_b_slug": player_slug},
        ],
    }
    cursor = col.find(query, {"_id": 0})
    docs = await cursor.to_list(200)
    result = []
    for doc in docs:
        # Find the specific entry row for this player
        partner_name = None
        partner_slug = None
        for entry in (doc.get("entries") or []):
            if entry.get("player_a_slug") == player_slug:
                partner_name = entry.get("player_b_name")
                partner_slug = entry.get("player_b_slug")
                break
            elif entry.get("player_b_slug") == player_slug:
                partner_name = entry.get("player_a_name")
                partner_slug = entry.get("player_a_slug")
                break
        doc.pop("entries", None)  # don't send full entry list to frontend
        for field in ("starts_at", "ends_at", "first_seen_at", "last_seen_at",
                      "registration_opens_at", "registration_closes_at"):
            if isinstance(doc.get(field), datetime):
                doc[field] = doc[field].isoformat()
        doc["partner_name"] = partner_name
        doc["partner_slug"] = partner_slug
        result.append(doc)
    result.sort(key=_sort_key)
    return result
