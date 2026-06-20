import { Helmet } from "react-helmet-async"
import TournamentCard from "../components/TournamentCard"
import TurnierjagerNav from "../components/TurnierjagerNav"
import { useMyProfile } from "../hooks/useMyProfile"
import { useMerkliste } from "../hooks/useMerkliste"

export default function TurnierjagerMinePage() {
  const {
    mySlug, myName, myInput, mySuggestions, myTournaments, myLoading, myError,
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

        {!myLoading && !myError && mySlug && myTournaments.length === 0 && (
          <p className="text-xs text-gray-600 mt-3">Keine offenen Anmeldungen gefunden.</p>
        )}

        {!myLoading && myTournaments.length > 0 && (
          <div className="mt-3 rounded-lg border border-gray-800 divide-y divide-gray-800 overflow-hidden">
            {myTournaments.map(t => (
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
        )}
      </div>
    </section>
  )
}
