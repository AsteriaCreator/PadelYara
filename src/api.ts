import type { SearchParams, SearchResponse } from "./types"

const API_BASE = "http://localhost:5000"

export async function fetchAvailability(params: SearchParams): Promise<SearchResponse> {
  const url = new URL(`${API_BASE}/api/search`)
  url.searchParams.set("date", params.date)
  url.searchParams.set("time", params.time)
  url.searchParams.set("region", params.region)
  url.searchParams.set("court_type", params.court_type)

  const res = await fetch(url.toString())
  return res.json() as Promise<SearchResponse>
}
