"""
add_venue.py — single-venue onboarding script
Usage: python add_venue.py <url>

Paste any URL (venue website, Eversports page, eTennis booking URL).
The script detects the platform, fetches all fields it can, and inserts
the venue into MongoDB as active: false for your review.
"""

import re
import sys
import uuid
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from curl_cffi.requests import Session as CurlSession

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
MONGODB_URI    = os.getenv("MONGODB_URI")


# ── platform detection ────────────────────────────────────────────────

def detect_platform(url: str, html: str) -> str:
    if "eversports" in url:
        return "eversports"
    if re.search(r"etennis", url, re.I) or re.search(r"etennis", html, re.I):
        return "etennis"
    if "eversports" in html:
        return "eversports"
    return "unknown"


# ── eTennis ───────────────────────────────────────────────────────────

def extract_etennis_id(url: str, html: str = "") -> str | None:
    # first try ?c= in the URL
    qs = parse_qs(urlparse(url).query)
    cid = qs.get("c", [None])[0]
    if cid:
        return cid
    # fall back to data-cid on the .calendar element in the page HTML
    if html:
        m = re.search(r'class=["\'][^"\']*calendar[^"\']*["\'][^>]*data-cid=["\'](\d+)["\']', html)
        if not m:
            m = re.search(r'data-cid=["\'](\d+)["\']', html)
        if m:
            return m.group(1)
    return None


# ── Eversports ────────────────────────────────────────────────────────

def extract_eversports_slug(url: str) -> str | None:
    # /sb/some-slug  or  /s/some-slug
    m = re.search(r"/sb/([a-z0-9_-]+)", url) or re.search(r"/s/([a-z0-9_-]+)", url)
    return m.group(1) if m else None


def fetch_eversports_data(slug: str) -> dict:
    """
    Fetches facility_id, court_ids, and venue name from the Eversports booking page.
    Uses curl_cffi with Chrome TLS fingerprinting to bypass Cloudflare,
    the same technique used by eversports_service.py.
    """
    result = {
        "eversports_slug":        slug,
        "eversports_facility_id": None,
        "eversports_court_ids":   [],
        "name":                   "",
    }
    url = f"https://www.eversports.at/sb/{slug}"

    try:
        with CurlSession(impersonate="chrome124") as session:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                print(f"  [warn] Eversports page returned {resp.status_code}")
                return result
            html = resp.text
    except Exception as e:
        print(f"  [warn] Could not fetch Eversports page: {e}")
        return result

    # extract venue name from <title> tag — typically "Venue Name | Eversports"
    m = re.search(r"<title>([^<]+)</title>", html, re.I)
    if m:
        title = m.group(1).strip()
        # strip the " | Eversports" suffix
        name = re.split(r"\s*[|\-–]\s*[Ee]versports", title)[0].strip()
        if name:
            result["name"] = name

    # facility_id is in a data-id attribute on the booking widget
    for pattern in [
        r'data-id=[\'"](\d+)[\'"]',
        r'"facilityId"\s*:\s*(\d+)',
        r'facility[_-]?id["\s:=]+(\d+)',
    ]:
        m = re.search(pattern, html, re.I)
        if m:
            result["eversports_facility_id"] = int(m.group(1))
            break

    # court IDs — try static HTML first, then calendar POST
    for pattern in [r'"courtId"\s*:\s*(\d+)', r'data-court=[\'"](\d+)[\'"]']:
        matches = re.findall(pattern, html)
        if matches:
            result["eversports_court_ids"] = list(dict.fromkeys(matches))
            break

    # if still empty, fetch via calendar endpoint (needs facility_id)
    if not result["eversports_court_ids"] and result["eversports_facility_id"]:
        court_ids = _fetch_court_ids_via_calendar(
            slug        = slug,
            facility_id = result["eversports_facility_id"],
            page_html   = html,
        )
        result["eversports_court_ids"] = court_ids

    return result


