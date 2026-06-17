"""
Integration tests for /api/search.

These are intentionally integration tests, not unit tests with mocked scrapers.
The bugs that matter here — slot grid mismatches, Cloudflare bypass failures,
duration filter edge cases, cache TTL races — only surface against the real
scraper pipeline. Mocking etennis_checker or eversports_service would make the
tests pass while hiding the class of failures that actually reach production.

Requires the backend to be running locally:
    npm run backend   (or: uvicorn Backend.app:app --port 8000)

Run with:
    python -m pytest Backend/test_search_api.py -v
"""

import pytest
import httpx
from datetime import date, timedelta

BASE_URL = "http://localhost:8000"

# One week out — always inside the booking window, never in the past
NEXT_WEEK = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")
SEARCH_TIME = "10:00"

# Vienna city centre — guarantees venues within a 20 km radius
VIENNA = {"lat": 48.2082, "lon": 16.3719, "radius": 20}

VALID_STATUSES = {"free", "busy", "pending", "no_slot", "other_duration", "error", "closed", "not_checked"}


@pytest.fixture(scope="module")
def client():
    try:
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
            c.get("/health")  # fail fast if backend is not running
            yield c
    except httpx.ConnectError:
        pytest.skip("Backend not running — start it with 'npm run backend'")


def _search(client, **extra):
    params = {"date": NEXT_WEEK, "time": SEARCH_TIME, "court_type": "both", **VIENNA, **extra}
    return client.get("/api/search", params=params)


# ── Happy path ─────────────────────────────────────────────────────────────────

def test_search_returns_ok(client):
    resp = _search(client)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_search_response_shape(client):
    data = _search(client).json()
    assert isinstance(data["results"], list)
    assert isinstance(data["availability_pending"], bool)
    assert isinstance(data["has_more"], bool)


def test_search_venue_fields(client):
    data = _search(client).json()
    for venue in data["results"]:
        assert "id" in venue, f"venue missing 'id': {venue}"
        assert "name" in venue, f"venue missing 'name': {venue}"
        assert "status" in venue, f"venue missing 'status': {venue}"
        assert venue["status"] in VALID_STATUSES, f"unexpected status '{venue['status']}' for venue {venue['id']}"


def test_search_vienna_returns_venues(client):
    data = _search(client).json()
    assert len(data["results"]) > 0, "Expected venues near Vienna but got none"


# ── Filtering ──────────────────────────────────────────────────────────────────

def test_indoor_filter_excludes_outdoor(client):
    data = _search(client, court_type="indoor").json()
    for venue in data["results"]:
        assert venue.get("court_type") in {"indoor", None}, (
            f"indoor-only search returned outdoor venue: {venue['name']}"
        )


def test_tiny_radius_returns_fewer_venues(client):
    wide  = _search(client, radius=50).json()["results"]
    tight = _search(client, radius=1).json()["results"]
    assert len(tight) <= len(wide), "Smaller radius should return fewer or equal venues"


def test_far_location_returns_no_venues(client):
    # Middle of the Atlantic Ocean — no padel courts there
    resp = client.get("/api/search", params={
        "date": NEXT_WEEK, "time": SEARCH_TIME,
        "lat": 0.0, "lon": -30.0, "radius": 10, "court_type": "both",
    })
    data = resp.json()
    assert data["ok"] is True
    assert data["results"] == []


# ── Validation ─────────────────────────────────────────────────────────────────

def test_past_date_is_rejected(client):
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    resp = _search(client, date=yesterday)
    assert resp.status_code == 400
    assert resp.json()["ok"] is False


def test_invalid_date_format_is_rejected(client):
    resp = _search(client, date="not-a-date")
    assert resp.status_code == 400
    assert resp.json()["ok"] is False


def test_far_future_date_is_rejected(client):
    too_far = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
    resp = _search(client, date=too_far)
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
