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
  query = query.trim()
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
    const MIN_IMPORTANCE = 0.05
    const importance = parseFloat(data[0].importance ?? "1")
    if (importance < MIN_IMPORTANCE) return null

    // Reject bare prefix/abbreviation matches where the query doesn't appear
    // in the result name at all and also covers less than half its length.
    // e.g. "Bad" vs "Bad Ischl": "bad" not in "bad ischl"? actually it is —
    // so use substring check as primary gate: if query is a substring of the
    // result name (case-insensitive), always accept.
    // e.g. "Schwechat" in "Flughafen Wien-Schwechat" → accept
    //      "Bad" in "Bad Ischl" → accept (but importance filter handles junk)
    //      "B" in "Baden" → substring match, but length ratio 1/5 = 0.2 → reject
    const resultName: string = data[0].name ?? ""
    const q = query.toLowerCase()
    const rn = resultName.toLowerCase()
    if (resultName && !rn.includes(q) && q.length / resultName.length < 0.5) return null

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
