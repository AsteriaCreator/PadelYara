import { useState, useRef, useEffect } from "react"
import type { Venue, SearchParams } from "./types"
import { fetchAvailability, type GeoParams } from "./api"
import { geocode } from "./geocode"
import SearchCard from "./components/SearchCard"
import VenueRow from "./components/VenueRow"
import SkeletonRow from "./components/SkeletonRow"

const SKELETON_COUNT = 5
const ET_BATCH = 5

/** Merge two result lists by venue id, preserving existing order and appending newcomers. */
function mergeResults(existing: Venue[], incoming: Venue[]): Venue[] {
  const map = new Map(existing.map((v) => [v.id, v]))
  const existingIds = new Set(existing.map((v) => v.id))
  for (const v of incoming) map.set(v.id, v)
  return [
    ...existing.map((v) => map.get(v.id)!),
    ...incoming.filter((v) => !existingIds.has(v.id)),
  ]
}

export default function App() {
  const [results, setResults]               = useState<Venue[]>([])
  const [isLoading, setLoading]             = useState(false)
  const [isLoadingMore, setLoadingMore]     = useState(false)
  const [hasMore, setHasMore]               = useState(false)
  const [etOffset, setEtOffset]             = useState(0)
  const [error, setError]                   = useState<string | null>(null)
  const [searched, setSearched]             = useState(false)
  const [pollingExpired, setPollingExpired] = useState(false)
  const [lastUpdated, setLastUpdated]       = useState<number | null>(null)
  const [secondsSince, setSecondsSince]     = useState(0)

  const refreshTimer  = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastParamsRef = useRef<SearchParams | null>(null)
  const lastGeoRef    = useRef<GeoParams | undefined>(undefined)

  function cancelRefresh() {
    if (refreshTimer.current) {
      clearTimeout(refreshTimer.current)
      refreshTimer.current = null
    }
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
  // Always polls et_offset=0 (initial batch); merges into the accumulated list.
  function scheduleRefresh(params: SearchParams, geo: GeoParams | undefined, attempt: number) {
    const delay = attempt === 1 ? 15_000 : 45_000
    refreshTimer.current = setTimeout(async () => {
      refreshTimer.current = null
      const refreshed = await fetchAvailability(params, geo, 0).catch(() => null)
      if (!refreshed?.ok) {
        setPollingExpired(true)
        return
      }
      setResults((prev) => mergeResults(prev, refreshed.results))
      setLastUpdated(Date.now())
      if (refreshed.availability_pending && attempt < 2) {
        scheduleRefresh(params, geo, attempt + 1)
      } else {
        if (refreshed.availability_pending) setPollingExpired(true)
      }
    }, delay)
  }

  async function onSearch(params: SearchParams) {
    if (isLoading) return
    cancelRefresh()
    setLoading(true)
    setError(null)
    setHasMore(false)
    setEtOffset(0)

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

    lastParamsRef.current = params
    lastGeoRef.current    = geo

    try {
      const res = await fetchAvailability(params, geo, 0)
      if (!res.ok) {
        setError(res.error ?? "Unbekannter Fehler")
        return
      }
      setResults(res.results)
      setHasMore(res.has_more ?? false)
      setLastUpdated(Date.now())
      setSearched(true)
      if (res.availability_pending) {
        scheduleRefresh(params, geo, 1)
      }
    } catch {
      setError("Verbindung fehlgeschlagen")
    } finally {
      setLoading(false)
    }
  }

  async function onLoadMore() {
    if (!lastParamsRef.current || isLoadingMore) return
    setLoadingMore(true)
    const nextOffset = etOffset + ET_BATCH
    try {
      const res = await fetchAvailability(lastParamsRef.current, lastGeoRef.current, nextOffset)
      if (!res.ok) return
      setResults((prev) => mergeResults(prev, res.results))
      setHasMore(res.has_more ?? false)
      setEtOffset(nextOffset)
      setLastUpdated(Date.now())
      // One-shot poll for any pending results in this batch
      if (res.availability_pending) {
        setTimeout(async () => {
          const polled = await fetchAvailability(
            lastParamsRef.current!,
            lastGeoRef.current,
            nextOffset,
          ).catch(() => null)
          if (polled?.ok) {
            setResults((prev) => mergeResults(prev, polled.results))
            setLastUpdated(Date.now())
          }
        }, 15_000)
      }
    } finally {
      setLoadingMore(false)
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

        {searched && !isLoading && !error && results.length > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800 mb-4">
            {results.map((venue) => (
              <VenueRow key={venue.id} venue={venue} pollingExpired={pollingExpired} />
            ))}
          </div>
        )}

        {isLoadingMore && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800 mb-4">
            {Array.from({ length: ET_BATCH }).map((_, i) => (
              <SkeletonRow key={`more-${i}`} />
            ))}
          </div>
        )}

        {hasMore && !isLoadingMore && !isLoading && searched && (
          <button
            onClick={onLoadMore}
            className="w-full py-3 rounded-xl border border-gray-700 text-gray-400 text-sm hover:border-gray-500 hover:text-gray-200 transition-colors mb-4 cursor-pointer"
          >
            Mehr Ergebnisse
          </button>
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
