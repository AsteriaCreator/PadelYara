# Scrapers

**Last cross-scraper parity check: 2026-07-08.** Verified eTennis, Eversports, and tennis04 all implement the same `status` (`free`/`busy`/`no_slot`/`unknown`) + `free_durations`/`fallback_durations` model consistently — no drift found. Known, tracked (not a bug): venue-info enrichment (photos, parking, klimaanlage, cancellation policy) only covers Padelzone-sourced venues so far; eTennis/tennis04 venues don't have an equivalent enrichment scraper yet. Re-check parity here whenever a scraper gets a new feature or bugfix — see the scraper consistency rule in `CLAUDE.md`.

## Purpose

PadelYara depends on two fundamentally different scraping systems:

- eTennis
- Eversports

These systems have different constraints, infrastructure requirements, and failure modes.

They should remain operationally and architecturally separated.

---

# eTennis

## Current Strategy

eTennis runs directly on Railway (the single backend service).

Implementation:
- Playwright-based scraper
- shared browser per batch
- controlled concurrency
- aggressive early exit logic
- pending-first architecture

Main file:
- `Backend/etennis_checker.py`

---

## Current Performance Model

Goals:
- very fast initial API response
- stable Railway RAM usage
- avoid browser explosion
- reliable final status resolution

Current implementation:
- one shared browser
- semaphore-controlled concurrency
- currently ~2 parallel venue checks
- page-per-venue
- reduced timeout values
- structured timing logs

---

## Important Constraints

Railway limits:
- Chromium instances are expensive in memory
- excessive parallelism can destabilize the deployment

Important:
Final slot resolution speed matters more than the initial pending response.

---

## Important Behaviors

### Pending-first model

The backend should return quickly with:
- cached results
- pending statuses

Final resolution happens separately.

Do not block the API waiting for all venues.

---

### Duplicate-run prevention

Current protection:
- `_RUNNING` guard

Purpose:
Prevent multiple overlapping Playwright batches for identical searches.

This protection is critical.

Do not remove casually.

---

### Cache and cooldown behavior

Current system includes:
- cache reuse
- cooldown periods for failed/unknown checks

Purpose:
- reduce scraper load
- stabilize production
- avoid repeated expensive retries

---

## Known Fragile Areas

Potential instability sources:
- selector changes
- slow venue pages
- Playwright hangs
- overlapping browser launches
- timeout tuning
- aggressive concurrency increases

---

## Optimization Philosophy

Do:
- optimize incrementally
- reuse working logic
- measure timings
- prioritize stability

Do NOT:
- rewrite scraper architecture casually
- massively increase concurrency
- optimize theoretical bottlenecks without logs

---

# Eversports

## Current Architecture

Eversports scraping runs on Railway, inside the same backend process as eTennis.

Reason:
Cloudflare protections require browser-capable infrastructure and TLS impersonation — both available on Railway.

Current architecture:
- `eversports_service.py` is imported directly into `app.py`
- Playwright fallback runs on the same Railway service
- Vercel edge function proxy used for Cloudflare calendar endpoint bypass

Main file:
- `Backend/eversports_service.py`

---

## Current Strategy

Two-layer system:

### Fast path
- `curl_cffi`
- Chrome TLS impersonation
- lightweight requests

### Fallback path
- Playwright Chromium
- browser rendering
- DOM parsing fallback
- CF cookie warmup ~45 s first time, then cached ~60 min
- only runs when `RAILWAY_ENVIRONMENT` is set — skipped locally to keep dev searches fast

---

## Important Constraints

Cloudflare behavior may:
- change unexpectedly
- block HTTP-only requests
- require browser execution
- invalidate old scraping assumptions

Never assume:
- plain requests will continue working permanently
- selectors remain stable

---

## Important Railway Notes

Railway currently uses:
- Docker deployment
- Playwright installed in Docker image

This is intentional.

Previous non-Docker deployments caused:
- missing browser binaries
- unstable Playwright environments

---

## Availability Logic

Current venue status logic:

### FREE
At least one known court is NOT booked.

### BUSY
All known courts are booked.

### UNKNOWN / PLATFORM_CHECK_REQUIRED
Returned when:
- target time is outside returned calendar scope
- parsing failed
- insufficient data available

---

## Important Reliability Principles

Do:
- preserve proven fallback logic
- keep Playwright fallback operational
- run all Eversports async code on uvicorn's main event loop via `run_coroutine_threadsafe` (never `_run_async`)
- maintain structured logs
- validate production behavior carefully

