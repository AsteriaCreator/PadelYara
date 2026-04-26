export type Region = "Bad Voeslau" | "Wien Sued" | "Wien" | "NOE Sued"

export type CourtType = "both" | "indoor" | "outdoor"

export type Status = "free" | "busy" | "error" | "unknown"

export interface SearchParams {
  date: string
  time: string
  region: Region
  court_type: CourtType
}

export interface Weather {
  icon: string
  desc: string
  temp: number
  rain_prob: number
  code: number
}

export interface Venue {
  id: string
  name: string
  region: Region
  court_type: "indoor" | "outdoor" | "indoor+outdoor"
  platform: "eTennis" | "Eversports" | "Andere"
  priority: number
  booking_url: string
  status: Status
  error: string | null
  weather: Weather | null
}

export interface SearchResponse {
  ok: boolean
  results: Venue[]
  date: string
  time: string
  error?: string
}
