import { Helmet } from "react-helmet-async"
import { Link } from "react-router-dom"
import { PADELQUARTIER_ENTRIES, type QuartierEntry } from "../data/padelquartier"

function QuartierCard({ entry }: { entry: QuartierEntry }) {
  const content = (
    <>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-white group-hover:text-[#d4f53c] transition-colors truncate">
          {entry.name}
        </p>
        <p className="text-xs text-gray-500 mt-0.5">{entry.city} · {entry.bundesland}</p>
        <p className="text-xs mt-1.5" style={{ color: "rgba(212,245,60,0.6)" }}>{entry.courtInfo}</p>
        {entry.note && <p className="text-xs text-gray-500 mt-0.5">{entry.note}</p>}
        <p className="text-xs text-gray-400 mt-2" style={{ lineHeight: 1.6 }}>{entry.description}</p>
      </div>
      <span className="text-xs text-gray-600 mt-0.5 shrink-0">{entry.isInternal ? "→" : "↗"}</span>
    </>
  )

  const className = "flex items-start justify-between gap-3 rounded-lg px-4 py-3 group"
  const style = { background: "rgba(255,255,255,0.03)", border: "1px solid rgba(212,245,60,0.12)" }

  return entry.isInternal ? (
    <Link to={entry.link} className={className} style={style}>{content}</Link>
  ) : (
    <a href={entry.link} target="_blank" rel="noopener" className={className} style={style}>{content}</a>
  )
}

export default function PadelquartierPage() {
  const hotels = PADELQUARTIER_ENTRIES.filter(e => e.type === "hotel")
  const reiseveranstalter = PADELQUARTIER_ENTRIES.filter(e => e.type === "reiseveranstalter")

  return (
    <>
      <Helmet>
        <title>Padelquartier — Hotels & Reisen mit Padelplatz | PadelYara</title>
        <meta name="description" content="Hotels in Österreich mit eigenem Padelplatz, und Veranstalter für Padel-Reisen. Kuratiert von Yara." />
        <meta name="robots" content="noindex, follow" />
      </Helmet>

      <h1
        className="text-xl font-bold mb-2"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#fff", letterSpacing: "0.01em" }}
      >
        Padelquartier
      </h1>
      <p
        className="text-base italic mb-6"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c" }}
      >
        Ein paar Hotels in Österreich haben einen eigenen Court. Nicht viele. Die, die es gibt, stehen hier — mit den Fakten, nicht mit Marketing-Français.
      </p>

      <p
        className="mb-3 px-1"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "0.85rem", color: "rgba(212,245,60,0.4)" }}
      >
        Hotels mit eigenem Court
      </p>
      <div className="space-y-2 mb-6">
        {hotels.map(e => <QuartierCard key={e.id} entry={e} />)}
      </div>

      <p
        className="mb-3 px-1"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "0.85rem", color: "rgba(212,245,60,0.4)" }}
      >
        Reiseveranstalter
      </p>
      <div className="space-y-2 mb-6">
        {reiseveranstalter.map(e => <QuartierCard key={e.id} entry={e} />)}
      </div>
    </>
  )
}
