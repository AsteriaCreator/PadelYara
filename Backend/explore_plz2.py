"""
Test PLZ → Bezirk extraction against actual venue addresses in the DB.
"""
import asyncio, os, re
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass
from motor.motor_asyncio import AsyncIOMotorClient
import pgeocode

nomi = pgeocode.Nominatim("AT")

WIEN_BEZIRKE = {
    1: "Innere Stadt", 2: "Leopoldstadt", 3: "Landstraße", 4: "Wieden",
    5: "Margareten", 6: "Mariahilf", 7: "Neubau", 8: "Josefstadt",
    9: "Alsergrund", 10: "Favoriten", 11: "Simmering", 12: "Meidling",
    13: "Hietzing", 14: "Penzing", 15: "Rudolfsheim-Fünfhaus",
    16: "Ottakring", 17: "Hernals", 18: "Währing", 19: "Döbling",
    20: "Brigittenau", 21: "Floridsdorf", 22: "Donaustadt", 23: "Liesing",
}

def plz_to_bezirk(plz: str) -> str | None:
    """Extract Bezirk name from Austrian postal code."""
    plz = plz.strip()
    if not re.match(r"^\d{4}$", plz):
        return None

    # Wien: 1010–1230
    if plz.startswith("1") and plz != "1000":
        num = int(plz[1:3])
        if 1 <= num <= 23:
            return f"{num}. Bezirk – {WIEN_BEZIRKE.get(num, '')}"

    # All others: use pgeocode county_name
    r = nomi.query_postal_code(plz)
    county = str(r.county_name) if r.county_name and str(r.county_name) != "nan" else None
    if not county:
        return None
    # Clean up: "Politischer Bezirk Mistelbach" → "Mistelbach"
    county = re.sub(r"^Politischer Bezirk ", "", county)
    # "Wiener Neustadt Stadt" → "Wiener Neustadt"
    county = re.sub(r" Stadt$", "", county)
    return county


async def main():
    db = AsyncIOMotorClient(os.environ["MONGODB_URI"])["padel_checker"]
    venues = await db["venues"].find({}, {"name": 1, "operator": 1, "address": 1, "_id": 0}).to_list(1000)

    print(f"{'Venue':<40} {'Address PLZ':<8} {'Bezirk'}")
    print("-" * 85)
    no_plz = 0
    for v in sorted(venues, key=lambda x: x.get("address", "")):
        addr = v.get("address", "")
        m = re.search(r"\b(\d{4})\b", addr)
        if not m:
            no_plz += 1
            continue
        plz = m.group(1)
        bezirk = plz_to_bezirk(plz)
        name = (v.get("operator", "") + " " + v.get("name", "")).strip()[:38]
        print(f"{name:<40} {plz:<8} {bezirk or '?'}")

    print(f"\nVenues without PLZ in address: {no_plz}")

asyncio.run(main())
