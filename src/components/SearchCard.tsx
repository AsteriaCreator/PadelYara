import { useState } from "react"
import type { SearchParams, Region, CourtType } from "../types"
import { REGION_ORDER, TIME_SLOTS } from "../constants"

const REGION_DISPLAY: Record<Region, string> = {
  "Bad Voeslau": "Bad Vöslau",
  "Wien Sued":   "Wien Süd",
  "Wien":        "Wien",
  "NOE Sued":    "NÖ Süd",
}

const inputClass = "bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white w-full focus:outline-none focus:border-gray-500"

interface Props {
  onSearch: (params: SearchParams) => void
  isLoading: boolean
}

function getNextFullHour(): { date: string; time: string } {
  const now  = new Date()
  // Add 1 hour; Date() handles midnight rollover automatically
  const next = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours() + 1)
  const pad  = (n: number) => String(n).padStart(2, "0")
  const date = `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`
  const time = `${pad(next.getHours())}:00`
  return { date, time }
}

export default function SearchCard({ onSearch, isLoading }: Props) {
  const { date: defaultDate, time: defaultTime } = getNextFullHour()

  const [date, setDate]           = useState(defaultDate)
  const [time, setTime]           = useState(defaultTime)
  const [region, setRegion]       = useState<Region>(REGION_ORDER[0])
  const [courtType, setCourtType] = useState<CourtType>("both")
  const [location, setLocation]   = useState("")
  const [radius, setRadius]       = useState(20)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onSearch({ date, time, region, court_type: courtType, location: location.trim() || undefined, radius })
  }

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 rounded-xl border border-gray-800 p-4 mb-6">
      <div className="flex flex-col sm:flex-row gap-3 mb-3">
        <div className="flex flex-col gap-1 flex-1 min-w-0">
          <label className="text-xs text-gray-500">PLZ oder Ort <span className="text-gray-600">(leer = Region)</span></label>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="z.B. 2500 oder Baden"
            className={inputClass}
          />
        </div>
        {location.trim() && (
          <div className="flex flex-col gap-1 sm:w-36 sm:shrink-0">
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
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">Datum</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputClass} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">Uhrzeit</label>
          <select value={time} onChange={(e) => setTime(e.target.value)} className={inputClass}>
            {TIME_SLOTS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">Region</label>
          <select value={region} onChange={(e) => setRegion(e.target.value as Region)} className={inputClass}>
            {REGION_ORDER.map((r) => <option key={r} value={r}>{REGION_DISPLAY[r]}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">Court</label>
          <select value={courtType} onChange={(e) => setCourtType(e.target.value as CourtType)} className={inputClass}>
            <option value="both">Indoor & Outdoor</option>
            <option value="indoor">Indoor</option>
            <option value="outdoor">Outdoor</option>
          </select>
        </div>
      </div>
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
