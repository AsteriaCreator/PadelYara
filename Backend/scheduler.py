import asyncio
import time

import tournaments_mongo
from padel_austria_scraper import scrape_all as scrape_padel_austria
import opening_hours
import venues_mongo
from venues_mongo import invalidate_venues_cache
import state


def _run_tournament_scrape(is_seed: bool = False) -> None:
    """Blocking scrape + upsert, intended to run in a thread.
    Upsert runs on the main event loop via run_coroutine_threadsafe to avoid
    motor being called from a different loop than the one it was created on.

    `is_seed` is True only for the initial import into an empty collection, so
    first_seen_at gets backdated instead of flagging the whole catalogue as NEU.
    """
    print(f"[mem] before daily scrape: {state.rss_mb():.0f} MB")
    print("[tournaments] Starting daily scrape...")
    tournaments = scrape_padel_austria()
    if not tournaments:
        print("[tournaments] Scrape returned 0 tournaments — skipping upsert.")
        return
    if state._main_loop is None:
        print("[tournaments] Main event loop not ready — skipping upsert.")
        return
    future = asyncio.run_coroutine_threadsafe(
        tournaments_mongo.upsert_tournaments(tournaments, is_seed=is_seed), state._main_loop
    )
    try:
        stats = future.result(timeout=120)
        print(f"[tournaments] Upsert done: {stats}")
    except Exception as exc:
        print(f"[tournaments] Upsert failed: {exc}")
        return

    # Close any tournament that disappeared from the remote list this run.
    # These are events that finished, were cancelled, or had their page removed.
    from padel_austria_scraper import SOURCE as PADEL_AUSTRIA_SOURCE
    seen_ids = [t["source_id"] for t in tournaments]
    stale_future = asyncio.run_coroutine_threadsafe(
        tournaments_mongo.mark_stale_closed(PADEL_AUSTRIA_SOURCE, seen_ids), state._main_loop
    )
    try:
        closed_count = stale_future.result(timeout=30)
        if closed_count:
            print(f"[tournaments] Marked {closed_count} disappeared tournament(s) as closed.")
    except Exception as exc:
        print(f"[tournaments] mark_stale_closed failed: {exc}")

    # Send Jagd-Alarm notifications for tournaments first seen today.
    # Skipped on is_seed runs to avoid flooding on initial import.
    if not is_seed:
        from datetime import datetime, timezone
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        alerts_future = asyncio.run_coroutine_threadsafe(
            _dispatch_alerts(today_start), state._main_loop
        )
        try:
            alerts_future.result(timeout=60)
        except Exception as exc:
            print(f"[tournaments] Jagd-Alarm dispatch failed: {exc}")

    print(f"[mem] after daily scrape: {state.rss_mb():.0f} MB")


async def _dispatch_alerts(today_start) -> None:
    """Query for tournaments first seen today, then dispatch Jagd-Alarm notifications."""
    from routers.tournament_alerts import send_alert_notifications
    from venues_mongo import _get_db
    db = _get_db()
    cursor = db["tournaments"].find(
        {"first_seen_at": {"$gte": today_start}},
        {"source_id": 1},
    )
    new_ids = [doc["source_id"] async for doc in cursor]
    if new_ids:
        print(f"[tournaments] Dispatching Jagd-Alarm for {len(new_ids)} new tournament(s).")
        await send_alert_notifications(db, new_ids)
    else:
        print("[tournaments] No new tournaments today — skipping Jagd-Alarm.")


def _run_match_cleanup() -> None:
    """Dein Match DSGVO housekeeping, intended to run in a thread: expire past
    matches, purge personal data from expired/cancelled ones after 7 days,
    delete the documents entirely after 60 days. See DeinMatch.md §5."""
    import matches_mongo
    if state._main_loop is None:
        print("[matches] Main event loop not ready — skipping cleanup.")
        return
    future = asyncio.run_coroutine_threadsafe(matches_mongo.cleanup_matches(), state._main_loop)
    try:
        stats = future.result(timeout=60)
        print(f"[matches] Cleanup done: {stats}")
    except Exception as exc:
        print(f"[matches] Cleanup failed: {exc}")


def _run_opening_hours_refresh() -> None:
    """Gemini+Google lookup of Eversports opening hours, intended to run in a
    thread. The blocking Gemini calls stay off the event loop; the Mongo writes
    go through motor on the main loop (run_coroutine_threadsafe), reusing the
    client the rest of the app uses. Reads the venue list from the in-memory
    VENUES snapshot. Invalidates the venue cache so learned hours apply live."""
    try:
        evs = [v for v in state.VENUES if v.get("platform") == "Eversports" and v.get("name")]
        print(f"[opening_hours] Refreshing hours for {len(evs)} Eversports venues...")
        if state._main_loop is None:
            print("[opening_hours] Main loop not ready — skipping.")
            return
        updated = 0
        for i, v in enumerate(evs):
            # Throttle: the Gemini free tier rate-limits (~15 req/min). Space the
            # grounded lookups ~5 s apart so the whole batch stays under the cap.
            if i > 0:
                time.sleep(5)
            hours = opening_hours.lookup_opening_hours(v["name"], v.get("address", ""))
            if not hours:
                continue
            try:
                ok = asyncio.run_coroutine_threadsafe(
                    venues_mongo.set_opening_hours(v["id"], hours), state._main_loop
                ).result(timeout=15)
                if ok:
                    updated += 1
            except Exception as exc:
                print(f"[opening_hours] write failed for {v['id']}: {exc}")
        if updated:
            invalidate_venues_cache()
        print(f"[opening_hours] Refresh done: {updated}/{len(evs)} venue(s) updated.")
    except Exception as exc:
        print(f"[opening_hours] Refresh failed: {exc}")
