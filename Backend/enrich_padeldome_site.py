"""Provider-website scraper #2: Padeldome (padeldome.at — the real marketing
site, NOT the padeldome.wien booking portal).

Per-location WordPress pages at /standort/<slug>/ carry photos + amenities incl.
Rezeption and parking notes. Same review-then-write pattern as Padelzone.

DRY-RUN by default. On --write: website_url / photos_scraped /
cancellation_policy_scraped are set; amenity booleans + notes + num_courts only
fill blanks (never clobber a manual value).

Maintenance script — run locally against prod. NOT in the Docker build.

Usage:
    python Backend/enrich_padeldome_site.py            # dry-run review
    python Backend/enrich_padeldome_site.py --write    # persist (after review)
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

BASE = "https://www.padeldome.at"
# venue id -> /standort/<slug>/ (curated; the .at slugs use a 'wien-' prefix the
# venue names lack, so a token match is unreliable here). Alte Donau in+out share
# one page; Stadlau has no page yet.
SLUG_MAP = {
    "padeldome-alt-erlaa":          "wien-alterlaa",
    "padeldome-erdberg":            "wien-erdberg",
    "padeldome-suessenbrunn":       "wien-suessenbrunn",
    "padeldome-alte-donau-outdoor": "alte-donau",
    "padeldome-alte-donau-indoor":  "alte-donau",
    "padeldome-wien-stadlau":       None,
}


def _has(low: str, *kws: str) -> bool:
    for kw in kws:
        i = low.find(kw)
        while i != -1:
            if not re.search(r"\b(kein|keine|ohne)\b", low[max(0, i - 18):i]):
                return True
            i = low.find(kw, i + 1)
    return False


def extract_photos(html: str) -> list[str]:
    """WordPress uploads; strip the -WxH resize suffix to get the original,
    drop logos/icons. og:image first."""
    og = re.findall(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
    urls = og + re.findall(r'https?://[^"\'\s)]+?/wp-content/uploads/[^"\'\s)]+?\.(?:jpg|jpeg|png)', html, re.I)
    seen: dict[str, None] = {}
    for u in urls:
        if re.search(r"logo|icon|favicon|sprite|placeholder|cropped", u, re.I):
            continue
        u = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", u)  # 'foo-1024x689.jpg' -> 'foo.jpg'
        seen.setdefault(u, None)
    return list(seen)[:8]


def extract_courts(flat: str) -> tuple[int | None, int | None, int | None]:
    # Only the explicit "N Indoorplätze / N Outdoorplätze" phrasing is reliable;
    # generic "courts" counts on marketing pages are often promo numbers.
    indoor = outdoor = 0
    for m in re.finditer(r"(\d+)\s*indoorpl[äa]tze", flat, re.I):
        indoor = max(indoor, int(m.group(1)))
    for m in re.finditer(r"(\d+)\s*outdoorpl[äa]tze", flat, re.I):
        outdoor = max(outdoor, int(m.group(1)))
    total = (indoor + outdoor) or None
    return total, (indoor or None), (outdoor or None)


def extract_cancellation(flat: str) -> str | None:
    m = re.search(r"Stornierungsbedingungen[\s:]*([A-ZÄÖÜ].{20,260}?\.)\s", flat)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def extract_reception(low: str) -> tuple[bool | None, str | None]:
    if _has(low, "rezeption", "empfang"):
        note = None
        if "nicht durchgehend" in low:
            note = "nicht durchgehend besetzt"
        return True, note
    if _has(low, "zutrittscode", "self-service", "selbstbedienung", "self service"):
        return False, "Self-Service / Zutrittscode"
    return None, None


def extract_parking(low: str) -> tuple[bool | None, str | None]:
    if _has(low, "parkplatz", "parken", "parkmöglichkeit"):
        m = re.search(r"(\d+\s*stunden?\s*gratis|gratis\s*park\w*|kostenlos\s*park\w*)", low)
        note = m.group(1).strip().title() if m else ("Gratis" if "gratis" in low and "park" in low else None)
        return True, note
    return None, None


async def scrape(session: AsyncSession, slug: str) -> dict:
    url = f"{BASE}/standort/{slug}/"
    r = await session.get(url, timeout=30)
    html = r.text
    flat = htmllib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)))
    low = flat.lower()
    total, indoor, outdoor = extract_courts(flat)
    reception, reception_note = extract_reception(low)
    parking, parking_note = extract_parking(low)
    return {
        "website_url":    url,
        "photos":         extract_photos(html),
        "num_courts":     total, "indoor_count": indoor, "outdoor_count": outdoor,
        "changing_rooms": True if _has(low, "umkleide") else None,
        "showers":        True if _has(low, "dusche") else None,
        "reception":      reception, "reception_note": reception_note,
        "parking":        parking, "parking_note": parking_note,
        "rental_rackets": True if _has(low, "racketverleih", "leihschläger", "schlägerverleih") else None,
        "gastro":         True if re.search(r"\b(padelbar|gastronomie|bistro|restaurant|caf[eé])\b", low) else None,
        "cancellation":   extract_cancellation(flat),
    }


def _b(v) -> str:
    return "✓" if v is True else ("✗" if v is False else "·")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise SystemExit("MONGODB_URI not set")
    db = AsyncIOMotorClient(uri)["padel_checker"]

    venues = [v async for v in db["venues"].find({"active": True, "operator": {"$regex": "padeldome", "$options": "i"}})]
    print(f"{'WRITE' if args.write else 'DRY-RUN'} — {len(venues)} Padeldome venues\n")

    updated = 0
    async with AsyncSession(impersonate="chrome124") as session:
        for v in venues:
            vid = v.get("id", "?")
            slug = SLUG_MAP.get(vid)
            if not slug:
                print(f"  {vid}: ⚠ no padeldome.at page")
                continue
            d = await scrape(session, slug)
            print(f"  {vid}  →  /standort/{slug}/")
            print(f"      courts={d['num_courts']} (in {d['indoor_count']}/out {d['outdoor_count']}) | "
                  f"Umkl {_b(d['changing_rooms'])} Dusch {_b(d['showers'])} Rezeption {_b(d['reception'])} "
                  f"Park {_b(d['parking'])}{f' ({d['parking_note']})' if d['parking_note'] else ''} "
                  f"Verleih {_b(d['rental_rackets'])} Gastro {_b(d['gastro'])} | "
                  f"{len(d['photos'])} photos | storno {'✓' if d['cancellation'] else '·'}")
            if d["reception_note"]:
                print(f"      reception: {d['reception_note']}")

            if args.write:
                upd = {"website_url": d["website_url"]}
                if d["photos"]:
                    upd["photos_scraped"] = d["photos"]
                if d["cancellation"]:
                    upd["cancellation_policy_scraped"] = d["cancellation"]
                    if not v.get("cancellation_url"):
                        upd["cancellation_url"] = d["website_url"]  # specific /standort/ page
                for f in ("changing_rooms", "showers", "reception", "parking", "rental_rackets", "gastro"):
                    if v.get(f) is None and d[f] is not None:
                        upd[f] = d[f]
                        upd[f"field_sources.{f}"] = "padeldome_scraper"
                for note in ("reception_note", "parking_note"):
                    if not v.get(note) and d[note]:
                        upd[note] = d[note]
                if not v.get("courts") and v.get("num_courts") is None and d["num_courts"]:
                    upd["num_courts"] = d["num_courts"]
                await db["venues"].update_one({"_id": v["_id"]}, {"$set": upd})
                updated += 1

    if args.write:
        print(f"\nUpdated {updated} venue document(s).")
    else:
        print("\nDry-run only — review, then re-run with --write.")


if __name__ == "__main__":
    asyncio.run(main())