def _fetch_court_ids_via_calendar(slug: str, facility_id: int, page_html: str) -> list:
    """
    POSTs to /api/booking/calendar/update (same as eversports_service.py)
    and extracts unique court IDs from the data-court attributes in the response.
    """
    from datetime import date as _date
    today = _date.today().strftime("%d/%m/%Y")  # Eversports datepicker format
    venue_url = f"https://www.eversports.at/sb/{slug}"

    # extract CSRF token from the page HTML we already have
    csrf_token = ""
    m = re.search(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)', page_html)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']csrf-token', page_html)
    if m:
        csrf_token = m.group(1)

    try:
        with CurlSession(impersonate="chrome124") as session:
            # re-GET the page to get fresh cookies
            get_resp = session.get(
                venue_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
                    "Referer": "https://www.eversports.at/",
                },
                timeout=20,
            )
            if get_resp.status_code != 200:
                return []

            # refresh CSRF from this response if we didn't have it
            if not csrf_token:
                m = re.search(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)', get_resp.text)
                if m:
                    csrf_token = m.group(1)

            post_headers = {
                "Content-Type":     "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Accept":           "*/*",
                "Accept-Language":  "de-AT,de;q=0.9,en;q=0.8",
                "Referer":          venue_url,
                "Origin":           "https://www.eversports.at",
            }
            if csrf_token:
                post_headers["X-CSRF-TOKEN"] = csrf_token

            post_resp = session.post(
                "https://www.eversports.at/api/booking/calendar/update",
                data={"date": today, "facilityId": str(facility_id), "facility": slug},
                headers=post_headers,
                timeout=20,
            )
            if post_resp.status_code != 200:
                print(f"  [warn] Calendar POST returned {post_resp.status_code}")
                return []

            court_ids = re.findall(r'data-court=[\'"](\d+)[\'"]', post_resp.text)
            return list(dict.fromkeys(court_ids))  # deduplicated, order preserved

    except Exception as e:
        print(f"  [warn] Could not fetch court IDs via calendar: {e}")
        return []


# ── geocoding ─────────────────────────────────────────────────────────

def geocode_address(address: str) -> dict:
    """Returns lat, lon, formatted_address."""
    r = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": address, "key": GOOGLE_API_KEY},
        timeout=10,
    )
    results = r.json().get("results", [])
    if not results:
        return {}
    loc = results[0]["geometry"]["location"]
    return {
        "lat": loc["lat"],
        "lon": loc["lng"],
        "address": results[0]["formatted_address"],
    }


def reverse_geocode_region(lat: float, lon: float) -> dict:
    """Returns region_key and region_label from coordinates."""
    r = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"latlng": f"{lat},{lon}", "key": GOOGLE_API_KEY},
        timeout=10,
    )
    for result in r.json().get("results", []):
        for component in result["address_components"]:
            if "administrative_area_level_1" in component["types"]:
                label = component["long_name"]
                key   = label.lower().replace(" ", "_").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
                return {"region_key": key, "region_label": label}
    return {}


# ── venue name + address from Google Places ───────────────────────────

def lookup_place(query: str) -> dict:
    """
    Text search using the new Places API (v1).
    Returns name, address, lat, lon.
    """
    try:
        r = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            json={
                "textQuery": query,
                # Restrict results to Austria so we never pull a geographically
                # wrong match from another country or a same-named place abroad.
                "locationRestriction": {
                    "rectangle": {
                        "low":  {"latitude": 46.37, "longitude": 9.53},
                        "high": {"latitude": 49.02, "longitude": 17.17},
                    }
                },
            },
            headers={
                "X-Goog-Api-Key": GOOGLE_API_KEY,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
            },
            timeout=10,
        )
        places = r.json().get("places", [])
        if not places:
            return {}
        p   = places[0]
        loc = p.get("location", {})
        return {
            "name":    p.get("displayName", {}).get("text", ""),
            "address": p.get("formattedAddress", ""),
            "lat":     loc.get("latitude"),
            "lon":     loc.get("longitude"),
        }
    except Exception as e:
        print(f"  [warn] Places API error: {e}")
        return {}


