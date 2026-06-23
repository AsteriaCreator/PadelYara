import { useState, useEffect, useRef } from "react"
import type { SearchParams, CourtType } from "../types"
import { TIME_SLOTS, DURATION_OPTIONS, DEFAULT_DURATIONS } from "../constants"
import { suggest, type Suggestion } from "../geocode"

// 16 px floor prevents iOS Safari auto-zoom on input focus
const inputClass = "bg-gray-800/60 border border-gray-700/70 rounded-lg px-3 text-base text-white w-full focus:outline-none focus-visible:ring-1 focus-visible:ring-[#d4f53c] focus-visible:border-[#d4f53c] transition-colors"
const labelClass = "text-xs font-semibold uppercase tracking-wide pl-0.5"
const labelStyle = { color: "rgba(212,245,60,0.7)" }

const VALID_RADII = [5, 10, 20, 25, 50]
const LS_LOCATION = "padel_location"
const LS_RADIUS   = "padel_radius"

function getStoredLocation(): string {
  try { return localStorage.getItem(LS_LOCATION) ?? "" } catch { return "" }
}
function getStoredRadius(): number {
  try {
    const n = Number(localStorage.getItem(LS_RADIUS))
    return VALID_RADII.includes(n) ? n : 20
  } catch { return 20 }
}

interface Props {
  onSearch: (params: SearchParams) => void
  isLoading: boolean
  courtFilter: { indoor: boolean; outdoor: boolean }
  onCourtFilterChange: (filter: { indoor: boolean; outdoor: boolean }) => void
  statusFilter: { frei: boolean; belegt: boolean }
  onStatusFilterChange: (filter: { frei: boolean; belegt: boolean }) => void
  initialLocation?: string
  initialDate?: string
  initialTime?: string
  initialRadius?: number
  initialDurations?: number[]
}

// "sv-SE" locale produces "YYYY-MM-DD HH:mm:ss" — stable cross-browser
function getNowVienna() {
  const now       = new Date()
  const viennaStr = now.toLocaleString("sv-SE", { timeZone: "Europe/Vienna" })
  const [datePart, timePart] = viennaStr.split(" ")
  const [year, month, day]   = datePart.split("-").map(Number)
  const [hour, minute]       = timePart.split(":").map(Number)
  return { year, month, day, hour, minute, dateStr: datePart }
}

const pad = (n: number) => String(n).padStart(2, "0")
const toMin = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number)
  return h * 60 + m
}

function getNextFullHour(): { date: string; time: string } {
  const v = getNowVienna()
  let { year, month, day } = v
  let nextHour = v.hour + 1

  if (nextHour > 22) {
    const tomorrow = new Date(year, month - 1, day + 1)
    year     = tomorrow.getFullYear()
    month    = tomorrow.getMonth() + 1
    day      = tomorrow.getDate()
    nextHour = 7
  } else if (nextHour < 7) {
    nextHour = 7
  }

  return {
    date: `${year}-${pad(month)}-${pad(day)}`,
    time: `${pad(nextHour)}:00`,
  }
}

function isSelectedPast(dateStr: string, timeStr: string): boolean {
  const v = getNowVienna()
  if (dateStr > v.dateStr) return false
  if (dateStr < v.dateStr) return true
  return toMin(timeStr) <= v.hour * 60 + v.minute
}

// Location pin SVG — inline, no icon library dependency
function GeoIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      style={spinning ? { animation: "spin 1s linear infinite" } : undefined}
      aria-hidden="true"
    >
      {spinning ? (
        <path d="M12 2a10 10 0 0 1 10 10" />
      ) : (
        <>
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
        </>
      )}
    </svg>
  )
}

