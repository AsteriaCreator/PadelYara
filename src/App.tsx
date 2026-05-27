import { useState, useRef, useEffect } from "react"
import type { Venue, SearchParams } from "./types"
import { fetchAvailability, type GeoParams } from "./api"
import { geocode, GeocodeTimeoutError } from "./geocode"
import SearchCard from "./components/SearchCard"
import VenueRow from "./components/VenueRow"
import SkeletonRow from "./components/SkeletonRow"
import ImprintModal from "./components/ImprintModal"

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
  const [pollingExpired, setPollingExpired]         = useState(false)
  const [lastUpdated, setLastUpdated]               = useState<number | null>(null)
  const [secondsSince, setSecondsSince]             = useState(0)
  const [bookingWindowNotice, setBookingWindowNotice] = useState<string | null>(null)
  const [searchLabel, setSearchLabel]               = useState<string | null>(null)
  const [showImprint, setShowImprint]       = useState(false)

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

  // Polling schedule (from first response):
  //   attempt 1 → +15 s  (catches warm-server eTennis ~40-50 s scrapes on poll 2)
  //   attempt 2 → +30 s  (T+45 s total — covers warm Render scrape completion)
  //   attempt 3 → +60 s  (T+105 s total — covers cold-start Render where browser
  //                        launch adds 20-30 s and scrape takes 60-80 s)
  // Max 3 auto-refreshes. Always polls et_offset=0; merges into the accumulated list.
  function scheduleRefresh(params: SearchParams, geo: GeoParams | undefined, attempt: number) {
    const delay = attempt === 1 ? 15_000 : attempt === 2 ? 30_000 : 60_000
    refreshTimer.current = setTimeout(async () => {
      refreshTimer.current = null
      const refreshed = await fetchAvailability(params, geo, 0).catch(() => null)
      if (!refreshed?.ok) {
        setPollingExpired(true)
        return
      }
      setResults((prev) => mergeResults(prev, refreshed.results))
      setLastUpdated(Date.now())
      if (refreshed.availability_pending && attempt < 3) {
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
    setSearchLabel(null)
    setBookingWindowNotice(null)

    let coords: { lat: number; lon: number } | null
    try {
      coords = await geocode(params.location!)
    } catch (err) {
      setError(
        err instanceof GeocodeTimeoutError
          ? "Ortssuche hat zu lange gedauert — bitte nochmal versuchen."
          : "Verbindung fehlgeschlagen"
      )
      setLoading(false)
      return
    }
    if (!coords) {
      setError("Ort nicht gefunden. Bitte gib den vollständigen Ortsnamen oder die PLZ ein.")
      setLoading(false)
      return
    }

    // Geocoding succeeded — persist the location for next visit
    try {
      localStorage.setItem("padel_location", params.location!)
      localStorage.setItem("padel_radius", String(params.radius))
    } catch { /* private-mode Safari */ }

    const geo: GeoParams = { ...coords, radius: params.radius }

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
      setSearchLabel(`${params.location} · ${params.radius} km Umkreis`)
      setBookingWindowNotice(res.booking_window_notice ?? null)
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
    <div className="min-h-screen overflow-x-hidden" style={{ backgroundColor: "#080810" }}>
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

        {searched && !isLoading && searchLabel && (
          <p className="text-xs text-gray-600 mb-1 px-1 tracking-wide uppercase">
            {searchLabel}
          </p>
        )}

        {searched && !isLoading && !error && results.length > 0 && lastParamsRef.current && (
          <p className="text-xs text-gray-500 mb-2 px-1">
            {results.length === 1
              ? `1 Ergebnis im Umkreis von ${lastParamsRef.current.radius} km`
              : `${results.length} Ergebnisse im Umkreis von ${lastParamsRef.current.radius} km`}
          </p>
        )}

        {searched && !isLoading && bookingWindowNotice && (
          <p className="text-xs text-gray-500 mb-3 px-1">
            ℹ️ {bookingWindowNotice}
          </p>
        )}

        {searched && !isLoading && !error && results.length > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800 mb-4">
            {results.map((venue) => (
              <VenueRow key={venue.id} venue={venue} pollingExpired={pollingExpired} />
            ))}
          </div>
        )}

        {searched && !isLoading && !error && results.length === 0 && (
          <p className="text-gray-500 text-sm px-1 mb-4">
            Keine Ergebnisse in diesem Umkreis gefunden.
          </p>
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

      <footer className="text-center py-6">
        <button
          onClick={() => setShowImprint(true)}
          className="text-xs text-gray-600 hover:text-gray-400 transition-colors"
        >
          Impressum
        </button>
      </footer>

      {showImprint && <ImprintModal onClose={() => setShowImprint(false)} />}
    </div>
  )
}
