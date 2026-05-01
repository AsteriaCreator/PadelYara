"""
eTennis availability checker — production module.
Called by app.py; not a standalone server.
"""

import asyncio
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

VIENNA_TZ = ZoneInfo("Europe/Vienna")


def _page_url(booking_url: str, date) -> str:
    ts = int(datetime(date.year, date.month, date.day, tzinfo=timezone.utc).timestamp())
    return f"{booking_url}&t={ts}"


def _target_ts(date, hour: int) -> int:
    return int(datetime(date.year, date.month, date.day, hour, tzinfo=VIENNA_TZ).timestamp())


def _parse_status(html: str, target_ts: int) -> str:
    soup = BeautifulSoup(html, "html.parser")
    matching = []
    for slot in soup.select(".slot[data-begin]"):
        begin = int(slot["data-begin"])
        size  = float(slot.get("data-size") or 1)
        if begin <= target_ts < begin + size * 3600:
            matching.append(slot)

    if not matching:
        return "unknown"
    return "free" if any("av" in s.get("class", []) for s in matching) else "busy"


async def _check_one(browser, venue: dict, dt: datetime) -> tuple[str, str, str | None]:
    url       = _page_url(venue["booking_url"], dt.date())
    target_ts = _target_ts(dt.date(), dt.hour)
    page      = None
    try:
        page   = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        await page.wait_for_selector(".slot[data-begin]", timeout=15_000)
        html   = await page.content()
        status = _parse_status(html, target_ts)
        return venue["id"], status, None
    except Exception as exc:
        return venue["id"], "unknown", str(exc)
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def _run(venues: list[dict], dt: datetime) -> dict[str, str]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        # return_exceptions=True: one failing venue doesn't cancel the others
        results = await asyncio.gather(
            *[_check_one(browser, v, dt) for v in venues],
            return_exceptions=True,
        )
        await browser.close()

    out = {}
    for r in results:
        if isinstance(r, Exception):
            print(f"[eTennis] gather exception: {r}")
        else:
            venue_id, status, err = r
            if err:
                print(f"[eTennis] {venue_id} error: {err}")
            out[venue_id] = status
    return out


def check_etennis_venues(venues: list[dict], dt: datetime) -> dict[str, str]:
    """
    Returns {venue_id: "free" | "busy" | "unknown"} for every eTennis venue.
    Runs Playwright in a dedicated thread with its own event loop so it works
    safely inside Flask (avoids event-loop conflicts with werkzeug).
    """
    if not venues:
        return {}

    output: dict[str, str] = {}

    def _run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            output.update(loop.run_until_complete(_run(venues, dt)))
        except Exception as exc:
            print(f"[eTennis] thread-level error: {exc}")
        finally:
            loop.close()

    t = threading.Thread(target=_run_in_thread, daemon=True)
    t.start()
    t.join(timeout=120)

    return output
