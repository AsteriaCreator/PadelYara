import re
import secrets
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from venues_mongo import _get_db

LEVELS = [
    "Starter", "Starter +", "Starter ++",
    "Low Advanced", "Mid Advanced", "High Advanced",
    "Expert", "Professional", "Elite",
]

SPOTS_TOTAL = 4
PURGE_AFTER_DAYS = 7
DELETE_AFTER_DAYS = 60

PUBLIC_PROJECTION = {
    "manage_token": 0,
    "organizer.phone": 0,
    "organizer.email": 0,
    "players.phone": 0,
    "players.email": 0,
    "players.token": 0,
}


def _col():
    return _get_db()["matches"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


async def ensure_indexes() -> None:
    col = _col()
    await col.create_index("slug", unique=True)
    await col.create_index([("status", 1), ("starts_at", 1)])
    await col.create_index("venue.id")


def normalize_phone(raw: str) -> str | None:
    """Strip formatting, keep a leading '+'. None if it doesn't look like a phone number."""
    digits = re.sub(r"[^\d+]", "", raw or "")
    has_plus = digits.startswith("+")
    core = digits.lstrip("+")
    if digits.count("+") > 1 or len(core) < 7 or len(core) > 15:
        return None
    return ("+" if has_plus else "") + core


def public_view(doc: dict) -> dict:
    """Strip all contact info — the shape returned by board/detail endpoints."""
    out = {k: v for k, v in doc.items() if k not in ("manage_token", "_id")}
    organizer = dict(out.get("organizer") or {})
    organizer.pop("phone", None)
    organizer.pop("email", None)
    out["organizer"] = organizer
    out["players"] = [
        {"name": p.get("name", ""), "added_by_organizer": p.get("added_by_organizer", False)}
        for p in out.get("players", [])
    ]
    return out


async def create_match(payload: dict) -> dict:
    now_iso = _now_iso()
    doc = {
        "slug": secrets.token_urlsafe(6)[:8],
        "manage_token": secrets.token_urlsafe(24),
        "venue": payload["venue"],
        "starts_at": payload["starts_at"],
        "ends_at": payload["ends_at"],
        "levels": payload["levels"],
        "court_booked": payload["court_booked"],
        "price_total": payload.get("price_total"),
        "note": payload.get("note"),
        "organizer": payload["organizer"],
        "players": payload.get("players", []),
        "spots_total": SPOTS_TOTAL,
        "status": "open",
        "created_at": now_iso,
        "updated_at": now_iso,
        "purged_at": None,
    }
    if len(doc["players"]) == SPOTS_TOTAL - 1:
        doc["status"] = "full"
    await _col().insert_one(doc)
    return doc


async def get_by_slug(slug: str) -> dict | None:
    return await _col().find_one({"slug": slug})


async def board(
    venue_ids: list[str] | None,
    lat: float | None,
    lon: float | None,
    radius_km: float | None,
    levels: list[str] | None,
) -> list[dict]:
    query: dict = {
        "status": {"$in": ["open", "full"]},
        "starts_at": {"$gt": _now_iso()},
    }
    if levels:
        query["levels"] = {"$in": levels}
    if venue_ids:
        query["venue.id"] = {"$in": venue_ids}

    docs = await _col().find(query).sort("starts_at", 1).to_list(length=200)

    if lat is not None and lon is not None and radius_km is not None:
        from distance import haversine_km
        filtered = []
        for d in docs:
            v = d.get("venue", {})
            if v.get("lat") is None or v.get("lon") is None:
                continue
            dist = haversine_km(lat, lon, v["lat"], v["lon"])
            if dist <= radius_km:
                d["venue"] = {**v, "distance_km": round(dist, 1)}
                filtered.append(d)
        docs = filtered

    return [public_view(d) for d in docs]


async def join_match(slug: str, name: str, phone: str, email: str | None) -> tuple[str, dict] | None:
    """Atomic join. Returns (player_token, updated_doc) or None if the match is
    unknown, past, cancelled, or already full (caller distinguishes via a
    lookup)."""
    now_iso = _now_iso()
    token = secrets.token_urlsafe(24)
    player = {
        "name": name, "phone": phone, "email": email, "token": token,
        "added_by_organizer": False, "joined_at": now_iso,
    }
    doc = await _col().find_one_and_update(
        {
            "slug": slug,
            "status": "open",
            "starts_at": {"$gt": now_iso},
            "$expr": {"$lt": [{"$size": "$players"}, {"$subtract": ["$spots_total", 1]}]},
        },
        {"$push": {"players": player}, "$set": {"updated_at": now_iso}},
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        return None
    if len(doc["players"]) == doc["spots_total"] - 1:
        await _col().update_one({"_id": doc["_id"]}, {"$set": {"status": "full"}})
        doc["status"] = "full"
    return token, doc


def phone_taken(doc: dict, phone: str) -> bool:
    if doc.get("organizer", {}).get("phone") == phone:
        return True
    return any(p.get("phone") == phone for p in doc.get("players", []))


async def leave_match(slug: str, player_token: str) -> tuple[dict, dict] | None:
    """Returns (removed_player, updated_doc) or None if token/slug didn't match."""
    doc = await _col().find_one({"slug": slug})
    if not doc:
        return None
    removed = next((p for p in doc.get("players", []) if p.get("token") == player_token), None)
    if not removed:
        return None
    now_iso = _now_iso()
    was_full = doc["status"] == "full"
    await _col().update_one(
        {"slug": slug},
        {"$pull": {"players": {"token": player_token}}, "$set": {"updated_at": now_iso}},
    )
    if was_full:
        await _col().update_one({"slug": slug, "status": "full"}, {"$set": {"status": "open"}})
    doc["players"] = [p for p in doc["players"] if p.get("token") != player_token]
    doc["status"] = "open" if was_full else doc["status"]
    return removed, doc


async def patch_match(slug: str, manage_token: str, updates: dict) -> dict | None:
    updates["updated_at"] = _now_iso()
    return await _col().find_one_and_update(
        {"slug": slug, "manage_token": manage_token},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )


async def add_player(slug: str, manage_token: str, name: str, phone: str | None) -> dict | None:
    now_iso = _now_iso()
    player = {
        "name": name, "phone": phone, "email": None, "token": secrets.token_urlsafe(24),
        "added_by_organizer": True, "joined_at": now_iso,
    }
    doc = await _col().find_one_and_update(
        {
            "slug": slug, "manage_token": manage_token, "status": "open",
            "$expr": {"$lt": [{"$size": "$players"}, {"$subtract": ["$spots_total", 1]}]},
        },
        {"$push": {"players": player}, "$set": {"updated_at": now_iso}},
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        return None
    if len(doc["players"]) == doc["spots_total"] - 1:
        await _col().update_one({"_id": doc["_id"]}, {"$set": {"status": "full"}})
        doc["status"] = "full"
    return doc


async def remove_player(slug: str, manage_token: str, player_token: str) -> tuple[dict, dict] | None:
    doc = await _col().find_one({"slug": slug, "manage_token": manage_token})
    if not doc:
        return None
    removed = next((p for p in doc.get("players", []) if p.get("token") == player_token), None)
    if not removed:
        return None
    now_iso = _now_iso()
    was_full = doc["status"] == "full"
    await _col().update_one(
        {"slug": slug},
        {"$pull": {"players": {"token": player_token}}, "$set": {"updated_at": now_iso}},
    )
    if was_full:
        await _col().update_one({"slug": slug, "status": "full"}, {"$set": {"status": "open"}})
    return removed, doc


async def cancel_match(slug: str, manage_token: str) -> dict | None:
    return await _col().find_one_and_update(
        {"slug": slug, "manage_token": manage_token},
        {"$set": {"status": "cancelled", "updated_at": _now_iso()}},
        return_document=ReturnDocument.AFTER,
    )


async def cleanup_matches() -> dict:
    """Daily DSGVO housekeeping — three stages:
    1. Past matches → status=expired (drops off the board).
    2. Expired 7+ days → strip phone/email/tokens, shorten names to initials.
    3. Expired 60+ days → delete the document entirely.
    """
    col = _col()
    now = _now()
    now_iso = now.isoformat()

    expired_result = await col.update_many(
        {"status": {"$in": ["open", "full"]}, "starts_at": {"$lt": now_iso}},
        {"$set": {"status": "expired", "updated_at": now_iso}},
    )

    purge_cutoff = (now - timedelta(days=PURGE_AFTER_DAYS)).isoformat()
    to_purge = await col.find(
        {"status": {"$in": ["expired", "cancelled"]}, "purged_at": None, "ends_at": {"$lt": purge_cutoff}}
    ).to_list(length=None)
    purged_count = 0
    for doc in to_purge:
        def _initial(name: str) -> str:
            return (name.strip()[:1] + ".") if name.strip() else "?"
        organizer = dict(doc.get("organizer") or {})
        organizer["name"] = _initial(organizer.get("name", ""))
        organizer.pop("phone", None)
        organizer.pop("email", None)
        players = []
        for p in doc.get("players", []):
            players.append({"name": _initial(p.get("name", "")), "added_by_organizer": p.get("added_by_organizer", False)})
        await col.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "organizer": organizer, "players": players, "manage_token": None,
                "purged_at": now_iso, "updated_at": now_iso,
            }},
        )
        purged_count += 1

    delete_cutoff = (now - timedelta(days=DELETE_AFTER_DAYS)).isoformat()
    delete_result = await col.delete_many(
        {"status": {"$in": ["expired", "cancelled"]}, "ends_at": {"$lt": delete_cutoff}}
    )

    return {
        "expired": expired_result.modified_count,
        "purged": purged_count,
        "deleted": delete_result.deleted_count,
    }
