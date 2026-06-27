// Generates public/sitemap.xml from MongoDB venues before each build.
// Reads MONGODB_URI from .env (local) or environment (Vercel).
import { MongoClient } from "mongodb"
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

const MONGO_URI = process.env.MONGODB_URI
if (!MONGO_URI) {
  console.warn("⚠️  MONGODB_URI not set — skipping venue URLs in sitemap")
  process.exit(0)
}

const BASE_URL = "https://www.padelyara.at"

const STATIC_URLS = [
  { loc: `${BASE_URL}/`,             changefreq: "daily",   priority: "1.0" },
  { loc: `${BASE_URL}/padelrevier`,  changefreq: "weekly",  priority: "0.8" },
  { loc: `${BASE_URL}/turnierjaeger`,changefreq: "daily",   priority: "0.8" },
  { loc: `${BASE_URL}/about`,        changefreq: "monthly", priority: "0.4" },
]

const client = new MongoClient(MONGO_URI)

try {
  await client.connect()
  const venues = await client
    .db("padel_checker")
    .collection("venues")
    .find({}, { projection: { id: 1, _id: 0 } })
    .toArray()

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
} finally {
  await client.close()
}
