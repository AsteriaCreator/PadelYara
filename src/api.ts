import type { SearchParams, SearchResponse, Venue, Status, Weather } from "./types"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"

// Anonymous session ID — random UUID persisted in localStorage.
// No personal data: just a random string to distinguish unique vs. returning
// browsers. Never tied to an account, IP, or fingerprint.
export function getSessionId(): string {
  const KEY = "anon_session_id"
  let id = localStorage.getItem(KEY)
  if (!id) {
    id = crypto.randomUUID()
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

// Shape the backend actually returns
type RawVenue = {
  venue_id: string
  name: string
  operator?: string
  platform: string
  distance_km: number | null
  court_type: string
  availability_status?: string
  booking_url: string
  public_url?: string
  time_adjusted?: boolean
  matched_time?: string
  requested_time?: string
  adjustment_label?: string
  price_eur?: number | null
  slot_duration_h?: number | null
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
    status: (v.availability_status as Status) ?? "pending",
    distance_km: v.distance_km,
    time_adjusted: v.time_adjusted,
    matched_time: v.matched_time,
    requested_time: v.requested_time,
    adjustment_label: v.adjustment_label,
    price_eur: v.price_eur,
    slot_duration_h: v.slot_duration_h,
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

const ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN ?? ""

function adminHeaders() {
  return { "Content-Type": "application/json", "X-Admin-Token": ADMIN_TOKEN }
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

export async function fetchSubscriberCount(): Promise<number> {
  const res = await fetch(`${API_BASE}/api/subscribers/count`, { headers: adminHeaders() })
  if (!res.ok) throw new Error("Failed to fetch subscriber count")
  const data = await res.json()
  return data.count as number
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
