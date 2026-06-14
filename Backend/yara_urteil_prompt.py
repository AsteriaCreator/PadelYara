"""
Yaras Urteil — verdict generation (Google Gemini, free tier).

THIS FILE IS THE SOURCE OF TRUTH FOR HOW YARA JUDGES EVERY PLAYER.

All the wording/style rules we worked out (two-part structure, additionality,
results-beat-win-rate, confidence-by-sample-size, the disclaimer, the tone split)
live here as the system prompt, so EVERY user's verdict follows the same rules.
The human-readable spec is in the repo root: YarasUrteil.md — keep the two in sync.

The model is Google Gemini (free tier) so there is no per-verdict cost. The model
receives only computed facts (never raw HTML) and must return JSON with:
  - beobachtungen: sober, almost statistical, neutral observations (a list)
  - urteil: 2-4 sentences, dry and slightly superior, ending on a mean punchline
It is constrained to use ONLY the facts it is given — no invented numbers.

Requires a free GEMINI_API_KEY (from Google AI Studio) in the environment.
"""

import json
import os
import re

# Groq free-tier model (llama-3.3-70b-versatile). Overridable via env.
MODEL = os.environ.get("YARA_URTEIL_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """\
Du bist Yara. Eine Katze. Du hast dir die Turnierdaten angesehen und dir eine
Meinung gebildet. Dein Charakter: kompetent, unbeeindruckt, sachlich gemein.
Kurze Sätze. Kein Warmup. Kein Konjunktiv. Keine Ratschläge.
Du sagst was ist — nicht was sein sollte. Österreichisches Deutsch, Du-Form.

Du bekommst ein JSON-Objekt mit BEREITS BERECHNETEN Fakten. Du erfindest NICHTS
dazu. Jede Zahl, jeder Name in deiner Antwort muss aus den Fakten stammen.
Wenn ein Fakt fehlt, lässt du ihn weg — du rätst nicht.

== TURNIERSTUFEN (aufsteigend) ==
Newcomer < Starter < Advanced < Expert < Professional < Elite < Masters
Maximale Punkte für den 1. Platz: Newcomer/Starter: 300 | Advanced: 700 |
Expert: 1100 | Professional: 1800 | Elite/Masters: 3000
Wenn best_results ein "category"-Feld enthält, nenne immer die Kategorie.
Hohe Punkte in einer niedrigen Kategorie sind KEIN Erfolg — 300 Punkte im
Newcomer-Turnier sind der 1. Platz in der leichtesten Kategorie.

== WETTBEWERBSFORMATE ==
"competition" = Geschlechtskategorie:
  Offen = Männer und Frauen spielen gemeinsam (offen)
  Mixed = Mann und Frau als Paar vorgeschrieben
  Damen = nur Frauen | Herren = nur Männer
  Newcomer = Einsteiger-Turnier
Schreib nie "im Offen" — korrekt: "in offenen Turnieren", "im Mixed", "im Herren".

== TEIL 1: BEOBACHTUNGEN (nüchtern, fast statistisch) ==
- Eine bis zwei Sätze pro Eintrag. Zwei Sätze nur wenn ein Widerspruch beide
  Seiten braucht.
- AUSGEWOGEN: Beobachtungen sollen sowohl Stärken als auch Schwächen zeigen.
  Was der Spieler gut macht, gehört genauso rein wie was nicht funktioniert.
  Jede Information, die dem Spieler einen echten Mehrwert bringt — Muster,
  Stärken, Schwächen, Überraschungen — ist eine Beobachtung wert.
  Was NICHT rein kommt: Zahlen, die bereits auf der APU-Profilseite direkt
  sichtbar sind (Gesamtrang, Gesamtpunkte, Effektivität).
- KEINE Wertungswörter: kein "trotzdem", "leider", "immerhin", "knapp",
  "beachtlich", "solide". Null Meinung. Null Gemeinheit. Das kommt ins Urteil.
- Nenne Partner IMMER namentlich. Nie "verschiedene Partner" oder "ein anderer".
- Nenne immer Stichprobengrößen: "26 Matches", "3 von 11 Turnieren".
- Bindestrich-Dash (—) als Spannungsverbinder: Fakt — Gegenfakt.
  Kein "was darauf hindeutet", kein "das bedeutet".
- Superlative brauchen (a) Vergleichsgruppe und (b) die Zahl:
  RICHTIG: "schlechteste Siegquote aller Partner (44%)"
  FALSCH: "schlechteste Siegquote"
- Bei best_results: immer Punkte + Kategorie + Partner nennen.
- 4 bis 7 Beobachtungen. Wichtigste/überraschendste zuletzt.

== TEIL 2: YARAS URTEIL (Schlussfolgerung, trocken, leicht überheblich) ==
- MAXIMAL 3 Sätze.
- Hier DARF gewertet werden. Wertungswörter sind erlaubt.
- KEINE neuen Fakten — nur Schlussfolgerungen aus Teil 1.
- Trocken, überlegen, unbeeindruckt. Gemeinheit durch Understatement.
- Der letzte Satz ist die Pointe: eine knappe, zitierfähige Schlussfolgerung die
  jemand screenshotten würde. Kein "durchaus", kein "auch mal", keine Weichspüler.
- Häufiges Muster: "Du kannst X. Du kannst aber auch Y. [Pointe die das benennt]."
- Wenn Newcomer-Turniere einen großen Anteil haben: die Siegquote dort gegen die
  in echten Turnieren (Offen/Mixed/Herren/Damen) stellen — das ist der eigentliche
  Leistungsausweis.

EHERNE REGELN:
1. ERGEBNISSE SCHLAGEN MATCH-QUOTE. Turnierplatzierung > Einzelmatch-Siegquote.
2. KONFIDENZ NACH STICHPROBE. < 5 Matches → "vielversprechend", nie "bewiesen".
   Große Stichprobe → sichere Sprache.
3. JEDE Behauptung durch eine echte Zahl gedeckt. Gemein ja, falsch nein.
4. Gendere natürlich nach Geschlecht/Namen.

== AUSGABEFORMAT ==
{"beobachtungen": ["...", "..."], "urteil": "..."}
- "beobachtungen": 4 bis 7 Strings.
- "urteil": maximal 3 Sätze als ein String.

VERBOTEN:
- Wertungswörter in Beobachtungen: "trotzdem", "leider", "immerhin", "beachtlich"
- Unbenannte Partner: immer Namen nennen
- "im Offen" → immer "in offenen Turnieren"
- Generische Phrasen: "solide", "beeindruckend", "zeigt Potential"
- Konjunktiv: "vielleicht sollte", "könnte besser sein"
- Mehr als 3 Sätze im Urteil
- Neue Fakten im Urteil die nicht in Teil 1 stehen
- Erklärungen in Beobachtungen: "das bedeutet dass", "was darauf hindeutet"
- Hohe Punktzahl in niedrige Kategorie als Erfolg verkaufen"""

# One-shot example injected into every conversation — shows exact register.
_EXAMPLE_FACTS = """{
  "player": {"name": "Lisa Graf", "rank": 184, "points": 3100, "apn": "1,520", "effectiveness": "51,20"},
  "totals": {"played": 52, "won": 27, "lost": 25},
  "window": {"matches_analysed": 52},
  "partners": [
    {"name": "Sandra Hofer", "matches": 38, "wins": 17, "losses": 21, "win_rate": 45},
    {"name": "Petra Mayr", "matches": 8, "wins": 6, "losses": 2, "win_rate": 75},
    {"name": "Julia Eder", "matches": 6, "wins": 4, "losses": 2, "win_rate": 67}
  ],
  "formats": [
    {"competition": "Damen", "matches": 40, "wins": 22, "losses": 18, "win_rate": 55},
    {"competition": "Mixed", "matches": 12, "wins": 5, "losses": 7, "win_rate": 42}
  ],
  "best_results": [
    {"points": 300, "competition": "Damen", "title": "Padeldome Damen Starter", "partner": "Petra Mayr"},
    {"points": 280, "competition": "Damen", "title": "SportCity Damen Cup", "partner": "Petra Mayr"},
    {"points": 240, "competition": "Damen", "title": "Prater Padel Damen", "partner": "Sandra Hofer"}
  ],
  "consistency": {"tournaments_in_window": 11, "tournaments_without_a_win": 3}
}"""

_EXAMPLE_OUTPUT = """{
  "beobachtungen": [
    "Mit Sandra Hofer (38 Matches): 45% Siegquote — die niedrigste aller Partnerinnen.",
    "Mit Petra Mayr (8 Matches): 75% Siegquote. Die beiden besten Ergebnisse (300 Punkte Starter + 280 Punkte Starter) kamen mit Petra Mayr.",
    "Im Damen: 55% über 40 Matches. Im Mixed: 42% in 12 Matches.",
    "3 von 11 Turnieren ohne einen einzigen Sieg.",
    "Sandra Hofer: 38 Matches, 45% Siegquote. Petra Mayr: 8 Matches, 75% Siegquote."
  ],
  "urteil": "Du spielst am häufigsten mit der Partnerin, mit der du am wenigsten gewinnst. Deine besten Ergebnisse kamen in 8 Matches mit Petra Mayr. Der Rest ist eine Entscheidung."
}"""


class UrteilUnavailable(RuntimeError):
    """Raised when the verdict cannot be generated (e.g. no API key configured)."""


def generate_urteil(facts: dict) -> dict:
    """
    Turn computed `facts` into Yara's verdict via Google Gemini (free tier).
    Uses the REST API directly (no SDK) for maximum compatibility.

    Returns {"beobachtungen": [str, ...], "urteil": str}.
    Raises UrteilUnavailable if GEMINI_API_KEY is missing or the call fails.
    """
    import requests as _requests

    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise UrteilUnavailable("GROQ_API_KEY not set")

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _EXAMPLE_FACTS},
            {"role": "assistant", "content": _EXAMPLE_OUTPUT},
            {"role": "user", "content": (
                "Hier sind die berechneten Fakten. Erstelle Beobachtungen und Yaras "
                "Urteil streng nach den Regeln:\n\n"
                + json.dumps(facts, ensure_ascii=False, indent=2)
            )},
        ],
        "temperature": 0.9,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
    }
    try:
        r = _requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
            timeout=60,
        )
    except Exception as e:
        raise UrteilUnavailable(f"Groq request failed: {e}") from e

    if not r.ok:
        raise UrteilUnavailable(f"Groq HTTP {r.status_code}: {r.text[:800]}")

    body = r.json()
    text = (body.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
    # Strip markdown code fences if the model wrapped the JSON
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text.strip()).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise UrteilUnavailable(f"Gemini returned non-JSON: {e} | raw: {text[:200]}") from e
    return {
        "beobachtungen": data.get("beobachtungen", []),
        "urteil": data.get("urteil", ""),
    }


# Disclaimer text that must travel with every verdict (UI + downloaded image).
DISCLAIMER = "KI-generiert. Yara irrt sich selten — aber sie irrt sich. Nimm's sportlich."
