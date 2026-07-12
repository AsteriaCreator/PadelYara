// Generates public/sitemap.xml from the backend venues API before each build.
// Uses the SAME source as scripts/prerender-venues.js (VITE_API_URL /api/venues)
// so the sitemap and the pre-rendered /court/:id pages can never drift apart —
// check-sitemap-coverage.js enforces that they match. Reads VITE_API_URL from
// .env (local) or environment (Vercel); falls back to the Railway backend.
import { writeFileSync, readFileSync } from "fs"
import { join, dirname } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, "..")

// Load .env manually (no dotenv dependency needed)
try {
  const env = readFileSync(join(ROOT, ".env"), "utf8")
  for (const line of env.split("\n")) {
    const [k, ...v] = line.split("=")
    if (k && v.length && !process.env[k.trim()]) {
      process.env[k.trim()] = v.join("=").trim().replace(/^["']|["']$/g, "")
    }
  }
} catch { /* no .env file — use environment directly */ }

const API_BASE = (process.env.VITE_API_URL ?? "https://neo-padel-checker-backend-production.up.railway.app").replace(/\/$/, "")
const BASE_URL = "https://www.padelyara.at"

const STATIC_URLS = [
  { loc: `${BASE_URL}/`,             changefreq: "daily",   priority: "1.0" },
  { loc: `${BASE_URL}/padelrevier`,          changefreq: "weekly",  priority: "0.8" },
  { loc: `${BASE_URL}/padelrevier/wien`,     changefreq: "weekly",  priority: "0.7" },
  { loc: `${BASE_URL}/padelrevier/graz`,     changefreq: "weekly",  priority: "0.7" },
  { loc: `${BASE_URL}/padelrevier/linz`,     changefreq: "weekly",  priority: "0.7" },
  { loc: `${BASE_URL}/padelrevier/salzburg`, changefreq: "weekly",  priority: "0.7" },
  { loc: `${BASE_URL}/turnierjaeger`,changefreq: "daily",   priority: "0.8" },
  { loc: `${BASE_URL}/dein-match`,  changefreq: "daily",   priority: "0.8" },
  { loc: `${BASE_URL}/about`,        changefreq: "monthly", priority: "0.4" },
]

let venues
try {
  const res = await fetch(`${API_BASE}/api/venues`, { signal: AbortSignal.timeout(20_000) })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  venues = data.venues ?? data
} catch (err) {
  console.warn(`⚠️  Could not fetch venues from ${API_BASE} — skipping venue URLs in sitemap (${err.message})`)
  process.exit(0)
}

const venueUrls = venues
  .filter(v => v.id)
  .map(v => ({
    loc: `${BASE_URL}/court/${v.id}`,
    changefreq: "weekly",
    priority: "0.6",
  }))

const allUrls = [...STATIC_URLS, ...venueUrls]

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${allUrls.map(u => `  <url>
    <loc>${u.loc}</loc>
    <changefreq>${u.changefreq}</changefreq>
    <priority>${u.priority}</priority>
  </url>`).join("\n")}
</urlset>`

writeFileSync(join(ROOT, "public", "sitemap.xml"), xml, "utf8")
console.log(`✅ sitemap.xml generated — ${allUrls.length} URLs (${venueUrls.length} venues)`)
