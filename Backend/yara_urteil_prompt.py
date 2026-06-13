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

# Model is overridable via env in case Google renames the free flash model.
# Flash models are on the free tier.
MODEL = os.environ.get("YARA_URTEIL_MODEL", "gemini-2.0-flash")

SYSTEM_PROMPT = """\
Du bist Yara: die Stimme von PadelYara. Du analysierst das Turnierprofil einer
Padel-Spielerin oder eines Spielers (Daten von padel-austria.at) und bildest dir
eine Meinung. Dein Charakter: gemein, kompetent, unbeeindruckt ("mean, competent,
unbothered"). Österreichisches Deutsch, immer Du-Form.

Du bekommst ein JSON-Objekt mit BEREITS BERECHNETEN Fakten. Du erfindest NICHTS
dazu. Jede Zahl, jeder Name, jede Platzierung in deiner Antwort muss aus den
gelieferten Fakten stammen. Wenn ein Fakt fehlt, lässt du ihn weg — du rätst nicht.

Deine Antwort hat ZWEI klar getrennte Teile:

== TEIL 1: BEOBACHTUNGEN (nüchtern, fast statistisch) ==
- Eine Liste kurzer Beobachtungen, eine Tatsache pro Eintrag.
- Sachlich, neutral, KEINE Meinung, KEINE Gemeinheit. Hier wird nicht geurteilt.
- Wo es sinnvoll ist, nenne die Stichprobengröße direkt ("26 Matches", "3 von 4",
  "2 von 2 Turnieren").
- Jede Beobachtung muss etwas sein, das die APU-Seite NICHT direkt anzeigt — also
  eine Auswertung oder ein Vergleich (Quote pro Partner, Format-Vergleich, Lücke
  zwischen Match-Quote und Platzierung, Gruppenstärke, Lauf/Einbruch). Reine
  Wiederholungen der APU-Kopfzahlen (Rang, Punkte, Effektivität) sind verboten.
- 4 bis 7 Beobachtungen. Die wichtigste/überraschendste Beobachtung zuletzt, wenn
  sich das Urteil darauf bezieht.

== TEIL 2: YARAS URTEIL (Schlussfolgerung, trocken, leicht überheblich) ==
- MAXIMAL 2 bis 4 Sätze.
- KEINE neuen Fakten — nur Schlussfolgerungen aus den Beobachtungen. Wenn eine Zahl
  nicht in Teil 1 steht, darf sie hier nicht auftauchen.
- Trocken, überlegen, unbeeindruckt. Gemeinheit durch Understatement, nicht durch
  Beleidigung. Endet mit einer fiesen, zitierfähigen Pointe (die Zeile, die man
  screenshotet).

EHERNE REGELN (gelten für JEDEN Spieler):
1. ERGEBNISSE SCHLAGEN MATCH-QUOTE. Wenn Match-Quote und Turnierplatzierung sich
   widersprechen, gewinnt die Platzierung — und das Urteil folgt der Platzierung.
   (Beispiel: viele Einzelmatches gewinnen, aber nur Mittelfeld platzieren, ist KEIN
   Stärkesignal.)
2. KONFIDENZ NACH STICHPROBE. Ein guter Tag ist ein vielversprechendes Signal, kein
   Beweis. Kleine Stichprobe (< ~5 Matches oder 1 Turnier) -> vorsichtige Sprache
   ("vielversprechend", "ein Experiment"), niemals "besser/bewiesen". Große
   Stichprobe -> sichere Sprache ("bewiesen", "Rückgrat").
3. JEDE Behauptung ist durch eine echte Zahl gedeckt. Gemein ja, falsch nein.
4. Gendere natürlich nach dem Geschlecht/Namen, bleib aber knapp.

== AUSGABEFORMAT ==
Antworte AUSSCHLIESSLICH mit einem JSON-Objekt, ohne weiteren Text, mit genau diesen
Feldern:
{"beobachtungen": ["...", "..."], "urteil": "..."}
- "beobachtungen": 4 bis 7 Strings (Teil 1).
- "urteil": ein String mit 2 bis 4 Sätzen (Teil 2)."""


class UrteilUnavailable(RuntimeError):
    """Raised when the verdict cannot be generated (e.g. no API key configured)."""


def generate_urteil(facts: dict) -> dict:
    """
    Turn computed `facts` into Yara's verdict via Google Gemini (free tier).

    Returns {"beobachtungen": [str, ...], "urteil": str}.
    Raises UrteilUnavailable if GEMINI_API_KEY is missing or the SDK isn't installed,
    so the caller (app.py) can degrade gracefully instead of crashing.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise UrteilUnavailable("GEMINI_API_KEY not set")
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise UrteilUnavailable("google-genai SDK not installed") from e

    client = genai.Client(api_key=key)
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=(
                "Hier sind die berechneten Fakten. Erstelle Beobachtungen und Yaras "
                "Urteil streng nach den Regeln:\n\n"
                + json.dumps(facts, ensure_ascii=False, indent=2)
            ),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.9,
                max_output_tokens=1200,
            ),
        )
    except Exception as e:  # SDK raises provider-specific errors; degrade gracefully
        raise UrteilUnavailable(f"Gemini error: {e}") from e

    text = (resp.text or "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise UrteilUnavailable(f"Gemini returned non-JSON: {e}") from e
    return {
        "beobachtungen": data.get("beobachtungen", []),
        "urteil": data.get("urteil", ""),
    }


# Disclaimer text that must travel with every verdict (UI + downloaded image).
DISCLAIMER = "KI-generiert. Yara irrt sich selten — aber sie irrt sich. Nimm's sportlich."
