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

from auth import _require_admin  # noqa: E402

_BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
_FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.padelyara.at")
_static = os.environ.get("RAILWAY_STATIC_URL", "")
_BACKEND_URL = f"https://{_static}" if _static else _FRONTEND_URL


# ── Email helpers ─────────────────────────────────────────────────────────────

def _format_filters_text(filters: dict) -> str:
    """Render active filters as a human-readable plain-text list."""
    labels = {
        "bundesland": "Bundesland",
        "category": "Level",
        "competition": "Wettbewerb",
        "weekday": "Wochentag",
        "venue_name": "Standort",
    }
    lines = []
    for key, label in labels.items():
        values = filters.get(key) or []
        if values:
            lines.append(f"{label}: {', '.join(values)}")
    return "\n".join(lines) if lines else "Alle neuen Turniere"


def _format_filters_html(filters: dict) -> str:
    """Render active filters as HTML rows for the email."""
    labels = {
        "bundesland": "Bundesland",
        "category": "Level",
        "competition": "Wettbewerb",
        "weekday": "Wochentag",
        "venue_name": "Standort",
    }
    rows = []
    for key, label in labels.items():
        values = filters.get(key) or []
        if values:
            rows.append(
                f'<tr>'
                f'<td style="color:#6b7280;font-size:12px;padding:3px 12px 3px 0;white-space:nowrap">{label}</td>'
                f'<td style="color:#d1d5db;font-size:12px;padding:3px 0">{", ".join(values)}</td>'
                f'</tr>'
            )
    if not rows:
        return '<p style="font-size:12px;color:#6b7280;margin:0">Alle neuen Turniere</p>'
    return f'<table style="border-collapse:collapse">{"".join(rows)}</table>'