Do NOT:
- remove fallback layers casually
- assume API stability
- tightly couple Eversports logic to eTennis logic

---

# Shared Operational Principles

## Production Stability First

Reliability is more important than:
- theoretical elegance
- excessive abstraction
- premature optimization

---

## Logging

Structured logging is important.

Critical metrics:
- venue duration
- batch duration
- timeout frequency
- fallback frequency
- duplicate-run prevention behavior

---

## Deployment Philosophy

Frontend:
- Vercel

Backend (all scraping — eTennis + Eversports):
- Railway

Cloudflare calendar bypass:
- Vercel edge function proxy (`EVERSPORTS_CALENDAR_PROXY`)

There is no longer a separate scraping microservice. Everything runs in the single Railway backend.

---

# Future Improvements

Potential future work:
- better monitoring
- scraper health dashboards
- smarter cache invalidation
- retry strategies
- selector versioning
- scraper-specific metrics

---

# Platforms to Build Next

## tennis04 (LIVE)

5 Austrian venues, growing as tennis clubs add padel courts. Implemented in
`Backend/tennis04_checker.py`, wired into `app.py` as "Phase 2.5" (alongside
eTennis and Eversports). Plain-HTTP public API — no auth, no browser.

**API — fully public, no auth, plain `requests.get`:**

1. **Get club ID** (one-time per venue):
   Fetch `https://app.tennis04.com/de/{slug}/buchungsplan`, regex `window\['_id'\] = (\d+)`.

2. **Get Padel courtgroup UUID + courts + opening hours** (one-time per venue):
   `GET https://app.tennis04.com/a/{club_id}/courtgroups`
   Response is **nested**: a top-level array of groups, each holding a
   `courtGroups` array. Flatten and pick the one whose `name` contains "padel".
   That object gives `id` (UUID), `courts[].id`, `hourFrom`, `hourUntil`,
   `defaultDurationMinutes`.

3. **Check availability** (per search):
   `GET https://app.tennis04.com/a/{club_id}/bookings?datefrom=YYYY-MM-DD&dateto=YYYY-MM-DD&courtgroup={padel_uuid}&useAccountingColors=false`
   ⚠️ **`useAccountingColors=false` is REQUIRED** — omitting it returns a 404
   ("No HTTP resource was found"). Returns an array of **booked** slots with
   `start`, `end` (naive Vienna-local ISO) and `resourceId` (court id).
   Logic: a court is busy if a booking covers the requested time
   (`start <= T < end`). Venue is FREE if ≥1 court is free, BUSY if all booked,
   `no_slot` if T is outside `hourFrom`–`hourUntil`.

The checker fetches courtgroups (cached in-process for 1 h, since court lists +
hours are static) and the day's bookings per check, so MongoDB only needs the
two IDs below — court lists are read live and stay current.

4. **Prices** (per check, shown as `€ X/h`):
   `GET https://app.tennis04.com/a/{club_id}/courtgroups/{padel_uuid}/pricelegend?seasonId={id}`
   Returns `priceUnit` (minutes — always 60 so far) and `tariffTable[]` of groups,
   each with `prices[]` of `{weekDay, beginTime, endTime, price}`. `weekDay` is
   1=Mon…7=Sun (matches Python `isoweekday()`; confirmed by venues that carry a
   flat weekend rate on days 6/7). The checker picks the **"Gast" (guest) group**
   — the public non-member rate (member groups are often €0) — and matches the
   requested weekday + time range, falling back to the cheapest non-zero rate if
   there's no guest group. `seasonId` comes from the courtgroup's `seasons[]` (the
   one covering the search date); pricelegend is cached in-process for 1 h.

**MongoDB fields per venue:** `tennis04_club_id` (int), `tennis04_courtgroup_id` (UUID string).

**Current tennis04 venues (club_id):** SV Lichtenberg (369), tcbw Feldkirch (12),
TC Hard (107), Padelclub Mattersburg (1183), UTC Sparkasse Scheibbs (505).

---

## Playtomic (priority: MEDIUM)

3 Austrian venues currently. Global platform, likely has a public API.
Worth investigating once tennis04 is live.

---

## ScrapeGraphAI — for venue onboarding, not availability scraping

ScrapeGraphAI (LLM-powered scraper) is **not** useful for structured APIs like tennis04 or Eversports.
Those have clean JSON endpoints — use the dedicated checkers. ScrapeGraphAI earns its keep on
**unstructured / one-off pages** where writing a custom parser isn't worth it:

