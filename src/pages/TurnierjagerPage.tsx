import { useState, useEffect, useCallback, useRef } from "react"
import type { Tournament } from "../types"
import TournamentCard from "../components/TournamentCard"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"

const BUNDESLAENDER = [
  "Wien", "Niederösterreich", "Oberösterreich", "Steiermark",
  "Tirol", "Kärnten", "Salzburg", "Vorarlberg", "Burgenland",
]
const KATEGORIEN = ["Starter", "Advanced", "Expert", "Professional", "Elite"]
const WETTBEWERBE = ["Herren", "Damen", "Mixed", "Jugend", "Offener Bewerb"]
const WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

const LS_KEY = "turnierjager_filters"

interface Filters {
  bundesland: string[]
  bezirk: string[]
  kategorie: string[]
  wettbewerb: string[]
  wochentag: string[]
  showFull: boolean
  showClosed: boolean
}

function defaultFilters(): Filters {
  return {
    bundesland: [],
    bezirk: [],
    kategorie: [],
    wettbewerb: [],
    wochentag: [],
    showFull: false,
    showClosed: false,
  }
}

function loadFilters(): Filters {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (raw) return { ...defaultFilters(), ...JSON.parse(raw) }
  } catch { /* ignore */ }
  return defaultFilters()
}

function saveFilters(f: Filters): void {
  try { localStorage.setItem(LS_KEY, JSON.stringify(f)) } catch { /* ignore */ }
}

// ── Multi-select chip group ────────────────────────────────────────────────

