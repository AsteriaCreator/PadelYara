import { useState, useEffect, useCallback } from "react"
import type { Tournament } from "../types"
import TournamentCard from "../components/TournamentCard"
import { opensSoon } from "../tournamentBadges"
import { BEZIRKE_BY_BUNDESLAND } from "../data/bezirke"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"

const BUNDESLAENDER = [
  "Wien", "Niederösterreich", "Oberösterreich", "Steiermark",
  "Tirol", "Kärnten", "Salzburg", "Vorarlberg", "Burgenland",
]
const KATEGORIEN = ["Newcomer", "Starter", "Advanced", "Expert", "Professional", "Elite"]
const WETTBEWERBE = ["Herren", "Damen", "Mixed", "Jugend", "Offener Bewerb"]
const WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

// Result sections — tournaments are grouped by registration status so each
// block is self-explanatory. Order runs most-actionable → least. Header colors
// mirror the status badges on the cards (lime = open, blue = soon, etc.).
const RESULT_SECTIONS: {
  title: string
  subtitle: string
  color: string
  match: (t: Tournament) => boolean
}[] = [
  {
    title: "Anmeldung offen",
    subtitle: "Plätze frei oder Warteliste — jetzt anmelden.",
    color: "#d4f53c",
    match: t => t.status === "open",
  },
  {
    title: "Anmeldung noch nicht offen",
    subtitle: "Schon angekündigt. Anmeldung öffnet später.",
    color: "#60a5fa",
    match: t => t.status === "not_open_yet",
  },
  {
    title: "Ausgebucht",
    subtitle: "Voll — nur noch Warteliste möglich.",
    color: "#fbbf24",
    match: t => t.status === "full",
  },
  {
    title: "Vorbei & abgesagt",
    subtitle: "Anmeldung geschlossen oder Turnier abgesagt.",
    color: "#6b7280",
    match: t => t.status === "closed" || t.status === "cancelled",
  },
  {
    title: "Sonstige",
    subtitle: "Status unbekannt — Anmeldestatus konnte nicht ausgelesen werden.",
    color: "#6b7280",
    match: t => t.status === "unknown",
  },
]

const LS_KEY = "turnierjager_filters"

interface Filters {
  bundesland: string[]
  // Per-bundesland bezirk selection — keys are bundesland names, values are selected bezirke.
  // Preserved across bundesland toggles so selections survive deselect/reselect.
  bezirkByBundesland: Record<string, string[]>
  venue: string[]
  kategorie: string[]
  wettbewerb: string[]
  wochentag: string[]
  showFull: boolean
  showClosed: boolean
  // Client-side: show only tournaments whose registration opens in the next few days.
  onlyOpensSoon: boolean
}

function defaultFilters(): Filters {
  return {
    bundesland: [],
    bezirkByBundesland: {},
    venue: [],
    kategorie: [],
    wettbewerb: [],
    wochentag: [],
    showFull: false,
    showClosed: false,
    onlyOpensSoon: false,
  }
}

function loadFilters(): Filters {
  try {
    const raw = localStorage.getItem(LS_KEY)
    // onlyOpensSoon is a transient "show me just these" view — never restore it
    // as active, or a return visit looks mysteriously empty.
    if (raw) return { ...defaultFilters(), ...JSON.parse(raw), onlyOpensSoon: false }
  } catch { /* ignore */ }
  return defaultFilters()
}

function saveFilters(f: Filters): void {
  try { localStorage.setItem(LS_KEY, JSON.stringify(f)) } catch { /* ignore */ }
}

// Flat list of all selected bezirke across all selected bundesländer (for the API)
function allSelectedBezirke(f: Filters): string[] {
  return f.bundesland.flatMap(bl => f.bezirkByBundesland[bl] ?? [])
}

// ── Multi-select chip group ────────────────────────────────────────────────

