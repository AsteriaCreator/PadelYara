# PadelYara — Product Marketing Context

Last updated: 2026-05-30

---

## Brand Name: PadelYara

### Domain
- padelyara.com ✅ available (confirmed 2026-05-29)
- padelyara.at ✅ available (confirmed 2026-05-29)

### Why This Name

**Personal connection:**
The founder has four cats. One of them is named Yara. The name came from a genuine personal place — not from a naming exercise.

**Mythological depth (three independent cultures, same direction):**
- **Persian:** *yārā* = "strength," "courage"; *yār* = "companion, friend, ally"
- **Arabic:** "small butterfly," "beloved," "dear friend" — widely used across the Levant and Gulf
- **Brazilian/Tupi-Guarani mythology:** Yara (Iara) was a warrior daughter who outshone her brothers in combat. Her father, to preserve male dominance, had her thrown into a river. She returned as an immortal water spirit — the most feared and beloved figure in the water. A woman who overcame being pushed down by a male-dominated world and became more powerful.
- **Turkish mythology:** Yara is a sea fairy known for mystical allure

**The Freya connection (hidden layer):**
The founder initially considered PadelFreya. Freya is the Norse goddess of war, love, and magic — and critically, **the goddess of cats**. Her chariot is pulled by two giant cats (Bygul and Trjegul). Cats were sacred to her. PadelYara carries the Freya energy — the cat lady goddess vibe — without using the name directly. It is a secret layer that exists for those who know.

**Note on "Padel" vs "Yara" typography:**
Written as `PadelYara` (CamelCase) in body text and URLs. Written as `PADELYARA` in logo/headline contexts. The capital Y visually separates Padel from Yara, reinforcing that Yara is a name within the brand name.

**Positioning relevance:**
The Brazilian mythology story is a founding narrative: a woman building a padel platform to challenge male-dominated padel sites, who was "thrown in the river" by the status quo, and came back stronger. This does not need to be stated explicitly — it is the underlying spirit.

**Pronunciation:**
German: YAH-rah (rhymes with Sara). Fully natural in German-speaking Austria.

**Gender strategy:**
Female energy is present but subtle. The name does not exclude men. Gender is a subtext, not a headline — used where it fits, not forced.

---

## Brand Identity

### Slogan
**"Dein Match. Dein Moment."**
German-first. Emotional, personal, scales across all three product phases (courts, stats, merch). Confirmed and final.

### Logo
- **Symbol:** Padel racket in teardrop/location-pin shape with cat/fox face inside. Ears break outside the racket frame. Hidden Y in the negative space between eyes and nose. Hole pattern 3-2-1 at top. Two-stripe handle grip.
- **Style:** Flat, minimal, black and white. Bold lines. Works at 32px and 30cm.
- **Created with:** Nanobanana AI (commercial use allowed per their terms)

### Typography
- **Wordmark:** Cinzel (Google Fonts, variable font)
  - "Padel" → Cinzel Regular (weight 400)
  - "Yara" → Cinzel SemiBold (weight 600)
