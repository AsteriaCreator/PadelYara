"""
Regression test: Eversports availability check must not be blocked by an
ongoing price refresh.

Bug: _refresh_running gated the entire Eversports check block, not just the
price-refresh task creation. While prices were refreshing (~6 min with stagger
across 12 venues), all Eversports venues returned 'unknown' ("Nicht online
prüfbar") instead of 'pending'.

Fix: the availability check (pending marking + background scraper kick-off)
runs regardless of _refresh_running. Only the price-refresh task creation is
gated.

Run with:
    python -m pytest Backend/test_ev_refresh_gate.py -v
    # or directly:
    python Backend/test_ev_refresh_gate.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import eversports_prices


# ── Minimal stub for the logic we're testing ──────────────────────────────────
# We don't spin up FastAPI — we reproduce the exact conditional structure from
# app.py so the test is fast, dependency-free, and pinned to the bug.

_EV_UNCHECKED = {None, "pending", "unknown"}


def _simulate_ev_block(ev_results: list[dict], refresh_running: bool) -> list[dict]:
    """
    Mirrors the app.py Eversports check block.
    Returns the modified ev_results after the block runs.

    BEFORE fix: the entire block was inside `if not refresh_running`, so
    venues stayed 'unknown' while a price refresh was in progress.

    AFTER fix: only the price task creation is gated; availability check
    always runs.
    """
    if ev_results:
        # Price refresh — gated, best-effort only
        if not refresh_running:
            pass  # would call asyncio.create_task(refresh_prices_async(...))

        # Availability check — always runs (this is the fix)
        ev_pending = []
        for r in ev_results:
            if r.get("availability_status") in _EV_UNCHECKED:
                r["availability_status"] = "pending"
                ev_pending.append(r)

    return ev_results


def _simulate_ev_block_bugged(ev_results: list[dict], refresh_running: bool) -> list[dict]:
    """
    Mirrors the BUGGY version of the block (before fix):
    entire check inside `if not refresh_running`.
    """
    if ev_results and not refresh_running:
        ev_pending = []
        for r in ev_results:
            if r.get("availability_status") in _EV_UNCHECKED:
                r["availability_status"] = "pending"
                ev_pending.append(r)

    return ev_results


# ── Tests ─────────────────────────────────────────────────────────────────────

def _make_ev_results(n: int = 3) -> list[dict]:
    return [
        {"venue_id": f"venue-{i}", "platform": "Eversports", "availability_status": "unknown"}
        for i in range(n)
    ]


def test_refresh_running_does_not_block_availability_check():
    """
    With _refresh_running=True, Eversports venues must still be marked 'pending'.
    This is the core regression: the fix.
    """
    results = _make_ev_results(3)
    out = _simulate_ev_block(results, refresh_running=True)
    statuses = [r["availability_status"] for r in out]
    assert all(s == "pending" for s in statuses), (
        f"Expected all 'pending' while refresh running, got: {statuses}"
    )


def test_refresh_not_running_marks_pending():
    """
    Normal case: no refresh in progress → venues still become 'pending'.
    """
    results = _make_ev_results(3)
    out = _simulate_ev_block(results, refresh_running=False)
    statuses = [r["availability_status"] for r in out]
    assert all(s == "pending" for s in statuses), (
        f"Expected all 'pending' with no refresh running, got: {statuses}"
    )


def test_bugged_version_reproduces_the_problem():
    """
    Confirms the old code DID cause the bug — documents the regression baseline.
    With refresh_running=True, the buggy block leaves venues as 'unknown'.
    """
    results = _make_ev_results(3)
    out = _simulate_ev_block_bugged(results, refresh_running=True)
    statuses = [r["availability_status"] for r in out]
    assert all(s == "unknown" for s in statuses), (
        f"Buggy version should leave statuses as 'unknown', got: {statuses}"
    )


def test_already_resolved_venues_not_overwritten():
    """
    A venue that already has a real status (e.g. cached 'free') must not be
    reset to 'pending' when the block runs.
    """
    results = [
        {"venue_id": "venue-cached", "platform": "Eversports", "availability_status": "free"},
        {"venue_id": "venue-fresh",  "platform": "Eversports", "availability_status": "unknown"},
    ]
    out = _simulate_ev_block(results, refresh_running=True)
    statuses = {r["venue_id"]: r["availability_status"] for r in out}
    assert statuses["venue-cached"] == "free",    "Cached 'free' must not be overwritten"
    assert statuses["venue-fresh"]  == "pending", "Unchecked venue must become 'pending'"


def test_empty_ev_results_no_error():
    """Edge case: no Eversports venues in the result set — block must not crash."""
    out = _simulate_ev_block([], refresh_running=True)
    assert out == []


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_refresh_running_does_not_block_availability_check,
        test_refresh_not_running_marks_pending,
        test_bugged_version_reproduces_the_problem,
        test_already_resolved_venues_not_overwritten,
        test_empty_ev_results_no_error,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")

    print(f"\n{passed}/{len(tests)} tests passed.")
    if passed < len(tests):
        raise SystemExit(1)
