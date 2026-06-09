"""Provider-website scraper #3: Padelbase (padelbase.at, a Webflow chain site).

19 /standort/<slug> pages with a structured "Details" block — Umkleiden,
Duschen, Gastrobereich, Rezeption, Stornierung. Same review-then-write pattern.

Court counts are intentionally NOT scraped here (the pages phrase them
inconsistently; the live eTennis check already reflects courts). Amenity
booleans + notes only fill blanks; website_url / photos / storno are set.

Maintenance script — run locally against prod. NOT in the Docker build.

Usage:
    python Backend/enrich_padelbase_site.py            # dry-run review
    python Backend/enrich_padelbase_site.py --write    # persist (after review)
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

BASE = "https://www.padelbase.at"
_UML = {ord("ä"): "ae", ord("ö"): "oe", ord("ü"): "ue", ord("ß"): "ss"}
# venue id -> /standort slug, only where token matching is unreliable.
OVERRIDES = {"cupra-arena": "salzburg-indoor-padelbase-cupra-arena", "linz-halle": "linz-halle-indoor"}
_BAD_PHOTO = ("logo", "cupra", "babolat", "sparkasse", "sponsor", "webclip", "icon", "stiegl", "favicon")


def _norm(s: str) -> str:
    n = re.sub(r"[^a-z0-9]", "", (s or "").lower().translate(_UML))
    return n.replace("ue", "u").replace("oe", "o").replace("ae", "a")  # münchen≈munchen


def _has(low: str, *kws: str) -> bool:
    for kw in kws:
        i = low.find(kw)
        while i != -1:
            if not re.search(r"\b(kein|keine|ohne)\b", low[max(0, i - 18):i]):
                return True
            i = low.find(kw, i + 1)
    return False


async def discover(session) -> list[str]:
    r = await session.get(f"{BASE}/standort", timeout=30)
    return sorted(set(re.findall(r"/standort/([a-z0-9\-]+)", r.text, re.I)))


def match(venue: dict, slugs: list[str]) -> str | None:
    if venue.get("id") in OVERRIDES:
        return OVERRIDES[venue["id"]]
    hay = _norm(venue.get("id", "") + venue.get("name", ""))
    cands = [s for s in slugs if _norm(s) in hay or hay in _norm(s)
             or _norm(s.split("-")[-1]) in hay]
    return max(cands, key=lambda s: len(_norm(s))) if cands else None


def extract_photos(html: str) -> list[str]:
    seen: dict[str, None] = {}
    for u in re.findall(r"https://cdn\.prod\.website-files\.com/[^\"'\s)]+?\.(?:jpg|jpeg|webp|png)", html, re.I):
        fname = u.split("/")[-1].lower()
        if any(b in fname for b in _BAD_PHOTO):
            continue
        base = re.sub(r"-p-\d+(\.\w+)$", r"\1", re.sub(r"-\d+x\d+(\.\w+)$", r"\1", u))
        seen.setdefault(base, None)
    return list(seen)[:8]


def extract_cancellation(flat: str) -> str | None:
    m = re.search(r"(Kostenfreie?\s+Stornierung.{10,240}?\.)\s", flat)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def scrape_html(html: str) -> dict:
    flat = htmllib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)))
    low = flat.lower()
    reception = (True if _has(low, "rezeption", "empfang")
                 else False if _has(low, "zutrittscode", "self-service", "selbstbedienung") else None)
    parking = True if _has(low, "parkplatz", "parken", "parkmöglichkeit") else None
    return {
        "photos":         extract_photos(html),
        "changing_rooms": True if _has(low, "umkleide") else None,
        "showers":        True if _has(low, "dusche") else None,
        "reception":      reception,
        "parking":        parking,
        "rental_rackets": True if _has(low, "racketverleih", "leihschläger", "schlägerverleih", "schlägerver.eih") else None,
        "gastro":         True if re.search(r"\b(gastrobereich|gastronomie|padelbar|bistro|restaurant|caf[eé])\b", low) else None,
        "cancellation":   extract_cancellation(flat),
    }


def _b(v) -> str:
    return "✓" if v is True else "✗" if v is False else "·"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise SystemExit("MONGODB_URI not set")
    db = AsyncIOMotorClient(uri)["padel_checker"]

    venues = [v async for v in db["venues"].find(
        {"active": True, "website_url": {"$regex": "padelbase.at"}})]
    print(f"{'WRITE' if args.write else 'DRY-RUN'} — {len(venues)} Padelbase venues\n")

    updated, unmatched = 0, []
    async with AsyncSession(impersonate="chrome124") as session:
        slugs = await discover(session)
        print(f"{len(slugs)} /standort pages\n")
        for v in venues:
            vid = v.get("id", "?")
            slug = match(v, slugs)
            if not slug:
                unmatched.append(vid)
                print(f"  {vid}: ⚠ no page matched")
                continue
            r = await session.get(f"{BASE}/standort/{slug}", timeout=30)
            d = scrape_html(r.text)
            print(f"  {vid}  →  /standort/{slug}")
            print(f"      Umkl {_b(d['changing_rooms'])} Dusch {_b(d['showers'])} Rezeption {_b(d['reception'])} "
                  f"Park {_b(d['parking'])} Verleih {_b(d['rental_rackets'])} Gastro {_b(d['gastro'])} | "
                  f"{len(d['photos'])} photos | storno {'✓' if d['cancellation'] else '·'}")

            if args.write:
                # NB: photos on padelbase.at are site-wide Webflow assets (identical
                # across locations), so they are intentionally NOT persisted.
                upd = {"website_url": f"{BASE}/standort/{slug}"}
                if d["cancellation"]:
                    upd["cancellation_policy_scraped"] = d["cancellation"]
                for f in ("changing_rooms", "showers", "rental_rackets", "gastro", "parking"):
                    if v.get(f) is None and d[f]:
                        upd[f] = True
                if v.get("reception") is None and d["reception"] is not None:
                    upd["reception"] = d["reception"]
                await db["venues"].update_one({"_id": v["_id"]}, {"$set": upd})
                updated += 1

    print(f"\nunmatched: {unmatched}")
    print(f"Updated {updated} venue(s)." if args.write else "Dry-run — review, then --write.")


if __name__ == "__main__":
    asyncio.run(main())
