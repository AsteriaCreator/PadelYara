import { useState, useEffect } from "react"
import { Helmet } from "react-helmet-async"
import { useParams } from "react-router-dom"
import TurnierjagerNav from "../components/TurnierjagerNav"
import { useMyProfile, type HistoryEntry } from "../hooks/useMyProfile"

const CATEGORY_RANK: Record<string, number> = {
  Newcomer: 1, Starter: 2, Advanced: 3, Expert: 4, Professional: 5, Elite: 6,
}
const CATEGORY_COLOR: Record<string, string> = {
  Newcomer: "#6b7280", Starter: "#60a5fa", Advanced: "#34d399",
  Expert: "#d4f53c", Professional: "#f59e0b", Elite: "#f87171",
}

function CategoryProgression({ history }: { history: HistoryEntry[] }) {
  const points = history
    .map(h => {
      const [day, month, year] = h.date.split(".")
      const ts = Date.parse(`${year}-${month}-${day}`)
      const rank = CATEGORY_RANK[h.category]
      return rank && !isNaN(ts) ? { ts, rank, category: h.category, title: h.title, date: h.date } : null
    })
    .filter((p): p is NonNullable<typeof p> => p !== null)
    .sort((a, b) => a.ts - b.ts)

  const distinctCategories = new Set(points.map(p => p.category)).size
  if (points.length < 2 || distinctCategories < 2) return null

  const W = 320, H = 100, PAD = { t: 12, b: 24, l: 8, r: 8 }
  const minTs = points[0].ts, maxTs = points[points.length - 1].ts
  const tsRange = maxTs - minTs || 1
  const rankMin = 1, rankMax = Math.max(...points.map(p => p.rank), 3)
  const rankRange = rankMax - rankMin || 1

  function px(ts: number) { return PAD.l + ((ts - minTs) / tsRange) * (W - PAD.l - PAD.r) }
  function py(rank: number) { return PAD.t + (1 - (rank - rankMin) / rankRange) * (H - PAD.t - PAD.b) }

  const polyline = points.map(p => `${px(p.ts).toFixed(1)},${py(p.rank).toFixed(1)}`).join(" ")

  const seenYears = new Set<string>()
  const yearMarks = points.filter(p => {
    const y = new Date(p.ts).getFullYear().toString()
    if (seenYears.has(y)) return false
    seenYears.add(y)
    return true
  })

  return (
    <div className="mb-4 rounded-lg border border-gray-800 p-3">
      <p className="text-[11px] tracking-widest mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#4b5563" }}>
        KATEGORIE-VERLAUF
      </p>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 100 }}>
        {Object.entries(CATEGORY_RANK).filter(([, r]) => r <= rankMax).map(([cat, rank]) => (
          <g key={cat}>
            <line x1={PAD.l} y1={py(rank)} x2={W - PAD.r} y2={py(rank)} stroke="rgba(107,114,128,0.12)" strokeWidth="1" />
            <text x={PAD.l} y={py(rank) - 3} fontSize="8" fill="rgba(107,114,128,0.5)" fontFamily="'Barlow Condensed', sans-serif">{cat}</text>
          </g>
        ))}
        {yearMarks.map(p => (
          <text key={p.ts} x={px(p.ts)} y={H - 4} fontSize="8" fill="rgba(107,114,128,0.4)" textAnchor="middle" fontFamily="'Barlow Condensed', sans-serif">
            {new Date(p.ts).getFullYear()}
          </text>
        ))}
        <polyline points={polyline} fill="none" stroke="rgba(212,245,60,0.3)" strokeWidth="1.5" strokeLinejoin="round" />
        {points.map((p, i) => (
          <circle key={i} cx={px(p.ts)} cy={py(p.rank)} r="3" fill={CATEGORY_COLOR[p.category] ?? "#d4f53c"} stroke="#080810" strokeWidth="1">
            <title>{p.title} · {p.date} · {p.category}</title>
          </circle>
        ))}
      </svg>
      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2">
        {Object.entries(CATEGORY_COLOR)
          .filter(([cat]) => points.some(p => p.category === cat))
          .map(([cat, color]) => (
            <div key={cat} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full inline-block" style={{ background: color }} />
              <span className="text-[10px]" style={{ color: "rgba(107,114,128,0.7)" }}>{cat}</span>
            </div>
          ))}
      </div>
    </div>
  )
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-xs px-2.5 py-1 rounded-full border transition-colors"
      style={{
        borderColor: active ? "#d4f53c" : "rgba(107,114,128,0.4)",
        color: active ? "#d4f53c" : "#6b7280",
        background: active ? "rgba(212,245,60,0.08)" : "transparent",
      }}
    >
      {label}
    </button>
  )
}

