import { useState, useRef, useEffect } from "react"
import type { Venue, SearchParams } from "./types"
import { fetchAvailability, type GeoParams } from "./api"
import { geocode } from "./geocode"
import SearchCard from "./components/SearchCard"
import VenueRow from "./components/VenueRow"
import SkeletonRow from "./components/SkeletonRow"

const SKELETON_COUNT = 5

export default function App() {
  const [results, setResults]               = useState<Venue[]>([])
  const [isLoading, setLoading]             = useState(false)
  const [error, setError]                   = useState<string | null>(null)
  const [searched, setSearched]             = useState(false)
  const [isPending, setIsPending]           = useState(false)
  const [pollingExpired, setPollingExpired] = useState(false)
  const [lastUpdated, setLastUpdated]       = useState<number | null>(null)
  const [secondsSince, setSecondsSince]     = useState(0)

  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  function cancelRefresh() {
    if (refreshTimer.current) {
      clearTimeout(refreshTimer.current)
      refreshTimer.current = null
    }
    setIsPending(false)
    setPollingExpired(false)
  }

  useEffect(() => cancelRefresh, [])

  // Tick the "last updated" counter every second
  useEffect(() => {
    if (!lastUpdated) return
    setSecondsSince(0)
    const interval = setInterval(() => {
      setSecondsSince(Math.floor((Date.now() - lastUpdated) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [lastUpdated])

  // attempt=1 fires after 15s, attempt=2 fires after 45s. Max 2 auto-refreshes.
  function scheduleRefresh(params: SearchParams, geo: GeoParams | undefined, attempt: number) {
    const delay = attempt === 1 ? 15_000 : 45_000
    refreshTimer.current = setTimeout(async () => {
      refreshTimer.current = null
      const refreshed = await fetchAvailability(params, geo).catch(() => null)
      if (!refreshed?.ok) {
        setIsPending(false)
        setPollingExpired(true)
        return
      }
      setResults(refreshed.results)
      setLastUpdated(Date.now())
      if (refreshed.availability_pending && attempt < 2) {
        scheduleRefresh(params, geo, attempt + 1)
      } else {
        setIsPending(false)
        if (refreshed.availability_pending) setPollingExpired(true)
      }
    }, delay)
  }

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
      setResults(res.results)
      setLastUpdated(Date.now())
      setSearched(true)
      if (res.availability_pending) {
        setIsPending(true)
        scheduleRefresh(params, geo, 1)
      }
    } catch {
      setError("Verbindung fehlgeschlagen")
    } finally {
      setLoading(false)
    }
  }

  const skeletonCount = results.length > 0 ? results.length : SKELETON_COUNT

  return (
    <div className="min-h-screen" style={{ backgroundColor: "#080810" }}>
      <div className="max-w-2xl mx-auto px-4 py-6">
        <h1 className="text-white text-xl font-bold mb-6">Padel Checker</h1>
        <SearchCard onSearch={onSearch} isLoading={isLoading} />

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        {isLoading && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800 mb-4">
            {Array.from({ length: skeletonCount }).map((_, i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        )}

        {searched && !isLoading && !error && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800 mb-4">
            {results.map((venue) => (
              <VenueRow key={venue.id} venue={venue} pollingExpired={pollingExpired} />
            ))}
          </div>
        )}

        {searched && !isLoading && lastUpdated && (
          <p className="text-gray-600 text-xs text-right mb-4">
            Zuletzt aktualisiert {secondsSince < 10 ? "gerade eben" : `vor ${secondsSince} Sekunden`}
          </p>
        )}
      </div>
    </div>
  )
}