- **Tagline:** Cinzel SemiBold (weight 600), smaller size, grey (#cccccc on dark / #555555 on light)

### Colors
- **Primary:** #111111 (near black) — backgrounds, logo on light
- **Primary light:** #ffffff (white) — logo on dark, text on dark backgrounds
- **Accent:** #cccccc (silver/light grey) — tagline on dark backgrounds
- **Accent dark:** #555555 (mid grey) — tagline on light backgrounds

### Brand Files
All files in `brand/` folder in the project root:
- `brand/logo/logo.svg` — original (black background built in)
- `brand/logo/logo-transparent-black.svg` — for light backgrounds
- `brand/logo/logo-transparent-white.svg` — for dark backgrounds
- `brand/lockups/lockup-horizontal-dark.svg` — website, social
- `brand/lockups/lockup-horizontal-light.svg` — documents, print
- `brand/lockups/lockup-vertical-dark.svg` — app, poster
- `brand/lockups/lockup-vertical-light.svg` — business card, merch

### Next brand step
Convert text to paths in Inkscape (Text → Convert to Path) on all lockup files for full portability without font dependency.

---

## The Product

### Current State (MVP live)
A court availability aggregator for padel players in Austria. Solves the fragmentation problem: in Austria, Playtomic is not used. Each padel venue uses a separate booking platform (primarily eTennis or Eversports). To find an available court, a player currently has to check each venue individually. PadelYara aggregates all of them into one search.

**Core user flow:**
1. Enter location
2. Set radius
3. Choose date + time
4. See all available courts across all providers
5. Click through to book on the original platform

**Technical stack:** React/Vite/TypeScript frontend on Vercel, FastAPI backend on Railway (single service — eTennis + Eversports scraping combined).

### Product Roadmap (in order)
1. **Court finder** (live) — availability aggregator, Vienna region first, then all Austria
2. **Tournament stats analyzer** — personal padel stats from tournaments, insights for future play
3. **Merch webshop** — print-on-demand padel lifestyle products (shirts, socks, accessories) with original designs created with AI assistance

### Business Model
Bootstrapped. No external funding. Income is planned to grow with the product but is not intended to become the founder's primary income stream. The padel market in Austria is not considered large enough for that. Income streams will emerge organically as user base grows.

---

## Founder Profile

- Female, passionate padel player
- Based in Bad Vöslau, plays in Bad Vöslau / Wr. Neustadt region and south of Vienna
- Tournaments across Vienna
- Four cats (one named Yara)
- Builds and codes the product herself
- Discovered the court-finding pain point firsthand as a player

---

## Market Context

### Global Padel Growth
- 35M+ players worldwide, 16% YoY growth in registered members
- Europe is the heartland: Spain, Sweden, Italy, France, Portugal most established
- Austria added ~300 courts recently — one of the fastest-growing DACH markets
- Switzerland adding 400 courts; Germany growing more slowly (875 courts total)
- Europe padel market: USD 146M in 2026, projected USD 225M by 2032 (CAGR ~7.5%)
- DACH is early-adoption phase — first-mover digital tools have a real window now

### Austrian Padel Specifically
- Playtomic is **not used in Austria** — this is the critical local insight
- Main booking platforms: **eTennis** and **Eversports**
- Each venue is on one platform only — players must check venues individually
- No aggregator exists for the Austrian market
- The problem is real and felt by players

---

## Target Audience

### Primary Persona
- Age 30–54 (core: 35–45)
- Urban, Vienna region and surrounding areas
- High disposable income, health/wellness oriented
- Tech-comfortable professional — already uses apps to organize life
- Plays 1–3x per week; often makes spontaneous or short-notice decisions ("can we play tonight?")
- Frustrated by juggling multiple booking apps/websites
- Likely in a padel WhatsApp group with friends
- German-speaking primary, but some English speakers

### Gender
~60% male, ~40% female — unusually high female participation for a racket sport. Do not design only for men.

### Key Pain Point
Platform fragmentation. eTennis and Eversports are separate. Finding a free court at a convenient time requires manual cross-checking of multiple sites. PadelYara solves this in one search.

### Behavioral Pattern
Decisions often made same-day or 1–2 days ahead. Speed and clarity of the answer ("is there a court near me tonight at 7?") matter more than depth of features.

---

## Competitive Landscape

| Competitor | Focus | Why PadelYara wins |
|---|---|---|
| **Playtomic** | Global booking platform + social | Not used in Austria; walled garden, no aggregation |
| **Eversports** | Austrian/DACH club management + booking | Single platform only; no cross-platform view |
| **eTennis** | Austrian booking platform | Same — siloed |
| **Playskan** (UK) | Padel booking aggregator, UK only | Exact same concept, validated; no DACH presence, no German UX |
| **Anybuddy** (France/Belgium) | Multi-sport aggregator | Not in Austria |
| **PadelChecker NL** (padelchecker.nl) | Dutch court availability checker — same core concept | Netherlands only, no DACH presence |

**Key strategic insight:** Playskan (playskan.com) describes itself as "Skyscanner for padel courts." They have press coverage, real users, and validated the concept. They are UK-only. PadelYara is the Austrian/DACH version of Playskan. This is the positioning frame.

---

## Positioning

**One-line positioning:**
PadelYara is the one place Austrian padel players check to find an available court — regardless of which booking platform the venue uses.

**Broader brand vision:**
A padel hub for the serious recreational player: find courts, understand your game, wear the brand.

**Tone:**
Confident but warm. Not corporate. Built by a player, for players. Female-founded without making it a campaign — it's just true.

**Language:**
German-first for Austria launch. Brand name works equally in German and English for future expansion.

---

## Marketing Starting Point

**Stage:** Pre-launch (public MVP exists but brand not yet established under PadelYara)

**Budget:** Zero. Growth through organic channels only until income streams develop.

**What has worked so far:**
- Word of mouth: padel players told about the tool find it useful immediately
- 2 testers confirmed the core value ("helpful")
- Personal network in the padel community (Bad Vöslau / Wr. Neustadt / Vienna south)

**First growth levers (zero budget):**
1. Personal network + padel WhatsApp groups — direct seeding in Vienna/NÖ padel community
2. Austrian padel Facebook groups and Reddit communities
3. Instagram presence under @padelyara — behind-the-scenes founder story + feature announcements
4. Reach out to padel club admins directly — they want players to find their courts easily
5. SEO content: "Padel Wien," "Padel Platz finden Wien," "Padel Niederösterreich" — long-tail, low competition

**Future income streams (in order of likelihood):**
1. Venue/club featured listings or partnerships
2. Tournament stats tool (freemium model possible)
3. Merch (print-on-demand, low risk, founder designs own prints with AI)
