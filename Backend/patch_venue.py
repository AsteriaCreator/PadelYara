"""
patch_venue.py — update a venue with data from the Claude browser extension

Usage:
    python patch_venue.py <eversports_slug>

Then paste the JSON when prompted. Fields supported:
    eversports_facility_id, eversports_court_ids, court_type,
    name, operator, notes, priority, public_url

If active is currently false, the script will flip it to true after patching.
"""

import json
import sys
import requests
from dotenv import load_dotenv
load_dotenv()
import os
from pymongo import MongoClient

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")


def geocode(address: str) -> dict:
    r = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": address, "key": GOOGLE_API_KEY},
        timeout=10,
    )
    results = r.json().get("results", [])
    if not results:
        return {}
    loc = results[0]["geometry"]["location"]
    region_key, region_label = "", ""
    for comp in results[0].get("address_components", []):
        if "administrative_area_level_1" in comp["types"]:
            region_label = comp["long_name"]
            region_key   = region_label.lower().replace(" ", "_").replace("ä","ae").replace("ö","oe").replace("ü","ue")
    return {"lat": loc["lat"], "lon": loc["lng"],
            "region_key": region_key, "region_label": region_label}

PATCHABLE_FIELDS = [
    "eversports_facility_id",
    "eversports_court_ids",
    "etennis_id",
    "platform_id",
    "courts",
    "court_type",
    "name",
    "operator",
    "address",
    "notes",
    "priority",
    "public_url",
]

VALID_COURT_TYPES = {"indoor_normal", "indoor_single", "outdoor_normal", "outdoor_single"}

def find_venue(col, query: str):
    """Find a venue by slug, etennis_id, booking_url fragment, or name fragment."""
    return (
        col.find_one({"eversports_slug": query})
        or col.find_one({"etennis_id": query})
        or col.find_one({"booking_url": {"$regex": query, "$options": "i"}})
        or col.find_one({"name": {"$regex": query, "$options": "i"}})
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python patch_venue.py <identifier>")
        print("  identifier can be: eversports slug, etennis_id, booking_url fragment, or name fragment")
        print("  examples:")
        print("    python patch_venue.py padelzone-voesendorf")
        print("    python patch_venue.py 2837")
        print("    python patch_venue.py tennisplatz")
        print("    python patch_venue.py Voesendorf")
        sys.exit(1)

    query = sys.argv[1].strip()
    col   = MongoClient(os.getenv("MONGODB_URI"))["padel_checker"]["venues"]

    doc = find_venue(col, query)
    if not doc:
        print(f"Venue not found: {query}")
        sys.exit(1)

    print(f"\nVenue found: {doc.get('name') or '(no name)'}")
    print(f"  slug:    {doc.get('eversports_slug')}")
    print(f"  active:  {doc.get('active')}")
    print(f"  platform:    {doc.get('platform')}")
    print(f"  etennis_id:  {doc.get('etennis_id')}")
    print(f"  facility_id: {doc.get('eversports_facility_id')}")
    print(f"  court_ids:   {doc.get('eversports_court_ids')}")
    print(f"  courts:      {doc.get('courts')}")
    print()
    print("Paste the JSON from Claude browser extension (then press Enter twice):")

    lines = []
    while True:
        line = input()
        if line == "" and lines:
            break
        lines.append(line)

    raw = "\n".join(lines).strip()

    # strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])

    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        sys.exit(1)

    # build update
    patch = {}
    for field in PATCHABLE_FIELDS:
        if field in data:
            val = data[field]

            if field == "eversports_court_ids":
                # normalise to list of strings
                val = [str(v) for v in val]

            elif field == "etennis_id":
                # also sync platform_id
                patch["platform_id"] = str(val)
                val = str(val)

            elif field == "courts":
                # validate and normalise each court object
                normalised = []
                for court in val:
                    cid   = str(court.get("id", ""))
                    ctype = court.get("type", "")
                    if ctype not in VALID_COURT_TYPES:
                        print(f"  [warn] unknown court type '{ctype}' for id {cid} — skipping")
                        continue
                    normalised.append({"id": cid, "type": ctype})
                val = normalised
                # also auto-fill eversports_court_ids from courts if not separately provided
                if "eversports_court_ids" not in data:
                    patch["eversports_court_ids"] = [c["id"] for c in normalised]

            patch[field] = val

    if not patch:
        print("No recognised fields in JSON — nothing to update.")
        sys.exit(1)

    # auto-geocode if address provided and coordinates missing
    if "address" in patch and not doc.get("lat"):
        print(f"  Geocoding: {patch['address']} ...")
        geo = geocode(patch["address"])
        if geo:
            patch.update(geo)
            print(f"  lat={geo['lat']}  lon={geo['lon']}  region={geo['region_label']}")

    print(f"\nWill patch: {list(patch.keys())}")

    # flip active if currently false
    was_inactive = not doc.get("active", True)
    if was_inactive:
        patch["active"] = True
        print("Will also flip active -> true")

    confirm = input("\nApply? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    col.update_one({"_id": doc["_id"]}, {"$set": patch})
    print(f"\nDone. {doc.get('name') or slug} updated.")
    if was_inactive:
        print("Venue is now active.")

if __name__ == "__main__":
    main()
