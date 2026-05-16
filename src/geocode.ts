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

    // Treat results with extremely low importance as not-found.
    // All real Austrian cities, towns, and PLZs score well above 0.1;
    // only spurious/junk matches fall this low.
    const MIN_IMPORTANCE = 0.1
    const importance = parseFloat(data[0].importance ?? "1")
    if (importance < MIN_IMPORTANCE) return null

    // Reject prefix/abbreviation matches: the user's query must cover at
    // least half the length of the result's canonical name.
    // e.g. "Bad" (3) vs "Bad Ischl" (9) = 33% → null
    //      "Baden" (5) vs "Baden" (5)   = 100% → accept
    //      "Wien" (4) vs "Wien" (4)     = 100% → accept
    //      "2500" (4) vs "2500" (4)     = 100% → accept
    const resultName: string = data[0].name ?? ""
    if (resultName && query.trim().length / resultName.length < 0.5) return null

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
