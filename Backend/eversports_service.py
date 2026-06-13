import asyncio
import json
import os
import re
import time as _time
from datetime import datetime
from typing import TypedDict
from urllib.parse import urlencode

from playwright.async_api import Error as PlaywrightError


class EversportsResult(TypedDict):
    status:      str   # "free" | "busy" | "platform_check_required"
    slots_count: int

from curl_cffi.requests import AsyncSession

from availability import court_free_durations
from opening_hours import DEFAULT_OPEN_MIN, DEFAULT_CLOSE_MIN

# If EVERSPORTS_SLOT_PROXY is set, use that URL instead of hitting eversports.at
# directly. Intended for the Vercel Edge Function proxy which runs on CF's own
# network and is not subject to Railway's IP block.
_SLOT_URL          = os.environ.get("EVERSPORTS_SLOT_PROXY") or "https://www.eversports.at/api/slot"
_CALENDAR_PROXY_URL: str | None = os.environ.get("EVERSPORTS_CALENDAR_PROXY")
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
# Cloudflare clearance cookie cache
# ---------------------------------------------------------------------------
# The /api/slot endpoint is protected by Cloudflare and requires a valid
# cf_clearance cookie. We obtain it once via Playwright (slow, ~45 s) and
# then reuse it for all subsequent curl_cffi calls (fast, <1 s).
# The cf_clearance cookie typically lasts ~1–2 hours; we refresh after 60 min.

_cf_cookies:    dict | None = None
_cf_cookies_ts: float       = 0.0
_cf_cookies_ttl = 3600      # seconds — refresh once per hour
_cf_lock: asyncio.Lock | None = None  # created lazily on first use inside the event loop

# If set, curl_cffi requests use this proxy (e.g. "http://user:pass@host:port").
# Lets Railway route Eversports traffic through a residential IP to bypass CF WAF.
_PROXY_URL: str | None = os.environ.get("EVERSPORTS_PROXY_URL")

# Hard CF block flag: set True when Playwright itself gets 403 (IP-level block,
# not a JS challenge). While set, skip all CF bypass attempts and fail fast.
_cf_hard_blocked: bool  = False
_cf_hard_blocked_ts: float = 0.0
_CF_HARD_BLOCK_TTL = 300  # re-probe after 5 min in case IP rotates


def _get_cf_lock() -> asyncio.Lock:
    """Return the module-level CF lock, creating it lazily on first call.

    asyncio.Lock() must be created inside a running event loop (Python ≤3.9
    binds the lock to the loop at construction time). Deferring creation to
    first use guarantees we're already inside the app's event loop.
    """
    global _cf_lock
    if _cf_lock is None:
        _cf_lock = asyncio.Lock()
    return _cf_lock


async def _refresh_cf_cookies() -> dict | None:
    """
    Launch a headless Chromium, visit www.eversports.at, solve the Cloudflare
    JS challenge, and return the resulting cookies dict.  Slow (~12–30 s).
    Skipped when a hard IP block is active (_cf_hard_blocked).
    """
    global _cf_hard_blocked, _cf_hard_blocked_ts

    from playwright.async_api import async_playwright
    t0 = _time.monotonic()
    print(json.dumps({"event": "cf_cookies_refresh_start"}))
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
                resp = await page.goto(_ES_BASE + "/", wait_until="networkidle", timeout=12_000)
                http_code = resp.status if resp else 0
                cookies = await context.cookies()
            finally:
                await browser.close()  # always close, even on timeout/exception

        # 403 from Playwright means IP-level block — JS challenge not even served.
        if http_code == 403:
            _cf_hard_blocked    = True
            _cf_hard_blocked_ts = _time.monotonic()
            print(json.dumps({
                "event":       "cf_hard_block_detected",
                "http_code":   http_code,
                "duration_ms": round((_time.monotonic() - t0) * 1000),
            }))
            return None

        cdict = {c["name"]: c["value"] for c in cookies}
        has_clearance = "cf_clearance" in cdict
        if has_clearance:
            _cf_hard_blocked = False  # recovered
        print(json.dumps({
            "event":         "cf_cookies_refresh_done",
            "has_clearance": has_clearance,
            "cookie_count":  len(cdict),
            "duration_ms":   round((_time.monotonic() - t0) * 1000),
        }))
        return cdict
    except (PlaywrightError, asyncio.TimeoutError) as exc:
        print(json.dumps({
            "event":       "cf_cookies_refresh_failed",
            "error":       f"{type(exc).__name__}: {exc}",
            "duration_ms": round((_time.monotonic() - t0) * 1000),
        }))
        return None


