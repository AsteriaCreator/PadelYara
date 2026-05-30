export interface Coords {
  lat: number
  lon: number
}

/** Thrown when the geocoding request takes longer than GEOCODE_TIMEOUT_MS. */
export class GeocodeTimeoutError extends Error {
  constructor() {
    super("Geocode request timed out")
    this.name = "GeocodeTimeoutError"
  }
}

const GEOCODE_TIMEOUT_MS = 5_000

export interface Suggestion {
  label: string
  lat: number
  lon: number
}

function distanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLon = (lon2 - lon1) * Math.PI / 180
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

const PHOTON_PLACE_TYPES = new Set(["city", "town", "village", "municipality", "borough", "suburb", "hamlet", "district"])

export async function suggest(query: string, userLocation?: Coords): Promise<Suggestion[]> {
  query = query.trim()
  if (query.length < 3) return []
  const url = new URL("https://photon.komoot.io/api/")
  url.searchParams.set("q", query)
  url.searchParams.set("countrycode", "at")
  url.searchParams.set("limit", "10")
  url.searchParams.set("lang", "de")
  if (userLocation) {
    url.searchParams.set("lat", String(userLocation.lat))
    url.searchParams.set("lon", String(userLocation.lon))
  }
  try {
    const res = await fetch(url.toString(), { signal: AbortSignal.timeout(5_000) })
    if (!res.ok) return []
    const data = await res.json()
    const features: Record<string, unknown>[] = data?.features ?? []
    const q = query.toLowerCase()
    return features
      .filter((f) => {
        const p = f.properties as Record<string, unknown>
        const name = ((p.name as string) ?? "").toLowerCase()
        return PHOTON_PLACE_TYPES.has(p.type as string) && name.startsWith(q)
      })
      .slice(0, 5)
      .map((f) => {
        const p = f.properties as Record<string, unknown>
        const geo = f.geometry as { coordinates: [number, number] }
        const name = (p.name as string) ?? ""
        const state = (p.state as string) ?? ""
        return {
          label: state ? `${name}, ${state}` : name,
          lat: geo.coordinates[1],
          lon: geo.coordinates[0],
        }
      })
  } catch {
    return []
  }
}

export async function geocode(query: string): Promise<Coords | null> {
  query = query.trim()
  const url = new URL("https://nominatim.openstreetmap.org/search")
  url.searchParams.set("q", query)
  url.searchParams.set("countrycodes", "at")
  url.searchParams.set("format", "json")
  url.searchParams.set("limit", "1")

  try {
    const res = await fetch(url.toString(), {
      signal: AbortSignal.timeout(GEOCODE_TIMEOUT_MS),
    })
    if (!res.ok) return null

    const data = await res.json()
    if (!Array.isArray(data) || data.length === 0) return null

    // Filter out truly junk results (importance well below any real AT place).
    // countrycodes=at + limit=1 already constrain the result set tightly.
    const MIN_IMPORTANCE = 0.01
    const importance = parseFloat(data[0].importance ?? "1")
    if (importance < MIN_IMPORTANCE) return null

    return { lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon) }
  } catch (err) {
    // AbortSignal.timeout fires a DOMException with name "TimeoutError"
    if (err instanceof DOMException && (err.name === "TimeoutError" || err.name === "AbortError")) {
      console.warn(`[geocode] timed out after ${GEOCODE_TIMEOUT_MS}ms for query: ${query}`)
      throw new GeocodeTimeoutError()
    }
    // Rethrow other errors (network down, CORS, etc.) so the caller can handle them
    throw err
  }
}
