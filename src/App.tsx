import React, { useState, useRef, useEffect, useCallback } from "react"
import { Routes, Route, NavLink, useSearchParams } from "react-router-dom"
import AdminDashboard from "./pages/AdminDashboard"
import type { Venue, SearchParams, Weather } from "./types"
import { fetchAvailability, fetchWeather, type GeoParams } from "./api"
import { geocode, GeocodeTimeoutError } from "./geocode"
import { subscribeEmail } from "./api"
import SearchCard from "./components/SearchCard"
import VenueRow from "./components/VenueRow"
import SkeletonRow from "./components/SkeletonRow"
import ImprintModal from "./components/ImprintModal"
import LoadingCat from "./components/LoadingCat"
import AboutSection from "./components/AboutSection"
import TurnierjagerPage from "./pages/TurnierjagerPage"
import PadelrevierPage from "./pages/PadelrevierPage"
import DatenschutzPage from "./pages/DatenschutzPage"

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

function FinderPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const urlLocation = searchParams.get("ort") ?? ""
  const urlDate     = searchParams.get("datum") ?? ""
  const urlTime     = searchParams.get("zeit") ?? ""
  const urlRadius   = Number(searchParams.get("radius")) || 0
  // Set by the Padelrevier map's "Verfügbarkeit prüfen" jump — highlight + scroll
  // to this venue once results render. Captured in state so the search's URL
  // rewrite (which drops the param) doesn't clear it.
  const [highlightId, setHighlightId] = useState(() => searchParams.get("venueId") ?? "")
  const didScrollRef = useRef(false)
  // The map jump also passes the venue's exact coords so the search centers on
  // it directly (no geocoding the venue name). Used only while the pre-filled
  // location is unchanged; once she edits the field, normal geocoding resumes.
  const prefillCoordsRef = useRef<{ location: string; lat: number; lon: number } | null>(
    (() => {
      const lat = Number(searchParams.get("lat"))
      const lon = Number(searchParams.get("lon"))
      return urlLocation && searchParams.get("lat") && searchParams.get("lon") && !isNaN(lat) && !isNaN(lon)
        ? { location: urlLocation, lat, lon }
        : null
    })()
  )

  const [results, setResults]               = useState<Venue[]>([])
  const [isLoading, setLoading]             = useState(false)
  const [isLoadingMore, setLoadingMore]     = useState(false)
  const [hasMore, setHasMore]               = useState(false)
  const [etOffset, setEtOffset]             = useState(0)
  const [error, setError]                   = useState<string | null>(null)
  const [searched, setSearched]             = useState(false)
  const [_pollingExpired, setPollingExpired]        = useState(false)
  const [pollingActive,  setPollingActive]          = useState(false)
  const activePollsRef = useRef(0)
  const [lastUpdated, setLastUpdated]               = useState<number | null>(null)
  const [secondsSince, setSecondsSince]             = useState(0)
  const [bookingWindowNotice, setBookingWindowNotice] = useState<string | null>(null)
  const [searchLabel, setSearchLabel]               = useState<string | null>(null)
  const [searchWeather, setSearchWeather]           = useState<Weather | null>(null)
  const [showImprint, setShowImprint]       = useState(false)
  const [courtFilter, setCourtFilter]       = useState<{ indoor: boolean; outdoor: boolean }>({ indoor: true, outdoor: true })
  const [statusFilter, setStatusFilter]     = useState<{ frei: boolean; belegt: boolean }>({ frei: true, belegt: true })

  const refreshTimer  = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastParamsRef = useRef<SearchParams | null>(null)
  const lastGeoRef    = useRef<GeoParams | undefined>(undefined)

  function cancelRefresh() {
    if (refreshTimer.current) {
      clearTimeout(refreshTimer.current)
      refreshTimer.current = null
    }
    activePollsRef.current = 0
    setPollingExpired(false)
    setPollingActive(false)
  }

  useEffect(() => cancelRefresh, [])

  // Auto-trigger search when URL params are present (shared link)
  useEffect(() => {
    if (urlLocation && urlDate && urlTime && urlRadius) {
      onSearch({ location: urlLocation, date: urlDate, time: urlTime, radius: urlRadius, court_type: "both" })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to + briefly highlight the venue jumped-to from the Padelrevier map,
  // once it appears in the results. Runs once (guarded by didScrollRef).
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
    setSecondsSince(0)
    const interval = setInterval(() => {
      setSecondsSince(Math.floor((Date.now() - lastUpdated) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [lastUpdated])

  // Polling schedule (from first response):
  //   attempt 1 → +3 s   (catches Eversports via Vercel proxy, ~3-5 s)
  //   attempt 2 → +5 s   (T+8 s  — catches any stragglers)
  //   attempt 3 → +12 s  (T+20 s — catches warm eTennis scrapes)
  //   attempt 4 → +25 s  (T+45 s — covers warm backend scrape completion)
  //   attempt 5 → +60 s  (T+105 s — covers cold-start backend)
  // Max 5 attempts. Always polls et_offset=0; merges into the accumulated list.
  const POLL_DELAYS = [3_000, 5_000, 12_000, 25_000, 60_000]
  function scheduleRefresh(params: SearchParams, geo: GeoParams | undefined, attempt: number) {
    // Signal immediately that a timer is running so venue rows can show
    // "Wird noch geprüft …" instead of "Konnte nicht geprüft werden".
    setPollingActive(true)
    const delay = POLL_DELAYS[attempt - 1] ?? 60_000
    refreshTimer.current = setTimeout(async () => {
      refreshTimer.current = null
      const refreshed = await fetchAvailability(params, geo, 0).catch(() => null)
      if (!refreshed?.ok) {
        // Network failure — stop polling, mark expired so pending rows convert
        setPollingActive(false)
        setPollingExpired(true)
        return
      }
      setResults((prev) => mergeResults(prev, refreshed.results))
      setLastUpdated(Date.now())
      if (refreshed.availability_pending && attempt < POLL_DELAYS.length) {
        // Still pending venues — schedule next attempt (sets pollingActive again)
        scheduleRefresh(params, geo, attempt + 1)
      } else {
        // All attempts exhausted (or everything resolved)
        setPollingActive(false)
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
    setSearchWeather(null)
    setBookingWindowNotice(null)

    let coords: { lat: number; lon: number } | null
    const pre = prefillCoordsRef.current
    if (pre && params.location === pre.location) {
      // Jumped from the Padelrevier map — use the venue's exact coords so the
      // search centers on it, instead of geocoding the venue name.
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

    // Geocoding succeeded — persist the location for next visit
    try {
      localStorage.setItem("padel_location", params.location!)
      localStorage.setItem("padel_radius", String(params.radius))
    } catch { /* private-mode Safari */ }

    const geo: GeoParams = { ...coords, radius: params.radius }

    lastParamsRef.current = params
    lastGeoRef.current    = geo

    // Fire weather fetch in parallel — show it as soon as it resolves
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
      setSearchParams({ ort: params.location!, datum: params.date, zeit: params.time, radius: String(params.radius) }, { replace: true })
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
      const isFree = v.status === "free"
      if (isFree && !statusFilter.frei) return false
      if (!isFree && !statusFilter.belegt) return false
    }
    return true
  })

  const skeletonCount = results.length > 0 ? results.length : SKELETON_COUNT

  function getWeatherHint(rain_prob: number): { text: string; color: string } | null {
    const { indoor, outdoor } = courtFilter
    if (indoor && !outdoor) return null
    if (!indoor && outdoor) {
      if (rain_prob <= 20) return { text: "Bedingungen gut", color: "text-green-400" }
      if (rain_prob <= 40) return { text: "Regen möglich", color: "text-amber-400" }
      if (rain_prob <= 65) return { text: "Regen wahrscheinlich", color: "text-red-400" }
      return { text: "Schlechte Bedingungen", color: "text-red-400" }
    }
    // both shown
    if (rain_prob <= 20) return { text: "Outdoor gut möglich", color: "text-green-400" }
    if (rain_prob <= 40) return { text: "Regen möglich — eher Indoor buchen", color: "text-amber-400" }
    if (rain_prob <= 65) return { text: "Regen wahrscheinlich — Indoor empfohlen", color: "text-red-400" }
    return { text: "Regen erwartet — Indoor empfohlen", color: "text-red-400" }
  }

  return (
    <div className="min-h-screen overflow-x-hidden" style={BG_STYLE}>
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="mb-6">
          <img
            src="/lockup-horizontal-dark.svg"
            alt="PadelYara"
            className="h-24 w-auto block"
          />
        </div>

        <Nav />

        <p
          className="text-base italic mb-4 mt-2"
          style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c" }}
        >
          Yara findet einen freien Court für dich. Wo willst du spielen?
        </p>

        <p className="mb-4 text-xs" style={{ color: "#6b7280" }}>
          PadelYara ist im Aufbau. Etwas fehlt oder stimmt nicht?{" "}
          <a href="mailto:cornelia.mayer@adventure-it.at?subject=PadelYara%20Feedback" style={{ color: "#9ca3af", textDecoration: "underline" }}>
            Schreib Yara.
          </a>
        </p>

        <NewsletterBanner />

        <SearchCard onSearch={onSearch} isLoading={isLoading} courtFilter={courtFilter} onCourtFilterChange={setCourtFilter} statusFilter={statusFilter} onStatusFilterChange={setStatusFilter} initialLocation={urlLocation || undefined} initialDate={urlDate || undefined} initialTime={urlTime || undefined} initialRadius={urlRadius || undefined} />

        {!searched && !isLoading && !error && (
          <div className="text-center py-8 text-gray-600 text-sm">
            <img src="/cat-head.svg" alt="Yara" className="h-16 w-auto mx-auto mb-3 opacity-30" />
            <p>Courts jagen. Sag mir wo.</p>
          </div>
        )}

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        {searchWeather && (
          <div className="mb-5">
            <p className="text-xs text-gray-500 mb-2 px-1 tracking-wide uppercase">
              Das Wetter in deiner Suchlocation
            </p>
            <div
              className="flex items-center gap-4 px-4 py-3 rounded-xl border text-sm"
              style={{ background: "rgba(212,245,60,0.05)", borderColor: "rgba(212,245,60,0.2)" }}
            >
              <span className="text-3xl leading-none">
                {searchWeather.icon === "sun" ? "☀️"
                  : searchWeather.icon === "cloud" ? "☁️"
                  : searchWeather.icon === "rain" || searchWeather.icon === "drizzle" ? "🌧️"
                  : searchWeather.icon === "snow" ? "❄️"
                  : searchWeather.icon === "thunder" ? "⛈️"
                  : searchWeather.icon === "fog" ? "🌫️"
                  : "🌡️"}
              </span>
              <div className="flex flex-col gap-0.5">
                <span className="text-xl font-bold text-white leading-none">{searchWeather.temp}°C</span>
                <span className="text-gray-400 text-xs">{searchWeather.desc}</span>
              </div>
              <div className="ml-auto text-right">
                <span className="text-blue-400 text-sm font-semibold">{searchWeather.rain_prob}%</span>
                <p className="text-gray-600 text-xs">Regenwahrsch.</p>
                {(() => { const h = getWeatherHint(searchWeather.rain_prob); return h ? <p className={`text-xs font-medium mt-0.5 ${h.color}`}>{h.text}</p> : null })()}
              </div>
            </div>
          </div>
        )}

        {(isLoading || pollingActive) && <LoadingCat />}

        {isLoading && (
          <>
            <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800 mb-4">
              {Array.from({ length: skeletonCount }).map((_, i) => (
                <SkeletonRow key={i} />
              ))}
            </div>
          </>
        )}

        {searched && !isLoading && searchLabel && (
          <p className="text-xs text-gray-600 mb-1 px-1 tracking-wide uppercase">
            {searchLabel}
          </p>
        )}

        {searched && !isLoading && !error && filteredResults.length > 0 && lastParamsRef.current && (
          <div className="mb-2 px-1 flex items-center justify-between">
            <p style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "0.85rem", color: "rgba(212,245,60,0.4)" }}>
              {filteredResults.length === 1
                ? `1 Ergebnis im Umkreis von ${lastParamsRef.current.radius} km`
                : `${filteredResults.length} Ergebnisse im Umkreis von ${lastParamsRef.current.radius} km`}
            </p>
            <ShareButton params={lastParamsRef.current} />
          </div>
        )}

        {searched && !isLoading && bookingWindowNotice && (
          <p className="text-xs text-gray-500 mb-3 px-1">
            ℹ️ {bookingWindowNotice}
          </p>
        )}

        {searched && !isLoading && !error && filteredResults.length > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800 mb-4">
            {filteredResults.map((venue) => (
              <VenueRow key={venue.id} venue={venue} pollingActive={pollingActive} searchDate={lastParamsRef.current?.date} highlighted={venue.id === highlightId} />
            ))}
          </div>
        )}

        {searched && !isLoading && !error && filteredResults.length === 0 && (
          <div className="text-center py-10 mb-4">
            <p className="text-3xl mb-3">🎾</p>
            <p className="text-white font-semibold mb-1">Keine Ergebnisse.</p>
            <p className="text-gray-500 text-sm">Lösungsvorschlag: woanders wohnen.</p>
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
            className="w-full py-3 rounded-xl text-sm font-bold tracking-wide transition-colors mb-4 cursor-pointer"
            style={{ border: "1px solid rgba(212,245,60,0.3)", color: "rgba(212,245,60,0.7)", fontFamily: "'Barlow Condensed', sans-serif", fontSize: "1rem" }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = "rgba(212,245,60,0.7)")}
            onMouseLeave={e => (e.currentTarget.style.borderColor = "rgba(212,245,60,0.3)")}
          >
            MEHR ERGEBNISSE
          </button>
        )}

        {searched && !isLoading && lastUpdated && (
          <p className="text-gray-600 text-xs text-right mb-4">
            Zuletzt aktualisiert {secondsSince < 10 ? "gerade eben" : `vor ${secondsSince} Sekunden`}
          </p>
        )}
      </div>

      <footer className="text-center py-8 mt-4">
        <p className="text-xs text-gray-700 mb-2 tracking-widest uppercase">PadelYara</p>
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={() => setShowImprint(true)}
            className="text-xs text-gray-700 hover:text-gray-400 transition-colors"
          >
            Impressum
          </button>
          <NavLink
            to="/datenschutz"
            className="text-xs text-gray-700 hover:text-gray-400 transition-colors"
          >
            Datenschutz
          </NavLink>
        </div>
      </footer>

      {showImprint && <ImprintModal onClose={() => setShowImprint(false)} />}
    </div>
  )
}

function ShareButton({ params }: { params: SearchParams | null }) {
  const [copied, setCopied] = useState(false)

  function buildShareText() {
    if (!params) return ""
    const [year, month, day] = params.date.split("-")
    const dateFormatted = `${day}.${month}.${year}`
    return `Schau mal, ob du am ${dateFormatted} um ${params.time} Uhr in ${params.location} spielen kannst:`
  }

  function handleShare() {
    const url = window.location.href
    const text = buildShareText()
    if (navigator.share) {
      navigator.share({ text, url }).catch(() => {})
    } else {
      navigator.clipboard.writeText(`${text}\n${url}`).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    }
  }

  return (
    <button
      onClick={handleShare}
      className="text-xs tracking-wide transition-colors"
      style={{ fontFamily: "'Barlow Condensed', sans-serif", color: copied ? "#d4f53c" : "rgba(212,245,60,0.4)" }}
    >
      {copied ? "KOPIERT" : "TEILEN"}
    </button>
  )
}

const NAV_LINK_STYLE = ({ isActive }: { isActive: boolean }) => ({
  display: "inline-block",
  paddingBottom: "8px",
  fontSize: "1rem",
  fontWeight: 600,
  marginRight: "24px",
  color: isActive ? "#ffffff" : "#4b5563",
  borderBottom: isActive ? "2px solid #d4f53c" : "2px solid transparent",
  textDecoration: "none",
  transition: "color 0.15s",
})

function Nav() {
  return (
    <div className="mb-2 border-b border-gray-800">
      <NavLink to="/" end style={NAV_LINK_STYLE}>Court Finder</NavLink>
      <NavLink to="/padelrevier" style={NAV_LINK_STYLE}>Padelrevier</NavLink>
      <NavLink to="/turnierjaeger" style={NAV_LINK_STYLE}>Turnierjagd</NavLink>
      <NavLink to="/about" style={NAV_LINK_STYLE}>Über Yara</NavLink>
    </div>
  )
}

function NewsletterBanner() {
  const [email, setEmail] = useState("")
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle")
  const [alreadySubscribed, setAlreadySubscribed] = useState(false)

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || status === "loading") return
    setStatus("loading")
    try {
      const res = await subscribeEmail(email.trim())
      if (res.ok) {
        setAlreadySubscribed(res.already ?? false)
        setStatus("done")
      } else {
        setStatus("error")
      }
    } catch {
      setStatus("error")
    }
  }, [email, status])

  if (status === "done") {
    return (
      <div
        className="mb-4 px-4 py-3 rounded-xl text-sm"
        style={{ background: "rgba(212,245,60,0.06)", border: "1px solid rgba(212,245,60,0.2)" }}
      >
        <p style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c", fontSize: "1rem" }}>
          {alreadySubscribed ? "Ich weiß. Du bist schon auf der Liste." : "Gut. Ich informiere dich."}
        </p>
      </div>
    )
  }

  return (
    <div
      className="mb-4 px-4 py-3 rounded-xl"
      style={{ background: "rgba(212,245,60,0.04)", border: "1px solid rgba(212,245,60,0.12)" }}
    >
      <p
        className="text-sm mb-2"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "rgba(212,245,60,0.7)", fontSize: "0.95rem" }}
      >
        Neue Features kommen. Ob du das mitbekommst, ist deine Entscheidung.
      </p>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="email"
          placeholder="deine@email.at"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className="flex-1 bg-transparent rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-600 outline-none min-w-0"
          style={{ border: "1px solid rgba(212,245,60,0.2)", fontFamily: "'Barlow Condensed', sans-serif" }}
        />
        <button
          type="submit"
          disabled={status === "loading"}
          className="px-4 py-1.5 rounded-lg text-sm font-bold tracking-wide transition-colors"
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            background: "rgba(212,245,60,0.12)",
            color: "#d4f53c",
            border: "1px solid rgba(212,245,60,0.3)",
          }}
        >
          {status === "loading" ? "…" : "INFORMIER MICH"}
        </button>
      </form>
      {status === "error" && (
        <p className="text-red-400 text-xs mt-1">Etwas ist schiefgelaufen. Versuch es nochmal.</p>
      )}
    </div>
  )
}

