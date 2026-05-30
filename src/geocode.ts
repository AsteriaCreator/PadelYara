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


// Only keep settlement-level results
const PHOTON_PLACE_KEYS = new Set(["place", "boundary"])

export async function suggest(query: string, userLocation?: Coords): Promise<Suggestion[]> {
  query = query.trim()
  if (query.length < 3) return []
  const url = new URL("https://photon.komoot.io/api/")
  url.searchParams.set("q", query)
  url.searchParams.set("countrycode", "at")
  url.searchParams.set("limit", "15")
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
    const seen = new Set<string>()
    const results: Suggestion[] = []
    for (const f of features) {
      const p = f.properties as Record<string, unknown>
      const geo = f.geometry as { coordinates: [number, number] }
      if (!PHOTON_PLACE_KEYS.has(p.osm_key as string)) continue
      const name = (p.name as string) ?? ""
      const state = (p.state as string) ?? ""
      const label = state ? `${name}, ${state}` : name
      if (seen.has(label)) continue
      seen.add(label)
      results.push({ label, lat: geo.coordinates[1], lon: geo.coordinates[0] })
      if (results.length === 5) break
    }
    return results
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
