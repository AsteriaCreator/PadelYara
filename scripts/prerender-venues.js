// Runs after `vite build`. For each venue, copies dist/index.html and injects
// venue-specific <title>, <meta description>, <link canonical>, and JSON-LD
// into the <head>, then saves as dist/court/:id/index.html.
//
// Google gets the key SEO signals directly from static HTML without needing
// to execute JavaScript. The React app still hydrates normally for users.
//
// Reads VITE_API_URL from .env (local) or environment (Vercel).
// Falls back gracefully if the backend is unreachable.

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "fs"
import { join, dirname } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, "..")

// Load .env manually
try {
  const env = readFileSync(join(ROOT, ".env"), "utf8")
  for (const line of env.split("\n")) {
    const [k, ...v] = line.split("=")
    if (k && v.length && !process.env[k.trim()]) {
      process.env[k.trim()] = v.join("=").trim().replace(/^["']|["']$/g, "")
    }
  }
} catch { /* no .env — use environment directly */ }

const API_BASE = (process.env.VITE_API_URL ?? "https://neo-padel-checker-backend-production.up.railway.app").replace(/\/$/, "")
const BASE_URL = "https://www.padelyara.at"
const DIST = join(ROOT, "dist")

if (!existsSync(join(DIST, "index.html"))) {
  console.warn("⚠️  dist/index.html not found — skipping pre-render")
  process.exit(0)
}

const shell = readFileSync(join(DIST, "index.html"), "utf8")

// Fetch all venues from the backend (includes name, city, address etc.)
let venues
try {
  const res = await fetch(`${API_BASE}/api/venues`, { signal: AbortSignal.timeout(20_000) })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  venues = data.venues ?? data
} catch (err) {
  console.warn(`⚠️  Could not fetch venues from ${API_BASE} — skipping pre-render (${err.message})`)
  process.exit(0)
}

// Pre-render static pages (SPA routes that Google struggles to index)
const STATIC_PAGES = [
  {
    path: "padelrevier",
    title: "Padelrevier — Alle Padel-Anlagen in Österreich auf der Karte",
    desc: "165 Padel-Anlagen in Österreich auf einer interaktiven Karte. Finde Courts in Wien, Graz, Linz, Salzburg und allen Bundesländern.",
    canonical: `${BASE_URL}/padelrevier`,
  },
  {
    path: "turnierjaeger",
    title: "Turnierjäger — Padel-Turniere in Österreich",
    desc: "Alle Padel-Turniere in Österreich auf einen Blick. Filterbar nach Bundesland, Kategorie und Datum. Über 700 Turniere gelistet.",
    canonical: `${BASE_URL}/turnierjaeger`,
  },
  {
    path: "padelrevier/wien",
    title: "Padel Courts Wien — alle Anlagen | PadelYara",
    desc: "Alle Padel-Anlagen in Wien. 18 Standorte, über 100 Courts — indoor und outdoor, vom 2. bis zum 22. Bezirk. Adresse, Öffnungszeiten und Verfügbarkeit direkt prüfen.",
    canonical: `${BASE_URL}/padelrevier/wien`,
  },
  {
    path: "padelrevier/graz",
    title: "Padel Courts Graz — alle Anlagen in der Steiermark | PadelYara",
    desc: "Alle Padel-Anlagen in Graz und der Steiermark. PadelZone Puntigam, PadelZone Ragnitz und weitere — Verfügbarkeit und Preise direkt prüfen.",
    canonical: `${BASE_URL}/padelrevier/graz`,
  },
  {
    path: "padelrevier/linz",
    title: "Padel Courts Linz — alle Anlagen in Oberösterreich | PadelYara",
    desc: "Alle Padel-Anlagen in Linz und Oberösterreich. PadelBase Linz, Pichling, Gunskirchen, Marchtrenk, Wels — Verfügbarkeit auf einen Blick.",
    canonical: `${BASE_URL}/padelrevier/linz`,
  },
  {
    path: "padelrevier/salzburg",
    title: "Padel Courts Salzburg — alle Anlagen | PadelYara",
    desc: "Alle Padel-Anlagen in Salzburg. PadelBase CUPRA Arena und weitere Standorte — Verfügbarkeit und Preise direkt prüfen.",
    canonical: `${BASE_URL}/padelrevier/salzburg`,
  },
]

for (const page of STATIC_PAGES) {
  const inject = `
  <title>${esc(page.title)}</title>
  <meta name="description" content="${esc(page.desc)}" />
  <link rel="canonical" href="${page.canonical}" />
  <meta property="og:title" content="${esc(page.title)}" />
  <meta property="og:description" content="${esc(page.desc)}" />
  <meta property="og:url" content="${page.canonical}" />`
  const html = shell.replace("</head>", `${inject}\n</head>`)
  const dir = join(DIST, page.path)
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, "index.html"), html, "utf8")
  console.log(`✅ Pre-rendered /${page.path}`)
}

console.log(`Pre-rendering ${venues.length} venue pages…`)

let ok = 0
let failed = 0

for (const d of venues) {
  const id = d.id
  try {
    if (!id) { failed++; continue }

    const title = `${d.name}${d.city ? " · " + d.city : ""} — PadelYara`
    const descParts = [
      d.name,
      d.city ? `in ${d.city}` : null,
      d.address ?? null,
      d.court_type === "indoor" ? "Indoor Padel" : d.court_type === "outdoor" ? "Outdoor Padel" : "Indoor & Outdoor Padel",
    ].filter(Boolean)
    const desc = descParts.join(" · ").slice(0, 160)
    const canonical = `${BASE_URL}/court/${id}`

    const ld = {
      "@context": "https://schema.org",
      "@type": "SportsActivityLocation",
      "name": d.name,
      "url": canonical,
      ...(d.address ? { "address": { "@type": "PostalAddress", "streetAddress": d.address, ...(d.city ? { "addressLocality": d.city } : {}), "addressCountry": "AT" } } : {}),
      ...(d.lat && d.lon ? { "geo": { "@type": "GeoCoordinates", "latitude": d.lat, "longitude": d.lon } } : {}),
      ...(d.photos?.length ? { "image": d.photos } : {}),
      ...(d.booking_url ? { "url": d.booking_url } : {}),
    }

    const inject = `
  <title>${esc(title)}</title>
  <meta name="description" content="${esc(desc)}" />
  <link rel="canonical" href="${canonical}" />
  <meta property="og:title" content="${esc(title)}" />
  <meta property="og:description" content="${esc(desc)}" />
  <meta property="og:url" content="${canonical}" />
  <script type="application/ld+json">${JSON.stringify(ld)}</script>`

    const html = shell.replace("</head>", `${inject}\n</head>`)

    const dir = join(DIST, "court", id)
    mkdirSync(dir, { recursive: true })
    writeFileSync(join(dir, "index.html"), html, "utf8")
    ok++
  } catch {
    failed++
  }
}

console.log(`✅ Pre-rendered ${ok} venue pages${failed > 0 ? ` (${failed} skipped)` : ""}`)

function esc(str) {
  return str.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}
