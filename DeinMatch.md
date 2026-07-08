# Dein Match — Feature-Spezifikation

Stand: 2026-07-06 · Status: **spezifiziert, nicht gebaut** · Umsetzung in separater Session.
Mockup (v3, verbindlich für Look & Copy): `.mockups/dein-match.html`

## 0. Was das Feature ist

Spieler organisieren ein Padel-Match (Doppel = 4 Spieler) ohne Login:
Match anlegen → Link in die WhatsApp-Gruppe → Leute treten bei, bis es voll ist.
Zusätzlich ein öffentliches Board (`/dein-match`) mit Venue- und Level-Filter, damit
man Matches findet, ohne dass sie einem per Link geschickt werden — das ersetzt das
"jede WhatsApp-Gruppe zeigt alle Matches"-Problem.

Entschieden (Session 2026-07-06, mit Cornelia):
- **Kein Doodle, kein Drittanbieter.** Nativ auf FastAPI + MongoDB.
- Match = **Vorschlag**, Buchung bleibt extern (Flag `court_booked` zeigt den Stand).
- Match ist an **genau eine Venue** gebunden (aus unseren Venue-Daten). Multi-Venue später (§9).
- **4 Spieler fix**, Preis immer **÷ 4**, gleichmäßig.
- Telefonnummern: **Pflicht, aber nie öffentlich.** Austausch nur Organisator ↔ Beitretender (§1.3).
- Benachrichtigungen per **E-Mail über den bestehenden Brevo-Versand** (wie `tournament_alerts.py`). Kein neuer Provider.
- Level-Skala eigens fürs Match (feiner als Turniere, bewusst **ohne Newcomer**).

---

## 1. Datenmodell

Eine neue Collection **`matches`** in `padel_checker`. Keine weiteren Collections in Phase 1.

```
matches {
  _id            ObjectId
  slug           string   // 8 Zeichen, secrets.token_urlsafe, unique index — öffentliche URL
  manage_token   string   // 32 Zeichen secret — Organisator-Link, niemals in öffentlichen Responses

  venue {                  // Snapshot aus state.VENUES / GET /api/venues beim Anlegen
    id, slug, name         // slug → Link auf /court/:slug
    court_type             // "indoor" | "outdoor" | "indoor+outdoor"
    lat, lon               // für Umkreissuche
  }

  starts_at      string   // ISO UTC
  ends_at        string   // ISO UTC, > starts_at
  levels         [string] // ≥1 aus LEVELS (s.u.), Mehrfachauswahl
  court_booked   bool
  price_total    number|null  // EUR gesamt; pro Person = price_total/4, immer, unabhängig vom Füllstand
  note           string|null  // ≤200 Zeichen, reiner Text

  organizer {
    name         string   // ≤40
    phone        string   // Pflicht, normalisiert (+43…)
    email        string   // Pflicht — Benachrichtigungen + Manage-Link-Recovery
  }

  players [{               // players[0] existiert NICHT implizit — Organisator ist separat
    name         string
    phone        string|null   // Pflicht bei Selbst-Beitritt; null wenn vom Organisator eingetragen
    email        string|null   // optional
    token        string        // 32 Zeichen — persönlicher Link (leave, Organisator-Nummer sehen)
    added_by_organizer bool
    joined_at    string
  }]

  spots_total    4        // fix in Phase 1, Feld trotzdem speichern (Zukunft: 2er)
  status         "open" | "full" | "cancelled" | "expired"
  created_at, updated_at
  purged_at      string|null   // gesetzt vom Cleanup-Job (§5)
}
```

**Zählweise:** Organisator + `players[]` = Belegung. `full` ⇔ `1 + len(players) == spots_total`.
`status` wird bei jedem Join/Leave mitgeschrieben (Board-Query bleibt trivial).

**LEVELS** (Konstante, Frontend + Backend identisch):
`["Starter", "Starter +", "Starter ++", "Low Advanced", "Mid Advanced", "High Advanced", "Expert", "Professional", "Elite"]`
Kein "Newcomer" — bewusste Entscheidung (Turnier-Skala in `TurnierjagerPage.tsx:13` hat es, hier nicht).

