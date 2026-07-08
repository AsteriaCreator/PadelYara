import json
import os
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import matches_mongo
from matches_mongo import LEVELS
from venues_mongo import load_venues

router = APIRouter()

_BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
_FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.padelyara.at")

MAX_NAME_LEN = 40
MAX_NOTE_LEN = 200
MAX_DURATION_HOURS = 4
MAX_PRICE = 200


# ── Rate limiting + honeypot ───────────────────────────────────────────────────
# In-memory is enough — one Railway instance, small community. See DeinMatch.md §6.

_rate_buckets: dict[str, list[float]] = defaultdict(list)


def _rate_limited(key: str, limit: int, window_seconds: float) -> bool:
    now = time.time()
    bucket = _rate_buckets[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    return False


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rate_limit_response() -> JSONResponse:
    return JSONResponse(status_code=429, content={"ok": False, "error": "Beeindruckender Eifer. Morgen wieder."})


# ── Validation helpers ─────────────────────────────────────────────────────────

def _parse_iso(s: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _valid_levels(levels: list[str]) -> bool:
    return bool(levels) and all(lvl in LEVELS for lvl in levels)


def _err(msg: str, status: int = 422) -> JSONResponse:
    return JSONResponse(status_code=status, content={"ok": False, "error": msg})


# ── Email ───────────────────────────────────────────────────────────────────────

async def _send_brevo(to_email: str, subject: str, text: str, html_body: str) -> None:
    payload = {
        "sender": {"name": "Yara", "email": "yara@adventure-it.at"},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": text,
        "htmlContent": html_body,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers={"api-key": _BREVO_API_KEY, "Content-Type": "application/json"},
            timeout=10,
        )
    if resp.status_code >= 400:
        print(json.dumps({"event": "brevo_error_match", "status": resp.status_code, "body": resp.text}))


def _shell(inner: str) -> str:
    return f"""<html><body style="background:#0a0a0a;font-family:Arial,sans-serif;padding:32px 16px;margin:0">
<div style="max-width:480px;margin:0 auto">
  <p style="margin:0 0 28px;font-size:18px;font-weight:900;color:#d4f53c;letter-spacing:0.04em">PadelYara</p>
  {inner}
  <p style="color:#4b5563;font-size:11px;margin:28px 0 0;padding-top:14px;border-top:1px solid #1f1f1f">padelyara.at</p>
</div>
</body></html>"""


def _btn(url: str, label: str) -> str:
    return (
        f'<p style="margin:0 0 20px"><a href="{url}" style="display:inline-block;background:#d4f53c;'
        f'color:#000000;font-weight:700;font-size:13px;letter-spacing:0.05em;text-transform:uppercase;'
        f'padding:12px 22px;border-radius:8px;text-decoration:none">{label}</a></p>'
    )


def _fmt_dt(starts_at: str, ends_at: str) -> str:
    s = _parse_iso(starts_at)
    e = _parse_iso(ends_at)
    if not s or not e:
        return ""
    return f"{s.day}.{s.month}.{s.year} · {s.strftime('%H:%M')}–{e.strftime('%H:%M')}"


def _match_line(doc: dict) -> str:
    return f"{doc['venue']['name']} · {_fmt_dt(doc['starts_at'], doc['ends_at'])}"


def _match_url(slug: str) -> str:
    return f"{_FRONTEND_URL}/match/{slug}"


def _manage_url(slug: str, manage_token: str) -> str:
    return f"{_FRONTEND_URL}/match/{slug}?t={manage_token}"


async def _email_match_created(doc: dict) -> None:
    slug, manage_token = doc["slug"], doc["manage_token"]
    match_url, manage_url = _match_url(slug), _manage_url(slug, manage_token)
    text = (
        f"Dein Match steht. Hier ist dein Schlüssel — der Manage-Link. Verlier ihn nicht.\n\n"
        f"{_match_line(doc)}\n\n"
        f"Öffentlicher Link (zum Teilen):\n{match_url}\n\n"
        f"Dein Manage-Link:\n{manage_url}\n\n— Yara"
    )
    html = _shell(
        f'<p style="font-size:15px;color:#fff;margin:0 0 4px;font-weight:700">Dein Match steht.</p>'
        f'<p style="font-size:13px;color:#9ca3af;margin:0 0 24px">Hier ist dein Schlüssel — der Manage-Link. Verlier ihn nicht.</p>'
        f'<p style="font-size:13px;color:#d1d5db;margin:0 0 20px">{_match_line(doc)}</p>'
        f'{_btn(match_url, "Öffentlicher Link")}'
        f'{_btn(manage_url, "Dein Manage-Link")}'
    )
    await _send_brevo(doc["organizer"]["email"], "Dein Match steht.", text, html)


async def _email_player_joined(doc: dict, joined_name: str, joined_phone: str) -> None:
    n = 1 + len(doc["players"])
    manage_url = _manage_url(doc["slug"], doc["manage_token"])
    text = f"{joined_name} ist dabei. {n} von 4.\n\nTelefonnummer: {joined_phone}\n\n{_match_line(doc)}\n{manage_url}\n\n— Yara"
    html = _shell(
        f'<p style="font-size:15px;color:#fff;margin:0 0 4px;font-weight:700">{joined_name} ist dabei. {n} von 4.</p>'
        f'<p style="font-size:13px;color:#9ca3af;margin:0 0 20px">{_match_line(doc)}</p>'
        f'<p style="font-size:13px;color:#d4f53c;margin:0 0 20px">Telefonnummer: {joined_phone}</p>'
        f'{_btn(manage_url, "Match verwalten")}'
    )
    await _send_brevo(doc["organizer"]["email"], f"{joined_name} ist dabei.", text, html)


async def _email_match_full(doc: dict) -> None:
    org_email = doc["organizer"].get("email")
    if org_email:
        manage_url = _manage_url(doc["slug"], doc["manage_token"])
        text = f"Ihr seid vier. Mehr braucht es nicht.\n\n{_match_line(doc)}\n{manage_url}\n\n— Yara"
        html = _shell(
            f'<p style="font-size:15px;color:#fff;margin:0 0 20px;font-weight:700">Ihr seid vier. Mehr braucht es nicht.</p>'
            f'<p style="font-size:13px;color:#9ca3af;margin:0 0 20px">{_match_line(doc)}</p>'
            f'{_btn(manage_url, "Match ansehen")}'
        )
        await _send_brevo(org_email, "Ihr seid vier.", text, html)

    match_url = _match_url(doc["slug"])
    organizer_phone = doc["organizer"]["phone"]
    for p in doc["players"]:
        if not p.get("email"):
            continue
        text = f"Ihr seid vier. Mehr braucht es nicht.\n\n{_match_line(doc)}\n\nOrganisator-Nummer: {organizer_phone}\n{match_url}\n\n— Yara"
        html = _shell(
            f'<p style="font-size:15px;color:#fff;margin:0 0 20px;font-weight:700">Ihr seid vier. Mehr braucht es nicht.</p>'
            f'<p style="font-size:13px;color:#9ca3af;margin:0 0 20px">{_match_line(doc)}</p>'
            f'<p style="font-size:13px;color:#d4f53c;margin:0 0 20px">Organisator-Nummer: {organizer_phone}</p>'
            f'{_btn(match_url, "Match ansehen")}'
        )
        await _send_brevo(p["email"], "Ihr seid vier.", text, html)


async def _email_player_left(doc: dict, left_name: str) -> None:
    org_email = doc["organizer"].get("email")
    if not org_email:
        return
    n = 1 + len(doc["players"])
    manage_url = _manage_url(doc["slug"], doc["manage_token"])
    text = f"{left_name} ist raus. Wieder {n} von 4. Der Link tut noch.\n\n{_match_line(doc)}\n{manage_url}\n\n— Yara"
    html = _shell(
        f'<p style="font-size:15px;color:#fff;margin:0 0 4px;font-weight:700">{left_name} ist raus. Wieder {n} von 4.</p>'
        f'<p style="font-size:13px;color:#9ca3af;margin:0 0 20px">Der Link tut noch. {_match_line(doc)}</p>'
        f'{_btn(manage_url, "Match verwalten")}'
    )
    await _send_brevo(org_email, f"{left_name} ist raus.", text, html)


async def _email_time_changed(doc: dict, old_line: str) -> None:
    match_url = _match_url(doc["slug"])
    new_line = _match_line(doc)
    for p in doc["players"]:
        if not p.get("email"):
            continue
        text = f"Neue Zeit fürs Match. Merk sie dir besser als die alte.\n\nAlt: {old_line}\nNeu: {new_line}\n\n{match_url}\n\n— Yara"
        html = _shell(
            f'<p style="font-size:15px;color:#fff;margin:0 0 20px;font-weight:700">Neue Zeit fürs Match.</p>'
            f'<p style="font-size:13px;color:#6b7280;margin:0 0 4px;text-decoration:line-through">{old_line}</p>'
            f'<p style="font-size:13px;color:#d4f53c;margin:0 0 20px">{new_line}</p>'
            f'{_btn(match_url, "Match ansehen")}'
        )
        await _send_brevo(p["email"], "Neue Zeit fürs Match.", text, html)


async def _email_match_cancelled(doc: dict) -> None:
    for p in doc["players"]:
        if not p.get("email"):
            continue
        text = f"Das Match am {_fmt_dt(doc['starts_at'], doc['ends_at'])} ist abgesagt. Nicht meine Entscheidung.\n\n{_match_line(doc)}\n\n— Yara"
        html = _shell(
            f'<p style="font-size:15px;color:#fff;margin:0 0 4px;font-weight:700">Abgesagt.</p>'
            f'<p style="font-size:13px;color:#9ca3af;margin:0 0 20px">Nicht meine Entscheidung. {_match_line(doc)}</p>'
        )
        await _send_brevo(p["email"], "Match abgesagt.", text, html)


async def _email_player_removed(doc: dict, removed_email: str) -> None:
    text = f"Die Organisatorin hat die Aufstellung geändert. Du bist für dieses Match nicht mehr eingetragen.\n\n{_match_line(doc)}"
    html = _shell(
        f'<p style="font-size:15px;color:#fff;margin:0 0 20px;font-weight:700">Die Aufstellung hat sich geändert.</p>'
        f'<p style="font-size:13px;color:#9ca3af;margin:0">Du bist für dieses Match nicht mehr eingetragen. {_match_line(doc)}</p>'
    )
    await _send_brevo(removed_email, "Du bist nicht mehr dabei.", text, html)


# ── Request bodies ──────────────────────────────────────────────────────────────

class GuestPlayer(BaseModel):
    name: str
    phone: str | None = None


class MatchCreateBody(BaseModel):
    venue_id: str
    starts_at: str
    ends_at: str
    levels: list[str]
    court_booked: bool
    price_total: float | None = None
    note: str | None = None
    organizer_name: str
    organizer_phone: str
    organizer_email: str
    guest_players: list[GuestPlayer] = []
    website: str = ""  # honeypot


class JoinBody(BaseModel):
    name: str
    phone: str
    email: str | None = None
    website: str = ""  # honeypot


class LeaveBody(BaseModel):
    player_token: str


class PatchBody(BaseModel):
    starts_at: str | None = None
    ends_at: str | None = None
    levels: list[str] | None = None
    court_booked: bool | None = None
    price_total: float | None = None
    note: str | None = None


class AddPlayerBody(BaseModel):
    name: str
    phone: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────────

@router.post("/api/matches")
async def create_match(body: MatchCreateBody, request: Request, background_tasks: BackgroundTasks):
    if body.website.strip():
        return {"ok": True, "slug": "x", "manage_token": "x"}  # honeypot — silently no-op

    if _rate_limited(f"create:{_client_ip(request)}", limit=5, window_seconds=86400):
        return _rate_limit_response()

    starts = _parse_iso(body.starts_at)
    ends = _parse_iso(body.ends_at)
    if not starts or not ends:
        return _err("invalid_time")
    if ends <= starts:
        return _err("end_before_start")
    if starts <= datetime.now(timezone.utc):
        return _err("starts_in_past")
    if ends - starts > timedelta(hours=MAX_DURATION_HOURS):
        return _err("duration_too_long")

    if not _valid_levels(body.levels):
        return _err("invalid_levels")

    if body.price_total is not None and not (0 <= body.price_total <= MAX_PRICE):
        return _err("invalid_price")

    name = body.organizer_name.strip()
    if not name or len(name) > MAX_NAME_LEN:
        return _err("invalid_organizer_name")

    phone = matches_mongo.normalize_phone(body.organizer_phone)
    if not phone:
        return _err("invalid_phone")

    email = body.organizer_email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return _err("invalid_email")

    note = (body.note or "").strip()[:MAX_NOTE_LEN] or None

    venues = await load_venues()
    venue = next((v for v in venues if v["id"] == body.venue_id), None)
    if not venue:
        return _err("unknown_venue", status=404)
    venue_snapshot = {
        "id": venue["id"], "name": venue["name"],
        "court_type": venue.get("court_type"), "lat": venue.get("lat"), "lon": venue.get("lon"),
    }

    guest_players = []
    for g in body.guest_players:
        gname = g.name.strip()
        if not gname or len(gname) > MAX_NAME_LEN:
            return _err("invalid_guest_name")
        gphone = matches_mongo.normalize_phone(g.phone) if g.phone else None
        guest_players.append({
            "name": gname, "phone": gphone, "email": None,
            "token": secrets.token_urlsafe(24),
            "added_by_organizer": True, "joined_at": datetime.now(timezone.utc).isoformat(),
        })
    if len(guest_players) > matches_mongo.SPOTS_TOTAL - 1:
        return _err("too_many_guests")

    doc = await matches_mongo.create_match({
        "venue": venue_snapshot,
        "starts_at": starts.isoformat(),
        "ends_at": ends.isoformat(),
        "levels": body.levels,
        "court_booked": body.court_booked,
        "price_total": body.price_total,
        "note": note,
        "organizer": {"name": name, "phone": phone, "email": email},
        "players": guest_players,
    })

    background_tasks.add_task(_email_match_created, doc)
    return {"ok": True, "slug": doc["slug"], "manage_token": doc["manage_token"]}


@router.get("/api/matches")
async def list_matches(
    venue_ids: str | None = Query(None),
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    radius: float | None = Query(None),
    levels: str | None = Query(None),
):
    venue_id_list = [v for v in (venue_ids or "").split(",") if v] or None
    level_list = [l for l in (levels or "").split(",") if l] or None
    matches = await matches_mongo.board(venue_id_list, lat, lon, radius, level_list)
    return {"matches": matches}


@router.get("/api/matches/{slug}")
async def get_match(slug: str):
    doc = await matches_mongo.get_by_slug(slug)
    if not doc:
        raise HTTPException(status_code=404, detail="Match not found")
    return matches_mongo.public_view(doc)


@router.get("/api/matches/{slug}/me")
async def get_match_personal(slug: str, t: str = Query(...)):
    doc = await matches_mongo.get_by_slug(slug)
    if not doc:
        raise HTTPException(status_code=404, detail="Match not found")

    base = {k: v for k, v in doc.items() if k not in ("_id", "manage_token")}

    if t == doc["manage_token"]:
        base["role"] = "organizer"
        return base

    player = next((p for p in doc.get("players", []) if p.get("token") == t), None)
    if player:
        base["role"] = "player"
        base["organizer"] = {"name": doc["organizer"]["name"], "phone": doc["organizer"]["phone"]}
        base["players"] = [
            {"name": p.get("name", ""), "added_by_organizer": p.get("added_by_organizer", False)}
            for p in doc.get("players", [])
        ]
        base["my_token"] = t
        return base

    raise HTTPException(status_code=403, detail="invalid_token")


@router.post("/api/matches/{slug}/join")
async def join_match(slug: str, body: JoinBody, request: Request, background_tasks: BackgroundTasks):
    if body.website.strip():
        return {"ok": True, "player_token": "x", "organizer_phone": ""}  # honeypot

    if _rate_limited(f"join:{_client_ip(request)}", limit=20, window_seconds=3600):
        return _rate_limit_response()

    doc = await matches_mongo.get_by_slug(slug)
    if not doc:
        raise HTTPException(status_code=404, detail="Match not found")

    name = body.name.strip()
    if not name or len(name) > MAX_NAME_LEN:
        return _err("invalid_name")
    phone = matches_mongo.normalize_phone(body.phone)
    if not phone:
        return _err("invalid_phone")
    email = body.email.strip().lower() if body.email else None

    if matches_mongo.phone_taken(doc, phone):
        return _err("Du bist schon drin. Einmal reicht.", status=400)

    result = await matches_mongo.join_match(slug, name, phone, email)
    if not result:
        return _err("Zu langsam. Das Match ist voll.", status=409)
    player_token, updated_doc = result

    background_tasks.add_task(_email_player_joined, updated_doc, name, phone)
    if updated_doc["status"] == "full":
        background_tasks.add_task(_email_match_full, updated_doc)

    return {
        "ok": True,
        "player_token": player_token,
        "organizer_phone": updated_doc["organizer"]["phone"],
        "match": matches_mongo.public_view(updated_doc),
    }


@router.post("/api/matches/{slug}/leave")
async def leave_match(slug: str, body: LeaveBody):
    result = await matches_mongo.leave_match(slug, body.player_token)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    removed, doc = result
    return {"ok": True, "match": matches_mongo.public_view(doc)}


@router.patch("/api/matches/{slug}")
async def patch_match(slug: str, body: PatchBody, t: str = Query(...), background_tasks: BackgroundTasks = None):
    existing = await matches_mongo.get_by_slug(slug)
    if not existing or existing["manage_token"] != t:
        raise HTTPException(status_code=403, detail="invalid_token")

    updates: dict = {}
    time_changed = False
    old_line = _match_line(existing)

    if body.starts_at is not None or body.ends_at is not None:
        new_starts = _parse_iso(body.starts_at) if body.starts_at else _parse_iso(existing["starts_at"])
        new_ends = _parse_iso(body.ends_at) if body.ends_at else _parse_iso(existing["ends_at"])
        if not new_starts or not new_ends or new_ends <= new_starts:
            return _err("invalid_time")
        if new_ends - new_starts > timedelta(hours=MAX_DURATION_HOURS):
            return _err("duration_too_long")
        updates["starts_at"] = new_starts.isoformat()
        updates["ends_at"] = new_ends.isoformat()
        time_changed = True

    if body.levels is not None:
        if not _valid_levels(body.levels):
            return _err("invalid_levels")
        updates["levels"] = body.levels

    if body.court_booked is not None:
        updates["court_booked"] = body.court_booked

    if body.price_total is not None:
        if not (0 <= body.price_total <= MAX_PRICE):
            return _err("invalid_price")
        updates["price_total"] = body.price_total

    if body.note is not None:
        updates["note"] = body.note.strip()[:MAX_NOTE_LEN] or None

    if not updates:
        return matches_mongo.public_view(existing)

    doc = await matches_mongo.patch_match(slug, t, updates)
    if time_changed and background_tasks is not None:
        background_tasks.add_task(_email_time_changed, doc, old_line)
    return matches_mongo.public_view(doc)


@router.post("/api/matches/{slug}/players")
async def add_player(slug: str, body: AddPlayerBody, t: str = Query(...)):
    name = body.name.strip()
    if not name or len(name) > MAX_NAME_LEN:
        return _err("invalid_name")
    phone = matches_mongo.normalize_phone(body.phone) if body.phone else None

    doc = await matches_mongo.add_player(slug, t, name, phone)
    if not doc:
        existing = await matches_mongo.get_by_slug(slug)
        if not existing or existing["manage_token"] != t:
            raise HTTPException(status_code=403, detail="invalid_token")
        return _err("match_full", status=409)
    return matches_mongo.public_view(doc)


@router.delete("/api/matches/{slug}/players/{player_token}")
async def remove_player(slug: str, player_token: str, t: str = Query(...), background_tasks: BackgroundTasks = None):
    result = await matches_mongo.remove_player(slug, t, player_token)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    removed, doc = result
    if removed.get("email") and background_tasks is not None:
        background_tasks.add_task(_email_player_removed, doc, removed["email"])
    return matches_mongo.public_view(doc)


@router.delete("/api/matches/{slug}")
async def cancel_match(slug: str, t: str = Query(...), background_tasks: BackgroundTasks = None):
    doc = await matches_mongo.cancel_match(slug, t)
    if not doc:
        raise HTTPException(status_code=403, detail="invalid_token")
    if background_tasks is not None:
        background_tasks.add_task(_email_match_cancelled, doc)
    return matches_mongo.public_view(doc)
