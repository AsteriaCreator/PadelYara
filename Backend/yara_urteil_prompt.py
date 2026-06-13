"""
Yaras Urteil — verdict generation.

THIS FILE IS THE SOURCE OF TRUTH FOR HOW YARA JUDGES EVERY PLAYER.

All the wording/style rules we worked out (two-part structure, additionality,
results-beat-win-rate, confidence-by-sample-size, the disclaimer, the tone split)
live here as the system prompt, so EVERY user's verdict follows the same rules.
The human-readable spec is in the repo root: YarasUrteil.md — keep the two in sync.

The model receives only computed facts (never raw HTML) and must turn them into:
  - Beobachtungen: sober, almost statistical, neutral observations (a list)
  - Urteil: 2-4 sentences, dry and slightly superior, ending on a mean punchline

It is constrained to use ONLY the facts it is given — no invented numbers.
"""

import json
import os

# Model is overridable via env so cost can be tuned without a code change.
# Default is Opus 4.8 (best voice); set YARA_URTEIL_MODEL=claude-haiku-4-5 to save.
MODEL = os.environ.get("YARA_URTEIL_MODEL", "claude-opus-4-8")

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
4. Gendere natürlich nach dem Geschlecht/Namen, bleib aber knapp."""

# Structured-output schema — guarantees we get back clean {beobachtungen, urteil}.
URTEIL_SCHEMA = {
    "type": "object",
    "properties": {
        "beobachtungen": {
            "type": "array",
            "items": {"type": "string"},
            "description": "4-7 nüchterne, datenbasierte Beobachtungen (Teil 1).",
        },
        "urteil": {
            "type": "string",
            "description": "2-4 Sätze, trocken/überheblich, mit Pointe (Teil 2).",
        },
    },
    "required": ["beobachtungen", "urteil"],
    "additionalProperties": False,
}


class UrteilUnavailable(RuntimeError):
    """Raised when the verdict cannot be generated (e.g. no API key configured)."""


def generate_urteil(facts: dict) -> dict:
    """
    Turn computed `facts` into Yara's verdict.

    Returns {"beobachtungen": [str, ...], "urteil": str}.
    Raises UrteilUnavailable if ANTHROPIC_API_KEY is missing or the SDK isn't
    installed, so the caller (app.py) can degrade gracefully instead of crashing.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise UrteilUnavailable("ANTHROPIC_API_KEY not set")
    try:
        import anthropic
    except ImportError as e:  # anthropic not installed
        raise UrteilUnavailable("anthropic SDK not installed") from e

    client = anthropic.Anthropic()
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            output_config={
                "format": {"type": "json_schema", "schema": URTEIL_SCHEMA},
                "effort": "medium",
            },
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Hier sind die berechneten Fakten. Erstelle Beobachtungen "
                        "und Yaras Urteil streng nach den Regeln:\n\n"
                        + json.dumps(facts, ensure_ascii=False, indent=2)
                    ),
                }
            ],
        )
    except anthropic.APIError as e:
        raise UrteilUnavailable(f"Anthropic API error: {e}") from e

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    data = json.loads(text)
    return {
        "beobachtungen": data.get("beobachtungen", []),
        "urteil": data.get("urteil", ""),
    }


# Disclaimer text that must travel with every verdict (UI + downloaded image).
DISCLAIMER = "KI-generiert. Yara irrt sich selten — aber sie irrt sich. Nimm's sportlich."