- **Venue onboarding** — point it at any venue site and get back
  `{platform, booking_url, court_type, address, prices, opening_hours}` without writing a
  platform-specific parser per site. Replaces the regex platform-detection in `add_venue.py` for
  weird sites.
- **Phone-only venues** — extract opening hours, phone, prices from messy HTML.
- **Venue discovery** — structured extraction from directory / listing pages.

### MCP server status (June 2026) — ⚠️ tools DO NOT WORK against the current API

The `scrapegraph` MCP server is registered in Claude Code at user scope, **but its tools are
non-functional** and should not be relied on. Why:

- The published package (`scrapegraph-mcp` v1.0.1, the latest) is **hardcoded to the old
  `https://api.scrapegraphai.com/v1` API**, which ScrapeGraph has **deprecated/decommissioned**.
- Keys issued by the current dashboard (`dashboard.scrapegraphai.com`) only work on the **new
  `https://v2-api.scrapegraphai.com/api` host**. So every MCP tool call returns
  `403 {"error":"Invalid API key."}` — the key is fine, the package is calling a dead endpoint.
- **`claude mcp get scrapegraph` showing `✓ Connected` is misleading** — it only confirms the local
  server process boots. It never validates the key against ScrapeGraph. The first real API call is
  what exposes the failure.

The key itself is **valid** (verified June 2026): a `GET https://v2-api.scrapegraphai.com/api/credits`
with header `SGAI-APIKEY: <key>` returns `{"remaining":500,"plan":"Free Plan",...}`. Key + the two
FastMCP env vars (`FASTMCP_SHOW_SERVER_BANNER=false`, `FASTMCP_CHECK_FOR_UPDATES=off`) live in
`C:\Users\Topfreisen Queen\.claude.json`.

### How to actually use ScrapeGraph today — call the v2 API directly

Until the package is updated upstream (or patched locally), skip the MCP tools and hit v2 with
`httpx` + the key. Endpoints discovered to work:

| Purpose | v2 call | Notes |
|---|---|---|
| Credits | `GET /api/credits` | Free. Returns `{remaining, used, plan}`. |
| Scrape one page | `POST /api/scrape` `{"url":..., "prompt":...}` | Returns **raw markdown** under `results.markdown.data`. The `prompt` is currently **ignored** (no LLM extraction) — you parse the markdown yourself. Add `"render_heavy_js": true` to attempt JS rendering. |
| Web search + scrape | `POST /api/search` `{"query":..., "num_results":N}` | Body key is `query` (not `user_prompt`). Returns `results[]` of `{url,title,content}` pages. ~30 credits for 3 pages. |

Base URL `https://v2-api.scrapegraphai.com`, auth header `SGAI-APIKEY: <key>`. The old v1 tool names
(`smartscraper`, `searchscraper`, `markdownify`, `sitemap`, `agentic-scrapper`, `crawl`) and their
request/response shapes from the package are **outdated** — do not assume they map 1:1 to v2.

### Free tier & credits ⚠️

- Credit system. Free plan started with **500 credits**. `scrape` is cheap (~3–5 credits);
  `search` is ~30 credits per call (3 pages).
- Check balance: `GET /api/credits` or https://dashboard.scrapegraphai.com.

### Reality check — ScrapeGraph adds little for venue discovery (tested June 2026)

Diffed ScrapeGraph output against the live `venues` collection (166 venues):

- **padelclubs.net** (Austria) → 13 clubs, **0 new**.
- **padel-test.de** (Austria section) → 8 venues, **all already in the DB**.
- **Eversports city listings** → venue cards are JS/XHR-rendered; v2 `scrape` (even with
  `render_heavy_js`) could not read them.

**Conclusion:** public padel directories are *less* complete than this DB — they yield nothing new.
Genuinely new venues only exist on the live booking platforms (Eversports/Playtomic, JS-rendered) and
Google Maps/Places. For discovery, prefer the existing `discover_venues_vienna.py` (Google Places) or
Playwright MCP on live platform pages — not ScrapeGraph.

### If you want the MCP tools working

Two options: (a) **patch** `scrapegraph_mcp/server.py` in site-packages to target
`v2-api.scrapegraphai.com/api` with the new paths + response parsing — works, but it's a
site-packages edit that's lost on reinstall/upgrade; or (b) **wait** for an upstream package release
that supports v2. Neither is done yet.

### Local Python alternative (no MCP)

For scripts rather than Claude tools: `pip install scrapegraphai`, uses the Anthropic key already in
`.env`.

---

# Important Warning

Do not rewrite working scraper systems without strong evidence and production measurements.

Scraping systems are fragile by nature.

