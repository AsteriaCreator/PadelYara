import { useState } from "react"
import type { Region, Venue, SearchParams } from "./types"
import { REGION_ORDER } from "./constants"
import { fetchAvailability } from "./api"
import SearchCard from "./components/SearchCard"
import RegionGroup from "./components/RegionGroup"

type GroupedVenues = Record<Region, Venue[]>

function groupByRegion(venues: Venue[]): GroupedVenues {
  const groups = {} as GroupedVenues
  for (const venue of venues) {
    if (!groups[venue.region]) groups[venue.region] = []
    groups[venue.region].push(venue)
  }
  return groups
}

export default function App() {
  const [grouped, setGrouped] = useState<GroupedVenues>({} as GroupedVenues)
  const [isLoading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)
  const [selectedRegion, setSelectedRegion] = useState<Region>(REGION_ORDER[0])

  async function onSearch(params: SearchParams) {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchAvailability(params)
      if (!res.ok) {
        setError(res.error ?? "Unbekannter Fehler")
        return
      }
      setGrouped(groupByRegion(res.results))
      setSelectedRegion(params.region)
      setSearched(true)
    } catch {
      setError("Verbindung fehlgeschlagen")
    } finally {
      setLoading(false)
    }
  }

  const sortedRegions = [
    selectedRegion,
    ...REGION_ORDER.filter((r) => r !== selectedRegion),
  ]

  return (
    <div className="min-h-screen" style={{ backgroundColor: "#080810" }}>
      <div className="max-w-2xl mx-auto px-4 py-6">
        <h1 className="text-white text-xl font-bold mb-6">Padel Checker</h1>
        <SearchCard onSearch={onSearch} isLoading={isLoading} />

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        {searched &&
          !isLoading &&
          !error &&
          sortedRegions.map((region) =>
            grouped[region]?.length ? (
              <RegionGroup key={region} region={region} venues={grouped[region]} />
            ) : null
          )}
      </div>
    </div>
  )
}