async def _send_confirmation_email(to_email: str, token: str, filters: dict) -> None:
    confirm_url = f"{_BACKEND_URL}/api/tournaments/alerts/confirm?token={token}"
    filters_text = _format_filters_text(filters)
    filters_html = _format_filters_html(filters)

    text = (
        f"Du willst wissen, wenn neue Turniere kommen.\n\n"
        f"Dein Jagd-Alarm:\n{filters_text}\n\n"
        f"Verständlich.\n\n"
        f"{confirm_url}\n\n"
        f"Danach melde ich mich. Wenn es sich lohnt.\n\n"
        f"— Yara"
    )
    html = f"""<html><body style="background:#0a0a0a;color:#d1d5db;font-family:sans-serif;padding:40px;max-width:520px;margin:0 auto">
<p style="margin:0 0 36px"><img src="https://www.padelyara.at/logo-white.svg" alt="PadelYara" style="height:28px;width:auto"></p>

<p style="font-size:16px;color:#d1d5db;margin:0 0 12px;line-height:1.7">Du willst wissen, wenn neue Turniere kommen.</p>

<div style="margin:0 0 28px;padding:16px 20px;border-radius:10px;border:1px solid rgba(212,245,60,0.15);background:rgba(212,245,60,0.04)">
  <p style="font-size:11px;color:#6b7280;margin:0 0 10px;text-transform:uppercase;letter-spacing:0.08em">Dein Jagd-Alarm</p>
  {filters_html}
</div>

<p style="font-size:16px;color:#d1d5db;margin:0 0 28px;line-height:1.7">Verständlich.</p>

<p style="margin:0 0 32px">
  <a href="{confirm_url}"
     style="display:inline-block;background:#d4f53c;color:#000000;font-weight:700;
            font-size:14px;letter-spacing:0.06em;text-transform:uppercase;
            padding:14px 28px;border-radius:8px;text-decoration:none">
    Jagd-Alarm aktivieren
  </a>
</p>

<p style="font-size:16px;color:#d1d5db;margin:0 0 32px;line-height:1.7">Danach melde ich mich. Wenn es sich lohnt.</p>
<p style="color:#6b7280;font-size:13px;margin:32px 0 0">— Yara</p>
</body></html>"""

    payload = {
        "sender": {"name": "Yara", "email": "yara@adventure-it.at"},
        "to": [{"email": to_email}],
        "subject": "Jagd-Alarm einrichten.",
        "textContent": text,
        "htmlContent": html,
        "trackOpens": True,
        "trackClicks": True,
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


def _format_reg_deadline(t: dict) -> str:
    """Return a human-readable registration deadline string, or empty string if unknown."""
    raw = t.get("registration_closes_at")
    if not raw:
        return ""
    try:
        from datetime import datetime, timezone
        if isinstance(raw, datetime):
            dt = raw
        else:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return f"{dt.day}.{dt.month}.{dt.year}"
    except Exception:
        return str(raw)[:10] if raw else ""


async def _send_notification_email(
    to_email: str,
    unsubscribe_token: str,
    matched_tournaments: list[dict],
    alert_filters: dict | None = None,
) -> None:
    count = len(matched_tournaments)
    subject = f"{count} neues Turnier für deine Jagd." if count == 1 else f"{count} neue Turniere für deine Jagd."

    unsubscribe_url = f"{_BACKEND_URL}/api/tournaments/alerts/unsubscribe?token={unsubscribe_token}"
    manage_url = f"{_FRONTEND_URL}/turnierjaeger?jagdalarm=open"

    # Build filter summary line for "Du bekommst das weil:" section
    filter_parts: list[str] = []
    if alert_filters:
        for key in ("bundesland", "category", "competition", "weekday", "venue_name"):
            vals = alert_filters.get(key) or []
            filter_parts.extend(vals)

    def _tournament_card(t: dict) -> str:
        title = t.get("title", "Turnier")
        date_str = t.get("start_date") or t.get("date") or ""
        venue = t.get("venue_name", "")
        category = t.get("category", "")
        competition = t.get("competition", "")
        bundesland = t.get("bundesland", "")
        source_id = t.get("source_id", "")
        detail_url = f"{_FRONTEND_URL}/turnierjaeger/turnier/{source_id}" if source_id else ""
        deadline = _format_reg_deadline(t)
        meta_parts = [x for x in [venue, category, competition, bundesland] if x]
        meta_line = " · ".join(meta_parts)
        deadline_html = (
            f'<p style="margin:0 0 8px;font-size:12px;color:#fbbf24;font-weight:600">'
            f'Anmeldeschluss: {deadline}</p>'
        ) if deadline else ""
        p_max = t.get("participants_max") or 0
        p_cur = t.get("participants_current") or 0
        spots_left = max(0, p_max - p_cur) if p_max else None
        if spots_left is None:
            spots_html = ""
        elif spots_left == 0:
            spots_html = '<p style="margin:0 0 8px;font-size:12px;color:#f87171;font-weight:600">Warteliste.</p>'
        elif spots_left <= 5:
            label = "Platz" if spots_left == 1 else "Plätze"
            spots_html = f'<p style="margin:0 0 8px;font-size:12px;color:#fbbf24;font-weight:600">Noch {spots_left} {label} frei.</p>'
        else:
            spots_html = ""
        return f"""
<div style="border:1px solid #2a2a2a;border-radius:10px;padding:16px 20px;margin:0 0 12px;background:#111111">
  <p style="margin:0 0 4px;font-size:15px;font-weight:700;color:#ffffff">{title}</p>
  {f'<p style="margin:0 0 4px;font-size:12px;color:#9ca3af">{date_str}</p>' if date_str else ''}
  {f'<p style="margin:0 0 8px;font-size:12px;color:#6b7280">{meta_line}</p>' if meta_line else ''}
  {deadline_html}
  {spots_html}
  {f'<a href="{detail_url}" style="font-size:13px;color:#d4f53c;text-decoration:none;font-weight:700">Zum Turnier →</a>' if detail_url else ''}
</div>"""

    cards_html = "".join(_tournament_card(t) for t in matched_tournaments)

    filter_badge_html = ""
    if filter_parts:
        badges = "".join(
            f'<span style="display:inline-block;background:#1a1a1a;color:#9ca3af;border:1px solid #2a2a2a;'
            f'font-size:11px;padding:2px 8px;border-radius:4px;margin:0 4px 4px 0">{p}</span>'
            for p in filter_parts
        )
        filter_badge_html = f"""
<div style="margin:20px 0 0;padding:14px 16px;background:#0d1a00;border-radius:8px;border-left:3px solid #d4f53c;border-top:1px solid #2a2a2a;border-right:1px solid #2a2a2a;border-bottom:1px solid #2a2a2a">
  <p style="margin:0 0 6px;font-size:11px;color:#d4f53c;text-transform:uppercase;letter-spacing:0.08em;font-weight:700">Dein Jagdauftrag</p>
  <div style="margin-bottom:10px">{badges}</div>
  <a href="{manage_url}" style="font-size:11px;color:#d4f53c;text-decoration:none">Filter ändern →</a>
</div>"""

    # Plain text
    text_lines = [f"Treffer.\n\n{count} {'neues Turnier' if count == 1 else 'neue Turniere'} für deine Jagd.\n"]
    for t in matched_tournaments:
        title = t.get("title", "Turnier")
        date_str = t.get("start_date") or t.get("date") or ""
        deadline = _format_reg_deadline(t)
        source_id = t.get("source_id", "")
        url = f"{_FRONTEND_URL}/turnierjaeger/turnier/{source_id}" if source_id else ""
        text_lines.append(f"- {title}{' — ' + date_str if date_str else ''}")
        if deadline:
            text_lines.append(f"  Anmeldeschluss: {deadline}")
        p_max = t.get("participants_max") or 0
        p_cur = t.get("participants_current") or 0
        if p_max:
            spots = max(0, p_max - p_cur)
            if spots == 0:
                text_lines.append("  Warteliste.")
            elif spots <= 5:
                text_lines.append(f"  Noch {spots} {'Platz' if spots == 1 else 'Plätze'} frei.")
        if url:
            text_lines.append(f"  {url}")
    if filter_parts:
        text_lines.append(f"\nDein Jagdauftrag: {' · '.join(filter_parts)}")
        text_lines.append(f"Filter ändern: {manage_url}")
    text_lines.append("\nMach was daraus.\n\n— Yara")
    text_lines.append(f"\npadelyara.at")
    text_lines.append(f"Du erhältst diese E-Mail weil du einen Jagd-Alarm auf padelyara.at aktiviert hast.")
    text_lines.append(f"Abmelden: {unsubscribe_url}")
    text = "\n".join(text_lines)

    html = f"""<html><body style="background:#0a0a0a;font-family:Arial,sans-serif;padding:32px 16px;margin:0">
<div style="max-width:560px;margin:0 auto">
  <p style="margin:0 0 32px;font-size:20px;font-weight:900;color:#d4f53c;letter-spacing:0.04em">PadelYara</p>
  <p style="font-size:16px;color:#ffffff;margin:0 0 4px;font-weight:700">
    {count} {'neues Turnier' if count == 1 else 'neue Turniere'} für deine Jagd.
  </p>
  <p style="font-size:13px;color:#d4f53c;margin:0 0 24px;font-weight:600">Treffer.</p>
  {cards_html}
  {filter_badge_html}
  <p style="font-size:14px;color:#6b7280;margin:24px 0 4px;font-style:italic">Mach was daraus.</p>
  <p style="font-size:14px;color:#9ca3af;margin:0 0 32px">— Yara</p>
  <div style="padding-top:16px;border-top:1px solid #1f1f1f">
    <p style="margin:0 0 6px;font-size:12px">
      <a href="{_FRONTEND_URL}" style="color:#d4f53c;text-decoration:none;font-weight:700">padelyara.at</a>
    </p>
    <p style="margin:0;font-size:11px;color:#4b5563">
      Du erhältst diese E-Mail weil du einen Jagd-Alarm auf padelyara.at aktiviert hast. &nbsp;·&nbsp;
      <a href="{unsubscribe_url}" style="color:#4b5563;text-decoration:none">Abmelden</a>
    </p>
  </div>
</div>
</body></html>"""

    payload = {
        "sender": {"name": "Yara", "email": "yara@adventure-it.at"},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": text,
        "htmlContent": html,
        "trackOpens": True,
        "trackClicks": True,
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
            await _send_notification_email(email, unsubscribe_token, matched, alert_filters)
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

_ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "mayer.conny@gmail.com")

@router.get("/api/tournaments/alerts/email-stats", dependencies=[Depends(_require_admin)])
async def alert_email_stats():
    """Fetch Brevo transactional email stats for the last 30 days, excluding the admin email."""
    from datetime import date, timedelta
    end = date.today()
    start = end - timedelta(days=30)
    params_base = {"startDate": str(start), "endDate": str(end), "limit": 100}

    delivered_ids: set[str] = set()
    opened_emails: set[str] = set()
    clicked_emails: set[str] = set()
    total_opens = 0
    total_clicks = 0

    async with httpx.AsyncClient() as client:
        for event_type, target_set, is_count_only in [
            ("delivered", delivered_ids, False),
            ("opened",    opened_emails, False),
            ("clicks",    clicked_emails, False),
        ]:
            offset = 0
            while True:
                resp = await client.get(
                    "https://api.brevo.com/v3/smtp/statistics/events",
                    params={**params_base, "event": event_type, "offset": offset},
                    headers={"api-key": _BREVO_API_KEY},
                    timeout=10,
                )
                if resp.status_code >= 400:
                    break
                events = resp.json().get("events", [])
                for ev in events:
                    email = ev.get("email", "")
                    if email == _ADMIN_EMAIL:
                        continue
                    msg_id = ev.get("messageId", "") or ev.get("subject", "") + email
                    if event_type == "delivered":
                        delivered_ids.add(msg_id)
                    elif event_type == "opened":
                        opened_emails.add(email)
                        total_opens += 1
                    elif event_type == "clicks":
                        clicked_emails.add(email)
                        total_clicks += 1
                if len(events) < 100:
                    break
                offset += 100

    return {
        "requests": len(delivered_ids),
        "delivered": len(delivered_ids),
        "opens": total_opens,
        "uniqueOpens": len(opened_emails),
        "clicks": total_clicks,
        "uniqueClicks": len(clicked_emails),
    }


@router.get("/api/tournaments/alerts/count", dependencies=[Depends(_require_admin)])
async def alerts_count():
    """Admin: count of confirmed Jagd-Alarm subscribers."""
    from venues_mongo import _get_db
    db = _get_db()
    count = await db["tournament_alerts"].count_documents({"confirmed": True})
    return {"count": count}


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

    background_tasks.add_task(_send_confirmation_email, email, confirm_token, filters_dict)
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


@router.get("/api/tournaments/alerts/list", dependencies=[Depends(_require_admin)])
async def alerts_list():
    """Admin: list all Jagd-Alarm subscriptions (confirmed + pending)."""
    from venues_mongo import _get_db
    db = _get_db()
    docs = await db["tournament_alerts"].find(
        {}, {"confirm_token": 0, "unsubscribe_token": 0, "_id": 0}
    ).sort("created_at", -1).to_list(length=500)
    return {"alerts": docs}


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
