"""Automated venue-website discovery via DuckDuckGo (no API key, scriptable).

For each active venue without a website_url, search "<name> padel <city>",
filter out booking portals / aggregators / social / news, and propose the
venue's own official site. DRY-RUN review by default; --write sets website_url.

Maintenance script — run locally against prod. NOT in the Docker build.

Usage:
    python Backend/discover_venue_websites.py --limit 10   # dry-run sample
    python Backend/discover_venue_websites.py              # dry-run all
    python Backend/discover_venue_websites.py --write       # persist
"""
import argparse
import asyncio
import html as htmllib
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

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

# Domains that are NOT a venue's own site (booking portals, directories, social).
_EXCLUDE = (
    "eversports.", "tennisplatz.info", "etennis.at", "playtomic.", "tennis04.com",
    "herold.at", "firmenabc.at", "firmeneintrag.", "creditreform.", "evi.gv.at",
    "wko.at", "padel-austria.at", "meinbezirk.at", "noen.at", "google.", "yelp.",
    "facebook.com", "instagram.com", "tiktok.com", "linkedin.com", "youtube.com",
    "twitter.com", "x.com", "wikipedia.org", "tripadvisor.", "padelyara.at",
    "openstreetmap.", "bing.com", "duckduckgo.com", "apple.com", "spotify.",
    # padel directories / booking-aggregator SaaS / business listings (not a venue's own site)
    "trustpadel.com", "padello.de", "padellands.com", "findglocal.com", "citiesapps.com",
    "bestpadel.com", "padeldir.com", "courtbrain.com", "caldaprojects.at",
    "lebenswertes-weinviertel.at", "chayns.site", "cylex.", "padelmaps.org",
    "padelscout.io", "steiermark.com", "salzburgtennis.at", "wildkogelresorts.at",
    "haus-der-zaehne.de", "findglocal.com",
)
_EXCLUDE_PREFIX = ("buchung-", "buchung.", "reservierung.", "booking.")


def _city(addr: str) -> str:
    m = re.search(r"\b\d{4}\s+([A-Za-zÄÖÜäöüß .\-]+)$", (addr or "").strip())
    return m.group(1).strip() if m else ""


_UML = {ord("ä"): "ae", ord("ö"): "oe", ord("ü"): "ue", ord("ß"): "ss"}
# Too-generic to count as a confident name↔domain match on their own.
_GENERIC_TOK = {"padel", "tennis", "arena", "court", "courts", "club", "sport",
                "sports", "wien", "halle", "center", "centre", "the", "padl"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower().translate(_UML))


def _confidence(site: str, name: str, city: str) -> str:
    """HIGH if the domain's main label shares a distinctive token with the
    venue name/city — else LOW (worth a manual eyeball)."""
    label = _norm(_domain(site).split(".")[0])
    toks = {t for t in re.findall(r"[a-zäöü]{4,}", (name + " " + city).lower())
            if t.translate(_UML) not in _GENERIC_TOK}
    return "HIGH" if any(_norm(t) in label for t in toks) else "LOW"


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:  # noqa: BLE001
        return ""


def _ok(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    if any(x in host for x in _EXCLUDE):
        return False
    if any(host.startswith(p) or host.replace("www.", "").startswith(p) for p in _EXCLUDE_PREFIX):
        return False
    return True


def parse_ddg(html: str) -> list[str]:
    """Ordered result URLs from a DuckDuckGo HTML SERP."""
    urls: list[str] = []
    for m in re.finditer(r'href="(//duckduckgo\.com/l/\?uddg=[^"]+|https?://[^"]+)"[^>]*class="result__a"', html):
        urls.append(m.group(1))
    # the class can also come before href — second pass
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"', html):
        urls.append(m.group(1))
    out: list[str] = []
    for u in urls:
        if "uddg=" in u:
            m = re.search(r"uddg=([^&]+)", u)
            u = unquote(m.group(1)) if m else ""
        if u.startswith("http") and u not in out:
            out.append(u)
    return out


async def search_site(session: AsyncSession, name: str, city: str) -> str | None:
    from urllib.parse import quote_plus
    q = f"{name} padel {city}".strip()
    # GET works; POST to the html endpoint returns a CAPTCHA challenge (202).
    r = await session.get(f"https://html.duckduckgo.com/html/?q={quote_plus(q)}", timeout=25)
    for url in parse_ddg(htmllib.unescape(r.text)):
        if _ok(url):
            # normalise to scheme://host (drop deep paths for a clean website_url)
            p = urlparse(url)
            return f"{p.scheme}://{p.netloc}"
    return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--include-low", action="store_true", help="also write LOW-confidence matches")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise SystemExit("MONGODB_URI not set")
    db = AsyncIOMotorClient(uri)["padel_checker"]

    q = {"active": True, "$or": [{"website_url": {"$exists": False}}, {"website_url": None}, {"website_url": ""}]}
    venues = [v async for v in db["venues"].find(q)]
    if args.limit:
        venues = venues[: args.limit]
    print(f"{'WRITE' if args.write else 'DRY-RUN'} — {len(venues)} venues without website_url\n")

    found = written = 0
    async with AsyncSession(impersonate="chrome124") as session:
        for v in venues:
            vid = v.get("id", "?")
            try:
                site = await search_site(session, v.get("name", ""), _city(v.get("address", "")))
            except Exception as e:  # noqa: BLE001
                print(f"  {vid}: ! search failed ({e})")
                continue
            if site:
                conf = _confidence(site, v.get("name", ""), _city(v.get("address", "")))
                found += 1
                flag = "  ⚠ CHECK" if conf == "LOW" else ""
                print(f"  [{conf:4}] {vid:38} -> {site}{flag}")
                if args.write and (conf == "HIGH" or args.include_low):
                    await db["venues"].update_one({"_id": v["_id"]}, {"$set": {"website_url": site}})
                    written += 1
            else:
                print(f"  [ -- ] {vid:38} -> (no clear site)")
            await asyncio.sleep(1.0)  # be polite to DDG

    print(f"\nFound sites for {found}/{len(venues)} venues.")
    if args.write:
        print(f"Wrote {written} website_url(s) ({'incl. LOW' if args.include_low else 'HIGH-confidence only'}).")
    else:
        print("Dry-run — review (esp. ⚠ CHECK rows), then --write (HIGH only) or --write --include-low.")


if __name__ == "__main__":
    asyncio.run(main())
