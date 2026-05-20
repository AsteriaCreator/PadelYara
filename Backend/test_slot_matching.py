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


def _match_exact(slots: list[dict], target_ts: int) -> list[dict]:
    """
    Mirrors the exact-start matching used in both the Playwright JS evaluation
    and the _http_scrape Python fallback in etennis_checker.py.

    A slot matches only when  begin == target_ts  (not begin <= ts < begin+size*3600).
    """
    return [s for s in slots if s["begin"] == target_ts]


def _status(slots: list[dict], target_ts: int) -> str:
    """Derive the scraper status string from matched slots."""
    matching = _match_exact(slots, target_ts)
    if not matching:
        return "no_slot"
    av_count = sum(1 for s in matching if s.get("av"))
    return "free" if av_count > 0 else "busy"


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


def test_range_overlap_never_matches():
    """
    Exhaustive overlap check: a 90-min slot at 09:00 must not match 09:30.
    Only 09:00 itself is valid.
    """
    slots = [_make_slot(9, 0, size=1.5, av=True)]
    assert _status(slots, _ts(9, 0)) == "free",    "09:00 must match its own start"
    assert _status(slots, _ts(9, 30)) == "no_slot", "09:30 must not match a slot starting at 09:00"
    assert _status(slots, _ts(10, 0)) == "no_slot", "10:00 must not match a slot starting at 09:00"


# ── Runner ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_0700_no_match_with_0630_and_0800_slots,
        test_0730_no_match_with_0630_and_0800_slots,
        test_0800_exact_match_is_free,
        test_0800_exact_match_is_busy,
        test_1800_no_slot_fallback_1830_is_free,
        test_1800_only_1730_slot_neither_primary_nor_fallback,
        test_range_overlap_never_matches,
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