const BG_STYLE: React.CSSProperties = {
  backgroundColor: "#080810",
  backgroundImage: `
    radial-gradient(ellipse 80% 40% at 50% 0%, rgba(212,245,60,0.18) 0%, transparent 70%),
    repeating-linear-gradient(45deg, rgba(212,245,60,0.12) 0px 1px, transparent 1px 14px),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E")
  `,
  backgroundSize: "auto, auto, 200px 200px",
}

export default function App() {
  return (
    <Routes>
      <Route path="/admin" element={<AdminDashboard />} />
      <Route path="/turnierjaeger" element={
        <div className="min-h-screen overflow-x-hidden" style={BG_STYLE}>
          <div className="max-w-2xl mx-auto px-4 py-6">
            <div className="mb-6">
              <img src="/lockup-horizontal-dark.svg" alt="PadelYara" className="h-24 w-auto block" />
            </div>
            <Nav />
            <TurnierjagerPage />
          </div>
        </div>
      } />
      <Route path="/padelrevier" element={
        <div className="min-h-screen overflow-x-hidden" style={BG_STYLE}>
          <div className="max-w-2xl mx-auto px-4 py-6">
            <div className="mb-6">
              <img src="/lockup-horizontal-dark.svg" alt="PadelYara" className="h-24 w-auto block" />
            </div>
            <Nav />
            <PadelrevierPage />
          </div>
        </div>
      } />
      <Route path="/about" element={
        <div className="min-h-screen overflow-x-hidden" style={BG_STYLE}>
          <div className="max-w-2xl mx-auto px-4 py-6">
            <div className="mb-6">
              <img src="/lockup-horizontal-dark.svg" alt="PadelYara" className="h-24 w-auto block" />
            </div>
            <Nav />
            <AboutSection />
          </div>
        </div>
      } />
      <Route path="/datenschutz" element={
        <div className="min-h-screen overflow-x-hidden" style={BG_STYLE}>
          <div className="max-w-2xl mx-auto px-4 py-6">
            <div className="mb-6">
              <img src="/lockup-horizontal-dark.svg" alt="PadelYara" className="h-24 w-auto block" />
            </div>
            <Nav />
            <DatenschutzPage />
          </div>
        </div>
      } />
      <Route path="/*" element={<FinderPage />} />
    </Routes>
  )
}
