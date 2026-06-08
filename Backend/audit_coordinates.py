"""
Audit venue coordinates by re-geocoding each venue's address via Nominatim
and flagging venues where the stored lat/lon is more than 5 km off.
"""
import os, sys, time, math
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")

import urllib.request, urllib.parse, json
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

def nominatim_geocode(address):
    """Geocode an address via Nominatim. Returns (lat, lon, display_name) or None."""
    q = urllib.parse.urlencode({"q": address, "format": "json", "limit": "1", "countrycodes": "at"})
    url = f"https://nominatim.openstreetmap.org/search?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "PadelYara-CoordAudit/1.0 mayer.conny@gmail.com"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]
    except Exception as e:
        print(f"    Nominatim error: {e}")
    return None

venues = list(db.venues.find(
    {"lat": {"$exists": True}, "lon": {"$exists": True}, "address": {"$exists": True}},
    {"id": 1, "name": 1, "lat": 1, "lon": 1, "address": 1}
))
print(f"Auditing {len(venues)} venues with lat/lon...\n")

THRESHOLD_KM = 5.0
suspicious = []
ok = []
no_result = []

for v in venues:
    stored_lat = v.get("lat")
    stored_lon = v.get("lon")
    address = v.get("address", "")
    name = v.get("name", v.get("id", "?"))
    vid = v.get("id", "?")

    if not address or stored_lat is None or stored_lon is None:
        no_result.append({"id": vid, "name": name, "reason": "missing address or coords"})
        continue

    result = nominatim_geocode(address)
    time.sleep(1.1)  # Nominatim rate limit: 1 req/sec

    if result is None:
        no_result.append({"id": vid, "name": name, "address": address, "reason": "Nominatim no result"})
        continue

    nom_lat, nom_lon, display = result
    dist = haversine_km(stored_lat, stored_lon, nom_lat, nom_lon)

    entry = {
        "id": vid,
        "name": name,
        "address": address,
        "stored": (stored_lat, stored_lon),
        "nominatim": (nom_lat, nom_lon),
        "dist_km": round(dist, 2),
        "nominatim_display": display,
    }

    if dist > THRESHOLD_KM:
        suspicious.append(entry)
        print(f"  ⚠  [{dist:.1f} km off]  {name}")
        print(f"      stored:    {stored_lat}, {stored_lon}")
        print(f"      nominatim: {nom_lat}, {nom_lon}")
        print(f"      address:   {address}")
        print(f"      Nominatim: {display[:80]}")
        print()
    else:
        ok.append(entry)
        print(f"  ✓  [{dist:.1f} km]  {name}")

print("\n" + "="*60)
print(f"SUMMARY:")
print(f"  OK (< {THRESHOLD_KM} km):    {len(ok)}")
print(f"  SUSPICIOUS (>= {THRESHOLD_KM} km): {len(suspicious)}")
print(f"  No Nominatim result:  {len(no_result)}")

if suspicious:
    print("\nSUSPICIOUS VENUES:")
    for s in sorted(suspicious, key=lambda x: -x["dist_km"]):
        print(f"  {s['dist_km']:6.1f} km  {s['name']}  ({s['id']})")
        print(f"           address:   {s['address']}")
        print(f"           stored:    {s['stored']}")
        print(f"           nominatim: {s['nominatim']}")

if no_result:
    print("\nNO NOMINATIM RESULT:")
    for n in no_result:
        print(f"  {n['name']}  ({n['id']})  — {n.get('address','')}")

# Save full results to JSON
out = {"ok": ok, "suspicious": suspicious, "no_result": no_result}
with open("Backend/coord_audit_results.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("\nFull results saved to Backend/coord_audit_results.json")
