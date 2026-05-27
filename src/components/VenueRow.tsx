import { trackBookingClick } from "../api"
import type { Venue } from "../types"
import WeatherCell from "./WeatherCell"

const STATUS_STYLES: Record<string, string> = {
  free:                    "bg-green-900/40 text-green-400",
  busy:                    "bg-red-900/40 text-red-400",
  // pending_active: timer is running — pulse to signal active background work
  pending_active:          "bg-blue-900/40 text-blue-400 animate-pulse",
  // pending (fallback, should not appear in normal operation)
  pending:                 "bg-blue-900/40 text-blue-400 animate-pulse",
  unknown:                 "bg-amber-900/40 text-amber-400",
  // check_failed: polling ended with this venue still unresolved
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
  unknown:                 "Konnte nicht geprüft werden",
  platform_check_required: "Konnte nicht geprüft werden",
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
}

export default function VenueRow({ venue, pollingActive }: Props) {
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

  const bookingLabel = venue.status === "free" ? "JETZT BUCHEN ↗" : "LINK ↗"
  const bookingStyle = venue.status === "free"
    ? "bg-green-600 hover:bg-green-500 text-white"
    : "bg-gray-700 hover:bg-gray-600 text-gray-300"

  return (
    <div className="px-4 py-3 border-b border-gray-700/50 last:border-0">
      {/* min-w-0 on the row is required so the truncate span can actually shrink.
          Without it, flex items default to min-width:auto and ignore overflow:hidden. */}
      <div className="flex items-center justify-between mb-1 min-w-0">
        <span className="font-medium text-white truncate min-w-0">{venue.name}</span>
        <div className="flex flex-col items-end shrink-0 ml-3">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLES[displayStatus]}`}>
            {STATUS_LABEL[displayStatus]}
          </span>
          {venue.time_adjusted && venue.adjustment_label && (
            <span className="text-xs text-amber-400 mt-0.5 whitespace-nowrap">
              {venue.adjustment_label}
            </span>
          )}
        </div>
      </div>
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex flex-wrap items-center gap-x-1.5 text-xs text-gray-500">
            <span>{venue.platform}</span>
            <span>·</span>
            <span>{venue.court_type}</span>
            {venue.distance_km != null && (
              <>
                <span>·</span>
                <span className="whitespace-nowrap">{venue.distance_km.toFixed(1)} km entfernt</span>
              </>
            )}
          </div>
          <WeatherCell weather={venue.weather} />
        </div>
        <a
          href={venue.booking_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => trackBookingClick(venue.id, venue.platform)}
          className={`text-xs font-semibold px-3 py-1 rounded shrink-0 whitespace-nowrap ${bookingStyle}`}
        >
          {bookingLabel}
        </a>
      </div>
    </div>
  )
}
