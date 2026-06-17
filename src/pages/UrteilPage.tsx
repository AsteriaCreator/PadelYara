// Maintenance placeholder — real implementation is preserved below but not exported.
// To restore: swap the export default below back to UrteilPageFull.

import { useState, useCallback } from "react"
const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"

// PadelYara cat-head logo, lime, inlined so we can tint it (the /cat-head.svg
// asset is white). Same path as public/cat-head.svg.
function CatHead({ size = 26 }: { size?: number }) {
  return (
    <svg viewBox="15 63 225 215" width={size} height={size} aria-hidden="true" style={{ flex: "none" }}>
      <path fill="#d4f53c" fillRule="evenodd" d="m 58.195428,218.00943 c -5.006494,-5.20767 5.09565,4.82298 9.428637,8.34775 4.332987,3.52477 10.513013,8.57282 12.894679,9.45829 10.451283,3.88564 14.662596,6.22754 17.046116,9.47926 l 1.8494,2.52305 0.8943,-3.56079 c 0.49186,-1.95843 1.97917,-6.16497 3.3051,-9.34788 4.48553,-10.76735 3.02459,-13.82025 -8.2158,-17.16836 -11.530484,-3.43453 -16.832538,-8.4263 -20.324248,-19.13482 -2.108261,-6.46572 -1.972755,-6.34585 -11.061767,-9.78441 -2.339205,-0.88497 -4.740282,-1.6029 -5.335731,-1.59541 -1.419646,0.0179 -4.296091,11.28108 -4.220632,16.52662 0.03135,2.17939 1.108844,6.29628 1.626846,9.32599 0.504357,2.9499 0.708327,3.55016 1.960872,4.67049 m 133.71454,6.38793 6.92499,-9.47074 0.22535,-4.95714 c 0.14112,-3.10421 0.89198,-11.71158 0.0961,-18.36501 -0.37497,-3.1347 -1.88356,-5.58781 -2.03091,-5.74079 -0.39175,-0.40673 -8.26807,2.37133 -11.56224,4.07812 -2.44531,1.26698 -3.00583,2.13051 -4.10929,6.33074 -2.79033,10.6212 -9.10601,17.39689 -18.99685,20.38051 -8.23564,2.48433 -10.74757,3.81203 -11.59002,6.12604 -1.20409,3.30737 -0.89674,4.86459 2.60851,13.2167 1.8226,4.34283 3.32494,8.66847 3.33853,9.61255 0.0214,1.48677 0.41992,1.27952 2.97795,-1.5486 3.31558,-3.66566 6.28258,-5.37885 16.06783,-9.2778 3.71897,-1.48184 8.90063,-4.17639 11.51477,-5.9879 l 4.49911,-4.30923 M 165.34173,207.76958 c 3.37955,-2.36713 5.17585,-7.92976 3.4439,-10.66481 -0.57886,-0.91414 -1.1851,-0.78373 -3.38775,0.72871 -3.54307,2.43284 -7.04484,5.66113 -7.94997,7.32911 -1.71936,3.16842 4.2688,5.14605 7.89382,2.60699 z M 98.649739,208.53255 c 3.225691,-1.23781 -0.40471,-6.9431 -7.03521,-11.05606 -2.92286,-1.81308 -3.93042,-0.63865 -3.38159,3.94165 0.63179,5.27267 5.87839,8.85596 10.4168,7.11441 z M 122.29898,261.33128 c 4.32216,-1.72938 4.19506,-3.66436 -0.55763,-8.48961 l -3.77383,-3.83144 1.68069,-1.68069 c 2.17467,-2.17466 10.43382,-2.93171 15.06696,-1.38107 4.63775,1.55218 4.65073,3.71174 0.0454,7.56128 -2.00499,1.67597 -3.64544,3.68268 -3.64544,4.45936 0,2.03773 3.20403,3.83634 7.69881,4.3218 5.32498,0.57512 8.92371,-1.34992 11.35265,-6.07277 2.41224,-4.69038 1.9912,-7.95256 -2.34272,-18.15143 -3.08611,-7.26241 -3.34167,-8.41616 -3.42197,-15.44857 -0.12412,-10.87116 2.04255,-15.61395 11.56443,-25.31428 10.70151,-10.90205 27.48825,-19.39468 49.9488,-25.26976 1.76,-0.46036 3.51475,-1.12004 3.89945,-1.46595 1.09355,-0.98327 -9.53053,-16.53454 -14.98769,-21.93861 -2.88422,-2.85617 -7.27123,-6.09127 -10.62764,-7.83711 -5.67134,-2.94995 -5.7111,-2.9934 -5.10176,-5.57371 3.54254,-15.00124 8.3478,-26.41101 15.85676,-37.650771 2.4803,-3.71263 3.82923,-5.11402 4.23119,-4.39576 2.24091,4.00429 3.05294,29.428191 1.40328,43.935581 -0.86804,7.63372 -0.83215,8.2159 0.56966,9.24092 1.39248,1.01821 1.59364,0.74694 2.90567,-3.9183 3.38313,-12.02961 4.65543,-30.50606 3.01837,-43.833241 -0.79114,-6.44066 -3.42892,-17.479432 -4.7568,-19.906587 -0.79453,-1.452364 -13.12187,10.760927 -21.72855,21.527578 -7.36562,9.21413 -21.45268,28.80464 -26.32543,36.61011 -3.02635,4.8478 -4.1527,5.95706 -7.55647,7.44187 -2.2,0.95969 -6.92007,3.1406 -10.48904,4.84646 -3.56897,1.70586 -6.84517,3.10156 -7.28045,3.10156 -0.43528,0 -5.85092,-2.25126 -12.03476,-5.0028 l -11.24334,-5.00281 -7.000341,-9.99719 C 83.351159,110.34244 69.237179,92.684589 59.567619,83.298224 l -5.62044,-5.455836 -1.01637,1.939808 c -3.2964,6.291403 -5.41215,27.391134 -4.2154,42.038874 0.77121,9.43928 2.53976,19.75697 4.0817,23.8126 0.77581,2.04052 0.80906,2.04823 2.27551,0.52762 1.4085,-1.46051 1.42527,-1.90732 0.3132,-8.34315 -1.50445,-8.70657 -1.69181,-29.55962 -0.34682,-38.600001 0.57279,-3.85 1.27425,-6.99535 1.5588,-6.98967 0.85423,0.0171 7.76191,11.134741 11.2452,18.098771 3.39753,6.79257 8.59565,21.42164 9.02383,25.39579 0.22673,2.10435 -0.22032,2.55824 -5.13802,5.21664 -8.54085,4.61699 -16.41326,13.2282 -22.93884,25.09155 -1.81298,3.29596 -2.24301,4.701 -1.50614,4.921 0.56724,0.16935 5.06019,1.4479 9.98435,2.84121 25.67181,7.26394 44.796741,20.10849 52.855341,35.49832 1.95786,3.739 2.15748,4.915 2.12623,12.52639 -0.0331,8.06128 -0.17045,8.71649 -3.40649,16.24857 -4.41102,10.26691 -4.82538,13.47129 -2.34716,18.15143 3.14614,5.94153 8.99934,7.83538 15.80288,5.11314 z M 137.43029,269.76972 c 1.7709,-0.9953 3.06254,-2.06412 2.8703,-2.37516 -0.19223,-0.31104 -2.06759,-0.80611 -4.16747,-1.10017 -2.09987,-0.29405 -4.67606,-1.00991 -5.72485,-1.5908 -1.60647,-0.88977 -2.29118,-0.86445 -4.34609,0.16067 -1.34155,0.66925 -4.17345,1.38347 -6.2931,1.58714 -2.11965,0.20367 -3.85391,0.60689 -3.85391,0.89604 0,0.69681 4.39954,3.27067 7.07411,4.13856 3.5219,1.14284 10.91785,0.26385 14.44101,-1.71628 z" />
    </svg>
  )
}

