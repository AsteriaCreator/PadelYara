import { useState, useRef, useEffect } from "react"
import { Link } from "react-router-dom"
import type { Tournament } from "../types"
import { isNew, opensSoon } from "../tournamentBadges"
import { exportToCalendar, exportRegistrationReminder, googleCalendarUrl } from "../utils/icsExport"
import { formatDate, formatDateRange } from "../utils/tournamentFormat"

function spotsLeft(t: Tournament): number | null {
  if (!t.participants_max) return null
  return Math.max(0, t.participants_max - t.participants_current)
}

export function StatusBadge({ t }: { t: Tournament }) {
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
        {t.registration_opens_at
          ? `Anmeldung ab ${formatDate(t.registration_opens_at, false)}`
          : "Anmeldung noch nicht offen"}
      </span>
    )
  }
  if (t.status === "closed") {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(107,114,128,0.15)", color: "#9ca3af" }}>
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


export function CategoryPill({ label }: { label: string }) {
  return (
    <span
      className="text-xs px-1.5 py-0.5 rounded"
      style={{ background: "rgba(212,245,60,0.08)", color: "rgba(212,245,60,0.6)", fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.04em" }}
    >
      {label.toUpperCase()}
    </span>
  )
}

function ShareButton({ t }: { t: Tournament }) {
  const share = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const text = `${t.title} – ${t.venue_name ?? ""}`
    const url = t.source_url ?? ""
    if (navigator.share) {
      void navigator.share({ title: t.title, text, url }).catch(() => {})
    } else {
      void navigator.clipboard.writeText(`${text}\n${url}`).catch(() => {})
    }
  }
  return (
    <button
      onClick={share}
      title="Teilen"
      className="shrink-0 p-1 rounded transition-colors"
      style={{ color: "rgba(212,245,60,0.5)" }}
      onMouseEnter={e => ((e.currentTarget as HTMLButtonElement).style.color = "#d4f53c")}
      onMouseLeave={e => ((e.currentTarget as HTMLButtonElement).style.color = "rgba(212,245,60,0.5)")}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
      </svg>
    </button>
  )
}

function BookmarkButton({ isBookmarked, onBookmark }: { isBookmarked: boolean; onBookmark: () => void }) {
  return (
    <button
      onClick={e => { e.preventDefault(); e.stopPropagation(); onBookmark() }}
      title={isBookmarked ? "Von Merkliste entfernen" : "Zur Merkliste hinzufügen"}
      aria-label={isBookmarked ? "Von Merkliste entfernen" : "Zur Merkliste hinzufügen"}
      className="shrink-0 p-1 rounded transition-colors"
      style={{ color: isBookmarked ? "#d4f53c" : "rgba(212,245,60,0.3)" }}
      onMouseEnter={e => { if (!isBookmarked) (e.currentTarget as HTMLButtonElement).style.color = "rgba(212,245,60,0.6)" }}
      onMouseLeave={e => { if (!isBookmarked) (e.currentTarget as HTMLButtonElement).style.color = "rgba(212,245,60,0.3)" }}
    >
      {isBookmarked ? (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M17 3H7a2 2 0 0 0-2 2v16l7-3 7 3V5a2 2 0 0 0-2-2z"/>
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 21l-7-3-7 3V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
        </svg>
      )}
    </button>
  )
}

export function CalendarDropdown({ t }: { t: Tournament }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", onOutside)
    return () => document.removeEventListener("mousedown", onOutside)
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={e => { e.preventDefault(); e.stopPropagation(); setOpen(o => !o) }}
        className="text-[10px] text-gray-600 hover:text-gray-400 transition-colors"
        title="Turnier zum Kalender hinzufügen"
      >
        + Kalender
      </button>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 rounded-lg border z-20 overflow-hidden"
          style={{ background: "#111118", borderColor: "rgba(107,114,128,0.4)", minWidth: "130px" }}
          onClick={e => e.stopPropagation()}
        >
          <a
            href={googleCalendarUrl(t)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 w-full text-left text-[11px] px-3 py-2 text-gray-400 hover:text-white transition-colors"
            style={{ textDecoration: "none" }}
            onMouseEnter={e => (e.currentTarget.style.background = "rgba(212,245,60,0.06)")}
            onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
          >
            Google Kalender
          </a>
          <button
            onClick={e => { e.preventDefault(); e.stopPropagation(); exportToCalendar(t); setOpen(false) }}
            className="flex items-center gap-2 w-full text-left text-[11px] px-3 py-2 text-gray-400 hover:text-white transition-colors"
            onMouseEnter={e => (e.currentTarget.style.background = "rgba(212,245,60,0.06)")}
            onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
          >
            Apple / .ics
          </button>
        </div>
      )}
    </div>
  )
}

