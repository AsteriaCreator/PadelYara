"""
Scrape Eversports listing pages + Playtomic Austria for padel venues,
then diff against what's already in MongoDB.
"""
import asyncio
import re
import json
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import urllib.request
import urllib.error

load_dotenv("Backend/.env")
uri = os.getenv("MONGODB_URI")
client = MongoClient(uri)
db = client["padel_checker"]
venues_col = db["venues"]

# ── Load existing venue slugs / names from DB ─────────────────────────────────
existing = list(venues_col.find({}, {"id": 1, "name": 1, "eversports_slug": 1, "booking_url": 1}))
existing_slugs = {v.get("eversports_slug", "") for v in existing}
existing_ids   = {v.get("id", "") for v in existing}
existing_urls  = {v.get("booking_url", "") for v in existing}

def fetch_html(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "de-AT,de;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"ERROR:{e}"

# ── 1. Eversports listing pages ───────────────────────────────────────────────
EVERSPORTS_CITIES = [
    "wien", "graz", "linz", "salzburg", "innsbruck",
    "klagenfurt", "bregenz", "wels", "st-poelten", "wiener-neustadt",
    "eisenstadt", "feldkirch", "steyr", "krems", "villach",
]

print("=" * 60)
print("EVERSPORTS /l/padel/<city>")
print("=" * 60)

eversports_found = {}  # slug -> {name, city, url}

for city in EVERSPORTS_CITIES:
    url = f"https://www.eversports.at/l/padel/{city}"
    html = fetch_html(url)
    if html.startswith("ERROR"):
        print(f"  {city}: {html}")
        continue

    # Extract facility slugs from href="/sb/<slug>"
    slugs = re.findall(r'href="/sb/([^"?#]+)"', html)
    # Also extract names from title or h tags near those links
    # Pattern: <a href="/sb/slug">...<span>Name</span> or similar
    # Let's extract name from og:title or structured data, or just near the link

    # Try to find venue cards: look for slug + name pairs
    # Eversports uses patterns like: /sb/slug">...<div class="...">Name
    card_pattern = re.findall(
        r'href="/sb/([^"?#]+)"[^>]*>.*?<[^>]+class="[^"]*(?:name|title)[^"]*"[^>]*>([^<]+)<',
        html, re.DOTALL
    )

    # Fallback: just unique slugs on page
    unique_slugs = list(dict.fromkeys(s for s in slugs if s and len(s) > 3 and "?" not in s))

    new_count = 0
    for slug in unique_slugs:
        if slug not in eversports_found:
            eversports_found[slug] = {"city": city, "url": f"https://www.eversports.at/sb/{slug}"}
            if slug not in existing_slugs and f"https://www.eversports.at/sb/{slug}" not in existing_urls:
                new_count += 1

    print(f"  {city}: {len(unique_slugs)} venues found, {new_count} new")

print()
print("── Eversports: all found venues ──")
new_eversports = []
for slug, info in sorted(eversports_found.items()):
    in_db = slug in existing_slugs or f"https://www.eversports.at/sb/{slug}" in existing_urls
    status = "✓ in DB" if in_db else "★ NEW"
    print(f"  [{status}]  {slug}  ({info['city']})")
    if not in_db:
        new_eversports.append({"slug": slug, **info})

print(f"\nTotal Eversports: {len(eversports_found)} venues, {len(new_eversports)} not in DB")

# ── 2. Playtomic Austria ──────────────────────────────────────────────────────
print()
print("=" * 60)
print("PLAYTOMIC Austria")
print("=" * 60)

# Playtomic venue list pages
playtomic_urls = [
    "https://playtomic.io/tenants?sport_id=PADEL&address=Austria&radius=200000&page=0",
    "https://playtomic.io/de-at/padel",
    "https://api.playtomic.io/v1/tenants?sport_id=PADEL&address=Austria&radius=200000&page=0",
]

for url in playtomic_urls:
    html = fetch_html(url)
    if html.startswith("ERROR"):
        print(f"  {url[:60]}: {html}")
        continue

    # Try JSON first (API endpoint)
    try:
        data = json.loads(html)
        if isinstance(data, list):
            print(f"  API returned {len(data)} venues")
            for v in data[:5]:
                print(f"    {v.get('tenant_name','?')} — {v.get('address','?')}")
        elif isinstance(data, dict):
            print(f"  API dict keys: {list(data.keys())[:5]}")
        break
    except json.JSONDecodeError:
        pass

    # HTML: look for venue names/links
    venue_links = re.findall(r'href="(/(?:de-at/)?[a-z0-9-]+/padel[^"]*)"', html)
    venue_names = re.findall(r'(?:class="[^"]*(?:name|title)[^"]*"|data-name)="([^"]+)"', html)
    print(f"  {url[:60]}: {len(html)} chars, {len(venue_links)} venue links found")
    if venue_links:
        for vl in venue_links[:10]:
            print(f"    {vl}")

print()
print("Done.")