function MultiChip({
  label, options, selected, onChange,
}: {
  label: string
  options: string[]
  selected: string[]
  onChange: (v: string[]) => void
}) {
  function toggle(opt: string) {
    onChange(selected.includes(opt) ? selected.filter(x => x !== opt) : [...selected, opt])
  }
  const allSelected = selected.length === 0
  return (
    <div className="mb-4">
      <p className="text-xs text-gray-500 mb-2 tracking-wide uppercase">{label}</p>
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

// ── Bundesland chip group (with per-chip expand arrow) ─────────────────────

function BundeslandChips({
  selected,
  expanded,
  onChange,
  onToggleExpand,
}: {
  selected: string[]
  expanded: string[]
  onChange: (v: string[]) => void
  onToggleExpand: (bl: string) => void
}) {
  function toggle(bl: string) {
    onChange(selected.includes(bl) ? selected.filter(x => x !== bl) : [...selected, bl])
  }
  const allSelected = selected.length === 0
  return (
    <div className="mb-1">
      <p className="text-xs text-gray-500 mb-2 tracking-wide uppercase">Bundesland</p>
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
        {BUNDESLAENDER.map(bl => {
          const active = selected.includes(bl)
          const open = expanded.includes(bl)
          const chipColor = active ? "#d4f53c" : "#6b7280"
          const chipBorder = active ? "#d4f53c" : "rgba(107,114,128,0.4)"
          const chipBg = active ? "rgba(212,245,60,0.08)" : "transparent"
          return active ? (
            // Selected: split chip — label toggles selection, arrow expands districts
            <div
              key={bl}
              className="flex rounded-full border overflow-hidden"
              style={{ borderColor: chipBorder, background: chipBg }}
            >
              <button
                onClick={() => toggle(bl)}
                className="text-xs pl-2.5 pr-1.5 py-1 transition-colors"
                style={{ color: chipColor }}
              >
                {bl}
              </button>
              <button
                onClick={() => onToggleExpand(bl)}
                className="text-xs pr-2 py-1 transition-colors flex items-center"
                style={{
                  color: open ? chipColor : "rgba(107,114,128,0.6)",
                  borderLeft: "1px solid rgba(212,245,60,0.2)",
                }}
                aria-label={open ? "Bezirke ausblenden" : "Bezirke auswählen"}
              >
                <svg
                  viewBox="0 0 10 6"
                  className="w-2.5 h-2.5 transition-transform"
                  style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)" }}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="1,1 5,5 9,1" />
                </svg>
              </button>
            </div>
          ) : (
            // Not selected: normal chip
            <button
              key={bl}
              onClick={() => toggle(bl)}
              className="text-xs px-2.5 py-1 rounded-full border transition-colors"
              style={{ borderColor: chipBorder, color: chipColor, background: chipBg }}
            >
              {bl}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Per-bundesland bezirk picker ───────────────────────────────────────────

function BezirkPicker({
  bundesland,
  selected,
  onChange,
}: {
  bundesland: string
  selected: string[]
  onChange: (bezirke: string[]) => void
}) {
  const options = BEZIRKE_BY_BUNDESLAND[bundesland] ?? []
  if (options.length === 0) return null

  function toggle(b: string) {
    onChange(selected.includes(b) ? selected.filter(x => x !== b) : [...selected, b])
  }

  // Wien has 23 entries — use a 2-column checkbox grid; others use chip row
  const useGrid = options.length > 12

  return (
    <div
      className="mb-3 rounded-lg border px-3 pt-2.5 pb-3"
      style={{ borderColor: "rgba(107,114,128,0.2)", background: "rgba(0,0,0,0.2)" }}
    >
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] text-gray-600 tracking-widest uppercase">{bundesland}</p>
        <button
          onClick={() => onChange(selected.length === options.length ? [] : options)}
          className="text-[10px] text-gray-700 hover:text-gray-500 transition-colors"
        >
          {selected.length === options.length ? "alle abwählen" : "alle auswählen"}
        </button>
      </div>

      {useGrid ? (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {options.map(b => {
            const active = selected.includes(b)
            return (
              <label key={b} className="flex items-center gap-1.5 cursor-pointer group">
                <span
                  className="flex-shrink-0 w-3.5 h-3.5 rounded-sm border flex items-center justify-center transition-colors"
                  style={{
                    borderColor: active ? "#d4f53c" : "rgba(107,114,128,0.4)",
                    background: active ? "rgba(212,245,60,0.15)" : "transparent",
                  }}
                >
                  {active && (
                    <svg viewBox="0 0 10 10" className="w-2.5 h-2.5">
                      <polyline points="1.5,5 4,7.5 8.5,2.5" stroke="#d4f53c" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </span>
                <input type="checkbox" checked={active} onChange={() => toggle(b)} className="sr-only" />
                <span
                  className="text-[11px] leading-tight transition-colors"
                  style={{ color: active ? "#d4f53c" : "#6b7280" }}
                >
                  {b}
                </span>
              </label>
            )
          })}
        </div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {options.map(b => {
            const active = selected.includes(b)
            return (
              <button
                key={b}
                onClick={() => toggle(b)}
                className="text-[11px] px-2 py-0.5 rounded-full border transition-colors"
                style={{
                  borderColor: active ? "#d4f53c" : "rgba(107,114,128,0.3)",
                  color: active ? "#d4f53c" : "#6b7280",
                  background: active ? "rgba(212,245,60,0.08)" : "transparent",
                }}
              >
                {b}
              </button>
            )
          })}
        </div>
      )}
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
  // UI-only: which bundesländer have their district picker open
  const [expandedBl, setExpandedBl] = useState<string[]>([])
  const [venueExpanded, setVenueExpanded] = useState(false)
  // Venue options fetched from API, scoped to selected bundesländer
  const [venueOptions, setVenueOptions] = useState<string[]>([])

  function toggleExpand(bl: string) {
    setExpandedBl(prev =>
      prev.includes(bl) ? prev.filter(x => x !== bl) : [...prev, bl]
    )
  }

  // Fetch venue options whenever bundesland selection changes
  useEffect(() => {
    const params = new URLSearchParams()
    if (filters.bundesland.length) params.set("bundesland", filters.bundesland.join(","))
    fetch(`${API_BASE}/api/tournaments/venues?${params}`)
      .then(r => r.json())
      .then(data => setVenueOptions(data.venues ?? []))
      .catch(() => setVenueOptions([]))
  }, [filters.bundesland])

  function updateFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters(prev => {
      const extra: Partial<Filters> = {}
      if (key === "bundesland") {
        // Collapse district pickers for bundesländer that got deselected
        const next_bl = value as string[]
        setExpandedBl(e => e.filter(bl => next_bl.includes(bl)))
        // Reset venue — selections may not exist in the new bundesland scope
        extra.venue = []
      }
      const next = { ...prev, ...extra, [key]: value }
      saveFilters(next)
      return next
    })
  }

  function updateBezirk(bundesland: string, bezirke: string[]) {
    setFilters(prev => {
      const next = {
        ...prev,
        bezirkByBundesland: { ...prev.bezirkByBundesland, [bundesland]: bezirke },
      }
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
      const bezirke = allSelectedBezirke(f)
      if (bezirke.length) params.set("bezirk", bezirke.join(","))
      if (f.venue.length) params.set("venue_name", f.venue.join(","))
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

  useEffect(() => {
    fetchTournaments(filters)
  }, [filters, fetchTournaments])

  function resetFilters() {
    const f = defaultFilters()
    saveFilters(f)
    setFilters(f)
  }

  const totalBezirkeSelected = allSelectedBezirke(filters).length
  const hasActiveFilters = (
    filters.bundesland.length > 0 ||
    totalBezirkeSelected > 0 ||
    filters.venue.length > 0 ||
    filters.kategorie.length > 0 ||
    filters.wettbewerb.length > 0 ||
    filters.wochentag.length > 0 ||
    filters.onlyOpensSoon
  )

  // "Öffnet bald" is a time-derived label, so we filter client-side rather than
  // round-tripping a date query to the API.
  const visibleTournaments = filters.onlyOpensSoon
    ? tournaments.filter(opensSoon)
    : tournaments

  return (
    <section className="mt-2 pb-12">
      {/* Intro */}
      <div className="mb-6 space-y-3 px-1">
        <p className="text-white text-lg font-semibold">Turnierjagd</p>
        <p className="text-gray-400 text-base leading-relaxed">
          Turniere überall verstreut. Viele Bundesländer, viele Kategorien, kein System.
          Niemand hat dafür Zeit. Also ich. Eine Liste. Fertig.
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

        <BundeslandChips
          selected={filters.bundesland}
          expanded={expandedBl}
          onChange={v => updateFilter("bundesland", v)}
          onToggleExpand={toggleExpand}
        />

        {/* Bezirk pickers — only for expanded bundesländer */}
        {expandedBl.filter(bl => filters.bundesland.includes(bl)).length > 0 && (
          <div className="mt-3 mb-4">
            {filters.bundesland
              .filter(bl => expandedBl.includes(bl))
              .map(bl => (
                <BezirkPicker
                  key={bl}
                  bundesland={bl}
                  selected={filters.bezirkByBundesland[bl] ?? []}
                  onChange={bezirke => updateBezirk(bl, bezirke)}
                />
              ))}
          </div>
        )}

        {/* Venue / Standort — collapsible multi-select checkbox list */}
        {venueOptions.length > 0 && (
          <div className="mb-4 mt-4">
            <div className="flex items-center justify-between mb-2">
              <button
                onClick={() => setVenueExpanded(v => !v)}
                className="flex items-center gap-1.5 group"
              >
                <p className="text-xs text-gray-500 tracking-wide uppercase">Standort</p>
                {filters.venue.length > 0 && (
                  <span className="text-xs font-bold" style={{ color: "#d4f53c" }}>
                    ({filters.venue.length})
                  </span>
                )}
                <svg
                  viewBox="0 0 10 6"
                  className="w-2.5 h-2.5 transition-transform"
                  style={{ transform: venueExpanded ? "rotate(180deg)" : "rotate(0deg)", color: venueExpanded ? "#d4f53c" : "#6b7280" }}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="1,1 5,5 9,1" />
                </svg>
              </button>
              {filters.venue.length > 0 && (
                <button
                  onClick={() => updateFilter("venue", [])}
                  className="text-[10px] text-gray-700 hover:text-gray-500 transition-colors"
                >
                  alle abwählen
                </button>
              )}
            </div>
            {venueExpanded && (
              <div
                className="rounded-lg border overflow-y-auto"
                style={{
                  borderColor: filters.venue.length ? "#d4f53c" : "rgba(107,114,128,0.3)",
                  maxHeight: "11rem",
                  background: "rgba(0,0,0,0.2)",
                }}
              >
                {venueOptions.map(v => {
                  const active = filters.venue.includes(v)
                  return (
                    <label
                      key={v}
                      className="flex items-center gap-2.5 px-3 py-1.5 cursor-pointer transition-colors"
                      style={{ background: active ? "rgba(212,245,60,0.05)" : "transparent" }}
                    >
                      <span
                        className="flex-shrink-0 w-3.5 h-3.5 rounded-sm border flex items-center justify-center"
                        style={{
                          borderColor: active ? "#d4f53c" : "rgba(107,114,128,0.4)",
                          background: active ? "rgba(212,245,60,0.15)" : "transparent",
                        }}
                      >
                        {active && (
                          <svg viewBox="0 0 10 10" className="w-2.5 h-2.5">
                            <polyline points="1.5,5 4,7.5 8.5,2.5" stroke="#d4f53c" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        )}
                      </span>
                      <input
                        type="checkbox"
                        checked={active}
                        onChange={() => {
                          const next = active
                            ? filters.venue.filter(x => x !== v)
                            : [...filters.venue, v]
                          updateFilter("venue", next)
                        }}
                        className="sr-only"
                      />
                      <span className="text-xs truncate" style={{ color: active ? "#d4f53c" : "#9ca3af" }}>
                        {v}
                      </span>
                    </label>
                  )
                })}
              </div>
            )}
          </div>
        )}

        <MultiChip
          label="Wochentag"
          options={WOCHENTAGE}
          selected={filters.wochentag}
          onChange={v => updateFilter("wochentag", v)}
        />
        <MultiChip
          label="Level"
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

        {/* Show full / show closed */}
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
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={filters.onlyOpensSoon}
              onChange={e => updateFilter("onlyOpensSoon", e.target.checked)}
              className="accent-lime-400"
            />
            <span className="text-xs" style={{ color: "#60a5fa" }}>Nur bald öffnende Anmeldungen</span>
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
            {visibleTournaments.length === 0
              ? "Keine Turniere gefunden"
              : visibleTournaments.length === 1
              ? "1 Turnier"
              : `${visibleTournaments.length} Turniere`}
          </p>
          {lastUpdated && (
            <p className="text-xs text-gray-700">Stand: {lastUpdated}</p>
          )}
        </div>
      )}

      {loading && (
        <div className="text-center py-10">
          <p className="text-gray-600 text-sm">Yara jagt …</p>
        </div>
      )}

      {error && !loading && (
        <p className="text-red-400 text-sm px-1">{error}</p>
      )}

      {!loading && !error && visibleTournaments.length > 0 && (
        <div className="space-y-6 mb-6">
          {RESULT_SECTIONS.map(s => {
            const items = visibleTournaments.filter(s.match)
            if (items.length === 0) return null
            return (
              <div key={s.title}>
                <div className="px-1 mb-2">
                  <p
                    className="text-sm font-semibold"
                    style={{ fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.04em", color: s.color }}
                  >
                    {s.title.toUpperCase()}
                    <span style={{ color: "rgba(107,114,128,0.7)" }}> · {items.length}</span>
                  </p>
                  {s.subtitle && <p className="text-xs text-gray-500 mt-0.5">{s.subtitle}</p>}
                </div>
                <div className="rounded-xl border border-gray-800 bg-gray-900 divide-y divide-gray-800">
                  {items.map(t => (
                    <TournamentCard key={`${t.source}:${t.source_id}`} t={t} />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {!loading && !error && visibleTournaments.length === 0 && (
        <div className="text-center py-10">
          <p className="text-3xl mb-3">🎾</p>
          <p className="text-white font-semibold mb-1">Keine Turniere gefunden.</p>
          <p className="text-gray-500 text-sm">
            {filters.onlyOpensSoon
              ? "Gerade öffnet keine Anmeldung in den nächsten Tagen. Filter anpassen."
              : "Filter anpassen oder mehr Optionen aktivieren."}
          </p>
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
