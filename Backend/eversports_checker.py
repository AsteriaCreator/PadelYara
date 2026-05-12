import json

from curl_cffi.requests import AsyncSession

_SLOT_URL = "https://www.eversports.at/api/slot"


def _parse_slots(text: str) -> list | None:
    """
    Parse /api/slot JSON response.

    The API returns two formats:
      • With results:  {"slots": [{...}, ...]}          <- flat list
      • Empty results: {"slots": {"slots": [], ...}}    <- nested object

    Both are normalised to a list (possibly empty).
    Returns None only on JSON parse failure or unexpected structure.
    """
    try:
        data = json.loads(text)
        slots = data.get("slots", [])
        if isinstance(slots, list):
            return slots
        if isinstance(slots, dict):
            inner = slots.get("slots", [])
            return inner if isinstance(inner, list) else None
        return None
    except Exception:
        return None


async def check_eversports(
    facility_id: int,
    court_ids: list[int],
    date_str: str,
    time_hhmm: str,
) -> str:
    """
    Returns 'free' | 'busy' | 'platform_check_required'.

    date_str  : 'YYYY-MM-DD'
    time_hhmm : 'HHMM', e.g. '1800'

    The /api/slot endpoint returns only AVAILABLE (free) slots starting from
    startDate.  A slot entry whose date+start matches our target means that
    court is free right now.

    Busy-vs-ambiguous heuristic when target slot is absent from the response:
      • Free slots exist on dates AFTER our target date  → target slot is BUSY
      • Free slots exist later on the SAME day           → target slot is BUSY
      • Response is empty or ends before our target      → AMBIGUOUS
                                                           → platform_check_required

    curl_cffi impersonates Chrome's TLS fingerprint so Cloudflare lets the
    GET request through without a browser challenge.
    """
    params: list[tuple[str, int | str]] = [
        ("facilityId", facility_id),
        ("startDate", date_str),
    ]
    for cid in court_ids:
        params.append(("courts[]", cid))

    print(json.dumps({
        "event":       "eversports_check_start",
        "facility_id": facility_id,
        "court_ids":   court_ids,
        "date":        date_str,
        "time":        time_hhmm,
    }))

    try:
        async with AsyncSession(impersonate="chrome124") as session:
            r = await session.get(_SLOT_URL, params=params, timeout=10)

        print(f"[Eversports] /api/slot HTTP {r.status_code}  facilityId={facility_id}")

        if r.status_code != 200:
            print(f"[Eversports] non-200 body excerpt: {r.text[:300]!r}")
            return "platform_check_required"

        slots = _parse_slots(r.text)
        if slots is None:
            print(f"[Eversports] unexpected response structure for facilityId={facility_id}")
            return "platform_check_required"

        slots_count = len(slots)
        all_dates  = [s.get("date",  "") for s in slots if s.get("date")]
        starts_seq = [s.get("start", "") for s in slots if s.get("start")]
        max_date   = max(all_dates) if all_dates else ""

        print(json.dumps({
            "event":        "eversports_slot_scope",
            "facility_id":  facility_id,
            "date":         date_str,
            "time":         time_hhmm,
            "slots_count":  slots_count,
            "first_starts": starts_seq[:3],
            "last_starts":  starts_seq[-3:] if len(starts_seq) > 3 else starts_seq,
            "max_date":     max_date,
        }))

        # Target slot present → free
        if any(s.get("start") == time_hhmm and s.get("date") == date_str for s in slots):
            print(f"[Eversports] MATCH at {date_str} {time_hhmm} → free")
            return "free"

        # Scope heuristic — is there evidence the target is booked?
        same_day_starts = [
            s.get("start", "") for s in slots
            if s.get("date") == date_str and s.get("start")
        ]
        max_same_day = max(same_day_starts) if same_day_starts else ""

        if max_date > date_str:
            print(f"[Eversports] scope ({max_date}) > target ({date_str}) → busy")
            return "busy"
        if max_same_day > time_hhmm:
            print(f"[Eversports] same-day max ({max_same_day}) > {time_hhmm} → busy")
            return "busy"

        # Empty or only covers times before/at target — genuinely ambiguous
        print(
            f"[Eversports] ambiguous: max_date={max_date or 'empty'} "
            f"same_day_max={max_same_day or 'none'} → platform_check_required"
        )
        return "platform_check_required"

    except Exception as exc:
        print(f"[Eversports] exception  facilityId={facility_id}  {type(exc).__name__}: {exc}")
        return "platform_check_required"
