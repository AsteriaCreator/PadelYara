import type { SearchParams, SearchResponse, Venue } from "./types"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"

// Shape the backend actually returns
type RawVenue = {
  venue_id: string
  name: string
  platform: string
  distance_km: number | null
  court_type: string
  region: string | null
  available: boolean | null
  booking_url: string
  weather: Venue["weather"]
}

function mapVenue(v: RawVenue): Venue {
  return {
    id: v.venue_id,
    name: v.name,
    region: (v.region ?? "Wien") as Venue["region"],
    court_type: v.court_type as Venue["court_type"],
    platform: v.platform as Venue["platform"],
    priority: 0,
    booking_url: v.booking_url,
    status: v.available === null ? "unknown" : v.available ? "free" : "busy",
    error: null,
    weather: v.weather,
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
  } else {
    url.searchParams.set("region", params.region)
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
    availability_pending: results.some((v) => v.status === "unknown"),
  }
}
