import { useEffect } from "react"
import { Helmet } from "react-helmet-async"
import TournamentCard from "../components/TournamentCard"
import TurnierjagerNav from "../components/TurnierjagerNav"
import { useMerkliste } from "../hooks/useMerkliste"

export default function TurnierjagerMerklistePage() {
  const { merkliste, toggleMerkliste, clearMerkliste, shareMerkliste, copied, loadFromUrl } = useMerkliste()

  useEffect(() => { loadFromUrl() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const items = Object.values(merkliste).sort(
    (a, b) => (a.starts_at ?? "") < (b.starts_at ?? "") ? -1 : 1
  )
  const isEmpty = items.length === 0

  return (
    <section className="mt-2 pb-12">
      <Helmet>
        <title>Merkliste — Turnierjäger</title>
        <meta name="description" content="Deine gemerkten Padel-Turniere — teile sie mit deinem Partner." />
        <link rel="canonical" href="https://padelyara.at/turnierjaeger/merkliste" />
      </Helmet>

      <div className="mb-6 space-y-3 px-1">
        <p className="text-white text-lg font-semibold">Merkliste</p>
        <p className="text-gray-400 text-base leading-relaxed">
          Turniere merken, Link kopieren, Partner schicken. Fertig.
        </p>
      </div>

      <TurnierjagerNav />

      <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
        {isEmpty ? (
          <div className="flex items-start gap-3 py-4">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4b5563" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 mt-0.5">
              <path d="M19 21l-7-3-7 3V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
            </svg>
            <p className="text-sm leading-relaxed" style={{ color: "#6b7280" }}>
              Noch nichts gemerkt. Geh zu{" "}
              <span style={{ color: "#9ca3af" }}>Turniere</span>
              {" "}und tippe auf das{" "}
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline -mt-0.5">
                <path d="M19 21l-7-3-7 3V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
              </svg>
              {" "}Symbol bei einem Turnier.
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold" style={{ fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.04em", color: "rgba(212,245,60,0.5)" }}>
                {items.length} {items.length === 1 ? "TURNIER" : "TURNIERE"}
              </span>
              <button onClick={clearMerkliste} className="text-[10px] tracking-widest text-gray-700 hover:text-gray-500 transition-colors">
                LEEREN
              </button>
            </div>

            <div className="rounded-lg border border-gray-800 divide-y divide-gray-800 overflow-hidden mb-4">
              {items.map(t => (
                <TournamentCard
                  key={`${t.source}:${t.source_id}`}
                  t={t}
                  showLink
                  isBookmarked
                  onBookmark={() => toggleMerkliste(t)}
                />
              ))}
            </div>

            <button
              onClick={() => void shareMerkliste(items)}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-lg text-sm font-bold tracking-wider transition-opacity hover:opacity-90"
              style={{ fontFamily: "'Barlow Condensed', sans-serif", background: "#d4f53c", color: "#080810" }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
              </svg>
              {copied ? "LINK KOPIERT!" : `${items.length} ${items.length === 1 ? "TURNIER" : "TURNIERE"} TEILEN`}
            </button>
          </>
        )}
      </div>
    </section>
  )
}
