"""
Production smoke test for NeoPadelChecker.

Hits the live Render backend and verifies all three verified regions return
real availability results (not pending/unknown).  Exits 0 on full pass, 1
on any failure.

Usage (from repo root):
    python Backend/smoke_test.py
    python Backend/smoke_test.py --date 2026-05-18 --time 17:00

Env vars:
    RENDER_URL   override Render backend  (default: https://neopadelchecker.onrender.com)
    RAILWAY_URL  override Railway service (default: https://neo-padel-checker-backend-production.up.railway.app)
"""

import argparse
import os
import sys
import time
from datetime import date, timedelta

try:
    import requests
except ImportError:
    sys.exit("requests not installed — pip install requests")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RENDER_URL  = os.getenv("RENDER_URL",  "https://neopadelchecker.onrender.com")
RAILWAY_URL = os.getenv("RAILWAY_URL", "https://neo-padel-checker-backend-production.up.railway.app")

# region= param must use region_label from the CSV, never the slug.
# Source: Backend/venues.py:53  "region": row["region_label"].strip()
REGIONS = {
    "Bad Voeslau": "bad-voeslau",   # for reference only — API uses label
    "Wien Sued":   "wien-sued",
    "Wien":        "wien",
    "NOE Sued":    "noe-sued",
}

