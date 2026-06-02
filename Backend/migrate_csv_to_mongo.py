"""
One-time migration script: imports Padel_Venues.csv into MongoDB.

Usage:
    cd Backend
    python migrate_csv_to_mongo.py

Requires MONGODB_URI in Backend/.env or as an environment variable.
Safe to re-run — uses upsert on venue id so duplicates are not created.
"""

import asyncio
import csv
import os
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient


def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

_load_env()

CSV_PATH = Path(__file__).parent.parent / "Padel_Venues.csv"


def _parse_int(val: str) -> int | None:
    v = (val or "").strip()
    return int(v) if v else None


def _parse_float(val: str) -> float | None:
    v = (val or "").strip()
    try:
        return float(v) if v else None
    except ValueError:
        return None


def _parse_bool(val: str) -> bool:
    return (val or "").strip().lower() == "true"


def _parse_fallback_minutes(val: str | None) -> list[int]:
    v = (val or "").strip()
    if not v:
        return []
    return [int(x) for x in v.split(",") if x.strip()]


def _parse_court_ids(val: str) -> list[int]:
    v = (val or "").strip()
    if not v:
        return []
    return [int(x) for x in v.split("|") if x.strip()]


def _parse_row(row: dict) -> dict:
    return {
        "id":                     row["id"].strip(),
        "name":                   row["name"].strip(),
        "active":                 _parse_bool(row.get("active", "")),
        "region_key":             row.get("region_key", "").strip(),
        "region_label":           row.get("region_label", "").strip(),
        "court_type":             row.get("court_type", "").strip(),
        "platform":               row.get("platform", "").strip(),
        "operator":               row.get("operator", "").strip(),
        "priority":               int(row.get("priority", "0").strip() or 0),
        "address":                row.get("address", "").strip(),
        "booking_url":            row.get("booking_url", "").strip(),
        "public_url":             row.get("public_url", "").strip(),
        "lat":                    _parse_float(row.get("lat", "")),
        "lon":                    _parse_float(row.get("lon", "")),
        "maps_id":                row.get("maps_id", "").strip() or None,
        "platform_id":            row.get("platform_id", "").strip() or None,
        "etennis_id":             row.get("etennis_id", "").strip() or None,
        "eversports_slug":        row.get("eversports_slug", "").strip() or None,
        "eversports_facility_id": _parse_int(row.get("eversports_facility_id", "")),
        "eversports_court_ids":   _parse_court_ids(row.get("eversports_court_ids", "")),
        "notes":                  (row.get("notes") or "").strip() or None,
        "issues":                 (row.get("issues") or "").strip() or None,
        "slot_fallback_minutes":  _parse_fallback_minutes(row.get("slot_fallback_minutes", "")),
    }


async def migrate():
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise RuntimeError("MONGODB_URI not set")

    client = AsyncIOMotorClient(uri)
    collection = client["padel_checker"]["venues"]

    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(_parse_row(row))

    inserted = 0
    updated = 0
    for doc in rows:
        result = await collection.update_one(
            {"id": doc["id"]},
            {"$set": doc},
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
            print(f"  [inserted] {doc['id']}")
        else:
            updated += 1
            print(f"  [updated]  {doc['id']}")

    print(f"\nDone. {inserted} inserted, {updated} updated. Total: {len(rows)} venues.")
    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
