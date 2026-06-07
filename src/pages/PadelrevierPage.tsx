import { useEffect, useMemo, useState } from "react"
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet"
import MarkerClusterGroup from "react-leaflet-cluster"
import L from "leaflet"
import { useNavigate } from "react-router-dom"
import "leaflet/dist/leaflet.css"
import "leaflet.markercluster/dist/MarkerCluster.css"
import "leaflet.markercluster/dist/MarkerCluster.Default.css"
import { fetchVenues } from "../api"
import type { MapVenue } from "../types"
import { bundeslandFromAddress } from "../data/plz"

const BUNDESLAENDER = [
  "Wien", "Niederösterreich", "Oberösterreich", "Steiermark",
  "Tirol", "Kärnten", "Salzburg", "Vorarlberg", "Burgenland",
]

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
    color: active ? "#d4f53c" : "#6b7280",
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

  const visible = useMemo(() => venues.filter(v => {
    const blOk = bundesland.length === 0 || bundesland.includes(bundeslandFromAddress(v.address))
    // A both-courts venue matches the Indoor chip and the Outdoor chip.
    const ctOk = courtType.length === 0
      || courtType.includes(v.court_type)
      || (v.court_type === "indoor+outdoor" && (courtType.includes("indoor") || courtType.includes("outdoor")))
    return blOk && ctOk
  }), [venues, bundesland, courtType])

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

  return (
    <>
      <p
        className="text-base italic mb-4 mt-2"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c" }}
      >
        Jeder Padel-Court in Österreich. Mein Revier. Such dir einen aus.
      </p>

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
            className="rounded-xl overflow-hidden border border-gray-800 mb-4"
            style={{ height: "70vh", minHeight: 420 }}
          >
            <MapContainer
              center={[47.7, 14.3]}
              zoom={7}
              scrollWheelZoom
              style={{ height: "100%", width: "100%", background: "#080810" }}
            >
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
                subdomains="abcd"
                maxZoom={20}
              />
              <MarkerClusterGroup chunkedLoading>
                {visible.map(v => (
                  <Marker key={v.id} position={[v.lat, v.lon]} icon={pinIcon}>
                    <Popup>
                      <div style={{ minWidth: 200 }}>
                        <p className="font-semibold" style={{ margin: "0 0 4px", color: "#fff" }}>
                          {v.name}
                        </p>
                        <p className="text-xs" style={{ margin: "0 0 2px", color: "#9ca3af" }}>
                          {v.address}
                        </p>
                        <p className="text-xs" style={{ margin: "0 0 10px", color: "#9ca3af" }}>
                          {courtTypeLabel(v.court_type)}
                        </p>
                        <div className="flex items-center gap-3" style={{ marginBottom: 8 }}>
                          {(v.public_url || v.booking_url) && (
                            <a
                              href={v.public_url || v.booking_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={POPUP_LINK}
                              style={{ color: "#d4f53c" }}
                            >
                              Zur Anlage →
                            </a>
                          )}
                          <a
                            href={`https://www.google.com/maps/dir/?api=1&destination=${v.lat},${v.lon}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={POPUP_LINK}
                            style={{ color: "#9ca3af" }}
                          >
                            Route →
                          </a>
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
                    </Popup>
                  </Marker>
                ))}
              </MarkerClusterGroup>
            </MapContainer>
          </div>
        </>
      )}
    </>
  )
}
