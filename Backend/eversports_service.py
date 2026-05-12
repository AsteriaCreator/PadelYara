import json
import os
import re
import time as _time
from datetime import datetime
from urllib.parse import urlencode

from curl_cffi.requests import AsyncSession
from fastapi import FastAPI, Query

app = FastAPI()

_SLOT_URL     = "https://www.eversports.at/api/slot"
_CAL_URL      = "https://www.eversports.at/api/booking/calendar/update"
_ES_BASE      = "https://www.eversports.at"
_PW_ARGS      = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
]
_PW_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_WEBDRIVER_INIT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dp_date(iso_date: str) -> str:
    """YYYY-MM-DD  →  DD/MM/YYYY  (Eversports datepicker format)."""
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")


def _parse_calendar_html(html: str, date: str, time_hhmm: str) -> tuple[str, int] | None:
    """
    Scan raw calendar HTML for <td data-date=... data-start=... data-state=...>.
    Returns (status, matched_cell_count) or None when no matching cells found.
    """
    all_states: list[str] = []
    matched: list[str] = []
    total_cells = 0

    for m in re.finditer(r"<td\b([^>]*)>", html, re.IGNORECASE):
        attrs = m.group(1)
        d = re.search(r'data-date="([^"]*)"',  attrs)
        s = re.search(r'data-start="([^"]*)"', attrs)
        st = re.search(r'data-state="([^"]*)"', attrs)
        if d and s and st:
            total_cells += 1
            all_states.append(st.group(1))
            if d.group(1) == date and s.group(1) == time_hhmm:
                matched.append(st.group(1))

    print(
        f"[cal-html] total_cells={total_cells}  matched={matched}  "
        f"date={date}  time={time_hhmm}"
    )
    if not matched:
        return None
    if "free" in matched:
        return "free", len(matched)
    if all(s == "busy" for s in matched):
        return "busy", len(matched)
    return "platform_check_required", len(matched)


# ---------------------------------------------------------------------------
# Method 1: direct curl_cffi POST to /api/booking/calendar/update
# ---------------------------------------------------------------------------

