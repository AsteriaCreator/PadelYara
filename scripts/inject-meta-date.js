// Injects the current month/year into the meta description in dist/index.html at build time.
// Result: "... Jetzt Verfügbarkeit prüfen und direkt buchen. Stand: Juli 2026"
// This freshness signal in the SERP snippet improves CTR (same tactic as Eversports).
import { readFileSync, writeFileSync } from "fs"
import { join, dirname } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const distIndex = join(__dirname, "..", "dist", "index.html")

const MONTHS_DE = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"]

const now = new Date()
const label = `${MONTHS_DE[now.getMonth()]} ${now.getFullYear()}`

let html
try {
  html = readFileSync(distIndex, "utf8")
} catch {
  console.warn("inject-meta-date: dist/index.html not found, skipping.")
  process.exit(0)
}

const updated = html.replace(
  /(<meta name="description" content="[^"]+?)(\.?)(")/,
  (_, prefix, _dot, close) => `${prefix}. Stand: ${label}${close}`
)

if (updated === html) {
  console.warn("inject-meta-date: meta description not found or already patched.")
} else {
  writeFileSync(distIndex, updated, "utf8")
  console.log(`inject-meta-date: Stand: ${label} injected.`)
}
