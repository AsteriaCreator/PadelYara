"""
One-time migration: enrich all venue documents with a `bezirk` field.
Run once manually; subsequent runs are safe (idempotent — skips venues that already have bezirk).

Usage:
    python enrich_venues_bezirk.py           # enrich all
    python enrich_venues_bezirk.py --force   # re-enrich even if bezirk already set
"""
import asyncio, os, sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from motor.motor_asyncio import AsyncIOMotorClient
from bezirk_utils import bezirk_from_address

FORCE = "--force" in sys.argv


async def main():
    db = AsyncIOMotorClient(os.environ["MONGODB_URI"])["padel_checker"]
    query = {} if FORCE else {"bezirk": {"$exists": False}}
    venues = await db["venues"].find(query, {"_id": 1, "name": 1, "operator": 1, "address": 1}).to_list(2000)
    print(f"Venues to enrich: {len(venues)}")

    updated = skipped = failed = 0
    for v in venues:
        addr = v.get("address", "")
        bezirk = bezirk_from_address(addr)
        name = (v.get("operator") or v.get("name") or "?")[:40]
        if bezirk:
            await db["venues"].update_one({"_id": v["_id"]}, {"$set": {"bezirk": bezirk}})
            print(f"  OK {name:<40} -> {bezirk}")
            updated += 1
        else:
            await db["venues"].update_one({"_id": v["_id"]}, {"$set": {"bezirk": None}})
            print(f"  ?? {name:<40} -> no PLZ in '{addr[:50]}'")
            failed += 1

    print(f"\nDone. Updated: {updated}, No PLZ: {failed}, Skipped: {skipped}")


asyncio.run(main())
