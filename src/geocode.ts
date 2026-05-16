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

export async function geocode(query: string): Promise<Coords | null> {
  const url = new URL("https://nominatim.openstreetmap.org/search")
  url.searchParams.set("q", query)
  url.searchParams.set("countrycodes", "at")
  url.searchParams.set("format", "json")
  url.searchParams.set("limit", "1")

  try {
    const res = await fetch(url.toString(), {
      headers: { "User-Agent": "PadelChecker/1.0" },
      signal: AbortSignal.timeout(GEOCODE_TIMEOUT_MS),
    })
    if (!res.ok) return null

    const data = await res.json()
    if (!Array.isArray(data) || data.length === 0) return null

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