Stable production behavior is extremely valuable.

---

# Venue Onboarding Pipeline

## Scripts

| Script | Usage | Purpose |
|---|---|---|
| `add_venue.py` | `python add_venue.py <url>` | Single venue — paste any URL, auto-inserts as `active: false` |
| `discover_venues_vienna.py` | `python discover_venues_vienna.py` | Bulk Vienna discovery via Google Places, idempotent |
| `patch_venue.py` | `python patch_venue.py <identifier>` | Fill gaps from Claude browser JSON, flips `active: true` |
| `audit_pending.py` | `python audit_pending.py` | Shows all `active: false` venues and missing fields |

`patch_venue.py` accepts: Eversports slug, eTennis ID, booking URL fragment, or name fragment.

---

## Which Path to Use

**Use `add_venue.py` → `patch_venue.py`** when you only have the URL and need Claude to fetch platform data (facility ID, court IDs) automatically.

**Skip both scripts and write directly to MongoDB** when you already have the complete JSON from the Claude browser prompt. Before inserting, always display the full document in chat for review. Only write to MongoDB after confirmation. In that case, a single `$set` upsert with all fields populated + `active: true` is faster and avoids the interactive prompt in `patch_venue.py`:

```python
col.update_one(
    {"eversports_slug": "<slug>"},          # or {"etennis_id": "<id>"}
    {"$set": {<all fields>, "active": True}},
)
```

The two-step pipeline exists for when you *don't* have the data yet. If you do, skip it.

**After any insert:** Railway must be restarted to pick up new venues. `VENUES` is loaded once at startup in `app.py` and never refreshed mid-run — the 5-minute TTL cache in `venues_mongo.py` is never re-invoked after startup. Trigger a redeploy from the Railway dashboard or via `railway redeploy --yes` — new venues won't appear in search results until then.

---

## Venue Schema Conventions

- `operator` — brand only (e.g. `Padelzone`, `Padeldome`, `Padel4Fun`)
- `name` — location label only (e.g. `Traiskirchen`, `Wien Floridsdorf`, `Alt Erlaa`)
- Frontend displays as `{operator} {name}` — but if they're equal or one contains the other, it shows only one. For self-operated venues with no separate brand, set both to the full venue name (e.g. `"Sportzentrum Marswiese"` / `"Sportzentrum Marswiese"`).
- `court_type` — `indoor`, `outdoor`, or `indoor+outdoor`
- `courts` — array of `{id: "123", type: "indoor_normal"}` — parallel to `eversports_court_ids`
- Court type values: `indoor_normal`, `indoor_single`, `outdoor_normal`, `outdoor_single`
- `issues` — set to `"phone_booking_only"` for venues that have an Eversports/eTennis page but don't offer online booking. Leave `eversports_facility_id: null` and `eversports_court_ids: []` — the scraper won't run but the venue still appears in results.
- `lat` / `lon` — **required** (note: `lon`, not `lng`). Venues without coordinates are invisible in search (search is location + radius). Always include when writing directly to MongoDB. Use Google Maps or geocoding to get coordinates from the address.
- `booking_url` — **required for all venues**. Used by the eTennis scraper to navigate to the booking page, and by the Eversports price fetcher as the slug source and Referer header. Without it the venue returns "Nicht online prüfbar" (eTennis) or shows no prices (Eversports). Patterns: `https://www.eversports.at/sb/<slug>` (Eversports), `https://www.buchung-padelbase.at/reservierung?c=<id>` (Padelbase), `https://www.padeldome.wien/reservierung?c=<id>` (Padeldome). Check an existing venue of the same operator if unsure.

---

## Venue Extractor Prompt

Use with the Claude Chrome extension **or** Playwright MCP (`browser_evaluate` + `browser_network_requests`). Returns clean JSON only.

---

### PLATFORM DETECTION
- `eversports.at` in URL → **Eversports**
- `etennis`, `tennisplatz.info`, or custom domain with `data-cid` / `?c=` → **eTennis**

---

### EVERSPORTS — steps

1. **Clear** network log, then navigate to `/sb/<slug>`. Wait for calendar to render.
2. **Read** network requests filtered by `slot` → parse `facilityId` (int) and all `courts[]` values from the URL.
3. **Run this JS** to get court→id→area in one call:

```js
const seen = new Set(), r = [];
for (const row of document.querySelectorAll('tr.court')) {
  const td = row.querySelector('td[data-court]');
  const name = row.querySelector('.court-name')?.textContent.trim();
  if (td && name && !seen.has(name)) {
    seen.add(name);
    r.push({ id: td.dataset.court, name, area: row.dataset.area });
  }
}
JSON.stringify(r)
```

