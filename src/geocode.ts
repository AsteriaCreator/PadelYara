export interface Coords {
  lat: number
  lon: number
}

export async function geocode(query: string): Promise<Coords | null> {
  const url = new URL("https://nominatim.openstreetmap.org/search")
  url.searchParams.set("q", query)
  url.searchParams.set("countrycodes", "at")
  url.searchParams.set("format", "json")
  url.searchParams.set("limit", "1")

  const res = await fetch(url.toString(), {
    headers: { "User-Agent": "PadelChecker/1.0" },
  })
  if (!res.ok) return null

  const data = await res.json()
  if (!Array.isArray(data) || data.length === 0) return null

  return { lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon) }
}
