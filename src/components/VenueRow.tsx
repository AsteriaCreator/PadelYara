import { trackBookingClick } from "../api"
import type { Venue } from "../types"

const STATUS_STYLES: Record<string, string> = {
  free:                    "bg-green-900/40 text-green-400 font-semibold",
  busy:                    "bg-red-900/40 text-red-400",
  pending_active:          "bg-blue-900/40 text-blue-400 animate-pulse",
  pending:                 "bg-blue-900/40 text-blue-400 animate-pulse",
  unknown:                 "bg-amber-900/40 text-amber-400",
  check_failed:            "bg-amber-900/40 text-amber-400",
  phone_only:              "bg-blue-900/40 text-blue-400",
  platform_check_required: "bg-amber-900/40 text-amber-400",
  not_checked:             "bg-gray-800 text-gray-500",
  no_slot:                 "bg-red-900/40 text-red-400",
  error:                   "bg-orange-900/40 text-orange-400",
}

const STATUS_LABEL: Record<string, string> = {
  free:                    "Frei",
  busy:                    "Belegt",
  // While a poll timer is running — "noch" signals ongoing activity
  pending_active:          "Wird noch geprüft …",
  // Defensive fallback only; not shown in normal operation
  pending:                 "Wird noch geprüft …",
  // Structural failures — venue type/platform cannot be checked
  unknown:                 "Nicht online prüfbar",
  platform_check_required: "Nicht online prüfbar",
  // Polling ran out of attempts with this venue still unresolved
  // "noch nicht" vs "nicht" distinguishes timeout from structural failure
  check_failed:            "Konnte noch nicht geprüft werden",
  phone_only:              "Nur telefonisch",
  not_checked:             "Nicht geprüft",
  no_slot:                 "Kein Slot",
  error:                   "Fehler",
}

interface Props {
  venue: Venue
  pollingActive: boolean
  searchDate?: string
}

function etennisBookingUrl(baseUrl: string, dateStr: string): string {
  // eTennis interprets &t= as Vienna midnight (matches the backend scraper).
  // Derive Vienna's UTC offset at noon on that day (safe from DST transitions),
  // then subtract it from UTC midnight to get Vienna midnight.
  const [y, m, d] = dateStr.split("-").map(Number)
  const utcMidnight = Date.UTC(y, m - 1, d)
  const noonUtc = utcMidnight + 12 * 3600 * 1000
  const viennaHourAtNoon = parseInt(
    new Intl.DateTimeFormat("en-US", { timeZone: "Europe/Vienna", hour: "numeric", hour12: false })
      .format(new Date(noonUtc))
  )
  const offsetH = viennaHourAtNoon - 12  // +1 (CET) or +2 (CEST)
  return `${baseUrl}&t=${Math.floor((utcMidnight - offsetH * 3600 * 1000) / 1000)}`
}

export default function VenueRow({ venue, pollingActive, searchDate }: Props) {
  // Derive an honest display status for pending venues based on poll state.
  //
  //   pollingActive=true              → a timer is scheduled; show "Wird noch geprüft …"
  //   pollingExpired=true             → all attempts exhausted; show "Konnte noch nicht …"
  //   both false (no polling at all)  → treat as expired; show "Konnte noch nicht …"
  //
  // Non-pending statuses pass through unchanged.
  const displayStatus = venue.status === "pending"
    ? (pollingActive ? "pending_active" : "check_failed")
    : venue.status

  const courtIcon = venue.court_type === "indoor" ? "🏠" : venue.court_type === "outdoor" ? "🌳" : "🏠🌳"

  const bookingLabel = venue.status === "free" ? "JETZT BUCHEN →" : "LINK →"
  const bookingStyle = venue.status === "free"
    ? "font-bold text-[#080810] hover:opacity-90"
    : "bg-gray-800 hover:bg-gray-700 text-gray-500 border border-gray-700"

  return (
    <div className="px-4 py-3 border-b border-gray-700/50 last:border-0">
      {/* min-w-0 on the row is required so the truncate span can actually shrink.
          Without it, flex items default to min-width:auto and ignore overflow:hidden. */}
      <div className="flex items-center justify-between mb-1 min-w-0">
        <span className="font-semibold text-white truncate min-w-0 text-sm">{venue.name}</span>
        <div className="flex flex-col items-end shrink-0 ml-3">
          <div className="flex items-center gap-2">
            {venue.price_eur != null && (
              <span className="text-xs font-semibold text-white whitespace-nowrap">
                € {venue.price_eur}/h
              </span>
            )}
            <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_STYLES[displayStatus]}`}>
              {STATUS_LABEL[displayStatus]}
            </span>
          </div>
          {venue.time_adjusted && venue.adjustment_label && (
            <span className="text-xs text-amber-400 mt-0.5 whitespace-nowrap">
              {venue.adjustment_label}
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-x-2 text-xs text-gray-500 min-w-0">
          <span>{courtIcon} {venue.court_type}</span>
          {venue.distance_km != null && (
            <span className="whitespace-nowrap">📍 {venue.distance_km.toFixed(1)} km</span>
          )}
        </div>
        <a
          href={
            searchDate && venue.platform === "eTennis"
              ? etennisBookingUrl(venue.booking_url, searchDate)
              : venue.booking_url
          }
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => trackBookingClick(venue.id, venue.platform)}
          className={`text-xs font-semibold px-3 py-1.5 rounded shrink-0 whitespace-nowrap ${bookingStyle}`}
          style={venue.status === "free" ? { backgroundColor: "#d4f53c" } : undefined}
        >
          {bookingLabel}
        </a>
      </div>
    </div>
  )
}
