import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import type { Tournament } from "../types"
import { CategoryPill } from "./TournamentCard"
import { formatTime as fmtTime } from "../utils/tournamentFormat"

const DAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
const DAY_NAMES_FULL = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

function getMonday(d: Date): Date {
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  const monday = new Date(d)
  monday.setDate(d.getDate() + diff)
  monday.setHours(0, 0, 0, 0)
  return monday
}

function addDays(d: Date, n: number): Date {
  const result = new Date(d)
  result.setDate(d.getDate() + n)
  return result
}

function localDateKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

function sameDay(a: Date, b: Date): boolean {
  return localDateKey(a) === localDateKey(b)
}

function weekLabel(weekStart: Date): string {
  const end = addDays(weekStart, 6)
  const startStr = weekStart.toLocaleDateString("de-AT", { day: "numeric", month: "short" })
  const endStr = end.toLocaleDateString("de-AT", { day: "numeric", month: "short" })
  return `${startStr} – ${endStr}`
}

// Compare tournament starts_at string (YYYY-MM-DD prefix) to a day's local date key.
// Avoids new Date() parsing quirks by slicing the date part directly.
function tournamentOnDay(t: Tournament, day: Date): boolean {
  if (!t.starts_at) return false
  return t.starts_at.slice(0, 10) === localDateKey(day)
}

function forDay(tournaments: Tournament[], day: Date): Tournament[] {
  return tournaments.filter(t => tournamentOnDay(t, day))
}

function firstWeekWithResults(tournaments: Tournament[], from: Date): Date {
  let weekStart = getMonday(from)
  for (let w = 0; w < 26; w++) {
    const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))
    if (days.some(day => forDay(tournaments, day).length > 0)) return weekStart
    weekStart = addDays(weekStart, 7)
  }
  return getMonday(from)
}

function CompactCard({ t }: { t: Tournament }) {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => navigate(`/turnierjaeger/turnier/${t.source_id}`)}
      className="w-full text-left px-2 py-1.5 rounded-lg mb-1 transition-colors"
      style={{ background: "rgba(212,245,60,0.05)", border: "1px solid rgba(212,245,60,0.08)" }}
      onMouseEnter={e => (e.currentTarget.style.background = "rgba(212,245,60,0.1)")}
      onMouseLeave={e => (e.currentTarget.style.background = "rgba(212,245,60,0.05)")}
    >
      <p className="text-white text-xs font-semibold leading-snug truncate mb-0.5">{t.title}</p>
      <div className="flex items-center gap-1 flex-wrap">
        {t.starts_at && (
          <span className="text-[10px]" style={{ color: "#6b7280" }}>{fmtTime(t.starts_at)}</span>
        )}
        {t.category && <CategoryPill label={t.category} />}
      </div>
    </button>
  )
}

