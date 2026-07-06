import { Helmet } from "react-helmet-async"
import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { fetchVenues } from "../api"
import type { MapVenue } from "../types"
import { bundeslandFromAddress } from "../data/plz"

const COURT_TYPE_LABEL: Record<string, string> = {
  indoor: "Indoor",
  outdoor: "Outdoor",
  "indoor+outdoor": "Indoor & Outdoor",
  indoor_outdoor: "Indoor & Outdoor",
}

interface CityConfig {
  displayName: string
  bundesland: string
  title: string
  description: string
  h1: string
  intro: string
  footerHeading: string
  footerCopy: string[]
}

const CITY_CONFIG: Record<string, CityConfig> = {
  wien: {
    displayName: "Wien",
    bundesland: "Wien",
    title: "Padel Courts Wien — alle Anlagen | PadelYara",
    description: "Alle Padel-Anlagen in Wien. 18 Standorte, über 100 Courts — indoor und outdoor, vom 2. bis zum 22. Bezirk. Adresse, Öffnungszeiten und Verfügbarkeit direkt prüfen.",
    h1: "Padel Courts Wien",
    intro: "18 Anlagen. Über 100 Courts. Wien hat die dichteste Padel-Abdeckung in Österreich — und trotzdem findet man keinen freien Court an einem Freitagabend. Nicht ohne mich.",
    footerHeading: "Padel in Wien — was du wissen musst",
    footerCopy: [
      "Wien hat Padel spät entdeckt, holt aber auf. Die meisten Anlagen stehen in den Außenbezirken — 21., 22. und 23. Bezirk — wo Platz für große Hallen und Outdooranlagen vorhanden ist. Im Innenstadtbereich gibt es wenig; Ausnahmen sind PadelDome Erdberg (3. Bezirk) und PadelUnion im Prater (2. Bezirk).",
      "Indoor-Courts überwiegen: PadelDome Wien allein betreibt vier Standorte mit insgesamt über 40 Courts. Outdoor-Courts öffnen je nach Anlage ab März oder April — und sind im Sommer die bessere Wahl, wenn das Wetter passt.",
      "Buchungen laufen über Eversports oder eTennis, je nach Anlage. PadelYara prüft die Verfügbarkeit auf allen Plattformen gleichzeitig.",
    ],
  },
  graz: {
    displayName: "Graz",
    bundesland: "Steiermark",
    title: "Padel Courts Graz — alle Anlagen in der Steiermark | PadelYara",
    description: "Alle Padel-Anlagen in Graz und der Steiermark. Indoor und outdoor — Standorte, Öffnungszeiten und Verfügbarkeit auf einen Blick.",
    h1: "Padel Courts Graz",
    intro: "Graz wächst. Die Padel-Szene auch. Alle Anlagen in Graz und Umgebung — auf einen Blick.",
    footerHeading: "Padel in Graz — was du wissen musst",
    footerCopy: [
      "Graz hat in den letzten Jahren mehrere neue Padel-Anlagen bekommen — darunter PadelZone Graz Racket Sport Center in Ragnitz und PadelZone Graz Puntigam im Süden der Stadt. Beide bieten kostenlose Parkplätze vor Ort.",
      "Buchungen laufen über Eversports. PadelYara zeigt dir Verfügbarkeit auf allen Grazer Anlagen gleichzeitig.",
    ],
  },
  linz: {
    displayName: "Linz",
    bundesland: "Oberösterreich",
    title: "Padel Courts Linz — alle Anlagen in Oberösterreich | PadelYara",
    description: "Alle Padel-Anlagen in Linz und Oberösterreich. Standorte, Öffnungszeiten und Verfügbarkeit direkt prüfen.",
    h1: "Padel Courts Linz",
    intro: "Linz, Wels, Marchtrenk — Oberösterreich hat mehr Padel-Courts als du denkst. Alle auf einem Blick.",
    footerHeading: "Padel in Oberösterreich — was du wissen musst",
    footerCopy: [
      "PadelBase betreibt mehrere Standorte in Linz (Halle, Pichling, Kleinmünchen) und Umgebung — Wels, Marchtrenk, Gunskirchen, Rohrbach-Berg. Dazu PadelZone Linz in der Ragnitzstraße. Alle Anlagen bieten kostenlose Parkplätze.",
      "Buchungen laufen über eTennis oder Eversports. PadelYara prüft Verfügbarkeit auf allen Plattformen gleichzeitig.",
    ],
  },
  salzburg: {
    displayName: "Salzburg",
    bundesland: "Salzburg",
    title: "Padel Courts Salzburg — alle Anlagen | PadelYara",
    description: "Alle Padel-Anlagen in Salzburg. Standorte, Öffnungszeiten und Verfügbarkeit direkt prüfen.",
    h1: "Padel Courts Salzburg",
    intro: "Salzburg hat wenige Padel-Courts. Die, die es gibt, sind hier.",
    footerHeading: "Padel in Salzburg — was du wissen musst",
    footerCopy: [
      "Salzburg ist im Vergleich zu Wien oder der Steiermark noch dünn mit Padel-Courts versorgt. PadelBase CUPRA Arena in der Wasserfeldstraße ist die bekannteste Anlage. Kostenlose Parkplätze vorhanden.",
    ],
  },
}

