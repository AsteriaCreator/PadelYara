# Yara — Social & Footage Playbook

*How Yara shows up in **video and photo footage** for marketing and social media. This is the third of three Yara docs — it does not repeat them, it points to them:*

- ***Who she is + how she writes/speaks:*** `.agents/yara-voice.md`
- ***How she looks in illustration / AI art:*** `brand/yara-character-brief.md`
- ***How she behaves on camera + how we post her:*** **this doc**

> One-line reminder of the character: a real black cat with green-gold eyes and standards — **competent, unbothered, mean** (the way a cat is mean, not cruel). She finds courts; the running is your problem. Full character in `yara-voice.md`.

---

## The core idea for footage

She is a **real cat**, so you don't make her "act." You film what she actually does and let the **edit + caption** supply the attitude. The gap between *ordinary cat doing nothing* and *withering caption* is the entire joke.

---

## The high ground — her single strongest visual rule

**Yara is always physically above humans. She watches from above. Never among the players.**

This alone creates her identity without a word. When you choose where to put the camera and where to put her, put her *up* and looking *down*.

**Where she sits:**
- on the glass wall above the court
- on the fence
- on the umpire / referee chair
- on the reception desk
- on a keyboard
- on top of a car
- on a windowsill overlooking the courts

**Never** at net height, never on the floor among players, never being carried at human level. If she has to be low, she's still the one being looked *at*, not one of the group.

---

## On camera — behaviour direction

**On-brand footage**
- Direct, level stares into the lens. The "I saw your smash" look.
- Sitting bolt upright, still, surveying — tail curled.
- Slow blinks, slow head-turns, the over-the-shoulder glance back at camera.
- A paw resting on / owning a ball or racket (native to her, never a held-up prop).
- Walking away mid-moment — the dismissal. Her best exit.
- Ignoring you completely while you talk. Contempt by indifference.

**Off-brand (even if cute — do not post)**
- Zoomies, play-pouncing, frantic toy-batting, anything hyper.
- Belly-up, kneading, head-boops, anything that reads as "aww."
- Wide startled eyes, meowing for attention, begging.
- Costumes, headbands, sweatbands, held-up props.

---

## Editing rules

- Let shots breathe — stillness and a held stare beat fast cuts.
- Deadpan audio over hype. If using a trending sound, pick the dry one.
- Captions carry the voice; the cat just exists, unbothered.
- **No on-screen "like & follow." Ever.** She never asks for engagement.

---

## Caption rules (quick — full voice in `yara-voice.md`)

First person, German-first, present tense. Short declarative sentences; line breaks do the work. No exclamation marks, no rhetorical questions. State facts, don't justify them. Don't market — report. Dismiss the moment the job is done. Equal-opportunity mean; the audience is always **in on the joke**, never the target of it.

**Caption seed bank** *(expand as footage comes in)*
- "Während du das liest, wurde irgendwo ein Court storniert. Ich weiß welcher."
- "Meine Menschin schreibt den Code. Ich finde die Courts. Das Laufen ist euer Problem."
- "Ihr trainiert. Ich beobachte. Einer von uns wird besser."
- "Ich spiele nicht. Ich muss nicht."
- "Pathetic." *(standalone closer)*

**Story-Format (bewährt für Facebook/längere Posts):**
Problem aufbauen → Twist → Produkt als Auflösung → Yara-Closer. Beispiel Post 1:
> Während ihr auf 4 Buchungsseiten aktualisiert, passiert etwas.
> Jemand storniert. Ein Court wird frei. Jemand anderes schnappt ihn sich.
> Ihr könntet diese Person sein.
> PadelYara zeigt freie Padel-Courts aus österreichischen Buchungssystemen. An einem Ort.
> Smashen müsst ihr selbst.

Regel: Nicht mit dem Produkt anfangen. Erst das Problem leben lassen, dann die Auflösung.

---

## Recurring formats (build a feed around these)

- **Yaras Urteil** — she silently judges a clip of someone's padel. Ties to the planned player-analysis subpage of the same name (repo `YarasUrteil.md`).
- **The Report** — deadpan "court status" to camera (she stares; the caption reports).
- **The Walk-Off** — any clip that ends with her leaving mid-moment. Reusable punchline.
- **Court Inspector** — she "inspects" a location, then declares it acceptable. Or not.

---

## Before you post — 5-point check

1. Would Yara actually do/say this, or is it generic cute-cat content?
2. Zero smiling, zero begging, dignity intact?
3. Caption in her voice — declarative, mean-not-cruel, no exclamation marks?
4. Is the audience in on the joke (not mocked personally)?
5. Same cat, same green-gold eyes, same "and?" energy as every other post?

If any answer is no, it's not Yara yet.

---

## Technischer Posting-Workflow (Instagram via Claude Code)

### Bild-Upload
`brand/social/output/` ist gitignored — Instagram braucht aber eine öffentliche URL. Workflow:
1. Bild nach `public/filename.png` kopieren
2. `git add public/filename.png && git commit && git push` → Vercel-Deploy abwarten (~1 Min)
3. URL `https://www.padelyara.at/filename.png` für Instagram-API verwenden
4. Nach dem Post: Datei löschen + cleanup-commit pushen

### Posten via Composio MCP (zwei Schritte)
```
INSTAGRAM_POST_IG_USER_MEDIA   → gibt creation_id zurück
INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH  → veröffentlicht
ig_user_id: "28365034623084985"
```

### Was die API NICHT kann
- **Caption nachträglich editieren** — API gibt `success: true` zurück aber ändert nichts. Immer in der App bearbeiten: ⋯ → Bearbeiten.
- **Musik hinzufügen** — von Meta generell für API-Posts gesperrt, kein Workaround. In der App nach dem Post hinzufügen.
- **KI-Label nachträglich** — kann nur beim Erstellen via `is_ai_generated` gesetzt werden, nicht im Nachhinein per API. In der App erledigen.

### Caption-Regeln für Instagram
- Bildtext **nicht wiederholen** — redundant, da Bild schon spricht
- Keine Absätze (Leerzeilen) — Instagram schneidet nach ~3 Zeilen ab, Absätze verschwenden sichtbaren Platz
- Wichtigstes zuerst; Hashtags ans Ende
