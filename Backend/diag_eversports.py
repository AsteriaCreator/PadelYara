"""
Diagnostic script: Eversports anonymous session for Padelzone Traiskirchen.

Opens the booking page exactly as a real anonymous browser would, then captures:
  - all /api/ network requests (URL, status, size)
  - HTML snapshots at multiple wait points
  - screenshot of the rendered timetable
  - parsed <td> slots at 17:00, 18:00, 19:00

Usage (from Backend/):
    python diag_eversports.py

Outputs written to Backend/diag_output/:
  - 01_html_after_load.html       -- DOM right after page load
  - 02_html_after_networkidle.html -- DOM after networkidle
  - 03_html_after_extra_wait.html -- DOM after 10 s extra wait
  - 04_calendar_responses/        -- each /api/booking/calendar/update body
  - screenshot_timetable.png      -- visible page at end
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

TARGET_URL  = "https://www.eversports.at/sb/padelzone-traiskirchen"
TARGET_DATE = "2026-05-04"
TARGET_HOURS = [17, 18, 19]
OUT_DIR = Path(__file__).parent / "diag_output"
OUT_DIR.mkdir(exist_ok=True)
(OUT_DIR / "04_calendar_responses").mkdir(exist_ok=True)


def _parse_slots(html: str, label: str):
    soup = BeautifulSoup(html, "html.parser")
    tds = soup.find_all(
        "td",
        attrs={"data-state": True, "data-start": True, "data-date": True, "data-court": True},
    )
    print(f"\n[{label}] Total slot <td> elements: {len(tds)}")

    for h in TARGET_HOURS:
        target_start = f"{h:02d}00"
        matching = [td for td in tds
                    if td.get("data-date") == TARGET_DATE
                    and td.get("data-start") == target_start]
        print(f"  {h:02d}:00 ({TARGET_DATE} start={target_start}) -> {len(matching)} matching tds:")
        for td in matching:
            print(
                f"    court={td.get('data-court')}"
                f"  state={td.get('data-state')}"
                f"  end={td.get('data-end')}"
                f"  title={td.get('data-original-title')!r}"
            )
        if not matching:
            # Show what dates/starts are present for context
            dates = sorted({td.get("data-date") for td in tds})
            starts_today = sorted({td.get("data-start") for td in tds
                                    if td.get("data-date") == TARGET_DATE})
            print(f"    (no match — dates in HTML: {dates[:5]}{'...' if len(dates)>5 else ''})")
            print(f"    (starts for {TARGET_DATE}: {starts_today[:10]}{'...' if len(starts_today)>10 else ''})")


async def _accept_cookies(page) -> bool:
    selectors = [
        "button:has-text('Auswahl erlauben')",
        "button:has-text('Alle akzeptieren')",
        "button:has-text('Akzeptieren')",
        "button:has-text('Accept')",
    ]
    for _ in range(20):
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=400):
                    await btn.click(timeout=2_000)
                    print(f"  [cookies] clicked: {sel}")
                    return True
            except Exception:
                pass
        await asyncio.sleep(0.5)
    return False


async def main():
    url = f"{TARGET_URL}?date={TARGET_DATE}"
    print(f"Target URL: {url}")
    print(f"Target date: {TARGET_DATE}")
    print(f"Target hours: {TARGET_HOURS}")
    print(f"Output dir: {OUT_DIR}\n")

    calendar_responses: list[tuple[str, int, str]] = []  # (url, index, body)
    all_api_calls: list[tuple[float, str, int, int]] = []  # (t, url, status, size)
    t0 = time.time()

    async with async_playwright() as pw:
        browser = None
        for channel in ("chrome", "msedge", None):
            try:
                kwargs = {
                    "headless": False,
                    "args": ["--disable-blink-features=AutomationControlled"],
                }
                if channel:
                    kwargs["channel"] = channel
                browser = await pw.chromium.launch(**kwargs)
                print(f"Browser launched: {channel or 'playwright-chromium'}")
                break
            except Exception as e:
                print(f"  channel={channel} failed: {e}")

        if browser is None:
            print("ERROR: no browser available")
            return

        ctx = await browser.new_context(
            locale="de-AT",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            extra_http_headers={"Accept-Language": "de-AT,de;q=0.9,en;q=0.8"},
            viewport={"width": 1400, "height": 900},
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await ctx.new_page()

        async def on_response(resp):
            elapsed = time.time() - t0
            size = 0
            try:
                body = await resp.body()
                size = len(body)
            except Exception:
                pass

            if "/api/" in resp.url:
                all_api_calls.append((elapsed, resp.url, resp.status, size))
                print(f"  [{elapsed:6.1f}s] API {resp.status} {size:>8} bytes  {resp.url[:120]}")

            if "/api/booking/calendar/update" in resp.url and resp.status == 200:
                try:
                    text = await resp.text()
                    idx = len(calendar_responses)
                    calendar_responses.append((resp.url, idx, text))
                    path = OUT_DIR / "04_calendar_responses" / f"cal_{idx:02d}_{int(elapsed*10):04d}ms.html"
                    path.write_text(text, encoding="utf-8")
                    print(f"  [{elapsed:6.1f}s] *** CALENDAR UPDATE #{idx} saved -> {path.name} ({len(text)} bytes)")
                except Exception as ex:
                    print(f"  [{elapsed:6.1f}s] *** CALENDAR UPDATE (failed to read body: {ex})")

        page.on("response", on_response)

        # ── Step 1: navigate ──────────────────────────────────────────────
        print(f"\n=== Step 1: goto {url} ===")
        try:
            await page.goto(url, wait_until="load", timeout=45_000)
        except Exception as ex:
            print(f"  load raised: {ex} (continuing anyway)")

        print(f"  Current URL: {page.url}")

        html_after_load = await page.content()
        (OUT_DIR / "01_html_after_load.html").write_text(html_after_load, encoding="utf-8")
        print(f"  Saved 01_html_after_load.html ({len(html_after_load)} bytes)")
        _parse_slots(html_after_load, "AFTER_LOAD")

        # ── Step 2: accept cookies ────────────────────────────────────────
        print(f"\n=== Step 2: accept cookies ===")
        clicked = await _accept_cookies(page)
        print(f"  Cookies clicked: {clicked}")
        if clicked:
            print("  Waiting 3s after cookie click...")
            await asyncio.sleep(3)

        # ── Step 3: wait for network idle ─────────────────────────────────
        print(f"\n=== Step 3: wait for networkidle ===")
        try:
            await page.wait_for_load_state("networkidle", timeout=20_000)
            print("  networkidle reached")
        except Exception as ex:
            print(f"  networkidle timed out: {ex}")

        print(f"  Current URL: {page.url}")
        html_after_idle = await page.content()
        (OUT_DIR / "02_html_after_networkidle.html").write_text(html_after_idle, encoding="utf-8")
        print(f"  Saved 02_html_after_networkidle.html ({len(html_after_idle)} bytes)")
        _parse_slots(html_after_idle, "AFTER_NETWORKIDLE")

        # ── Step 4: look for and click the correct date in calendar ───────
        print(f"\n=== Step 4: find date selector for {TARGET_DATE} ===")
        # Try to find a clickable element for the target date
        date_selectors = [
            f"[data-date='{TARGET_DATE}']",
            f"td[data-date='{TARGET_DATE}']",
            f"a[data-date='{TARGET_DATE}']",
            f"button[data-date='{TARGET_DATE}']",
            f"[data-value='{TARGET_DATE}']",
            # Day number 4 in the date picker
            f"td:has-text('4')",
        ]
        date_clicked = False
        for sel in date_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1_000):
                    print(f"  Found date element: {sel}")
                    await el.click(timeout=3_000)
                    date_clicked = True
                    print(f"  Clicked date element: {sel}")
                    break
            except Exception:
                pass

        if not date_clicked:
            print(f"  No date selector found/clicked — date may already be selected via URL param")

        if date_clicked:
            await asyncio.sleep(3)
            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass

        # ── Step 5: extra wait ────────────────────────────────────────────
        print(f"\n=== Step 5: extra 10s wait for any deferred JS ===")
        await asyncio.sleep(10)

        print(f"  Current URL: {page.url}")
        html_after_wait = await page.content()
        (OUT_DIR / "03_html_after_extra_wait.html").write_text(html_after_wait, encoding="utf-8")
        print(f"  Saved 03_html_after_extra_wait.html ({len(html_after_wait)} bytes)")
        _parse_slots(html_after_wait, "AFTER_EXTRA_WAIT")

        # ── Step 6: try JS updateCalendar trigger ─────────────────────────
        print(f"\n=== Step 6: JS updateCalendar trigger ===")
        before_count = len(calendar_responses)
        try:
            await page.evaluate(
                "() => { if (typeof updateCalendar === 'function') { updateCalendar(); return 'called'; } return 'not_found'; }"
            )
            await asyncio.sleep(5)
            print(f"  Calendar responses before: {before_count}, after: {len(calendar_responses)}")
        except Exception as ex:
            print(f"  JS trigger error: {ex}")

        # ── Step 7: screenshot ────────────────────────────────────────────
        print(f"\n=== Step 7: screenshot ===")
        ss_path = OUT_DIR / "screenshot_timetable.png"
        await page.screenshot(path=str(ss_path), full_page=False)
        print(f"  Saved {ss_path}")

        # ── Step 8: final HTML with most slots ────────────────────────────
        print(f"\n=== Step 8: final DOM parse ===")
        html_final = await page.content()
        _parse_slots(html_final, "FINAL_DOM")

        # ── Summary ───────────────────────────────────────────────────────
        print(f"\n{'='*60}")
        print("API CALLS SUMMARY")
        print(f"{'='*60}")
        for t, u, s, sz in all_api_calls:
            print(f"  [{t:6.1f}s] {s} {sz:>8}b  {u[:110]}")

        print(f"\n{'='*60}")
        print(f"CALENDAR RESPONSES CAPTURED: {len(calendar_responses)}")
        print(f"{'='*60}")
        for u, i, body in calendar_responses:
            soup = BeautifulSoup(body, "html.parser")
            tds = soup.find_all("td", attrs={"data-state": True, "data-start": True})
            states = {}
            for td in tds:
                st = td.get("data-state", "?")
                states[st] = states.get(st, 0) + 1
            print(f"  #{i}: {len(tds)} slot tds, states={states}")
            print(f"       url={u[:100]}")

        print(f"\nDone. Check {OUT_DIR} for saved files.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