export default function SearchCard({ onSearch, isLoading, courtFilter, onCourtFilterChange, statusFilter, onStatusFilterChange, initialLocation, initialDate, initialTime, initialRadius, initialDurations }: Props) {
  const { date: defaultDate, time: defaultTime } = getNextFullHour()

  const [date, setDate]               = useState(initialDate || defaultDate)
  const [time, setTime]               = useState(initialTime || defaultTime)
  const [location, setLocation]       = useState(initialLocation || getStoredLocation())
  const [radius, setRadius]           = useState(initialRadius || getStoredRadius())
  const [durations, setDurations]     = useState<number[]>(initialDurations ?? DEFAULT_DURATIONS)
  const [formError, setFormError]     = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [showSugg, setShowSugg]       = useState(false)
  const [geoAvailable]              = useState(() => "geolocation" in navigator)
  const [geoLoading, setGeoLoading] = useState(false)
  const debounceRef                 = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapperRef                  = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowSugg(false)
      }
    }
    document.addEventListener("pointerdown", onPointerDown)
    return () => document.removeEventListener("pointerdown", onPointerDown)
  }, [])

  const v       = getNowVienna()
  const isToday = date === v.dateStr
  const nowMin  = v.hour * 60 + v.minute

  async function handleGeolocate() {
    if (!geoAvailable || geoLoading) return
    setGeoLoading(true)
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 6000 })
      })
      const { latitude, longitude } = position.coords
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&accept-language=de`,
        { signal: AbortSignal.timeout(5000) }
      )
      if (!res.ok) return
      const data = await res.json()
      const plz = data.address?.postcode || data.address?.city || data.address?.town || data.address?.village
      if (plz) {
        setLocation(String(plz))
        setFormError(null)
        setSuggestions([])
        setShowSugg(false)
      }
    } catch {
      // silent failure
    } finally {
      setGeoLoading(false)
    }
  }

  function handleDateChange(newDate: string) {
    setFormError(null)
    const vNow = getNowVienna()
    if (newDate === vNow.dateStr) {
      const min = vNow.hour * 60 + vNow.minute
      if (toMin(time) <= min) {
        const nextSlot = TIME_SLOTS.find(t => toMin(t) > min)
        if (nextSlot) {
          setTime(nextSlot)
        } else {
          const { date: nd, time: nt } = getNextFullHour()
          setDate(nd)
          setTime(nt)
          return
        }
      }
    }
    setDate(newDate)
  }

  function handleTimeChange(newTime: string) {
    setTime(newTime)
    setFormError(null)
  }

  function toggleDuration(value: number) {
    setFormError(null)
    setDurations((prev) => {
      if (prev.includes(value)) {
        if (prev.length === 1) return prev
        return prev.filter((d) => d !== value)
      }
      return [...prev, value].sort((a, b) => a - b)
    })
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (isSelectedPast(date, time)) {
      setFormError("Diese Uhrzeit ist bereits vorbei.")
      return
    }

    const trimmedLocation = location.trim()
    if (!trimmedLocation) {
      setFormError("Bitte PLZ oder Ort eingeben.")
      return
    }

    setFormError(null)
    const court_type: CourtType =
      courtFilter.indoor && courtFilter.outdoor ? "both"
      : courtFilter.indoor ? "indoor"
      : courtFilter.outdoor ? "outdoor"
      : "both"
    onSearch({ date, time, court_type, location: trimmedLocation, radius, durations })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl mb-6"
      style={{
        background: "#111318",
        backgroundImage: "linear-gradient(180deg, rgba(212,245,60,0.05) 0%, rgba(212,245,60,0) 64px)",
        border: "1px solid rgba(212,245,60,0.12)",
        borderTopColor: "rgba(212,245,60,0.28)",
        padding: "1.25rem",
      }}
    >
      {/* Location + Radius */}
      <div className="flex flex-row gap-3 mb-4">
        <div className="flex flex-col gap-1.5 flex-1 min-w-0" ref={wrapperRef}>
          <label htmlFor="sc-location" className={labelClass} style={labelStyle}>Wo?</label>
          <div className="relative">
            <input
              id="sc-location"
              type="text"
              value={location}
              onChange={(e) => {
                const val = e.target.value
                setLocation(val)
                setFormError(null)
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
              onFocus={() => {
                if (suggestions.length > 0) setShowSugg(true)
              }}
              placeholder="z.B. 2500 oder Baden"
              className={`${inputClass} py-2.5 ${geoAvailable ? "pr-9" : "pr-3"}`}
              autoComplete="off"
              style={{ fontSize: "max(16px, 1em)" }}
            />
            {geoAvailable && (
              <button
                type="button"
                onClick={handleGeolocate}
                aria-label="Meinen Standort verwenden"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 transition-colors"
                style={{ color: geoLoading ? "rgba(212,245,60,0.9)" : "rgba(212,245,60,0.45)" }}
                onMouseEnter={e => { if (!geoLoading) (e.currentTarget as HTMLButtonElement).style.color = "rgba(212,245,60,0.85)" }}
                onMouseLeave={e => { if (!geoLoading) (e.currentTarget as HTMLButtonElement).style.color = "rgba(212,245,60,0.45)" }}
              >
                <GeoIcon spinning={geoLoading} />
              </button>
            )}
            {showSugg && (
              <ul className="absolute z-50 left-0 right-0 top-full mt-1 bg-gray-800 border border-gray-700 rounded-lg overflow-hidden shadow-lg">
                {suggestions.map((s, i) => (
                  <li
                    key={i}
                    onPointerDown={(e) => {
                      e.preventDefault()
                      setLocation(s.label)
                      setSuggestions([])
                      setShowSugg(false)
                    }}
                    className="px-3 py-2 text-sm text-white cursor-pointer hover:bg-gray-700 truncate"
                  >
                    {s.label}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <div className="flex flex-col gap-1.5 w-28 shrink-0">
          <label htmlFor="sc-radius" className={labelClass} style={labelStyle}>Umkreis</label>
          <select
            id="sc-radius"
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
            className={`${inputClass} py-2.5`}
            style={{ fontSize: "max(16px, 1em)" }}
          >
            {[5, 10, 20, 25, 50].map((km) => (
              <option key={km} value={km}>{km} km</option>
            ))}
          </select>
        </div>
      </div>

      {/* Date + Time */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="sc-date" className={labelClass} style={labelStyle}>Wann?</label>
          <input
            id="sc-date"
            type="date"
            value={date}
            onChange={(e) => handleDateChange(e.target.value)}
            className={`${inputClass} py-2.5`}
            style={{ fontSize: "max(16px, 1em)" }}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="sc-time" className={labelClass} style={labelStyle}>Ab wann?</label>
          <select
            id="sc-time"
            value={time}
            onChange={(e) => handleTimeChange(e.target.value)}
            className={`${inputClass} py-2.5`}
            style={{ fontSize: "max(16px, 1em)" }}
          >
            {TIME_SLOTS.map((t) => (
              <option key={t} value={t} disabled={isToday && toMin(t) <= nowMin}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t mb-4" style={{ borderColor: "rgba(255,255,255,0.06)" }} />

      {/* Duration */}
      <div className="mb-4">
        <label className={`${labelClass} block mb-2`} style={labelStyle}>Wie lange?</label>
        <div className="flex gap-2">
          {DURATION_OPTIONS.map((opt) => {
            const active = durations.includes(opt.value)
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => toggleDuration(opt.value)}
                aria-pressed={active}
                className="px-3 py-1.5 rounded-lg text-sm font-semibold border transition-all"
                style={active ? {
                  backgroundColor: "#d4f53c",
                  borderColor: "#d4f53c",
                  color: "#080810",
                  boxShadow: "0 0 10px rgba(212,245,60,0.2)",
                } : {
                  backgroundColor: "transparent",
                  borderColor: "rgba(255,255,255,0.12)",
                  color: "#9ca3af",
                }}
                onMouseEnter={e => { if (!active) (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(212,245,60,0.4)" }}
                onMouseLeave={e => { if (!active) (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(255,255,255,0.12)" }}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Court type + Availability */}
      <div className="mb-5 flex items-start justify-between flex-wrap gap-y-3">
        <div>
          <label className={`${labelClass} block mb-2`} style={labelStyle}>Court-Typ</label>
          <div className="flex gap-4">
            {(["indoor", "outdoor"] as const).map((type) => (
              <label key={type} className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={courtFilter[type]}
                  onChange={(e) => onCourtFilterChange({ ...courtFilter, [type]: e.target.checked })}
                  className="w-4 h-4 rounded accent-[#d4f53c] cursor-pointer"
                />
                <span className="text-sm text-white">{type === "indoor" ? "Indoor" : "Outdoor"}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className={`${labelClass} block mb-2`} style={labelStyle}>Verfügbarkeit</label>
          <div className="flex gap-4">
            {(["frei", "belegt"] as const).map((s) => (
              <label key={s} className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={statusFilter[s]}
                  onChange={(e) => onStatusFilterChange({ ...statusFilter, [s]: e.target.checked })}
                  className="w-4 h-4 rounded accent-[#d4f53c] cursor-pointer"
                />
                <span className="text-sm text-white">{s === "frei" ? "Frei" : "Belegt"}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {formError && (
        <p className="text-red-400 text-xs mb-3">{formError}</p>
      )}

      <button
        type="submit"
        disabled={isLoading}
        className="w-full py-3 rounded-lg text-sm font-bold tracking-wide flex items-center justify-center gap-2 transition-all"
        style={{
          backgroundColor: "#d4f53c",
          color: "#080810",
          opacity: isLoading ? 0.7 : 1,
          letterSpacing: "0.1em",
        }}
        onMouseEnter={e => { if (!isLoading) (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 20px rgba(212,245,60,0.28)" }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.boxShadow = "none" }}
      >
        {isLoading && (
          <span className="inline-block h-4 w-4 rounded-full border-2 border-gray-900 border-t-transparent animate-spin" />
        )}
        {isLoading ? "LADEN…" : "SUCHEN"}
      </button>
    </form>
  )
}
