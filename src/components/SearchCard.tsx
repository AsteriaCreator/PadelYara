import { useState, useEffect, useRef } from "react"
import type { SearchParams } from "../types"
import { TIME_SLOTS } from "../constants"
import { suggest, type Suggestion, type Coords } from "../geocode"

// text-base (16 px) keeps iOS Safari/Chrome from auto-zooming on focus.
// text-sm (14 px) is below the 16 px threshold that triggers the zoom.
const inputClass = "bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-base text-white w-full focus:outline-none focus:border-gray-500"
const labelClass = "text-xs font-semibold uppercase tracking-wide pl-1"
const labelStyle = { color: "rgba(212,245,60,0.55)" }

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

function getNextFullHour(): { date: string; time: string } {
  const v = getNowVienna()
  let { year, month, day } = v
  let nextHour = v.hour + 1

  if (nextHour > 22) {
    // No useful slots remain today — default to tomorrow 07:00
    const tomorrow = new Date(year, month - 1, day + 1)
    year     = tomorrow.getFullYear()
    month    = tomorrow.getMonth() + 1
    day      = tomorrow.getDate()
    nextHour = 7
  } else if (nextHour < 7) {
    // Early morning before first slot — snap to 07:00 today
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
  return parseInt(timeStr) <= v.hour
}

export default function SearchCard({ onSearch, isLoading, courtFilter, onCourtFilterChange, statusFilter, onStatusFilterChange }: Props) {
  const { date: defaultDate, time: defaultTime } = getNextFullHour()

  const [date, setDate]           = useState(defaultDate)
  const [time, setTime]           = useState(defaultTime)
  const [location, setLocation]       = useState(getStoredLocation)
  const [radius, setRadius]           = useState(getStoredRadius)
  const [formError, setFormError]     = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [showSugg, setShowSugg]       = useState(false)
  const debounceRef                   = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapperRef                    = useRef<HTMLDivElement>(null)
  const userLocationRef               = useRef<Coords | undefined>(undefined)

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
  const minHour = v.hour + 1

  function handleDateChange(newDate: string) {
    setFormError(null)
    const vNow = getNowVienna()
    if (newDate === vNow.dateStr) {
      const min = vNow.hour + 1
      if (parseInt(time) < min) {
        const nextSlot = TIME_SLOTS.find(t => parseInt(t) >= min)
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
    onSearch({ date, time, court_type: "both", location: trimmedLocation, radius })
  }

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 rounded-xl border border-gray-800 p-4 mb-6">

      {/* Location + Radius */}
      <div className="flex flex-row gap-3 mb-3">
        <div className="flex flex-col gap-1 flex-1 min-w-0" ref={wrapperRef}>
          <label className={labelClass} style={labelStyle}>Wo?</label>
          <div className="relative">
            <input
              type="text"
              value={location}
              onChange={(e) => {
                const val = e.target.value
                setLocation(val)
                setFormError(null)
                if (debounceRef.current) clearTimeout(debounceRef.current)
                if (val.trim().length >= 3) {
                  debounceRef.current = setTimeout(async () => {
                    const results = await suggest(val, userLocationRef.current)
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
                if (!userLocationRef.current && navigator.geolocation) {
                  navigator.geolocation.getCurrentPosition(
                    (pos) => { userLocationRef.current = { lat: pos.coords.latitude, lon: pos.coords.longitude } },
                    () => { /* permission denied — fall back to importance sort */ }
                  )
                }
              }}
              placeholder="z.B. 2500 oder Baden"
              className={inputClass}
              autoComplete="off"
            />
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
        <div className="flex flex-col gap-1 w-28 shrink-0">
          <label className={labelClass} style={labelStyle}>Umkreis</label>
          <select
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
            className={inputClass}
          >
            {[5, 10, 20, 25, 50].map((km) => (
              <option key={km} value={km}>{km} km</option>
            ))}
          </select>
        </div>
      </div>

      {/* Date + Time — stack vertically on mobile (<640px) so the native iOS
          date picker (Tag/Monat/Jahr spinners) has enough width (~180px+).
          Side-by-side only on sm: and above. */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
        <div className="flex flex-col gap-1">
          <label className={labelClass} style={labelStyle}>Wann?</label>
          <input
            type="date"
            value={date}
            onChange={(e) => handleDateChange(e.target.value)}
            className={inputClass}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className={labelClass} style={labelStyle}>Ab wann?</label>
          <select
            value={time}
            onChange={(e) => handleTimeChange(e.target.value)}
            className={inputClass}
          >
            {TIME_SLOTS.map((t) => (
              <option key={t} value={t} disabled={isToday && parseInt(t) < minHour}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mb-3 flex items-start justify-between flex-wrap gap-y-3">
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
                <span className="text-sm text-white capitalize">{type === "indoor" ? "Indoor" : "Outdoor"}</span>
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
                <span className="text-sm text-white capitalize">{s === "frei" ? "Frei" : "Belegt"}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {formError && (
        <p className="text-red-400 text-xs mb-2">{formError}</p>
      )}

      <button
        type="submit"
        style={{ backgroundColor: "#d4f53c", opacity: isLoading ? 0.7 : 1 }}
        className="w-full py-2.5 rounded-lg text-sm font-bold text-gray-900 tracking-wide flex items-center justify-center gap-2"
      >
        {isLoading && (
          <span className="animate-spin inline-block h-4 w-4 rounded-full border-2 border-gray-900 border-t-transparent" />
        )}
        {isLoading ? "LADEN…" : "SUCHEN"}
      </button>
    </form>
  )
}
