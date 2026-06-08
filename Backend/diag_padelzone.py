"""
Diagnostic script for Padelzone Eversports availability issues.

Fetches /api/slot directly for every Padelzone venue and reports:
  - HTTP status from Eversports
  - Whether response is a CF block or valid JSON
  - Slots count and date scope
  - Whether the scope would cover today's target time
  - Raw excerpt of the response body

Usage:
    cd Backend
    python diag_padelzone.py
    python diag_padelzone.py --date 2026-06-03 --time 18:00
"""

import argparse
import asyncio
import json
import sys
from datetime import date, timedelta
from urllib.parse import urlencode

# ---------------------------------------------------------------------------
# Inline minimal venue loader (no FastAPI dependency needed)
# ---------------------------------------------------------------------------

import csv
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "Padel_Venues.csv"


def _parse_court_ids(val: str) -> list[int]:
    v = val.strip()
    return [int(x) for x in v.split("|") if x.strip()] if v else []


def load_padelzone_venues() -> list[dict]:
    venues = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("active", "").strip().lower() != "true":
                continue
            brand = row.get("operator", "").strip()
            if brand.lower() != "padelzone":
                continue
            fid_raw = row.get("eversports_facility_id", "").strip()
            venues.append({
                "id":           row["id"].strip(),
                "name":         row["name"].strip(),
                "facility_id":  int(fid_raw) if fid_raw else None,
                "court_ids":    _parse_court_ids(row.get("eversports_court_ids", "")),
                "booking_url":  row.get("booking_url", "").strip(),
                "slug":         row.get("eversports_slug", "").strip(),
            })
    return venues


# ---------------------------------------------------------------------------
# Minimal Eversports /api/slot fetch (mirrors eversports_service._fetch_slots)
# but without the CF cookie cache — uses curl_cffi Chrome impersonation only.
# ---------------------------------------------------------------------------

_SLOT_URL = "https://www.eversports.at/api/slot"
_CAL_URL  = "https://www.eversports.at/api/booking/calendar/update"


async def _raw_slot_fetch(facility_id: int, court_ids: list[int], date_str: str) -> tuple[int, str]:
    """Fetch /api/slot via curl_cffi Chrome impersonation."""
    try:
        from curl_cffi.requests import AsyncSession
    except ImportError:
        sys.exit("curl_cffi not installed — pip install curl_cffi")

    params: list[tuple] = [("facilityId", facility_id), ("startDate", date_str)]
    for cid in court_ids:
        params.append(("courts[]", cid))

    async with AsyncSession(impersonate="chrome124") as session:
        r = await session.get(_SLOT_URL, params=params, timeout=15)
    return r.status_code, r.text


async def _raw_calendar_fetch(venue_url: str, facility_id: int, date_str: str) -> tuple[int, str]:
    """POST /api/booking/calendar/update via curl_cffi Chrome impersonation."""
    try:
        from curl_cffi.requests import AsyncSession
    except ImportError:
        sys.exit("curl_cffi not installed — pip install curl_cffi")

    import re
    from datetime import datetime

    facility_slug = venue_url.rstrip("/").split("/")[-1]
    dp = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")

    async with AsyncSession(impersonate="chrome124") as session:
        get_resp = await session.get(venue_url, timeout=20)
        if get_resp.status_code != 200:
            return get_resp.status_code, get_resp.text[:200]

        csrf_token = ""
        m = re.search(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)', get_resp.text)
        if not m:
            m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']csrf-token', get_resp.text)
        if m:
            csrf_token = m.group(1)

        fid_in_page = facility_id
        m2 = re.search(r"data-id=['\"](\d+)['\"]", get_resp.text)
        if m2:
            fid_in_page = int(m2.group(1))

        headers = {
            "Content-Type":     "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Accept":           "*/*",
            "Accept-Language":  "de-AT,de;q=0.9,en;q=0.8",
            "Referer":          venue_url,
            "Origin":           "https://www.eversports.at",
        }
        if csrf_token:
            headers["X-CSRF-TOKEN"] = csrf_token

        post_data = {
            "date":       dp,
            "facilityId": str(fid_in_page),
            "facility":   facility_slug,
        }
        post_resp = await session.post(_CAL_URL, data=post_data, headers=headers, timeout=20)
        return post_resp.status_code, post_resp.text


def _is_cf_block(status: int, text: str) -> bool:
    return status in (403, 503) or "Just a moment" in text[:500] or "Checking your browser" in text[:500]


def _parse_slots(text: str) -> list | None:
    try:
        data = json.loads(text)
        slots = data.get("slots", [])
        if isinstance(slots, list):
            return slots
        if isinstance(slots, dict):
            inner = slots.get("slots", [])
            return inner if isinstance(inner, list) else None
        return None
    except Exception:
        return None