async def _check_via_calendar_post(
    facility_id: int, venue_url: str, date: str, time_hhmm: str
) -> tuple[str, int] | None:
    """
    Fast path: use curl_cffi (Chrome TLS fingerprint) to:
      1. GET the booking page → extract CSRF token + session cookies
      2. POST /api/booking/calendar/update with those cookies
      3. Parse the returned HTML for td[data-state]

    Returns (status, count) or None if this path failed.
    """
    facility_slug = venue_url.rstrip("/").split("/")[-1]
    dp = _dp_date(date)

    print(
        f"[cal-post] start  facility_id={facility_id}  slug={facility_slug}  "
        f"date={dp}  time={time_hhmm}"
    )

    try:
        async with AsyncSession(impersonate="chrome124") as session:
            # Step 1: GET the booking page to harvest cookies + CSRF token
            get_resp = await session.get(
                venue_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
                    "Referer": "https://www.eversports.at/",
                },
                timeout=20,
            )
            print(f"[cal-post] GET booking page  status={get_resp.status_code}")

            if get_resp.status_code != 200:
                print(f"[cal-post] GET failed with {get_resp.status_code}")
                return None

            page_html = get_resp.text

            # Extract CSRF token (Laravel/meta tag pattern)
            csrf_token = ""
            m = re.search(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)', page_html)
            if not m:
                m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']csrf-token', page_html)
            if m:
                csrf_token = m.group(1)
                print(f"[cal-post] csrf_token found (len={len(csrf_token)})")
            else:
                print("[cal-post] no csrf-token meta tag found")

            # Also try to extract facilityId from the page itself (for accuracy)
            fid_in_page = facility_id
            m2 = re.search(r"data-id=['\"](\d+)['\"]", page_html)
            if m2:
                fid_in_page = int(m2.group(1))
                print(f"[cal-post] facility_id from page={fid_in_page} (param={facility_id})")

            # Step 2: POST to calendar update endpoint
            post_headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "*/*",
                "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
                "Referer": venue_url,
                "Origin": _ES_BASE,
            }
            if csrf_token:
                post_headers["X-CSRF-TOKEN"] = csrf_token

            post_data = {
                "date":       dp,
                "facilityId": str(fid_in_page),
                "facility":   facility_slug,
            }
            print(f"[cal-post] POST  data={post_data}")

            post_resp = await session.post(
                _CAL_URL,
                data=post_data,
                headers=post_headers,
                timeout=20,
            )
            print(
                f"[cal-post] POST status={post_resp.status_code}  "
                f"body[:300]={post_resp.text[:300]!r}"
            )

            if post_resp.status_code != 200:
                return None

            cal_html = post_resp.text
            if not cal_html.strip() or "<td" not in cal_html:
                print("[cal-post] response has no <td> — empty or wrong format")
                return None

            result = _parse_calendar_html(cal_html, date, time_hhmm)
            if result is None:
                print(f"[cal-post] no cells matched {date}/{time_hhmm}")
                return None

            print(f"[cal-post] result={result[0]}  matched_cells={result[1]}")
            return result

    except Exception as e:
        print(f"[cal-post] exception: {type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# Method 2: Playwright DOM scrape (fallback when direct POST fails)
# ---------------------------------------------------------------------------

async def _check_via_playwright_dom(
    facility_id: int, venue_url: str, date: str, time_hhmm: str
) -> tuple[str, int]:
    """
    Fallback: open the booking page in headless Chromium, trigger the calendar
    AJAX manually (via vanilla JS fetch or jQuery), parse td[data-state].

    Returns (status, cell_count).
    """
    from playwright.async_api import async_playwright

    facility_slug = venue_url.rstrip("/").split("/")[-1]
    dp = _dp_date(date)
    print(f"[pw-dom] start  url={venue_url}  date={date}  time={time_hhmm}  slug={facility_slug}")

    async def _diag(page, label: str) -> None:
        try:
            current_url = page.url
            title       = await page.title()
            body_text   = await page.evaluate("() => document.body?.innerText?.substring(0, 600) || ''")
            td_count    = await page.evaluate("() => document.querySelectorAll('td').length")
            ds_count    = await page.evaluate("() => document.querySelectorAll('[data-state]').length")
            has_cf      = await page.evaluate(
                "() => (document.body?.innerText?.includes('Just a moment') || "
                "document.body?.innerText?.includes('Checking your browser')) || false"
            )
            has_cal     = await page.evaluate(
                "() => !!document.getElementById('booking-calendar-container')"
            )
            cal_html    = await page.evaluate(
                "() => document.getElementById('booking-calendar-container')?.innerHTML?.substring(0,400) || 'missing'"
            )
            csrf_meta   = await page.evaluate(
                "() => document.querySelector('meta[name=\"csrf-token\"]')?.content || 'none'"
            )
            print(json.dumps({
                "event":             "pw_dom_diag",
                "label":             label,
                "url":               current_url,
                "title":             title,
                "cloudflare":        has_cf,
                "has_cal_container": has_cal,
                "cal_inner_html_400": cal_html,
                "td_count":          td_count,
                "data_state_count":  ds_count,
                "csrf_meta":         csrf_meta,
                "body_200":          body_text[:200],
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

            # Track all /api/ calls to understand what the page fires
            _api_log: list[str] = []

            def _on_req(req):
                if "/api/" in req.url:
                    pd = (req.post_data or "")[:120]
                    _api_log.append(
                        f"REQ {req.method} {req.url.split('eversports.at')[1].split('?')[0]} post={pd!r}"
                    )

            async def _on_resp(resp):
                if "/api/" in resp.url:
                    try:
                        body = await resp.text()
                        _api_log.append(
                            f"RESP {resp.status} "
                            f"{resp.url.split('eversports.at')[1].split('?')[0]} "
                            f"body={body[:200]!r}"
                        )
                    except Exception:
                        _api_log.append(
                            f"RESP {resp.status} "
                            f"{resp.url.split('eversports.at')[1].split('?')[0]} (unreadable)"
                        )

            page.on("request",  _on_req)
            page.on("response", _on_resp)

            # ── Step 1: load the booking page ────────────────────────────
            try:
                await page.goto(venue_url, wait_until="networkidle", timeout=45_000)
                print(f"[pw-dom] goto complete  url={page.url}  api_calls={_api_log}")
            except Exception as e:
                print(f"[pw-dom] goto failed: {type(e).__name__}: {e}  api_calls={_api_log}")
                await _diag(page, "goto_failed")
                return "platform_check_required", 0

            # ── Step 2: wait for td[data-state] to appear ────────────────
            try:
                await page.wait_for_selector("td[data-state]", timeout=5_000)
                print("[pw-dom] td[data-state] appeared naturally")
            except Exception:
                # Not present — try to trigger the calendar manually
                print(
                    f"[pw-dom] td[data-state] absent after networkidle  "
                    f"api_calls_so_far={_api_log}"
                )
                await _diag(page, "before_manual_trigger")

                # Extract CSRF token and facility info from the DOM
                page_info = await page.evaluate("""
                    () => {
                        const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
                        const ct   = document.getElementById('calendar-title');
                        const fid  = ct?.dataset?.id   || ct?.getAttribute('data-id')   || '';
                        const slug = ct?.dataset?.facility || ct?.getAttribute('data-facility') || '';
                        return {csrf, fid, slug};
                    }
                """)
                print(f"[pw-dom] page_info={page_info}")

                # Prefer values extracted from page; fall back to params
                p_fid  = page_info.get("fid")  or str(facility_id)
                p_slug = page_info.get("slug") or facility_slug
                p_csrf = page_info.get("csrf") or ""

                # Trigger calendar update via vanilla JS fetch (works even without jQuery)
                trigger_result = await page.evaluate(f"""
                    async () => {{
                        try {{
                            const body = new URLSearchParams({{
                                date:       '{dp}',
                                facilityId: '{p_fid}',
                                facility:   '{p_slug}',
                            }}).toString();
                            const headers = {{
                                'Content-Type':     'application/x-www-form-urlencoded; charset=UTF-8',
                                'X-Requested-With': 'XMLHttpRequest',
                            }};
                            if ('{p_csrf}') headers['X-CSRF-TOKEN'] = '{p_csrf}';

                            const r = await fetch('/api/booking/calendar/update', {{
                                method:      'POST',
                                headers:     headers,
                                credentials: 'include',
                                body:        body,
                            }});
                            const html = await r.text();

                            // Inject calendar HTML into container if we got something useful
                            const container = document.getElementById('booking-calendar-container');
                            if (container && html.includes('<td')) {{
                                container.innerHTML = html;
                            }}
                            return 'status:' + r.status + ' len:' + html.length +
                                   ' has_td:' + html.includes('<td') +
                                   ' excerpt:' + html.substring(0, 100);
                        }} catch(e) {{
                            return 'error:' + e.message;
                        }}
                    }}
                """)
                print(f"[pw-dom] fetch trigger result={trigger_result!r}  api_calls={_api_log}")

                # Wait for td[data-state] after injection
                try:
                    await page.wait_for_selector("td[data-state]", timeout=5_000)
                    print("[pw-dom] td[data-state] appeared after fetch trigger")
                except Exception:
                    print(
                        f"[pw-dom] td[data-state] still absent after fetch trigger  "
                        f"api_calls={_api_log}"
                    )
                    await _diag(page, "td_data_state_timeout")
                    return "platform_check_required", 0

            # ── Step 3: is the target date already visible? ───────────────
            cells = await page.query_selector_all(
                f'td[data-date="{date}"][data-start="{time_hhmm}"]'
            )

            if not cells:
                # Navigate to the target date via the datepicker
                print(f"[pw-dom] date {date!r} not in view — navigating via datepicker")
                dp_el = await page.query_selector("#datepicker")
                if dp_el is None:
                    print("[pw-dom] #datepicker not found")
                    return "platform_check_required", 0

                await dp_el.triple_click()
                await dp_el.type(dp)
                await page.keyboard.press("Enter")

                try:
                    await page.wait_for_selector(
                        f'td[data-date="{date}"][data-state]', timeout=15_000
                    )
                except Exception:
                    print(f"[pw-dom] timeout after datepicker nav to {date!r}")
                    await _diag(page, "datepicker_nav_timeout")
                    return "platform_check_required", 0

                cells = await page.query_selector_all(
                    f'td[data-date="{date}"][data-start="{time_hhmm}"]'
                )

            if not cells:
                print(f"[pw-dom] no cells for date={date} start={time_hhmm} after nav")
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
            return "platform_check_required", len(states)

        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Legacy /api/slot helpers (fallback when venue_url missing)
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
        if venue_url:
            # ── Primary: direct curl_cffi POST to /api/booking/calendar/update ──
            result = await _check_via_calendar_post(facility_id, venue_url, date, time_hhmm)
            if result is not None:
                status, count = result
                print(f"[check] cal-post succeeded  status={status}  count={count}")
                _log(status, count)
                return {"status": status, "slots_count": count}

            # ── Fallback: Playwright DOM scrape ───────────────────────────────
            print("[check] cal-post failed — falling back to Playwright DOM scrape")
            status, count = await _check_via_playwright_dom(
                facility_id, venue_url, date, time_hhmm
            )
            print(f"[check] pw-dom result  status={status}  count={count}")
            _log(status, count)
            return {"status": status, "slots_count": count}

        # ── Legacy fallback: /api/slot (used only if venue_url missing) ────
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


@app.get("/debug-pw-cal")
async def debug_pw_cal(
    facility_id: int = Query(default=83836),
    venue_url:   str = Query(default="https://www.eversports.at/sb/padelzone-wiener-neustadt-or-achtersee"),
    date:        str = Query(default="2026-05-13"),
    time:        str = Query(default="18:00"),
):
    """
    Playwright diagnostic: loads the booking page, runs the manual JS fetch
    trigger, and returns everything needed to understand why td[data-state]
    is not appearing.
    """
    from playwright.async_api import async_playwright

    time_hhmm     = time.replace(":", "")
    facility_slug = venue_url.rstrip("/").split("/")[-1]
    dp            = _dp_date(date)

    result: dict = {
        "goto_ok":           False,
        "goto_url":          "",
        "api_calls":         [],
        "td_after_goto":     0,
        "ds_after_goto":     0,
        "cal_html_200":      "",
        "page_info":         {},
        "trigger_result":    "",
        "td_after_trigger":  0,
        "ds_after_trigger":  0,
        "post_body_500":     "",
    }

    try:
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

                _api_log: list[str] = []
                _post_body: list[str] = []

                def _on_req(req):
                    if "/api/" in req.url:
                        pd = (req.post_data or "")[:120]
                        _api_log.append(f"REQ {req.method} {req.url.split('eversports.at')[1].split('?')[0]} post={pd!r}")

                async def _on_resp(resp):
                    if "/api/booking/calendar" in resp.url:
                        try:
                            body = await resp.text()
                            _post_body.append(body[:500])
                            _api_log.append(f"RESP {resp.status} {resp.url.split('eversports.at')[1].split('?')[0]} body={body[:200]!r}")
                        except Exception:
                            _api_log.append(f"RESP {resp.status} unreadable")

                page.on("request",  _on_req)
                page.on("response", _on_resp)

                try:
                    await page.goto(venue_url, wait_until="networkidle", timeout=45_000)
                    result["goto_ok"]  = True
                    result["goto_url"] = page.url
                except Exception as e:
                    result["goto_ok"]  = False
                    result["goto_url"] = f"error: {e}"

                result["api_calls"]     = _api_log[:]
                result["td_after_goto"] = await page.evaluate("() => document.querySelectorAll('td[data-state]').length")
                result["ds_after_goto"] = await page.evaluate("() => document.querySelectorAll('[data-state]').length")
                result["cal_html_200"]  = await page.evaluate(
                    "() => document.getElementById('booking-calendar-container')?.innerHTML?.substring(0,200) || 'empty'"
                )

                # Extract page info
                page_info = await page.evaluate("""
                    () => {
                        const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
                        const ct   = document.getElementById('calendar-title');
                        const fid  = ct?.dataset?.id || ct?.getAttribute('data-id') || '';
                        const slug = ct?.dataset?.facility || ct?.getAttribute('data-facility') || '';
                        const calScript = Array.from(document.scripts).map(s => s.src || s.textContent.substring(0,50)).join(' | ').substring(0,300);
                        return {csrf: csrf.substring(0,20), fid, slug, scripts_hint: calScript};
                    }
                """)
                result["page_info"] = page_info

                p_fid  = page_info.get("fid")  or str(facility_id)
                p_slug = page_info.get("slug") or facility_slug
                p_csrf = page_info.get("csrf") or ""

                # Run the fetch trigger
                trigger_result = await page.evaluate(f"""
                    async () => {{
                        try {{
                            const body = new URLSearchParams({{
                                date:       '{dp}',
                                facilityId: '{p_fid}',
                                facility:   '{p_slug}',
                            }}).toString();
                            const headers = {{
                                'Content-Type':     'application/x-www-form-urlencoded; charset=UTF-8',
                                'X-Requested-With': 'XMLHttpRequest',
                            }};
                            if ('{p_csrf}') headers['X-CSRF-TOKEN'] = '{p_csrf}';
                            const r = await fetch('/api/booking/calendar/update', {{
                                method:      'POST',
                                headers:     headers,
                                credentials: 'include',
                                body:        body,
                            }});
                            const html = await r.text();
                            const container = document.getElementById('booking-calendar-container');
                            if (container && html.includes('<td')) {{
                                container.innerHTML = html;
                            }}
                            return JSON.stringify({{status: r.status, len: html.length, has_td: html.includes('<td'), excerpt: html.substring(0,200)}});
                        }} catch(e) {{
                            return 'error:' + e.message;
                        }}
                    }}
                """)
                result["trigger_result"] = trigger_result
                if _post_body:
                    result["post_body_500"] = _post_body[-1]

                # Wait briefly for DOM update then recount
                try:
                    await page.wait_for_selector("td[data-state]", timeout=5_000)
                except Exception:
                    pass

                result["td_after_trigger"] = await page.evaluate("() => document.querySelectorAll('td[data-state]').length")
                result["ds_after_trigger"] = await page.evaluate("() => document.querySelectorAll('[data-state]').length")
                result["api_calls"]        = _api_log[:]

            finally:
                await browser.close()

    except Exception as exc:
        result["exception"] = f"{type(exc).__name__}: {exc}"

    return result


@app.get("/debug-cal-post")
async def debug_cal_post(
    facility_id: int = Query(default=83836),
    venue_url:   str = Query(default="https://www.eversports.at/sb/padelzone-wiener-neustadt-or-achtersee"),
    date:        str = Query(default="2026-05-12"),
    time:        str = Query(default="20:00"),
):
    """
    Debug endpoint: shows exactly what happens during the direct cal-post check.
    Returns raw GET + POST results without scraping.
    """
    time_hhmm     = time.replace(":", "")
    facility_slug = venue_url.rstrip("/").split("/")[-1]
    dp            = _dp_date(date)

    try:
        async with AsyncSession(impersonate="chrome124") as session:
            # GET the booking page
            get_resp = await session.get(
                venue_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
                    "Referer": "https://www.eversports.at/",
                },
                timeout=20,
            )
            page_html = get_resp.text

            # Extract CSRF
            csrf_token = ""
            m = re.search(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)', page_html)
            if not m:
                m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']csrf-token', page_html)
            if m:
                csrf_token = m.group(1)

            # Extract facilityId from page
            fid_in_page = facility_id
            m2 = re.search(r"data-id=['\"](\d+)['\"]", page_html)
            if m2:
                fid_in_page = int(m2.group(1))

            # POST to calendar update
            post_headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "*/*",
                "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
                "Referer": venue_url,
                "Origin": _ES_BASE,
            }
            if csrf_token:
                post_headers["X-CSRF-TOKEN"] = csrf_token

            post_data = {
                "date":       dp,
                "facilityId": str(fid_in_page),
                "facility":   facility_slug,
            }

            post_resp = await session.post(
                _CAL_URL,
                data=post_data,
                headers=post_headers,
                timeout=20,
            )
            cal_html    = post_resp.text
            has_td      = "<td" in cal_html
            td_count    = len(re.findall(r"<td\b", cal_html, re.IGNORECASE))
            ds_count    = len(re.findall(r"data-state=", cal_html, re.IGNORECASE))

            result = _parse_calendar_html(cal_html, date, time_hhmm) if has_td else None

        return {
            "get_status":        get_resp.status_code,
            "get_body_len":      len(page_html),
            "csrf_token_found":  bool(csrf_token),
            "csrf_token_len":    len(csrf_token),
            "fid_in_page":       fid_in_page,
            "post_data":         post_data,
            "post_status":       post_resp.status_code,
            "post_body_len":     len(cal_html),
            "post_body_500":     cal_html[:500],
            "has_td":            has_td,
            "td_count":          td_count,
            "data_state_count":  ds_count,
            "parsed_result":     result,
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
