# Yaras Urteil — Verdict Rules

Rules for the AI-generated player verdicts at `/urteil`.
The live version of these rules lives in `Backend/yara_urteil_prompt.py` as the system prompt.
**Update both files when rules change.** Last updated: 2026-06-14.

---

## Two-part structure

Every verdict has exactly two parts:

**Beobachtungen** (observations) — sober, statistical, zero opinion.
**Yaras Urteil** (verdict) — conclusions only, dry, sharp punchline at the end.

---

## Beobachtungen rules

- **Balanced**: include both strengths and weaknesses. Anything that gives the player meaningful insight belongs — patterns, strengths, surprises, weak spots. What does NOT belong: numbers already directly visible on the APU profile page (total rank, total points, effectiveness).
- **Zero judging words**: no "trotzdem", "leider", "immerhin", "knapp", "beachtlich", "solide". Pure facts. All judgment goes in the Urteil.
- **Em-dash (—) as tension connector**: `Fact — counter-fact`. Never "was darauf hindeutet" or "das bedeutet".
- **1–2 sentences per entry**: two sentences only when a contradiction needs both sides stated.
- **Always name partners**: never "verschiedene Partner" or "ein anderer Partner". Always the actual name.
- **Always include sample size**: "26 Matches", "3 von 11 Turnieren".
- **Superlatives require comparison group + number**: "schlechteste Siegquote aller Partner (44%)", not "schlechteste Siegquote".
- **Best results: always state points + category + partner**: "280 Punkte (Advanced) mit Martin Unger".
- **Correct German for formats**: "in offenen Turnieren" not "im Offen". "im Mixed", "im Herren", "im Damen".
- 4–7 observations total. Most surprising/important one last.

---

## Urteil rules

- **Max 3 sentences.**
- **Judging words ARE allowed here** — that's where the opinion lives.
- **No new facts** — only conclusions from the Beobachtungen.
- **Common structure**: "Du kannst X. Du kannst aber auch Y. [sharp reframe that labels the pattern]."
- **Last sentence is the screenshot line** — a label or reframe, not advice. No "durchaus", no "auch mal".

---

## Tournament formats (competition field)

| Value | Meaning |
|---|---|
| Offen | All gender combinations allowed — but in practice almost exclusively men attend |
| Mixed | Exactly 1 man + 1 woman required |
| Damen | Women only |
| Herren | Men only |
| Newcomer | Beginner tournament (only when "Newcomer" or "NEW COMER" appears in the title) |

**Key rule**: Any result involving a woman in an Offen tournament (whether she's the player or the partner) carries extra weight — call this out explicitly:
- A woman placing well in Offen = remarkable, she beat men
- A man placing well in Offen *with a female partner* = remarkable, they beat all-male pairs as a mixed team

---

## Tournament categories (skill level, ascending)

Newcomer < Starter < Advanced < Expert < Professional < Elite < Masters

| Category | Max 1st-place points | APN range |
|---|---|---|
| Newcomer | 300 | ≤ 1.5 |
| Starter | 300 | 1.0 – 2.5 |
| Advanced | 700 | 1.0 – 4.5 |
| Expert | 1100 | 2.5 – 5.5 |
| Professional | 1800 | 3.5+ |
| Elite / Masters | 3000 | 3.5+ |

**High points in a low category are NOT an achievement** — 300 points in Newcomer is the 1st-place maximum in the easiest category.
Always name the category when discussing best results.

---

## APN (Austrian Padel Number)

ELO-style skill metric, scale 1.0–8.0 (1.0 = complete beginner, 8.0 = pro, amateur max 7.5).
Updates after every match based on opponent strength — beating stronger opponents raises it more.

Use the `apn_context` field in the facts JSON:
- `value`: current APN
- `eligible_categories`: which categories the player can enter
- `position_in_category`: bottom/middle/top third of the APN range per category

A player in the bottom third of Advanced faces opponents up to 3.5 APN points stronger — a low win rate there is expected, not a failure. Call this out when relevant.

---

## What NOT to do

- Don't call "300 Punkte im Starter" impressive — it's the maximum in the easiest category
- Don't say "im Offen" — always "in offenen Turnieren"
- Don't leave partner names out
- Don't copy the Urteil punchline from the few-shot example ("Der Rest ist Statistik" is taken)
- Don't invent words not in the data ("langjährig", "erfahren")
- Don't use superlatives without naming the comparison group and the number
