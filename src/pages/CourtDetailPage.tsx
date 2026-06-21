import { useEffect, useState } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { Helmet } from "react-helmet-async"
import { fetchVenueDetail } from "../api"
import { trackBookingClick } from "../api"
import type { VenueDetail, RelatedVenue } from "../types"

const COURT_TYPE_LABEL: Record<string, string> = {
  indoor: "Indoor",
  outdoor: "Outdoor",
  "indoor+outdoor": "Indoor & Outdoor",
}
const COURT_TYPE_ICON: Record<string, string> = {
  indoor: "🏠",
  outdoor: "🌳",
  "indoor+outdoor": "🏠🌳",
}

// Build the courts label:
// - All one type  → "3 Outdoor-Courts" / "4 Indoor-Courts"
// - Mixed         → "5 Courts, davon 3 Indoor + 2 Outdoor"
// - Type unknown  → "4 Courts"
function courtsText(d: VenueDetail): string | null {
  if (d.num_courts == null) return null
  const i = d.indoor_count ?? 0
  const o = d.outdoor_count ?? 0
  if (i > 0 && o === 0) return `${i} Indoor-Courts`
  if (o > 0 && i === 0) return `${o} Outdoor-Courts`
  if (i > 0 && o > 0)   return `${d.num_courts} Courts, davon ${i} Indoor + ${o} Outdoor`
  return `${d.num_courts} Courts`
}

// One amenity row. state: true = yes, false = no, null/undefined = unknown.
function AmenityFact({
  icon, label, state, yesText = "Vorhanden", noText = "Nicht vorhanden", sub, wide,
}: {
  icon: string
  label: string
  state?: boolean | null
  yesText?: string
  noText?: string
  sub?: string | null
  wide?: boolean
}) {
  const unknown = state == null
  return (
    <div className={`vd-fact${wide ? " vd-wide" : ""}${unknown ? " vd-unknown" : ""}`}>
      <div className="vd-top">
        <span className="vd-ic">{icon}</span>
        <div className="vd-body">
          <div className="vd-k">{label}</div>
          <div className={`vd-v ${unknown ? "" : state ? "yes" : "no"}`}>
            {unknown ? "Noch unbekannt" : state ? yesText : noText}
          </div>
          {!unknown && state && sub && <div className="vd-sub">{sub}</div>}
        </div>
      </div>
    </div>
  )
}

function RelatedCard({ v }: { v: RelatedVenue }) {
  return (
    <Link className="vd-vcard" to={`/court/${v.id}`}>
      <div className="vd-n">{v.name}</div>
      <div className="vd-m">
        {v.city || v.operator}
        {v.num_courts ? <> · <b>{v.num_courts} Courts</b></> : null}
      </div>
    </Link>
  )
}

// Fields that can be community-reported. Only unknown ones (null) are shown.
const SUGGEST_FIELDS: { key: string; label: string; type: "bool" | "number" }[] = [
  { key: "num_courts",     label: "Anzahl Courts",  type: "number" },
  { key: "changing_rooms", label: "Umkleiden",      type: "bool"   },
  { key: "showers",        label: "Duschen",        type: "bool"   },
  { key: "reception",      label: "Rezeption",      type: "bool"   },
  { key: "parking",        label: "Parkplatz",      type: "bool"   },
  { key: "rental_rackets", label: "Leihschläger",   type: "bool"   },
  { key: "gastro",         label: "Gastronomie",    type: "bool"   },
]

