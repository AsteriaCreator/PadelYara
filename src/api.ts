import type { SearchParams, SearchResponse, Venue, Status, Weather, MapVenue, VenueDetail } from "./types"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"

// Anonymous session ID — random UUID persisted in localStorage.
// No personal data: just a random string to distinguish unique vs. returning
// browsers. Never tied to an account, IP, or fingerprint.
export function getSessionId(): string {
  const KEY = "anon_session_id"
  let id = localStorage.getItem(KEY)
  if (!id) {
    id = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2)
    localStorage.setItem(KEY, id)
  }
  return id
}

/**
 * Fire-and-forget booking intent signal. Never blocks navigation or throws.
 * Uses fetch+keepalive so it survives target="_blank" tab opens.
 */
export function trackBookingClick(venueId: string, platform: string): void {
  const url = `${API_BASE}/api/booking-click`
  const body = JSON.stringify({ venue_id: venueId, platform, session_id: getSessionId() })
  // Defer by one tick so the click handler returns before the network request
  // goes out. This avoids colliding with the peak load of an active scrape on
  // the backend (target="_blank" keeps the current page alive, so keepalive
  // is sufficient — sendBeacon's "survives unload" property is not needed here).
  setTimeout(() => {
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {})
  }, 0)
}

// True only for the very first pageview after a full page load. The browser's
// document.referrer does NOT change on client-side (SPA) route changes, so we
// only attribute an external referrer on the entry view; later route changes
// are internal navigations and send referrer_host = null.
let _isFirstPageview = true

/**
 * Fire-and-forget, cookieless page view. Sends only the internal path, the
 * bare hostname of an external referrer (or "direct"), and the anonymous
 * session id. No full URLs, no query strings, no IPs. Never throws.
 */
export function trackPageview(path: string): void {
  let referrer_host: string | null = null
  if (_isFirstPageview) {
    _isFirstPageview = false
    try {
      if (document.referrer) {
        const ref = new URL(document.referrer)
        // Only count genuinely external referrers
        if (ref.host !== location.host) {
          referrer_host = ref.hostname.replace(/^www\./, "")
        }
      } else {
        referrer_host = "direct"
      }
    } catch { /* malformed referrer — leave null */ }
  }
  const url = `${API_BASE}/api/pageview`
  const body = JSON.stringify({ path, referrer_host, session_id: getSessionId() })
  setTimeout(() => {
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {})
  }, 0)
}

// Shape the backend actually returns
type RawVenue = {
  venue_id: string
  name: string
  operator?: string
  platform: string
  distance_km: number | null
  court_type: string
  availability_status?: Status
  booking_url: string
  public_url?: string
  time_adjusted?: boolean
  matched_time?: string
  requested_time?: string
  adjustment_label?: string
  price_eur?: number | null
  slot_duration_h?: number | null
  matched_duration_h?: number | null
  available_durations_h?: number[] | null
}

function mapVenue(v: RawVenue): Venue {
  return {
    id: v.venue_id,
    name: v.name,
    operator: v.operator,
    court_type: v.court_type as Venue["court_type"],
    platform: v.platform as Venue["platform"],
    booking_url: v.booking_url,
    public_url: v.public_url,
    status: v.availability_status ?? "pending",
    distance_km: v.distance_km,
    time_adjusted: v.time_adjusted,
    matched_time: v.matched_time,
    requested_time: v.requested_time,
    adjustment_label: v.adjustment_label,
    price_eur: v.price_eur,
    slot_duration_h: v.slot_duration_h,
    matched_duration_h: v.matched_duration_h,
    available_durations_h: v.available_durations_h,
  }
}


export interface GeoParams {
  lat: number
  lon: number
  radius: number
}