export default function TournamentCalendar({ tournaments }: { tournaments: Tournament[] }) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const [weekStart, setWeekStart] = useState(() => getMonday(today))
  const [selectedDay, setSelectedDay] = useState<Date>(today)

  // Auto-jump to first week with results when tournaments load (or change).
  // Only jumps if the current week view is empty — respects manual navigation.
  useEffect(() => {
    if (tournaments.length === 0) return
    const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))
    const currentWeekHasResults = days.some(day => forDay(tournaments, day).length > 0)
    if (!currentWeekHasResults) {
      const target = firstWeekWithResults(tournaments, today)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setWeekStart(target)
      setSelectedDay(target)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tournaments])

  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))

  function goToWeek(newWeekStart: Date) {
    setWeekStart(newWeekStart)
    // Mobile: reset selected day to Monday so something is always highlighted
    setSelectedDay(newWeekStart)
  }

  return (
    <>
      {/* Desktop: week grid (≥640px) */}
      <div className="hidden sm:block">
        <div className="flex items-center justify-between mb-4 px-1">
          <button
            onClick={() => goToWeek(addDays(weekStart, -7))}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: "#6b7280", background: "rgba(107,114,128,0.1)" }}
            onMouseEnter={e => (e.currentTarget.style.color = "#d4f53c")}
            onMouseLeave={e => (e.currentTarget.style.color = "#6b7280")}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <span className="text-sm text-white" style={{ fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.04em" }}>
            {weekLabel(weekStart).toUpperCase()}
          </span>
          <button
            onClick={() => goToWeek(addDays(weekStart, 7))}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: "#6b7280", background: "rgba(107,114,128,0.1)" }}
            onMouseEnter={e => (e.currentTarget.style.color = "#d4f53c")}
            onMouseLeave={e => (e.currentTarget.style.color = "#6b7280")}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </button>
        </div>

        <div className="grid grid-cols-7 gap-1">
          {days.map((day, i) => {
            const isToday = sameDay(day, today)
            const items = forDay(tournaments, day)
            return (
              <div
                key={i}
                className="rounded-lg p-1.5 min-h-[80px]"
                style={{
                  background: isToday ? "rgba(212,245,60,0.05)" : "rgba(255,255,255,0.02)",
                  border: isToday ? "1px solid rgba(212,245,60,0.2)" : "1px solid rgba(107,114,128,0.15)",
                }}
              >
                <div className="text-center mb-1.5">
                  <p
                    className="text-[10px] font-semibold"
                    style={{ fontFamily: "'Barlow Condensed', sans-serif", color: isToday ? "#d4f53c" : "#6b7280", letterSpacing: "0.05em" }}
                  >
                    {DAY_NAMES[i]}
                  </p>
                  <p className="text-xs font-bold" style={{ color: isToday ? "#d4f53c" : "#9ca3af" }}>
                    {day.getDate()}
                  </p>
                </div>
                {items.map(t => <CompactCard key={t.source_id} t={t} />)}
              </div>
            )
          })}
        </div>
      </div>

      {/* Mobile: day strip + list (<640px) */}
      <div className="sm:hidden">
        <div className="flex items-center justify-between mb-3">
          <button onClick={() => goToWeek(addDays(weekStart, -7))} className="p-1.5 rounded" style={{ color: "#6b7280" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <span className="text-xs text-gray-500">{weekLabel(weekStart)}</span>
          <button onClick={() => goToWeek(addDays(weekStart, 7))} className="p-1.5 rounded" style={{ color: "#6b7280" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </button>
        </div>

        <div className="flex gap-1.5 overflow-x-auto pb-2 mb-4 scrollbar-hide">
          {days.map((day, i) => {
            const isSelected = sameDay(day, selectedDay)
            const isToday = sameDay(day, today)
            const hasTournaments = forDay(tournaments, day).length > 0
            return (
              <button
                key={i}
                onClick={() => setSelectedDay(day)}
                className="flex-shrink-0 flex flex-col items-center px-3 py-1.5 rounded-lg transition-colors"
                style={{
                  background: isSelected ? "#d4f53c" : isToday ? "rgba(212,245,60,0.08)" : "rgba(255,255,255,0.03)",
                  border: isToday && !isSelected ? "1px solid rgba(212,245,60,0.2)" : "1px solid transparent",
                }}
              >
                <span
                  className="text-[10px] font-semibold"
                  style={{ color: isSelected ? "#080810" : "#6b7280", fontFamily: "'Barlow Condensed', sans-serif" }}
                >
                  {DAY_NAMES[i]}
                </span>
                <span className="text-sm font-bold" style={{ color: isSelected ? "#080810" : "#fff" }}>
                  {day.getDate()}
                </span>
                {hasTournaments && (
                  <span
                    className="w-1 h-1 rounded-full mt-0.5"
                    style={{ background: isSelected ? "#080810" : "#d4f53c" }}
                  />
                )}
              </button>
            )
          })}
        </div>

        <div>
          <p
            className="text-xs font-semibold mb-2"
            style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "rgba(212,245,60,0.5)", letterSpacing: "0.04em" }}
          >
            {DAY_NAMES_FULL[days.findIndex(d => sameDay(d, selectedDay))]?.toUpperCase() ?? ""}
            {" "}· {selectedDay.getDate()}.{selectedDay.getMonth() + 1}.
          </p>
          {forDay(tournaments, selectedDay).length === 0 ? (
            <p className="text-xs text-gray-600 py-4 text-center">Kein Turnier an diesem Tag</p>
          ) : (
            forDay(tournaments, selectedDay).map(t => <CompactCard key={t.source_id} t={t} />)
          )}
        </div>
      </div>
    </>
  )
}
