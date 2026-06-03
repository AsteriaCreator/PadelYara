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
  booking_url: string
  status: Status
  distance_km?: number | null
  time_adjusted?: boolean
  matched_time?: string
  requested_time?: string
  adjustment_label?: string
  price_eur?: number | null
  slot_duration_h?: number | null
}

export interface SearchResponse {
  ok: boolean
  results: Venue[]
  date: string
  time: string
  availability_pending?: boolean
  has_more?: boolean
  error?: string
  booking_window_notice?: string
  weather?: Weather | null
}
