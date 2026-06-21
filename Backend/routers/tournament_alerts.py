import json
import os
import re
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Query
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

router = APIRouter()

_BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
_FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.padelyara.at")
_static = os.environ.get("RAILWAY_STATIC_URL", "")
_BACKEND_URL = f"https://{_static}" if _static else _FRONTEND_URL


# ── Email helpers ─────────────────────────────────────────────────────────────

async def _send_confirmation_email(to_email: str, token: str) -> None:
    confirm_url = f"{_BACKEND_URL}/api/tournaments/alerts/confirm?token={token}"
    text = (
        f"Du willst wissen, wenn neue Turniere kommen.\n\n"
        f"Verständlich.\n\n"
        f"{confirm_url}\n\n"
        f"Danach wirst du informiert. Ich nicht.\n\n"
        f"— Yara"
    )
    html = f"""<html><body style="background:#0a0a0a;color:#d1d5db;font-family:sans-serif;padding:40px;max-width:520px;margin:0 auto">
<p style="margin:0 0 36px"><img src="https://www.padelyara.at/logo-white.svg" alt="PadelYara" style="height:28px;width:auto"></p>

<p style="font-size:16px;color:#d1d5db;margin:0 0 12px;line-height:1.7">Du willst wissen, wenn neue Turniere kommen.</p>
<p style="font-size:16px;color:#d1d5db;margin:0 0 32px;line-height:1.7">Verständlich.</p>

<p style="margin:0 0 32px">
  <a href="{confirm_url}"
     style="display:inline-block;background:#d4f53c;color:#000000;font-weight:700;
            font-size:14px;letter-spacing:0.06em;text-transform:uppercase;
            padding:14px 28px;border-radius:8px;text-decoration:none">
    Jagd-Alarm aktivieren
  </a>
</p>

<p style="font-size:16px;color:#d1d5db;margin:0 0 32px;line-height:1.7">Danach wirst du informiert. Ich nicht.</p>
<p style="color:#6b7280;font-size:13px;margin:32px 0 0">— Yara</p>
</body></html>"""

    payload = {
        "sender": {"name": "Yara", "email": "yara@adventure-it.at"},
        "to": [{"email": to_email}],
        "subject": "Jagd-Alarm einrichten.",
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
        print(json.dumps({"event": "brevo_error_alerts", "status": resp.status_code, "body": resp.text}))


async def _send_notification_email(
    to_email: str,
    unsubscribe_token: str,
    matched_tournaments: list[dict],
) -> None:
    count = len(matched_tournaments)
    plural_s = "s" if count == 1 else ""
    plural_e = "e" if count != 1 else ""
    subject = f"{count} neue{plural_s} Turnier{plural_e} für deine Jagd."

    unsubscribe_url = f"{_BACKEND_URL}/api/tournaments/alerts/unsubscribe?token={unsubscribe_token}"

    def _tournament_card(t: dict) -> str:
        title = t.get("title", "Turnier")
        date_str = t.get("start_date") or t.get("date") or ""
        category = t.get("category", "")
        competition = t.get("competition", "")
        bundesland = t.get("bundesland", "")
        source_url = t.get("source_url", "")
        meta_parts = [x for x in [category, competition, bundesland] if x]
        meta_line = " · ".join(meta_parts)
        return f"""
<div style="border:1px solid rgba(212,245,60,0.15);border-radius:10px;padding:16px 20px;margin:0 0 12px">
  <p style="margin:0 0 4px;font-size:15px;font-weight:700;color:#ffffff">{title}</p>
  {f'<p style="margin:0 0 4px;font-size:12px;color:#6b7280">{date_str}</p>' if date_str else ''}
  {f'<p style="margin:0 0 10px;font-size:12px;color:#6b7280">{meta_line}</p>' if meta_line else ''}
  {f'<a href="{source_url}" style="font-size:12px;color:#d4f53c;text-decoration:none;font-weight:600">Zum Turnier →</a>' if source_url else ''}
</div>"""

    cards_html = "".join(_tournament_card(t) for t in matched_tournaments)

    text_lines = [f"{count} neue{plural_s} Turnier{plural_e} passend zu deinem Jagd-Alarm:\n"]
    for t in matched_tournaments:
        title = t.get("title", "Turnier")
        date_str = t.get("start_date") or t.get("date") or ""
        url = t.get("source_url", "")
        text_lines.append(f"- {title}{' - ' + date_str if date_str else ''}")
        if url:
            text_lines.append(f"  {url}")
    text_lines.append(f"\nKeine weiteren Hinweise: {unsubscribe_url}")
    text = "\n".join(text_lines)

    html = f"""<html><body style="background:#0a0a0a;color:#d1d5db;font-family:sans-serif;padding:40px;max-width:560px;margin:0 auto">
<p style="margin:0 0 28px"><img src="https://www.padelyara.at/logo-white.svg" alt="PadelYara" style="height:28px;width:auto"></p>
<p style="font-size:15px;color:#d1d5db;margin:0 0 24px;line-height:1.6">
  {count} neue{plural_s} Turnier{plural_e} für deine Jagd.
</p>
{cards_html}
<p style="margin:32px 0 0;border-top:1px solid rgba(107,114,128,0.2);padding-top:16px">
  <a href="{unsubscribe_url}" style="font-size:11px;color:#6b7280;text-decoration:none">Keine weiteren Hinweise.</a>
</p>
</body></html>"""

    payload = {
        "sender": {"name": "Yara", "email": "yara@adventure-it.at"},
        "to": [{"email": to_email}],
        "subject": subject,
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
        print(json.dumps({"event": "brevo_error_notification", "status": resp.status_code, "body": resp.text}))


# ── Notification dispatch ─────────────────────────────────────────────────────

def _filter_matches(alert_filters: dict, tournament: dict) -> bool:
    """Return True if a tournament matches the alert's filter criteria.
    An empty list for any filter dimension means 'match all'."""
    checks = [
        ("bundesland", "bundesland"),
        ("category", "category"),
        ("competition", "competition"),
        ("weekday", "weekday"),
        ("venue_name", "venue_name"),
    ]
    for filter_key, t_key in checks:
        allowed = alert_filters.get(filter_key) or []
        if allowed:
            val = tournament.get(t_key) or ""
            if val not in allowed:
                return False
    return True


async def send_alert_notifications(db, new_tournament_ids: list[str]) -> None:
    """Send alert emails to confirmed subscribers whose filters match any of the new tournaments.

    Called from the scheduler after a scrape run, passing source_ids of tournaments
    whose first_seen_at is today (UTC).
    """
    if not new_tournament_ids:
        return

    # Fetch the new tournament documents
    new_tournaments = await db["tournaments"].find(
        {"source_id": {"$in": new_tournament_ids}}
    ).to_list(length=None)

    if not new_tournaments:
        return

    now_iso = datetime.now(timezone.utc).isoformat()

    # Iterate over all confirmed alert subscriptions
    async for alert in db["tournament_alerts"].find({"confirmed": True}):
        alert_filters = alert.get("filters", {})
        matched = [t for t in new_tournaments if _filter_matches(alert_filters, t)]
        if not matched:
            continue

        email = alert["email"]
        unsubscribe_token = alert.get("unsubscribe_token", "")
        print(json.dumps({
            "event": "alert_notification_send",
            "email": email,
            "count": len(matched),
        }))
        try:
            await _send_notification_email(email, unsubscribe_token, matched)
            await db["tournament_alerts"].update_one(
                {"_id": alert["_id"]},
                {"$set": {"last_notified_at": now_iso}},
            )
        except Exception as exc:
            print(json.dumps({"event": "alert_notification_error", "email": email, "error": str(exc)}))


# ── Request/response models ───────────────────────────────────────────────────

class AlertFilters(BaseModel):
    bundesland: list[str] = []
    category: list[str] = []
    competition: list[str] = []
    weekday: list[str] = []
    venue_name: list[str] = []


class AlertBody(BaseModel):
    email: str
    filters: AlertFilters = AlertFilters()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api/tournaments/alerts")
async def create_alert(body: AlertBody, background_tasks: BackgroundTasks):
    """Subscribe (or update) a Jagd-Alarm for new tournaments matching the given filters."""
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return JSONResponse(status_code=422, content={"ok": False, "error": "invalid_email"})

    from venues_mongo import _get_db
    db = _get_db()

    confirm_token = secrets.token_urlsafe(32)
    unsubscribe_token = secrets.token_urlsafe(32)
    filters_dict = body.filters.model_dump()
    now_iso = datetime.now(timezone.utc).isoformat()

    existing = await db["tournament_alerts"].find_one({"email": email})
    if existing:
        # Re-confirm required — overwrite filters, reset confirmed state
        await db["tournament_alerts"].update_one(
            {"email": email},
            {"$set": {
                "filters": filters_dict,
                "confirmed": False,
                "confirm_token": confirm_token,
                "last_notified_at": None,
                "updated_at": now_iso,
            }},
        )
        print(json.dumps({"event": "alert_updated", "email": email}))
    else:
        await db["tournament_alerts"].insert_one({
            "email": email,
            "filters": filters_dict,
            "confirmed": False,
            "confirm_token": confirm_token,
            "unsubscribe_token": unsubscribe_token,
            "created_at": now_iso,
            "confirmed_at": None,
            "last_notified_at": None,
        })
        print(json.dumps({"event": "alert_created", "email": email}))

    background_tasks.add_task(_send_confirmation_email, email, confirm_token)
    return {"ok": True}


@router.get("/api/tournaments/alerts/confirm")
async def confirm_alert(token: str = Query(...)):
    """Activate a Jagd-Alarm via the one-time token sent by email."""
    from venues_mongo import _get_db
    db = _get_db()

    result = await db["tournament_alerts"].find_one_and_update(
        {"confirm_token": token, "confirmed": False},
        {"$set": {
            "confirmed": True,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if not result:
        return RedirectResponse(
            url=f"{_FRONTEND_URL}/turnierjaeger?alert=invalid", status_code=302
        )
    print(json.dumps({"event": "alert_confirmed", "email": result.get("email")}))
    return RedirectResponse(
        url=f"{_FRONTEND_URL}/turnierjaeger?alert=confirmed", status_code=302
    )


@router.get("/api/tournaments/alerts/unsubscribe")
async def unsubscribe_alert(token: str = Query(...)):
    """Delete a Jagd-Alarm via the unsubscribe token included in notification emails."""
    from venues_mongo import _get_db
    db = _get_db()

    result = await db["tournament_alerts"].find_one_and_delete(
        {"unsubscribe_token": token}
    )
    if not result:
        return RedirectResponse(
            url=f"{_FRONTEND_URL}/turnierjaeger?alert=invalid", status_code=302
        )
    print(json.dumps({"event": "alert_unsubscribed", "email": result.get("email")}))
    return RedirectResponse(
        url=f"{_FRONTEND_URL}/turnierjaeger?alert=unsubscribed", status_code=302
    )
