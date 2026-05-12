import json
import os
import time as _time
from datetime import datetime
from urllib.parse import urlencode

from curl_cffi.requests import AsyncSession
from fastapi import FastAPI, Query

app = FastAPI()

_SLOT_URL  = "https://www.eversports.at/api/slot"
_PW_ARGS   = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
]
_PW_UA     = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_WEBDRIVER_INIT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)


# ---------------------------------------------------------------------------
# DOM-based availability check (primary method)
# ---------------------------------------------------------------------------

async def _check_via_playwright_dom(
    venue_url: str, date: str, time_hhmm: str
) -> tuple[str, int]:
    """
    Open the Eversports booking page with a real Chromium browser, navigate
    to the requested date, and read data-state from the calendar grid cells.

    Returns (status, cell_count) where status is one of:
      "free"                   — at least one court has data-state="free"
      "busy"                   — all courts are data-state="busy"
      "platform_check_required"— date/time not found or ambiguous
    """
    from playwright.async_api import async_playwright

    # Convert YYYY-MM-DD → DD/MM/YYYY for the Eversports datepicker
    dp_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")
    print(f"[pw-dom] start  url={venue_url}  date={date}  time={time_hhmm}  dp_date={dp_date}")

    async def _diag(page, label: str) -> None:
        """Log full page diagnostics to help debug why calendar didn't load."""
        try:
            current_url = page.url
            title       = await page.title()
            body_text   = await page.evaluate("() => document.body?.innerText?.substring(0, 600) || ''")
            td_count    = await page.evaluate("() => document.querySelectorAll('td').length")
            ds_count    = await page.evaluate("() => document.querySelectorAll('[data-state]').length")
            has_cf      = await page.evaluate(
                "() => document.body?.innerText?.includes('Just a moment') || "
                "document.body?.innerText?.includes('Checking your browser') || false"
            )
            has_cal     = await page.evaluate(
                "() => !!document.getElementById('booking-calendar-container')"
            )
            cal_html    = await page.evaluate(
                "() => document.getElementById('booking-calendar-container')?.innerHTML?.substring(0,200) || 'missing'"
            )
            print(json.dumps({
                "event":       "pw_dom_diag",
                "label":       label,
                "url":         current_url,
                "title":       title,
                "cloudflare":  has_cf,
                "has_cal_container": has_cal,
                "cal_inner_html_200": cal_html,
                "td_count":    td_count,
                "data_state_count": ds_count,
                "body_200":    body_text[:200],
            }))
        except Exception as e:
            print(f"[pw-dom] diag error: {e}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=_PW_ARGS)
        try:
            context = await browser.new_context(
                user_agent=_PW_UA,
                viewport={"width": 1280, "height": 800},
                locale="de-AT",
                extra_http_headers={"Accept-Language": "de-AT,de;q=0.9,en;q=0.8"},
            )
            await context.add_init_script(_WEBDRIVER_INIT)
            page = await context.new_page()

            # ── Monitor all /api/ network activity ────────────────────────
            _api_log: list[str] = []

            def _on_req(req):
                if "/api/" in req.url:
                    pd = (req.post_data or "")[:120]
                    _api_log.append(f"REQ {req.method} {req.url.split('eversports.at')[1].split('?')[0]} post={pd!r}")

            async def _on_resp(resp):
                if "/api/" in resp.url:
                    try:
                        body = await resp.text()
                        _api_log.append(f"RESP {resp.status} {resp.url.split('eversports.at')[1].split('?')[0]} body={body[:120]!r}")
                    except Exception:
                        _api_log.append(f"RESP {resp.status} {resp.url.split('eversports.at')[1].split('?')[0]} (unreadable)")

            page.on("request",  _on_req)
            page.on("response", _on_resp)

            # ── Step 1: load the booking page ────────────────────────────
            # "networkidle" lets the Cloudflare JS challenge resolve AND
            # waits for the AJAX that populates the booking calendar grid
            # (POST /api/booking/calendar/update) to complete.
            try:
                await page.goto(venue_url, wait_until="networkidle", timeout=45_000)
                print(f"[pw-dom] goto complete  url={page.url}  api_calls={_api_log}")
            except Exception as e:
                print(f"[pw-dom] goto failed: {type(e).__name__}: {e}  api_calls={_api_log}")
                await _diag(page, "goto_failed")
                return "platform_check_required", 0

            # ── Step 2: confirm the calendar grid populated ───────────────
            # If not yet present, try manually triggering the calendar init
            # by executing the page's own initCalendar/update logic via JS.
            try:
                await page.wait_for_selector("td[data-state]", timeout=5_000)
            except Exception:
                # Calendar didn't auto-populate — try to trigger it manually
                print(f"[pw-dom] td[data-state] not present — trying manual trigger  api_calls_so_far={_api_log}")
                cal_data = await page.evaluate("""
                    () => {
                        const ct = document.getElementById('calendar-title');
                        if (!ct) return {error: 'no calendar-title'};
                        const attrs = {};
                        for (const a of ct.attributes) attrs[a.name] = a.value;
                        return attrs;
                    }
                """)
                print(f"[pw-dom] calendar-title attrs={cal_data}")

                # Try to trigger the calendar AJAX via jQuery (if loaded)
                trigger_result = await page.evaluate("""
                    () => new Promise((resolve) => {
                        if (typeof $ === 'undefined') { resolve('no jQuery'); return; }
                        const ct = $('#calendar-title');
                        const fid = ct.data('id');
                        const slug = ct.data('facility');
                        if (!fid) { resolve('no facilityId'); return; }
                        // Try the datepicker-triggered update (uses today's date)
                        const today = new Date();
                        const dd = String(today.getDate()).padStart(2,'0');
                        const mm = String(today.getMonth()+1).padStart(2,'0');
                        const yyyy = today.getFullYear();
                        $.ajax({
                            url: '/api/booking/calendar/update',
                            type: 'POST',
                            data: {date: dd+'/'+mm+'/'+yyyy, facilityId: fid, facility: slug},
                            success: function(html) { resolve('ok:'+html.substring(0,100)); },
                            error:   function(xhr)  { resolve('err:'+xhr.status+':'+xhr.responseText.substring(0,100)); }
                        });
                        setTimeout(() => resolve('timeout'), 10000);
                    })
                """)
                print(f"[pw-dom] manual trigger result={trigger_result!r}")

                # Wait again after manual trigger
                try:
                    await page.wait_for_selector("td[data-state]", timeout=8_000)
                except Exception:
                    print(f"[pw-dom] td[data-state] still absent after manual trigger  api_calls={_api_log}")
                    await _diag(page, "td_data_state_timeout")
                    return "platform_check_required", 0

            # ── Step 3: check whether the target date is already visible ──
            cells = await page.query_selector_all(
                f'td[data-date="{date}"][data-start="{time_hhmm}"]'
            )

            if not cells:
                # Navigate to the target date via the datepicker
                print(f"[pw-dom] date {date!r} not in current view — navigating via datepicker")
                dp = await page.query_selector("#datepicker")
                if dp is None:
                    print("[pw-dom] datepicker element not found")
                    return "platform_check_required", 0

                await dp.triple_click()
                await dp.type(dp_date)
                await page.keyboard.press("Enter")

                try:
                    await page.wait_for_selector(
                        f'td[data-date="{date}"][data-state]', timeout=15_000
                    )
                except Exception:
                    print(f"[pw-dom] timeout after datepicker navigation to {date!r}")
                    await _diag(page, "datepicker_nav_timeout")
                    return "platform_check_required", 0

                cells = await page.query_selector_all(
                    f'td[data-date="{date}"][data-start="{time_hhmm}"]'
                )

            if not cells:
                print(f"[pw-dom] no cells for date={date} start={time_hhmm} after navigation")
                return "platform_check_required", 0

            # ── Step 4: collect data-state values ─────────────────────────
            states = []
            for cell in cells:
                state = await cell.get_attribute("data-state")
                if state:
                    states.append(state)

            print(f"[pw-dom] found {len(cells)} cells  states={states}")

            if "free" in states:
                return "free", len(states)
            if states and all(s == "busy" for s in states):
                return "busy", len(states)
            # Unexpected states (e.g. empty, "reserved", etc.)
            return "platform_check_required", len(states)

        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Legacy /api/slot helpers (fallback when venue_url is not supplied)
# ---------------------------------------------------------------------------

def _is_cloudflare_block(status: int, text: str) -> bool:
    return status == 403 or "Just a moment" in text[:500]


async def _playwright_fetch(params: list[tuple]) -> tuple[int, str]:
    """Bypass Cloudflare JS challenge for the /api/slot endpoint."""
    from playwright.async_api import async_playwright

    full_url = f"{_SLOT_URL}?{urlencode(params)}"
    print(f"[playwright] launching  url={full_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=_PW_ARGS)
        try:
            context = await browser.new_context(user_agent=_PW_UA)
            await context.add_init_script(_WEBDRIVER_INIT)
            page = await context.new_page()
            resp = await page.goto(full_url, wait_until="networkidle", timeout=30_000)
            http_status = resp.status if resp else 0
            content = await page.evaluate("() => document.body.innerText")
            print(f"[playwright] HTTP {http_status}  content[:200]={content[:200]!r}")
            return http_status, content
        finally:
            await browser.close()


async def _fetch_slots(params: list[tuple]) -> tuple[int, str]:
    async with AsyncSession(impersonate="chrome124") as session:
        r = await session.get(_SLOT_URL, params=params, timeout=10)
    print(f"[curl_cffi] HTTP {r.status_code}  body[:200]={r.text[:200]!r}")
    if _is_cloudflare_block(r.status_code, r.text):
        print("[curl_cffi] Cloudflare block — falling back to Playwright")
        return await _playwright_fetch(params)
    return r.status_code, r.text


def _parse_slots(text: str) -> list | None:
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

@app.get("/health")
async def health():
    return {"ok": True, "service": "eversports-service"}


@app.get("/check")
async def check(
    facility_id: int = Query(...),
    court_ids:   str = Query(...),
    date:        str = Query(...),
    time:        str = Query(...),
    venue_url:   str = Query(default=""),
):
    time_hhmm = time.replace(":", "")

    print(
        f"[check] facilityId={facility_id} courts={court_ids} "
        f"date={date} time_hhmm={time_hhmm} "
        f"venue_url={venue_url!r}"
    )

    t0 = _time.monotonic()

    def _log(status: str, slots_count: int, error: str | None = None) -> None:
        entry: dict = {
            "event":       "railway_check_result",
            "facility_id": facility_id,
            "date":        date,
            "time":        time,
            "status":      status,
            "slots_count": slots_count,
            "duration_ms": round((_time.monotonic() - t0) * 1000),
        }
        if error:
            entry["error"] = error
        print(json.dumps(entry))

    try:
        # ── Primary path: DOM scraping via booking page ───────────────────
        if venue_url:
            status, count = await _check_via_playwright_dom(venue_url, date, time_hhmm)
            _log(status, count)
            return {"status": status, "slots_count": count}

        # ── Legacy fallback: /api/slot (used only if venue_url missing) ───
        params, cids = _build_params(facility_id, court_ids, date)
        http_status, text = await _fetch_slots(params)

        if http_status != 200:
            print(f"[check] non-200 after all layers: {http_status}")
            _log("platform_check_required", 0, error=f"http_{http_status}")
            return {"status": "platform_check_required", "slots_count": 0}

        slots = _parse_slots(text)
        if slots is None:
            print("[check] JSON parse failed or slots not a list")
            _log("platform_check_required", 0, error="parse_error")
            return {"status": "platform_check_required", "slots_count": 0}

        slots_count = len(slots)
        first_dates = [f"{s.get('date')}T{s.get('start')}" for s in slots[:5]]
        print(f"[check] slots_count={slots_count}  first_slots={first_dates}")

        if any(s.get("start") == time_hhmm and s.get("date") == date for s in slots):
            print(f"[check] MATCH at {date} {time_hhmm} — free")
            _log("free", slots_count)
            return {"status": "free", "slots_count": slots_count}

        if any(s.get("start") == time_hhmm for s in slots):
            print(f"[check] {time_hhmm} offered but not on {date!r} — busy")
            _log("busy", slots_count)
            return {"status": "busy", "slots_count": slots_count}

        print(f"[check] {time_hhmm!r} not offered at facilityId={facility_id} — platform_check_required")
        _log("platform_check_required", slots_count, error="time_not_offered")
        return {"status": "platform_check_required", "slots_count": slots_count}

    except Exception as exc:
        print(f"[check] EXCEPTION {type(exc).__name__}: {exc}")
        _log("platform_check_required", 0, error=f"{type(exc).__name__}: {exc}")
        return {"status": "platform_check_required", "slots_count": 0}


@app.get("/diag")
async def diag(
    facility_id: int = Query(default=79237),
    court_ids:   str = Query(default="101686,101687,101688,101689"),
    date:        str = Query(default="2026-05-09"),
    time:        str = Query(default="18:00"),
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