4. If **multiple sport tabs** exist (e.g. "Padel Indoor" / "Padel Outdoor"), click each tab and repeat steps 2–3. Collect all courts across tabs.
5. Navigate to `/s/<slug>` → scroll to Location section → read address.
6. `booking_link` = `https://www.eversports.at/sb/<slug>`

**Court type mapping** (use `area` field from JS):
- `area=indoor` + name contains "Single" → `indoor_single`
- `area=indoor` → `indoor_normal`
- `area=outdoor` + name contains "Single" → `outdoor_single`
- `area=outdoor` → `outdoor_normal`

---

### eTENNIS — steps

1. On the reservation page, run this JS to get cid + courts + booking link at once:

```js
const url = location.href;
const cid = document.querySelector('[data-cid]')?.dataset?.cid
  || new URLSearchParams(location.search).get('c');
const dayCourts = document.querySelector('.day-courts');
const src = dayCourts || document;
const courts = [...new Set(
  [...src.querySelectorAll('div.court')]
    .map(el => el.textContent.trim())
    .filter(t => t.length > 0 && t.length < 50)
)];
JSON.stringify({
  cid,
  booking_link: url.includes('?c=') ? url : location.origin + '/reservierung?c=' + cid,
  courts
})
```

2. **Court type + address**: navigate to the operator's full standort listing page. Use these known URLs:
   - **Padelbase** → `padelbase.at/standort` (lists ALL locations with address, indoor/outdoor counts — use cached data if already fetched this session)
   - **Padeldome** → `padeldome.at/standort/<slug>` (individual pages; find slug from `padeldome.at` nav if needed)
   - **Others** → check operator's main domain for a `/standort/` or `/locations/` section

3. **Court type mapping** (from court name):
   - name contains "Single" → `indoor_single` or `outdoor_single`
   - otherwise → `indoor_normal` or `outdoor_normal`

---

### RULES
- Never call `read_page` — it's slow and unnecessary
- Always batch JS extraction + operator page navigation where possible
- **Padelbase**: always use `padelbase.at/standort` (the full listing); use cached data if already fetched this session
- **Padeldome**: use `padeldome.at/standort/<slug>`; if 404, check nav links on `padeldome.at` for the correct slug
- Scope court extraction to `.day-courts` to avoid noise on multi-sport sites
- Output JSON only

---

## Platform Detection

**Eversports:**
- URL pattern: `eversports.at/sb/<slug>`
- Facility ID: `data-id` attribute on the booking widget (fetched via `curl_cffi`)
- Court IDs: NOT in static HTML — use Claude browser prompt or DevTools (Network → /api/slot)
- Cloudflare blocks Vercel proxy for calendar endpoint — `EVERSPORTS_CALENDAR_PROXY` must be empty on Railway

**eTennis:**
- URL pattern: `?c=<id>` or `data-cid` attribute in page DOM
- Works on custom domains (e.g. `padeldome.wien`, `reservierung.padel4fun.at`)

---

## Known Operator Quirks

**Padeldome** — JS-rendered site, booking links not in static HTML. All venues book via `padeldome.wien/reservierung?c=ID`:
- Erdberg: `c=2665` · Süßenbrunn: `c=2667` · Alt Erlaa: `c=2668`
- Alte Donau indoor: `c=3216` · Alte Donau outdoor: `c=3218`

**Padelzone** — venue pages at `padelzone.at/<location>` contain Eversports links. Homepage has none.

---

## Known Backend Bug — Eversports Availability Blocked by Price Refresh (fixed)

**Symptom:** All Eversports venues show "Nicht online prüfbar" after a Railway restart.

**Root cause:** `eversports_prices._refresh_running = True` was gating the entire Eversports availability check, not just the price task. With 12 venues × 30 s stagger, the price refresh ran for ~6 min, during which all Eversports checks were skipped and venues returned `unknown`.

**Fix (app.py):** The availability check (pending marking + background scraper) now always runs. Only the price-refresh task creation is gated on `_refresh_running`.

**Regression test:** `Backend/test_ev_refresh_gate.py` — run with `python test_ev_refresh_gate.py`.

---

## Expanding Discovery to All of Austria

In `discover_venues_vienna.py`, update `search_places()`:
1. Remove or expand the `locationBias` circle
2. Add city-specific queries (e.g. `"padel Graz"`, `"padel Salzburg"`)
3. Add city-specific hardcoded venue lists to `HARDCODED_VENUES`