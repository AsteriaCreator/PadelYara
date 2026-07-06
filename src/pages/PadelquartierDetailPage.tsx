import { Helmet } from "react-helmet-async"
import { Link, useNavigate, useParams } from "react-router-dom"
import { PADELQUARTIER_ENTRIES } from "../data/padelquartier"

export default function PadelquartierDetailPage() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const entry = PADELQUARTIER_ENTRIES.find(e => e.id === slug)

  if (!entry) {
    navigate("/padelquartier", { replace: true })
    return null
  }

  const title = `${entry.name} — ${entry.type === "hotel" ? "Padel-Hotel" : "Padel-Reisen"} | PadelYara`
  const description = entry.description

  const jsonLd = entry.type === "hotel"
    ? {
        "@context": "https://schema.org",
        "@type": "LodgingBusiness",
        "name": entry.name,
        "description": description,
        "address": entry.address ?? `${entry.city}, ${entry.bundesland}`,
        "url": entry.websiteUrl,
      }
    : {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": entry.name,
        "description": description,
        "url": entry.websiteUrl,
      }

  return (
    <>
      <Helmet>
        <title>{title}</title>
        <meta name="description" content={description} />
        <meta name="robots" content="noindex, follow" />
        <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      </Helmet>

      <p className="text-xs text-gray-500 mb-3">
        <Link to="/padelquartier" style={{ color: "#d4f53c" }}>← Padelquartier</Link>
      </p>

      <h1
        className="text-xl font-bold mb-1"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#fff", letterSpacing: "0.01em" }}
      >
        {entry.name}
      </h1>
      <p className="text-xs text-gray-500 mb-4">
        {entry.address ?? (entry.city === entry.bundesland ? entry.city : `${entry.city}, ${entry.bundesland}`)}
      </p>

      <div className="flex flex-wrap gap-2 mb-6">
        <span
          className="text-xs font-semibold rounded px-3 py-1.5"
          style={{ background: "rgba(212,245,60,0.1)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.25)" }}
        >
          {entry.courtInfo}
        </span>
        {entry.note && (
          <span className="text-xs rounded px-3 py-1.5 text-gray-400" style={{ border: "1px solid rgba(255,255,255,0.1)" }}>
            {entry.note}
          </span>
        )}
      </div>

      <div className="text-sm text-gray-300 space-y-3 mb-8" style={{ maxWidth: 680, lineHeight: 1.75 }}>
        {entry.detailParagraphs.map((para, i) => <p key={i}>{para}</p>)}
      </div>

      <div className="flex flex-wrap gap-2 mb-8">
        {entry.internalCourtSlug && (
          <Link
            to={`/court/${entry.internalCourtSlug}`}
            className="inline-block text-xs font-bold tracking-wide rounded px-4 py-2"
            style={{ background: "#d4f53c", color: "#080810" }}
          >
            → Verfügbarkeit auf PadelYara prüfen
          </Link>
        )}
        {entry.bookingUrl && (
          <a
            href={entry.bookingUrl}
            target="_blank"
            rel="noopener"
            className="inline-block text-xs font-bold tracking-wide rounded px-4 py-2"
            style={{ background: "rgba(212,245,60,0.1)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.25)" }}
          >
            ↗ Jetzt buchen
          </a>
        )}
        <a
          href={entry.websiteUrl}
          target="_blank"
          rel="noopener"
          className="inline-block text-xs font-bold tracking-wide rounded px-4 py-2 text-gray-300"
          style={{ border: "1px solid rgba(255,255,255,0.15)" }}
        >
          ↗ Website
        </a>
      </div>
    </>
  )
}
