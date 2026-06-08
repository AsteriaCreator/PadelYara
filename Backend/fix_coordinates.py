"""
Fix wrong venue coordinates identified by the coordinate audit.
Uses name-based matching since some venues lack an 'id' field.
Skips GWR Padel (Nominatim gave wrong result for that street name).
Smash Mitterndorf has no street address — needs manual lookup.
"""
import os, sys, math
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")

from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("Backend/.env")
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["padel_checker"]

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# Confirmed fixes: (venue_name, new_lat, new_lon, reason)
# Source: Nominatim geocode of the stored address field.
# Skipped:
#   GWR Padel GmbH — Nominatim matched "Waidhofner Str." to Sonntagberg instead of Amstetten;
#                    stored coords (48.1224, 14.8726) are consistent with Amstetten center.
#   Smash Mitterndorf — address is just "Mitterndorf an der Fischa, Niederösterreich" with no
#                       street number; need proper address before fixing.
FIXES = [
    # Large errors (clearly Google Places returned the wrong thing by name)
    ("Union Tennisclub Biberbach",          48.0309694, 14.7116337, "Nom: Waldesblick, Biberbach"),
    ("Smashhouse Lanzenkirchen",            47.758222,  16.2450444, "Nom: Gewerbepark, Lanzenkirchen"),
    ("PADELFIELD Weer (Tirol)",             47.3089375, 11.6580127, "Nom: Rinderweg, Weer"),

    # Moderately wrong (6–8 km)
    ("TC Dürnkrut",                         48.4696536, 16.8550088, "Nom: Hauptstraße, Dürnkrut"),
    ("UTPC Göstling",                       47.8120651, 14.9590574, "Nom: Steinbachmauer, Göstling"),
    ("Monte Haidhof Padel Club",            48.0990848, 14.8727599, "Nom: Haidhofstraße, Winklarn"),
    ("UTC Tullnerbach",                     48.1911156, 16.0905204, "Nom: Lawieserstraße, Tullnerbach"),
    ("PLAYPADEL Gänserndorf",               48.3550513, 16.7340525, "Nom: Industriestraße, Gänserndorf"),
    ("UTPC Göstling",                       47.8120651, 14.9590574, "Nom: Steinbachmauer, Göstling"),
    ("Padel Waldenstein",                   48.72943,   15.0171339, "Nom: Waldenstein village"),

    # Borderline (5–6 km)
    ("Smash Mitterndorf",                   47.9974719, 16.4703767, "Nom: Mitterndorf an der Fischa village"),
    ("Tennishotel Khail",                   48.0944205, 16.4205702, "Nom: Himberger Straße, Maria Lanzendorf"),
    ("PADELZONE Graz | Racket Sport Center Graz",  47.0787943, 15.4721119, "Nom: Ragnitzstraße, Graz"),
    ("Padel Tulln",                         48.3314947, 16.0704113, "Nom: Donaulände, Tulln (stored lon=16.0 was clearly truncated)"),
    ("Tennisverein Enzersfeld",             48.3472688, 16.4107428, "Nom: In den Nussern, Königsbrunn"),
]

# Deduplicate (UTPC Göstling appeared twice)
seen = set()
deduped = []
for f in FIXES:
    if f[0] not in seen:
        seen.add(f[0])
        deduped.append(f)
FIXES = deduped

fixed = 0
not_found = []

for name, new_lat, new_lon, reason in FIXES:
    doc = db.venues.find_one({"name": name})
    if not doc:
        not_found.append(name)
        print(f"  ✗ NOT FOUND: {name}")
        continue

    old_lat = doc.get("lat")
    old_lon = doc.get("lon")
    dist = haversine_km(old_lat, old_lon, new_lat, new_lon)

    result = db.venues.update_one(
        {"_id": doc["_id"]},
        {"$set": {"lat": new_lat, "lon": new_lon,
                  "maps_id": f"https://www.google.com/maps?q={new_lat},{new_lon}"}}
    )
    if result.modified_count:
        print(f"  ✓  {name}: {old_lat},{old_lon} → {new_lat},{new_lon}  [{dist:.1f} km shift]  ({reason})")
        fixed += 1
    else:
        print(f"  ~ unchanged: {name}")

print(f"\nFixed {fixed}/{len(FIXES)} venues.")
if not_found:
    print(f"Not found in DB: {not_found}")
