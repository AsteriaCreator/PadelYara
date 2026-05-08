"""
Diagnostic: test padel4fun-tattendorf eTennis page with 5 different t= values.
Run with: python Backend/diag_etennis_t.py
"""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

VIENNA_TZ   = ZoneInfo("Europe/Vienna")
BOOKING_URL = "https://reservierung.padel4fun.at/reservierung?c=4029"
TARGET_DATE = "2026-05-08"
TARGET_HOUR = 19  # 19:00 Vienna


async def test_t_value(browser, label: str, t: int, target_ts: int) -> None:
    url  = f"{BOOKING_URL}&t={t}"
    t_human = datetime.fromtimestamp(t, tz=VIENNA_TZ).isoformat()
    print(f"\n{'='*60}")
    print(f"[t={t}]  {label}  ({t_human})")
    print(f"  url: {url}")
    page = None
    try:
        page = await browser.new_page()
        await page.goto(url, wait_until="commit", timeout=30_000)
        try:
            await page.wait_for_selector(".slot[data-begin]", state="attached", timeout=10_000)
        except Exception as e:
            print(f"  [ERROR] .slot[data-begin] not found: {e}")
            return

        result = await page.evaluate(
            """(ts) => {
                const slots   = [...document.querySelectorAll('.slot[data-begin]')];
                const first10 = slots.slice(0, 10).map(s => ({
                    begin: parseInt(s.dataset.begin),
                    size:  s.dataset.size,
                    av:    s.classList.contains('av'),
                }));
                const matching = slots.filter(s => {
                    const begin = parseInt(s.dataset.begin);
                    const size  = parseFloat(s.dataset.size || '1');
                    return begin <= ts && ts < begin + size * 3600;
                });
                return { total: slots.length, first10: first10, matchingCount: matching.length };
            }""",
            target_ts,
        )

        target_found = result["matchingCount"] > 0
        print(f"  total_slots={result['total']}  matching={result['matchingCount']}  19:00_found={'YES ✓' if target_found else 'NO ✗'}")
        print(f"  first 10 slots:")
        for i, slot in enumerate(result["first10"]):
            begin    = slot["begin"]
            dt_human = datetime.fromtimestamp(begin, tz=VIENNA_TZ).strftime("%Y-%m-%d %H:%M")
            av_flag  = "av" if slot["av"] else "  "
            print(f"    slot[{i:02d}]  begin={begin}  {dt_human}  {av_flag}")
    except Exception as exc:
        print(f"  [EXCEPTION] {type(exc).__name__}: {exc}")
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def main() -> None:
    date = datetime.strptime(TARGET_DATE, "%Y-%m-%d").date()

    target_ts      = int(datetime(date.year, date.month, date.day, TARGET_HOUR, tzinfo=VIENNA_TZ).timestamp())
    vienna_midnight = int(datetime(date.year, date.month, date.day, tzinfo=VIENNA_TZ).timestamp())
    utc_midnight    = int(datetime(date.year, date.month, date.day).timestamp())  # naive = UTC

    t_values = [
        ("Vienna midnight",     vienna_midnight),
        ("UTC midnight",        utc_midnight),
        ("target_ts (19:00)",   target_ts),
        ("target_ts - 6h",      target_ts - 6  * 3600),
        ("target_ts - 12h",     target_ts - 12 * 3600),
    ]

    print(f"Target: {TARGET_DATE} {TARGET_HOUR}:00 Vienna")
    print(f"  target_ts={target_ts}  ({datetime.fromtimestamp(target_ts, tz=VIENNA_TZ).isoformat()})")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for label, t in t_values:
                await test_t_value(browser, label, t, target_ts)
        finally:
            await browser.close()

    print(f"\n{'='*60}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
