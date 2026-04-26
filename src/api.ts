import type { SearchParams, SearchResponse, Venue } from "./types"

const MOCK_VENUES: Venue[] = [
  // ── Bad Voeslau ──────────────────────────────────────────────
  { id: "padelzone-traiskirchen", name: "Padelzone Traiskirchen", region: "Bad Voeslau", court_type: "indoor", platform: "Eversports", priority: 1, booking_url: "https://www.eversports.at/sb/padelzone-traiskirchen", status: "free", error: null, weather: { icon: "cloud", desc: "Partly cloudy", temp: 16, rain_prob: 20, code: 801 } },
  { id: "padel4fun-tattendorf", name: "Padel4Fun Tattendorf", region: "Bad Voeslau", court_type: "indoor", platform: "eTennis", priority: 2, booking_url: "https://reservierung.padel4fun.at/reservierung?c=4029", status: "free", error: null, weather: { icon: "cloud", desc: "Partly cloudy", temp: 16, rain_prob: 20, code: 801 } },
  { id: "padel4fun-baden", name: "Padel4Fun Baden", region: "Bad Voeslau", court_type: "outdoor", platform: "eTennis", priority: 3, booking_url: "https://reservierung.padel4fun.at/reservierung?c=3533", status: "busy", error: null, weather: { icon: "cloud", desc: "Partly cloudy", temp: 16, rain_prob: 20, code: 801 } },
  { id: "padel-ebreichsdorf", name: "Padel Ebreichsdorf", region: "Bad Voeslau", court_type: "outdoor", platform: "Eversports", priority: 5, booking_url: "https://www.eversports.at/sb/padel-tennis-ebreichsdorf-og", status: "unknown", error: null, weather: { icon: "cloud", desc: "Partly cloudy", temp: 16, rain_prob: 20, code: 801 } },
  { id: "padel4fun-wr-neudorf", name: "Padel4Fun Wr. Neudorf", region: "Bad Voeslau", court_type: "outdoor", platform: "eTennis", priority: 6, booking_url: "https://reservierung.padel4fun.at/reservierung?c=2859", status: "free", error: null, weather: { icon: "cloud", desc: "Partly cloudy", temp: 16, rain_prob: 20, code: 801 } },

  // ── Wien Sued ─────────────────────────────────────────────────
  { id: "padeldome-alt-erlaa", name: "Padeldome Alt Erlaa", region: "Wien Sued", court_type: "indoor", platform: "eTennis", priority: 1, booking_url: "https://www.padeldome.wien/reservierung?c=2668", status: "free", error: null, weather: { icon: "sun", desc: "Sunny", temp: 18, rain_prob: 10, code: 800 } },
  { id: "padeldome-erdberg", name: "Padeldome Erdberg", region: "Wien Sued", court_type: "indoor", platform: "eTennis", priority: 1, booking_url: "https://www.padeldome.wien/reservierung?c=2665", status: "busy", error: null, weather: { icon: "sun", desc: "Sunny", temp: 18, rain_prob: 10, code: 800 } },
  { id: "padel4fun-la-ville", name: "Padel4Fun La Ville", region: "Wien Sued", court_type: "outdoor", platform: "eTennis", priority: 2, booking_url: "https://reservierung.padel4fun.at/reservierung?c=2946", status: "free", error: null, weather: { icon: "sun", desc: "Sunny", temp: 18, rain_prob: 10, code: 800 } },
  { id: "europahalle", name: "Europahalle", region: "Wien Sued", court_type: "indoor", platform: "eTennis", priority: 3, booking_url: "https://reservierung.europahalle.at/reservierung?c=4797", status: "busy", error: null, weather: { icon: "sun", desc: "Sunny", temp: 18, rain_prob: 10, code: 800 } },
  { id: "padelzone-wien-cc-wienerberg", name: "Padelzone Wien C&C Wienerberg", region: "Wien Sued", court_type: "indoor", platform: "Eversports", priority: 7, booking_url: "https://www.eversports.at/sb/padelzone-wien-or-candc-wienerberg", status: "free", error: null, weather: { icon: "sun", desc: "Sunny", temp: 18, rain_prob: 10, code: 800 } },

  // ── Wien ──────────────────────────────────────────────────────
  { id: "padeldome-alte-donau-outdoor", name: "Padeldome Alte Donau outdoor", region: "Wien", court_type: "outdoor", platform: "eTennis", priority: 2, booking_url: "https://www.padeldome.wien/reservierung?c=3218", status: "free", error: null, weather: { icon: "sun", desc: "Clear", temp: 20, rain_prob: 0, code: 800 } },
  { id: "sportcenter-donaucity", name: "Sportcenter Donaucity", region: "Wien", court_type: "outdoor", platform: "Eversports", priority: 5, booking_url: "https://www.eversports.at/sb/sportcenter-donaucity", status: "busy", error: null, weather: { icon: "sun", desc: "Clear", temp: 20, rain_prob: 0, code: 800 } },
  { id: "padel-union-wien", name: "Padel Union Wien", region: "Wien", court_type: "outdoor", platform: "eTennis", priority: 6, booking_url: "https://www.padelunion.at/reservierung?c=3776", status: "free", error: null, weather: { icon: "sun", desc: "Clear", temp: 20, rain_prob: 0, code: 800 } },
  { id: "padelbase-wien", name: "Padelbase Wien", region: "Wien", court_type: "outdoor", platform: "eTennis", priority: 7, booking_url: "https://www.buchung-padelbase.at/reservierung?c=3532", status: "error", error: "Booking system unavailable", weather: null },
  { id: "racketworld-wien", name: "Racketworld Wien", region: "Wien", court_type: "indoor", platform: "eTennis", priority: 8, booking_url: "https://www.racketworld.wien/reservierung?c=3660", status: "busy", error: null, weather: { icon: "sun", desc: "Clear", temp: 20, rain_prob: 0, code: 800 } },
  { id: "padeldome-suessenbrunn", name: "Padeldome Suessenbrunn", region: "Wien", court_type: "indoor", platform: "eTennis", priority: 8, booking_url: "https://www.padeldome.wien/reservierung?c=2667", status: "free", error: null, weather: { icon: "sun", desc: "Clear", temp: 20, rain_prob: 0, code: 800 } },
  { id: "padelzone-wien-floridsdorf", name: "Padelzone Wien Floridsdorf", region: "Wien", court_type: "indoor+outdoor", platform: "Eversports", priority: 8, booking_url: "https://www.eversports.at/sb/padelzone-wien-or-floridsdorf-powered-by-cupra", status: "free", error: null, weather: { icon: "sun", desc: "Clear", temp: 20, rain_prob: 0, code: 800 } },
  { id: "padeldome-alte-donau-indoor", name: "Padeldome Alte Donau indoor", region: "Wien", court_type: "indoor", platform: "eTennis", priority: 8, booking_url: "https://www.padeldome.wien/reservierung?c=3216", status: "unknown", error: null, weather: { icon: "sun", desc: "Clear", temp: 20, rain_prob: 0, code: 800 } },
  { id: "padelzone-wien-sportinsel", name: "Padelzone Wien Sportinsel", region: "Wien", court_type: "outdoor", platform: "Eversports", priority: 8, booking_url: "https://www.eversports.at/sb/padelzone-wien-or-sportinsel", status: "busy", error: null, weather: { icon: "sun", desc: "Clear", temp: 20, rain_prob: 0, code: 800 } },

  // ── NOE Sued ──────────────────────────────────────────────────
  { id: "padelzone-wr-neustadt-arena-27", name: "Padelzone Wr. Neustadt Arena 27", region: "NOE Sued", court_type: "indoor", platform: "Eversports", priority: 4, booking_url: "https://www.eversports.at/sb/padelzone-wiener-neustadt-or-arena-27", status: "free", error: null, weather: { icon: "cloud", desc: "Overcast", temp: 14, rain_prob: 35, code: 804 } },
  { id: "padelzone-sprungart", name: "Padelzone Sprungart", region: "NOE Sued", court_type: "indoor", platform: "Eversports", priority: 9, booking_url: "https://www.eversports.at/sb/padelzone-wiener-neustadt-or-sprungart", status: "busy", error: null, weather: { icon: "cloud", desc: "Overcast", temp: 14, rain_prob: 35, code: 804 } },
]

export async function fetchAvailability(
  params: SearchParams
): Promise<SearchResponse> {
  await new Promise((resolve) => setTimeout(resolve, 600))
  const results = MOCK_VENUES.filter((v) => {
  if (params.court_type === "both") return true
  if (params.court_type === "indoor") return v.court_type === "indoor"
  if (params.court_type === "outdoor") return v.court_type === "outdoor"
  return true
})

return { ok: true, results, date: params.date, time: params.time }
}
