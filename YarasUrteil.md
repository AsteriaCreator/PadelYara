# Yaras Urteil — Spieleranalyse (working spec)

> **Status:** Planning. Not built yet. Name provisional.
> Companion to `PROJECT_STATE.md` and `Scrapers.md`. This is the source of truth
> for the player-analysis feature. Update it as decisions land.

## Concept

A new subpage. The user pastes a **padel-austria.at profile URL**
(e.g. `https://padel-austria.at/players/mayer-cornelia`) and Yara generates a
**verdict + dashboard**: real statistics turned into a mean, competent, unbothered
opinion in Yara's voice.

Hook (Cornelia's framing):
> "Füge den Link zu deinem Turnierprofil ein. Yara bildet sich eine Meinung."
> Button: **[Urteil anfordern]** → personalised Yara judgement.

The **verdict is the product**, not the dashboard. People screenshot the verdict,
not a win-rate bar. Numbers are the *evidence*; Yara delivers the *sentence*.

### Modes (same engine, different framing)
1. **Solo** — one profile → full dashboard + verdict (yourself, or anyone).
2. **Duell** — two profiles → opponent scouting / head-to-head.
3. **Doppel-Check** — two profiles → "do you two actually win together?"
4. **Turnier-Scouting** — paste a tournament link → scout the whole field before you play.

**v1 scope (decided 2026-06-13): everything** — all four modes *and* the
group- & schedule-strength layer. Internal build sequence still starts with the Solo
single-profile engine (the other modes reuse it), but all of it ships in v1.

### Output
- AI-written (Claude API, Yara voice) grounded in computed stats, in **two distinct parts**
  (see "Output structure" below): calm evidence-based **Beobachtungen**, then one mean
  **Yaras Urteil** line.
- **Every claim must cite a real number.** Mean is on-brand; wrong is not. No invented flaws.
- Downloadable **branded image** (story-format card) for WhatsApp — mirrors the
  Court Finder "Teilen" pattern.
- "Nächste Turniere für dich" — suggest upcoming tournaments matching the player's
  typical category + region (near-free: query the existing `tournaments` collection).

## The hard-won rule: win-rate ≠ results

A naïve win-rate dashboard gives **confidently wrong advice**. Example from Cornelia's
own profile: with Martin Unger her recent **match** record is 11–15 (sub-.500), but her
**two best career results (2× 2nd place) were both with Martin**. Win-rate flatters the
partner you have easy days with and punishes the one you go deep with.

**The verdict MUST weight tournament placement, not just match win %.**

## The second rule: weight by confidence (sample size)

One good day with a partner is a **promising signal, not a proven one** — results ride on
weather, the draw, who showed up. So verdicts must be weighted by sample size:

- Small sample (e.g. 4 matches / 1 tournament) → tentative language: *"vielversprechend"*,
  *"ein Experiment"* — never *"besser"*.
- Large sample (e.g. 26 matches across many tournaments) → confident language: *"bewiesen"*,
  *"dein Rückgrat"*.

Concretely, the Ines vs Martin read is **not** "dump Martin for Ines". It's: *Martin is the
proven backbone (many games, best results); Ines is a promising experiment* — and, per the
outlook below, one Cornelia has already re-booked. Yara should reward the player for testing
it, not crown it.

## Output structure: Beobachtungen, dann Urteil

The output is **two separated parts**, with different tones. This is deliberate — calm,
trustworthy data first; concentrated meanness last.

**Part 1 — Beobachtungen (nüchtern, fast statistisch).** Bullet points, one derived fact each,
with the sample size attached where it matters (`26 Matches`, `3 von 4`, `2 von 2 Turnieren`).
Neutral — no opinion, no meanness. Where a bullet points somewhere, frame it as a hypothesis,
not a command (*"… — scheint dir zu liegen"*). **Every bullet must be something the APU page
does NOT already show** (see Additionality below) — a computed aggregate or cross-reference,
never a number the user can read straight off their profile. Dimensions to judge (use what the
data supports):
- **Format / Bewerb** — Damen vs Mixed vs Herren. Report *both* win rate and placement — they
  can disagree (Cornelia wins more matches in Damen but places higher in Mixed). Don't conflate.
- **Level / Kategorie** — where the player sits, whether they're climbing.
- **Partner** — proven backbone vs promising experiment (confidence-weighted; see rules above).
- **Gruppenstärke** — were the good results in the strong group (top-N cohort) or the weak one.
- **Nerven / enge Matches** — clutch record (e.g. won the deciding super-tiebreak 10:8).
- **Konstanz** — bad days that collapse entirely (whole tournaments without a set won).
- **Aktivität / Orte** — where and how often they play.

**Part 2 — Yaras Urteil (Schlussfolgerung, trocken, leicht überheblich).** **Max 2–4 sentences.**
**No new facts** — only conclusions synthesised from the Beobachtungen (if a stat isn't in Part 1,
it may not appear here). Dry, superior, unbothered — meanness by understatement, not insult. Ends
on a mean punchline (the line people screenshot). Example register:
*"Im Damen-Doppel sammelst du Siege, im Mixed Platzierungen. Nur eine davon steht im Ranking."*

Keep Part 1 nüchtern and Part 2 short and sharp. The contrast is the point.

## Verdict generation — methodology (the reusable rules)

These turn *any* profile (yours, an opponent's, one with 1 page of matches or 10) into a
meaningful verdict.

### Additionality — beat the APU page or stay silent
The APU profile already shows rank, points, APN, matches won/lost, effectiveness, per-tournament
points, and match scores. **Restating any of those is worthless.** Litmus test for every
Beobachtung: *could the user read this number straight off their APU profile?* If yes, cut it.
Only **derived** insights qualify — things APU does not compute, or actively hides:
- win rate **per partner**, and which partner you go *deepest* (best placements) with
- **format split** — Damen vs Mixed vs Herren, win rate *and* placement
- the **win-rate-vs-placement gap** — winning matches ≠ placing; the single most valuable insight
- **group strength** of your results (APU merges the groups and hides which one you were in)
- **strength of schedule** — the ranking points of the opponents you actually beat
- **streaks, collapse days, clutch record** in deciding tiebreaks
- **trend over time** — climbing or sliding
This derived layer *is* the product — the reason to use PadelYara instead of the APU page.

*Group strength vs strength of schedule* — two answers to the same question ("a real result, or
farmed against weak teams?"). **Group strength** is the coarse version: which group (the strong
top-N cohort, or the weaker rest) you were placed in. **Strength of schedule** is the precise,
per-match version: the actual ranking points of the opponents you beat — and it works even at
venues that run no groups.

### Results beat win rate, always
When match win rate and tournament placement disagree, **placement wins**, and the Urteil follows
placement. (This is the rule that stopped us telling Cornelia to play more Damen — where she wins
matches but places mid-table, while her two podiums are Mixed with Martin.)

### How much history to fetch (the pagination meta-rule)
Profiles range from one page of matches to many. Don't fetch everything — fetch what's *meaningful*:
- **Always fetch the full points/results table.** It's one page, cheap, and authoritative for
  placements, categories, dates and competition type. Drives the results analysis.
- **Fetch match pages newest-first, up to a window:** default **the last ~12 months or 3 pages**,
  whichever is larger; hard cap ~5 pages. This matches the rolling ranking window and bounds cost
  for very active players. Recent form outweighs ancient history.
- **Always state the window** in the output (*"Stand: deine letzten 12 Monate"*) so Yara never
  implies it read a whole career it didn't.
- Cache per profile; refresh when new results appear.

### Confidence by sample size
Attach N to every split; a split built on <~5 matches or a single tournament gets tentative
language and never reaches verdict grade. (See "weight by confidence" above.)

### Disclaimer — AI-generated, can be wrong (required)
The verdict is AI-generated, interpretive, and built on imperfectly-parsed public data (messy
score formats, small samples, reconstructed groups). It **will** sometimes be wrong — we already
caught it about to claim the opposite of the truth. So a disclaimer is mandatory:
- Show a short, visible disclaimer **near the verdict** and **burned into the downloadable image**
  (so it travels with the screenshot).
- Yara's voice, not legalese — unbothered, not grovelling. Draft:
  *"KI-generiert. Yara irrt sich selten — aber sie irrt sich. Nimm's sportlich."*
- It matters most in **opponent-scouting** mode, where the opinion is about a *named third party* —
  frame those clearly as Yara's opinion / entertainment, based on public APU data.

## Data source: padel-austria.at

No auth needed. Plain `requests` + a browser `User-Agent` header works (this is why
`WebFetch` gets 403 but our scraper doesn't) — **reuse the `padel_austria_scraper.py`
pattern** (requests + UA + BeautifulSoup). Cache scraped profiles in MongoDB; they
change slowly. Be polite (sleeps between requests).

### Player profile — `/players/<slug>`
- **Header:** name, ID (`#1015344`), `Platz` (rank), `Punkte`, `APN` (rating),
  `Matches gespielt / gewonnen / verloren`, `Effektivität` (win %).
- **"Zusammensetzung der Punkte"** table: `Punkte | Datum | Kategorie | Turnier` —
  which tournaments fed the ranking points.
- **"Matches"** — match-by-match, grouped by tournament, **both pairs named + set
  scores**. Paginated (`?page=2`…). Plain text (the match list does NOT link to profiles).
  - Gives us, per match: **partner identity, opponents, result**.
  - **Score quirks:** tiebreaks shown merged — `77` = 7–6 (TB to 7), `64` = the loser's
    6–4 TB count, super-tiebreaks like `68 / 710` = 10–8 in the champions tiebreak.
    Parse carefully; aggregate W/L totals are given in the header as a cross-check.
- **The profile is retrospective only** — no "upcoming / registered" section, no future
  dates. A player's *upcoming* tournaments are NOT on their profile; they're found by
  scanning open tournaments' entry lists for the player's name/ID (see Ausblick below).

### Tournament detail — `/ranked/tournaments/<uuid>`
- **Before play (seeded entry list):** table `# | APN | Punkte | Team`, **sorted by
  points** (`#1` = highest points). Each player links to their profile. → lets us rank
  the field and reconstruct group strength.
- **Rules documented on the page:** group-vs-KO by number of pairs; a tournament counts
  from 8 pairs (6 for women's draws); round-robin tiebreakers = head-to-head → game
  difference → coin toss; APN category bands; "Einteilung erfolgt auf Einzelpersonenbasis".
- **After play (results):** table `Platz | Punkte | Spieler`. In **two-group**
  tournaments **every rank appears twice** (one team per group). **Groups are NOT
  labeled** on the page.

### Points system — `/rankings/points` (reference, scrape once)
- Rows are `Kategorie – Feldgröße`; each gives points per placement.
- **Starter ladder (top):** `1st 300 · 2nd 280 · 3rd 260 · 4th 240 · 5th 220 · 6th 200
  · 7th 180 · 8th 160 · …` (lower ranks depend on field size; top 8 are constant).
- **1st place pays by category:** Starter 300 · Advanced 700 · Expert 1100 ·
  Professional 1800 · Elite/Masters 3000. **Category weight is large** — a player
  grinding Advanced is on a different level than one winning Starters.
- ⇒ **Placement is derivable from points + category** (+ field size for lower ranks),
  or read directly from the results table.

## Key domain logic (validated with Cornelia)

1. **Groups are split by ranking POINTS (not APN) into fixed top-N cohorts — NOT halves.**
   The strong group takes the top N teams; the rest fall into the second group (e.g. one
   tournament: the best 8 teams in group 1, everyone else in group 2). Group size + how many
   groups depend on participant count. Not all venues run groups. To reconstruct group
   strength: rank the field by points and take the top cohort — don't assume a 50/50 split.
2. **The federation pays both group winners equally** (two `#1` rows, 300 each). So the
   official points **overvalue weak-group results and undervalue strong-group ones.**
   The federation's own site can't tell you this — **Yara correcting for it is an edge,
   i.e. PadelYara is more accurate than the source.**
3. A win in the strong group ≫ the same placement in the weak group, even for identical
   points.

## Analysis model: "true result quality"

Don't rank results by flat federation points. Score each result as:

```
quality = placement  ×  category weight  ×  field size  ×  opponent strength
```

- **placement** — from points + category (or results table).
- **category weight** — Starter < Advanced < Expert < Professional < Elite (see ladder).
- **field size** — from participant count (bigger draw = more meaningful).
- **opponent strength** — *strength of schedule*: we know the actual opponents per match,
  so look up their ranking points. Beat 5000-pt teams → real; beat 1500-pt teams → discount.
  This is venue-independent (handles the no-group venues) and is preferable to inferring
  group membership. Group-strength from the seed split is the fallback.

This is what lets the verdict be both **mean and true** — e.g. *"deine zwei besten
Ergebnisse, beide in der starken Gruppe, beide mit Martin. Die Statistik lügt, das
Podest nicht."*

## Ausblick: kommende Turniere (forward-looking)

The verdict shouldn't only look backward. For a player, surface their **upcoming
registered tournaments** + partner + what we can already say about each.

**Source:** the profile has no upcoming section — instead, index the **entry lists of open
tournaments** by player name/ID. Each open tournament's `# | APN | Punkte | Team` table
shows registered pairs (e.g. `Cornelia Mayer / Ines Krammer`). Scan open tournaments once,
index by player → a player's upcoming tournaments + partner is a lookup. Bounded (open
tournaments only) and cacheable. This is also how we know Cornelia "already signed up with
Ines again" — Yara can comment on the partner choice.

**The outlook escalates as certainty settles:**
1. **Registration still open** — field not final. Say: category/level, how many of the
   spots are filled, who's registered so far, where the user's team would seed right now,
   the strongest team in so far, days until Nennschluss.
2. **Registration closed, draw not made** — full seeded field known. Predict groups (split
   by ranking points into top-N cohorts — strongest teams in group 1), name likely group
   opponents, flag the favourites, show where the user sits. Yara's read on the draw.
3. **Draw made / in progress** — exact opponents.

Always label the certainty stage so Yara never over-claims ("Stand jetzt…", "sobald die
Anmeldung schließt…").

## Tech notes

- **Scraper:** new backend module, reuse `padel_austria_scraper.py` pattern. Per
  scraper-consistency rule, add it to the **Dockerfile** (`COPY` line + build-time import
  check) and check whether any shared fix belongs in the other scrapers.
- **Cache** profiles + tournament results in MongoDB (slow-changing data).
- **Verdict generation:** Claude API with Yara's voice; feed it the computed stats and
  constrain it to cite only real numbers.
- **Frontend:** new route + nav item in `src/App.tsx` (same shell pattern as
  `/turnierjaeger`, `/padelrevier`). Mobile-first, brand dark `#080810` + lime `#d4f53c`,
  Barlow Condensed. Download via client-side html-to-image.
- **Voice:** German, Yara's voice (`.agents/yara-voice.md`).

## Open questions

- Exact group-count thresholds by participant count (in the WSO /
  "Durchführungsbestimmungen").
- Whether the seeded entry list stays accessible after a tournament finishes (needed to
  reconstruct historical group membership) — if not, lean on opponent-profile lookups.
- **Name** — provisional "Urteil" / "Yaras Urteil". Other candidates: Spielerakte,
  Steckbrief, Seziert, Realitätscheck.
- v1 scope (Solo only vs Solo + Duell vs all modes).
- Privacy/PR posture for scouting *other* players (public federation data, but worth a
  sentence before shipping opponent-scouting).
