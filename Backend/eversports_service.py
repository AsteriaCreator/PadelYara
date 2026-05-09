import os

from curl_cffi.requests import AsyncSession
from fastapi import FastAPI, Query

app = FastAPI()

_SLOT_URL = "https://www.eversports.at/api/slot"


@app.get("/check")
async def check(
    facility_id: int = Query(...),
    court_ids: str = Query(...),
    date: str = Query(...),
    time: str = Query(...),
):
    cids = [int(c.strip()) for c in court_ids.split(",")]
    time_hhmm = time.replace(":", "")  # "18:00" -> "1800"

    params: list[tuple[str, int | str]] = [
        ("facilityId", facility_id),
        ("startDate", date),
    ]
    for cid in cids:
        params.append(("courts[]", cid))

    print(f"[check] facilityId={facility_id} courts={cids} date={date} time_hhmm={time_hhmm}")

    try:
        async with AsyncSession(impersonate="chrome124") as session:
            r = await session.get(_SLOT_URL, params=params, timeout=10)

        print(f"[check] HTTP {r.status_code}  body[:300]={r.text[:300]!r}")

        if r.status_code != 200:
            return {"status": "platform_check_required", "slots_count": 0}

        data = r.json()
        slots = data.get("slots", [])
        print(f"[check] slots type={type(slots).__name__}  len={len(slots) if isinstance(slots, list) else 'n/a'}")

        if not isinstance(slots, list):
            return {"status": "platform_check_required", "slots_count": 0}

        slots_count = len(slots)
        for slot in slots:
            if slot.get("start") == time_hhmm:
                print(f"[check] MATCH at start={time_hhmm}  court={slot.get('court')}")
                return {"status": "free", "slots_count": slots_count}

        print(f"[check] no match for time_hhmm={time_hhmm!r}  first starts={[s.get('start') for s in slots[:5]]}")
        return {"status": "busy", "slots_count": slots_count}

    except Exception as exc:
        print(f"[check] EXCEPTION {type(exc).__name__}: {exc}")
        return {"status": "platform_check_required", "slots_count": 0}


@app.get("/diag")
async def diag(
    facility_id: int = Query(default=79237),
    court_ids: str = Query(default="101686,101687,101688,101689"),
    date: str = Query(default="2026-05-10"),
    time: str = Query(default="18:00"),
):
    """Diagnostic endpoint: returns raw Eversports API response details."""
    cids = [int(c.strip()) for c in court_ids.split(",")]
    time_hhmm = time.replace(":", "")

    params: list[tuple[str, int | str]] = [
        ("facilityId", facility_id),
        ("startDate", date),
    ]
    for cid in cids:
        params.append(("courts[]", cid))

    try:
        async with AsyncSession(impersonate="chrome124") as session:
            r = await session.get(_SLOT_URL, params=params, timeout=10)

        body_excerpt = r.text[:500]
        slots = []
        slots_type = "n/a"
        parse_error = None

        if r.status_code == 200:
            try:
                data = r.json()
                raw_slots = data.get("slots", [])
                slots_type = type(raw_slots).__name__
                if isinstance(raw_slots, list):
                    slots = raw_slots
            except Exception as e:
                parse_error = str(e)

        matching = [s for s in slots if s.get("start") == time_hhmm]

        return {
            "http_status":    r.status_code,
            "body_excerpt":   body_excerpt,
            "slots_type":     slots_type,
            "slots_count":    len(slots),
            "time_hhmm":      time_hhmm,
            "matching_slots": matching,
            "result":         "free" if matching else ("busy" if slots else "platform_check_required"),
            "parse_error":    parse_error,
            "first_5_starts": [s.get("start") for s in slots[:5]],
        }

    except Exception as exc:
        return {
            "exception": type(exc).__name__,
            "detail":    str(exc),
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("eversports_service:app", host="0.0.0.0", port=port, reload=False)
