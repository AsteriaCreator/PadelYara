import { useState } from "react"
import type { SearchParams, CourtType } from "../types"
import { TIME_SLOTS } from "../constants"

const inputClass = "bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white w-full focus:outline-none focus:border-gray-500"

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
    // No useful slots remain today — default to tomorrow 18:00
    const tomorrow = new Date(year, month - 1, day + 1)
    year     = tomorrow.getFullYear()
    month    = tomorrow.getMonth() + 1
    day      = tomorrow.getDate()
    nextHour = 18
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

export default function SearchCard({ onSearch, isLoading }: Props) {
  const { date: defaultDate, time: defaultTime } = getNextFullHour()

  const [date, setDate]           = useState(defaultDate)
  const [time, setTime]           = useState(defaultTime)
  const [courtType, setCourtType] = useState<CourtType>("both")
  const [location, setLocation]   = useState(getStoredLocation)
  const [radius, setRadius]       = useState(getStoredRadius)
  const [formError, setFormError] = useState<string | null>(null)

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

    if (!location.trim()) {
      setFormError("Bitte PLZ oder Ort eingeben.")
      return
    }

    setFormError(null)
    const trimmedLocation = location.trim()
    onSearch({ date, time, court_type: courtType, location: trimmedLocation, radius })
  }

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 rounded-xl border border-gray-800 p-4 mb-6">

      {/* Location + Radius */}
      <div className="flex flex-row gap-3 mb-3">
        <div className="flex flex-col gap-1 flex-1 min-w-0">
          <label className="text-xs text-gray-500">PLZ oder Ort</label>
          <input
            type="text"
            value={location}
            onChange={(e) => { setLocation(e.target.value); setFormError(null) }}
            placeholder="z.B. 2500 oder Baden"
            className={inputClass}
          />
        </div>
        <div className="flex flex-col gap-1 w-28 shrink-0">
          <label className="text-xs text-gray-500">Radius</label>
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

      {/* Date + Time + Court */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">Datum</label>
          <input
            type="date"
            value={date}
            onChange={(e) => handleDateChange(e.target.value)}
            className={inputClass}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">Uhrzeit</label>
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
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">Court</label>
          <select
            value={courtType}
            onChange={(e) => setCourtType(e.target.value as CourtType)}
            className={inputClass}
          >
            <option value="both">Indoor & Outdoor</option>
            <option value="indoor">Indoor</option>
            <option value="outdoor">Outdoor</option>
          </select>
        </div>
      </div>

      {formError && (
        <p className="text-red-400 text-xs mb-2">{formError}</p>
      )}

      <button
        type="submit"
        disabled={isLoading}
        style={{ backgroundColor: "#d4f53c" }}
        className="w-full py-2.5 rounded-lg text-sm font-bold text-gray-900 tracking-wide disabled:opacity-50"
      >
        {isLoading ? "LADEN…" : "SUCHEN"}
      </button>
    </form>
  )
}
