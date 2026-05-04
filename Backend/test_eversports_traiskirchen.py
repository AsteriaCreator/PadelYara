"""
Standalone test for the Eversports checker against Padelzone Traiskirchen.

Usage (from Backend/):
    python test_eversports_traiskirchen.py

Runs the checker for today's date at 17:00, 18:00, and 19:00 and prints
the raw parsed status.  app.py's platform_check_required override is NOT
applied here — you see exactly what the checker returns.
"""

import sys
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# Enable debug output before importing the checker module
os.environ["EVERSPORTS_DEBUG"] = "1"

# Patch DEBUG_MODE before the module is imported
import eversports_checker
eversports_checker.DEBUG_MODE = True

from eversports_checker import check_eversports_venues

VIENNA_TZ = ZoneInfo("Europe/Vienna")

TRAISKIRCHEN = {
    "id":          "padelzone-traiskirchen",
    "name":        "Padelzone Traiskirchen",
    "booking_url": "https://www.eversports.at/sb/padelzone-traiskirchen",
}

EBREICHSDORF = {
    "id":          "padel-ebreichsdorf",
    "name":        "Padel Ebreichsdorf",
    "booking_url": "https://www.eversports.at/sb/padel-tennis-ebreichsdorf-og",
}

TEST_DATE = "2026-05-04"  # date from the acceptance criteria
TEST_HOURS = [17, 18, 19]


def make_dt(hour: int) -> datetime:
    return datetime.strptime(f"{TEST_DATE}T{hour:02d}:00", "%Y-%m-%dT%H:%M").replace(
        tzinfo=VIENNA_TZ
    )


def run_test(venue: dict, hour: int) -> str:
    dt = make_dt(hour)
    print(f"\n{'='*60}")
    print(f"Testing {venue['name']} @ {TEST_DATE} {hour:02d}:00")
    print(f"{'='*60}")
    result = check_eversports_venues([venue], dt)
    status = result.get(venue["id"], "MISSING")
    print(f"\n>>> RESULT: {venue['id']} @ {hour:02d}:00 -> {status}")
    return status


if __name__ == "__main__":
    print("Eversports Traiskirchen checker test")
    print(f"Test date: {TEST_DATE}")
    print(f"Test hours: {TEST_HOURS}")

    summary: list[tuple[str, int, str]] = []

    # Test Traiskirchen at each hour
    for h in TEST_HOURS:
        status = run_test(TRAISKIRCHEN, h)
        summary.append(("traiskirchen", h, status))

    # Test Ebreichsdorf at 17:00 to confirm false-positive fix
    status = run_test(EBREICHSDORF, 17)
    summary.append(("ebreichsdorf", 17, status))

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for venue_key, hour, status in summary:
        expected = {
            ("traiskirchen", 17): "free (if slot exists)",
            ("traiskirchen", 18): "busy (if only booked slots)",
            ("traiskirchen", 19): "must NOT be free",
            ("ebreichsdorf", 17): "should not be free false-positive",
        }.get((venue_key, hour), "?")
        print(f"  {venue_key:20s} {hour:02d}:00 -> {status:10s}  [{expected}]")
