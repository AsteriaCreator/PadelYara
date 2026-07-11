import { Helmet } from "react-helmet-async"
import { useState, useEffect, useRef, useCallback } from "react"
import { Link } from "react-router-dom"
import { fetchMatches, fetchVenues, type MatchBoardFilter } from "../api"
import type { MatchPublic, MapVenue } from "../types"
import { suggest, geocode, type Suggestion } from "../geocode"
import {
  inputClass, labelClass, labelStyle, LS_MATCH_FILTER,
  formatMatchWhen, formatPrice, courtTypeLabel, spotsLeftLabel, occupied,
} from "./matchShared"
import { LevelPills, AvatarRow } from "./matchComponents"

interface StoredFilter {
  mode: "venue" | "radius"
  venueIds: string[]
  venueNames: Record<string, string>
  location: string
  lat: number | null
  lon: number | null
  radius: number
  levels: string[]
}

function defaultFilter(): StoredFilter {
  return { mode: "venue", venueIds: [], venueNames: {}, location: "", lat: null, lon: null, radius: 20, levels: [] }
}

function loadFilter(): StoredFilter {
  try {
    const raw = localStorage.getItem(LS_MATCH_FILTER)
    if (!raw) return defaultFilter()
    return { ...defaultFilter(), ...JSON.parse(raw) }
  } catch { return defaultFilter() }
}

function saveFilter(f: StoredFilter): void {
  try { localStorage.setItem(LS_MATCH_FILTER, JSON.stringify(f)) } catch { /* private-mode Safari */ }
}

