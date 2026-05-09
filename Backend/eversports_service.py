import json
import os
from urllib.parse import urlencode

from curl_cffi.requests import AsyncSession
from fastapi import FastAPI, Query

app = FastAPI()

_SLOT_URL = "https://www.eversports.at/api/slot"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_cloudflare_block(status: int, text: str) -> bool:
    """True when Eversports replied with a Cloudflare JS challenge page."""
    return status == 403 or "Just a moment" in text[:500]


async def _playwright_fetch(params: list[tuple]) -> tuple[int, str]:
    """
    Bypass Cloudflare JS challenge via a real headless Chromium browser.
    Navigates directly to the /api/slot URL; Playwright executes the
    challenge script, obtains clearance cookies, and the final page body
    is the raw JSON response.
    """
    from playwright.async_api import async_playwright

    full_url = f"{_SLOT_URL}?{urlencode(params)}"
    print(f"[playwright] launching  url={full_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        try:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            # Remove the navigator.webdriver flag to avoid bot detection
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            # wait_until="networkidle" lets the Cloudflare challenge finish
            resp = await page.goto(full_url, wait_until="networkidle", timeout=30_000)
            http_status = resp.status if resp else 0

            # After the challenge the browser shows the raw JSON; read it as text
            content = await page.evaluate("() => document.body.innerText")
            print(f"[playwright] HTTP {http_status}  content[:200]={content[:200]!r}")
            return http_status, content
        finally:
            await browser.close()


async def _fetch_slots(params: list[tuple]) -> tuple[int, str]:
    """
    Two-layer fetch:
      1. curl_cffi with Chrome TLS impersonation (fast, ~10 ms overhead)
      2. Playwright Chromium fallback if Cloudflare blocks curl_cffi
    """
    async with AsyncSession(impersonate="chrome124") as session:
        r = await session.get(_SLOT_URL, params=params, timeout=10)

    print(f"[curl_cffi] HTTP {r.status_code}  body[:200]={r.text[:200]!r}")

    if _is_cloudflare_block(r.status_code, r.text):
        print("[curl_cffi] Cloudflare block — falling back to Playwright")
        return await _playwright_fetch(params)

    return r.status_code, r.text


def _parse_slots(text: str) -> list | None:
    """Returns the slots list from JSON text, or None on any error."""
    try:
        data = json.loads(text)
        slots = data.get("slots", [])
        return slots if isinstance(slots, list) else None
    except Exception:
        return None


def _build_params(
    facility_id: int, court_ids: str, date: str
) -> tuple[list[tuple], list[int]]:
    cids = [int(c.strip()) for c in court_ids.split(",")]
    params: list[tuple[str, int | str]] = [
        ("facilityId", facility_id),
        ("startDate", date),
    ]
    for cid in cids:
        params.append(("courts[]", cid))
    return params, cids


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/check")
async def check(
    facility_id: int = Query(...),
    court_ids: str = Query(...),
    date: str = Query(...),
    time: str = Query(...),
):
    params, cids = _build_params(facility_id, court_ids, date)
    time_hhmm = time.replace(":", "")

    print(
        f"[check] facilityId={facility_id} courts={cids} "
        f"date={date} time_hhmm={time_hhmm}"
    )

    try:
        http_status, text = await _fetch_slots(params)

        if http_status != 200:
            print(f"[check] non-200 after all layers: {http_status}")
            return {"status": "platform_check_required", "slots_count": 0}

        slots = _parse_slots(text)
        if slots is None:
            print("[check] JSON parse failed or slots not a list")
            return {"status": "platform_check_required", "slots_count": 0}

        slots_count = len(slots)
        print(f"[check] slots_count={slots_count}  first_starts={[s.get('start') for s in slots[:5]]}")

        for slot in slots:
            if slot.get("start") == time_hhmm:
                print(f"[check] MATCH at {time_hhmm}")
                return {"status": "free", "slots_count": slots_count}

        print(f"[check] no match for {time_hhmm!r}")
        return {"status": "busy", "slots_count": slots_count}

    except Exception as exc:
        print(f"[check] EXCEPTION {type(exc).__name__}: {exc}")
        return {"status": "platform_check_required", "slots_count": 0}


@app.get("/diag")
async def diag(
    facility_id: int = Query(default=79237),
    court_ids: str = Query(default="101686,101687,101688,101689"),
    date: str = Query(default="2026-05-09"),
    time: str = Query(default="18:00"),
):
    """Diagnostic endpoint: returns raw Eversports API response details."""
    params, _ = _build_params(facility_id, court_ids, date)
    time_hhmm = time.replace(":", "")

    try:
        http_status, text = await _fetch_slots(params)
        body_excerpt = text[:500]
        slots: list = []
        slots_type = "n/a"
        parse_error = None

        if http_status == 200:
            try:
                data = json.loads(text)
                raw_slots = data.get("slots", [])
                slots_type = type(raw_slots).__name__
                if isinstance(raw_slots, list):
                    slots = raw_slots
            except Exception as e:
                parse_error = str(e)

        matching = [s for s in slots if s.get("start") == time_hhmm]

        return {
            "http_status":    http_status,
            "body_excerpt":   body_excerpt,
            "slots_type":     slots_type,
            "slots_count":    len(slots),
            "time_hhmm":      time_hhmm,
            "matching_slots": matching,
            "result":         "free" if matching else ("busy" if slots else "platform_check_required"),
            "parse_error":    parse_error,
            "first_5_starts": [s.get("start") for s in slots[:5]],
        }

    except Exception as exc:
        return {
            "exception": type(exc).__name__,
            "detail":    str(exc),
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("eversports_service:app", host="0.0.0.0", port=port, reload=False)
