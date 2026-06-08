"""
Compare tournament venue_names against venue names/operators in the venues collection.
Prints venues from tournaments that have NO match in the venues collection.
"""
import asyncio
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    uri = os.environ["MONGODB_URI"]
    client = AsyncIOMotorClient(uri)
    db = client["padel_checker"]

    # Get all distinct venue_names from tournaments
    tournament_venues = await db["tournaments"].distinct("venue_name")
    tournament_venues = set(v for v in tournament_venues if v)
    print(f"Distinct venue names in tournaments: {len(tournament_venues)}")

    # Get all venue names + operators from venues collection
    venue_docs = await db["venues"].find({}, {"name": 1, "operator": 1, "_id": 0}).to_list(length=2000)
    venue_names = set()
    for v in venue_docs:
        if v.get("name"): venue_names.add(v["name"].strip())
        if v.get("operator"): venue_names.add(v["operator"].strip())
    print(f"Distinct names/operators in venues: {len(venue_names)}")

    # Find tournament venues with no match
    unmatched = []
    for tv in sorted(tournament_venues):
        # Try exact match first, then partial
        if tv in venue_names:
            continue
        # Check if any venue name contains this tournament venue or vice versa
        found = False
        for vn in venue_names:
            if tv.lower() in vn.lower() or vn.lower() in tv.lower():
                found = True
                break
        if not found:
            unmatched.append(tv)

    print(f"\n=== {len(unmatched)} tournament venues NOT found in venue DB ===")
    for u in unmatched:
        print(f"  - {u}")

    print(f"\n=== MATCHED: {len(tournament_venues) - len(unmatched)}/{len(tournament_venues)} ===")

asyncio.run(main())