export default function DeinMatchPage() {
  const [filter, setFilter] = useState<StoredFilter>(loadFilter)
  const [allVenues, setAllVenues] = useState<MapVenue[]>([])
  const [matches, setMatches] = useState<MatchPublic[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)

  useEffect(() => { fetchVenues().then(setAllVenues).catch(() => {}) }, [])

  const runSearch = useCallback(async (f: StoredFilter) => {
    const hasVenues = f.mode === "venue" && f.venueIds.length > 0
    const hasGeo = f.mode === "radius" && f.lat != null && f.lon != null
    if (!hasVenues && !hasGeo) {
      setMatches([])
      setSearched(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const params: MatchBoardFilter = { levels: f.levels }
      if (hasVenues) params.venueIds = f.venueIds
      if (hasGeo) { params.lat = f.lat!; params.lon = f.lon!; params.radius = f.radius }
      const results = await fetchMatches(params)
      setMatches(results)
      setSearched(true)
    } catch {
      setError("Meine Jagd ist gerade unterbrochen. Versuch es gleich nochmal.")
    } finally {
      setLoading(false)
    }
  }, [])

  // Restore + search on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { runSearch(filter) }, [])

  function updateFilter(patch: Partial<StoredFilter>) {
    const next = { ...filter, ...patch }
    setFilter(next)
    saveFilter(next)
    runSearch(next)
  }

  return (
    <div>
      <Helmet>
        <title>Dein Match — PadelYara</title>
        <meta name="description" content="Vier Spieler, ein Link, kein Login. Match aufmachen oder offenen Matches in deiner Nähe beitreten." />
        <link rel="canonical" href="https://www.padelyara.at/dein-match" />
      </Helmet>

      <p
        className="text-base italic mb-4 mt-2"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c" }}
      >
        Vier müsst ihr sein. Den Anfang mache ich. Den Rest jagt ihr selbst.
      </p>

      <Link
        to="/dein-match/neu"
        className="block w-full py-3 rounded-xl text-center text-sm font-bold tracking-wide mb-5 transition-colors"
        style={{ background: "rgba(212,245,60,0.12)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.3)" }}
      >
        + MATCH AUFMACHEN
      </Link>

      <FilterBox filter={filter} onChange={updateFilter} allVenues={allVenues} />

      {loading && (
        <div className="text-center py-10 text-gray-600 text-sm">Yara sucht …</div>
      )}

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

      {!loading && !error && searched && matches.length === 0 && (
        <div className="text-center py-10 mb-4">
          <p className="text-3xl mb-3">🎾</p>
          <p className="text-white font-semibold mb-1">Keine offenen Matches.</p>
          <p className="text-gray-500 text-sm">Dann mach eben das erste auf.</p>
        </div>
      )}

      {!loading && !searched && !error && (
        <div className="text-center py-10 text-gray-600 text-sm">
          Wähl Venues oder einen Umkreis, um offene Matches zu sehen.
        </div>
      )}

      {!loading && matches.length > 0 && (
        <>
          <p className="text-xs text-gray-600 mb-3 px-1 tracking-wide uppercase">
            {matches.length === 1 ? "1 offenes Match" : `${matches.length} offene Matches`}
          </p>
          <div className="flex flex-col gap-3">
            {matches.map(m => <MatchCard key={m.slug} match={m} />)}
          </div>
        </>
      )}
    </div>
  )
}

function FilterBox({ filter, onChange, allVenues }: {
  filter: StoredFilter
  onChange: (patch: Partial<StoredFilter>) => void
  allVenues: MapVenue[]
}) {
  return (
    <div
      className="rounded-xl mb-5 p-4"
      style={{ background: "#111318", border: "1px solid rgba(212,245,60,0.12)" }}
    >
      <div className="flex gap-2 mb-4">
        {(["venue", "radius"] as const).map(mode => (
          <button
            key={mode}
            type="button"
            onClick={() => onChange({ mode })}
            className="flex-1 py-2 rounded-lg text-sm font-semibold border transition-colors"
            style={{
              borderColor: filter.mode === mode ? "#d4f53c" : "rgba(107,114,128,0.4)",
              color: filter.mode === mode ? "#d4f53c" : "#9ca3af",
              background: filter.mode === mode ? "rgba(212,245,60,0.1)" : "transparent",
            }}
          >
            {mode === "venue" ? "Nach Venue" : "Umkreissuche"}
          </button>
        ))}
      </div>

      {filter.mode === "venue" ? (
        <VenuePicker
          allVenues={allVenues}
          selectedIds={filter.venueIds}
          venueNames={filter.venueNames}
          onChange={(venueIds, venueNames) => onChange({ venueIds, venueNames })}
        />
      ) : (
        <RadiusPicker filter={filter} onChange={onChange} />
      )}

      <p className={`${labelClass} block mt-4 mb-2`} style={labelStyle}>Level (mehrere möglich)</p>
      <LevelPills selected={filter.levels} onChange={levels => onChange({ levels })} />
    </div>
  )
}

function VenuePicker({ allVenues, selectedIds, venueNames, onChange }: {
  allVenues: MapVenue[]
  selectedIds: string[]
  venueNames: Record<string, string>
  onChange: (ids: string[], names: Record<string, string>) => void
}) {
  const [query, setQuery] = useState("")
  const [showDropdown, setShowDropdown] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setShowDropdown(false)
    }
    document.addEventListener("pointerdown", onPointerDown)
    return () => document.removeEventListener("pointerdown", onPointerDown)
  }, [])

  const matches = query.trim().length >= 1
    ? allVenues.filter(v => v.name.toLowerCase().includes(query.trim().toLowerCase()) && !selectedIds.includes(v.id)).slice(0, 8)
    : []

  function add(v: MapVenue) {
    onChange([...selectedIds, v.id], { ...venueNames, [v.id]: v.name })
    setQuery("")
    setShowDropdown(false)
  }
  function remove(id: string) {
    onChange(selectedIds.filter(x => x !== id), venueNames)
  }

  return (
    <div>
      <p className={`${labelClass} block mb-2`} style={labelStyle}>Venues</p>
      {selectedIds.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {selectedIds.map(id => (
            <span
              key={id}
              className="text-xs px-2.5 py-1 rounded-full flex items-center gap-1.5"
              style={{ background: "rgba(212,245,60,0.14)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.4)" }}
            >
              {venueNames[id] ?? id}
              <button type="button" onClick={() => remove(id)} aria-label={`${venueNames[id]} entfernen`}>✕</button>
            </span>
          ))}
        </div>
      )}
      <div className="relative" ref={wrapperRef}>
        <input
          type="text"
          value={query}
          onChange={e => { setQuery(e.target.value); setShowDropdown(true) }}
          onFocus={() => setShowDropdown(true)}
          placeholder="Venue suchen …"
          className={`${inputClass} py-2`}
        />
        {showDropdown && matches.length > 0 && (
          <ul className="absolute z-30 left-0 right-0 top-full mt-1 bg-gray-800 border border-gray-700 rounded-lg overflow-hidden shadow-lg max-h-52 overflow-y-auto">
            {matches.map(v => (
              <li
                key={v.id}
                onPointerDown={e => { e.preventDefault(); add(v) }}
                className="px-3 py-2 text-sm text-white cursor-pointer hover:bg-gray-700 truncate"
              >
                {v.name}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function RadiusPicker({ filter, onChange }: {
  filter: StoredFilter
  onChange: (patch: Partial<StoredFilter>) => void
}) {
  const [location, setLocation] = useState(filter.location)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [showSugg, setShowSugg] = useState(false)
  const [geocoding, setGeocoding] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setShowSugg(false)
    }
    document.addEventListener("pointerdown", onPointerDown)
    return () => document.removeEventListener("pointerdown", onPointerDown)
  }, [])

  async function pickLocation(label: string) {
    setLocation(label)
    setSuggestions([])
    setShowSugg(false)
    setGeocoding(true)
    try {
      const coords = await geocode(label)
      if (coords) onChange({ location: label, lat: coords.lat, lon: coords.lon })
    } finally {
      setGeocoding(false)
    }
  }

  return (
    <div className="flex gap-2">
      <div className="flex-1 relative" ref={wrapperRef}>
        <p className={`${labelClass} block mb-2`} style={labelStyle}>Ort</p>
        <input
          type="text"
          value={location}
          onChange={e => {
            const val = e.target.value
            setLocation(val)
            if (debounceRef.current) clearTimeout(debounceRef.current)
            if (val.trim().length >= 3) {
              debounceRef.current = setTimeout(async () => {
                const results = await suggest(val)
                setSuggestions(results)
                setShowSugg(results.length > 0)
              }, 300)
            } else {
              setSuggestions([])
              setShowSugg(false)
            }
          }}
          placeholder="z.B. 2500 oder Baden"
          className={`${inputClass} py-2`}
        />
        {geocoding && <p className="text-xs text-gray-600 mt-1">Orte werden gesucht …</p>}
        {showSugg && (
          <ul className="absolute z-30 left-0 right-0 top-full mt-1 bg-gray-800 border border-gray-700 rounded-lg overflow-hidden shadow-lg">
            {suggestions.map((s, i) => (
              <li
                key={i}
                onPointerDown={e => { e.preventDefault(); pickLocation(s.label) }}
                className="px-3 py-2 text-sm text-white cursor-pointer hover:bg-gray-700 truncate"
              >
                {s.label}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="w-24 shrink-0">
        <p className={`${labelClass} block mb-2`} style={labelStyle}>Umkreis</p>
        <select
          value={filter.radius}
          onChange={e => onChange({ radius: Number(e.target.value) })}
          className={`${inputClass} py-2`}
        >
          {[5, 10, 20, 25, 50].map(km => <option key={km} value={km}>{km} km</option>)}
        </select>
      </div>
    </div>
  )
}

function MatchCard({ match }: { match: MatchPublic }) {
  const isFull = match.status === "full"
  return (
    <div
      className="rounded-xl p-4"
      style={{ background: "#111827", border: "1px solid #1f2937", opacity: isFull ? 0.6 : 1 }}
    >
      <div className="flex justify-between items-start gap-3 mb-1">
        <div>
          <Link
            to={`/court/${match.venue.id}`}
            className="font-semibold text-lg hover:underline"
            style={{ color: "#d4f53c" }}
          >
            {match.venue.name} →
          </Link>
          <p className="text-sm text-gray-200 mt-0.5">{formatMatchWhen(match.starts_at, match.ends_at)}</p>
          <p className="text-xs text-gray-600 mt-0.5">
            {[courtTypeLabel(match.venue.court_type), match.venue.distance_km != null ? `${match.venue.distance_km} km entfernt` : null]
              .filter(Boolean).join(" · ")}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {match.levels.map(l => (
            <span key={l} className="text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap" style={{ border: "1px solid rgba(212,245,60,0.4)", color: "#d4f53c" }}>
              {l}
            </span>
          ))}
          <span
            className="text-xs px-2 py-0.5 rounded-full whitespace-nowrap"
            style={match.court_booked
              ? { background: "rgba(74,222,128,0.1)", color: "#4ade80", border: "1px solid rgba(74,222,128,0.3)" }
              : { background: "rgba(251,191,36,0.09)", color: "#fbbf24", border: "1px solid rgba(251,191,36,0.3)" }}
          >
            {match.court_booked ? "✓ Court gebucht" : "Court noch nicht gebucht"}
          </span>
        </div>
      </div>

      <p className="text-sm text-gray-400 mt-2">Organisiert von <span className="text-white font-medium">{match.organizer.name}</span></p>
      <p className="text-sm mt-1" style={{ color: "#d4f53c" }}>{formatPrice(match.price_total, match.spots_total)}</p>
      {match.note && (
        <div className="mt-2 pl-2.5 py-1.5 text-sm text-gray-300 italic" style={{ borderLeft: "2px solid rgba(212,245,60,0.35)" }}>
          „{match.note}"
        </div>
      )}

      <p className="text-sm mt-3 mb-2" style={{ color: "#d4f53c" }}>
        {occupied(match)} von {match.spots_total} · <span style={{ color: isFull ? "#6b7280" : "rgba(212,245,60,0.45)" }}>{spotsLeftLabel(match)}</span>
      </p>
      <AvatarRow organizerName={match.organizer.name} players={match.players} spotsTotal={match.spots_total} />

      <div className="flex items-center gap-3 mt-3">
        <Link
          to={`/match/${match.slug}`}
          className="flex-1 text-center py-2.5 rounded-lg text-sm font-bold tracking-wide uppercase"
          style={isFull
            ? { background: "transparent", color: "#6b7280", border: "1px solid #374151" }
            : { background: "rgba(212,245,60,0.12)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.3)" }}
        >
          {isFull ? "Voll" : "Ich bin dabei"}
        </Link>
        <ShareMatchButton slug={match.slug} venueName={match.venue.name} />
      </div>
    </div>
  )
}

export function ShareMatchButton({ slug, venueName }: { slug: string; venueName: string }) {
  const [copied, setCopied] = useState(false)
  function handleShare() {
    const url = `${window.location.origin}/match/${slug}`
    const text = `Wer spielt mit — ${venueName}? Link in die Gruppe. Wer ihn ignoriert, spielt nicht.`
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
      className="text-xs tracking-wide uppercase transition-colors px-2"
      style={{ fontFamily: "'Barlow Condensed', sans-serif", color: copied ? "#d4f53c" : "rgba(212,245,60,0.4)" }}
    >
      {copied ? "Kopiert" : "Teilen"}
    </button>
  )
}