def _hhmm_to_min(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[2:])


async def diagnose_venue(venue: dict, date_str: str, time_hhmm: str) -> dict:
    fid      = venue["facility_id"]
    cids     = venue["court_ids"]
    name     = venue["name"]
    book_url = venue["booking_url"]

    result: dict = {
        "venue":        name,
        "facility_id":  fid,
        "court_ids":    cids,
        "date":         date_str,
        "time":         time_hhmm,
    }

    if not fid or not cids:
        result["error"] = "missing facility_id or court_ids in CSV"
        return result

    # --- Method 1: /api/slot ---
    print(f"  [{name}] fetching /api/slot ...")
    http_status, text = await _raw_slot_fetch(fid, cids, date_str)
    result["slot_http_status"] = http_status
    result["slot_body_excerpt"] = text[:300]
    result["slot_cf_block"]     = _is_cf_block(http_status, text)

    if not result["slot_cf_block"] and http_status == 200:
        slots = _parse_slots(text)
        if slots is None:
            result["slot_parse_error"] = True
            result["slot_verdict"] = "parse_error → platform_check_required"
        else:
            result["slot_count"] = len(slots)
            all_dates   = [s.get("date", "")  for s in slots if s.get("date")]
            all_starts  = sorted(set(s.get("start", "") for s in slots if s.get("start")))
            scope_max   = max(all_dates) if all_dates else ""
            same_day    = [s.get("start", "") for s in slots if s.get("date") == date_str and s.get("start")]
            max_same    = max(same_day) if same_day else ""
            scope_covers = scope_max > date_str or max_same > time_hhmm

            result["scope_max_date"]   = scope_max or "(empty)"
            result["same_day_starts"]  = sorted(set(same_day)) or []
            result["all_time_slots"]   = all_starts[:20]
            result["scope_covers"]     = scope_covers

            if not scope_covers:
                result["slot_verdict"] = "scope does NOT cover target → platform_check_required"
            else:
                booked_at_target = {s.get("court") for s in slots
                                    if s.get("date") == date_str and s.get("start") == time_hhmm}
                result["booked_courts_at_target"] = list(booked_at_target)
                free_count = sum(1 for c in cids if c not in booked_at_target)
                result["slot_verdict"] = "free" if free_count > 0 else "busy"
    elif result["slot_cf_block"]:
        result["slot_verdict"] = "CLOUDFLARE BLOCK on /api/slot"

    # --- Method 2: calendar POST (only if booking_url available) ---
    if book_url:
        print(f"  [{name}] fetching /api/booking/calendar/update ...")
        try:
            cal_status, cal_body = await _raw_calendar_fetch(book_url, fid, date_str)
            result["cal_http_status"] = cal_status
            result["cal_cf_block"]    = _is_cf_block(cal_status, cal_body)
            result["cal_has_td"]      = "<td" in cal_body
            result["cal_body_excerpt"] = cal_body[:300]
        except Exception as exc:
            result["cal_error"] = f"{type(exc).__name__}: {exc}"

    return result


async def main():
    parser = argparse.ArgumentParser()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    parser.add_argument("--date", default=tomorrow, help="ISO date (default: tomorrow)")
    parser.add_argument("--time", default="18:00",  help="HH:MM time (default: 18:00)")
    args = parser.parse_args()

    date_str  = args.date
    time_hhmm = args.time.replace(":", "")

    venues = load_padelzone_venues()
    if not venues:
        sys.exit("No active Padelzone venues found in CSV.")

    print(f"\nDiagnosing {len(venues)} Padelzone venue(s) — date={date_str}  time={args.time}\n")
    print("=" * 70)

    results = []
    for v in venues:
        print(f"\n>> {v['name']}  (fid={v['facility_id']}  courts={v['court_ids']})")
        r = await diagnose_venue(v, date_str, time_hhmm)
        results.append(r)

    print("\n" + "=" * 70)
    print("SUMMARY\n")
    for r in results:
        verdict  = r.get("slot_verdict", "n/a")
        scope    = r.get("scope_max_date", "—")
        cf_slot  = "CF-BLOCK" if r.get("slot_cf_block") else "ok"
        cf_cal   = ("CF-BLOCK" if r.get("cal_cf_block") else ("has-td" if r.get("cal_has_td") else "no-td")) if "cal_http_status" in r else "—"
        print(f"  {r['venue']:<45}  slot={cf_slot:<8}  cal={cf_cal:<10}  scope_max={scope:<12}  => {verdict}")

    print()

    # Dump full JSON for inspection
    out_path = Path(__file__).parent / "diag_padelzone_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Full results written to: {out_path}\n")


if __name__ == "__main__":
    asyncio.run(main())