**Indexe:** `slug` (unique) · `{status: 1, starts_at: 1}` (Board) · `venue.id`.
Umkreissuche: **kein** Geo-Index — offene Matches sind wenige; Haversine in Python über die
Kandidaten, gleiche Formel wie der Court-Finder-Search verwendet.

### 1.3 Sichtbarkeits-Matrix (verbindlich)

| Feld | Öffentlich (Board + `/match/:slug`) | Beitretender (mit eigenem Token) | Organisator (mit manage_token) |
|---|---|---|---|
| Venue, Zeit, Levels, Preis, gebucht, Notiz | ✅ | ✅ | ✅ |
| Vornamen aller Spieler | ✅ | ✅ | ✅ |
| Organisator-Name | ✅ | ✅ | ✅ |
| **Organisator-Telefon** | ❌ | ✅ (Kernfunktion) | ✅ |
| **Spieler-Telefone** | ❌ | ❌ (auch nicht die der anderen!) | ✅ |
| E-Mails | ❌ | ❌ | ❌ (nur Backend) |
| Tokens | ❌ | nur der eigene | nur manage_token |

Der Organisator ist die einzige Kontakt-Drehscheibe. Spieler sehen einander nie.

---

## 2. Backend-Endpoints

Neuer Router **`Backend/routers/matches.py`**, eingebunden in `app.py` wie die anderen.
⚠️ Dockerfile-Regel prüfen: neue `.py` braucht ggf. `COPY`-Zeile + Import-Check (falls
`routers/` nicht als Verzeichnis kopiert wird).

| Methode & Pfad | Auth | Zweck |
|---|---|---|
| `POST /api/matches` | — | Anlegen. Body = alle Felder aus §1. Response: `{slug, manage_token}`. Sendet Bestätigungs-Mail an Organisator (enthält beide Links → Manage-Link-Recovery). |
| `GET /api/matches` | — | Board. Query: `venue_ids` (CSV) **oder** `lat`+`lon`+`radius`; `levels` (CSV, OR-match: Match erscheint, wenn ≥1 Level überlappt); optional `include_full=1`. Liefert nur `status in (open, full)` und `starts_at > now`. Öffentliche Shape (§1.3), sortiert nach `starts_at` asc. |
| `GET /api/matches/{slug}` | — | Öffentliche Detail-Ansicht. 404 wenn unbekannt. Cancelled/expired liefern den Status mit (Frontend rendert Endzustand). |
| `GET /api/matches/{slug}/me?t=` | Token | Persönliche Ansicht. `t == manage_token` → Organisator-View (alle Telefone). `t == player.token` → Spieler-View (nur Organisator-Telefon). Sonst 403. |
| `POST /api/matches/{slug}/join` | — | Body: `{name, phone, email?}` + Honeypot-Feld. Atomar (s.u.). Response: `{player_token, organizer_phone}`. Mails: an Organisator ("X ist dabei"); wenn dadurch voll → zusätzlich an alle Spieler mit E-Mail. |
| `POST /api/matches/{slug}/leave` | Token (Body) | Spieler trägt sich aus. `full → open` falls nötig. Mail an Organisator. |
| `PATCH /api/matches/{slug}?t=manage` | manage | Editieren: Zeit, Levels, Preis, `court_booked`, Notiz. Bei Zeit-Änderung: Mail an alle Spieler mit E-Mail. |
| `POST /api/matches/{slug}/players?t=manage` | manage | Organisator trägt Spieler manuell ein (`{name, phone?}`) — der "ich hab schon einen Partner"-Fall. |
| `DELETE /api/matches/{slug}/players/{player_token}?t=manage` | manage | Organisator entfernt Spieler. Mail an den Entfernten, falls E-Mail vorhanden. |
| `DELETE /api/matches/{slug}?t=manage` | manage | **Absagen** (Status → cancelled, kein Doc-Delete). Mail an alle Spieler mit E-Mail. |

**Atomarer Join (Race auf den letzten Platz):** `find_one_and_update` mit Filter
`{slug, status: "open", $expr: {$lt: [{$size: "$players"}, {$subtract: ["$spots_total", 1]}]}}`
und `$push` in einem Schritt. Kein Treffer → **409**, Frontend zeigt „Zu langsam. Das Match ist voll."

