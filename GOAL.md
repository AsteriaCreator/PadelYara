# Goal: Verify Live Scraper Pipeline End-to-End

_Created: 2026-05-16_

## Objective

Confirm the full pipeline — Render backend → Railway Eversports microservice → Eversports/eTennis scrapers — returns **real** availability results (not `unknown`/`pending`/`platform_check_required`) for three test cases.

## Measurable End State

`/api/search` returns at least one venue per test case with `availability_status` in `["free", "busy"]` (not `"unknown"`, `"pending"`, or `"platform_check_required"`).

### Test Cases

| # | Venue group | Region param | Expected venues |
|---|------------|--------------|-----------------|
| 1 | Eversports Traiskirchen | `Bad Voeslau` | `padelzone-traiskirchen` |
| 2 | Eversports Achtersee / Wr. Neustadt | `NOE Sued` | `padelzone-wr-neustadt-achtersee`, `padelzone-wr-neustadt-arena-27` |
| 3 | eTennis Wien | `Wien` | multiple eTennis venues |

## Test Commands

### PowerShell (Windows)

> **Note:** `region` must use the label format from the CSV (`region_label` column), not the key.
> Correct values: `"Bad Voeslau"`, `"Wien Sued"`, `"Wien"`, `"NOE Sued"`.

```powershell
$RENDER  = "https://neopadelchecker.onrender.com"
$RAILWAY = "https://neo-padel-checker-backend-production.up.railway.app"
$DATE    = (Get-Date).AddDays(1).ToString("yyyy-MM-dd")  # tomorrow
$TIME    = "18:00"

# Test 1 — Eversports Traiskirchen (Bad Voeslau region)
$r1 = Invoke-RestMethod "$RENDER/api/search?region=Bad Voeslau&date=$DATE&time=$TIME" -TimeoutSec 90
$r1.results | ForEach-Object { "$($_.venue_id) -> $($_.availability_status)" }

# Test 2 — Eversports Achtersee / Arena 27 (NOE Sued region)
$r2 = Invoke-RestMethod "$RENDER/api/search?region=NOE Sued&date=$DATE&time=$TIME" -TimeoutSec 90
$r2.results | ForEach-Object { "$($_.venue_id) -> $($_.availability_status)" }

# Test 3 — eTennis Wien region (poll until pending=False)
for ($i = 1; $i -le 3; $i++) {
    $r3 = Invoke-RestMethod "$RENDER/api/search?region=Wien&date=$DATE&time=$TIME" -TimeoutSec 90
    $r3.results | ForEach-Object { "$($_.venue_id) [$($_.platform)] -> $($_.availability_status)" }
    if (-not $r3.availability_pending) { break }
    Start-Sleep -Seconds 35
}

# Railway health check
Invoke-RestMethod "$RAILWAY/health"
# Expected: {"ok": true, "service": "eversports-service"}
```

### curl (bash / WSL)

```bash
RENDER="https://neopadelchecker.onrender.com"
DATE=$(date -d tomorrow +%Y-%m-%d)
TIME="18:00"

# Test 1 (note: URL-encode the space as %20 or +)
curl -s "$RENDER/api/search?region=Bad%20Voeslau&date=$DATE&time=$TIME" | python -m json.tool | grep -E '"venue_id"|"availability_status"'

# Test 2
curl -s "$RENDER/api/search?region=NOE%20Sued&date=$DATE&time=$TIME" | python -m json.tool | grep -E '"venue_id"|"availability_status"'

# Test 3
curl -s "$RENDER/api/search?region=Wien&date=$DATE&time=$TIME" | python -m json.tool | grep -E '"venue_id"|"availability_status"'
```

## Constraints

- Do NOT rewrite the app
- Do NOT start the MongoDB/public MVP refactor yet
- Preserve current region-based personal mode
- Reuse existing scraper/weather/frontend logic
- Only make minimal fixes needed for real production results
- Commit only after tests pass

## Deployment Branches

| Service | Branch |
|---------|--------|
| Railway backend (consolidated) | `main` |

## Pass Criteria

For each test case, at least one venue must have `availability_status` in `["free", "busy"]`. Specifically:
- Test 1: `padelzone-traiskirchen` → `free` or `busy`
- Test 2: `padelzone-wr-neustadt-achtersee` OR `padelzone-wr-neustadt-arena-27` → `free` or `busy`
- Test 3: any eTennis Wien venue → `free` or `busy`

## Results — 2026-05-16

### What ran

All three test cases executed against live production services.

| Service | URL | Status |
|---------|-----|--------|
| Render backend | `https://neopadelchecker.onrender.com` | ✅ live |
| Railway Eversports | `https://neo-padel-checker-backend-production.up.railway.app` | ✅ live |

### Test outcomes

| Test | Venue | Result | Pass? |
|------|-------|--------|-------|
| 1 — Bad Voeslau | `padelzone-traiskirchen` | `free` | ✅ |
| 1 — Bad Voeslau | `padel-ebreichsdorf` | `free` | ✅ |
| 2 — NOE Sued | `padelzone-wr-neustadt-arena-27` | `busy` | ✅ |
| 2 — NOE Sued | `padelzone-wr-neustadt-achtersee` | `busy` | ✅ |
| 2 — NOE Sued | `padelzone-sprungart` | `busy` | ✅ |
| 3 — Wien eTennis | `padeldome-alte-donau-outdoor` | `busy` | ✅ |
| 3 — Wien eTennis | `padelbase-wien` | `busy` | ✅ |
| 3 — Wien eTennis | `racketworld-wien` | `busy` | ✅ |
| 3 — Wien eTennis | `padeldome-suessenbrunn` | `busy` | ✅ |
| 3 — Wien eTennis | `padeldome-alte-donau-indoor` | `busy` | ✅ |
| 3 — Wien eTennis | `padel-union-wien` | `no_slot` | ✅ (real result) |
| 3 — Wien Eversports | `padelzone-wien-floridsdorf` | `free` | ✅ |
| 3 — Wien Eversports | `padelzone-wien-sportinsel` | `free` | ✅ |

**All three test cases PASS.** No `unknown` or `pending` results in any final response.

### Failures

One non-code issue discovered during setup:

- **Initial test commands used wrong region format.** I sent `region=bad-voeslau` (the CSV `region_key` column) but `venues.py:53` loads `region` from `region_label` ("Bad Voeslau", "NOE Sued", etc.). This caused 0 results until corrected. Not a production bug — the frontend always sends the label format.

### Root cause of the region mismatch (test commands only)

`venues.py` line 53: `"region": row["region_label"].strip()` — the dict key `region` holds the human-readable label, not the slug. The query param must match that label exactly (case-sensitive, space-separated). The frontend `constants.ts` already uses labels; only ad-hoc curl/PowerShell tests need care.

### Files changed

None. No code changes were needed. Pipeline works end-to-end as deployed.

GOAL.md test commands corrected to use label format.

### Commit/push needed?

No. No production code was changed. GOAL.md is a local notes file; no need to commit it unless desired for reference.
