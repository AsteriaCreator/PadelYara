import type { Tournament } from "../types"
import { isNew, opensSoon } from "../tournamentBadges"

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
        {t.registration_opens_at
          ? `Anmeldung ab ${formatDate(t.registration_opens_at, false)}`
          : "Anmeldung noch nicht offen"}
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

function formatDate(isoStr: string | null, includeYear = true): string {
  if (!isoStr) return ""
  const d = new Date(isoStr)
  return d.toLocaleDateString("de-AT", {
    weekday: "short", day: "2-digit", month: "2-digit",
    ...(includeYear ? { year: "numeric" } : {}),
  })
}

function formatTime(isoStr: string | null): string {
  if (!isoStr) return ""
  const d = new Date(isoStr)
  return d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" })
}

function isSameDay(a: string, b: string): boolean {
  return a.slice(0, 10) === b.slice(0, 10)
}

function formatDateRange(starts: string | null, ends: string | null): string {
  if (!starts) return ""
  if (!ends || ends === starts) {
    // No end info — just show start
    return `${formatDate(starts)}, ${formatTime(starts)} Uhr`
  }
  if (isSameDay(starts, ends)) {
    // Same day — show date once, time range
    return `${formatDate(starts)}, ${formatTime(starts)} – ${formatTime(ends)} Uhr`
  }
  // Multi-day — show date range (omit year on start to save space)
  return `${formatDate(starts, false)} – ${formatDate(ends)}`
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

export default function TournamentCard({ t, showLink, showShare }: { t: Tournament; showLink?: boolean; showShare?: boolean }) {
  const newBadge = isNew(t)
  const soonBadge = opensSoon(t)
  const isOpen = t.status === "open" || t.status === "not_open_yet"
  // padel-austria.at redirects expired tournament URLs to homepage — only link active ones
  // showLink overrides this (e.g. Meine Turniere where player is still competing)
  const isLinkable = showLink
    ? !!t.source_url
    : t.status === "open" || t.status === "not_open_yet" || t.status === "full"
  const Tag = isLinkable ? "a" : "div"

  return (
    <Tag
      {...(isLinkable ? { href: t.source_url, target: "_blank", rel: "noopener noreferrer" } : {})}
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

          {/* Pills */}
          <div className="flex flex-wrap gap-1.5">
            {t.competition && <CategoryPill label={t.competition} />}
            {t.category && <CategoryPill label={t.category} />}
          </div>
        </div>

        {/* Right side: status + participants + share */}
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <div className="flex items-center gap-1">
            <StatusBadge t={t} />
            {showShare && <ShareButton t={t} />}
          </div>
          {t.participants_max > 0 && (
            <span className="text-xs text-gray-600">
              {t.participants_current}/{t.participants_max}
            </span>
          )}
        </div>
      </div>
    </Tag>
  )
}