**Validierung (Backend, Pydantic):** `ends_at > starts_at` · `starts_at > now` · Dauer ≤ 4 h ·
`price_total` 0–200 oder null · `levels ⊆ LEVELS`, ≥1 · Namen ≤40, Notiz ≤200 ·
Telefon normalisieren (Ziffern/+, min. 7 Ziffern) · Doppel-Join-Guard: gleiche normalisierte
Nummer schon in `players` → 400 „Du bist schon drin. Einmal reicht."

---

## 3. Frontend

Neuer Nav-Tab **„Dein Match"** in `App.tsx` (zwischen Turnierjagd und Über Yara).
Passt zum Slogan „Dein Match. Dein Moment." — der Tab-Name ist die Marke.

Routen + Dateien:
- `/dein-match` → `src/pages/DeinMatchPage.tsx` (Board)
- `/dein-match/neu` → `src/pages/MatchCreatePage.tsx`
- `/match/:slug` → `src/pages/MatchDetailPage.tsx` (öffentlich; `?t=` schaltet persönliche/Manage-Sicht)

### 3.1 Board `/dein-match`

- **Filterbox** (siehe Mockup): Segment-Toggle **Nach Venue / Umkreissuche**.
  - Venue-Modus: Multi-Select-Pills, Quelle `GET /api/venues`.
  - Umkreis-Modus: Ort + Radius, identisch zum Court Finder (gleiches Geocoding wiederverwenden).
  - Level-Pills, Mehrfachauswahl.
