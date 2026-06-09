"""Scrape venue info from Eversports into MongoDB:
  - photos    -> `photos_scraped`            (from the /sb/<slug> booking page)
  - storno    -> `cancellation_policy_scraped` (from the /s/<slug> sportpage)

Never touches the manual fields `photos` / `cancellation_policy` — those are
reserved for own/community input and win in the API (see venues_mongo._detail).

Maintenance script, run locally against the production DB (like
enrich_venues_bezirk.py). NOT part of the Docker runtime build.

Usage:
    python Backend/enrich_venue_info.py                # dry-run, all Eversports venues
    python Backend/enrich_venue_info.py --slug <id>    # dry-run, one venue by id
    python Backend/enrich_venue_info.py --limit 5      # dry-run, first 5
    python Backend/enrich_venue_info.py --write        # ACTUALLY write to MongoDB
"""
import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

# Windows consoles default to cp1252 and choke on umlauts / arrows in output.
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

# ── Photos (from the legacy /sb booking page) ─────────────────────────────────
_PHOTO_RE = re.compile(
    r"https://files\.eversports\.com/([0-9a-f-]{36})/([^\"'\\\s]+?)-(x-large|large|x-small|small)\.webp",
    re.I,
)
_SKIP_TOKENS = ("logo", "social", "grafiken", "favicon", "icon")
_MAX_PHOTOS = 8


def extract_gallery(html: str) -> list[str]:
    by_uuid: dict[str, str] = {}
    order: list[str] = []
    for m in _PHOTO_RE.finditer(html):
        uuid, name = m.group(1), m.group(2)
        if any(tok in name.lower() for tok in _SKIP_TOKENS):
            continue
        if uuid not in by_uuid:
            order.append(uuid)
        by_uuid[uuid] = f"https://files.eversports.com/{uuid}/{name}-x-large.webp"
    return [by_uuid[u] for u in order][:_MAX_PHOTOS]


# ── Cancellation policy (from the modern /s sportpage description JSON) ────────
def extract_cancellation(html: str) -> str | None:
    """The venue's Stornobedingungen live inside its description as a <p> that
    mentions 'storniert'/'Stornierung'. The JSON escapes angle brackets, so we
    un-escape, then pull the matching paragraph and strip tags + a leading '*'."""
    text = (html
            .replace("\\u003C", "<").replace("\\u003E", ">")
            .replace("\\u002F", "/").replace("\\u0026", "&")
            .replace("\\u0027", "'").replace('\\"', '"'))
    for m in re.finditer(r"<p>(.*?)</p>", text, re.S):
        inner = m.group(1)
        if re.search(r"stornier", inner, re.I):
            clean = re.sub(r"<[^>]+>", "", inner)       # strip nested tags
            clean = re.sub(r"\s+", " ", clean).strip()
            clean = clean.lstrip("*").strip()           # drop markdown emphasis
            return clean or None
    return None


async def scrape_venue(session: AsyncSession, slug: str) -> tuple[list[str], str | None]:
    photos: list[str] = []
    cancellation: str | None = None
    # /sb booking page → photos
    try:
        r = await session.get(f"https://www.eversports.at/sb/{slug}", timeout=30)
        if r.status_code == 200:
            photos = extract_gallery(r.text)
    except Exception as e:  # noqa: BLE001
        print(f"    ! /sb fetch failed: {e}")
    # /s sportpage → cancellation policy
    try:
        r = await session.get(f"https://www.eversports.at/s/{slug}", timeout=30)
        if r.status_code == 200:
            cancellation = extract_cancellation(r.text)
    except Exception as e:  # noqa: BLE001
        print(f"    ! /s fetch failed: {e}")
    return photos, cancellation


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="actually write to MongoDB")
    ap.add_argument("--slug", help="only this venue id")
    ap.add_argument("--limit", type=int, default=0, help="cap number of venues")
    args = ap.parse_args()

    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise SystemExit("MONGODB_URI not set (copy Backend/.env.example to Backend/.env)")
    db = AsyncIOMotorClient(uri)["padel_checker"]

    query: dict = {"active": True, "platform": "Eversports", "eversports_slug": {"$nin": [None, ""]}}
    if args.slug:
        query["id"] = args.slug

    venues = [v async for v in db["venues"].find(query)]
    if args.limit:
        venues = venues[: args.limit]

    print(f"{'WRITE' if args.write else 'DRY-RUN'} — {len(venues)} Eversports venue(s)\n")

    n_photos = n_storno = updated = 0
    async with AsyncSession(impersonate="chrome124") as session:
        for v in venues:
            vid = v.get("id", "?")
            slug = v.get("eversports_slug")
            photos, cancellation = await scrape_venue(session, slug)
            n_photos += len(photos)
            n_storno += 1 if cancellation else 0
            print(f"  {vid}: {len(photos)} photo(s), storno={'YES' if cancellation else '—'}")
            if cancellation:
                print(f"      ↳ {cancellation[:110]}{'…' if len(cancellation) > 110 else ''}")
            if args.write:
                update: dict = {}
                if photos:
                    update["photos_scraped"] = photos
                if cancellation:
                    update["cancellation_policy_scraped"] = cancellation
                if update:
                    await db["venues"].update_one({"_id": v["_id"]}, {"$set": update})
                    updated += 1

    print(f"\nDone. {n_photos} photos; {n_storno}/{len(venues)} venues with storno text.")
    if args.write:
        print(f"Updated {updated} venue document(s).")
    else:
        print("Dry-run only — nothing written. Re-run with --write to persist.")


if __name__ == "__main__":
    asyncio.run(main())
