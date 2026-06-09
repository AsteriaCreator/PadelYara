"""Recover num_courts for eTennis venues from their booking grid.

eTennis white-label booking pages (.../reservierung?c=<id>) render each court
as a cell with class="court...">Platz N<. The distinct court names = the court
count — data the live availability checker sees but never persists. This stores
it as num_courts (the indoor/outdoor split then comes from the venue court_type
via venues_mongo._court_counts).

Only fills num_courts where it's unset and there's no Eversports `courts` array
(that count is authoritative). DRY-RUN by default.

Maintenance script — run locally against prod. NOT in the Docker build.

Usage:
    python Backend/enrich_etennis_courts.py --limit 10   # dry-run sample
    python Backend/enrich_etennis_courts.py              # dry-run all
    python Backend/enrich_etennis_courts.py --write       # persist
"""
import argparse
import asyncio
import html as htmllib
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from curl_cffi.requests import AsyncSession
from motor.motor_asyncio import AsyncIOMotorClient

_COURT_CELL = re.compile(r'class="court[^"]*"[^>]*>\s*([^<]{1,30}?)\s*<', re.I)


def count_courts(html: str) -> tuple[int, list[str]]:
    names = []
    for raw in _COURT_CELL.findall(html):
        n = htmllib.unescape(raw).strip()
        # a real court label has a number (Platz 1, Court 3, Feld 2, …)
        if re.search(r"\d", n) and 2 <= len(n) <= 25 and n not in names:
            names.append(n)
    return len(names), names


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise SystemExit("MONGODB_URI not set")
    db = AsyncIOMotorClient(uri)["padel_checker"]

    venues = [v async for v in db["venues"].find(
        {"active": True, "booking_url": {"$regex": "/reservierung"}})]
    if args.limit:
        venues = venues[: args.limit]
    print(f"{'WRITE' if args.write else 'DRY-RUN'} — {len(venues)} eTennis venues\n")

    got = written = 0
    async with AsyncSession(impersonate="chrome124") as session:
        for v in venues:
            vid = v.get("id", "?")
            if v.get("courts") or v.get("num_courts"):
                print(f"  {vid}: already has courts — skip")
                continue
            try:
                r = await session.get(v["booking_url"], timeout=20)
                n, names = count_courts(r.text) if r.status_code == 200 else (0, [])
            except Exception as e:  # noqa: BLE001
                print(f"  {vid}: ! fetch failed ({e})")
                continue
            if n:
                got += 1
                print(f"  {vid:40} {v.get('court_type','?'):14} -> {n} courts  {names[:8]}")
                if args.write:
                    await db["venues"].update_one({"_id": v["_id"]}, {"$set": {"num_courts": n}})
                    written += 1
            else:
                print(f"  {vid:40} -> (no courts parsed)")
            await asyncio.sleep(0.4)

    print(f"\nGot court counts for {got}/{len(venues)}.")
    print(f"Wrote num_courts to {written}." if args.write else "Dry-run — review, then --write.")


if __name__ == "__main__":
    asyncio.run(main())