export async function fetchAvailability(
  params: SearchParams,
  geo?: GeoParams,
  etOffset = 0,
): Promise<SearchResponse> {
  const url = new URL(`${API_BASE}/api/search`)
  url.searchParams.set("date", params.date)
  url.searchParams.set("time", params.time)

  // Backend accepts "all" not "both"
  const ct = params.court_type === "both" ? "all" : params.court_type
  url.searchParams.set("court_type", ct)

  if (geo) {
    url.searchParams.set("lat", String(geo.lat))
    url.searchParams.set("lon", String(geo.lon))
    url.searchParams.set("radius", String(geo.radius))
  }

  // Pass the human-readable location name for analytics (no PII — user typed it)
  if (params.location) {
    url.searchParams.set("search_location", params.location)
  }

  // Acceptable play durations (minutes). Omitted → backend default (2 h).
  if (params.durations && params.durations.length > 0) {
    url.searchParams.set("durations", params.durations.join(","))
  }

  if (etOffset > 0) {
    url.searchParams.set("et_offset", String(etOffset))
  }

  const res = await fetch(url.toString(), {
    headers: { "X-Session-Id": getSessionId() },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    return {
      ok: false,
      results: [],
      date: params.date,
      time: params.time,
      error: body.error ?? "Server error",
    }
  }

  const data = await res.json()
  const results = (data.results as RawVenue[]).map(mapVenue)
  return {
    ok: true,
    results,
    date: data.date,
    time: data.time,
    availability_pending: data.availability_pending ?? results.some((v) => v.status === "pending"),
    has_more: data.has_more ?? false,
    booking_window_notice: data.booking_window_notice as string | undefined,
    weather: data.weather ?? null,
  }
}

/** All active venues with static info (coords, address, links) for the Padelrevier map. */
export async function fetchVenues(): Promise<MapVenue[]> {
  const res = await fetch(`${API_BASE}/api/venues`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return (data.venues ?? []) as MapVenue[]
}

/** Full detail for one venue (Court-Detailseite). Returns null on 404. */
export async function fetchVenueDetail(slug: string): Promise<VenueDetail | null> {
  const res = await fetch(`${API_BASE}/api/venues/${encodeURIComponent(slug)}`)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return await res.json() as VenueDetail
}

/** Community suggestion: field picks + free text for one venue. */
export async function submitVenueSuggestion(
  slug: string,
  picks: Record<string, string>,
  freeText: string,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/venues/${encodeURIComponent(slug)}/suggest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ picks, free_text: freeText }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

// The admin secret is NEVER baked into the frontend bundle. The admin types it
// into the dashboard login once; it lives only in this browser's localStorage.
const ADMIN_TOKEN_KEY = "admin_token"

export function getAdminToken(): string {
  try {
    return localStorage.getItem(ADMIN_TOKEN_KEY) ?? ""
  } catch {
    return ""
  }
}

export function setAdminToken(token: string): void {
  try { localStorage.setItem(ADMIN_TOKEN_KEY, token) } catch { /* */ }
}

export function clearAdminToken(): void {
  try { localStorage.removeItem(ADMIN_TOKEN_KEY) } catch { /* */ }
}

export function hasAdminToken(): boolean {
  return getAdminToken().length > 0
}

function adminHeaders() {
  return { "Content-Type": "application/json", "X-Admin-Token": getAdminToken() }
}

const MY_SESSIONS_KEY = "analytics_my_sessions"

/** Returns the list of session IDs the owner has registered as "mine". */
export function getMySessionIds(): string[] {
  try {
    const raw = localStorage.getItem(MY_SESSIONS_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

/** Adds the current device's session ID to the "my sessions" list. */
export function registerThisDevice(): string[] {
  const id = getSessionId()
  const current = getMySessionIds()
  if (current.includes(id)) return current
  const updated = [...current, id]
  try { localStorage.setItem(MY_SESSIONS_KEY, JSON.stringify(updated)) } catch { /* */ }
  return updated
}

/** Removes a session ID from the "my sessions" list. */
export function removeMySession(id: string): string[] {
  const updated = getMySessionIds().filter((s) => s !== id)
  try { localStorage.setItem(MY_SESSIONS_KEY, JSON.stringify(updated)) } catch { /* */ }
  return updated
}

function _excludeParam(ids: string[]): string {
  return ids.length ? `?exclude_sessions=${encodeURIComponent(ids.join(","))}` : ""
}

export async function fetchAnalytics(excludeIds: string[] = []) {
  const res = await fetch(`${API_BASE}/api/analytics${_excludeParam(excludeIds)}`, { headers: adminHeaders() })
  if (res.status === 403) throw new Error("Unauthorized")
  if (!res.ok) throw new Error("Failed to fetch analytics")
  return res.json()
}

export async function fetchAnalyticsInsights(excludeIds: string[] = []) {
  const res = await fetch(`${API_BASE}/api/analytics/insights${_excludeParam(excludeIds)}`, { headers: adminHeaders() })
  if (res.status === 403) throw new Error("Unauthorized")
  if (!res.ok) throw new Error("Failed to fetch insights")
  return res.json()
}

export async function fetchAnalyticsTrends(excludeIds: string[] = []) {
  const res = await fetch(`${API_BASE}/api/analytics/trends${_excludeParam(excludeIds)}`, { headers: adminHeaders() })
  if (res.status === 403) throw new Error("Unauthorized")
  if (!res.ok) throw new Error("Failed to fetch trends")
  return res.json()
}

export async function fetchSearchConsole() {
  const res = await fetch(`${API_BASE}/api/analytics/search-console`, { headers: adminHeaders() })
  if (res.status === 403) throw new Error("Unauthorized")
  if (res.status === 503) return null  // not configured yet
  if (!res.ok) throw new Error("Failed to fetch Search Console data")
  return res.json()
}

export async function fetchSubscriberCount(): Promise<number> {
  const res = await fetch(`${API_BASE}/api/subscribers/count`, { headers: adminHeaders() })
  if (!res.ok) throw new Error("Failed to fetch subscriber count")
  const data = await res.json()
  return data.count as number
}

export async function fetchAlertCount(): Promise<number> {
  const res = await fetch(`${API_BASE}/api/tournaments/alerts/count`, { headers: adminHeaders() })
  if (!res.ok) throw new Error("Failed to fetch alert count")
  const data = await res.json()
  return data.count as number
}

export interface AlertSubscriber {
  email: string
  filters: { bundesland: string[]; category: string[]; competition: string[]; weekday: string[]; venue_name: string[] }
  confirmed: boolean
  created_at: string
  confirmed_at: string | null
  last_notified_at: string | null
}

export async function fetchAlertList(): Promise<AlertSubscriber[]> {
  const res = await fetch(`${API_BASE}/api/tournaments/alerts/list`, { headers: adminHeaders() })
  if (!res.ok) throw new Error("Failed to fetch alert list")
  const data = await res.json()
  return data.alerts as AlertSubscriber[]
}

export interface EmailStats {
  requests: number
  delivered: number
  opens: number
  uniqueOpens: number
  clicks: number
  uniqueClicks: number
}

export async function fetchEmailStats(): Promise<EmailStats | null> {
  const res = await fetch(`${API_BASE}/api/tournaments/alerts/email-stats`, { headers: adminHeaders() })
  if (!res.ok) return null
  const data = await res.json()
  if (data.error) return null
  return data as EmailStats
}

export async function subscribeEmail(email: string): Promise<{ ok: boolean; already?: boolean }> {
  try {
    const res = await fetch(`${API_BASE}/api/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    })
    const data = await res.json().catch(() => ({}))
    return { ok: res.ok && data.ok, already: data.already ?? false }
  } catch {
    return { ok: false }
  }
}

export async function fetchWeather(
  lat: number,
  lon: number,
  date: string,
  time: string,
): Promise<Weather | null> {
  const url = new URL(`${API_BASE}/api/weather`)
  url.searchParams.set("lat", String(lat))
  url.searchParams.set("lon", String(lon))
  url.searchParams.set("date", date)
  url.searchParams.set("time", time)
  try {
    const res = await fetch(url.toString())
    if (!res.ok) return null
    return await res.json() as Weather
  } catch {
    return null
  }
}
