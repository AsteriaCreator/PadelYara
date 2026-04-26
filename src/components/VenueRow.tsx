import type { Venue } from "../types"
import WeatherCell from "./WeatherCell"

const STATUS_STYLES: Record<string, string> = {
  free:    "bg-green-900/40 text-green-400",
  busy:    "bg-red-900/40 text-red-400",
  error:   "bg-orange-900/40 text-orange-400",
  unknown: "bg-gray-800 text-gray-500",
}

const STATUS_LABEL: Record<string, string> = {
  free:    "Frei",
  busy:    "Belegt",
  error:   "Fehler",
  unknown: "Unbekannt",
}

interface Props {
  venue: Venue
}

export default function VenueRow({ venue }: Props) {
  const bookingLabel = venue.status === "free" ? "JETZT BUCHEN ↗" : "LINK ↗"
  const bookingStyle = venue.status === "free"
    ? "bg-green-600 hover:bg-green-500 text-white"
    : "bg-gray-700 hover:bg-gray-600 text-gray-300"

  return (
    <div className="px-4 py-3 border-b border-gray-700/50 last:border-0">
      <div className="flex items-center justify-between mb-1">
        <span className="font-medium text-white truncate">{venue.name}</span>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ml-3 ${STATUS_STYLES[venue.status]}`}>
          {STATUS_LABEL[venue.status]}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>{venue.platform}</span>
          <span>·</span>
          <span>{venue.court_type}</span>
          <span>·</span>
          <WeatherCell weather={venue.weather} />
        </div>
        <a
          href={venue.booking_url}
          target="_blank"
          rel="noopener noreferrer"
          className={`text-xs font-semibold px-3 py-1 rounded shrink-0 ml-3 ${bookingStyle}`}
        >
          {bookingLabel}
        </a>
      </div>
    </div>
  )
}