# Statuses that count as a real result (scraper ran and produced an answer)
REAL = {"free", "busy", "no_slot", "not_checked", "phone_only"}
# Statuses that mean the scraper hasn't finished yet
PENDING = {"pending", "unknown"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _search(region: str, date_str: str, time_str: str, timeout: int = 90) -> dict:
    r = requests.get(
        f"{RENDER_URL}/api/search",
        params={"region": region, "date": date_str, "time": time_str},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def _poll(region: str, date_str: str, time_str: str, max_wait: int = 90) -> dict:
    """Call /api/search and re-poll until availability_pending is False."""
    deadline = time.monotonic() + max_wait
    while True:
        data = _search(region, date_str, time_str)
        if not data.get("availability_pending") or time.monotonic() >= deadline:
            return data
        remaining = int(deadline - time.monotonic())
        print(f"      [poll] still pending — retrying in 20s ({remaining}s left) …")
        time.sleep(20)


def _fmt(results: dict) -> str:
    return "  ".join(f"{vid}={st}" for vid, st in sorted(results.items()))


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_railway_health() -> bool:
    print("[ Railway ] GET /health")
    try:
        r = requests.get(f"{RAILWAY_URL}/health", timeout=15)
        r.raise_for_status()
        body = r.json()
        ok = body.get("ok") is True and body.get("service") == "eversports-service"
        print(f"           {body}")
        return ok
    except Exception as exc:
        print(f"           ERROR: {exc}")
        return False


def test_1_traiskirchen(date_str: str, time_str: str) -> bool:
    """
    Eversports Traiskirchen via Bad Voeslau region.
    Required: padelzone-traiskirchen in {free, busy}.
    """
    print("[ Test 1  ] Eversports Traiskirchen (region=Bad Voeslau)")
    target = "padelzone-traiskirchen"
    try:
        data = _search("Bad Voeslau", date_str, time_str)
        statuses = {v["venue_id"]: v["availability_status"] for v in data["results"]}
        status = statuses.get(target, "MISSING")
        passed = status in {"free", "busy"}
        marker = "PASS" if passed else "FAIL"
        print(f"           {target} = {status}  [{marker}]")
        print(f"           all: {_fmt(statuses)}")
        return passed
    except Exception as exc:
        print(f"           ERROR: {exc}")
        return False


def test_2_achtersee(date_str: str, time_str: str) -> bool:
    """
    Eversports Achtersee + Arena 27 via NOE Sued region.
    Required: at least one of the two targets in {free, busy}.
    """
    print("[ Test 2  ] Eversports Achtersee / Arena 27 (region=NOE Sued)")
    targets = {
        "padelzone-wr-neustadt-achtersee",
        "padelzone-wr-neustadt-arena-27",
    }
    try:
        data = _search("NOE Sued", date_str, time_str)
        statuses = {v["venue_id"]: v["availability_status"] for v in data["results"]}
        target_statuses = {vid: statuses.get(vid, "MISSING") for vid in targets}
        passed = any(s in {"free", "busy"} for s in target_statuses.values())
        marker = "PASS" if passed else "FAIL"
        for vid, st in sorted(target_statuses.items()):
            print(f"           {vid} = {st}")
        print(f"           [{marker}]  all: {_fmt(statuses)}")
        return passed
    except Exception as exc:
        print(f"           ERROR: {exc}")
        return False


def test_3_bad_voeslau_etennis(date_str: str, time_str: str) -> bool:
    """
    eTennis Padel4Fun venues in Bad Voeslau region.
    Required: at least one of the Padel4Fun venues resolves to a real status
    (not pending/unknown) — confirms the HTTP fallback / Playwright path works.
    Polls until availability_pending is False.
    """
    print("[ Test 3  ] eTennis Padel4Fun (region=Bad Voeslau) — polling up to 120s for scraper")
    targets = {
        "padel4fun-tattendorf",
        "padel4fun-baden",
        "padel4fun-wr-neudorf",
    }
    try:
        data = _poll("Bad Voeslau", date_str, time_str, max_wait=120)
        statuses = {v["venue_id"]: v["availability_status"] for v in data["results"]}
        target_statuses = {vid: statuses.get(vid, "MISSING") for vid in targets}
        passed = any(s in REAL for s in target_statuses.values())
        marker = "PASS" if passed else "FAIL"
        for vid, st in sorted(target_statuses.items()):
            print(f"           {vid} = {st}")
        print(f"           [{marker}]  all: {_fmt(statuses)}")
        return passed
    except Exception as exc:
        print(f"           ERROR: {exc}")
        return False


def test_4_wien_etennis(date_str: str, time_str: str) -> bool:
    """
    eTennis Wien region.
    Required: at least one eTennis venue in {free, busy, no_slot} — i.e. scraper ran.
    Polls until availability_pending is False (background scraper finishes).
    """
    print("[ Test 4  ] eTennis Wien (region=Wien) — polling up to 90s for scraper")
    try:
        data = _poll("Wien", date_str, time_str, max_wait=90)
        etennis = [v for v in data["results"] if v.get("platform") == "eTennis"]
        statuses = {v["venue_id"]: v["availability_status"] for v in etennis}
        passed = any(s in REAL for s in statuses.values())
        marker = "PASS" if passed else "FAIL"
        for vid, st in sorted(statuses.items()):
            print(f"           {vid} = {st}")
        print(f"           [{marker}]")
        return passed
    except Exception as exc:
        print(f"           ERROR: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="NeoPadelChecker production smoke test")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    parser.add_argument("--date", default=tomorrow, help="ISO date (default: tomorrow)")
    parser.add_argument("--time", default="18:00",  help="HH:MM slot (default: 18:00)")
    args = parser.parse_args()

    print(f"NeoPadelChecker smoke test — {args.date} {args.time}")
    print(f"Render:  {RENDER_URL}")
    print(f"Railway: {RAILWAY_URL}")
    print()

    results = {
        "railway_health": test_railway_health(),
    }
    print()
    results["test_1"] = test_1_traiskirchen(args.date, args.time)
    print()
    results["test_2"] = test_2_achtersee(args.date, args.time)
    print()
    results["test_3"] = test_3_bad_voeslau_etennis(args.date, args.time)
    print()
    results["test_4"] = test_4_wien_etennis(args.date, args.time)
    print()

    passed = sum(results.values())
    total  = len(results)
    print("=" * 60)
    print(f"RESULT: {passed}/{total} passed")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print("=" * 60)

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