export default function TournamentCard({ t, showLink, showShare, isBookmarked, onBookmark }: { t: Tournament; showLink?: boolean; showShare?: boolean; isBookmarked?: boolean; onBookmark?: () => void }) {
  const newBadge = isNew(t)
  const soonBadge = opensSoon(t)
  const isOpen = t.status === "open" || t.status === "not_open_yet"
  const isLinkable = showLink
    ? !!t.source_id
    : t.status === "open" || t.status === "not_open_yet" || t.status === "full"
  const detailUrl = `/turnierjaeger/turnier/${t.source_id}`

  const hoverStyle = { background: "rgba(212,245,60,0.04)" }
  const wrapperClass = "block px-4 py-3 transition-colors"
  const wrapperStyle = { opacity: isOpen ? 1 : 0.55 }

  const inner = (
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Title row */}
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {newBadge && (
              <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ background: "rgba(212,245,60,0.2)", color: "#d4f53c" }}>
                NEU
              </span>
            )}
            {soonBadge && (
              <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ background: "rgba(96,165,250,0.2)", color: "#60a5fa" }}>
                ÖFFNET BALD
              </span>
            )}
            <span className="text-white text-sm font-semibold leading-snug" style={{ userSelect: "text" }}>{t.title}</span>
          </div>

          {/* Venue + location */}
          <p className="text-xs text-gray-500 mb-1.5 truncate">
            {t.venue_name}{t.bundesland ? ` · ${t.bundesland}` : ""}
          </p>

          {/* Date + time */}
          <p className="text-xs text-gray-400 mb-2">
            {formatDateRange(t.starts_at, t.ends_at)}
          </p>

          {/* Pills + calendar actions */}
          <div className="flex flex-wrap items-center gap-1.5">
            {t.competition && <CategoryPill label={t.competition} />}
            {t.category && <CategoryPill label={t.category} />}
            <div className="flex items-center gap-2 ml-auto">
              {t.registration_opens_at && new Date(t.registration_opens_at) > new Date() && (
                <button
                  onClick={e => { e.preventDefault(); e.stopPropagation(); exportRegistrationReminder(t) }}
                  className="text-[10px] text-gray-600 hover:text-gray-400 transition-colors"
                  title="Erinnerung: Anmeldung öffnet"
                >
                  ⏰ Anmeldung
                </button>
              )}
              <CalendarDropdown t={t} />
            </div>
          </div>
        </div>

        {/* Right side: status + participants + share */}
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <div className="flex items-center gap-1">
            <StatusBadge t={t} />
            {showShare && <ShareButton t={t} />}
            {onBookmark !== undefined && <BookmarkButton isBookmarked={!!isBookmarked} onBookmark={onBookmark} />}
          </div>
          {t.participants_max > 0 && (
            <span className="text-xs text-gray-500">
              {t.participants_current}/{t.participants_max}
              {t.participants_waitlist > 0 && (
                <span style={{ color: "#fbbf24" }}> +{t.participants_waitlist} WL</span>
              )}
            </span>
          )}
        </div>
      </div>
  )

  if (isLinkable) {
    return (
      <Link
        to={detailUrl}
        className={wrapperClass}
        style={wrapperStyle}
        onMouseEnter={e => (e.currentTarget.style.background = hoverStyle.background)}
        onMouseLeave={e => (e.currentTarget.style.background = "")}
      >{inner}</Link>
    )
  }
  return (
    <div
      className={wrapperClass}
      style={wrapperStyle}
      onMouseEnter={e => (e.currentTarget.style.background = hoverStyle.background)}
      onMouseLeave={e => (e.currentTarget.style.background = "")}
    >{inner}</div>
  )
}
