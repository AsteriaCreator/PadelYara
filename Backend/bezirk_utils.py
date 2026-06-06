"""
Austrian postal code → Bezirk name lookup.

Wien (1010–1230): formula-based (digits 2-3 of PLZ) → avoids GeoNames data quality issues.
All other Bundesländer: pgeocode (GeoNames) county_name field, cleaned up.

Usage:
    from bezirk_utils import plz_to_bezirk

    plz_to_bezirk("1220")  → "22. Bezirk – Donaustadt"
    plz_to_bezirk("8200")  → "Graz-Umgebung"
    plz_to_bezirk("5020")  → "Salzburg"
"""
import re
import pgeocode

_nomi = None  # lazy-loaded singleton

def _get_nomi():
    global _nomi
    if _nomi is None:
        _nomi = pgeocode.Nominatim("AT")
    return _nomi


WIEN_BEZIRKE = {
    1: "Innere Stadt",
    2: "Leopoldstadt",
    3: "Landstraße",
    4: "Wieden",
    5: "Margareten",
    6: "Mariahilf",
    7: "Neubau",
    8: "Josefstadt",
    9: "Alsergrund",
    10: "Favoriten",
    11: "Simmering",
    12: "Meidling",
    13: "Hietzing",
    14: "Penzing",
    15: "Rudolfsheim-Fünfhaus",
    16: "Ottakring",
    17: "Hernals",
    18: "Währing",
    19: "Döbling",
    20: "Brigittenau",
    21: "Floridsdorf",
    22: "Donaustadt",
    23: "Liesing",
}


def plz_to_bezirk(plz: str) -> str | None:
    """
    Convert a 4-digit Austrian postal code to a Bezirk name.
    Returns None if the PLZ is invalid or data is unavailable.
    """
    plz = plz.strip()
    if not re.match(r"^\d{4}$", plz):
        return None

    # Wien: 1010–1230
    if plz.startswith("1") and plz != "1000":
        num = int(plz[1:3])
        if 1 <= num <= 23:
            name = WIEN_BEZIRKE.get(num, "")
            return f"{num}. Bezirk – {name}" if name else f"{num}. Bezirk"

    # All other Bundesländer: use pgeocode county_name
    try:
        r = _get_nomi().query_postal_code(plz)
        county = str(r.county_name) if r.county_name and str(r.county_name) != "nan" else None
        if not county:
            return None
        # "Politischer Bezirk Mistelbach" → "Mistelbach"
        county = re.sub(r"^Politischer Bezirk ", "", county)
        # "Wiener Neustadt Stadt" / "Klagenfurt am Wörthersee Stadt" → without " Stadt"
        county = re.sub(r" Stadt$", "", county)
        return county.strip() or None
    except Exception:
        return None


def extract_plz_from_address(address: str) -> str | None:
    """Extract a 4-digit Austrian PLZ from an address string like 'Straße 5, 1220 Wien'."""
    if not address:
        return None
    m = re.search(r"\b(\d{4})\b", address)
    return m.group(1) if m else None


def bezirk_from_address(address: str) -> str | None:
    """Convenience: extract PLZ from address then map to Bezirk."""
    plz = extract_plz_from_address(address)
    return plz_to_bezirk(plz) if plz else None
