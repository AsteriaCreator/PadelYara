import json
import os
import re
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from auth import _require_admin

router = APIRouter()

_BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
_FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.padelyara.at")
_static = os.environ.get("RAILWAY_STATIC_URL", "")
_BACKEND_URL = f"https://{_static}" if _static else _FRONTEND_URL


async def _send_confirmation_email(to_email: str, token: str) -> None:
    confirm_url = f"{_BACKEND_URL}/api/confirm?token={token}"
    text = (
        f"Menschen bauen merkwürdige Regeln.\n\n"
        f"Eine davon ist diese.\n\n"
        f"{confirm_url}\n\n"
        f"Danach weißt du, was ich weiß.\n\n"
        f"— Yara"
    )
    html = f"""<html><body style="background:#0a0a0a;color:#d1d5db;font-family:sans-serif;padding:40px;max-width:520px;margin:0 auto">
<p style="margin:0 0 36px"><img src="https://www.padelyara.at/logo-white.svg" alt="PadelYara" style="height:28px;width:auto"></p>

<p style="font-size:16px;color:#d1d5db;margin:0 0 12px;line-height:1.7">Menschen bauen merkwürdige Regeln.</p>
<p style="font-size:16px;color:#d1d5db;margin:0 0 32px;line-height:1.7">Eine davon ist diese.</p>

<p style="margin:0 0 32px">
  <a href="{confirm_url}"
     style="display:inline-block;background:#d4f53c;color:#000000;font-weight:700;
            font-size:14px;letter-spacing:0.06em;text-transform:uppercase;
            padding:14px 28px;border-radius:8px;text-decoration:none">
    Anmeldung bestätigen
  </a>
</p>

<p style="font-size:16px;color:#d1d5db;margin:0 0 32px;line-height:1.7">Danach weißt du, was ich weiß.</p>
<p style="color:#6b7280;font-size:13px;margin:32px 0 0">— Yara</p>
</body></html>"""

    payload = {
        "sender": {"name": "Yara", "email": "yara@adventure-it.at"},
        "to": [{"email": to_email}],
        "subject": "Eine Formalität.",
        "textContent": text,
        "htmlContent": html,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers={"api-key": _BREVO_API_KEY, "Content-Type": "application/json"},
            timeout=10,
        )
    if resp.status_code >= 400:
        print(json.dumps({"event": "brevo_error", "status": resp.status_code, "body": resp.text}))


class SubscribeBody(BaseModel):
    email: str


@router.get("/api/subscribers/count", dependencies=[Depends(_require_admin)])
async def subscribers_count():
    """Admin: count of confirmed newsletter subscribers."""
    from venues_mongo import _get_db
    db = _get_db()
    count = await db["subscribers"].count_documents({"confirmed": True})
    return {"count": count}


@router.post("/api/subscribe")
async def subscribe(body: SubscribeBody, background_tasks: BackgroundTasks):
    """Add an email to the newsletter waitlist and send a confirmation link."""
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return JSONResponse(status_code=422, content={"ok": False, "error": "invalid_email"})
    from venues_mongo import _get_db
    db = _get_db()
    existing = await db["subscribers"].find_one({"email": email})
    if existing:
        if existing.get("confirmed"):
            return {"ok": True, "already": True}
        token = existing.get("confirm_token") or secrets.token_urlsafe(32)
        await db["subscribers"].update_one({"email": email}, {"$set": {"confirm_token": token}})
        background_tasks.add_task(_send_confirmation_email, email, token)
        return {"ok": True, "already": False}
    token = secrets.token_urlsafe(32)
    await db["subscribers"].insert_one({
        "email": email,
        "subscribed_at": datetime.now(timezone.utc).isoformat(),
        "confirmed": False,
        "confirm_token": token,
    })
    background_tasks.add_task(_send_confirmation_email, email, token)
    print(json.dumps({"event": "subscriber_pending", "email": email}))
    return {"ok": True, "already": False}


@router.get("/api/confirm")
async def confirm_subscription(token: str = Query(...)):
    """Activate a subscriber via the one-time token sent in the confirmation email."""
    from venues_mongo import _get_db
    db = _get_db()
    result = await db["subscribers"].find_one_and_update(
        {"confirm_token": token, "confirmed": False},
        {"$set": {"confirmed": True, "confirmed_at": datetime.now(timezone.utc).isoformat()}},
    )
    if not result:
        return RedirectResponse(url=_FRONTEND_URL, status_code=302)
    return RedirectResponse(url=f"{_FRONTEND_URL}?confirmed=1", status_code=302)
