#!/usr/bin/env python3
"""
One-time migration: seed MongoDB venues collection from Padel_Venues.csv.

Run whenever the CSV changes (upserts, so safe to re-run):

    cd Backend
    python seed_venues.py

Requires MONGODB_URI in Backend/.env (copy from .env.example).
"""

import asyncio
import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

CSV_PATH = Path(__file__).parent.parent / "Padel_Venues.csv"


def _parse_float(s: str) -> float | None:
    s = s.strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _parse_int(s: str, default: int = 0) -> int:
    try:
        return int(s.strip()) if s.strip() else default
    except ValueError:
        return default


def _row_to_doc(row: dict) -> dict:
    """Map one CSV row to a MongoDB document. _id = venue id."""
    return {
        "_id":             row["id"].strip(),
        "name":            row["name"].strip(),
        "active":          row.get("active", "").strip().lower() == "true",
        "region_key":      row.get("region_key", "").strip(),
        "region_label":    row.get("region_label", "").strip(),
        "court_type":      row.get("court_type", "").strip(),
        "platform":        row.get("platform", "").strip(),
        "operator":        row.get("operator", "").strip(),
        "priority":        _parse_int(row.get("priority", "0")),
        "address":         row.get("address", "").strip(),
        "booking_url":     row.get("booking_url", "").strip(),
        "public_url":      row.get("public_url", "").strip(),
        "lat":             _parse_float(row.get("lat", "")),
        "lon":             _parse_float(row.get("lon", "")),
        "platform_id":     row.get("platform_id", "").strip() or None,
        "etennis_id":      row.get("etennis_id", "").strip() or None,
        "eversports_slug": row.get("eversports_slug", "").strip() or None,
        "notes":           row.get("notes", "").strip(),
        "issues":          row.get("issues", "").strip(),
    }


async def seed() -> None:
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        print("ERROR: MONGODB_URI not set.")
        print("  → Copy Backend/.env.example to Backend/.env and fill in the URI.")
        sys.exit(1)

    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found at {CSV_PATH}")
        sys.exit(1)

    # Read CSV
    docs: list[dict] = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            docs.append(_row_to_doc(row))

    if not docs:
        print("ERROR: CSV is empty or has no data rows.")
        sys.exit(1)

    print(f"Read {len(docs)} rows from {CSV_PATH.name}")
    print(f"Connecting to MongoDB...")

    client = AsyncIOMotorClient(uri)
    collection = client["padel_checker"]["venues"]

    inserted = updated = 0
    for doc in docs:
        vid = doc["_id"]
        result = await collection.replace_one({"_id": vid}, doc, upsert=True)
        if result.upserted_id:
            inserted += 1
            status = "active  " if doc["active"] else "inactive"
            print(f"  + [{status}] {vid}")
        else:
            updated += 1
            status = "active  " if doc["active"] else "inactive"
            print(f"  ~ [{status}] {vid}")

    client.close()
    print(f"\nDone: {inserted} inserted, {updated} updated ({len(docs)} total).")


if __name__ == "__main__":
    asyncio.run(seed())
