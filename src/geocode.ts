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

const PLACE_CLASSES = new Set(["place", "boundary", "landuse"])

export async function suggest(query: string): Promise<Suggestion[]> {
  query = query.trim()
  if (query.length < 3) return []
  const url = new URL("https://nominatim.openstreetmap.org/search")
  url.searchParams.set("q", query)
  url.searchParams.set("countrycodes", "at")
  url.searchParams.set("format", "json")
  url.searchParams.set("limit", "10")
  url.searchParams.set("addressdetails", "1")
  try {
    const res = await fetch(url.toString(), { signal: AbortSignal.timeout(5_000) })
    if (!res.ok) return []
    const data = await res.json()
    if (!Array.isArray(data)) return []
    return data
      .filter((r: Record<string, unknown>) =>
        PLACE_CLASSES.has(r.class as string) &&
        parseFloat(r.importance as string ?? "0") >= 0.01
      )
      .sort((a: Record<string, unknown>, b: Record<string, unknown>) =>
        parseFloat(b.importance as string ?? "0") - parseFloat(a.importance as string ?? "0")
      )
      .slice(0, 5)
      .map((r: Record<string, unknown>) => {
        const addr = r.address as Record<string, string> | undefined
        const name = (r.name as string) || ""
        const state = addr?.state ?? ""
        const label = state ? `${name}, ${state}` : name
        return {
          label: label || (r.display_name as string),
          lat: parseFloat(r.lat as string),
          lon: parseFloat(r.lon as string),
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
