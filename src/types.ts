export type CourtType = "both" | "indoor" | "outdoor"

export type Status = "free" | "busy" | "pending" | "unknown" | "check_failed" | "phone_only" | "platform_check_required" | "not_checked" | "no_slot" | "error"

export interface SearchParams {
  date: string
  time: string
  court_type: CourtType
  location?: string
  radius: number
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
  court_type: "indoor" | "outdoor" | "indoor+outdoor"
  platform: "eTennis" | "Eversports" | "Andere"
  priority: number
  booking_url: string
  status: Status
  error: string | null
  weather: Weather | null
  distance_km?: number | null
}

export interface SearchResponse {
  ok: boolean
  results: Venue[]
  date: string
  time: string
  availability_pending?: boolean
  has_more?: boolean
  error?: string
}
