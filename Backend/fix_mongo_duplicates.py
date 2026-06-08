"""
One-time cleanup: remove duplicate venue documents from MongoDB and add
a unique index on the `id` field to prevent recurrence.

Usage:
    cd Backend
    python fix_mongo_duplicates.py
"""
import asyncio
import os
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient


def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

_load_env()


async def main():
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise RuntimeError("MONGODB_URI not set")

    client = AsyncIOMotorClient(uri)
    col = client["padel_checker"]["venues"]

    # ── Step 1: find and remove duplicates ───────────────────────────────────
    # For each venue id, keep the document with the lowest _id (oldest insert)
    # and delete any newer duplicates.
    seen: dict[str, object] = {}   # id → _id to keep
    to_delete = []

    async for doc in col.find({}, {"_id": 1, "id": 1}).sort("_id", 1):
        vid = doc.get("id")
        if not vid:
            continue
        if vid in seen:
            to_delete.append(doc["_id"])
            print(f"  [duplicate] id={vid!r}  _id={doc['_id']} — will delete")
        else:
            seen[vid] = doc["_id"]

    if to_delete:
        result = await col.delete_many({"_id": {"$in": to_delete}})
        print(f"\nDeleted {result.deleted_count} duplicate document(s).")
    else:
        print("No duplicates found.")

    # ── Step 2: delete documents with null/missing id ────────────────────────
    null_result = await col.delete_many({"id": None})
    if null_result.deleted_count:
        print(f"Deleted {null_result.deleted_count} document(s) with id=null.")

    # ── Step 3: ensure unique index on `id` ──────────────────────────────────
    await col.create_index("id", unique=True, sparse=True, name="id_unique")
    print("Unique index on `id` ensured.")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
