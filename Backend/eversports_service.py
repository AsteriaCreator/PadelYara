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

    try:
        async with AsyncSession(impersonate="chrome124") as session:
            r = await session.get(_SLOT_URL, params=params, timeout=10)

        if r.status_code != 200:
            print(f"[eversports_service] HTTP {r.status_code} for facilityId={facility_id}")
            return {"status": "platform_check_required", "slots_count": 0}

        data = r.json()
        slots = data.get("slots", [])

        if not isinstance(slots, list):
            print(f"[eversports_service] unexpected slots shape: {type(slots).__name__}")
            return {"status": "platform_check_required", "slots_count": 0}

        slots_count = len(slots)
        for slot in slots:
            if slot.get("start") == time_hhmm:
                return {"status": "free", "slots_count": slots_count}

        return {"status": "busy", "slots_count": slots_count}

    except Exception as exc:
        print(f"[eversports_service] {type(exc).__name__}: {exc}")
        return {"status": "platform_check_required", "slots_count": 0}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("eversports_service:app", host="0.0.0.0", port=port, reload=False)
