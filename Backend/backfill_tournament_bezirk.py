"""
One-time backfill: enrich existing tournament documents with `bezirk`
by fuzzy-matching venue_name against the venues collection.

Run after enrich_venues_bezirk.py. Safe to re-run (--force to overwrite existing).
"""
import asyncio, os, re, sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from motor.motor_asyncio import AsyncIOMotorClient

FORCE = "--force" in sys.argv


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\|\-]", " ", s.lower())).strip()


def _fuzzy_bezirk(venue_name: str, pairs: list[tuple[str, str | None]]) -> str | None:
    if not venue_name or not pairs:
        return None
    vn = _norm(venue_name)
    best_len = 0
    best_bezirk = None
    for key, bezirk in pairs:
        if key in vn or vn in key:
            if len(key) > best_len:
                best_len = len(key)
                best_bezirk = bezirk
    return best_bezirk


async def main():
    db = AsyncIOMotorClient(os.environ["MONGODB_URI"])["padel_checker"]

    # Build venue pairs
    venue_docs = await db["venues"].find(
        {"bezirk": {"$exists": True}},
        {"name": 1, "operator": 1, "bezirk": 1}
    ).to_list(2000)

    pairs: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for d in venue_docs:
        bezirk = d.get("bezirk")
        operator = (d.get("operator") or "").strip()
        name = (d.get("name") or "").strip()
        combined = _norm(f"{operator} {name}")
        if combined and combined not in seen:
            pairs.append((combined, bezirk))
            seen.add(combined)
        for part in (operator, name):
            key = _norm(part)
            if key and len(key) > 6 and key not in seen:
                pairs.append((key, bezirk))
                seen.add(key)
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    print(f"Venue pairs: {len(pairs)}")

    venue_names = await db["tournaments"].distinct("venue_name")
    print(f"Distinct tournament venue_names: {len(venue_names)}\n")

    matched = unmatched = 0
    total_updated = 0
    for vn in sorted(venue_names):
        bezirk = _fuzzy_bezirk(vn, pairs)
        if bezirk:
            matched += 1
            print(f"  OK  {vn[:52]:<54} -> {bezirk}")
        else:
            unmatched += 1
            print(f"  ??  {vn[:52]:<54} -> None")

        query = {"venue_name": vn} if FORCE else {"venue_name": vn, "bezirk": {"$exists": False}}
        result = await db["tournaments"].update_many(query, {"$set": {"bezirk": bezirk}})
        total_updated += result.modified_count

    print(f"\nMatched: {matched}/{len(venue_names)} | Updated: {total_updated} tournament docs")

asyncio.run(main())