export default function CourtDetailPage() {
  const { slug = "" } = useParams()
  const navigate = useNavigate()
  const [d, setD] = useState<VenueDetail | null>(null)
  const [state, setState] = useState<"loading" | "ok" | "notfound" | "error">("loading")

  // Community "Schreibs Yara" form — picks maps field key → "Ja" | "Nein" | free text
  const [picks, setPicks] = useState<Record<string, string>>({})
  const [freeText, setFreeText] = useState("")
  const [sent, setSent] = useState(false)

  useEffect(() => {
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState("loading")
    fetchVenueDetail(slug)
      .then((res) => {
        if (!alive) return
        if (!res) { setState("notfound"); return }
        setD(res)
        setState("ok")
      })
      .catch(() => alive && setState("error"))
    return () => { alive = false }
  }, [slug])

  // SEO handled via <Helmet> below — no manual document.title needed

  if (state === "loading") {
    return <div className="py-16 text-center text-gray-600 text-sm">Lädt …</div>
  }
  if (state === "notfound") {
    return (
      <div className="py-16 text-center">
        <p className="text-3xl mb-3">🎾</p>
        <p className="text-white font-semibold mb-1">Diese Anlage kennt Yara nicht.</p>
        <Link to="/padelrevier" className="text-sm" style={{ color: "#d4f53c" }}>← Zurück zur Karte</Link>
      </div>
    )
  }
  if (state === "error" || !d) {
    return (
      <div className="py-16 text-center">
        <p className="text-white font-semibold mb-1">Da ist was schiefgelaufen.</p>
        <button onClick={() => navigate(0)} className="text-sm" style={{ color: "#d4f53c" }}>Nochmal versuchen</button>
      </div>
    )
  }

  const photos = d.photos ?? []
  const cText = courtsText(d)
  const rel = d.related
  const finderHref = `/?ort=${encodeURIComponent(d.city || d.name)}`
  const unknown = SUGGEST_FIELDS.filter(f => (d as unknown as Record<string, unknown>)[f.key] == null)

  const pageTitle = `${d.name}${d.city ? " · " + d.city : ""} — PadelYara`
  const metaDesc = [
    d.name,
    d.city ? `in ${d.city}` : null,
    d.court_type === "indoor" ? "Indoor Padel" : d.court_type === "outdoor" ? "Outdoor Padel" : "Indoor & Outdoor Padel",
    d.num_courts ? `${d.num_courts} Courts` : null,
    "Verfügbarkeit & Preise auf PadelYara prüfen.",
  ].filter(Boolean).join(" · ")

  const ld = {
    "@context": "https://schema.org",
    "@type": "SportsActivityLocation",
    "name": d.name,
    "url": `https://padelyara.at/court/${d.id}`,
    ...(d.address ? { "address": d.address } : {}),
    ...(d.lat != null && d.lon != null
      ? { "geo": { "@type": "GeoCoordinates", "latitude": d.lat, "longitude": d.lon } }
      : {}),
    "sport": "Padel",
    ...(d.photos && d.photos.length ? { "image": d.photos } : {}),
  }

  return (
    <div className="vd">
      <Helmet>
        <title>{pageTitle}</title>
        <meta name="description" content={metaDesc} />
        <link rel="canonical" href={`https://padelyara.at/court/${d.id}`} />
        <script type="application/ld+json">{JSON.stringify(ld)}</script>
      </Helmet>

      <DetailStyles />

      {/* Breadcrumb */}
      <div className="vd-crumbs">
        <Link to="/padelrevier">Padelrevier</Link> ›{" "}
        {d.city ? <><Link to="/padelrevier">{d.city}</Link> › </> : null}
        <span>{d.name}</span>
      </div>

      {/* Photo gallery — only when we actually have photos */}
      {photos.length > 0 && (
        <div className={`vd-gallery vd-g-${Math.min(photos.length, 4)}`}>
          {photos.slice(0, 4).map((src, i) => (
            <div key={i} className={`vd-ph${i === 0 ? " vd-main" : ""}`}>
              <img src={src} alt={`${d.name} — Foto ${i + 1}`} loading="lazy" />
            </div>
          ))}
        </div>
      )}

      {/* Hero */}
      <h1 className="vd-h1">{d.name}</h1>
      <div className="vd-addr">
        {d.address ? <>📍 {d.address}</> : null}
        {d.maps_url ? <> · <a href={d.maps_url} target="_blank" rel="noopener noreferrer">Auf Google Maps öffnen</a></> : null}
        {d.website_url ? <> · <a href={d.website_url} target="_blank" rel="noopener noreferrer">🌐 Webseite des Anbieters</a></> : null}
      </div>

      <div className="vd-badges">
        <span className="vd-badge lime">{COURT_TYPE_ICON[d.court_type]} {COURT_TYPE_LABEL[d.court_type] ?? d.court_type}</span>
        {d.num_courts ? <span className="vd-badge">{d.num_courts} Courts</span> : null}
        {d.platform ? <span className="vd-badge">{d.platform}</span> : null}
      </div>

      <Link className="vd-cta vd-primary" to={finderHref}>Freie Courts &amp; Preise prüfen →</Link>
      {d.booking_url && (
        <a
          className="vd-cta-secondary"
          href={d.booking_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => trackBookingClick(d.id, d.platform ?? "")}
        >
          Direkt {d.platform ? `auf ${d.platform} ` : ""}buchen ↗
        </a>
      )}

      {/* Ausstattung */}
      <div className="vd-sec-title">Ausstattung</div>
      <div className="vd-facts">
        {cText
          ? <div className="vd-fact vd-wide"><div className="vd-top"><span className="vd-ic">🎾</span><div className="vd-body"><div className="vd-k">Courts</div><div className="vd-v">{cText}</div></div></div></div>
          : <AmenityFact icon="🎾" label="Courts" state={null} wide />}

        <AmenityFact icon="🧥" label="Umkleiden" state={d.changing_rooms} />
        <AmenityFact icon="🚿" label="Duschen" state={d.showers} />
        <AmenityFact
          icon="🛎️" label="Rezeption" state={d.reception}
          yesText="Vorhanden" noText="Self-Service" sub={d.reception_note}
        />
        <AmenityFact
          icon="🅿️" label="Parkplatz" state={d.parking}
          yesText={d.parking_free === true ? "Kostenlos" : d.parking_free === false ? "Kostenpflichtig" : d.parking_note || "Vorhanden"}
          sub={d.parking_note ?? undefined}
        />

        {d.public_transport && (
          <div className="vd-fact vd-wide">
            <div className="vd-top">
              <span className="vd-ic">🚇</span>
              <div className="vd-body">
                <div className="vd-k">Öffentliche Verkehrsmittel</div>
                <div className="vd-v">{d.public_transport}</div>
              </div>
            </div>
          </div>
        )}
        <AmenityFact
          icon="🏓" label="Leihschläger" state={d.rental_rackets}
          yesText="Ja" sub={d.rental_rackets_system}
        />

        {/* Gastronomie */}
        {d.gastro == null ? (
          <AmenityFact icon="🍽️" label="Gastronomie" state={null} wide />
        ) : d.gastro === false ? (
          <AmenityFact icon="🍽️" label="Gastronomie" state={false} wide />
        ) : (
          <div className="vd-fact vd-wide">
            <div className="vd-top">
              <span className="vd-ic">🍽️</span>
              <div className="vd-body">
                <div className="vd-k">Gastronomie</div>
                <div className="vd-v yes">{d.gastro_name || "Vorhanden"}</div>
              </div>
            </div>
            {(d.gastro_maps_url || d.gastro_menu_url || d.gastro_hours) && (
              <div className="vd-links">
                {d.gastro_maps_url && <a href={d.gastro_maps_url} target="_blank" rel="noopener noreferrer">📍 Google Maps</a>}
                {d.gastro_menu_url && <a href={d.gastro_menu_url} target="_blank" rel="noopener noreferrer">📋 Speisekarte</a>}
                {d.gastro_hours && <span className="vd-sub">🕒 {d.gastro_hours}</span>}
              </div>
            )}
          </div>
        )}

        {/* Besonderheiten — only when present */}
        {d.extras && (
          <div className="vd-fact vd-wide">
            <div className="vd-top">
              <span className="vd-ic">⭐</span>
              <div className="vd-body"><div className="vd-k">Besonderheiten</div><div className="vd-v">{d.extras}</div></div>
            </div>
          </div>
        )}

        {/* Stornobedingungen — scraped text + "no guarantee" disclaimer + verify link */}
        <div className={`vd-fact vd-wide${d.cancellation_policy ? "" : " vd-unknown"}`}>
          <div className="vd-top">
            <span className="vd-ic">📋</span>
            <div className="vd-body">
              <div className="vd-k">Stornobedingungen</div>
              {d.cancellation_policy
                ? <div className="vd-policy">{d.cancellation_policy}</div>
                : <div className="vd-v">Noch unbekannt</div>}
            </div>
          </div>
          <div className="vd-storno-foot">
            {d.cancellation_policy && (
              <span className="vd-disclaimer">⚠️ Ohne Gewähr — kann sich geändert haben.</span>
            )}
            {d.cancellation_url && (
              <a href={d.cancellation_url} target="_blank" rel="noopener noreferrer">
                Beim Anbieter prüfen →
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Community CTA */}
      <div className="vd-community">
        {sent ? (
          <>
            <h3>Hat Yara.</h3>
            <p>Danke. Sie prüft's und ergänzt's.</p>
          </>
        ) : (
          <>
            <h3>Kennst du diese Anlage?</h3>
            <p>Du warst dort und weißt mehr? Trag alles auf einmal ein — Yara prüft's und ergänzt's.</p>
            <form
              className="vd-form"
              onSubmit={(e) => {
                e.preventDefault()
                const filled = unknown.filter(f => picks[f.key])
                if (!filled.length && !freeText.trim()) return
                const subject = `PadelYara: Info zu ${d.name}`
                const lines: string[] = [`Anlage: ${d.name} (${d.id})`]
                for (const f of filled) lines.push(`${f.label}: ${picks[f.key]}`)
                if (freeText.trim()) lines.push(`\nSonstiges: ${freeText.trim()}`)
                // eslint-disable-next-line react-hooks/immutability
                window.location.href =
                  `mailto:yara@adventure-it.at?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.join("\n"))}`
                setSent(true)
              }}
            >
              {unknown.length > 0 && (
                <div className="vd-suggest-grid">
                  {unknown.map(f => (
                    <div key={f.key} className="vd-suggest-row">
                      <span className="vd-suggest-label">{f.label}</span>
                      {f.type === "bool" ? (
                        <span className="vd-toggle-group">
                          <button type="button"
                            className={`vd-toggle${picks[f.key] === "Ja" ? " on-yes" : ""}`}
                            onClick={() => setPicks(p => ({ ...p, [f.key]: p[f.key] === "Ja" ? "" : "Ja" }))}>
                            Ja
                          </button>
                          <button type="button"
                            className={`vd-toggle${picks[f.key] === "Nein" ? " on-no" : ""}`}
                            onClick={() => setPicks(p => ({ ...p, [f.key]: p[f.key] === "Nein" ? "" : "Nein" }))}>
                            Nein
                          </button>
                        </span>
                      ) : (
                        <input type="number" className="vd-suggest-input" placeholder="Anzahl" min={1} max={30}
                          value={picks[f.key] || ""}
                          onChange={e => setPicks(p => ({ ...p, [f.key]: e.target.value }))} />
                      )}
                    </div>
                  ))}
                </div>
              )}
              <textarea
                placeholder={unknown.length ? "Sonst noch was? Freier Text …" : "Was weißt du? Freier Text …"}
                value={freeText}
                onChange={e => setFreeText(e.target.value)}
                rows={2}
              />
              <button type="submit">Abschicken</button>
            </form>
          </>
        )}
      </div>

      {/* Cross-links */}
      {rel && (rel.same_city.length > 0 || rel.same_operator.length > 0) && (
        <div className="vd-block">
          <div className="vd-sec-title">Andere Anlagen</div>
          {rel.same_city.length > 0 && (
            <>
              <div className="vd-group-label">In <b>{rel.city}</b></div>
              <div className="vd-links-grid" style={{ marginBottom: rel.same_operator.length ? 18 : 0 }}>
                {rel.same_city.map((v) => <RelatedCard key={v.id} v={v} />)}
              </div>
            </>
          )}
          {rel.same_operator.length > 0 && (
            <>
              <div className="vd-group-label">Betreiber <b>{rel.operator}</b></div>
              <div className="vd-links-grid">
                {rel.same_operator.map((v) => <RelatedCard key={v.id} v={v} />)}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// Scoped styles ported from the approved mockup (prefixed `vd-` to avoid clashes).
function DetailStyles() {
  return (
    <style>{`
      .vd { font-family: "Barlow Condensed", sans-serif; color: #f5f6f4; line-height: 1.25; }
      .vd a { text-decoration: none; }

      .vd-crumbs { font-size: 14px; color: #6b7280; margin-bottom: 14px; }
      .vd-crumbs a { color: #6b7280; }
      .vd-crumbs a:hover { color: #d4f53c; }
      .vd-crumbs span { color: #9ca3af; }

      .vd-gallery { display: grid; gap: 8px; border-radius: 16px; overflow: hidden; margin-bottom: 18px; grid-template-rows: 110px 110px; }
      .vd-gallery.vd-g-1 { grid-template-columns: 1fr; grid-template-rows: 220px; }
      .vd-gallery.vd-g-2 { grid-template-columns: 1fr 1fr; grid-template-rows: 180px; }
      .vd-gallery.vd-g-3, .vd-gallery.vd-g-4 { grid-template-columns: 2fr 1fr 1fr; }
      .vd-ph { background: linear-gradient(135deg, #1a1d27, #0d0f16); overflow: hidden; }
      .vd-gallery.vd-g-3 .vd-main, .vd-gallery.vd-g-4 .vd-main { grid-row: 1 / 3; }
      .vd-ph img { width: 100%; height: 100%; object-fit: cover; display: block; }

      .vd-h1 { font-size: 38px; font-weight: 700; letter-spacing: 0.3px; line-height: 1.02; margin-bottom: 6px; }
      .vd-addr { font-size: 17px; color: #9ca3af; font-weight: 500; margin-bottom: 12px; }
      .vd-addr a { color: #9ca3af; text-decoration: underline; text-underline-offset: 2px; }
      .vd-addr a:hover { color: #d4f53c; }

      .vd-badges { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 18px; }
      .vd-badge { font-size: 14px; font-weight: 600; letter-spacing: 0.3px; padding: 4px 11px; border-radius: 999px; border: 1px solid rgba(107,114,128,0.30); color: #9ca3af; display: inline-flex; align-items: center; gap: 5px; }
      .vd-badge.lime { border-color: rgba(212,245,60,0.5); color: #d4f53c; background: rgba(212,245,60,0.07); }

      .vd-cta { display: block; text-align: center; background: #d4f53c; color: #080810; font-size: 17px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; padding: 14px; border-radius: 11px; }
      .vd-cta:hover { opacity: 0.92; }
      .vd-cta.vd-primary { margin-bottom: 10px; }
      .vd-cta-secondary { display: block; text-align: center; background: transparent; color: rgba(212,245,60,0.8); border: 1px solid rgba(212,245,60,0.35); font-size: 16px; font-weight: 600; letter-spacing: 0.6px; padding: 12px; border-radius: 11px; margin-bottom: 26px; }
      .vd-cta-secondary:hover { border-color: rgba(212,245,60,0.7); color: #d4f53c; }

      .vd-sec-title { font-size: 13px; font-weight: 700; letter-spacing: 1.4px; text-transform: uppercase; color: #d4f53c; margin: 0 2px 12px; }

      .vd-facts { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 28px; }
      .vd-fact { background: #11131a; border: 1px solid rgba(107,114,128,0.30); border-radius: 13px; padding: 13px 14px; }
      .vd-fact .vd-top { display: flex; align-items: center; gap: 11px; }
      .vd-ic { font-size: 21px; width: 26px; text-align: center; flex-shrink: 0; }
      .vd-body { min-width: 0; }
      .vd-k { font-size: 12px; letter-spacing: 0.8px; text-transform: uppercase; color: #6b7280; font-weight: 600; }
      .vd-v { font-size: 18px; font-weight: 600; color: #f5f6f4; }
      .vd-v.yes { color: #4ade80; }
      .vd-v.no { color: #f87171; }
      .vd-unknown { border-style: dashed; opacity: 0.7; }
      .vd-unknown .vd-v { color: #6b7280; font-style: italic; font-weight: 500; }
      .vd-sub { font-size: 13px; color: #9ca3af; font-weight: 500; }
      .vd-fact.vd-wide { grid-column: 1 / -1; }
      .vd-links { display: flex; flex-wrap: wrap; gap: 14px; padding-left: 37px; margin-top: 6px; align-items: center; }
      .vd-links a { color: #d4f53c; font-size: 13px; font-weight: 600; }
      .vd-links a:hover { text-decoration: underline; }

      .vd-policy { font-size: 15px; font-weight: 500; color: #d1d5db; line-height: 1.4; margin-top: 2px; }
      .vd-storno-foot { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; padding-left: 37px; margin-top: 8px; }
      .vd-disclaimer { font-size: 12.5px; color: #c89a2a; font-weight: 500; }
      .vd-storno-foot a { color: #d4f53c; font-size: 13px; font-weight: 600; }
      .vd-storno-foot a:hover { text-decoration: underline; }

      .vd-community { background: linear-gradient(135deg, rgba(212,245,60,0.06), rgba(212,245,60,0.02)); border: 1px dashed rgba(212,245,60,0.4); border-radius: 16px; padding: 20px; margin-bottom: 30px; }
      .vd-community h3 { font-size: 24px; font-weight: 700; margin-bottom: 5px; }
      .vd-community p { font-size: 16px; color: #9ca3af; font-weight: 500; margin-bottom: 14px; max-width: 52ch; }
      .vd-form { display: flex; flex-direction: column; gap: 9px; }
      .vd-form textarea { background: #15171f; border: 1px solid rgba(107,114,128,0.30); color: #f5f6f4; border-radius: 9px; padding: 10px 12px; font-family: inherit; font-size: 16px; font-weight: 500; outline: none; resize: vertical; }
      .vd-form textarea:focus { border-color: rgba(212,245,60,0.6); }
      .vd-form button { background: #d4f53c; color: #080810; border: none; cursor: pointer; font-family: inherit; font-size: 15px; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; border-radius: 9px; padding: 10px 20px; align-self: flex-start; }
      .vd-suggest-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 16px; margin-bottom: 4px; }
      .vd-suggest-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
      .vd-suggest-label { font-size: 15px; font-weight: 600; color: #d1d5db; }
      .vd-toggle-group { display: flex; gap: 5px; flex-shrink: 0; }
      .vd-toggle { background: #15171f; border: 1px solid rgba(107,114,128,0.30); color: #9ca3af; border-radius: 7px; padding: 5px 13px; font-family: inherit; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.12s; }
      .vd-toggle:hover { border-color: rgba(212,245,60,0.4); color: #d4f53c; }
      .vd-toggle.on-yes { background: rgba(74,222,128,0.12); border-color: #4ade80; color: #4ade80; }
      .vd-toggle.on-no  { background: rgba(248,113,113,0.12); border-color: #f87171; color: #f87171; }
      .vd-suggest-input { background: #15171f; border: 1px solid rgba(107,114,128,0.30); color: #f5f6f4; border-radius: 7px; padding: 5px 10px; font-family: inherit; font-size: 15px; font-weight: 600; outline: none; width: 70px; text-align: center; }
      .vd-suggest-input:focus { border-color: rgba(212,245,60,0.6); }

      .vd-links-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
      .vd-vcard { background: #11131a; border: 1px solid rgba(107,114,128,0.30); border-radius: 13px; padding: 13px 15px; display: block; transition: border-color 0.15s; }
      .vd-vcard:hover { border-color: rgba(212,245,60,0.5); }
      .vd-n { font-size: 19px; font-weight: 600; color: #f5f6f4; margin-bottom: 2px; }
      .vd-m { font-size: 14px; color: #6b7280; font-weight: 500; }
      .vd-m b { color: #d4f53c; font-weight: 600; }
      .vd-group-label { font-size: 14px; color: #6b7280; font-weight: 500; margin: 0 2px 9px; }
      .vd-group-label b { color: #9ca3af; font-weight: 600; }
      .vd-block { margin-bottom: 30px; }

      @media (max-width: 560px) {
        .vd-h1 { font-size: 30px; }
        .vd-facts { grid-template-columns: 1fr; }
        .vd-gallery.vd-g-3, .vd-gallery.vd-g-4 { grid-template-columns: 1fr 1fr; grid-template-rows: 100px 80px; }
        .vd-gallery.vd-g-3 .vd-main, .vd-gallery.vd-g-4 .vd-main { grid-column: 1 / 3; grid-row: 1; }
        .vd-suggest-grid { grid-template-columns: 1fr; }
      }
    `}</style>
  )
}
