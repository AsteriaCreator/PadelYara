import { useState, useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import { Helmet } from "react-helmet-async"
import type { Tournament } from "../types"
import { StatusBadge, CategoryPill, CalendarDropdown } from "../components/TournamentCard"
import { formatDateRange } from "../utils/tournamentFormat"
import { exportRegistrationReminder } from "../utils/icsExport"
import JagdAlarmModal from "../components/JagdAlarmModal"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"

export default function TournamentDetailPage() {
  const { sourceId } = useParams<{ sourceId: string }>()
  const [t, setT] = useState<Tournament | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [jagdAlarmOpen, setJagdAlarmOpen] = useState(false)

  useEffect(() => {
    if (!sourceId) return
    setLoading(true)
    setNotFound(false)
    fetch(`${API_BASE}/api/tournaments/${encodeURIComponent(sourceId)}`)
      .then(r => {
        if (r.status === 404) { setNotFound(true); return null }
        return r.json()
      })
      .then(data => { if (data) setT(data as Tournament) })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false))
  }, [sourceId])

  if (loading) {
    return (
      <section className="max-w-xl mx-auto px-4 py-10">
        <p className="text-gray-500 text-sm text-center">Yara sucht …</p>
      </section>
    )
  }

  if (notFound || !t) {
    return (
      <section className="max-w-xl mx-auto px-4 py-10 text-center">
        <p className="text-white font-semibold mb-2">Turnier nicht gefunden.</p>
        <Link to="/turnierjaeger" className="text-xs" style={{ color: "#d4f53c" }}>
          ← Zurück zum Turnierjäger
        </Link>
      </section>
    )
  }

  const title = `${t.title} – ${formatDateRange(t.starts_at, t.ends_at)} | PadelYara`
  const description = `${t.competition} ${t.category} in ${t.bundesland}. Jetzt auf PadelYara entdecken.`
  const canonicalUrl = `https://www.padelyara.at/turnierjaeger/turnier/${t.source_id}`

  const registrationOpensInFuture = !!t.registration_opens_at && new Date(t.registration_opens_at) > new Date()

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SportsEvent",
    "name": t.title,
    "startDate": t.starts_at,
    "endDate": t.ends_at,
    "location": { "@type": "Place", "name": t.venue_name, "address": t.bundesland },
    "url": canonicalUrl,
    "organizer": { "@type": "Organization", "name": "Austrian Padel Union", "url": "https://padel-austria.at" },
  }

  return (
    <section className="max-w-xl mx-auto px-4 py-6">
      <Helmet>
        <title>{title}</title>
        <meta name="description" content={description} />
        <link rel="canonical" href={canonicalUrl} />
      </Helmet>
      <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>

      {/* Back link */}
      <Link
        to="/turnierjaeger"
        className="inline-flex items-center gap-1 text-xs mb-5 transition-colors"
        style={{ color: "#6b7280" }}
        onMouseEnter={e => (e.currentTarget.style.color = "#9ca3af")}
        onMouseLeave={e => (e.currentTarget.style.color = "#6b7280")}
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
        Turnierjäger
      </Link>

      {/* Title */}
      <h1
        className="text-2xl font-bold text-white mb-3 leading-snug"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.02em" }}
      >
        {t.title}
      </h1>

      {/* Category + competition badges */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {t.competition && <CategoryPill label={t.competition} />}
        {t.category && <CategoryPill label={t.category} />}
      </div>

      {/* Detail grid */}
      <div
        className="rounded-xl border mb-6 divide-y"
        style={{ background: "#0d0d14", borderColor: "rgba(107,114,128,0.3)" }}
      >
        <Row label="Datum">
          {formatDateRange(t.starts_at, t.ends_at) || "–"}
        </Row>
        <Row label="Venue">
          {t.venue_name || "–"}
        </Row>
        <Row label="Bundesland">{t.bundesland || "–"}</Row>
        <Row label="Teilnehmer">
          {t.participants_max > 0
            ? `${t.participants_current} / ${t.participants_max}`
            : t.participants_current > 0 ? String(t.participants_current) : "–"}
          {t.participants_waitlist > 0 && (
            <span className="ml-2 text-xs" style={{ color: "#fbbf24" }}>
              +{t.participants_waitlist} Warteliste
            </span>
          )}
        </Row>
        <Row label="Status">
          <StatusBadge t={t} />
        </Row>
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-3 mb-8">
        {/* Registration link */}
        {t.source_url && (
          <a
            href={t.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full text-center py-3 rounded-xl font-bold text-sm tracking-wider transition-opacity hover:opacity-85"
            style={{ background: "#d4f53c", color: "#080810", fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.06em" }}
          >
            ZUR ANMELDUNG AUF PADEL-AUSTRIA.AT
          </a>
        )}

        {/* Secondary actions row */}
        <div className="flex items-center gap-3">
          <CalendarDropdown t={t} />
          {registrationOpensInFuture && (
            <button
              onClick={() => exportRegistrationReminder(t)}
              className="text-xs transition-colors"
              style={{ color: "#6b7280" }}
              onMouseEnter={e => (e.currentTarget.style.color = "#9ca3af")}
              onMouseLeave={e => (e.currentTarget.style.color = "#6b7280")}
            >
              ⏰ Anmeldung erinnern
            </button>
          )}
        </div>
      </div>

      {/* Jagd-Alarm CTA */}
      <div
        className="flex items-center justify-between gap-4 px-4 py-3 rounded-xl mb-6"
        style={{ background: "rgba(212,245,60,0.04)", border: "1px solid rgba(212,245,60,0.1)" }}
      >
        <div>
          <p className="text-xs font-bold tracking-wider text-white" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>JAGD-ALARM</p>
          <p className="text-xs text-gray-500 mt-0.5">Yara informiert dich automatisch über neue Turniere, die zu deinen Filtern passen.</p>
        </div>
        <button
          onClick={() => setJagdAlarmOpen(true)}
          className="flex-shrink-0 text-xs font-bold px-3 py-1.5 rounded-lg transition-opacity hover:opacity-80"
          style={{ fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.06em", background: "#d4f53c", color: "#000000" }}
        >
          AKTIVIEREN
        </button>
      </div>

      <JagdAlarmModal
        isOpen={jagdAlarmOpen}
        onClose={() => setJagdAlarmOpen(false)}
        filters={{ bundeslaender: [], categories: [], competitions: [], weekdays: [], venueNames: [] }}
      />
    </section>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-4 px-4 py-3">
      <span
        className="text-xs shrink-0 w-24"
        style={{ color: "#6b7280", fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.04em", paddingTop: "1px" }}
      >
        {label.toUpperCase()}
      </span>
      <span className="text-sm text-white">{children}</span>
    </div>
  )
}
