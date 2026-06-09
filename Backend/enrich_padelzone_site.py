"""Provider-website scraper #1: Padelzone (padelzone.at, a Wix site).

For each active Padelzone venue, find its padelzone.at/<location> page and
extract what the booking platforms don't carry:
  - website_url          (the marketing page itself)
  - amenities            changing_rooms / showers / rental_rackets / gastro / parking
  - num_courts + indoor/outdoor
  - cancellation policy
  - photos               (Wix media, logos/icons filtered out)

DRY-RUN by default — prints a review report and writes NOTHING. Amenities are
fuzzy (keyword + simple negation check), so review the report before --write.

On --write:
  - website_url, photos_scraped, cancellation_policy_scraped are set
  - amenity booleans are set ONLY where currently unset (never overwrite a
    manual value); same for num_courts.

Maintenance script — run locally against prod. NOT in the Docker build. This is
the template for further provider scrapers (padel4fun, padeldome, racketworld …).

Usage:
    python Backend/enrich_padelzone_site.py            # dry-run review report
    python Backend/enrich_padelzone_site.py --write    # persist (after review)
"""
import argparse
import asyncio
import html as htmllib
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

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

BASE = "https://www.padelzone.at"
# Non-location nav paths on padelzone.at, excluded when harvesting /standorte.
_GENERIC = {
    "/abos-tarife", "/academy", "/academy-future", "/attersee-cup", "/blog", "/buchen",
    "/feiern-events", "/gutscheine", "/haftungen", "/impressum", "/info-groups", "/jobs",
    "/kinder", "/levelguide", "/matchmaking", "/merch", "/nadalacademy", "/newsletter",
    "/padelpass", "/padeltennis-court-bauen", "/padeltennis-kontakt", "/padeltennis-vision-team",
    "/privat-training", "/regeln", "/shop", "/sommer-abo", "/standorte", "/support",
    "/turniere", "/unternehmen", "/workshop-kalender", "/workshops",
}
_UMLAUTS = {ord("ä"): "ae", ord("ö"): "oe", ord("ü"): "ue", ord("ß"): "ss"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower().translate(_UMLAUTS))


async def discover_locations(session: AsyncSession) -> list[str]:
    # Include %-encoded / umlaut slugs (e.g. /v%C3%B6sendorf → Vösendorf).
    r = await session.get(f"{BASE}/standorte", timeout=30)
    paths = set(re.findall(r'href="(?:https://www\.padelzone\.at)?(/[a-z0-9\-%äöü]{3,40})"', r.text, re.I))
    return sorted(p for p in paths if unquote(p) not in _GENERIC)


def match_location(venue: dict, slugs: list[str]) -> str | None:
    """Pick the most specific location slug contained in the venue id/name."""
    hay = _norm(venue.get("id", "") + " " + venue.get("name", ""))
    cands = [s for s in slugs if _norm(unquote(s)) in hay]
    return max(cands, key=lambda s: len(_norm(unquote(s)))) if cands else None


def _has(text_low: str, *kws: str) -> bool:
    """True if any keyword appears without a 'kein/keine/ohne' just before it."""
    for kw in kws:
        i = text_low.find(kw)
        while i != -1:
            if not re.search(r"\b(kein|keine|ohne)\b", text_low[max(0, i - 18):i]):
                return True
            i = text_low.find(kw, i + 1)
    return False


# Wix media: keep .jpg photos (logos/icons are .png), drop sponsor names.
_WIX_RE = re.compile(r"static\.wixstatic\.com/media/([0-9a-z]+_[0-9a-z]+~mv2\.jpe?g)", re.I)
_BAD_PHOTO = ("logo", "cupra", "certina", "logoleiste", "sponsor")


