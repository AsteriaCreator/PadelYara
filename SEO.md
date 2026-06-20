# SEO & Discoverability

## What's live

### Meta & Open Graph
- `<title>` — keyword-rich: "Padel Courts in Österreich vergleichen & buchen"
- `<meta description>` — 155 chars, includes Wien, Österreich, Courts, Preise, CTA
- Open Graph tags (`og:title`, `og:description`, `og:image`, `og:url`, `og:locale`)
- Twitter Card (`summary_large_image`)
- `og:image` → `public/og-image-1200x630.png` (1200×630 PNG, dark brand design)
- Canonical URL → `https://padelyara.at/`
- `lang="de"` on `<html>`

### Per-page titles & descriptions (react-helmet-async)
Every route has its own `<title>`, `<meta name="description">`, and `<link rel="canonical">`:
- `/` — handled via `index.html` static tags
- `/about` — "Über PadelYara — Österreichs Padel Court Aggregator"
- `/padelrevier` — "Padelrevier — Padel Anlagen in Österreich auf der Karte"
- `/turnierjaeger` — "Turnierjäger — Padel Turniere in Österreich"
- `/court/:id` — dynamic per-venue title + description via CourtDetailPage
- `/impressum` — title only, `noindex`
- `/datenschutz` — title only, `noindex`

### Structured data (JSON-LD)
- **`WebSite` + `SearchAction`** in `index.html` — Google understands the search function
- **`WebApplication`** in `index.html` — categorises app as sports app
- **Dynamic `SportsActivityLocation` ItemList** in `App.tsx` — injected into `<head>` after each search (venues with name, court type, price, availability)
- **Per venue detail page** via react-helmet-async: `SportsActivityLocation` JSON-LD with coordinates, address, photos

### Crawling & indexing
- `public/robots.txt` — `Allow: /`, sitemap reference
- `public/sitemap.xml` — 4 static routes + all venue `/court/:id` URLs, generated at build time from MongoDB via `scripts/generate-sitemap.js` (runs before `tsc && vite build`)
- `public/llms.txt` — describes the site for AI assistants (Gemini, ChatGPT, Perplexity)
- Google Search Console — domain property `padelyara.at` verified, sitemap submitted, manual indexing requested for `/about`, `/padelrevier`, `/turnierjaeger`
- `/impressum` — real page at `padelyara.at/impressum` (crawlable, noindex); provides authorship/trust signal (name, address, legal info)

### Performance
- Code-split by route via `React.lazy` + `Suspense` — main bundle reduced from ~607kB to ~297kB; Leaflet (240kB) only loads on `/padelrevier`

### GSC Admin Dashboard
- `GOOGLE_SERVICE_ACCOUNT_JSON` set on Railway ✅
- `/api/analytics/search-console` endpoint live — shows clicks, impressions, top queries, top countries in admin dashboard

---

## Open items

### Short term
- **Backlinks** — contact ÖTV, Austrian padel clubs, venues directly; getting linked from authoritative AT sports sites is the highest-leverage SEO action remaining

### Medium term
- **Pre-rendering** — generate static HTML for venue detail pages at build time; speeds up Google indexing but low priority since Google renders JS anyway

### Long term
- **Venue photo uploads** — venue detail pages already show photos from the `photos` field; long-term goal is letting venues upload their own directly (currently photos are added manually to MongoDB)
- **More venue data** — community contributions to fill amenity fields (rental rackets, showers, parking, food) for richer detail pages
