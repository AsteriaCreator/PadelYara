"""Give every active venue a proper, SEO-friendly slug `id`.

Root cause: a one-off eTennis-network import created ~104 venues with
`platform:"eTennis"` but no `id` field. `venues_mongo._normalize` masked this
(`id = id or _id`), so the map/search worked but `/court/:slug` detail pages —
which query strictly by `id` — 404'd (or resolved via the ugly _id hex).

This backfills a name-based slug for venues that have no `id`. Existing slug
ids are left untouched. Uniqueness is enforced against ALL venue ids.

Maintenance script, run locally against the production DB. NOT in the Docker
build.

Usage:
    python Backend/backfill_venue_slugs.py            # dry-run
    python Backend/backfill_venue_slugs.py --write    # persist
"""
import argparse
import asyncio
import os
import re
import sys
import unicodedata
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

from motor.motor_asyncio import AsyncIOMotorClient

_UMLAUTS = {
    ord("ä"): "ae", ord("ö"): "oe", ord("ü"): "ue",
    ord("Ä"): "ae", ord("Ö"): "oe", ord("Ü"): "ue", ord("ß"): "ss",
}


def slugify(name: str) -> str:
    s = (name or "").translate(_UMLAUTS)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "venue"


def _is_missing(v: dict) -> bool:
    return not v.get("id")  # missing, None, or ""


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="persist to MongoDB")
    args = ap.parse_args()

    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise SystemExit("MONGODB_URI not set")
    db = AsyncIOMotorClient(uri)["padel_checker"]

    all_venues = [v async for v in db["venues"].find({})]
    taken = {v["id"] for v in all_venues if v.get("id")}
    missing = [v for v in all_venues if _is_missing(v) and v.get("active", False)]

    print(f"{len(all_venues)} venues total; {len(taken)} already have an id; "
          f"{len(missing)} active venues need one.\n")

    assignments: list[tuple] = []
    for v in missing:
        base = slugify(v.get("name", ""))
        slug = base
        n = 2
        while slug in taken:
            slug = f"{base}-{n}"
            n += 1
        taken.add(slug)
        assignments.append((v["_id"], v.get("name", "?"), v.get("platform", "?"), slug))

    for _id, name, platform, slug in assignments:
        print(f"  [{platform}] {name!r:45} -> {slug}")

    if args.write:
        for _id, _name, _platform, slug in assignments:
            await db["venues"].update_one({"_id": _id}, {"$set": {"id": slug}})
        print(f"\nWrote id to {len(assignments)} venue document(s).")
    else:
        print(f"\nDry-run only — {len(assignments)} slugs proposed. Re-run with --write.")


if __name__ == "__main__":
    asyncio.run(main())
