"""Scrape venue info into MongoDB:

  Eversports venues:
    - photos -> `photos_scraped`              (from the /sb/<slug> booking page)
    - storno -> `cancellation_policy_scraped` (from the /s/<slug> sportpage)

  eTennis venues (white-label /reservierung pages):
    - storno -> `cancellation_policy_scraped` (only ~8% of venues publish it;
      no photo source exists — these pages only carry the club logo)

Never touches the manual fields `photos` / `cancellation_policy` — those are
reserved for own/community input and win in the API (see venues_mongo._detail).

tennis04 is intentionally skipped: its /buchungsplan page is a JS shell with
nothing scrapable statically (and only 4 venues).

Maintenance script, run locally against the production DB (like
enrich_venues_bezirk.py). NOT part of the Docker runtime build.

Usage:
    python Backend/enrich_venue_info.py                 # dry-run, all venues
    python Backend/enrich_venue_info.py --platform etennis
    python Backend/enrich_venue_info.py --slug <id>     # dry-run, one venue
    python Backend/enrich_venue_info.py --limit 5
    python Backend/enrich_venue_info.py --write         # ACTUALLY write
"""
import argparse
import asyncio
import html as htmllib
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

# ── Eversports photos (from the legacy /sb booking page) ──────────────────────
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


# ── Eversports cancellation (from the modern /s sportpage description JSON) ────
def extract_cancellation_eversports(html: str) -> str | None:
    text = (html
            .replace("\\u003C", "<").replace("\\u003E", ">")
            .replace("\\u002F", "/").replace("\\u0026", "&")
            .replace("\\u0027", "'").replace('\\"', '"'))
    for m in re.finditer(r"<p>(.*?)</p>", text, re.S):
        inner = m.group(1)
        if re.search(r"stornier", inner, re.I):
            clean = re.sub(r"<[^>]+>", "", inner)
            clean = re.sub(r"\s+", " ", clean).strip().lstrip("*").strip()
            return clean or None
    return None


# ── eTennis cancellation (announcement marquee / page text) ───────────────────
def extract_cancellation_etennis(html: str) -> str | None:
    """eTennis reservation pages occasionally publish the Stornobedingungen in
    an announcement marquee <li>, or a <p>/<div>. Return the first block whose
    text mentions 'stornier' and is a full sentence (not a one-word footer link)."""
    for li in re.findall(r"<li[^>]*>(.*?)</li>", html, re.I | re.S):
        flat = re.sub(r"<[^>]+>", "", li)
        if re.search(r"stornier", flat, re.I) and len(flat.strip()) > 30:
            return re.sub(r"\s+", " ", htmllib.unescape(flat)).strip() or None
    for tag in ("p", "div"):
        for blk in re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.I | re.S):
            flat = re.sub(r"<[^>]+>", "", blk)
            if re.search(r"stornier", flat, re.I) and 30 < len(flat.strip()) < 600:
                return re.sub(r"\s+", " ", htmllib.unescape(flat)).strip() or None
    return None


# ── Per-platform scrape ───────────────────────────────────────────────────────
async def scrape_eversports(session: AsyncSession, slug: str) -> tuple[list[str], str | None]:
    photos: list[str] = []
    cancellation: str | None = None
    try:
        r = await session.get(f"https://www.eversports.at/sb/{slug}", timeout=30)
        if r.status_code == 200:
            photos = extract_gallery(r.text)
    except Exception as e:  # noqa: BLE001
        print(f"    ! /sb fetch failed: {e}")
    try:
        r = await session.get(f"https://www.eversports.at/s/{slug}", timeout=30)
        if r.status_code == 200:
            cancellation = extract_cancellation_eversports(r.text)
    except Exception as e:  # noqa: BLE001
        print(f"    ! /s fetch failed: {e}")
    return photos, cancellation


async def scrape_etennis(session: AsyncSession, url: str) -> str | None:
    if not url:
        return None
    try:
        r = await session.get(url, timeout=15)
        if r.status_code == 200:
            return extract_cancellation_etennis(r.text)
    except Exception as e:  # noqa: BLE001
        print(f"    ! eTennis fetch failed: {e}")
    return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="actually write to MongoDB")
    ap.add_argument("--slug", help="only this venue id")
    ap.add_argument("--platform", choices=["eversports", "etennis"], help="limit to one platform")
    ap.add_argument("--limit", type=int, default=0, help="cap number of venues")
    args = ap.parse_args()

    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise SystemExit("MONGODB_URI not set (copy Backend/.env.example to Backend/.env)")
    db = AsyncIOMotorClient(uri)["padel_checker"]

    platforms = {
        "eversports": ["Eversports"],
        "etennis": ["eTennis", "etennis"],
    }
    wanted = platforms.get(args.platform) if args.platform else ["Eversports", "eTennis", "etennis"]
    query: dict = {"active": True, "platform": {"$in": wanted}}
    if args.slug:
        query = {"active": True, "id": args.slug}

    venues = [v async for v in db["venues"].find(query)]
    if args.limit:
        venues = venues[: args.limit]

    print(f"{'WRITE' if args.write else 'DRY-RUN'} — {len(venues)} venue(s)\n")

    n_photos = n_storno = updated = 0
    async with AsyncSession(impersonate="chrome124") as session:
        for v in venues:
            vid = v.get("id", "?")
            plat = (v.get("platform") or "").lower()
            photos: list[str] = []
            cancellation: str | None = None

            if plat == "eversports" and v.get("eversports_slug"):
                photos, cancellation = await scrape_eversports(session, v["eversports_slug"])
            elif plat == "etennis":
                cancellation = await scrape_etennis(session, v.get("booking_url") or v.get("public_url") or "")
            else:
                continue

            n_photos += len(photos)
            n_storno += 1 if cancellation else 0
            tag = "" if (photos or cancellation) else "  (nothing)"
            print(f"  [{plat}] {vid}: {len(photos)} photo(s), storno={'YES' if cancellation else '—'}{tag}")
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