- **Letzte Suche** in `localStorage` (`padel_match_filter`: mode, venueIds, ort, radius, levels) — beim Öffnen wiederherstellen.
- Karten: Venue-Name = **Link auf `/court/:slug`**, Zeit von–bis, Indoor/Outdoor, Entfernung (nur im Umkreis-Modus), Level-Badges, Gebucht-Badge (grün ✓ / amber „noch nicht gebucht"), „Organisiert von **X**", Preis (`28 € gesamt · 7 €/Person` bzw. „Preis noch offen"), Notiz, Zähler, Avatare (★ = Organisator, helle Kreise = eingetragene Spieler), „Ich bin dabei" + „Teilen".
- Volle Matches gedimmt unterhalb der offenen.
- **States:** Loading (Skeleton) · Leer → *„Keine offenen Matches. Dann mach eben das erste auf."* + CTA · Fehler → *„Meine Jagd ist gerade unterbrochen. Versuch es gleich nochmal."*

### 3.2 Anlegen `/dein-match/neu`

Felder wie im Mockup: Venue (Autocomplete aus `/api/venues`) · Datum · Von–Bis ·
Court gebucht? (Ja/Nein) · Preis gesamt (Pro-Person-Feld readonly, `÷ 4`) · Name + Handynummer ·
E-Mail (Pflicht, mit Hinweis *„Du bekommst eine Mail, wenn jemand beitritt oder absagt."*) ·
Level-Pills mit Yara-Hinweis (§7) · Mitspieler eintragen (Chips, optional) · Notiz (Placeholder *„Vorname reicht."* beim Namensfeld beachten, s. §6).

Nach Submit → **Erfolgs-Screen**:
- Öffentlicher Link + „Link kopieren" + **WhatsApp-Button** (`wa.me/?text=`).
- Manage-Link separat, deutlich markiert: *„Dein Schlüssel zum Match. Verlier ihn nicht — ich schicke ihn dir zur Sicherheit auch per Mail."*

### 3.3 Match-Seite `/match/:slug`

- **Offen, ohne Token:** Detail-Karte + „Ich bin dabei" → Join-Formular (Name, Handynummer mit Inline-Hinweis *„Wird nur an die Organisatorin weitergegeben — nicht öffentlich sichtbar."*, E-Mail optional). Nach Bestätigen: grüne Reveal-Box mit Organisator-Nummer (*„Nur für dich sichtbar. Nicht für andere Mitspieler."*) + persönlicher Link zum Speichern. Token zusätzlich in `localStorage` (`padel_match_tokens`: slug → token) — Wiederbesuch zeigt automatisch die persönliche Sicht.
- **Voll:** gedimmt, *„Voll. Der Rest kommt zu spät."* Kein Join-Button.
- **Mit Spieler-Token:** wie öffentlich + Organisator-Nummer + Button **„Doch nicht"** (austragen, mit Confirm).
- **Mit manage_token:** Editier-Modus (Zeit, Levels, Preis, gebucht, Notiz), Spieler-Liste **mit Telefonnummern**, Spieler entfernen, Spieler hinzufügen, **„Match absagen"** (Confirm: *„Sicher? Ich sage allen Bescheid. Peinlich wird es trotzdem."*).
- **Abgesagt:** *„Abgesagt. Von der Organisatorin, nicht von mir."* · **Vorbei/expired:** read-only, *„Das Match ist vorbei. Ob ihr gewonnen habt, weiß ich nicht — und es ist nicht mein Problem."* · **404:** *„Dieses Match existiert nicht. Vielleicht hat es nie existiert."*

### 3.4 Edge Cases (verbindlich abzudecken)

1. Race auf den letzten Platz → 409 → *„Zu langsam. Das Match ist voll."* + Karte aktualisieren.
2. Join nach `starts_at` → Backend blockt, Frontend zeigt Vorbei-State.
3. Doppel-Join (gleiche Nummer) → 400-Meldung (§2).
4. Spieler entfernt bei vollem Match → `full → open`, Match erscheint wieder am Board.
5. Preis/Zeit-Änderung nach Joins → Mail an Spieler (nur bei Zeit), UI zeigt neuen Stand beim nächsten Load — kein Live-Sync nötig.
6. Verlorener persönlicher Link: keine Recovery in Phase 1 (Organisator kann den Spieler entfernen und er tritt neu bei). Verlorener Manage-Link: steht in der Bestätigungs-Mail.
7. Organisator will selbst aussteigen → gibt es nicht; er kann nur absagen (dokumentieren im UI-Text des Manage-Views).
8. `?t=` mit ungültigem Token → öffentliche Sicht + dezenter Hinweis *„Der Link ist ungültig. Ich kenne dich nicht."*

---

## 4. E-Mail-Benachrichtigungen

**Provider: Brevo — existiert schon.** `tournament_alerts.py` hat den kompletten Versand-Helper
(`api.brevo.com/v3/smtp/email`, Sender `Yara <yara@adventure-it.at>`, `BREVO_API_KEY` auf Railway).
Den Helper in ein gemeinsames Modul ziehen oder kopieren — **kein neuer Provider, kein DNS-Setup.**

Nur transaktional, kein Marketing, kein Double-Opt-in nötig (Vertragskommunikation).
Alle Texte kurz, Yara-Ton, mit Link zum Match:

| Trigger | An | Inhalt (Kern) |
|---|---|---|
| Match angelegt | Organisator | Beide Links. *„Dein Match steht. Hier ist dein Schlüssel — der Manage-Link. Verlier ihn nicht."* |
| Jemand tritt bei | Organisator | *„{Name} ist dabei. {n} von 4."* + Telefonnummer des Beitretenden. |
| Match voll | Organisator + alle Spieler mit E-Mail | *„Ihr seid vier. Mehr braucht es nicht."* Spieler-Version enthält die Organisator-Nummer. |
| Spieler tritt aus | Organisator | *„{Name} ist raus. Wieder {n} von 4. Der Link tut noch."* |
| Zeit geändert | Alle Spieler mit E-Mail | Alte Zeit → neue Zeit. *„Merk sie dir besser als die alte."* |
| Abgesagt | Alle Spieler mit E-Mail | *„Das Match am {Datum} ist abgesagt. Nicht meine Entscheidung."* |
| Spieler entfernt | Der Entfernte (falls E-Mail) | Neutral, kein Yara-Biss: *„Die Organisatorin hat die Aufstellung geändert. Du bist für dieses Match nicht mehr eingetragen."* |

---

## 5. DSGVO

**Rechtsgrundlage:** Art. 6 Abs. 1 lit. b DSGVO — Verarbeitung zur Durchführung der angefragten
Vermittlung. Die Telefon-Weitergabe ist die Kernfunktion und wird **direkt am Eingabefeld**
offengelegt (Inline-Texte, §3). Keine Einwilligungs-Checkbox nötig; keine Newsletter-Kopplung.

**Gespeichert:** Vorname (empfohlen), Telefonnummer, E-Mail (Organisator Pflicht / Spieler optional),
Match-Metadaten. **Nicht gespeichert:** IPs (Rate-Limits nur in-memory), keine Accounts, kein Tracking
über das bestehende hinaus.

**Löschkonzept** (ein täglicher APScheduler-Job, Scheduler existiert schon):
1. `ends_at < now` → `status = expired` (verschwindet vom Board).
2. `ends_at < now − 7 Tage` → **Purge personenbezogener Daten**: alle `phone`, `email`, Tokens
   entfernen, Namen auf Initialen kürzen, `purged_at` setzen. (7 Tage Karenz für „der ist nicht
   aufgetaucht"-Klärungen.)
3. `ends_at < now − 60 Tage` → Dokument löschen.

**Betroffenenrechte, self-service:** Spieler-Token = austragen (löscht die eigenen Daten aus dem
Match), Manage-Token = absagen/entfernen. Rest per Mail an `yara@adventure-it.at`.

**Auftragsverarbeiter:** Brevo (bereits für Turnier-Alerts im Einsatz — AVV ist damit schon Thema,
nichts Neues), MongoDB Atlas, Railway, Vercel. **To-do bei Umsetzung:** Abschnitt „Dein Match" auf
der Datenschutz-Seite ergänzen (was, wofür, wie lange, an wen).

---

## 6. Missbrauchsschutz

Maßstab: kleine österreichische Community, kein Login — Schutz ja, Festung nein (ponytail).

- **Rate-Limits** (in-memory, eine Railway-Instanz reicht): max 5 Creates/IP/Tag, max 20 Joins/IP/Stunde. Antwort 429, Text: *„Beeindruckender Eifer. Morgen wieder."*
- **Honeypot**: unsichtbares Feld `website` in Create- und Join-Formular; gefüllt → stilles 200, nichts speichern.
- **Unratbare IDs**: `slug` 8 Zeichen, `manage_token`/`player.token` 32 Zeichen (`secrets.token_urlsafe`). Keine sequentiellen IDs, keine Enumeration (Board liefert nur offene, zukünftige Matches).
- **Anti-Stalking**: Telefonnummern nie öffentlich, nie zwischen Spielern; keine Personensuche; keine spielerübergreifende Liste („alle Matches von X" gibt es nicht); Namensfeld-Placeholder *„Vorname reicht."*
- **Notiz**: 200 Zeichen, reiner Text, keine Linkifizierung (Spam-Links bleiben tot).
- **Moderation**: „Melden"-Mailto auf der Match-Seite (`yara@adventure-it.at`, Betreff mit slug). Organisator kann Störer entfernen. Admin-Eingriffe direkt in MongoDB — **kein Admin-UI bauen**.
- Auto-Expire hält das Board sauber (keine Karteileichen).

---

## 7. Yara-Texte (kanonisch, alle Deutsch)

| Ort | Text |
|---|---|
| Board-Lede | *Vier müsst ihr sein. Den Anfang mache ich. Den Rest jagt ihr selbst.* |
| Create-CTA | **+ Match aufmachen** |
| Board leer | *Keine offenen Matches. Dann mach eben das erste auf.* |
| Zähler | *3 von 4 · einer fehlt noch* / *2 von 4 · zwei fehlen noch* |
| Voll | *Voll. Der Rest kommt zu spät.* |
| Join-CTA | **Ich bin dabei** |
| Join 409 | *Zu langsam. Das Match ist voll.* |
| Doppel-Join | *Du bist schon drin. Einmal reicht.* |
| Level-Hinweis | *Trag dein echtes Level ein, nicht dein Wunschlevel. Die anderen merken es in den ersten fünf Minuten.* |
| Telefon-Hinweis (Join) | *Wird nur an die Organisatorin weitergegeben — nicht öffentlich sichtbar.* |
| Nummern-Reveal | *Nur für dich sichtbar. Nicht für andere Mitspieler.* |
| Austragen-Button | **Doch nicht** |
| Absage-Confirm | *Sicher? Ich sage allen Bescheid. Peinlich wird es trotzdem.* |
| Abgesagt-State | *Abgesagt. Von der Organisatorin, nicht von mir.* |
| Vorbei-State | *Das Match ist vorbei. Ob ihr gewonnen habt, weiß ich nicht — und es ist nicht mein Problem.* |
| 404 | *Dieses Match existiert nicht. Vielleicht hat es nie existiert.* |
| Ungültiger Token | *Der Link ist ungültig. Ich kenne dich nicht.* |
| Rate-Limit | *Beeindruckender Eifer. Morgen wieder.* |
| Share-Nudge (Erfolgs-Screen) | *Link in die Gruppe. Wer ihn ignoriert, spielt nicht.* |
| Seiten-Footer | *Ob ihr gewinnt, ist nicht mein Problem.* |

Regeln wie immer: `.agents/yara-voice.md` — kurz, deklarativ, keine Rufzeichen, gender-bewusst
(Organisator/Organisatorin je nach Kontext neutral halten, im Zweifel „wer organisiert").

---

## 8. Was NICHT gebaut wird (Scope-Grenzen Phase 1)

- ❌ Accounts, Login, Profile, Passwörter — das Feature existiert, *weil* es das nicht braucht.
- ❌ Chat/Messaging zwischen Spielern (Telefonaustausch ersetzt das).
- ❌ Zahlungen, Preis-Splitting-Abwicklung (Preis ist reine Info).
- ❌ Buchungsintegration (Match ≠ Buchung; `court_booked` ist nur ein Flag).
- ❌ Multi-Venue-Vorschläge / „Court fixieren" (§9).
- ❌ Gespeicherte Alerts („sag mir, wenn ein Match für mich auftaucht") (§9).
- ❌ Doodle-artige Terminumfragen (evtl. Phase 2, eigene Entscheidung).
- ❌ WhatsApp-/SMS-Push (E-Mail reicht; WhatsApp Business API = Kosten + Approval).
- ❌ Warteliste bei vollen Matches.
- ❌ Wiederkehrende Matches („jeden Dienstag").
- ❌ Level-Verifikation, Bewertungen, Rankings.
- ❌ Admin-/Moderations-UI (MongoDB direkt).
- ❌ Kalender-Export (.ics), native App, i18n.

Wenn beim Bauen etwas hiervon „nur fünf Minuten" kosten würde: trotzdem nicht bauen. Erst Traktion, dann Ausbau.

## 9. Später (Daten sind vorbereitet, Code nicht)

- **Alerts**: Muster von `tournament_alerts.py` (Brevo, Confirm/Unsubscribe-Tokens) 1:1 auf
  Match-Filter übertragbar. Filter-Shape = `padel_match_filter` aus localStorage.
- **Multi-Venue**: additive Felder `venue_options[]` + `confirmed_venue_id`; Organisator-Aktion
  „Court fixieren", Match erscheint bis dahin unter allen Kandidaten-Venues.
- **2er-Matches** (`spots_total = 2`), „Deine Matches"-Liste aus `padel_match_tokens`.

## 10. Umsetzungs-Checkliste (Konsistenzregeln des Repos)

- [ ] `Backend/routers/matches.py` → in `app.py` registrieren; Dockerfile: `COPY`-Zeile + Import-Check prüfen (Projekt-Regel für neue `.py`-Dateien).
- [ ] Brevo-Helper aus `tournament_alerts.py` wiederverwenden (ggf. in gemeinsames Modul heben — kleinste Lösung wählen).
- [ ] Geocoding + Haversine des Court Finders wiederverwenden, nicht duplizieren.
- [ ] Datenschutz-Seite: Abschnitt „Dein Match" ergänzen.
- [ ] Sitemap/SEO: `/dein-match` in die dynamische Sitemap; Helmet-Meta für Board + Match-Seite (Match-Seiten `noindex` — kurzlebig, personenbezogen).
- [ ] Vor Push: `npm run build` (tsc -b), Preview-Pass; Verified = typecheck + preview.
