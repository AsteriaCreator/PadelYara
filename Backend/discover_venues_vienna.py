"""
discover_venues_vienna.py — padel venue discovery for Vienna

Searches Google Places for padel venues, detects their booking platform,
and inserts each new venue into MongoDB as active: false for review.

Usage:
    python discover_venues_vienna.py

Safe to re-run — skips venues already in the DB.
"""

import re
import uuid
import time
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import load_dotenv
import os
from pymongo import MongoClient

# reuse all the logic we already built in add_venue.py
from add_venue import (
    fetch_eversports_data,
    extract_eversports_slug,
    extract_etennis_id,
    geocode_address,
    reverse_geocode_region,
    find_venue_location,
    get_collection,
    already_exists,
)

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# ── search queries ────────────────────────────────────────────────────
# Multiple queries to catch venues with different naming conventions.
# Results are deduplicated by Google Place ID.

SEARCH_QUERIES = [
    "padel Wien",
    "padel court Wien",
    "Padelzone Wien",
    "Padeldome Wien",
    "padel tennis Wien",
    "padel club Wien",
]

# Vienna bounding box — keeps results focused on the city
LOCATION_BIAS = "circle:30000@48.2082,16.3738"  # 30 km radius around Vienna centre

# ── hardcoded venues ──────────────────────────────────────────────────
# Venues whose booking platform can't be detected automatically
# (e.g. JS-rendered sites). Add new ones here as you discover them.
#
# Format: (name, booking_url, address)
HARDCODED_VENUES = [
    # Padeldome — eTennis via padeldome.wien, site is JS-rendered
    ("Padeldome Erdberg",           "https://www.padeldome.wien/reservierung?c=2665", "Franzosengraben 2, 1030 Wien"),
    ("Padeldome Süßenbrunn",        "https://www.padeldome.wien/reservierung?c=2667", "Weingartenallee 22, 1220 Wien"),
    # Alt Erlaa already in DB — kept here for reference, idempotency check will skip it
    ("Padeldome Alt Erlaa",         "https://www.padeldome.wien/reservierung?c=2668", "Anton-Baumgartner-Straße 40, 1230 Wien"),
    ("Padeldome Alte Donau indoor", "https://www.padeldome.wien/reservierung?c=3216", "Arbeiterstrandbadstraße 87A, 1210 Wien"),
    ("Padeldome Alte Donau outdoor","https://www.padeldome.wien/reservierung?c=3218", "Arbeiterstrandbadstraße 87A, 1210 Wien"),
]


# ── Google Places search ──────────────────────────────────────────────

def search_places(query: str) -> list[dict]:
    """
    New Places API text search.
    Returns a list of raw place dicts with name, address, location, website, place_id.
    """
    try:
        r = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            json={
                "textQuery":    query,
                "locationBias": {
                    "circle": {
                        "center": {"latitude": 48.2082, "longitude": 16.3738},
                        "radius": 30000.0,
                    }
                },
            },
            headers={
                "X-Goog-Api-Key":   GOOGLE_API_KEY,
                "X-Goog-FieldMask": (
                    "places.id,"
                    "places.displayName,"
                    "places.formattedAddress,"
                    "places.location,"
                    "places.websiteUri,"
                    "places.nationalPhoneNumber"
                ),
            },
            timeout=10,
        )
        return r.json().get("places", [])
    except Exception as e:
        print(f"  [warn] Places search failed for '{query}': {e}")
        return []


# ── platform detection from website ──────────────────────────────────

def _fetch_html(url: str) -> str:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""


def _find_platform_in_html(html: str) -> tuple[str, str]:
    """Scans HTML for Eversports or eTennis booking links."""
    # Eversports
    ev = re.search(r'eversports\.at/sb/([\w-]+)', html)
    if ev:
        slug = ev.group(1)
        return "eversports", f"https://www.eversports.at/sb/{slug}"

    # eTennis — any URL containing ?c=NNNN (works for custom domains like reservierung.padel4fun.at)
    et = re.search(r'https?://[^\s"\'<>]+\?[^\s"\'<>]*\bc=(\d+)', html)
    if et:
        booking_url = et.group(0).rstrip("'\"")
        # verify it actually leads to an eTennis page
        booking_html = _fetch_html(booking_url)
        if "etennis" in booking_html.lower() or "slot" in booking_html.lower():
            return "etennis", booking_url

    return "unknown", ""


