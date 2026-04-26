import type { Region, Venue } from "../types"
import VenueRow from "./VenueRow"

const REGION_DISPLAY: Record<Region, string> = {
  "Bad Voeslau": "Bad Vöslau",
  "Wien Sued":   "Wien Süd",
  "Wien":        "Wien",
  "NOE Sued":    "NÖ Süd",
}

interface Props {
  region: Region
  venues: Venue[]
}

export default function RegionGroup({ region, venues }: Props) {
  return (
    <div className="mb-4">
      <div className="px-4 py-2 bg-gray-800">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">
          {REGION_DISPLAY[region]}
        </h2>
      </div>
      <div className="bg-gray-900 divide-y divide-gray-800">
        {venues.map((venue) => (
          <VenueRow key={venue.id} venue={venue} />
        ))}
      </div>
    </div>
  )
}
