import { Helmet } from "react-helmet-async"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { MapContainer, TileLayer, Marker, Popup, GeoJSON, useMap } from "react-leaflet"
import MarkerClusterGroup from "react-leaflet-cluster"
import L from "leaflet"
import type { GeoJsonObject, FeatureCollection } from "geojson"
import { useNavigate } from "react-router-dom"
import "leaflet/dist/leaflet.css"
import "leaflet.markercluster/dist/MarkerCluster.css"
import "leaflet.markercluster/dist/MarkerCluster.Default.css"
import { fetchVenues } from "../api"
import type { MapVenue } from "../types"
import bundeslaenderRaw from "../data/austria-bundeslaender.json"
import { bundeslandFromAddress } from "../data/plz"

const BUNDESLAENDER = [
  "Wien", "Niederösterreich", "Oberösterreich", "Steiermark",
  "Tirol", "Kärnten", "Salzburg", "Vorarlberg", "Burgenland",
]

// Austria's 9 Bundesländer as boundary polygons — used to (a) draw Austria as a
// distinct lime shape against the dark neighbours and (b) zoom the map to the
// selected region. Feature `name` matches the chip labels above.
const BUNDESLAENDER_GEO = bundeslaenderRaw as unknown as FeatureCollection
const AUSTRIA_BOUNDS = L.geoJSON(BUNDESLAENDER_GEO as GeoJsonObject).getBounds()

function boundsForSelection(selected: string[]): L.LatLngBounds {
  const names = selected.filter(n => n !== "Unbekannt")
  if (names.length === 0) return AUSTRIA_BOUNDS
  const feats = BUNDESLAENDER_GEO.features.filter(f => names.includes(f.properties?.name))
  if (feats.length === 0) return AUSTRIA_BOUNDS
  return L.geoJSON({ type: "FeatureCollection", features: feats } as GeoJsonObject).getBounds()
}