def _padelzone_subpage(venue_name: str) -> str:
    """
    Derives the padelzone.at subpage path from the Google Places venue name.
    e.g. "PADELZONE Wien | C&C Wienerberg" -> "/wienerberg"
         "Padelzone Wien Colony Club"       -> "/colony-club"
         "PADELZONE Klosterneuburg | Happyland" -> "/klosterneuburg"
    """
    # take the part after | or after "Wien" / "PADELZONE"
    name = venue_name.lower()
    name = re.sub(r'padelzone\s*', '', name)
    name = re.sub(r'wien\s*', '', name)
    name = re.sub(r'[|&+]', ' ', name)
    # grab the first meaningful word(s)
    words = [w for w in re.split(r'\s+', name.strip()) if len(w) > 2]
    if not words:
        return ""
    slug = words[0].rstrip('.')
    return f"/{slug}"


def detect_platform_from_website(website_url: str, venue_name: str = "") -> tuple[str, str]:
    """
    Fetches the venue's website and looks for booking platform links.
    Returns (platform, booking_url).
    """
    if not website_url:
        return "unknown", ""

    # direct Eversports URL
    if "eversports" in website_url:
        slug = extract_eversports_slug(website_url)
        if slug:
            return "eversports", f"https://www.eversports.at/sb/{slug}"

    # direct eTennis URL
    if re.search(r"etennis", website_url, re.I):
        eid = extract_etennis_id(website_url)
        if eid:
            return "etennis", website_url

    parsed = urlparse(website_url)
    domain = parsed.netloc.replace("www.", "")

    # ── padelzone.at: try subpage derived from venue name ────────────────
    if "padelzone.at" in domain:
        subpage = _padelzone_subpage(venue_name) if venue_name else ""
        # if the URL already has a subpath, use that; otherwise derive from name
        path = parsed.path.rstrip("/") or subpage
        if path and path != "/":
            subpage_url = f"https://www.padelzone.at{path}"
            html = _fetch_html(subpage_url)
            platform, booking_url = _find_platform_in_html(html)
            if platform != "unknown":
                return platform, booking_url

    # ── padeldome.at: check padeldome.wien (their booking domain) ────────
    if "padeldome.at" in domain or "padeldome.wien" in domain:
        # extract location slug from URL path e.g. /alterlaa -> alterlaa
        path_parts = [p for p in parsed.path.split("/") if p]
        location = path_parts[-1] if path_parts else ""
        # try padeldome.wien with the location path
        for check_url in [
            f"https://www.padeldome.wien/standort/{location}" if location else None,
            "https://www.padeldome.wien/reservierung",
            "https://www.padeldome.wien",
        ]:
            if not check_url:
                continue
            html = _fetch_html(check_url)
            platform, booking_url = _find_platform_in_html(html)
            if platform != "unknown":
                return platform, booking_url

    # ── generic: fetch the page and scan for booking links ───────────────
    html = _fetch_html(website_url)
    platform, booking_url = _find_platform_in_html(html)
    if platform != "unknown":
        return platform, booking_url

    return "unknown", ""


# ── build venue doc ───────────────────────────────────────────────────

def build_venue(place: dict, platform: str, booking_url: str) -> dict:
    """Assembles a venue document from a Places result + platform info."""
    loc  = place.get("location", {})
    name = place.get("displayName", {}).get("text", "")

    venue = {
        "id":                     str(uuid.uuid4())[:8],
        "active":                 False,
        "name":                   name,
        "address":                place.get("formattedAddress", ""),
        "lat":                    loc.get("latitude"),
        "lon":                    loc.get("longitude"),
        "region_key":             "",
        "region_label":           "",
        "court_type":             "",
        "operator":               "",
        "platform":               platform,
        "booking_url":            booking_url,
        "public_url":             place.get("websiteUri", booking_url),
        "priority":               0,
        "maps_id":                place.get("id"),
        "platform_id":            None,
        "etennis_id":             None,
        "eversports_slug":        None,
        "eversports_facility_id": None,
        "eversports_court_ids":   [],
        "notes":                  "",
        "issues":                 None,
        "slot_fallback_minutes":  [],
    }

    # platform-specific fields
    if platform == "eversports":
        slug = extract_eversports_slug(booking_url)
        if slug:
            ev = fetch_eversports_data(slug)
            venue.update(ev)
            # prefer the name from Places (more accurate) over Eversports page title
            if name:
                venue["name"] = name

    elif platform == "etennis":
        eid = extract_etennis_id(booking_url)
        venue["etennis_id"]  = eid
        venue["platform_id"] = eid

    # reverse-geocode region from coordinates
    if venue["lat"] and venue["lon"]:
        region = reverse_geocode_region(venue["lat"], venue["lon"])
        venue.update(region)

    return venue


