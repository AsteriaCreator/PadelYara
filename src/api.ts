import type { SearchParams, SearchResponse, Venue, Status } from "./types"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"

/**
 * Fire-and-forget booking intent signal. Never blocks navigation or throws.
 * Uses sendBeacon (survives tab close) with a fetch+keepalive fallback.
 */
export function trackBookingClick(venueId: string, platform: string): void {
  const url = `${API_BASE}/api/booking-click`
  const body = JSON.stringify({ venue_id: venueId, platform })
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
  platform: string
  distance_km: number | null
  court_type: string
  availability_status?: string
  booking_url: string
  weather: Venue["weather"]
}

function mapVenue(v: RawVenue): Venue {
  return {
    id: v.venue_id,
    name: v.name,
    court_type: v.court_type as Venue["court_type"],
    platform: v.platform as Venue["platform"],
    booking_url: v.booking_url,
    status: (v.availability_status as Status) ?? "pending",
    weather: v.weather,
    distance_km: v.distance_km,
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

  if (etOffset > 0) {
    url.searchParams.set("et_offset", String(etOffset))
  }

  const res = await fetch(url.toString())
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    return {
      ok: false,
      results: [],
      date: params.date,
      time: params.time,
      error: body.message ?? "Server error",
    }
  }

  const data = await res.json()
  const results = (data.results as RawVenue[]).map(mapVenue)
  return {
    ok: true,
    results,
    date: data.date,
    time: data.time,
    // Prefer the explicit backend field; fall back to client-side check for old servers
    availability_pending: data.availability_pending ?? results.some((v) => v.status === "pending"),
    has_more: data.has_more ?? false,
  }
}