// Lives inside MapContainer so it can grab the Leaflet map; re-fits the view to
// the selected Bundesland(s) whenever the selection changes (or to all of
// Austria when nothing is selected).
function MapFit({ selected }: { selected: string[] }) {
  const map = useMap()
  const key = selected.slice().sort().join("|")
  useEffect(() => {
    map.fitBounds(boundsForSelection(selected), { padding: [24, 24], animate: false })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return null
}

// Labels for popups — includes the combined type (a venue can have both).
const COURT_TYPE_LABELS: Record<string, string> = {
  indoor: "Indoor",
  outdoor: "Outdoor",
  "indoor+outdoor": "Indoor & Outdoor",
}

function courtTypeLabel(ct: string): string {
  return COURT_TYPE_LABELS[ct] ?? ct
}

// Filter chips: just Indoor / Outdoor. "Indoor & Outdoor" is dropped — it
// duplicated "Alle" visually; instead a both-courts venue matches either chip.
const COURT_TYPE_FILTERS = [
  { key: "indoor", label: "Indoor" },
  { key: "outdoor", label: "Outdoor" },
]

// Lime brand pin via divIcon — also sidesteps the well-known broken default
// Leaflet marker icons under Vite (asset paths don't resolve through the bundler).
const pinIcon = L.divIcon({
  className: "padel-pin",
  html: `<div style="width:14px;height:14px;border-radius:50%;background:#d4f53c;border:2px solid #080810;box-shadow:0 0 0 2px rgba(212,245,60,0.4)"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
  popupAnchor: [0, -8],
})

const CHIP_BASE = "text-xs px-2.5 py-1 rounded-full border transition-colors cursor-pointer"
function chipStyle(active: boolean) {
  return {
    borderColor: active ? "#d4f53c" : "rgba(107,114,128,0.4)",
    color: active ? "#d4f53c" : "#9ca3af",
    background: active ? "rgba(212,245,60,0.08)" : "transparent",
  }
}

// Multi-select chip group — same look as the Turnierjagd filters.
function MultiChip({
  label, options, selected, onChange,
}: {
  label: string
  options: { key: string; label: string }[]
  selected: string[]
  onChange: (v: string[]) => void
}) {
  function toggle(opt: string) {
    onChange(selected.includes(opt) ? selected.filter(x => x !== opt) : [...selected, opt])
  }
  const allSelected = selected.length === 0
  return (
    <div className="mb-4">
      <p className="text-xs text-gray-500 mb-2 tracking-wide uppercase">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        <button onClick={() => onChange([])} className={CHIP_BASE} style={chipStyle(allSelected)}>
          Alle
        </button>
        {options.map(opt => (
          <button
            key={opt.key}
            onClick={() => toggle(opt.key)}
            className={CHIP_BASE}
            style={chipStyle(selected.includes(opt.key))}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

const POPUP_LINK = "text-xs font-semibold tracking-wide"

export default function PadelrevierPage() {
  const navigate = useNavigate()
  const [venues, setVenues] = useState<MapVenue[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [bundesland, setBundesland] = useState<string[]>([])
  const [courtType, setCourtType] = useState<string[]>([])
  const [query, setQuery] = useState("")
  const [showSuggestions, setShowSuggestions] = useState(false)

  useEffect(() => {
    fetchVenues()
      .then(setVenues)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  // Only offer Bundesland chips that actually have venues; keep the canonical order.
  const blOptions = useMemo(() => {
    const present = new Set(venues.map(v => bundeslandFromAddress(v.address)))
    const opts = BUNDESLAENDER.filter(bl => present.has(bl)).map(bl => ({ key: bl, label: bl }))
    if (present.has("Unbekannt")) opts.push({ key: "Unbekannt", label: "Unbekannt" })
    return opts
  }, [venues])

  const suggestions = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (q.length < 2) return []
    return venues
      .filter(v => v.name.toLowerCase().includes(q) || v.address.toLowerCase().includes(q))
      .slice(0, 8)
  }, [venues, query])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return venues.filter(v => {
      const blOk = bundesland.length === 0 || bundesland.includes(bundeslandFromAddress(v.address))
      const ctOk = courtType.length === 0
        || courtType.includes(v.court_type)
        || (v.court_type === "indoor+outdoor" && (courtType.includes("indoor") || courtType.includes("outdoor")))
      const qOk = q.length < 2 || v.name.toLowerCase().includes(q) || v.address.toLowerCase().includes(q)
      return blOk && ctOk && qOk
    })
  }, [venues, bundesland, courtType, query])

  // Some places are stored as two records on identical coordinates (e.g. an
  // indoor and an outdoor venue at the same address — Padeldome Alte Donau).
  // Group the (already-filtered) venues by coordinate so each location is one
  // pin; the popup then lists every venue at that spot.
  const groups = useMemo(() => {
    const m = new Map<string, MapVenue[]>()
    for (const v of visible) {
      const key = `${v.lat},${v.lon}`
      const g = m.get(key)
      if (g) g.push(v); else m.set(key, [v])
    }
    return [...m.values()]
  }, [visible])

  // Jump into the Court Finder pre-filled to this venue. We pass the venue's
  // exact coords (lat/lon) so the Finder centers on it directly — bare PLZ
  // geocodes to a district centroid that can exclude the venue, and full street
  // addresses geocode unreliably. The venue name shows in the location field;
  // venueId drives the highlight. Date/time stay default so she picks when.
  function checkAvailability(v: MapVenue) {
    const q = new URLSearchParams({
      ort: v.name,
      lat: String(v.lat),
      lon: String(v.lon),
      radius: "5",
      venueId: v.id,
    })
    navigate(`/?${q.toString()}`)
  }

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": "Padel Courts in Österreich — alle Anlagen auf der Karte",
    "description": "Interaktive Karte aller Padel-Anlagen in Österreich. Über 165 Courts in Wien, Graz, Linz, Salzburg und ganz Österreich — indoor und outdoor. Verfügbarkeit direkt prüfen.",
    "url": "https://www.padelyara.at/padelrevier",
    "provider": {
      "@type": "Organization",
      "name": "PadelYara",
      "url": "https://www.padelyara.at"
    },
    "about": {
      "@type": "SportsActivityLocation",
      "name": "Padel Courts Österreich",
      "sport": "Padel"
    }
  }

  return (
    <>
      <Helmet>
        <title>Padel Courts Wien & Österreich — alle Anlagen auf der Karte | PadelYara</title>
        <meta name="description" content="Alle Padel-Anlagen in Österreich auf einer interaktiven Karte. 165+ Courts in Wien, Graz, Linz und ganz Österreich — indoor und outdoor. Verfügbarkeit direkt prüfen." />
        <link rel="canonical" href="https://www.padelyara.at/padelrevier" />
        <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      </Helmet>

      <h1
        className="text-xl font-bold mb-1 mt-2"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#fff", letterSpacing: "0.01em" }}
      >
        Padel Courts in Österreich
      </h1>
      <p
        className="text-base italic mb-3"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c" }}
      >
        Jeder Court in Österreich. Mein Revier. Such dir einen aus.
      </p>
      <p className="text-sm text-gray-400 mb-5" style={{ maxWidth: 640, lineHeight: 1.6 }}>
        Über 165 Padel-Anlagen und 400+ Courts in ganz Österreich. Indoor, Outdoor, Wien, Graz,
        Linz, Salzburg und alles dazwischen. Jeder Pin zeigt Adresse, Öffnungszeiten und
        Verfügbarkeit. Irgendwo ist gerade ein Court frei geworden. Ich weiß welcher.
      </p>

      {/* Search field */}
      <div className="relative mb-5" style={{ maxWidth: 400 }}>
        <input
          type="text"
          value={query}
          onChange={e => { setQuery(e.target.value); setShowSuggestions(true) }}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
          placeholder="Anlage suchen …"
          className="w-full text-sm px-4 py-2 rounded-lg outline-none"
          style={{
            background: "rgba(255,255,255,0.06)", border: "1px solid rgba(107,114,128,0.4)",
            color: "#e5e7eb", fontFamily: "'Barlow Condensed', sans-serif",
          }}
        />
        {query && (
          <button
            onClick={() => { setQuery(""); setShowSuggestions(false) }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            style={{ fontSize: 16, lineHeight: 1 }}
          >×</button>
        )}
        {showSuggestions && suggestions.length > 0 && (
          <div
            className="absolute z-50 w-full rounded-lg overflow-hidden mt-1"
            style={{ background: "#1a1c24", border: "1px solid rgba(212,245,60,0.25)" }}
          >
            {suggestions.map(v => (
              <Link
                key={v.id}
                to={`/court/${v.id}`}
                className="flex flex-col px-4 py-2.5 hover:bg-white/5 transition-colors"
                style={{ textDecoration: "none" }}
              >
                <span className="text-sm font-semibold" style={{ color: "#e5e7eb", fontFamily: "'Barlow Condensed', sans-serif" }}>
                  {v.name}
                </span>
                <span className="text-xs" style={{ color: "#6b7280" }}>{v.address}</span>
              </Link>
            ))}
          </div>
        )}
      </div>

      <MultiChip label="Bundesland" options={blOptions} selected={bundesland} onChange={setBundesland} />
      <MultiChip label="Platztyp" options={COURT_TYPE_FILTERS} selected={courtType} onChange={setCourtType} />

      {loading && (
        <p className="text-center py-10 text-gray-500 text-sm">Yara kartiert das Revier …</p>
      )}

      {error && (
        <p className="text-red-400 text-sm py-10 text-center">
          Verbindung fehlgeschlagen. Bitte Seite neu laden.
        </p>
      )}

      {!loading && !error && (
        <>
          <p
            className="mb-2 px-1"
            style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "0.85rem", color: "rgba(212,245,60,0.4)" }}
          >
            {visible.length === 1 ? "1 Anlage" : `${visible.length} Anlagen`}
          </p>

          <div
            className="padelrevier-map rounded-xl overflow-hidden mb-4"
            style={{ height: "70vh", minHeight: 420, border: "1px solid rgba(212,245,60,0.25)" }}
          >
            <MapContainer
              center={[47.7, 14.3]}
              zoom={7}
              scrollWheelZoom
              style={{ height: "100%", width: "100%", background: "#1a1c24" }}
            >
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
                subdomains="abcd"
                maxZoom={20}
              />
              {/* Austria highlighted as a lime shape so it stands out from the
                  dark neighbouring countries. Selected Bundesländer glow brighter.
                  Non-interactive so it never swallows pin clicks. */}
              <GeoJSON
                key={bundesland.slice().sort().join("|")}
                data={BUNDESLAENDER_GEO as GeoJsonObject}
                interactive={false}
                style={(feature) => {
                  const sel = bundesland.length > 0 && bundesland.includes(feature?.properties?.name)
                  return {
                    color: sel ? "rgba(212,245,60,0.8)" : "rgba(212,245,60,0.45)",
                    weight: sel ? 2 : 1,
                    fillColor: "#d4f53c",
                    fillOpacity: sel ? 0.16 : 0.07,
                  }
                }}
              />
              <MapFit selected={bundesland} />
              <MarkerClusterGroup
                chunkedLoading
                maxClusterRadius={30}
                disableClusteringAtZoom={9}
                spiderfyOnMaxZoom
                showCoverageOnHover={false}
              >
                {groups.map(group => {
                  const head = group[0]
                  return (
                    <Marker key={head.id} position={[head.lat, head.lon]} icon={pinIcon}>
                      <Popup>
                        <div style={{ minWidth: 210 }}>
                          <p className="text-xs" style={{ margin: "0 0 10px", color: "#9ca3af" }}>
                            {head.address}
                          </p>
                          {group.map((v, i) => (
                            <div
                              key={v.id}
                              style={i > 0 ? { marginTop: 10, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.1)" } : undefined}
                            >
                              <p className="font-semibold" style={{ margin: "0 0 1px", color: "#fff" }}>
                                {v.name}
                              </p>
                              <p className="text-xs" style={{ margin: "0 0 8px", color: "#9ca3af" }}>
                                {courtTypeLabel(v.court_type)}
                              </p>
                              <div className="flex items-center gap-3" style={{ marginBottom: 8 }}>
                                <button
                                  onClick={() => navigate(`/court/${v.id}`)}
                                  className={POPUP_LINK}
                                  style={{ color: "#d4f53c", background: "none", border: "none", padding: 0, cursor: "pointer" }}
                                >
                                  Details →
                                </button>
                                {(v.public_url || v.booking_url) && (
                                  <a
                                    href={v.public_url || v.booking_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className={POPUP_LINK}
                                    style={{ color: "#9ca3af" }}
                                  >
                                    Zur Anlage →
                                  </a>
                                )}
                              </div>
                              <button
                                onClick={() => checkAvailability(v)}
                                className="w-full rounded text-xs font-bold tracking-wide cursor-pointer"
                                style={{
                                  padding: "6px 10px",
                                  background: "rgba(212,245,60,0.12)",
                                  color: "#d4f53c",
                                  border: "1px solid rgba(212,245,60,0.3)",
                                }}
                              >
                                VERFÜGBARKEIT PRÜFEN
                              </button>
                            </div>
                          ))}
                          <a
                            href={`https://www.google.com/maps/dir/?api=1&destination=${head.lat},${head.lon}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={POPUP_LINK}
                            style={{ display: "inline-block", marginTop: 10, color: "#9ca3af" }}
                          >
                            Route →
                          </a>
                        </div>
                      </Popup>
                    </Marker>
                  )
                })}
              </MarkerClusterGroup>
            </MapContainer>
          </div>

          <div className="mt-8 mb-4 text-sm text-gray-400 space-y-3" style={{ maxWidth: 680, lineHeight: 1.7 }}>
            <h2 className="text-base font-semibold text-gray-200" style={{ fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.02em" }}>
              Padel Courts in Österreich — was du hier findest
            </h2>
            <p>
              PadelYara listet alle bekannten Padel-Anlagen in Österreich — aktuell über 165 Courts
              in 9 Bundesländern. Die Karte zeigt sowohl eigenständige Padel-Zentren als auch
              Courts in bestehenden Tennis- und Sportzentren. Für jeden Standort findest du
              Adresse, Platztyp (indoor oder outdoor), Verfügbarkeit und direkte Buchungslinks.
            </p>
            <p>
              <strong className="text-gray-300">Wien</strong> hat die höchste Dichte an Padel-Courts in Österreich —
              über 20 Anlagen, verteilt über alle Bezirke vom 1. bis zum 22. Bezirk.
              Außerhalb Wiens sind <strong className="text-gray-300">Niederösterreich</strong>,{" "}
              <strong className="text-gray-300">Steiermark</strong> und{" "}
              <strong className="text-gray-300">Oberösterreich</strong> am stärksten vertreten.
            </p>
            <p>
              Die Daten werden laufend aktualisiert. Anlage fehlt?{" "}
              <a href="mailto:hello@padelyara.at" className="underline" style={{ color: "#d4f53c" }}>
                Sag's mir
              </a>{" "}
              Ich trag sie ein.
            </p>
          </div>

          <div className="mt-6 mb-2">
            <p className="text-xs text-gray-500 mb-3 tracking-wide uppercase">Courts nach Stadt</p>
            <div className="flex flex-wrap gap-2">
              {[
                { slug: "wien", label: "Wien" },
                { slug: "graz", label: "Graz" },
                { slug: "linz", label: "Linz" },
                { slug: "salzburg", label: "Salzburg" },
              ].map(({ slug, label }) => (
                <Link
                  key={slug}
                  to={`/padelrevier/${slug}`}
                  className="text-xs px-3 py-1.5 rounded-full"
                  style={{ border: "1px solid rgba(212,245,60,0.25)", color: "#d4f53c", background: "rgba(212,245,60,0.06)" }}
                >
                  Padel Courts {label}
                </Link>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  )
}