def extract_photos(html: str) -> list[str]:
    og = re.findall(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
    seen: dict[str, None] = {}
    for fn in og + [m.group(1) for m in _WIX_RE.finditer(html)]:
        fname = fn.split("/")[-1] if fn.startswith("http") else fn
        if not re.match(r"[0-9a-z]+_[0-9a-z]+~mv2\.jpe?g", fname, re.I):
            continue
        if any(b in fname.lower() for b in _BAD_PHOTO):
            continue
        seen.setdefault(f"https://static.wixstatic.com/media/{fname}", None)
    return list(seen)[:8]


def extract_courts(flat: str) -> tuple[int | None, int | None, int | None]:
    indoor = outdoor = 0
    for m in re.finditer(r"(\d+)\s*x?\s*(indoor|outdoor)\s*courts?", flat, re.I):
        n, kind = int(m.group(1)), m.group(2).lower()
        if kind == "indoor":
            indoor = max(indoor, n)
        else:
            outdoor = max(outdoor, n)
    total = (indoor + outdoor) or None
    return total, (indoor or None), (outdoor or None)


def extract_cancellation(flat: str) -> str | None:
    m = re.search(r"Stornierungsbedingungen[\s:]*([A-ZÄÖÜ].{20,280}?\.)(?:\s{2,}|\s+[A-ZÄÖÜ][a-zäöü]+\s+[A-ZÄÖÜ])", flat)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return None


async def scrape_location(session: AsyncSession, slug: str) -> dict:
    url = f"{BASE}{slug}"
    r = await session.get(url, timeout=30)
    html = r.text
    flat = htmllib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)))
    low = flat.lower()
    total, indoor, outdoor = extract_courts(flat)
    return {
        "website_url":    url,
        "photos":         extract_photos(html),
        "num_courts":     total,
        "indoor_count":   indoor,
        "outdoor_count":  outdoor,
        "changing_rooms": _has(low, "umkleide"),
        "showers":        _has(low, "dusche"),
        "rental_rackets": _has(low, "racketverleih", "leihschläger", "schlägerverleih", "racket verleih"),
        # Real gastro only — a Snackautomat (vending machine) is NOT Gastronomie.
        "gastro":         bool(re.search(r"\b(gastronomie|gastro\s?bereich|bistro|restaurant|caf[eé])\b", low)),
        "parking":        _has(low, "parkplatz", "parkmöglichkeit", "gratis parken", "parken vor ort"),
        "cancellation":   extract_cancellation(flat),
    }


def _b(v: bool) -> str:
    return "✓" if v else "·"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="persist to MongoDB (after review)")
    args = ap.parse_args()

    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise SystemExit("MONGODB_URI not set")
    db = AsyncIOMotorClient(uri)["padel_checker"]

    venues = [v async for v in db["venues"].find({"active": True, "operator": "Padelzone"})]
    print(f"{'WRITE' if args.write else 'DRY-RUN'} — {len(venues)} Padelzone venues\n")

    async with AsyncSession(impersonate="chrome124") as session:
        slugs = await discover_locations(session)
        print(f"{len(slugs)} location pages on padelzone.at\n")

        unmatched, updated = [], 0
        for v in venues:
            vid = v.get("id", "?")
            slug = match_location(v, slugs)
            if not slug:
                unmatched.append(vid)
                print(f"  {vid}: ⚠ no padelzone.at page matched")
                continue
            try:
                d = await scrape_location(session, slug)
            except Exception as e:  # noqa: BLE001
                print(f"  {vid}: ! scrape failed ({e})")
                continue

            courts = f"{d['num_courts']}c" if d["num_courts"] else "?c"
            print(f"  {vid}  →  {slug}")
            print(f"      courts={courts} (in {d['indoor_count']}/out {d['outdoor_count']}) | "
                  f"Umkl {_b(d['changing_rooms'])} Dusch {_b(d['showers'])} "
                  f"Verleih {_b(d['rental_rackets'])} Gastro {_b(d['gastro'])} Park {_b(d['parking'])} | "
                  f"{len(d['photos'])} photos | storno {'✓' if d['cancellation'] else '·'}")
            if d["cancellation"]:
                print(f"      storno: {d['cancellation'][:100]}{'…' if len(d['cancellation']) > 100 else ''}")

            if args.write:
                upd: dict = {"website_url": d["website_url"]}
                if d["photos"]:
                    upd["photos_scraped"] = d["photos"]
                if d["cancellation"]:
                    upd["cancellation_policy_scraped"] = d["cancellation"]
                # amenities + courts: set only where currently unset (never clobber)
                for field in ("changing_rooms", "showers", "rental_rackets", "gastro", "parking"):
                    if v.get(field) is None and d[field]:
                        upd[field] = True
                # Only fill num_courts when there's no authoritative Eversports
                # court list AND none stored — the booking-platform count wins.
                if not v.get("courts") and v.get("num_courts") is None and d["num_courts"]:
                    upd["num_courts"] = d["num_courts"]
                await db["venues"].update_one({"_id": v["_id"]}, {"$set": upd})
                updated += 1

    print(f"\nDone. {len(unmatched)} unmatched: {unmatched}")
    if args.write:
        print(f"Updated {updated} venue document(s).")
    else:
        print("Dry-run only — review the report above, then re-run with --write.")


if __name__ == "__main__":
    asyncio.run(main())
