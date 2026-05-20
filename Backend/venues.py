import csv
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "Padel_Venues.csv"

_COURT_TYPE_MAP = {"indoor_outdoor": "indoor+outdoor"}
_PLATFORM_MAP = {"etennis": "eTennis", "eversports": "Eversports", "other": "Andere"}


def _parse_int(val: str) -> int | None:
    v = val.strip()
    return int(v) if v else None


def _parse_fallback_minutes(val: str) -> list[int]:
    v = val.strip()
    if not v:
        return []
    return [int(x) for x in v.split(",") if x.strip()]


def _parse_court_ids(val: str) -> list[int]:
    v = val.strip()
    if not v:
        return []
    return [int(x) for x in v.split("|") if x.strip()]


def load_venues() -> list[dict]:
    venues = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("active", "").strip().lower() != "true":
                continue
            venues.append(_parse_row(row))
    return venues


def _parse_row(row: dict) -> dict:
    lat_raw = row.get("lat", "").strip()
    lon_raw = row.get("lon", "").strip()

    try:
        lat = float(lat_raw) if lat_raw else None
    except ValueError:
        lat = None

    try:
        lon = float(lon_raw) if lon_raw else None
    except ValueError:
        lon = None

    court_type = row.get("court_type", "").strip()
    platform = row.get("platform", "").strip().lower()

    return {
        "id":               row["id"].strip(),
        "name":             row["name"].strip(),
        "region":           row["region_label"].strip(),
        "court_type":       _COURT_TYPE_MAP.get(court_type, court_type),
        "platform":         _PLATFORM_MAP.get(platform, platform),
        "priority":         int(row.get("priority", "0").strip() or 0),
        "booking_url":      row.get("booking_url", "").strip(),
        "lat":              lat,
        "lon":              lon,
        "platform_id":             row.get("etennis_id", "").strip() or None,
        "eversports_slug":         row.get("eversports_slug", "").strip() or None,
        "eversports_facility_id":  _parse_int(row.get("eversports_facility_id", "")),
        "eversports_court_ids":    _parse_court_ids(row.get("eversports_court_ids", "")),
        "issues":                  (row.get("issues") or "").strip(),
        "slot_fallback_minutes":   _parse_fallback_minutes(row.get("slot_fallback_minutes", "")),
    }
