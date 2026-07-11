// Runs after prerender-venues.js. Checks that every pre-rendered page is in the sitemap.
// Fails the build with a clear error if any are missing.
import { readFileSync, readdirSync, existsSync } from "fs"
import { join, dirname } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, "..")
const DIST = join(ROOT, "dist")
const SITEMAP = join(ROOT, "public", "sitemap.xml")

if (!existsSync(SITEMAP)) {
  console.warn("check-sitemap-coverage: sitemap.xml not found, skipping.")
  process.exit(0)
}
if (!existsSync(DIST)) {
  console.warn("check-sitemap-coverage: dist/ not found, skipping.")
  process.exit(0)
}

const sitemap = readFileSync(SITEMAP, "utf8")

// Collect all index.html files under dist/ (excluding the root shell)
function findPrerendered(dir, base = "") {
  const results = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      results.push(...findPrerendered(join(dir, entry.name), `${base}/${entry.name}`))
    } else if (entry.name === "index.html" && base !== "") {
      results.push(base)
    }
  }
  return results
}

const prerendered = findPrerendered(DIST)
const missing = prerendered.filter(path => !sitemap.includes(path))

if (missing.length === 0) {
  console.log(`✅ sitemap coverage OK — all ${prerendered.length} pre-rendered pages are listed.`)
  process.exit(0)
}

console.error(`\n❌ sitemap-coverage: ${missing.length} pre-rendered page(s) are missing from sitemap.xml:\n`)
for (const p of missing) {
  console.error(`   ${p}`)
}
console.error(`\nAdd these to STATIC_URLS in scripts/generate-sitemap.js and rebuild.\n`)
process.exit(1)