interface Partner { name: string; matches: number; wins: number; losses: number; win_rate: number }
interface UrteilData {
  slug: string
  facts: {
    player: { name: string; rank: number | null; points: number | null; apn: string | null; effectiveness: string | null }
    totals: { played: number | null; won: number | null; lost: number | null }
    window: { matches_analysed: number; note: string }
    partners: Partner[]
  }
  upcoming: { title: string; competition?: string; status?: string; starts_at?: string; source_url?: string }[]
  beobachtungen: string[]
  urteil: string | null
  disclaimer: string
  ai_available: boolean
}

const card = "rgba(255,255,255,0.04)"
const lime = "#d4f53c"

export default function UrteilPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4"
      style={{ background: "#080810", fontFamily: "'Barlow Condensed', sans-serif" }}>
      <CatHead size={64} />
      <p className="mt-6 text-lg font-bold tracking-widest uppercase" style={{ color: lime }}>
        Kommt bald.
      </p>
      <p className="mt-2 text-sm text-gray-500">Yaras Urteil wird gerade geschärft.</p>
    </div>
  )
}

export function UrteilPageFull() {
  const [profile, setProfile] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<UrteilData | null>(null)
  const [copied, setCopied] = useState(false)

  const request = useCallback(async () => {
    const value = profile.trim()
    if (!value || loading) return
    setLoading(true)
    setError(null)
    setData(null)
    try {
      const res = await fetch(`${API_BASE}/api/urteil?profile=${encodeURIComponent(value)}`)
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        setError(body?.detail ?? "Yara konnte das Profil nicht laden.")
        return
      }
      setData(await res.json())
    } catch {
      setError("Verbindung fehlgeschlagen.")
    } finally {
      setLoading(false)
    }
  }, [profile, loading])

  function handleShare() {
    if (!data?.urteil) return
    const text = `Yaras Urteil über ${data.facts.player.name}:\n\n${data.urteil}`
    const url = `${window.location.origin}/urteil`
    if (navigator.share) {
      navigator.share({ text, url }).catch(() => {})
    } else {
      navigator.clipboard.writeText(`${text}\n\n${url}`).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    }
  }

  const f = data?.facts

  return (
    <div>
      <p className="text-base italic mb-4 mt-2" style={{ fontFamily: "'Barlow Condensed', sans-serif", color: lime }}>
        Füg den Link zu deinem Turnierprofil ein. Yara bildet sich eine Meinung.
      </p>

      <div className="flex gap-2 mb-2">
        <input
          type="text"
          value={profile}
          onChange={e => setProfile(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") request() }}
          placeholder="padel-austria.at/players/dein-name"
          className="flex-1 bg-transparent rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 outline-none min-w-0"
          style={{ border: "1px solid rgba(212,245,60,0.2)", fontFamily: "'Barlow Condensed', sans-serif" }}
        />
        <button
          onClick={request}
          disabled={loading}
          className="px-4 py-2 rounded-lg text-sm font-bold tracking-wide"
          style={{ fontFamily: "'Barlow Condensed', sans-serif", background: lime, color: "#080810" }}
        >
          {loading ? "…" : "URTEIL ANFORDERN"}
        </button>
      </div>

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

      {loading && (
        <div className="text-center py-10 text-gray-600 text-sm">
          <img src="/cat-head.svg" alt="Yara" className="h-16 w-auto mx-auto mb-3 opacity-30 animate-pulse" />
          <p>Yara liest deine letzten Turniere …</p>
        </div>
      )}

      {f && (
        <div className="mt-4">
          {/* Player + stat field */}
          <div className="flex items-baseline gap-3 mb-3">
            <span className="text-2xl font-bold text-white">{f.player.name}</span>
          </div>
          <div className="grid grid-cols-4 gap-2 mb-2">
            {[
              { label: "Platz", value: f.player.rank ?? "–" },
              { label: "Punkte", value: f.player.points ?? "–" },
              { label: "APN", value: f.player.apn ?? "–" },
              { label: "Effektiv.", value: f.player.effectiveness ? `${f.player.effectiveness} %` : "–" },
            ].map(s => (
              <div key={s.label} style={{ background: card, borderRadius: 8, padding: "10px 6px", textAlign: "center" }}>
                <div className="text-xs uppercase tracking-wide" style={{ color: "#6b7280" }}>{s.label}</div>
                <div className="text-xl font-bold" style={{ color: s.label === "Effektiv." ? lime : "#fff" }}>{s.value}</div>
              </div>
            ))}
          </div>
          <p className="text-xs mb-5" style={{ color: "#4b5563" }}>
            Stand: {f.window.matches_analysed} ausgewertete Matches
          </p>

          {/* Beobachtungen */}
          {data!.beobachtungen.length > 0 && (
            <>
              <div className="text-sm font-semibold uppercase tracking-wider mb-2" style={{ color: "#9ca3af", fontFamily: "'Barlow Condensed', sans-serif" }}>
                Beobachtungen
              </div>
              <div className="flex flex-col gap-2 mb-5">
                {data!.beobachtungen.map((b: string, i: number) => (
                  <div key={i} className="flex gap-2 text-sm" style={{ color: "#cbd1d9", lineHeight: 1.4 }}>
                    <span style={{ color: "#4b5563" }}>•</span>
                    <span>{b}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Yaras Urteil */}
          {data!.urteil ? (
            <div style={{ background: "rgba(212,245,60,0.05)", border: `1px solid rgba(212,245,60,0.3)`, borderRadius: 12, padding: "16px 16px 13px", marginBottom: 8 }}>
              <div className="flex items-center gap-2 mb-2">
                <CatHead />
                <span className="font-bold tracking-wide" style={{ fontSize: 18, color: lime, fontFamily: "'Barlow Condensed', sans-serif" }}>YARAS URTEIL</span>
              </div>
              <p style={{ margin: 0, fontSize: 17, lineHeight: 1.5, color: "#e9edf2" }}>{data!.urteil}</p>
            </div>
          ) : (
            <div className="text-sm mb-4" style={{ color: "#9ca3af" }}>
              Yara konnte sich gerade keine Meinung bilden — die Daten stehen oben.
            </div>
          )}

          {/* Disclaimer + feedback */}
          <div className="flex items-center gap-3 flex-wrap mb-6">
            <span className="text-xs" style={{ color: "#4b5563" }}>{data!.disclaimer}</span>
            <a href={`mailto:yara@adventure-it.at?subject=Yara%20korrigieren%20(${data!.slug})`} className="text-xs" style={{ color: "#9ca3af", border: "1px solid rgba(255,255,255,0.14)", borderRadius: 6, padding: "3px 9px", textDecoration: "none" }}>
              Yara korrigieren
            </a>
          </div>

          {/* Kommende Turniere (Ausblick) */}
          {data!.upcoming.length > 0 && (
            <>
              <div className="text-sm font-semibold uppercase tracking-wider mb-2" style={{ color: "#9ca3af", fontFamily: "'Barlow Condensed', sans-serif" }}>
                Kommende Turniere
              </div>
              <div className="flex flex-col gap-2 mb-6">
                {data!.upcoming.slice(0, 4).map((t: UrteilData["upcoming"][number], i: number) => (
                  <a key={i} href={t.source_url} target="_blank" rel="noopener noreferrer"
                    className="flex items-center justify-between"
                    style={{ background: "rgba(212,245,60,0.06)", border: "1px solid rgba(212,245,60,0.18)", borderRadius: 8, padding: "9px 12px", textDecoration: "none" }}>
                    <div>
                      <div className="text-sm text-white">{t.title}</div>
                      {t.competition && <div className="text-xs" style={{ color: "#9ca3af" }}>{t.competition}{t.status ? ` · ${t.status}` : ""}</div>}
                    </div>
                    <span className="text-sm" style={{ color: lime, whiteSpace: "nowrap" }}>Details →</span>
                  </a>
                ))}
              </div>
            </>
          )}

          {/* Share */}
          {data!.urteil && (
            <button onClick={handleShare} className="w-full py-3 rounded-xl text-sm font-bold tracking-wide"
              style={{ border: "1px solid rgba(212,245,60,0.3)", color: copied ? "#080810" : lime, background: copied ? lime : "transparent", fontFamily: "'Barlow Condensed', sans-serif", fontSize: "1rem" }}>
              {copied ? "KOPIERT" : "URTEIL TEILEN"}
            </button>
          )}
        </div>
      )}

      {!f && !loading && !error && (
        <div className="text-center py-8 text-gray-600 text-sm">
          <img src="/cat-head.svg" alt="Yara" className="h-16 w-auto mx-auto mb-3 opacity-30" />
          <p>Profil rein. Urteil raus.</p>
        </div>
      )}
    </div>
  )
}
