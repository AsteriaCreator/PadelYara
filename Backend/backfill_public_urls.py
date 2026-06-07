"""
backfill_public_urls.py

For every active phone-only venue that is missing both booking_url and public_url,
looks up the venue on Google Places and stores the websiteUri as public_url.

Safe to re-run — skips venues that already have a public_url or booking_url.
"""

import os, time
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
MONGODB_URI    = os.getenv("MONGODB_URI")

client = MongoClient(MONGODB_URI)
col    = client["padel_checker"]["venues"]


def places_lookup(name: str, lat: float, lon: float) -> str | None:
    """Query Google Places for the venue and return websiteUri if found."""
    try:
        r = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            json={
                "textQuery": name,
                "locationBias": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lon},
                        "radius": 2000.0,
                    }
                },
                "maxResultCount": 1,
            },
            headers={
                "X-Goog-Api-Key":   GOOGLE_API_KEY,
                "X-Goog-FieldMask": "places.displayName,places.websiteUri",
            },
            timeout=10,
        )
        places = r.json().get("places", [])
        if places:
            website = places[0].get("websiteUri", "")
            found_name = places[0].get("displayName", {}).get("text", "?")
            return website, found_name
    except Exception as e:
        print(f"  [warn] Places lookup failed: {e}")
    return None, None


def main():
    venues = list(col.find(
        {
            "active": True,
            "issues": "phone_booking_only",
            "public_url": {"$in": [None, ""]},
            "booking_url": {"$in": [None, ""]},
        },
        {"name": 1, "operator": 1, "address": 1, "lat": 1, "lon": 1}
    ))

    print(f"Found {len(venues)} venues to backfill\n")
    updated = 0
    not_found = 0

    for v in venues:
        name = v.get("name") or v.get("operator", "?")
        lat  = v.get("lat")
        lon  = v.get("lon")

        if not lat or not lon:
            print(f"  [{name}] — no coordinates, skipping")
            not_found += 1
            continue

        website, found_name = places_lookup(name, lat, lon)
        print(f"  {name}")
        print(f"    -> Places match: {found_name}")
        print(f"    -> Website: {website or '(none)'}")

        if website:
            col.update_one(
                {"_id": v["_id"]},
                {"$set": {"public_url": website}}
            )
            updated += 1
        else:
            not_found += 1

        time.sleep(0.2)

    print(f"\nDone. Updated: {updated}  |  No website found: {not_found}")


if __name__ == "__main__":
    main()
