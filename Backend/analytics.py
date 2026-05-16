"""
DSGVO-friendly product telemetry.

Architecture: asyncio.Queue + single worker task on the FastAPI event loop.

  Track functions are sync — callable from any thread (route handlers,
  scraper threads). _enqueue() uses call_soon_threadsafe() for a zero-copy
  hand-off to the event loop. One motor client is shared for all writes;
  no thread or connection is created per event.

  Lifecycle:
    lifespan_startup() must be awaited inside the FastAPI lifespan context
    manager before requests are served. It initialises the queue, starts the
    worker task, and creates MongoDB indexes. Until it runs, all track_*
    calls are silent no-ops.

  DSGVO constraints enforced here:
    - No cookies, no fingerprints, no user IDs
    - No exact coordinates or IPs
    - Only product telemetry (search outcomes, booking intent, scraper failures)
    - Analytics write failures are swallowed — never propagate to API responses
"""
import asyncio
import json
import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

_DB_NAME = "padel_checker"
_COLLECTION = "analytics_events"

# Set by lifespan_startup(). Both are None until then → _enqueue is a no-op.
_queue: asyncio.Queue | None = None
_loop: asyncio.AbstractEventLoop | None = None


# ── Internal dispatcher ───────────────────────────────────────────────────────

def _enqueue(doc: dict) -> None:
    """
    Thread-safe, non-blocking hand-off to the event loop queue.

    Safe to call from any thread, including FastAPI's sync route threadpool
    and Playwright daemon threads. call_soon_threadsafe() schedules
    queue.put_nowait on the running event loop without blocking the caller.
    """
    if _queue is None or _loop is None:
        return
    doc["timestamp"] = datetime.now(timezone.utc)
    try:
        _loop.call_soon_threadsafe(_queue.put_nowait, doc)
    except Exception:
        pass


async def _worker(col) -> None:
    """
    Single async consumer. Runs for the lifetime of the process on the FastAPI
    event loop. Drains the queue and persists each document to MongoDB.
    Errors are logged and swallowed so the worker never dies.
    """
    while True:
        doc = await _queue.get()
        try:
            await col.insert_one(doc)
            print(json.dumps({
                "event":           "analytics_written",
                "analytics_event": doc["event"],
            }))
        except Exception as exc:
            print(json.dumps({
                "event": "analytics_write_error",
                "error": f"{type(exc).__name__}: {exc}",
            }))
        finally:
            _queue.task_done()


# ── Startup ───────────────────────────────────────────────────────────────────

async def lifespan_startup() -> None:
    """
    Initialise the analytics subsystem. Must be awaited inside the FastAPI
    lifespan context manager (before yield), so it runs on the same event loop
    that will later process requests.

    Silently skips everything when MONGODB_URI is absent.
    """
    global _queue, _loop
    _loop = asyncio.get_running_loop()

    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        print(json.dumps({"event": "analytics_disabled", "reason": "MONGODB_URI not set"}))
        return

    _queue = asyncio.Queue()
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5_000)
    col = client[_DB_NAME][_COLLECTION]

    await col.create_index("timestamp")
    await col.create_index("event")
    print(json.dumps({"event": "analytics_indexes_ready"}))

    asyncio.create_task(_worker(col), name="analytics_worker")
    print(json.dumps({"event": "analytics_worker_started"}))


# ── Public tracking helpers ───────────────────────────────────────────────────

def track_search_completed(
    *,
    radius: float | None,
    court_type: str | None,
    results_count: int,
    response_ms: int,
) -> None:
    """
    Fired after /api/search returns results successfully.

    Stored (no coordinates, no IPs):
      radius        — search radius in km (lat/lon/radius mode), else None
      court_type    — "indoor" | "outdoor" | "all" | None
      results_count — number of venues returned
      response_ms   — wall-clock time from request entry to response build
    """
    _enqueue({
        "event":         "search_completed",
        "radius":        radius,
        "court_type":    court_type,
        "results_count": results_count,
        "response_ms":   response_ms,
    })


def track_booking_clicked(*, venue_id: str, platform: str) -> None:
    """
    Fired on POST /api/booking-click (booking intent signal from the frontend).

    Stored:
      venue_id — venue slug (e.g. "padelzone-traiskirchen")
      platform — "eTennis" | "Eversports" | "Andere"
    """
    _enqueue({
        "event":    "booking_clicked",
        "venue_id": venue_id,
        "platform": platform,
    })


def track_scraper_timeout(*, venue_id: str, platform: str, timeout_ms: int) -> None:
    """
    Fired when a scraper or downstream service call exceeds its timeout.

    Stored:
      venue_id   — venue slug
      platform   — "eTennis" | "Eversports"
      timeout_ms — configured or elapsed timeout in milliseconds
    """
    _enqueue({
        "event":      "scraper_timeout",
        "venue_id":   venue_id,
        "platform":   platform,
        "timeout_ms": timeout_ms,
    })


def track_search_failed(*, reason: str, court_type: str | None = None) -> None:
    """
    Fired when /api/search cannot process the request (bad params, etc.).

    Stored:
      reason     — machine-readable label (e.g. "invalid_datetime")
      court_type — value passed in, for debugging
    """
    _enqueue({
        "event":      "search_failed",
        "reason":     reason,
        "court_type": court_type,
    })


# ── Aggregation reference (future admin dashboard) ────────────────────────────
#
# Collection: analytics_events
# Indexes:    timestamp (range), event (point lookup)
#
# searches_today
#   db.analytics_events.countDocuments({
#       event: "search_completed",
#       timestamp: { $gte: <today_00:00_UTC>, $lt: <tomorrow_00:00_UTC> }
#   })
#
# booking_clicks_today
#   db.analytics_events.countDocuments({
#       event: "booking_clicked",
#       timestamp: { $gte: <today_00:00_UTC>, $lt: <tomorrow_00:00_UTC> }
#   })
#
# avg_response_ms  (last 24 h)
#   db.analytics_events.aggregate([
#       { $match: { event: "search_completed",
#                   timestamp: { $gte: <24h_ago> } } },
#       { $group: { _id: null, avg_ms: { $avg: "$response_ms" } } }
#   ])
#
# timeout_rate_per_platform  (last 7 days)
#   db.analytics_events.aggregate([
#       { $match: { event: "scraper_timeout",
#                   timestamp: { $gte: <7d_ago> } } },
#       { $group: { _id: "$platform", timeouts: { $sum: 1 } } }
#   ])
