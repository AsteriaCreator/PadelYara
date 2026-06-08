import os, sys
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("Backend/.env")
db = MongoClient(os.getenv("MONGODB_URI"))["padel_checker"]
venues = db["venues"]

docs = [
    # ── Tennishotel Khail (Maria Lanzendorf, near Vienna)
    # 8 indoor + 1 outdoor padel courts; facility_id=77294
    {
        "id": "tennishotel-khail",
        "active": True,
        "address": "Himberger Straße 15, 2326 Maria Lanzendorf",
        "booking_url": "https://www.eversports.at/sb/tennishotel-khail",
        "court_type": "indoor_outdoor",
        "courts": [
            {"id": "89309", "type": "indoor_normal"},
            {"id": "89310", "type": "indoor_normal"},
            {"id": "89311", "type": "indoor_normal"},
            {"id": "89312", "type": "indoor_normal"},
            {"id": "89313", "type": "indoor_normal"},
            {"id": "89314", "type": "indoor_normal"},
            {"id": "89315", "type": "indoor_normal"},
            {"id": "89316", "type": "indoor_normal"},
            {"id": "89317", "type": "outdoor_normal"},
        ],
        "etennis_id": None,
        "eversports_court_ids": [89309,89310,89311,89312,89313,89314,89315,89316,89317],
        "eversports_facility_id": 77294,
        "eversports_slug": "tennishotel-khail",
        "issues": None,
        "lat": 48.0456,
        "lon": 16.4528,
        "maps_id": "https://www.google.com/maps?q=48.0456,16.4528",
        "name": "Tennishotel Khail",
        "notes": None,
        "operator": "Tennishotel Khail",
        "platform": "Eversports",
        "platform_id": "tennishotel-khail",
        "priority": 6,
        "public_url": "https://www.tennishotel-khail.at",
        "region_key": "niederoesterreich",
        "region_label": "Niederösterreich",
        "slot_fallback_minutes": [],
        "bezirk": None,
    },
    # ── KSV Wien (Prater, 1020 Wien)
    # 10 outdoor courts; facility_id=80214
    {
        "id": "ksv-wien",
        "active": True,
        "address": "Rustenschacherallee 3, 1020 Wien",
        "booking_url": "https://www.eversports.at/sb/kultur-und-sportvereinigung-der-wiener-gemeindebediensteten",
        "court_type": "outdoor",
        "courts": [
            {"id": "104418", "type": "outdoor_normal"},
            {"id": "104419", "type": "outdoor_normal"},
            {"id": "104420", "type": "outdoor_normal"},
            {"id": "104421", "type": "outdoor_normal"},
            {"id": "104422", "type": "outdoor_normal"},
            {"id": "104423", "type": "outdoor_normal"},
            {"id": "104424", "type": "outdoor_normal"},
            {"id": "104425", "type": "outdoor_normal"},
            {"id": "104426", "type": "outdoor_normal"},
            {"id": "104427", "type": "outdoor_normal"},
        ],
        "etennis_id": None,
        "eversports_court_ids": [104418,104419,104420,104421,104422,104423,104424,104425,104426,104427],
        "eversports_facility_id": 80214,
        "eversports_slug": "kultur-und-sportvereinigung-der-wiener-gemeindebediensteten",
        "issues": None,
        "lat": 48.2200,
        "lon": 16.4234,
        "maps_id": "https://www.google.com/maps?q=48.2200,16.4234",
        "name": "KSV Wien",
        "notes": "Multi-sport club (Prater), Padel + Tennis + Beach Volleyball",
        "operator": "KSV Wien",
        "platform": "Eversports",
        "platform_id": "kultur-und-sportvereinigung-der-wiener-gemeindebediensteten",
        "priority": 5,
        "public_url": "https://www.eversports.at/sb/kultur-und-sportvereinigung-der-wiener-gemeindebediensteten",
        "region_key": "wien",
        "region_label": "Wien",
        "slot_fallback_minutes": [],
        "bezirk": "2. Bezirk – Leopoldstadt",
    },
    # ── TAPEDESIGN Wundschuh (Steiermark, 3rd TAPEDESIGN location)
    # 1 outdoor court; facility_id=83307
    {
        "id": "tapedesign-wundschuh",
        "active": True,
        "address": "Gewerbepark 5, 8142 Wundschuh",
        "booking_url": "https://www.eversports.at/sb/tapedesign-sports-performance-center-wundschuh",
        "court_type": "outdoor",
        "courts": [
            {"id": "111574", "type": "outdoor_normal"},
        ],
        "etennis_id": None,
        "eversports_court_ids": [111574],
        "eversports_facility_id": 83307,
        "eversports_slug": "tapedesign-sports-performance-center-wundschuh",
        "issues": None,
        "lat": 46.9394,
        "lon": 15.4369,
        "maps_id": "https://www.google.com/maps?q=46.9394,15.4369",
        "name": "TAPEDESIGN Wundschuh",
        "notes": None,
        "operator": "TAPEDESIGN",
        "platform": "Eversports",
        "platform_id": "tapedesign-sports-performance-center-wundschuh",
        "priority": 6,
        "public_url": "https://www.tapedesign.at",
        "region_key": "steiermark",
        "region_label": "Steiermark",
        "slot_fallback_minutes": [],
        "bezirk": None,
    },
]

result = db.venues.insert_many(docs)
print(f"Inserted {len(result.inserted_ids)} venues:")
for doc, iid in zip(docs, result.inserted_ids):
    print(f"  {doc['name']} ({doc['id']}) -> {iid}")
print(f"\nTotal venues now: {db.venues.count_documents({})}")
