"""
Unit tests for eTennis exact-start slot matching.

Verifies that a slot is only considered available when its start timestamp
matches the requested time EXACTLY.  Range-based overlap (a slot that
merely *contains* the requested time) must NOT produce a match.

This guards against false positives like:
  - search 07:00, slot 06:30-08:00 → must be no_slot (not free)
  - search 18:00, slot 17:30-19:00 → must be no_slot (not free)

Run with:
  python -m pytest Backend/test_slot_matching.py -v
  # or directly:
  python Backend/test_slot_matching.py
"""

from datetime import datetime
from zoneinfo import ZoneInfo

VIENNA_TZ = ZoneInfo("Europe/Vienna")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ts(hour: int, minute: int = 0, date: str = "2026-05-21") -> int:
    """Unix timestamp for a given HH:MM in Vienna timezone."""
    dt = datetime.fromisoformat(f"{date}T{hour:02d}:{minute:02d}:00").replace(
        tzinfo=VIENNA_TZ
    )
    return int(dt.timestamp())


def _make_slot(hour: int, minute: int = 0, size: float = 1.5, av: bool = True) -> dict:
    """Minimal slot dict mirroring the eTennis HTML data attributes."""
    return {"begin": _ts(hour, minute), "size": size, "av": av}


def _status(slots: list[dict], target_ts: int) -> str:
    """
    Derive the scraper status string from matched slots.

    Mirrors the logic in _check_one (JS evaluate) and _http_scrape:
      1. Exact start-time match → 'free' or 'busy'
      2. No exact match, but a running slot covers this time → 'busy'
      3. No slot at all → 'no_slot'
    """
    matching = [s for s in slots if s["begin"] == target_ts]
    if matching:
        av_count = sum(1 for s in matching if s.get("av"))
        return "free" if av_count > 0 else "busy"
    # Range check: is any BOOKED (non-av) slot running at target_ts?
    # A free slot that contains the time means the court is empty but no new
    # booking can start here — that is still "no_slot", not "busy".
    occupied = any(
        not s.get("av") and s["begin"] < target_ts < s["begin"] + s.get("size", 1.5) * 3600
        for s in slots
    )
    return "busy" if occupied else "no_slot"


# ── Test cases ─────────────────────────────────────────────────────────────────

def test_0700_no_match_with_0630_and_0800_slots():
    """
    07:00 with slots at 06:30 and 08:00 → no_slot.

    The 06:30 slot (size=1.5) would range-match 07:00, but must NOT — only
    exact start times are valid.
    """
    slots = [_make_slot(6, 30, size=1.5), _make_slot(8, 0, size=1.5)]
    assert _status(slots, _ts(7, 0)) == "no_slot", (
        "07:00 must not match a slot starting at 06:30 even though 07:00 falls "
        "within its 90-min window"
    )


def test_0730_no_match_with_0630_and_0800_slots():
    """
    07:30 fallback also has no match with slots 06:30 / 08:00 → no_slot.

    Confirms the fallback correctly returns no_slot instead of matching the
    earlier 06:30 slot whose range covers 07:30.
    """
    slots = [_make_slot(6, 30, size=1.5), _make_slot(8, 0, size=1.5)]
    assert _status(slots, _ts(7, 30)) == "no_slot", (
        "07:30 fallback must not match a slot starting at 06:30"
    )


def test_0800_exact_match_is_free():
    """
    08:00 with a free slot starting at 08:00 → free.
    """
    slots = [_make_slot(6, 30, size=1.5), _make_slot(8, 0, size=1.5, av=True)]
    assert _status(slots, _ts(8, 0)) == "free", (
        "08:00 must match the slot that starts exactly at 08:00"
    )


def test_0800_exact_match_is_busy():
    """
    08:00 with a taken slot starting at 08:00 → busy.
    """
    slots = [_make_slot(8, 0, size=1.5, av=False)]
    assert _status(slots, _ts(8, 0)) == "busy", (
        "08:00 must match the slot at 08:00 and report busy when av=False"
    )


def test_1800_no_slot_fallback_1830_is_free():
    """
    18:00 primary → no_slot (no exact start).
    18:30 fallback → free (slot starts exactly at 18:30).

    This is the canonical Padelunion Prater case.
    """
    slots = [_make_slot(18, 30, size=1.5, av=True)]
    assert _status(slots, _ts(18, 0)) == "no_slot", (
        "18:00 must not match slot starting at 18:30"
    )
    assert _status(slots, _ts(18, 30)) == "free", (
        "18:30 fallback must match the slot starting at 18:30"
    )


def test_1800_only_1730_slot_neither_primary_nor_fallback():
    """
    18:00 with only a slot at 17:30 → neither primary (18:00) nor fallback
    (18:30) should match.
    """
    slots = [_make_slot(17, 30, size=1.5, av=True)]
    assert _status(slots, _ts(18, 0)) == "no_slot", (
        "18:00 must not match a slot at 17:30"
    )
    assert _status(slots, _ts(18, 30)) == "no_slot", (
        "18:30 fallback must not match a slot at 17:30"
    )


def test_range_overlap_free_slot_never_matches():
    """
    A FREE (unbooked) slot at 09:00 (size=1.5h):
      - 09:00 exact start → 'free'
      - 09:30 inside the free slot → 'no_slot' (court empty, but can't start new booking here)
      - 10:00 after the slot ends → 'no_slot'
    Only a BOOKED (non-av) overlapping slot produces 'busy'.
    """
    slots = [_make_slot(9, 0, size=1.5, av=True)]
    assert _status(slots, _ts(9, 0))  == "free",    "09:00 must match its own start as free"
    assert _status(slots, _ts(9, 30)) == "no_slot", "09:30 inside unbooked slot — no new booking possible, court empty"
    assert _status(slots, _ts(10, 0)) == "no_slot", "10:00 is after the slot ends"


def test_occupied_slot_shows_busy_not_no_slot():
    """
    Schwechat-style: a BUSY 90-min slot starting at 10:30.
    Searching at 11:00 should return 'busy' (court occupied), not 'no_slot'.
    """
    slots = [_make_slot(10, 30, size=1.5, av=False)]   # busy slot 10:30–12:00
    assert _status(slots, _ts(10, 30)) == "busy",   "10:30 exact start is busy"
    assert _status(slots, _ts(11, 0))  == "busy",   "11:00 inside running busy slot must be busy"
    assert _status(slots, _ts(12, 0))  == "no_slot", "12:00 is after the slot ends"


# ── Runner ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_0700_no_match_with_0630_and_0800_slots,
        test_0730_no_match_with_0630_and_0800_slots,
        test_0800_exact_match_is_free,
        test_0800_exact_match_is_busy,
        test_1800_no_slot_fallback_1830_is_free,
        test_1800_only_1730_slot_neither_primary_nor_fallback,
        test_range_overlap_free_slot_never_matches,
        test_occupied_slot_shows_busy_not_no_slot,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")

    print(f"\n{passed}/{len(tests)} tests passed.")
    if passed < len(tests):
        raise SystemExit(1)
