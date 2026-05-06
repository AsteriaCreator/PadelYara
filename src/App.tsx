import { useState, useRef, useEffect } from "react"
import type { Region, Venue, SearchParams } from "./types"
import { REGION_ORDER } from "./constants"
import { fetchAvailability, type GeoParams } from "./api"
import { geocode } from "./geocode"
import SearchCard from "./components/SearchCard"
import RegionGroup from "./components/RegionGroup"
import VenueRow from "./components/VenueRow"

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
  const [flatResults, setFlatResults] = useState<Venue[]>([])
  const [isGeoMode, setIsGeoMode] = useState(false)
  const [isLoading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)
  const [selectedRegion, setSelectedRegion] = useState<Region | "">("")

  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  function cancelRefresh() {
    if (refreshTimer.current) {
      clearTimeout(refreshTimer.current)
      refreshTimer.current = null
    }
  }

  useEffect(() => cancelRefresh, [])

  async function onSearch(params: SearchParams) {
    if (isLoading) return
    cancelRefresh()
    setLoading(true)
    setError(null)

    let geo: GeoParams | undefined
    if (params.location) {
      const coords = await geocode(params.location)
      if (!coords) {
        setError("Ort nicht gefunden — bitte PLZ oder Ortsname prüfen")
        setLoading(false)
        return
      }
      geo = { ...coords, radius: params.radius }
    }

    try {
      const res = await fetchAvailability(params, geo)
      if (!res.ok) {
        setError(res.error ?? "Unbekannter Fehler")
        return
      }
      if (geo) {
        setIsGeoMode(true)
        setFlatResults(res.results)
      } else {
        setIsGeoMode(false)
        setGrouped(groupByRegion(res.results))
        setSelectedRegion(params.region)
      }
      setSearched(true)
      if (res.availability_pending) {
        refreshTimer.current = setTimeout(async () => {
          refreshTimer.current = null
          const refreshed = await fetchAvailability(params, geo).catch(() => null)
          if (!refreshed?.ok) return
          if (geo) {
            setFlatResults(refreshed.results)
          } else {
            setGrouped(groupByRegion(refreshed.results))
          }
        }, 12_000)
      }
    } catch {
      setError("Verbindung fehlgeschlagen")
    } finally {
      setLoading(false)
    }
  }

  const sortedRegions = selectedRegion
    ? [selectedRegion, ...REGION_ORDER.filter((r) => r !== selectedRegion)]
    : REGION_ORDER

  return (
    <div className="min-h-screen" style={{ backgroundColor: "#080810" }}>
      <div className="max-w-2xl mx-auto px-4 py-6">
        <h1 className="text-white text-xl font-bold mb-6">Padel Checker</h1>
        <SearchCard onSearch={onSearch} isLoading={isLoading} />

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        {searched && !isLoading && !error && isGeoMode && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800 mb-4">
            {flatResults.map((venue) => (
              <VenueRow key={venue.id} venue={venue} pollingExpired={false} />
            ))}
          </div>
        )}

        {searched && !isLoading && !error && !isGeoMode &&
          sortedRegions.map((region) =>
            grouped[region]?.length ? (
              <RegionGroup key={region} region={region} venues={grouped[region]} pollingExpired={false} />
            ) : null
          )}
      </div>
    </div>
  )
}
