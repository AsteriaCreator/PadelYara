import { useState, useRef, useEffect } from "react"
import type { Region, Venue, SearchParams } from "./types"
import { REGION_ORDER } from "./constants"
import { fetchAvailability, type GeoParams } from "./api"
import { geocode } from "./geocode"
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

const POLL_INTERVAL_MS = 5_000
const POLL_MAX = 12   // 12 × 5s = 60s

export default function App() {
  const [grouped, setGrouped] = useState<GroupedVenues>({} as GroupedVenues)
  const [isLoading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)
  const [selectedRegion, setSelectedRegion] = useState<Region>(REGION_ORDER[0])

  const pollTimer  = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollCount  = useRef(0)
  const lastParams = useRef<SearchParams | null>(null)
  const lastGeo    = useRef<GeoParams | undefined>(undefined)

  function stopPolling() {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current)
      pollTimer.current = null
    }
  }

  async function doPoll() {
    const params = lastParams.current
    if (!params || pollCount.current >= POLL_MAX) { stopPolling(); return }
    pollCount.current += 1
    try {
      const res = await fetchAvailability(params, lastGeo.current)
      if (res.ok) {
        setGrouped(groupByRegion(res.results))
        if (!res.availability_pending) { stopPolling(); return }
      }
    } catch { /* ignore poll errors silently */ }
    pollTimer.current = setTimeout(doPoll, POLL_INTERVAL_MS)
  }

  // Clean up on unmount
  useEffect(() => stopPolling, [])

  async function onSearch(params: SearchParams) {
    stopPolling()
    pollCount.current = 0
    lastParams.current = params
    setLoading(true)
    setError(null)

    // Public mode if location text given; otherwise fall back to region mode
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
    lastGeo.current = geo

    try {
      const res = await fetchAvailability(params, geo)
      if (!res.ok) {
        setError(res.error ?? "Unbekannter Fehler")
        return
      }
      setGrouped(groupByRegion(res.results))
      setSelectedRegion(params.region)
      setSearched(true)
      if (res.availability_pending) {
        pollTimer.current = setTimeout(doPoll, POLL_INTERVAL_MS)
      }
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