async def _get_cf_cookies() -> dict | None:
    """Return cached CF cookies, refreshing if stale or absent.

    Returns None immediately while a hard IP block is active (avoids launching
    a Playwright browser that will just get 403 again).  Re-probes after
    _CF_HARD_BLOCK_TTL seconds in case Railway's egress IP has rotated.
    """
    global _cf_cookies, _cf_cookies_ts
    async with _get_cf_lock():
        now = _time.monotonic()
        if _cf_hard_blocked and (now - _cf_hard_blocked_ts) < _CF_HARD_BLOCK_TTL:
            print(json.dumps({"event": "cf_hard_block_skip", "ttl_remaining_s": round(_CF_HARD_BLOCK_TTL - (now - _cf_hard_blocked_ts))}))
            return None
        if _cf_cookies and (now - _cf_cookies_ts) < _cf_cookies_ttl:
            return _cf_cookies
        cookies = await _refresh_cf_cookies()
        if cookies:
            _cf_cookies    = cookies
            _cf_cookies_ts = now
        return _cf_cookies


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dp_date(iso_date: str) -> str:
    """YYYY-MM-DD  →  DD/MM/YYYY  (Eversports datepicker format)."""
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")


def _parse_calendar_html(
    html: str, date: str, time_hhmm: str
) -> tuple[str, int, int | None, float | None] | None:
    """
    Scan raw calendar HTML for <td data-date=... data-start=... data-state=...>.
    Returns (status, matched_cell_count, min_price_eur, slot_duration_h) or None.
    price and duration are None when not present in the HTML.
    """
    all_states: list[str] = []
    matched: list[str] = []
    prices: list[int] = []
    duration_h: float | None = None
    total_cells = 0

    for m in re.finditer(r"<td\b([^>]*)>", html, re.IGNORECASE):
        attrs = m.group(1)
        d  = re.search(r'data-date="([^"]*)"',  attrs)
        s  = re.search(r'data-start="([^"]*)"', attrs)
        st = re.search(r'data-state="([^"]*)"', attrs)
        if d and s and st:
            total_cells += 1
            all_states.append(st.group(1))
            if d.group(1) == date and s.group(1) == time_hhmm:
                matched.append(st.group(1))
                p = re.search(r'data-price=["\']([^"\']*)["\']', attrs)
                if p and p.group(1).isdigit():
                    prices.append(int(p.group(1)))
                if duration_h is None:
                    e = re.search(r'data-end=["\']([^"\']*)["\']', attrs)
                    if e:
                        try:
                            start_m = int(time_hhmm[:2]) * 60 + int(time_hhmm[2:])
                            end_s   = e.group(1)
                            end_m   = int(end_s[:2]) * 60 + int(end_s[2:])
                            if end_m > start_m:
                                duration_h = (end_m - start_m) / 60.0
                        except (ValueError, IndexError):
                            pass

    min_price = min(prices) if prices else None
    print(
        f"[cal-html] total_cells={total_cells}  matched={matched}  "
        f"date={date}  time={time_hhmm}  min_price={min_price}  duration_h={duration_h}"
    )
    if not matched:
        return None
    if "free" in matched:
        return "free", len(matched), min_price, duration_h
    if all(s == "busy" for s in matched):
        return "busy", len(matched), min_price, duration_h
    return "platform_check_required", len(matched), min_price, duration_h


# ---------------------------------------------------------------------------
# Method 1: direct curl_cffi POST to /api/booking/calendar/update
# ---------------------------------------------------------------------------

