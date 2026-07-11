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
- `public/robots.txt` — explicit `Allow: /` entries for GPTBot, ChatGPT-User, PerplexityBot, ClaudeBot, anthropic-ai, Google-Extended, Bingbot, plus sitemap reference
- `public/sitemap.xml` — generated at build time from MongoDB via `scripts/generate-sitemap.js` (runs before `tsc && vite build`); includes `/`, `/padelrevier`, `/padelrevier/wien|graz|linz|salzburg`, `/turnierjaeger`, `/dein-match`, `/about`, and every venue `/court/:id`
- `scripts/check-sitemap-coverage.js` runs at the end of `npm run build` — fails the build if a pre-rendered page is missing from the sitemap. Safety net only; the real discipline is adding sitemap + prerender entries the moment a new route is written (see `CLAUDE.md` → "New indexable page rule")
- **Pre-rendering** (`scripts/prerender-venues.js`, runs after `vite build`) — generates static `index.html` shells with page-specific title/description/canonical/JSON-LD for: every venue `/court/:id`, `/padelrevier`, `/turnierjaeger`, and all 4 city pages. Fixes "crawled — currently not indexed" for SPA routes since Google gets real HTML without needing to execute JS
- `scripts/inject-meta-date.js` — injects "Stand: [Monat Jahr]" into the homepage meta description at build time (freshness signal in the SERP snippet, same tactic Eversports uses)
- `public/llms.txt` — expanded to 8 structured Q&A blocks with real numbers (165 venues, 3 platforms, founder attribution) for AI assistants (ChatGPT, Perplexity, Claude, Gemini)
- `FAQPage` JSON-LD added to `index.html` (6 questions) — eligible for AI Overview snippet extraction
- Google Search Console — domain property `padelyara.at` verified, sitemap submitted, manual indexing requested for all major routes; canonical-duplicate issue on 5 venue pages fixed via pre-rendering (validation submitted 2026-07-06)
- `/impressum` — real page at `padelyara.at/impressum` (crawlable, noindex); provides authorship/trust signal (name, address, legal info)
- Author attribution added to `/about` — short in-voice footnote naming Cornelia Mayer as the human behind Yara (E-E-A-T signal)
- Homepage now shows live stats (165 Anlagen · 309 Courts · 728 Turniere) in the empty state — both a UX and AI-citation-friendly signal

### Performance
- Code-split by route via `React.lazy` + `Suspense` — main bundle reduced from ~607kB to ~297kB; Leaflet (240kB) only loads on `/padelrevier`

### GSC Admin Dashboard
- `GOOGLE_SERVICE_ACCOUNT_JSON` set on Railway ✅
- `/api/analytics/search-console` endpoint live — shows clicks, impressions, top queries, top countries in admin dashboard

### Real ranking check (2026-07-06)
Checked actual Google results (not just GSC):
- **"padelyara"** → PadelYara ranks #1, plus 2 more results on page 1. Brand search works.
- **"padel court wien finden"** / **"padel buchen österreich"** → PadelYara does **not** appear on page 1. Eversports, Padelzone, Padeldome, padel-austria.at dominate — all either much older domains or the venues themselves.
- GSC top queries are almost entirely venue-branded ("padel puntigam", "utc fischlham", "padelbase gunskirchen") with high impressions but ~0 clicks at position ~10. People searching a specific venue by name want that venue directly, not an aggregator — this traffic was never going to convert well.
- Conclusion: technical SEO is in good shape; the gap is domain authority for generic queries, which only backlinks fix — not more on-page work.

---

## Open items

### Short term
- **Backlinks** — contact ÖTV, Austrian padel clubs, venues directly; getting linked from authoritative AT sports sites is the highest-leverage SEO action remaining. Confirmed as the real bottleneck by the 2026-07-06 ranking check above, not a technical gap.

### Long term
- **Venue photo uploads** — venue detail pages already show photos from the `photos` field; long-term goal is letting venues upload their own directly (currently photos are added manually to MongoDB)
- **More venue data** — community contributions to fill amenity fields (rental rackets, showers, parking, food) for richer detail pages
