import { useState, useEffect, useRef } from "react"
import { Helmet } from "react-helmet-async"
import TournamentCard from "../components/TournamentCard"
import TurnierjagerNav from "../components/TurnierjagerNav"
import { useMyProfile } from "../hooks/useMyProfile"
import { useMerkliste } from "../hooks/useMerkliste"
import { useTournamentStatus, STATUS_LABELS, AUTO_STATUSES } from "../hooks/useTournamentStatus"
import type { TournamentStatusValue } from "../hooks/useTournamentStatus"
import type { Tournament } from "../types"

const STATUS_COLORS: Record<TournamentStatusValue, string> = {
  interessant: "#6b7280",
  gefragt: "#60a5fa",
  zusage: "#a78bfa",
  ich_buche: "#fb923c",
  sie_bucht: "#fb923c",
  warteliste: "#fbbf24",
  gebucht: "#d4f53c",
}

function statusLabel(s: TournamentStatusValue): string {
  if (s === "warteliste") return `⚡ ${STATUS_LABELS[s]}`
  if (s === "gebucht") return `✓ ${STATUS_LABELS[s]}`
  return STATUS_LABELS[s]
}

function StatusChip({ t, getStatus, setStatus }: {
  t: Tournament
  getStatus: (t: Tournament) => TournamentStatusValue
  setStatus: (t: Tournament, s: TournamentStatusValue) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const current = getStatus(t)

  useEffect(() => {
    if (!open) return
    function onOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", onOutside)
    return () => document.removeEventListener("mousedown", onOutside)
  }, [open])

  const isAuto = AUTO_STATUSES.includes(current)

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen(o => !o)}
        className="text-[10px] font-bold px-2 py-0.5 rounded-full tracking-wider transition-opacity hover:opacity-80"
        style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          background: `${STATUS_COLORS[current]}22`,
          color: STATUS_COLORS[current],
          border: `1px solid ${STATUS_COLORS[current]}55`,
          opacity: isAuto ? 1 : 0.9,
        }}
      >
        {statusLabel(current)}
        <span style={{ fontSize: "8px", marginLeft: "3px", opacity: 0.6 }}>▾</span>
      </button>
      {open && (
        <div
          className="absolute left-0 top-full mt-1 rounded-lg border overflow-hidden z-20"
          style={{ background: "#111118", borderColor: "rgba(107,114,128,0.4)", minWidth: "130px" }}
        >
          {(Object.keys(STATUS_LABELS) as TournamentStatusValue[]).map(s => (
            <button
              key={s}
              onClick={() => { setStatus(t, s); setOpen(false) }}
              className="w-full text-left text-[11px] px-3 py-1.5 transition-colors"
              style={{
                color: s === current ? STATUS_COLORS[s] : "#9ca3af",
                background: s === current ? `${STATUS_COLORS[s]}11` : "transparent",
                fontWeight: s === current ? 700 : 400,
              }}
              onMouseEnter={e => { if (s !== current) (e.currentTarget as HTMLElement).style.background = "rgba(212,245,60,0.06)" }}
              onMouseLeave={e => { if (s !== current) (e.currentTarget as HTMLElement).style.background = "transparent" }}
            >
              {statusLabel(s)}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function TurnierjagerMinePage() {
  const {
    mySlug, myName, myInput, mySuggestions, myTournaments, myLoading, myError,
    searchMyName, selectPlayer, clearMyProfile,
  } = useMyProfile()
  const { merkliste, toggleMerkliste, clearMerkliste, shareMerkliste, copied, loadFromUrl } = useMerkliste()
  const { getStatus, setStatus, autoSetStatus } = useTournamentStatus()

  const [tab, setTab] = useState<"bevorstehend" | "gemerkt">("bevorstehend")

  useEffect(() => { loadFromUrl() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-detect waitlist / booked status from padel-austria.at data
  useEffect(() => {
    for (const t of myTournaments) {
      if (t.is_waitlisted) {
        autoSetStatus(t, "warteliste")
      } else {
        autoSetStatus(t, "gebucht")
      }
    }
  }, [myTournaments]) // eslint-disable-line react-hooks/exhaustive-deps

  const merklisteItems = Object.values(merkliste).sort(
    (a, b) => (a.starts_at ?? "") < (b.starts_at ?? "") ? -1 : 1
  )

  const now = new Date()
  const upcoming = myTournaments.filter(t => !t.starts_at || new Date(t.starts_at) >= now)

  return (
    <section className="mt-2 pb-12">
      <Helmet>
        <title>Meine Jagd — Turnierjäger</title>
        <meta name="description" content="Deine angemeldeten und gemerkten Padel-Turniere auf einen Blick." />
        <link rel="canonical" href="https://www.padelyara.at/turnierjaeger/meine" />
      </Helmet>

      <div className="mb-6 space-y-3 px-1">
        <p className="text-white text-lg font-semibold">Meine Jagd</p>
        <p className="text-gray-400 text-base leading-relaxed">
          Deine angemeldeten Turniere und deine Merkliste.
        </p>
      </div>

      <TurnierjagerNav />

      <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
        {/* Profile setup / badge */}
        {myName ? (
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold" style={{ color: "#d4f53c" }}>{myName}</span>
            <div className="flex items-center gap-3">
              <a
                href={`/turnierjaeger/spielanalyse/${mySlug}`}
                className="text-[10px] tracking-widest font-bold transition-colors"
                style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "rgba(212,245,60,0.5)", textDecoration: "none" }}
                onMouseEnter={e => (e.currentTarget.style.color = "#d4f53c")}
                onMouseLeave={e => (e.currentTarget.style.color = "rgba(212,245,60,0.5)")}
              >
                SPIELANALYSE →
              </a>
              <button onClick={clearMyProfile} className="text-[10px] text-gray-700 hover:text-gray-500">
                ändern
              </button>
            </div>
          </div>
        ) : (
          <div className="relative mb-4">
            <input
              type="text"
              value={myInput}
              onChange={e => void searchMyName(e.target.value)}
              placeholder="Deinen Namen eingeben …"
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
              <p className="text-[11px] text-gray-600 mt-2">
                Kein Spieler gefunden. Bist du in einem offenen Turnier angemeldet?
              </p>
            )}
          </div>
        )}

        {myLoading && <p className="text-xs text-gray-600 mb-3">Suche …</p>}
        {myError && <p className="text-xs text-red-400 mb-3">{myError}</p>}

        {/* Tabs */}
        <div className="flex gap-1 mb-4 p-1 rounded-lg" style={{ background: "rgba(255,255,255,0.03)" }}>
          {(["bevorstehend", "gemerkt"] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="flex-1 py-1.5 rounded-md text-[11px] font-bold tracking-wider transition-colors relative"
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                background: tab === t ? "rgba(212,245,60,0.1)" : "transparent",
                color: tab === t ? "#d4f53c" : "#6b7280",
              }}
            >
              {t === "bevorstehend" ? "BEVORSTEHEND" : "GEMERKT"}
              {t === "gemerkt" && merklisteItems.length > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full text-[10px] font-bold flex items-center justify-center"
                  style={{ background: "#d4f53c", color: "#080810" }}>
                  {merklisteItems.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* BEVORSTEHEND */}
        {tab === "bevorstehend" && (
          <>
            {!myName && !myLoading && (
              <p className="text-xs text-gray-600 py-4 text-center">
                Namen eingeben um deine Turniere zu sehen.
              </p>
            )}
            {myName && !myLoading && upcoming.length === 0 && (
              <p className="text-xs text-gray-600">Keine bevorstehenden Turniere gefunden.</p>
            )}
            {upcoming.length > 0 && (
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
                          <a href={`https://padel-austria.at/players/${t.partner_slug}`}
                            target="_blank" rel="noopener noreferrer"
                            className="hover:underline" style={{ color: "rgba(212,245,60,0.6)" }}>
                            {t.partner_name}
                          </a>
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* GEMERKT */}
        {tab === "gemerkt" && (
          <>
            {merklisteItems.length === 0 ? (
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
                    {merklisteItems.length} {merklisteItems.length === 1 ? "TURNIER" : "TURNIERE"}
                  </span>
                  <button onClick={clearMerkliste} className="text-[10px] tracking-widest text-gray-700 hover:text-gray-500 transition-colors">
                    LEEREN
                  </button>
                </div>
                <div className="rounded-lg border border-gray-800 divide-y divide-gray-800 overflow-hidden mb-4">
                  {merklisteItems.map(t => (
                    <div key={`${t.source}:${t.source_id}`}>
                      <TournamentCard
                        t={t}
                        showLink
                        isBookmarked
                        onBookmark={() => toggleMerkliste(t)}
                      />
                      <div className="px-4 pb-3 -mt-1">
                        <StatusChip t={t} getStatus={getStatus} setStatus={setStatus} />
                      </div>
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => void shareMerkliste(merklisteItems)}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-lg text-sm font-bold tracking-wider transition-opacity hover:opacity-90"
                  style={{ fontFamily: "'Barlow Condensed', sans-serif", background: "#d4f53c", color: "#080810" }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
                    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
                  </svg>
                  {copied ? "LINK KOPIERT" : `${merklisteItems.length} ${merklisteItems.length === 1 ? "TURNIER" : "TURNIERE"} TEILEN`}
                </button>
              </>
            )}
          </>
        )}
      </div>
    </section>
  )
}
