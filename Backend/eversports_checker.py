from curl_cffi.requests import AsyncSession

_SLOT_URL = "https://www.eversports.at/api/slot"


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

    The /api/slot endpoint returns only available slots — booked slots are
    absent.  An empty list means no availability at all.  A slot entry whose
    'start' matches time_hhmm means at least one court is free at that time.

    curl_cffi impersonates Chrome's TLS fingerprint so Cloudflare lets the
    request through without a browser challenge.
    """
    params: list[tuple[str, int | str]] = [
        ("facilityId", facility_id),
        ("startDate", date_str),
    ]
    for cid in court_ids:
        params.append(("courts[]", cid))

    print(f"[Eversports] calling /api/slot  facilityId={facility_id}  courts={court_ids}  date={date_str}  time={time_hhmm}")
    try:
        async with AsyncSession(impersonate="chrome124") as session:
            r = await session.get(_SLOT_URL, params=params, timeout=10)

        print(f"[Eversports] /api/slot HTTP {r.status_code}  facilityId={facility_id}")
        if r.status_code != 200:
            print(f"[Eversports] non-200 body excerpt: {r.text[:300]!r}")
            return "platform_check_required"

        data = r.json()
        slots = data.get("slots", [])
        print(f"[Eversports] slots type={type(slots).__name__}  len={len(slots) if isinstance(slots, list) else 'n/a'}")

        # Without courts[] the API returns {"slots": {"slots": []}} — a nested
        # dict, not a list.  Any non-list response is treated as unexpected.
        if not isinstance(slots, list):
            print(f"[Eversports] unexpected slots shape for facilityId={facility_id}: {type(slots)}")
            return "platform_check_required"

        for slot in slots:
            if slot.get("start") == time_hhmm:
                print(f"[Eversports] matched slot  start={time_hhmm}  court={slot.get('court')}")
                return "free"

        return "busy"

    except Exception as exc:
        print(f"[Eversports] exception  facilityId={facility_id}  {type(exc).__name__}: {exc}")
        return "platform_check_required"
