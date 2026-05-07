"""
Standalone test: can Railway reach Eversports /api/slot without HTTP 403?
Run with: python Backend/test_eversports_api.py
"""
import asyncio
from curl_cffi.requests import AsyncSession

FACILITY_ID = 79237
COURT_IDS   = [101686, 101687, 101688, 101689]
DATE        = "2026-05-08"
CHECK_TIME  = "1800"   # 18:00 in HHMM format

_SLOT_URL = "https://www.eversports.at/api/slot"


async def main():
    params = [("facilityId", FACILITY_ID), ("startDate", DATE)]
    for cid in COURT_IDS:
        params.append(("courts[]", cid))

    print(f"[test] GET {_SLOT_URL}")
    print(f"[test] params: facilityId={FACILITY_ID}  courts={COURT_IDS}  date={DATE}")

    async with AsyncSession(impersonate="chrome124") as session:
        r = await session.get(_SLOT_URL, params=params, timeout=15)

    print(f"\n[result] HTTP status : {r.status_code}")
    print(f"[result] body (first 300 chars):\n{r.text[:300]}")

    if r.status_code != 200:
        print("\n[result] FAILED — non-200 response, Cloudflare likely blocking")
        return

    data  = r.json()
    slots = data.get("slots", [])

    if not isinstance(slots, list):
        print(f"\n[result] unexpected slots shape: {type(slots).__name__} — {str(slots)[:200]}")
        return

    print(f"\n[result] slots parsed : {len(slots)}")

    match = any(s.get("start") == CHECK_TIME for s in slots)
    print(f"[result] 18:00 (HHMM={CHECK_TIME}) : {'FREE' if match else 'BUSY / not available'}")


if __name__ == "__main__":
    asyncio.run(main())