async def _check_via_calendar_post(
    facility_id: int, venue_url: str, date: str, time_hhmm: str
) -> tuple[str, int, int | None, float | None] | None:
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

            print(f"[cal-post] result={result[0]}  matched_cells={result[1]}  price={result[2]}  duration_h={result[3]}")
            return result

    except Exception as e:
        print(f"[cal-post] exception: {type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# Method 1b: Vercel edge proxy for calendar HTML (Railway-safe, returns prices)
# ---------------------------------------------------------------------------

async def _check_via_calendar_proxy(
    facility_id: int, venue_url: str, date: str, time_hhmm: str
) -> tuple[str, int, int | None, float | None] | None:
    """
    Call the Vercel edge proxy (EVERSPORTS_CALENDAR_PROXY) to fetch calendar HTML.
    The proxy does the GET→POST session dance from CF's own network, bypassing
    the Cloudflare WAF block that affects Railway's egress IPs.

    Returns (status, count, min_price_eur, slot_duration_h) or None on failure.
    """
    if not _CALENDAR_PROXY_URL:
        return None

    print(f"[cal-proxy] start  facility_id={facility_id}  url={venue_url}  date={date}  time={time_hhmm}")
    try:
        async with AsyncSession(impersonate="chrome124") as session:
            r = await session.post(
                _CALENDAR_PROXY_URL,
                json={
                    "venue_url":   venue_url,
                    "facility_id": str(facility_id),
                    "date":        date,
                    "time_hhmm":   time_hhmm,
                },
                timeout=25,
            )
        print(
            f"[cal-proxy] response  status={r.status_code}"
            f"  has_td={'<td' in r.text}"
            f"  csrf_found={r.headers.get('X-CSRF-Found', '?')}"
            f"  csrf_source={r.headers.get('X-CSRF-Source', '?')}"
            f"  body[:200]={r.text[:200]!r}"
        )
        if r.status_code != 200:
            return None
        cal_html = r.text
        if not cal_html.strip() or "<td" not in cal_html:
            print("[cal-proxy] response has no <td> — empty or wrong format")
            return None
        result = _parse_calendar_html(cal_html, date, time_hhmm)
        if result is None:
            print(f"[cal-proxy] no cells matched {date}/{time_hhmm}")
            return None
        print(f"[cal-proxy] result={result[0]}  cells={result[1]}  price={result[2]}  duration_h={result[3]}")
        return result
    except Exception as e:
        print(f"[cal-proxy] exception: {type(e).__name__}: {e}")
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
                # Pass values as an argument object — never interpolate into JS strings
                trigger_result = await page.evaluate("""
                    async (args) => {
                        try {
                            const body = new URLSearchParams({
                                date:       args.dp,
                                facilityId: args.p_fid,
                                facility:   args.p_slug,
                            }).toString();
                            const headers = {
                                'Content-Type':     'application/x-www-form-urlencoded; charset=UTF-8',
                                'X-Requested-With': 'XMLHttpRequest',
                            };
                            if (args.p_csrf) headers['X-CSRF-TOKEN'] = args.p_csrf;

                            const r = await fetch('/api/booking/calendar/update', {
                                method:      'POST',
                                headers:     headers,
                                credentials: 'include',
                                body:        body,
                            });
                            const html = await r.text();

                            // Inject calendar HTML into container if we got something useful
                            const container = document.getElementById('booking-calendar-container');
                            if (container && html.includes('<td')) {
                                container.innerHTML = html;
                            }
                            return 'status:' + r.status + ' len:' + html.length +
                                   ' has_td:' + html.includes('<td') +
                                   ' excerpt:' + html.substring(0, 100);
                        } catch(e) {
                            return 'error:' + e.message;
                        }
                    }
                """, {"dp": dp, "p_fid": p_fid, "p_slug": p_slug, "p_csrf": p_csrf})
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
            resp = await page.goto(full_url, wait_until="networkidle", timeout=12_000)
            http_status = resp.status if resp else 0
            content = await page.evaluate("() => document.body.innerText")
            print(f"[playwright] HTTP {http_status}  content[:200]={content[:200]!r}")
            return http_status, content
        finally:
            await browser.close()


async def _fetch_slots(params: list[tuple]) -> tuple[int, str]:
    """
    Fetch /api/slot with Cloudflare bypass.

    Strategy (fastest first):
      1. If EVERSPORTS_PROXY_URL is set: curl_cffi through proxy (no CF cookies needed)
      2. Try curl_cffi with cached cf_clearance cookies  (fast, ~0.5 s)
      3. If blocked: invalidate inside _cf_lock, retry with freshly obtained cookies
      4. If still blocked: full Playwright page navigation
         — skipped entirely when a hard IP block is active (_cf_hard_blocked)
    """
    global _cf_cookies, _cf_cookies_ts

    # ── Strategy 1a: Vercel Edge Function proxy ──────────────────────────────
    # When _SLOT_URL has been overridden to a Vercel proxy, skip CF cookies
    # entirely — the proxy runs on CF's own network and handles auth itself.
    _is_proxied_url = _SLOT_URL != "https://www.eversports.at/api/slot"
    if _is_proxied_url:
        try:
            async with AsyncSession(impersonate="chrome124") as session:
                r = await session.get(_SLOT_URL, params=params, timeout=15)
            print(
                f"[curl_cffi+vercel-proxy] HTTP {r.status_code}  "
                f"body[:100]={r.text[:100]!r}"
            )
            if not _is_cloudflare_block(r.status_code, r.text):
                return r.status_code, r.text
            print("[curl_cffi+vercel-proxy] still CF-blocked — falling through")
        except Exception as exc:
            print(f"[curl_cffi+vercel-proxy] exception: {type(exc).__name__}: {exc} — falling through")

    # ── Strategy 1b: HTTP proxy route (bypasses CF WAF via residential IP) ──
    if _PROXY_URL:
        proxies = {"https": _PROXY_URL, "http": _PROXY_URL}
        try:
            async with AsyncSession(impersonate="chrome124") as session:
                r = await session.get(_SLOT_URL, params=params, proxies=proxies, timeout=15)
            print(
                f"[curl_cffi+proxy] HTTP {r.status_code}  "
                f"body[:100]={r.text[:100]!r}"
            )
            if not _is_cloudflare_block(r.status_code, r.text):
                return r.status_code, r.text
            print("[curl_cffi+proxy] still CF-blocked via proxy — falling through")
        except Exception as exc:
            print(f"[curl_cffi+proxy] exception: {type(exc).__name__}: {exc} — falling through")

    # ── Strategy 2+3: CF clearance cookie dance ─────────────────────────────
    # _get_cf_cookies() returns None immediately when hard IP block is active.
    cookies = await _get_cf_cookies()

    if cookies:
        async with AsyncSession(impersonate="chrome124") as session:
            r = await session.get(_SLOT_URL, params=params, cookies=cookies, timeout=10)
        print(
            f"[curl_cffi+cookies] HTTP {r.status_code}  "
            f"body[:100]={r.text[:100]!r}"
        )
        if not _is_cloudflare_block(r.status_code, r.text):
            return r.status_code, r.text

        # Invalidate inside the lock so concurrent requests don't race to reset.
        # The identity check (is cookies) ensures only the request that used the
        # stale batch clears it — a concurrent request may have already refreshed.
        async with _get_cf_lock():
            if _cf_cookies is cookies:
                _cf_cookies    = None
                _cf_cookies_ts = 0.0
                print(json.dumps({"event": "cf_cookies_invalidated", "reason": "cf_block"}))

        # One retry with freshly obtained cookies (lock serialises the refresh)
        cookies = await _get_cf_cookies()
        if cookies:
            async with AsyncSession(impersonate="chrome124") as session:
                r = await session.get(_SLOT_URL, params=params, cookies=cookies, timeout=10)
            if not _is_cloudflare_block(r.status_code, r.text):
                return r.status_code, r.text
        print(json.dumps({"event": "cf_cookies_retry_still_blocked"}))

    # ── Strategy 4: Playwright full-page navigation ──────────────────────────
    # Skipped when hard IP block is active — would just get another 403.
    if _cf_hard_blocked and (_time.monotonic() - _cf_hard_blocked_ts) < _CF_HARD_BLOCK_TTL:
        print(json.dumps({"event": "cf_playwright_fetch_skipped", "reason": "hard_block"}))
        return 403, "CF hard block — skipped Playwright fetch"

    print("[fetch-slots] falling back to Playwright page navigation")
    return await _playwright_fetch(params)


def _parse_slots(text: str) -> list | None:
    """
    Parse /api/slot JSON response.

    The API returns two formats:
      • With results:  {"slots": [{...}, ...]}          ← flat list
      • Empty results: {"slots": {"slots": [], ...}}    ← nested object

    Both are normalised to a list (possibly empty).
    Returns None only on JSON parse failure or unexpected structure.
    """
    try:
        data = json.loads(text)
        slots = data.get("slots", [])
        if isinstance(slots, list):
            return slots
        if isinstance(slots, dict):
            # Nested format: {"slots": {"slots": [...], ...}}
            inner = slots.get("slots", [])
            return inner if isinstance(inner, list) else None
        return None
    except Exception:
        return None


def _ev_free_durations(
    slots: list, date: str, court_ids: list[int],
    target_min: int, open_min: int, close_min: int,
) -> list[int]:
    """
    Bookable continuous durations (minutes) free at target_min across the given
    courts, derived from Eversports' BOOKED-slot list.

    Eversports /api/slot lists one entry per occupied grid-cell (a free cell is
    simply absent — verified against live data). Each court's grid (cell width)
    is inferred from the spacing of its OWN booked cells: 30 min only when we
    actually observe a 30-min gap, otherwise the coarser 60 min. Assuming the
    coarser grid when unsure means a booked cell is treated as covering a full
    hour, so we err toward "busy" and never report a 2 h block that is in truth
    only part-free (the original bug this feature fixes).
    """
    by_court: dict[int, set[int]] = {}
    for s in slots:
        if s.get("date") != date:
            continue
        c  = s.get("court")
        st = s.get("start")
        if c is None or not st:
            continue
        try:
            by_court.setdefault(c, set()).add(int(st[:2]) * 60 + int(st[2:]))
        except (ValueError, IndexError):
            continue

    available: set[int] = set()
    for cid in court_ids:
        booked = sorted(by_court.get(cid, set()))
        grid = 60
        for a, b in zip(booked, booked[1:]):
            if b - a == 30:
                grid = 30
                break
        busy = [(m, m + grid) for m in booked]
        available.update(court_free_durations(busy, target_min, grid, open_min, close_min))
    return sorted(available)


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
# Public API — called directly by app.py (no HTTP hop)
# ---------------------------------------------------------------------------

async def check_eversports_slot(
    facility_id: int,
    court_ids:   str,
    date:        str,
    time:        str,
    venue_url:   str = "",
    venue_id:    str = "",
    open_min:    int = DEFAULT_OPEN_MIN,
    close_min:   int = DEFAULT_CLOSE_MIN,
) -> EversportsResult:
    """
    Core Eversports availability check.  Returns {"status": ..., "slots_count": ...}.
    On the /api/slot path it also returns "free_durations": the bookable
    continuous durations (minutes) free at the requested time, bounded by the
    venue's [open_min, close_min) opening window (auto-learned; see
    opening_hours.py). Callers intersect that with the durations the user picked.
    Replaces the former /check HTTP endpoint — call directly instead of via HTTP.
    """
    time_hhmm = time.replace(":", "")

    print(json.dumps({
        "event":       "eversports_check_start",
        "venue_id":    venue_id,
        "facility_id": facility_id,
        "court_ids":   court_ids,
        "date":        date,
        "time":        time,
    }))

    t0 = _time.monotonic()

    def _log(
        status: str,
        slots_count: int,
        first_starts: list[str] | None = None,
        last_starts:  list[str] | None = None,
        max_date:     str | None       = None,
        error:        str | None       = None,
    ) -> None:
        entry: dict = {
            "event":       "eversports_check_result",
            "venue_id":    venue_id,
            "facility_id": facility_id,
            "court_ids":   court_ids,
            "date":        date,
            "time":        time,
            "status":      status,
            "slots_count": slots_count,
            "duration_ms": round((_time.monotonic() - t0) * 1000),
        }
        if first_starts is not None:
            entry["first_starts"] = first_starts
        if last_starts is not None:
            entry["last_starts"] = last_starts
        if max_date is not None:
            entry["max_date"] = max_date
        if error:
            entry["error"] = error
        print(json.dumps(entry))

    try:
        # ── Method 1a: Vercel calendar proxy — Railway-safe, returns prices ─────
        # When EVERSPORTS_CALENDAR_PROXY is set, try it first. The Vercel edge
        # function runs on CF's own network so the calendar POST is not blocked.
        # This is the preferred path on Railway because it also returns data-price.
        if venue_url and _CALENDAR_PROXY_URL:
            result = await _check_via_calendar_proxy(facility_id, venue_url, date, time_hhmm)
            if result is not None:
                status, count, price_eur, duration_h = result
                print(f"[check] cal-proxy succeeded  status={status}  count={count}  price={price_eur}")
                _log(status, count)
                return {"status": status, "slots_count": count, "price_eur": price_eur, "slot_duration_h": duration_h}
            print("[check] cal-proxy failed — falling through to /api/slot")

        # ── Method 1b: direct curl_cffi POST to /api/booking/calendar/update ──
        # Works on non-Railway IPs; blocked by Cloudflare WAF from Railway's IP.
        # Skipped when a slot proxy is configured (Railway uses /api/slot instead).
        _slot_proxied = _SLOT_URL != "https://www.eversports.at/api/slot"
        if venue_url and _slot_proxied:
            print("[check] slot proxy configured — skipping cal-post, going straight to /api/slot")
        if venue_url and not _slot_proxied:
            result = await _check_via_calendar_post(facility_id, venue_url, date, time_hhmm)
            if result is not None:
                status, count, price_eur, duration_h = result
                print(f"[check] cal-post succeeded  status={status}  count={count}  price={price_eur}")
                _log(status, count)
                return {"status": status, "slots_count": count, "price_eur": price_eur, "slot_duration_h": duration_h}
            print("[check] cal-post failed (likely Cloudflare block) — trying /api/slot")

        # ── Method 2: /api/slot — primary path on Railway ─────────────────────
        # Returns OCCUPIED slots (existing bookings per court) from startDate on.
        # Two JSON formats from the API:
        #   • {"slots":[{...},...]}          ← flat list  (has bookings)
        #   • {"slots":{"slots":[], ...}}    ← nested obj (no bookings / fully free)
        # _parse_slots handles both and returns a list (possibly empty) or None.
        #
        # Status logic (API returns BOOKED slots, not free slots):
        #   • Target time present in response          → BUSY (court is booked)
        #   • Target time absent AND scope covers      → FREE (no booking at this time)
        #   • Scope does not reach target date/time    → AMBIGUOUS → platform_check_required
        slot_status = "platform_check_required"
        slots_count = 0
        first_starts: list[str] = []
        last_starts:  list[str] = []
        scope_max_date = ""
        ev_free: list[int] = []

        params, cids = _build_params(facility_id, court_ids, date)
        http_status, text = await _fetch_slots(params)

        if http_status != 200:
            print(f"[check] /api/slot non-200: {http_status}")
            _log(slot_status, 0, error=f"http_{http_status}")
        else:
            slots = _parse_slots(text)
            if slots is None:
                print("[check] /api/slot JSON parse failed")
                _log(slot_status, 0, error="parse_error")
            else:
                slots_count = len(slots)

                # Collect first/last slot starts for structured logging
                starts_seq = [s.get("start", "") for s in slots if s.get("start")]
                first_starts = starts_seq[:3]
                last_starts  = starts_seq[-3:] if len(starts_seq) > 3 else starts_seq

                all_dates = [s.get("date", "") for s in slots if s.get("date")]
                scope_max_date = max(all_dates) if all_dates else ""

                print(json.dumps({
                    "event":        "eversports_slot_scope",
                    "venue_id":     venue_id,
                    "facility_id":  facility_id,
                    "date":         date,
                    "time":         time,
                    "slots_count":  slots_count,
                    "first_starts": first_starts,
                    "last_starts":  last_starts,
                    "max_date":     scope_max_date,
                }))

                same_day_starts = [
                    s.get("start", "") for s in slots
                    if s.get("date") == date and s.get("start")
                ]
                max_same_day_start = max(same_day_starts) if same_day_starts else ""

                # Helper: HHMM string → minutes since midnight
                def _hhmm_to_min(hhmm: str) -> int:
                    return int(hhmm[:2]) * 60 + int(hhmm[2:])

                target_min = _hhmm_to_min(time_hhmm)
                # Max booking duration we look back.  Strict window (> not >=) ensures
                # a booking that ENDS at target_min is not mis-flagged as mid-booking.
                MAX_LOOKBACK_MIN = 60

                # Courts with an explicit booking starting exactly at the target time
                booked_at_target = {
                    s.get("court") for s in slots
                    if s.get("date") == date and s.get("start") == time_hhmm
                    and s.get("court") is not None
                }

                # Courts likely mid-booking: have a recent entry strictly within
                # (target - 60 min, target).  These courts are occupied even though
                # their booking started before the target time.
                mid_booking_courts = {
                    s.get("court") for s in slots
                    if s.get("date") == date
                    and s.get("court") is not None
                    and s.get("court") not in booked_at_target
                    and s.get("start")
                    and target_min - MAX_LOOKBACK_MIN < _hhmm_to_min(s["start"]) < target_min
                }

                effectively_booked = booked_at_target | mid_booking_courts

                # Scope covers target date when:
                #   (a) bookings exist on a later date (strongest proof), or
                #   (b) a same-day booking exists after the target time
                #   (c) slots list is empty — the API returns only BOOKED slots,
                #       so an empty response with HTTP 200 means no courts are
                #       booked from startDate onwards → all courts free.
                #       This correctly handles far-future dates where no one has
                #       booked yet, instead of returning platform_check_required.
                scope_covers = scope_max_date > date or max_same_day_start > time_hhmm

                if slots_count == 0:
                    print(f"[check] empty slot list → no bookings from {date} onwards → free")
                    slot_status = "free"
                elif not scope_covers:
                    print(
                        f"[check] scope ({scope_max_date or 'empty'}) does not cover "
                        f"{date} {time_hhmm} → platform_check_required"
                    )
                    slot_status = "platform_check_required"
                elif all(cid in effectively_booked for cid in cids):
                    print(
                        f"[check] all {len(cids)} courts booked/mid-booking "
                        f"at {date} {time_hhmm} "
                        f"(at_target={len(booked_at_target)}, mid={len(mid_booking_courts)}) → busy"
                    )
                    slot_status = "busy"
                else:
                    free_count = sum(1 for cid in cids if cid not in effectively_booked)
                    print(
                        f"[check] {free_count}/{len(cids)} courts free at {date} {time_hhmm} "
                        f"(at_target={len(booked_at_target)}, mid={len(mid_booking_courts)}) → free"
                    )
                    slot_status = "free"

                # Bookable continuous durations free at the requested time,
                # bounded by opening hours (duration-aware availability).
                ev_free = _ev_free_durations(slots, date, cids, target_min, open_min, close_min)

                _log(slot_status, slots_count,
                     first_starts=first_starts, last_starts=last_starts,
                     max_date=scope_max_date)

        # ── Method 3: Playwright DOM scrape — DISABLED on Railway ─────────────
        # Cloudflare WAF blocks all AJAX POSTs from Railway's egress IPs, so
        # _check_via_playwright_dom always returns platform_check_required here
        # and wastes ~45 s.  /api/slot (Method 2) handles all cases reliably.
        # Method 3 remains available in the codebase for non-Railway deployments
        # where the booking-page AJAX is reachable.

        # Guard: grid-alignment returns [] the same as "no durations computed"
        # but the venue IS free (slot_status confirms no booking). Pass None so
        # the caller doesn't downgrade a free venue to busy on a :30 search.
        ev_free_out = None if (slot_status == "free" and not ev_free) else ev_free
        return {"status": slot_status, "slots_count": slots_count, "free_durations": ev_free_out}

    except Exception as exc:
        print(f"[check] EXCEPTION {type(exc).__name__}: {exc}")
        _log("platform_check_required", 0, error=f"{type(exc).__name__}: {exc}")
        return {"status": "platform_check_required", "slots_count": 0}


async def diag_eversports(
    facility_id: int = 79237,
    court_ids:   str = "101686,101687,101688,101689",
    date:        str = "2026-05-09",
    time:        str = "18:00",
):
    """Diagnostic endpoint: returns raw Eversports API response details."""
    params, _ = _build_params(facility_id, court_ids, date)
    time_hhmm = time.replace(":", "")

    try:
        http_status, text = await _fetch_slots(params)
        body_excerpt = text[:500]
        parse_error = None
        slots: list = []

        if http_status == 200:
            parsed = _parse_slots(text)
            if parsed is None:
                parse_error = "unsupported response structure"
            else:
                slots = parsed

        # Slots matching the requested date+time
        matching_date_time = [
            s for s in slots
            if s.get("start") == time_hhmm and s.get("date") == date
        ]
        # All slots matching the time on any date (for cross-date inspection)
        matching_time_any  = [s for s in slots if s.get("start") == time_hhmm]

        all_dates  = sorted(set(s.get("date",  "") for s in slots if s.get("date")))
        all_starts = sorted(set(s.get("start", "") for s in slots if s.get("start")))

        return {
            "http_status":        http_status,
            "body_excerpt":       body_excerpt,
            "slots_count":        len(slots),
            "time_hhmm":          time_hhmm,
            "matching_date_time": matching_date_time,
            "matching_time_any":  matching_time_any[:10],
            "all_dates":          all_dates,
            "all_starts":         all_starts,
            "parse_error":        parse_error,
            "first_5_starts":     [s.get("start") for s in slots[:5]],
        }

    except Exception as exc:
        return {
            "exception": type(exc).__name__,
            "detail":    str(exc),
        }

