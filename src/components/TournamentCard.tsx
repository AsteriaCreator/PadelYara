import React from "react"
import type { Tournament } from "../types"

const DAYS_NEW = 7

function isNew(firstSeenAt: string | null): boolean {
  if (!firstSeenAt) return false
  const diffMs = Date.now() - new Date(firstSeenAt).getTime()
  return diffMs < DAYS_NEW * 24 * 60 * 60 * 1000
}

function spotsLeft(t: Tournament): number | null {
  if (!t.participants_max) return null
  return Math.max(0, t.participants_max - t.participants_current)
}

function StatusBadge({ t }: { t: Tournament }) {
  const spots = spotsLeft(t)

  if (t.status === "open" && spots !== null && spots > 0) {
    return (
      <span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: "rgba(212,245,60,0.15)", color: "#d4f53c" }}>
        {spots} {spots === 1 ? "Platz frei" : "Plätze frei"}
      </span>
    )
  }
  if (t.status === "open" && spots === 0) {
    return (
      <span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: "rgba(251,191,36,0.15)", color: "#fbbf24" }}>
        Warteliste{t.participants_waitlist > 0 ? ` (${t.participants_waitlist})` : ""}
      </span>
    )
  }
  if (t.status === "full") {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(107,114,128,0.2)", color: "#6b7280" }}>
        Ausgebucht{t.participants_waitlist > 0 ? ` · Warteliste (${t.participants_waitlist})` : ""}
      </span>
    )
  }
  if (t.status === "not_open_yet") {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(59,130,246,0.15)", color: "#60a5fa" }}>
        Anmeldung noch nicht offen
      </span>
    )
  }
  if (t.status === "closed") {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(107,114,128,0.15)", color: "#4b5563" }}>
        Anmeldung geschlossen
      </span>
    )
  }
  if (t.status === "cancelled") {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(239,68,68,0.15)", color: "#f87171" }}>
        Abgesagt
      </span>
    )
  }
  return null
}

function formatDate(isoStr: string | null): string {
  if (!isoStr) return ""
  const d = new Date(isoStr)
  return d.toLocaleDateString("de-AT", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" })
}

function formatTime(isoStr: string | null): string {
  if (!isoStr) return ""
  const d = new Date(isoStr)
  return d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" })
}

function CategoryPill({ label }: { label: string }) {
  return (
    <span
      className="text-xs px-1.5 py-0.5 rounded"
      style={{ background: "rgba(212,245,60,0.08)", color: "rgba(212,245,60,0.6)", fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.04em" }}
    >
      {label.toUpperCase()}
    </span>
  )
}

export default function TournamentCard({ t }: { t: Tournament }) {
  const newBadge = isNew(t.first_seen_at)
  const isOpen = t.status === "open" || t.status === "not_open_yet"

  return (
    <a
      href={t.source_url}
      target="_blank"
      rel="noopener noreferrer"
      className="block px-4 py-3 transition-colors"
      style={{ opacity: isOpen ? 1 : 0.55 }}
      onMouseEnter={e => (e.currentTarget.style.background = "rgba(212,245,60,0.04)")}
      onMouseLeave={e => (e.currentTarget.style.background = "")}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Title row */}
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {newBadge && (
              <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ background: "rgba(212,245,60,0.2)", color: "#d4f53c" }}>
                NEU
              </span>
            )}
            <span className="text-white text-sm font-semibold leading-snug">{t.title}</span>
          </div>

          {/* Venue + location */}
          <p className="text-xs text-gray-500 mb-1.5 truncate">
            {t.venue_name}{t.bundesland ? ` · ${t.bundesland}` : ""}
          </p>

          {/* Date + time */}
          <p className="text-xs text-gray-400 mb-2">
            {formatDate(t.starts_at)}
            {t.starts_at ? `, ${formatTime(t.starts_at)} Uhr` : ""}
            {t.ends_at && t.ends_at !== t.starts_at ? ` – ${formatDate(t.ends_at)}` : ""}
          </p>

          {/* Pills */}
          <div className="flex flex-wrap gap-1.5">
            {t.competition && <CategoryPill label={t.competition} />}
            {t.category && <CategoryPill label={t.category} />}
          </div>
        </div>

        {/* Right side: status + participants */}
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <StatusBadge t={t} />
          {t.participants_max > 0 && (
            <span className="text-xs text-gray-600">
              {t.participants_current}/{t.participants_max}
            </span>
          )}
        </div>
      </div>
    </a>
  )
}