export default function PadelrevierCityPage() {
  const { city } = useParams<{ city: string }>()
  const navigate = useNavigate()
  const config = city ? CITY_CONFIG[city.toLowerCase()] : undefined

  const [venues, setVenues] = useState<MapVenue[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!config) return
    fetchVenues()
      .then(setVenues)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [config])

  const cityVenues = useMemo(() =>
    venues.filter(v => config && bundeslandFromAddress(v.address) === config.bundesland),
    [venues, config]
  )

  if (!config) {
    navigate("/padelrevier", { replace: true })
    return null
  }

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": config.h1,
    "description": config.description,
    "url": `https://www.padelyara.at/padelrevier/${city}`,
    "provider": { "@type": "Organization", "name": "PadelYara", "url": "https://www.padelyara.at" },
    "about": {
      "@type": "SportsActivityLocation",
      "sport": "Padel",
      "addressLocality": config.displayName,
      "addressCountry": "AT",
    },
    ...(cityVenues.length > 0 && {
      "hasPart": cityVenues.map(v => ({
        "@type": "SportsActivityLocation",
        "name": v.name,
        "address": v.address,
        "sport": "Padel",
        "url": `https://www.padelyara.at/court/${v.id}`,
      })),
    }),
  }

  return (
    <>
      <Helmet>
        <title>{config.title}</title>
        <meta name="description" content={config.description} />
        <link rel="canonical" href={`https://www.padelyara.at/padelrevier/${city}`} />
        <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      </Helmet>

      <p className="text-xs text-gray-500 mb-3">
        <Link to="/padelrevier" style={{ color: "#d4f53c" }}>← Padelrevier</Link>
        {" / "}{config.displayName}
      </p>

      <h1
        className="text-xl font-bold mb-2"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#fff", letterSpacing: "0.01em" }}
      >
        {config.h1}
      </h1>
      <p
        className="text-base italic mb-6"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c" }}
      >
        {config.intro}
      </p>

      {loading && (
        <p className="text-gray-500 text-sm py-8 text-center">Yara kartiert …</p>
      )}

      {!loading && (
        <>
          <p
            className="mb-3 px-1"
            style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "0.85rem", color: "rgba(212,245,60,0.4)" }}
          >
            {cityVenues.length === 1 ? "1 Anlage" : `${cityVenues.length} Anlagen`}
          </p>

          <div className="space-y-2 mb-6">
            {cityVenues.map(v => (
              <Link
                key={v.id}
                to={`/court/${v.id}`}
                className="flex items-start justify-between gap-3 rounded-lg px-4 py-3 group"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(212,245,60,0.12)" }}
              >
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-white group-hover:text-[#d4f53c] transition-colors truncate">
                    {v.name}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">{v.address}</p>
                </div>
                <span className="text-xs text-gray-600 mt-0.5 shrink-0">
                  {COURT_TYPE_LABEL[v.court_type] ?? v.court_type}
                </span>
              </Link>
            ))}
          </div>

          <Link
            to="/padelrevier"
            className="inline-block text-xs font-bold tracking-wide rounded px-4 py-2 mb-8"
            style={{ background: "rgba(212,245,60,0.1)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.25)" }}
          >
            → Alle Anlagen auf der Karte
          </Link>

          <div className="text-sm text-gray-400 space-y-3 mb-4" style={{ maxWidth: 680, lineHeight: 1.7 }}>
            <h2
              className="text-base font-semibold text-gray-200"
              style={{ fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.02em" }}
            >
              {config.footerHeading}
            </h2>
            {config.footerCopy.map((para, i) => (
              <p key={i}>{para}</p>
            ))}
            <p>
              Anlage fehlt?{" "}
              <a href="mailto:hello@padelyara.at" className="underline" style={{ color: "#d4f53c" }}>
                Sag's mir
              </a>{" "}
              Ich trag sie ein.
            </p>
          </div>
        </>
      )}
    </>
  )
}
