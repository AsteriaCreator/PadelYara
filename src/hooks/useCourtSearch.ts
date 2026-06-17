import { useState, useRef, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import type { Venue, SearchParams, Weather } from "../types"
import { fetchAvailability, fetchWeather, type GeoParams } from "../api"
import { geocode, GeocodeTimeoutError } from "../geocode"

export const SKELETON_COUNT = 5
export const ET_BATCH = 5

// Fibonacci-ish backoff: catches Eversports (~3-5s), stragglers (8s),
// warm eTennis (20s), warm backend (45s), cold-start (105s)
const POLL_DELAYS = [3_000, 5_000, 12_000, 25_000, 60_000]

function mergeResults(existing: Venue[], incoming: Venue[]): Venue[] {
  const map = new Map(existing.map((v) => [v.id, v]))
  const existingIds = new Set(existing.map((v) => v.id))
  for (const v of incoming) map.set(v.id, v)
  return [
    ...existing.map((v) => map.get(v.id)!),
    ...incoming.filter((v) => !existingIds.has(v.id)),
  ]
}

export function useCourtSearch() {
  const [searchParams, setSearchParams] = useSearchParams()

  const urlLocation  = searchParams.get("ort") ?? ""
  const urlDate      = searchParams.get("datum") ?? ""
  const urlTime      = searchParams.get("zeit") ?? ""
  const urlRadius    = Number(searchParams.get("radius")) || 0
  const _urlDurRaw   = searchParams.get("dur") ?? ""
  const urlDurations: number[] = _urlDurRaw
    ? _urlDurRaw.split(",").map(Number).filter(n => [60, 90, 120].includes(n))
    : []

  // Set by the Padelrevier map's "Verfügbarkeit prüfen" jump — highlight + scroll
  // to this venue once results render. Captured in state so the search's URL
  // rewrite (which drops the param) doesn't clear it.
  const [highlightId, setHighlightId] = useState(() => searchParams.get("venueId") ?? "")
  const didScrollRef = useRef(false)

  // The map jump also passes the venue's exact coords so the search centers on
  // it directly (no geocoding the venue name). Used only while the pre-filled
  // location is unchanged; once the user edits the field, normal geocoding resumes.
  const prefillCoordsRef = useRef<{ location: string; lat: number; lon: number } | null>(
    (() => {
      const lat = Number(searchParams.get("lat"))
      const lon = Number(searchParams.get("lon"))
      return urlLocation && searchParams.get("lat") && searchParams.get("lon") && !isNaN(lat) && !isNaN(lon)
        ? { location: urlLocation, lat, lon }
        : null
    })()
  )

  const [results, setResults]                         = useState<Venue[]>([])
  const [isLoading, setLoading]                       = useState(false)
  const [isLoadingMore, setLoadingMore]               = useState(false)
  const [hasMore, setHasMore]                         = useState(false)
  const [etOffset, setEtOffset]                       = useState(0)
  const [error, setError]                             = useState<string | null>(null)
  const [searched, setSearched]                       = useState(false)
  const [pollingActive, setPollingActive]             = useState(false)
  const [lastParams, setLastParams]                   = useState<SearchParams | null>(null)
  const activePollsRef                                = useRef(0)
  const [lastUpdated, setLastUpdated]                 = useState<number | null>(null)
  const [secondsSince, setSecondsSince]               = useState(0)
  const [bookingWindowNotice, setBookingWindowNotice] = useState<string | null>(null)
  const [searchLabel, setSearchLabel]                 = useState<string | null>(null)
  const [searchWeather, setSearchWeather]             = useState<Weather | null>(null)
  const [courtFilter, setCourtFilter]                 = useState<{ indoor: boolean; outdoor: boolean }>({ indoor: true, outdoor: true })
  const [statusFilter, setStatusFilter]               = useState<{ frei: boolean; belegt: boolean }>({ frei: true, belegt: true })

  const refreshTimer  = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastParamsRef = useRef<SearchParams | null>(null)
  const lastGeoRef    = useRef<GeoParams | undefined>(undefined)

  function cancelRefresh() {
    if (refreshTimer.current) {
      clearTimeout(refreshTimer.current)
      refreshTimer.current = null
    }
    activePollsRef.current = 0
    setPollingActive(false)
  }

  useEffect(() => cancelRefresh, [])

  // Auto-trigger search when URL params are present (shared link)
  useEffect(() => {
    if (urlLocation && urlDate && urlTime && urlRadius) {
      onSearch({
        location: urlLocation, date: urlDate, time: urlTime, radius: urlRadius, court_type: "both",
        ...(urlDurations.length > 0 ? { durations: urlDurations } : {}),
      })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to + briefly highlight the venue jumped to from the Padelrevier map
  useEffect(() => {
    if (!highlightId || didScrollRef.current) return
    const el = document.getElementById(`venue-${highlightId}`)
    if (!el) return
    didScrollRef.current = true
    el.scrollIntoView({ behavior: "smooth", block: "center" })
    const t = setTimeout(() => setHighlightId(""), 3500)
    return () => clearTimeout(t)
  }, [results, highlightId])

  // Tick the "last updated" counter every second
  useEffect(() => {
    if (!lastUpdated) return
    const interval = setInterval(() => {
      setSecondsSince(Math.floor((Date.now() - lastUpdated) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [lastUpdated])

  // Inject structured data for search engines / AI assistants whenever results change
  useEffect(() => {
    const existing = document.getElementById("jsonld-venues")
    if (results.length === 0) {
      existing?.remove()
      return
    }
    const items = results.map((v, i) => ({
      "@type": "SportsActivityLocation",
      "position": i + 1,
      "name": v.name,
      ...(v.public_url ? { "url": v.public_url } : {}),
      ...(v.price_eur != null ? {
        "offers": {
          "@type": "Offer",
          "price": v.price_eur,
          "priceCurrency": "EUR",
          "availability": v.status === "free" ? "https://schema.org/InStock" : "https://schema.org/SoldOut",
        }
      } : {}),
      "amenityFeature": {
        "@type": "LocationFeatureSpecification",
        "name": v.court_type === "indoor" ? "Indoor Padel" : v.court_type === "outdoor" ? "Outdoor Padel" : "Indoor & Outdoor Padel",
        "value": true,
      }
    }))
    const script = existing ?? document.createElement("script")
    script.id = "jsonld-venues"
    script.setAttribute("type", "application/ld+json")
    script.textContent = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "ItemList",
      "name": "Padel Courts in Österreich",
      "numberOfItems": results.length,
      "itemListElement": items,
    })
    if (!existing) document.head.appendChild(script)
  }, [results])

  function scheduleRefresh(params: SearchParams, geo: GeoParams | undefined, attempt: number) {
    setPollingActive(true)
    const delay = POLL_DELAYS[attempt - 1] ?? 60_000
    refreshTimer.current = setTimeout(async () => {
      refreshTimer.current = null
      const refreshed = await fetchAvailability(params, geo, 0).catch(() => null)
      if (!refreshed?.ok) {
        setPollingActive(false)
        return
      }
      setResults((prev) => mergeResults(prev, refreshed.results))
      setLastUpdated(Date.now())
      if (refreshed.availability_pending && attempt < POLL_DELAYS.length) {
        scheduleRefresh(params, geo, attempt + 1)
      } else {
        setPollingActive(false)
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
    setSearchWeather(null)
    setBookingWindowNotice(null)

    let coords: { lat: number; lon: number } | null
    const pre = prefillCoordsRef.current
    if (pre && params.location === pre.location) {
      coords = { lat: pre.lat, lon: pre.lon }
    } else {
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
    }
    if (!coords) {
      setError("Ort nicht gefunden. Bitte gib den vollständigen Ortsnamen oder die PLZ ein.")
      setLoading(false)
      return
    }

    try {
      localStorage.setItem("padel_location", params.location!)
      localStorage.setItem("padel_radius", String(params.radius))
    } catch { /* private-mode Safari */ }

    const geo: GeoParams = { ...coords, radius: params.radius }
    lastParamsRef.current = params
    lastGeoRef.current    = geo
    setLastParams(params)

    fetchWeather(coords.lat, coords.lon, params.date, params.time)
      .then((w) => { if (w) setSearchWeather(w) })

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
      setSearchParams({
        ort: params.location!,
        datum: params.date,
        zeit: params.time,
        radius: String(params.radius),
        ...(params.durations?.length ? { dur: params.durations.join(",") } : {}),
      }, { replace: true })
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
      if (res.availability_pending) {
        activePollsRef.current += 1
        setPollingActive(true)
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
          activePollsRef.current -= 1
          if (activePollsRef.current === 0) setPollingActive(false)
        }, 15_000)
      }
    } finally {
      setLoadingMore(false)
    }
  }

  const filteredResults = results.filter((v) => {
    if (v.court_type === "indoor" && !courtFilter.indoor) return false
    if (v.court_type === "outdoor" && !courtFilter.outdoor) return false
    if (v.court_type !== "indoor" && v.court_type !== "outdoor") {
      if (!courtFilter.indoor && !courtFilter.outdoor) return false
    }
    if (v.status !== "pending") {
      // other_duration = free court, wrong block length → counts as "frei" for filtering
      const isFree = v.status === "free" || v.status === "other_duration"
      if (isFree && !statusFilter.frei) return false
      if (!isFree && !statusFilter.belegt) return false
    }
    return true
  })

  function getWeatherHint(rain_prob: number): { text: string; color: string } | null {
    const { indoor, outdoor } = courtFilter
    if (indoor && !outdoor) return null
    if (!indoor && outdoor) {
      if (rain_prob <= 20) return { text: "Bedingungen gut", color: "text-green-400" }
      if (rain_prob <= 40) return { text: "Regen möglich", color: "text-amber-400" }
      if (rain_prob <= 65) return { text: "Regen wahrscheinlich", color: "text-red-400" }
      return { text: "Schlechte Bedingungen", color: "text-red-400" }
    }
    if (rain_prob <= 20) return { text: "Outdoor gut möglich", color: "text-green-400" }
    if (rain_prob <= 40) return { text: "Regen möglich — eher Indoor buchen", color: "text-amber-400" }
    if (rain_prob <= 65) return { text: "Regen wahrscheinlich — Indoor empfohlen", color: "text-red-400" }
    return { text: "Regen erwartet — Indoor empfohlen", color: "text-red-400" }
  }

  return {
    urlLocation, urlDate, urlTime, urlRadius, urlDurations,
    results, filteredResults, isLoading, isLoadingMore, hasMore,
    error, searched, pollingActive, lastUpdated, secondsSince,
    bookingWindowNotice, searchLabel, searchWeather, highlightId,
    courtFilter, setCourtFilter, statusFilter, setStatusFilter,
    lastParams, lastParamsRef,
    skeletonCount: results.length > 0 ? results.length : SKELETON_COUNT,
    onSearch, onLoadMore, getWeatherHint,
  }
}
