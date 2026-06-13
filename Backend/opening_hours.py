"""
Auto-learned venue opening hours.

Only Eversports needs these: its fast availability path (/api/slot) returns
BOOKED slots only, so "free" is inferred from absence — which has no natural
upper edge. Without a real closing time, a 2 h search could invent a block that
runs past closing. tennis04 (hours from its API) and eTennis (full offered grid)
don't need this.

Eversports' own pages are bot-protected (the calendar grid rejects us, the
venue page 403s), so we can't scrape hours directly. Instead we do exactly what
a human would: Google the venue. We reuse the project's existing Gemini
integration with Google Search grounding to look up each venue's hours and parse
them into structured per-weekday open/close times, stored on the venue document
and refreshed weekly by a scheduler job.

Stored shape on the venue doc:
    opening_hours: { "mon": {"open": "07:00", "close": "23:00"}, ..., "sun": ... }
    opening_hours_updated: ISO-8601 timestamp

A missing weekday (or missing opening_hours entirely) means "unknown" — callers
fall back to a generous default window.
"""

import json
import os
import re
from datetime import datetime, timezone

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Fallback window used when a venue's hours haven't been learned yet. Wide on
# purpose (most padel venues sit inside 07:00–23:00) so we don't hide late free
# slots; the learning job replaces it with the real values per venue.
DEFAULT_OPEN_MIN = 7 * 60
DEFAULT_CLOSE_MIN = 23 * 60

_HHMM_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def hhmm_to_min(hhmm: str) -> int | None:
    m = _HHMM_RE.match(hhmm.strip())
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def day_window_min(opening_hours: dict | None, weekday_idx: int) -> tuple[int, int]:
    """
    (open_min, close_min) for the given weekday (0=Mon..6=Sun). Falls back to the
    generous default window when hours are unknown or unparseable. A venue marked
    closed that day still returns the default rather than (0,0), so we never wrongly
    hide a venue purely on a stale/odd hours record — the booked-slot data and the
    14-day booking window already bound results.
    """
    if opening_hours:
        day = opening_hours.get(WEEKDAYS[weekday_idx])
        if isinstance(day, dict):
            o = hhmm_to_min(str(day.get("open", "")))
            c = hhmm_to_min(str(day.get("close", "")))
            if o is not None and c is not None and c > o:
                return o, c
    return DEFAULT_OPEN_MIN, DEFAULT_CLOSE_MIN


# ── Gemini-grounded lookup ────────────────────────────────────────────────────

_PROMPT = """Find the current opening hours for this padel/tennis venue and return them as JSON.

Venue: {name}
Address: {address}

Use Google Search. Return ONLY a JSON object, no prose, with exactly these keys:
mon, tue, wed, thu, fri, sat, sun. Each value is either:
  - an object {{"open": "HH:MM", "close": "HH:MM"}} in 24-hour time, or
  - null if the venue is closed that day or the hours are unknown.

If the venue is open until after midnight, cap "close" at "23:59".
Only report hours you are confident apply to THIS specific venue at this address.
If you cannot find reliable hours, return all seven days as null."""


def _strip_json(text: str) -> str:
    """Pull a JSON object out of an LLM reply that may be fenced or chatty."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    start, end = t.find("{"), t.rfind("}")
    return t[start : end + 1] if start != -1 and end != -1 and end > start else t


def _validate(parsed: dict) -> dict | None:
    """Keep only well-formed weekday → {open, close} entries. None if nothing valid."""
    out: dict[str, dict] = {}
    for wd in WEEKDAYS:
        day = parsed.get(wd)
        if not isinstance(day, dict):
            continue
        o, c = day.get("open"), day.get("close")
        if isinstance(o, str) and isinstance(c, str) and hhmm_to_min(o) is not None and hhmm_to_min(c) is not None:
            out[wd] = {"open": o, "close": c}
    return out or None


def lookup_opening_hours(name: str, address: str) -> dict | None:
    """
    Ask Gemini (with Google Search grounding) for the venue's opening hours and
    return a validated per-weekday dict, or None if unavailable/not found.
    Network/SDK/parse failures degrade to None — the caller keeps the old value.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None

    client = genai.Client(api_key=key)
    try:
        resp = client.models.generate_content(
            model=os.environ.get("YARA_URTEIL_MODEL", "gemini-3.5-flash"),
            contents=_PROMPT.format(name=name, address=address or "(unbekannt)"),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.0,
            ),
        )
    except Exception as exc:
        print(json.dumps({"event": "opening_hours_lookup_error", "venue": name, "error": str(exc)}))
        return None

    try:
        parsed = json.loads(_strip_json(resp.text or ""))
    except (json.JSONDecodeError, TypeError):
        print(json.dumps({"event": "opening_hours_parse_failed", "venue": name}))
        return None
    return _validate(parsed) if isinstance(parsed, dict) else None


# ── Weekly refresh job (sync; runs in the BackgroundScheduler thread) ──────────

def refresh_eversports_hours() -> int:
    """
    Look up + store opening hours for every active Eversports venue. Uses a
    synchronous pymongo client so it's independent of the app's async event loop.
    Returns the number of venues updated. Safe to run weekly.
    """
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        print(json.dumps({"event": "opening_hours_refresh_skip", "reason": "no_mongodb_uri"}))
        return 0
    try:
        from pymongo import MongoClient
    except ImportError:
        return 0

    cli = MongoClient(uri)
    updated = 0
    try:
        col = cli["padel_checker"]["venues"]
        cursor = col.find(
            {"active": True, "platform": {"$regex": "eversports", "$options": "i"}},
            {"name": 1, "address": 1},
        )
        for doc in cursor:
            hours = lookup_opening_hours(doc.get("name", ""), doc.get("address", ""))
            if hours:
                col.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "opening_hours": hours,
                        "opening_hours_updated": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                updated += 1
        print(json.dumps({"event": "opening_hours_refresh_done", "updated": updated}))
    finally:
        cli.close()
    return updated