export default function SpielanalysePage() {
  const { slug: routeSlug } = useParams<{ slug?: string }>()

  const {
    mySlug, myName, myInput, mySuggestions, myLoading, myError,
    myHistory, matchResults, historyLoading, playerStats,
    searchMyName, selectPlayer, loadPlayerBySlug, clearMyProfile,
  } = useMyProfile({ skipInitialLoad: !!routeSlug })

  const [filterCategory, setFilterCategory] = useState("")
  const [filterCompetition, setFilterCompetition] = useState("")
  const [filterPartner, setFilterPartner] = useState("")
  const [filterYear, setFilterYear] = useState("")

  // Auto-load from route slug — history endpoint returns the name directly
  useEffect(() => {
    if (!routeSlug) return
    void loadPlayerBySlug(routeSlug)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeSlug])

  const mrByTitleDate = Object.values(matchResults).reduce<Record<string, typeof matchResults[string]>>(
    (acc, r) => {
      if (r.title && r.date) {
        const shortDate = r.date.replace(/^.+?\s/, "").split(",")[0].trim()
        acc[`${r.title}||${shortDate}`] = r
      }
      return acc
    }, {}
  )

  // Partner stats respect category/competition/year filters but not the partner filter
  const partnerStats = (() => {
    const map: Record<string, { wins: number; losses: number; tournaments: number; slug: string | null }> = {}
    const relevantHistory = myHistory.filter(h => {
      if (filterCategory && h.category !== filterCategory) return false
      if (filterCompetition && h.competition !== filterCompetition) return false
      if (filterYear && !h.date?.endsWith(filterYear)) return false
      if (filterPartner) {
        const mr = mrByTitleDate[`${h.title}||${h.date}`]
        if (!mr || mr.partner !== filterPartner) return false
      }
      return true
    })
    for (const h of relevantHistory) {
      const mr = mrByTitleDate[`${h.title}||${h.date}`]
      if (!mr?.partner) continue
      if (!map[mr.partner]) map[mr.partner] = { wins: 0, losses: 0, tournaments: 0, slug: mr.partner_slug ?? null }
      map[mr.partner].wins += mr.wins
      map[mr.partner].losses += mr.losses
      map[mr.partner].tournaments += 1
    }
    return Object.entries(map)
      .map(([name, s]) => ({ name, ...s, matches: s.wins + s.losses }))
      .filter(p => p.tournaments > 0)
      .sort((a, b) => b.tournaments - a.tournaments)
  })()

  const partnerTotals = partnerStats.reduce(
    (acc, p) => ({ tournaments: acc.tournaments + p.tournaments, matches: acc.matches + p.matches, wins: acc.wins + p.wins, losses: acc.losses + p.losses }),
    { tournaments: 0, matches: 0, wins: 0, losses: 0 }
  )

  const categories = [...new Set(myHistory.map(h => h.category).filter(Boolean))].sort()
  const competitions = [...new Set(myHistory.map(h => h.competition).filter(Boolean))].sort()
  const partners = [...new Set(Object.values(matchResults).map(r => r.partner).filter((p): p is string => !!p))].sort()
  const years = [...new Set(myHistory.map(h => h.date?.split(".").at(-1)).filter(Boolean))].sort((a, b) => Number(b) - Number(a)) as string[]

  const filteredHistory = myHistory.filter(h => {
    if (filterCategory && h.category !== filterCategory) return false
    if (filterCompetition && h.competition !== filterCompetition) return false
    if (filterYear && !h.date?.endsWith(filterYear)) return false
    if (filterPartner) {
      const mr = mrByTitleDate[`${h.title}||${h.date}`]
      if (!mr || mr.partner !== filterPartner) return false
    }
    return true
  })

  const hasFilter = !!(filterCategory || filterCompetition || filterPartner || filterYear)

  return (
    <section className="mt-2 pb-12">
      <Helmet>
        <title>{myName ? `${myName} — Spielanalyse` : "Spielanalyse — Turnierjäger"}</title>
        <meta name="description" content="Spielhistorie, Partner-Stats und Kategorie-Verlauf für jeden Padel-Spieler in Österreich." />
        {routeSlug && <link rel="canonical" href={`https://www.padelyara.at/turnierjaeger/spielanalyse/${routeSlug}`} />}
      </Helmet>

      <div className="mb-6 space-y-3 px-1">
        <p className="text-white text-lg font-semibold">Spielanalyse</p>
        <p className="text-gray-400 text-base leading-relaxed">
          Spielhistorie, Partner-Stats und Kategorie-Verlauf — für dich oder jeden anderen.
        </p>
      </div>

      <TurnierjagerNav />

      <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
        {/* Active player badge */}
        {mySlug && myName && (
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold" style={{ color: "#d4f53c" }}>{myName}</span>
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  const url = `https://www.padelyara.at/turnierjaeger/spielanalyse/${mySlug}`
                  const text = `🎾 Schau dir meine Padel-Stats an (${myName})!\n\n${url}`
                  if (navigator.share) void navigator.share({ text })
                  else void navigator.clipboard.writeText(url)
                }}
                className="text-[10px] tracking-widest font-bold transition-colors"
                style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "rgba(212,245,60,0.5)" }}
                onMouseEnter={e => (e.currentTarget.style.color = "#d4f53c")}
                onMouseLeave={e => (e.currentTarget.style.color = "rgba(212,245,60,0.5)")}
              >
                TEILEN →
              </button>
              <button onClick={clearMyProfile} className="text-[10px] text-gray-700 hover:text-gray-500">
                andere Person
              </button>
            </div>
          </div>
        )}

        {/* Player search */}
        {!myName && (
          <div className="relative mb-4">
            <input
              type="text"
              value={myInput}
              onChange={e => void searchMyName(e.target.value)}
              placeholder="Spieler suchen …"
              className="w-full text-xs rounded-lg px-3 py-2 outline-none"
              style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(107,114,128,0.4)", color: "#e5e7eb" }}
            />
            {mySuggestions.length > 0 && (
              <div className="absolute left-0 right-0 top-full mt-1 rounded-lg border overflow-hidden z-10"
                style={{ background: "#111118", borderColor: "rgba(107,114,128,0.4)" }}>
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
              <p className="text-[11px] text-gray-600 mt-2">Kein Spieler gefunden.</p>
            )}
          </div>
        )}

        {myLoading && <p className="text-xs text-gray-600">Suche …</p>}
        {myError && <p className="text-xs text-red-400">{myError}</p>}

        {/* APN + Points header */}
        {mySlug && !historyLoading && (playerStats.apn || playerStats.points) && (
          <div className="flex gap-2 mb-4">
            {[
              { label: "Punkte", value: playerStats.points },
              { label: "APN", value: playerStats.apn },
              { label: "Platz", value: playerStats.rank },
              playerStats.matchesPlayed != null ? { label: "Matches", value: `${playerStats.matchesWon}S · ${playerStats.matchesLost}N` } : null,
            ].filter(Boolean).map(s => s && (
              <div key={s.label} className="flex-1 rounded-lg p-2.5 text-center" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(107,114,128,0.15)" }}>
                <div className="text-[10px] uppercase tracking-wide mb-1" style={{ color: "#4b5563" }}>{s.label}</div>
                <div className="text-sm font-bold" style={{ color: s.label === "APN" ? "#d4f53c" : "#e5e7eb" }}>{s.value ?? "–"}</div>
              </div>
            ))}
          </div>
        )}

        {/* Stats */}
        {mySlug && (
          <div className="mt-2">
            {historyLoading ? (
              <p className="text-xs text-gray-600">Lade Analyse …</p>
            ) : myHistory.length > 0 ? (
              <>
                <CategoryProgression history={myHistory} />

                {partnerStats.length > 0 && (
                  <div className="mb-4 rounded-lg border border-gray-800 p-3">
                    <p className="text-[11px] tracking-widest mb-3" style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#4b5563" }}>
                      PARTNER-STATS
                    </p>
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-[10px] text-gray-700 flex-1">Partner</span>
                      <span className="text-[10px] w-8 text-center text-gray-700">Turniere</span>
                      <span className="text-[10px] w-8 text-center text-gray-700">Matches</span>
                      <span className="text-[10px] w-8 text-center" style={{ color: "rgba(212,245,60,0.35)" }}>Siege</span>
                      <span className="text-[10px] w-8 text-center" style={{ color: "rgba(107,114,128,0.5)" }}>Ndlg.</span>
                      <span className="text-[10px] w-8 text-center text-gray-700">Quote</span>
                    </div>
                    <div className="space-y-2">
                      {partnerStats.slice(0, 5).map(p => (
                        <div key={p.name} className="flex items-center gap-2">
                          {p.slug ? (
                            <a href={`/turnierjaeger/spielanalyse/${p.slug}`} className="text-xs flex-1 truncate hover:underline" style={{ color: "rgba(212,245,60,0.7)" }}>{p.name}</a>
                          ) : (
                            <span className="text-xs text-gray-400 flex-1 truncate">{p.name}</span>
                          )}
                          <span className="text-xs text-gray-600 w-8 text-center">{p.tournaments}</span>
                          <span className="text-xs text-gray-600 w-8 text-center">{p.matches}</span>
                          <span className="text-xs font-bold w-8 text-center" style={{ color: "#d4f53c" }}>{p.wins}</span>
                          <span className="text-xs w-8 text-center" style={{ color: "#6b7280" }}>{p.losses}</span>
                          <span className="text-xs text-gray-700 w-8 text-center">
                            {p.matches > 0 ? `${Math.round(100 * p.wins / p.matches)}%` : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-800">
                      <span className="text-[10px] text-gray-600 flex-1">Gesamt</span>
                      <span className="text-[10px] font-bold text-gray-500 w-8 text-center">{partnerTotals.tournaments}</span>
                      <span className="text-[10px] font-bold text-gray-500 w-8 text-center">{partnerTotals.matches}</span>
                      <span className="text-[10px] font-bold w-8 text-center" style={{ color: "rgba(212,245,60,0.7)" }}>{partnerTotals.wins}</span>
                      <span className="text-[10px] font-bold w-8 text-center" style={{ color: "#6b7280" }}>{partnerTotals.losses}</span>
                      <span className="text-[10px] font-bold text-gray-500 w-8 text-center">
                        {partnerTotals.matches > 0 ? `${Math.round(100 * partnerTotals.wins / partnerTotals.matches)}%` : ""}
                      </span>
                    </div>
                  </div>
                )}

                {/* Filters */}
                {(categories.length > 1 || competitions.length > 1 || partners.length > 1 || years.length > 1) && (
                  <div className="mb-3 space-y-2">
                    {categories.length > 1 && (
                      <div className="flex flex-wrap gap-1.5">
                        {categories.map(c => <FilterChip key={c} label={c} active={filterCategory === c} onClick={() => setFilterCategory(filterCategory === c ? "" : c)} />)}
                      </div>
                    )}
                    {competitions.length > 1 && (
                      <div className="flex flex-wrap gap-1.5">
                        {competitions.map(c => <FilterChip key={c} label={c} active={filterCompetition === c} onClick={() => setFilterCompetition(filterCompetition === c ? "" : c)} />)}
                      </div>
                    )}
                    {partners.length > 1 && (
                      <div className="flex flex-wrap gap-1.5">
                        {partners.map(p => <FilterChip key={p} label={p} active={filterPartner === p} onClick={() => setFilterPartner(filterPartner === p ? "" : p)} />)}
                      </div>
                    )}
                    {years.length > 1 && (
                      <div className="flex flex-wrap gap-1.5">
                        {years.map(y => <FilterChip key={y} label={y} active={filterYear === y} onClick={() => setFilterYear(filterYear === y ? "" : y)} />)}
                      </div>
                    )}
                  </div>
                )}

                <div className="flex items-center justify-between mb-1">
                  <p className="text-[11px] tracking-widest" style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#4b5563" }}>
                    HISTORIE · {filteredHistory.length}{hasFilter ? ` / ${myHistory.length}` : ""}
                  </p>
                  {hasFilter && (
                    <button onClick={() => { setFilterCategory(""); setFilterCompetition(""); setFilterPartner(""); setFilterYear("") }}
                      className="text-[10px] text-gray-700 hover:text-gray-500 transition-colors">
                      Filter löschen
                    </button>
                  )}
                </div>
                <p className="text-[10px] text-gray-700 mb-2">
                  <span style={{ color: "#d4f53c" }}>S</span> = Siege &nbsp;·&nbsp; <span style={{ color: "#6b7280" }}>N</span> = Niederlagen
                </p>

                <div className="rounded-lg border border-gray-800 divide-y divide-gray-800 overflow-hidden mb-6">
                  {filteredHistory.map((h, i) => {
                    const mr = mrByTitleDate[`${h.title}||${h.date}`]
                    return (
                      <div key={i} className="px-4 py-3" style={{ opacity: 0.8 }}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            {h.url ? (
                              <a href={h.url} target="_blank" rel="noopener noreferrer"
                                className="text-sm font-semibold text-white leading-snug hover:underline">{h.title}</a>
                            ) : (
                              <span className="text-sm font-semibold text-white leading-snug">{h.title}</span>
                            )}
                            <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                              <span className="text-xs text-gray-500">{h.date}</span>
                              {mr?.partner && <span className="text-xs text-gray-600">mit {mr.partner}</span>}
                            </div>
                          </div>
                          <div className="shrink-0 text-right space-y-1">
                            <div className="flex items-center gap-1.5 justify-end">
                              <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(212,245,60,0.08)", color: "rgba(212,245,60,0.5)", fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.04em" }}>
                                {h.category.toUpperCase()}
                              </span>
                            </div>
                            {mr && (mr.wins + mr.losses) > 0 && (
                              <div className="flex items-center gap-1 justify-end">
                                <span className="text-[11px] font-bold" style={{ color: "#d4f53c" }}>{mr.wins}S</span>
                                <span className="text-[11px] text-gray-700">·</span>
                                <span className="text-[11px]" style={{ color: "#6b7280" }}>{mr.losses}N</span>
                              </div>
                            )}
                            <p className="text-[11px] text-gray-700">{h.points} Pkt</p>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
            ) : !historyLoading && (
              <p className="text-xs text-gray-600 mt-2">Keine Daten gefunden.</p>
            )}

            {/* Urteil — coming soon, unobtrusive */}
            {myHistory.length > 0 && (
              <div className="mt-2 pt-4 border-t border-gray-800">
                <p className="text-[11px] tracking-widest mb-2" style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#374151" }}>
                  YARAS URTEIL
                </p>
                <p className="text-xs" style={{ color: "#374151" }}>Kommt bald.</p>
              </div>
            )}
          </div>
        )}

        {!mySlug && !myLoading && (
          <div className="py-6 text-center">
            <img src="/cat-head.svg" alt="Yara" className="h-10 w-auto mx-auto mb-3 opacity-20" />
            <p className="text-xs text-gray-700">Name eingeben und Analyse starten.</p>
          </div>
        )}

        <p className="mt-6 text-[10px] text-gray-800 text-center">
          Daten von{" "}
          <a href="https://padel-austria.at" target="_blank" rel="noopener noreferrer" className="hover:text-gray-600">
            padel-austria.at
          </a>
          {" "}· öffentliche Turnierergebnisse · keine dauerhafte Speicherung ·{" "}
          <a href="/datenschutz" className="hover:text-gray-600">Datenschutz</a>
        </p>
      </div>
    </section>
  )
}
