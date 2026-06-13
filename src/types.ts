export type CourtType = "both" | "indoor" | "outdoor"

export type Status = "free" | "busy" | "pending" | "unknown" | "check_failed" | "phone_only" | "platform_check_required" | "not_checked" | "no_slot" | "error"

export interface SearchParams {
  date: string
  time: string
  court_type: CourtType
  location?: string
  radius: number
  // Acceptable play durations in minutes (e.g. [120] or [90, 120]).
  // A venue counts as free only if it can host one of these continuously.
  // Omitted/undefined → backend default (2 h).
  durations?: number[]
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
  operator?: string
  court_type: "indoor" | "outdoor" | "indoor+outdoor"
  platform: "eTennis" | "Eversports" | "tennis04" | "Andere"
  booking_url: string
  public_url?: string
  status: Status
  distance_km?: number | null
  time_adjusted?: boolean
  matched_time?: string
  requested_time?: string
  adjustment_label?: string
  price_eur?: number | null
  slot_duration_h?: number | null
  // The longest requested duration (hours) this venue can actually host
  // continuously at the searched time, e.g. 2 for "2h frei". Set by the backend
  // when a duration filter is active and the venue matches.
  matched_duration_h?: number | null
}

// Lightweight venue shape for the Padelrevier map (GET /api/venues).
// Distinct from `Venue` above, which carries live-availability/search fields.
export interface MapVenue {
  id: string
  name: string
  operator?: string
  address: string
  region?: string
  court_type: "indoor" | "outdoor" | "indoor+outdoor"
  platform?: string
  booking_url: string
  public_url?: string
  lat: number
  lon: number
}

// Compact venue shape for the "Andere Anlagen" cross-links on a detail page.
export interface RelatedVenue {
  id: string
  name: string
  operator?: string
  city?: string
  num_courts?: number | null
}

// Full venue payload for the /court/:slug detail page (GET /api/venues/:slug).
// Amenity booleans are tri-state: true = yes, false = no, null/undefined = unknown
// (the page then shows "Noch unbekannt" + the community prompt).
export interface VenueDetail {
  id: string
  name: string
  operator?: string
  address?: string
  bezirk?: string | null
  region_label?: string | null
  city?: string
  court_type: "indoor" | "outdoor" | "indoor+outdoor"
  platform?: string
  booking_url?: string
  public_url?: string
  website_url?: string | null
  maps_url?: string | null
  lat?: number | null
  lon?: number | null
  num_courts?: number | null
  indoor_count?: number | null
  outdoor_count?: number | null
  changing_rooms?: boolean | null
  showers?: boolean | null
  reception?: boolean | null
  reception_note?: string | null
  parking?: boolean | null
  parking_note?: string | null
  rental_rackets?: boolean | null
  rental_rackets_system?: string | null
  gastro?: boolean | null
  gastro_name?: string | null
  gastro_maps_url?: string | null
  gastro_menu_url?: string | null
  gastro_hours?: string | null
  extras?: string | null
  cancellation_policy?: string | null
  cancellation_url?: string | null
  photos?: string[]
  related?: {
    operator: string
    city: string
    same_operator: RelatedVenue[]
    same_city: RelatedVenue[]
  }
}

export interface Tournament {
  source: string
  source_id: string
  source_url: string
  title: string
  venue_name: string
  city: string
  bundesland: string
  bezirk: string | null
  starts_at: string | null
  ends_at: string | null
  weekday: string
  category: string
  competition: string
  participants_current: number
  participants_max: number
  participants_waitlist: number
  registration_opens_at: string | null
  registration_closes_at: string | null
  status: "open" | "full" | "not_open_yet" | "closed" | "cancelled" | "unknown"
  first_seen_at: string | null
  last_seen_at: string | null
  partner_name?: string | null
  partner_slug?: string | null
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