function MultiChip({
  label, options, selected, onChange, loading = false,
}: {
  label: string
  options: string[]
  selected: string[]
  onChange: (v: string[]) => void
  loading?: boolean
}) {
  function toggle(opt: string) {
    onChange(
      selected.includes(opt)
        ? selected.filter(x => x !== opt)
        : [...selected, opt]
    )
  }

  const allSelected = selected.length === 0

  return (
    <div className="mb-4">
      <p className="text-xs text-gray-500 mb-2 tracking-wide uppercase flex items-center gap-2">
        {label}
        {loading && <span className="text-gray-700 normal-case tracking-normal">laden…</span>}
      </p>
      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => onChange([])}
          className="text-xs px-2.5 py-1 rounded-full border transition-colors"
          style={{
            borderColor: allSelected ? "#d4f53c" : "rgba(107,114,128,0.4)",
            color: allSelected ? "#d4f53c" : "#6b7280",
            background: allSelected ? "rgba(212,245,60,0.08)" : "transparent",
          }}
        >
          Alle
        </button>
        {options.map(opt => {
          const active = selected.includes(opt)
          return (
            <button
              key={opt}
              onClick={() => toggle(opt)}
              className="text-xs px-2.5 py-1 rounded-full border transition-colors"
              style={{
                borderColor: active ? "#d4f53c" : "rgba(107,114,128,0.4)",
                color: active ? "#d4f53c" : "#6b7280",
                background: active ? "rgba(212,245,60,0.08)" : "transparent",
              }}
            >
              {opt}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────

export default function TurnierjagerPage() {
  const [filters, setFilters] = useState<Filters>(loadFilters)
  const [tournaments, setTournaments] = useState<Tournament[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)

  // Bezirk filter state — options loaded dynamically from API
  const [bezirkOptions, setBezirkOptions] = useState<string[]>([])
  const [bezirkLoading, setBezirkLoading] = useState(false)
  const prevBundesland = useRef<string>("")

  // Fetch bezirke options whenever bundesland selection changes
  useEffect(() => {
    const key = filters.bundesland.join(",")
    if (key === prevBundesland.current) return
    prevBundesland.current = key

    setBezirkLoading(true)
    const params = new URLSearchParams()
    if (filters.bundesland.length) params.set("bundesland", filters.bundesland.join(","))

    fetch(`${API_BASE}/api/tournaments/bezirke?${params}`)
      .then(r => r.json())
      .then(data => {
        setBezirkOptions(data.bezirke ?? [])
        // Drop any selected bezirke that don't exist in the new bundesland scope
        setFilters(prev => {
          const valid = new Set(data.bezirke ?? [])
          const nextBezirk = prev.bezirk.filter(b => valid.has(b))
          if (nextBezirk.length === prev.bezirk.length) return prev
          const next = { ...prev, bezirk: nextBezirk }
          saveFilters(next)
          return next
        })
      })
      .catch(() => setBezirkOptions([]))
      .finally(() => setBezirkLoading(false))
  }, [filters.bundesland])

  function updateFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters(prev => {
      // When bundesland changes, reset bezirk — stale district selections don't make sense
      const extra = key === "bundesland" ? { bezirk: [] } : {}
      const next = { ...prev, [key]: value, ...extra }
      saveFilters(next)
      return next
    })
  }

  const fetchTournaments = useCallback(async (f: Filters) => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (f.bundesland.length) params.set("bundesland", f.bundesland.join(","))
      if (f.bezirk.length) params.set("bezirk", f.bezirk.join(","))
      if (f.kategorie.length) params.set("category", f.kategorie.join(","))
      if (f.wettbewerb.length) params.set("competition", f.wettbewerb.join(","))
      if (f.wochentag.length) params.set("weekday", f.wochentag.join(","))
      params.set("show_full", String(f.showFull))
      params.set("show_closed", String(f.showClosed))

      const res = await fetch(`${API_BASE}/api/tournaments?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setTournaments(data.tournaments ?? [])
      setLastUpdated(new Date().toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" }))
    } catch {
      setError("Verbindung fehlgeschlagen. Bitte Seite neu laden.")
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch when filters change
  useEffect(() => {
    fetchTournaments(filters)
  }, [filters, fetchTournaments])

  function resetFilters() {
    const f = defaultFilters()
    saveFilters(f)
    setFilters(f)
  }

  const hasActiveFilters = (
    filters.bundesland.length > 0 ||
    filters.bezirk.length > 0 ||
    filters.kategorie.length > 0 ||
    filters.wettbewerb.length > 0 ||
    filters.wochentag.length > 0
  )

  return (
    <section className="mt-2 pb-12">
      {/* Intro */}
      <div className="mb-6 space-y-3 px-1">
        <p className="text-white text-lg font-semibold">Turnierjäger</p>
        <p className="text-gray-400 text-base leading-relaxed">
          Padel Austria zeigt dir Turniere nur einzeln — ein Bundesland nach dem anderen,
          eine Kategorie nach der anderen. Yara durchsucht alles auf einmal und zeigt dir
          eine saubere Liste.
        </p>
      </div>

      {/* Filters */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-4 mb-6">
        <div className="flex items-center justify-between mb-4">
          <p className="text-xs text-gray-500 tracking-widest uppercase">Filter</p>
          {hasActiveFilters && (
            <button
              onClick={resetFilters}
              className="text-xs text-gray-600 hover:text-gray-400 transition-colors"
            >
              Zurücksetzen
            </button>
          )}
        </div>

        <MultiChip
          label="Bundesland"
          options={BUNDESLAENDER}
          selected={filters.bundesland}
          onChange={v => updateFilter("bundesland", v)}
        />

        {/* Bezirk — only shown when options exist */}
        {(bezirkOptions.length > 0 || bezirkLoading) && (
          <MultiChip
            label="Bezirk"
            options={bezirkOptions}
            selected={filters.bezirk}
            onChange={v => updateFilter("bezirk", v)}
            loading={bezirkLoading}
          />
        )}

        <MultiChip
          label="Wochentag"
          options={WOCHENTAGE}
          selected={filters.wochentag}
          onChange={v => updateFilter("wochentag", v)}
        />
        <MultiChip
          label="Kategorie"
          options={KATEGORIEN}
          selected={filters.kategorie}
          onChange={v => updateFilter("kategorie", v)}
        />
        <MultiChip
          label="Wettbewerb"
          options={WETTBEWERBE}
          selected={filters.wettbewerb}
          onChange={v => updateFilter("wettbewerb", v)}
        />

        {/* Show full / show closed checkboxes */}
        <div className="mt-3 flex flex-col gap-2 border-t border-gray-800 pt-3">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={filters.showFull}
              onChange={e => updateFilter("showFull", e.target.checked)}
              className="accent-lime-400"
            />
            <span className="text-xs text-gray-500">Volle Turniere zeigen</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={filters.showClosed}
              onChange={e => updateFilter("showClosed", e.target.checked)}
              className="accent-lime-400"
            />
            <span className="text-xs text-gray-500">Vergangene / geschlossene Turniere zeigen</span>
          </label>
        </div>
      </div>

      {/* Results header */}
      {!loading && !error && (
        <div className="flex items-center justify-between mb-2 px-1">
          <p
            className="text-sm"
            style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "rgba(212,245,60,0.5)" }}
          >
            {tournaments.length === 0
              ? "Keine Turniere gefunden"
              : tournaments.length === 1
              ? "1 Turnier"
              : `${tournaments.length} Turniere`}
          </p>
          {lastUpdated && (
            <p className="text-xs text-gray-700">Stand: {lastUpdated}</p>
          )}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="text-center py-10">
          <p className="text-gray-600 text-sm">Yara jagt …</p>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <p className="text-red-400 text-sm px-1">{error}</p>
      )}

      {/* Results list */}
      {!loading && !error && tournaments.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 divide-y divide-gray-800 mb-6">
          {tournaments.map(t => (
            <TournamentCard key={`${t.source}:${t.source_id}`} t={t} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && tournaments.length === 0 && (
        <div className="text-center py-10">
          <p className="text-3xl mb-3">🎾</p>
          <p className="text-white font-semibold mb-1">Keine Turniere gefunden.</p>
          <p className="text-gray-500 text-sm">Filter anpassen oder mehr Optionen aktivieren.</p>
        </div>
      )}

      {/* Notification placeholder */}
      <div
        className="mt-8 rounded-xl border p-6 text-center"
        style={{ borderColor: "rgba(212,245,60,0.1)", background: "rgba(212,245,60,0.02)" }}
      >
        <p className="text-white font-semibold mb-1">Passende Turniere im Blick behalten?</p>
        <p className="text-gray-500 text-sm mb-3">
          Yara benachrichtigt dich, wenn neue Turniere auftauchen — oder die Anmeldung öffnet.
        </p>
        <p className="text-xs text-gray-700 italic">Benachrichtigungen kommen bald.</p>
      </div>

      {/* Source attribution */}
      <p className="text-center text-xs text-gray-800 mt-6">
        Daten von{" "}
        <a
          href="https://padel-austria.at/tournaments"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-gray-600 transition-colors"
        >
          padel-austria.at
        </a>
        {" "}· täglich aktualisiert
      </p>
    </section>
  )
}