# ── main ──────────────────────────────────────────────────────────────

def main():
    print("PadelYara — Vienna venue discovery")
    print("=" * 40)

    col = get_collection()

    # collect all Place IDs we've seen to deduplicate across queries
    seen_place_ids: set[str] = set()
    all_places: list[dict] = []

    print(f"\nSearching Google Places ({len(SEARCH_QUERIES)} queries)...")
    for query in SEARCH_QUERIES:
        results = search_places(query)
        print(f"  '{query}' -> {len(results)} results")
        for p in results:
            pid = p.get("id", "")
            if pid and pid not in seen_place_ids:
                seen_place_ids.add(pid)
                all_places.append(p)
        time.sleep(0.3)  # be polite to the API

    print(f"\nUnique venues found: {len(all_places)}")
    print("=" * 40)

    inserted   = 0
    skipped_db = 0
    skipped_no_platform = 0

    for i, place in enumerate(all_places, 1):
        name    = place.get("displayName", {}).get("text", "?")
        website = place.get("websiteUri", "")
        address = place.get("formattedAddress", "")

        print(f"\n[{i}/{len(all_places)}] {name}")
        print(f"  Address: {address}")
        print(f"  Website: {website}")

        # detect platform from website
        platform, booking_url = detect_platform_from_website(website, venue_name=name)
        print(f"  Platform: {platform}  |  Booking URL: {booking_url or '—'}")

        if platform == "unknown":
            print("  -> Skipping (no booking platform found)")
            skipped_no_platform += 1
            continue

        # check if already in DB
        if already_exists(col, booking_url, name):
            print("  -> Already in DB, skipping")
            skipped_db += 1
            continue

        # build and insert
        venue = build_venue(place, platform, booking_url)
        col.insert_one(venue)
        print(f"  -> Inserted as active=false  (id: {venue['id']}, facility_id: {venue.get('eversports_facility_id')})")
        inserted += 1

        time.sleep(0.5)  # avoid hammering Eversports

    # ── process hardcoded venues ─────────────────────────────────────────
    print(f"\nProcessing {len(HARDCODED_VENUES)} hardcoded venues...")
    print("=" * 40)

    for name, booking_url, address in HARDCODED_VENUES:
        print(f"\n[hardcoded] {name}")

        if already_exists(col, booking_url, name):
            print("  -> Already in DB, skipping")
            skipped_db += 1
            continue

        platform = "etennis"
        eid = extract_etennis_id(booking_url)

        # geocode the address
        geo = geocode_address(address)
        region = reverse_geocode_region(geo["lat"], geo["lon"]) if geo.get("lat") else {}

        venue = {
            "id":                     str(uuid.uuid4())[:8],
            "active":                 False,
            "name":                   name,
            "address":                geo.get("address", address),
            "lat":                    geo.get("lat"),
            "lon":                    geo.get("lon"),
            "region_key":             region.get("region_key", "wien"),
            "region_label":           region.get("region_label", "Wien"),
            "court_type":             "",
            "operator":               "Padeldome",
            "platform":               platform,
            "booking_url":            booking_url,
            "public_url":             "https://www.padeldome.wien",
            "priority":               0,
            "maps_id":                None,
            "platform_id":            eid,
            "etennis_id":             eid,
            "eversports_slug":        None,
            "eversports_facility_id": None,
            "eversports_court_ids":   [],
            "notes":                  "",
            "issues":                 None,
            "slot_fallback_minutes":  [],
        }

        col.insert_one(venue)
        print(f"  -> Inserted as active=false  (id: {venue['id']}, etennis_id: {eid})")
        inserted += 1

    print("\n" + "=" * 40)
    print(f"Done.")
    print(f"  Inserted:              {inserted}")
    print(f"  Already in DB:         {skipped_db}")
    print(f"  No platform detected:  {skipped_no_platform}")
    print(f"\nGo to MongoDB Atlas, review the new docs, and flip active: true for each one you want live.")


if __name__ == "__main__":
    main()
