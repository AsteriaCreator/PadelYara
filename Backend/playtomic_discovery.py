import os, sys, json
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding='utf-8')

import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("Backend/.env")
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["padel_checker"]
venues_col = db["venues"]

existing_names = {v.get("name","").lower() for v in venues_col.find({}, {"name": 1})}
existing_booking_urls = {v.get("booking_url","") for v in venues_col.find({}, {"booking_url": 1})}

# Austria center coords + large radius to catch all venues
# Use coordinate-based search instead of address string
r = requests.get(
    "https://api.playtomic.io/v1/tenants",
    params={
        "sport_id": "PADEL",
        "coordinate": "47.5,13.5",   # center of Austria
        "radius": 400000,             # 400km covers all of Austria
        "page": 0,
        "page_size": 100,
    },
    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    timeout=20
)
print(f"Status: {r.status_code}, Content-Length: {len(r.text)}")
data = r.json()
print(f"Total returned: {len(data)}")

# Filter to Austria only
at_venues = [v for v in data if v.get("address", {}).get("country_code") in ("AT", "AUT", "A")]
if not at_venues:
    # Try different country field names
    at_venues = [v for v in data if "Austria" in str(v.get("address", {}))]

print(f"Austria venues: {len(at_venues)}\n")

new_venues = []
for v in at_venues:
    name = v.get("tenant_name", "?")
    addr = v.get("address", {})
    city = addr.get("city", "?")
    street = addr.get("street", "")
    country = addr.get("country_code", addr.get("country", "?"))
    tenant_id = v.get("tenant_id", "")
    playtomic_url = f"https://playtomic.com/venue/{tenant_id}" if tenant_id else ""
    in_db = name.lower() in existing_names or playtomic_url in existing_booking_urls

    status = "in DB" if in_db else "NEW"
    print(f"[{status}]  {name}  |  {street}, {city}  |  {country}")
    if not in_db:
        new_venues.append({"name": name, "city": city, "street": street, "url": playtomic_url, "id": tenant_id})

print(f"\n==> {len(new_venues)} new Playtomic venues not in our DB")
print(json.dumps(new_venues, ensure_ascii=False, indent=2))
