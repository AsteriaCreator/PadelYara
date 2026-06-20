import { Helmet } from "react-helmet-async"
import TournamentCard from "../components/TournamentCard"
import TurnierjagerNav from "../components/TurnierjagerNav"
import { useMyProfile } from "../hooks/useMyProfile"
import { useMerkliste } from "../hooks/useMerkliste"

export default function TurnierjagerMinePage() {
  const {
    mySlug, myName, myInput, mySuggestions, myTournaments, myLoading, myError,
    myHistory, historyLoading,
    searchMyName, selectPlayer, clearMyProfile,
  } = useMyProfile()
  const { merkliste, toggleMerkliste } = useMerkliste()

  return (
    <section className="mt-2 pb-12">
      <Helmet>
        <title>Meine Turniere — Turnierjäger</title>
        <meta name="description" content="Deine angemeldeten Padel-Turniere auf einen Blick." />
        <link rel="canonical" href="https://padelyara.at/turnierjaeger/meine" />
      </Helmet>

      <div className="mb-6 space-y-3 px-1">
        <p className="text-white text-lg font-semibold">Meine Turniere</p>
        <p className="text-gray-400 text-base leading-relaxed">
          Gib deinen Namen ein — Yara zeigt dir, wo du angemeldet bist.
        </p>
      </div>

      <TurnierjagerNav />

      <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
        {/* Active player badge */}
        {mySlug && myName && (
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold" style={{ color: "#d4f53c" }}>{myName}</span>
            <button onClick={clearMyProfile} className="text-[10px] text-gray-700 hover:text-gray-500">
              ändern
            </button>
          </div>
        )}

        {/* Name search */}
        {!myName && (
          <div className="relative mb-1">
            <input
              type="text"
              value={myInput}
              onChange={e => void searchMyName(e.target.value)}
              placeholder="Name eingeben …"
              className="w-full text-xs rounded-lg px-3 py-2 outline-none"
              style={{
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(107,114,128,0.4)",
                color: "#e5e7eb",
              }}
            />
            {mySuggestions.length > 0 && (
              <div
                className="absolute left-0 right-0 top-full mt-1 rounded-lg border overflow-hidden z-10"
                style={{ background: "#111118", borderColor: "rgba(107,114,128,0.4)" }}
              >
                {mySuggestions.map(p => (
                  <button
                    key={p.slug}
                    onClick={() => selectPlayer(p.name, p.slug)}
                    className="w-full text-left text-xs px-3 py-2 transition-colors"
                    style={{ color: "#e5e7eb" }}
                    onMouseEnter={e => (e.currentTarget.style.background = "rgba(212,245,60,0.08)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "")}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            )}
            {myInput.length >= 2 && mySuggestions.length === 0 && (
              <p className="text-[11px] text-gray-600 mt-2">
                Kein Spieler gefunden. Bist du in einem offenen Turnier angemeldet?
              </p>
            )}
          </div>
        )}

        {myLoading && <p className="text-xs text-gray-600 mt-3">Suche …</p>}
        {myError && <p className="text-xs text-red-400 mt-3">{myError}</p>}

        {!myLoading && !myError && mySlug && myTournaments.length === 0 && !historyLoading && myHistory.length === 0 && (
          <p className="text-xs text-gray-600 mt-3">Keine Turniere gefunden.</p>
        )}

        {!myLoading && myTournaments.length > 0 && (() => {
          const now = new Date()
          const upcoming = myTournaments.filter(t => !t.starts_at || new Date(t.starts_at) >= now)
          if (upcoming.length === 0) return null
          return (
            <div className="mt-3 space-y-4">
              <div>
                <p className="text-[11px] tracking-widest mb-2" style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c" }}>
                  BEVORSTEHEND · {upcoming.length}
                </p>
                <div className="rounded-lg border border-gray-800 divide-y divide-gray-800 overflow-hidden">
                  {upcoming.map(t => (
                    <div key={t.source_id}>
                      <TournamentCard
                        t={t}
                        showLink
                        showShare
                        isBookmarked={!!merkliste[`${t.source}:${t.source_id}`]}
                        onBookmark={() => toggleMerkliste(t)}
                      />
                      {t.partner_name && (
                        <div className="px-4 pb-2 -mt-1">
                          <span className="text-[11px] text-gray-500">
                            Partner:{" "}
                            <a
                              href={`https://padel-austria.at/players/${t.partner_slug}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="hover:underline"
                              style={{ color: "rgba(212,245,60,0.6)" }}
                            >
                              {t.partner_name}
                            </a>
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )
        })()}

        {/* History from padel-austria.at points table */}
        {mySlug && (
          <div className="mt-4">
            {historyLoading ? (
              <p className="text-xs text-gray-600">Lade Historie …</p>
            ) : myHistory.length > 0 && (
              <div>
                <p className="text-[11px] tracking-widest mb-2" style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#4b5563" }}>
                  HISTORIE · {myHistory.length}
                </p>
                <div className="rounded-lg border border-gray-800 divide-y divide-gray-800 overflow-hidden">
                  {myHistory.map((h, i) => (
                    <div key={i} className="px-4 py-3" style={{ opacity: 0.7 }}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          {h.url ? (
                            <a href={h.url} target="_blank" rel="noopener noreferrer"
                              className="text-sm font-semibold text-white leading-snug hover:underline"
                              style={{ userSelect: "text" }}
                            >{h.title}</a>
                          ) : (
                            <span className="text-sm font-semibold text-white leading-snug" style={{ userSelect: "text" }}>{h.title}</span>
                          )}
                          <p className="text-xs text-gray-500 mt-0.5">{h.date}</p>
                        </div>
                        <div className="shrink-0 text-right">
                          <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(212,245,60,0.08)", color: "rgba(212,245,60,0.5)", fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.04em" }}>
                            {h.category.toUpperCase()}
                          </span>
                          <p className="text-[11px] text-gray-700 mt-1">{h.points} Pkt</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
