import json as _json
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorClient

from auth import _require_admin

router = APIRouter()


@router.get("/api/analytics", dependencies=[Depends(_require_admin)])
async def get_analytics(exclude_sessions: str | None = Query(default=None), dach_only: bool = Query(default=False)):
    """Admin: search counts, top locations, and booking-click rates for today vs. yesterday."""
    from analytics import _DB_NAME, _COLLECTION
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise HTTPException(status_code=503, detail="Analytics not configured")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5_000)
    col = client[_DB_NAME][_COLLECTION]

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    hours_elapsed = int((now - today_start).total_seconds())
    yesterday_window_end = yesterday_start + timedelta(seconds=hours_elapsed)

    _ids = [s for s in (exclude_sessions or "").split(",") if s]
    # Use without None for event counts (booking_clicked has no session_id)
    _excl: dict = {"session_id": {"$nin": _ids}} if _ids else {}
    # Use with None for session/visitor counts (only count events that have a session_id)
    _excl_sess: dict = {"session_id": {"$nin": _ids + [None]}} if _ids else {}

    # Bots inflate raw traffic: they load one page and leave, almost always from a
    # non-DACH (US datacenter) country. search/booking events are already bot-free
    # (bots never engage) and booking_clicked has no country field, so when the
    # "real visitors only" filter is on we apply the DACH geo filter ONLY to the
    # pageview- and session-based numbers where the bots actually show up.
    _engaged = {"event": {"$in": ["search_completed", "booking_clicked"]}}
    _dach = {"country": {"$in": ["Austria", "Germany", "Switzerland"]}}
    _geo = _dach if dach_only else {}

    async def _session_count(start, end, extra=None):
        match = {"timestamp": {"$gte": start, "$lt": end}, "session_id": {"$exists": True, "$ne": None}, **_excl_sess, **_geo}
        if extra:
            match.update(extra)
        pipeline = [
            {"$match": match},
            {"$group": {"_id": "$session_id"}},
            {"$count": "count"},
        ]
        r = await col.aggregate(pipeline).to_list(1)
        return r[0]["count"] if r else 0

    async def _event_breakdown(start, end):
        pipeline = [
            {"$match": {"timestamp": {"$gte": start, "$lt": end}, "event": {"$ne": "pageview"}, **_excl}},
            {"$group": {"_id": "$event", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        rows = await col.aggregate(pipeline).to_list(20)
        return {r["_id"]: r["count"] for r in rows}

    _no_pv = {"event": {"$ne": "pageview"}}
    today_total      = await col.count_documents({"timestamp": {"$gte": today_start}, **_no_pv, **_excl})
    today_sessions   = await _session_count(today_start, now)
    today_engaged    = await _session_count(today_start, now, _engaged)
    today_dach       = await _session_count(today_start, now, _dach)
    today_breakdown  = await _event_breakdown(today_start, now)
    today_pageviews  = await col.count_documents({"timestamp": {"$gte": today_start}, "event": "pageview", **_excl, **_geo})
    yday_total       = await col.count_documents({"timestamp": {"$gte": yesterday_start, "$lt": yesterday_window_end}, **_no_pv, **_excl})
    yday_sessions    = await _session_count(yesterday_start, yesterday_window_end)
    yday_engaged     = await _session_count(yesterday_start, yesterday_window_end, _engaged)
    yday_breakdown   = await _event_breakdown(yesterday_start, yesterday_window_end)
    yday_pageviews   = await col.count_documents({"timestamp": {"$gte": yesterday_start, "$lt": yesterday_window_end}, "event": "pageview", **_excl, **_geo})

    returning_pipeline = [
        {"$match": {"session_id": {"$exists": True, "$ne": None}, **_excl_sess, **_geo}},
        {"$group": {"_id": "$session_id", "first_seen": {"$min": "$timestamp"}, "last_seen": {"$max": "$timestamp"}}},
        {"$match": {"first_seen": {"$lt": today_start}, "last_seen": {"$gte": today_start}}},
        {"$count": "count"},
    ]
    ret_r = await col.aggregate(returning_pipeline).to_list(1)
    returning_sessions = ret_r[0]["count"] if ret_r else 0

    avg_today_r = await col.aggregate([
        {"$match": {"timestamp": {"$gte": today_start}, "response_ms": {"$exists": True}, **_excl}},
        {"$group": {"_id": None, "avg_ms": {"$avg": "$response_ms"}}},
    ]).to_list(1)
    avg_yday_r = await col.aggregate([
        {"$match": {"timestamp": {"$gte": yesterday_start, "$lt": yesterday_window_end}, "response_ms": {"$exists": True}, **_excl}},
        {"$group": {"_id": None, "avg_ms": {"$avg": "$response_ms"}}},
    ]).to_list(1)
    avg_ms       = round(avg_today_r[0]["avg_ms"]) if avg_today_r else None
    avg_ms_yday  = round(avg_yday_r[0]["avg_ms"])  if avg_yday_r  else None

    def _delta(a, b):
        if b is None or b == 0:
            return None
        return round(((a - b) / b) * 100)

    return {
        "total_events_today":      today_total,
        "pageviews_today":         today_pageviews,
        "unique_sessions_today":   today_sessions,
        "engaged_sessions_today":  today_engaged,
        "dach_sessions_today":     today_dach,
        "returning_sessions_today": returning_sessions,
        "new_sessions_today":      today_sessions - returning_sessions,
        "avg_response_ms":         avg_ms,
        "event_breakdown_today":   today_breakdown,
        "deltas": {
            "total_events":    _delta(today_total,    yday_total),
            "pageviews":       _delta(today_pageviews, yday_pageviews),
            "unique_sessions": _delta(today_sessions, yday_sessions),
            "engaged_sessions": _delta(today_engaged, yday_engaged),
            "avg_response_ms": _delta(avg_ms, avg_ms_yday) if avg_ms and avg_ms_yday else None,
            "events_by_type":  {
                evt: _delta(today_breakdown.get(evt, 0), yday_breakdown.get(evt, 0))
                for evt in set(list(today_breakdown) + list(yday_breakdown))
            },
        },
    }


@router.get("/api/analytics/trends", dependencies=[Depends(_require_admin)])
async def get_analytics_trends(exclude_sessions: str | None = Query(default=None), dach_only: bool = Query(default=False)):
    """Admin: daily search volume for the last 7 days (sparkline data)."""
    from analytics import _DB_NAME, _COLLECTION
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise HTTPException(status_code=503, detail="Analytics not configured")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5_000)
    col = client[_DB_NAME][_COLLECTION]

    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]

    _ids = [s for s in (exclude_sessions or "").split(",") if s]
    _excl: dict = {"session_id": {"$nin": _ids}} if _ids else {}
    _excl_sess: dict = {"session_id": {"$nin": _ids + [None]}} if _ids else {}
    # DACH geo filter for the "real visitors only" toggle — applied to pageview
    # and session counts only (see get_analytics for the full rationale).
    _geo = {"country": {"$in": ["Austria", "Germany", "Switzerland"]}} if dach_only else {}

    event_rows = await col.aggregate([
        {"$match": {"timestamp": {"$gte": seven_days_ago}, "event": {"$ne": "pageview"}, **_excl}},
        {"$group": {"_id": {
            "date":  {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
            "event": "$event",
        }, "count": {"$sum": 1}}},
        {"$sort": {"_id.date": 1}},
    ]).to_list(500)

    pageview_rows = await col.aggregate([
        {"$match": {"timestamp": {"$gte": seven_days_ago}, "event": "pageview", **_excl, **_geo}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]).to_list(100)

    session_rows = await col.aggregate([
        {"$match": {"timestamp": {"$gte": seven_days_ago}, "session_id": {"$exists": True, "$ne": None}, **_excl_sess, **_geo}},
        {"$group": {"_id": {
            "date":    {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
            "session": "$session_id",
        }}},
        {"$group": {"_id": "$_id.date", "unique_sessions": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]).to_list(100)

    events_by_date: dict = {d: {} for d in dates}
    all_event_types: set = set()
    for row in event_rows:
        d, e = row["_id"]["date"], row["_id"]["event"]
        if d in events_by_date:
            events_by_date[d][e] = row["count"]
            all_event_types.add(e)

    sessions_by_date = {r["_id"]: r["unique_sessions"] for r in session_rows}
    pageviews_by_date = {r["_id"]: r["count"] for r in pageview_rows}

    return {
        "dates":                    dates,
        "event_types":              sorted(all_event_types),
        "events_by_date":           events_by_date,
        "unique_sessions_by_date":  {d: sessions_by_date.get(d, 0) for d in dates},
        "pageviews_by_date":        {d: pageviews_by_date.get(d, 0) for d in dates},
    }


@router.get("/api/analytics/insights", dependencies=[Depends(_require_admin)])
async def get_analytics_insights(exclude_sessions: str | None = Query(default=None), dach_only: bool = Query(default=False)):
    """Popular search locations, peak hours, and device breakdown — last 30 days."""
    from analytics import _DB_NAME, _COLLECTION
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise HTTPException(status_code=503, detail="Analytics not configured")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5_000)
    col = client[_DB_NAME][_COLLECTION]

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    _ids = [s for s in (exclude_sessions or "").split(",") if s]
    _excl: dict = {"session_id": {"$nin": _ids}} if _ids else {}
    base_match = {
        "event": "search_completed",
        "timestamp": {"$gte": thirty_days_ago},
        **_excl,
    }

    location_rows = await col.aggregate([
        {"$match": {**base_match, "search_location": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$search_location", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)

    hour_rows = await col.aggregate([
        {"$match": base_match},
        {"$addFields": {"hour_vienna": {"$hour": {"date": "$timestamp", "timezone": "Europe/Vienna"}}}},
        {"$group": {"_id": "$hour_vienna", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]).to_list(24)

    device_rows = await col.aggregate([
        {"$match": {**base_match, "device_type": {"$exists": True}}},
        {"$group": {"_id": "$device_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]).to_list(10)

    # "real visitors only" → restrict pageview-based breakdowns to DACH (drops US bots).
    # search/booking breakdowns above are already bot-free, so they're left unfiltered.
    _geo = {"country": {"$in": ["Austria", "Germany", "Switzerland"]}} if dach_only else {}
    pv_match = {"event": "pageview", "timestamp": {"$gte": thirty_days_ago}, **_excl, **_geo}

    referrer_rows = await col.aggregate([
        {"$match": {**pv_match, "referrer_host": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$referrer_host", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)

    page_rows = await col.aggregate([
        {"$match": {**pv_match, "path": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$path", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)

    country_rows = await col.aggregate([
        # pv_match already carries the DACH filter when dach_only; only add the
        # null/empty exclusion in the unfiltered case (avoid overriding country).
        {"$match": {**pv_match, **({} if dach_only else {"country": {"$nin": [None, ""]}})}},
        {"$group": {"_id": "$country", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 15},
    ]).to_list(15)

    venue_rows = await col.aggregate([
        {"$match": {"event": "booking_clicked", "timestamp": {"$gte": thirty_days_ago}, **_excl}},
        {"$group": {"_id": "$venue_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)

    zero_rows = await col.aggregate([
        {"$match": {"event": "search_completed", "timestamp": {"$gte": thirty_days_ago}, "results_count": 0, **_excl}},
        {"$group": {"_id": "$search_location", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)
    zero_total = await col.count_documents({
        "event": "search_completed", "timestamp": {"$gte": thirty_days_ago},
        "results_count": 0, **_excl,
    })

    searches_30d = await col.count_documents(
        {"event": "search_completed", "timestamp": {"$gte": thirty_days_ago}, **_excl}
    )
    bookings_30d = await col.count_documents(
        {"event": "booking_clicked", "timestamp": {"$gte": thirty_days_ago}, **_excl}
    )

    hours_map = {r["_id"]: r["count"] for r in hour_rows}
    hourly = [{"hour": h, "count": hours_map.get(h, 0)} for h in range(24)]

    return {
        "top_locations":         [{"location": r["_id"], "count": r["count"]} for r in location_rows],
        "hourly_searches":       hourly,
        "device_breakdown":      {r["_id"]: r["count"] for r in device_rows},
        "top_referrers":         [{"referrer": r["_id"], "count": r["count"]} for r in referrer_rows],
        "top_pages":             [{"path": r["_id"], "count": r["count"]} for r in page_rows],
        "top_countries":         [{"country": r["_id"], "count": r["count"]} for r in country_rows],
        "top_venues":            [{"venue": r["_id"], "count": r["count"]} for r in venue_rows],
        "zero_results_locations":[{"location": r["_id"] or "Ort nicht angegeben", "count": r["count"]} for r in zero_rows],
        "zero_results_total":    zero_total,
        "searches_30d":          searches_30d,
        "bookings_30d":          bookings_30d,
    }


@router.get("/api/analytics/search-console", dependencies=[Depends(_require_admin)])
async def get_search_console():
    """Fetch last 28 days of Search Console data: top queries, pages, countries."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        # Google client libs missing from the image — degrade cleanly instead of 500ing.
        return {"ok": False, "reason": "dependency_missing"}

    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return {"ok": False, "reason": "not_configured"}

    try:
        info = _json.loads(raw)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Auth error: {exc}")

    site = "https://www.padelyara.at/"

    def _query(dimensions, row_limit=10):
        body = {
            "startDate": (datetime.now(timezone.utc) - timedelta(days=28)).strftime("%Y-%m-%d"),
            "endDate":   datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "dimensions": dimensions,
            "rowLimit": row_limit,
        }
        try:
            resp = svc.searchanalytics().query(siteUrl=site, body=body).execute()
            return resp.get("rows", [])
        except Exception:
            return []

    query_rows   = _query(["query"], 15)
    page_rows    = _query(["page"], 10)
    country_rows = _query(["country"], 10)
    date_rows    = _query(["date"], 28)

    def _fmt(rows, key):
        return [
            {
                key: r["keys"][0],
                "clicks":      r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr":         round(r.get("ctr", 0) * 100, 1),
                "position":    round(r.get("position", 0), 1),
            }
            for r in rows
        ]

    return {
        "top_queries":   _fmt(query_rows, "query"),
        "top_pages":     _fmt(page_rows, "page"),
        "top_countries": _fmt(country_rows, "country"),
        "daily":         [{"date": r["keys"][0], "clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0)} for r in date_rows],
    }
