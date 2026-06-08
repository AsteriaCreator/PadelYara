"""Check what address/location fields actually exist in venue documents."""
import asyncio, os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    db = AsyncIOMotorClient(os.environ["MONGODB_URI"])["padel_checker"]

    # Get a sample of venues with all their fields
    docs = await db["venues"].find({}, {"_id": 0}).to_list(length=5)
    for d in docs:
        print({k: v for k, v in d.items() if k not in ("eversports_court_ids", "courts", "slot_fallback_minutes")})
        print()

    # Check which address-like fields exist across the collection
    all_keys = set()
    async for doc in db["venues"].find({}, {"_id": 0}):
        all_keys.update(doc.keys())
    print("All field names in venues collection:")
    print(sorted(all_keys))

asyncio.run(main())