def find_venue_location(name: str, slug: str, platform: str, url: str) -> dict:
    """
    Tries multiple queries to find the venue on Google Places.
    Falls back gracefully so we always get something.
    """
    queries = []

    if name:
        queries.append(name)                      # "Smash Trumau"
        queries.append(f"{name} Austria")         # "Smash Trumau Austria"

    if slug:
        readable = slug.replace("-", " ").title()
        queries.append(f"{readable} Austria")     # "Smash Trumau Austria" from slug

    for query in queries:
        result = lookup_place(query)
        if result.get("name"):
            print(f"  Found via query: '{query}'")
            return result

    return {}


# ── MongoDB ───────────────────────────────────────────────────────────

def get_collection():
    client = MongoClient(MONGODB_URI)
    return client["padel_checker"]["venues"]


def already_exists(col, booking_url: str, name: str) -> bool:
    if col.find_one({"booking_url": booking_url}):
        return True
    if name and col.find_one({"name": name}):
        return True
    return False


# ── main ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python add_venue.py <url>")
        sys.exit(1)

    url = sys.argv[1].strip()
    print(f"\nProcessing: {url}")

    # fetch the page so we can inspect content
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        html = resp.text
    except Exception as e:
        print(f"Could not fetch URL: {e}")
        html = ""

    platform = detect_platform(url, html)
    print(f"Platform detected: {platform}")

    venue = {
        "id":                     str(uuid.uuid4())[:8],
        "active":                 False,
        "platform":               platform,
        "booking_url":            url,
        "public_url":             url,
        "name":                   "",
        "address":                "",
        "lat":                    None,
        "lon":                    None,
        "region_key":             "",
        "region_label":           "",
        "court_type":             "",
        "operator":               "",
        "priority":               0,
        "maps_id":                None,
        "platform_id":            None,
        "etennis_id":             None,
        "eversports_slug":        None,
        "eversports_facility_id": None,
        "eversports_court_ids":   [],
        "notes":                  "",
        "issues":                 None,
        "slot_fallback_minutes":  [],
    }

    # platform-specific extraction
    if platform == "etennis":
        venue["etennis_id"] = extract_etennis_id(url, html)
        venue["platform_id"] = venue["etennis_id"]
        print(f"  eTennis ID: {venue['etennis_id']}")

    elif platform == "eversports":
        slug = extract_eversports_slug(url)
        if slug:
            print(f"  Eversports slug: {slug}")
            ev = fetch_eversports_data(slug)
            venue.update(ev)
            print(f"  Name from page: {venue['name']}")
            print(f"  Facility ID: {venue['eversports_facility_id']}")
            print(f"  Court IDs: {venue['eversports_court_ids']}")

    # look up name + location from Google Places
    place = find_venue_location(
        name     = venue.get("name", ""),
        slug     = venue.get("eversports_slug", ""),
        platform = platform,
        url      = url,
    )
    if place:
        # only overwrite name if we don't already have one from the page
        if not venue["name"] and place.get("name"):
            venue["name"] = place["name"]
        for k in ("address", "lat", "lon"):
            if place.get(k):
                venue[k] = place[k]
        print(f"  Name: {venue['name']}")
        print(f"  Address: {venue['address']}")

    # geocode if we have an address but no coordinates
    if venue["address"] and venue["lat"] is None:
        geo = geocode_address(venue["address"])
        venue.update({k: v for k, v in geo.items() if v})

    # reverse-geocode region
    if venue["lat"] and venue["lon"]:
        region = reverse_geocode_region(venue["lat"], venue["lon"])
        venue.update(region)
        print(f"  Region: {venue['region_label']} ({venue['region_key']})")

    # insert into MongoDB
    col = get_collection()
    if already_exists(col, url, venue["name"]):
        print("\nVenue already exists in DB — skipping insert.")
        return

    col.insert_one(venue)
    venue_id = venue["id"]
    print(f"\nInserted as active=false  (id: {venue_id})")
    print("Go to MongoDB Atlas, verify the doc, then set active: true to go live.")


if __name__ == "__main__":
    main()
