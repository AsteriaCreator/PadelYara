# SEO & Discoverability

## Was live ist

### Meta & Open Graph
- `<title>` — keyword-reich: „Padel Courts in Österreich vergleichen & buchen"
- `<meta description>` — 155 Zeichen, enthält Wien, Österreich, Courts, Preise, CTA
- Open Graph Tags (`og:title`, `og:description`, `og:image`, `og:url`, `og:locale`)
- Twitter Card (`summary_large_image`)
- `og:image` → `/public/og-image-1200x630.png` (1200×630 PNG, dark brand design)
- Canonical URL → `https://padelyara.at/`
- `lang="de"` auf `<html>`

### Strukturierte Daten (JSON-LD)
- **`WebSite` + `SearchAction`** in `index.html` — Google versteht die Suchfunktion
- **`WebApplication`** in `index.html` — kategorisiert die App als Sport-App
- **Dynamische `SportsActivityLocation` ItemList** in `App.tsx` — wird nach jeder Suche in `<head>` injiziert (Venues mit Name, Court-Typ, Preis, Verfügbarkeit)
- **Pro Venue-Detailseite** via `react-helmet-async`: `<title>`, `<meta description>`, `<link rel="canonical">`, `SportsActivityLocation` JSON-LD mit Koordinaten, Adresse, Fotos

### Crawling & Indexierung
- `public/robots.txt` — `Allow: /`, Sitemap-Verweis
- `public/sitemap.xml` — static routes + all 165 `/court/:id` venue URLs (generated at build time from MongoDB via `scripts/generate-sitemap.js`)
- `public/llms.txt` — beschreibt die Site für KI-Assistenten (Gemini, ChatGPT, Perplexity)
- Google Search Console — Domain-Property `padelyara.at` verifiziert, Sitemap eingereicht

---

## Was noch offen ist

### Kurzfristig
- **GSC manual indexing** — request indexing via URL Inspection in Search Console for `/padelrevier`, `/turnierjaeger`, `/about` (one by one, takes a few days)
- **Sentry-Fehler `/api/analytics/search-console`** — fixed (returns `ok: false` instead of HTTP 503)

### Mittelfristig
- **GSC API im Admin Dashboard** — echte Klick/Impressions-Daten direkt sichtbar (braucht Google Service Account + Railway Env-Var)
- **Pre-Rendering** — Venue-Detailseiten als statisches HTML zur Build-Zeit generieren; macht Google-Indexierung schneller und zuverlässiger als JS-Rendering
- **Backlinks** — ÖTV, österreichische Padel-Verbände, Venues direkt kontaktieren

### Langfristig
- **Venue-Fotos** — Venues selbst hochladen lassen (rechtlich sauberste Lösung)
- **Mehr Venue-Daten** — Community-Beiträge vervollständigen Amenity-Felder (Leihschläger, Duschen, Parkplatz, Gastronomie) für reichhaltigere Detailseiten
