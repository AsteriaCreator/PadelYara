export interface QuartierEntry {
  id: string
  name: string
  city: string
  bundesland: string
  address?: string
  type: "hotel" | "reiseveranstalter"
  courtInfo: string
  note?: string
  description: string
  detailParagraphs: string[]
  websiteUrl: string
  bookingUrl?: string
  internalCourtSlug?: string
}

export const PADELQUARTIER_ENTRIES: QuartierEntry[] = [
  {
    id: "hotel-das-zeit-attersee",
    name: "Hotel Das Zeit — Padelzone Attersee",
    city: "Lenzing",
    bundesland: "Oberösterreich",
    address: "Kreuzstraße 30a, 4860 Lenzing",
    type: "hotel",
    courtInfo: "7 Courts — 3 outdoor, 3 indoor Doppel, 1 indoor Single",
    note: "World-Padel-Tour-Belag",
    description: "Die größte Padel-Anlage außerhalb Wiens steht direkt neben dem Hotel. World-Padel-Tour-Belag, Umkleiden, Schlägerverleih, Gastro. Man muss nicht mal das Grundstück verlassen.",
    detailParagraphs: [
      "Padelzone Attersee, betrieben direkt am Gelände von Hotel Das Zeit in Lenzing, ist die größte Padel-Anlage Österreichs außerhalb Wiens: 7 Courts, davon 3 outdoor und 4 indoor (3 Doppel, 1 Single) mit World-Padel-Tour-Belag, ganzjährig nutzbar.",
      "Zur Anlage gehören Umkleiden mit Duschen, Schlägerverleih, ein Chill-out-Bereich und Gastronomie vor Ort. Parkplätze sind kostenlos vorhanden, ebenso eine Bus-Anbindung (Linie 582).",
      "Neben normalen Courtbuchungen bietet die Anlage mehrtägige Padel-Camps (Coaching, Unterkunft, Verpflegung, Sauna, Seezugang) und Corporate-Events mit Turnierformat an.",
      "Buchbar öffentlich über Eversports — kostenfreie Stornierung bis 24h vor Spielbeginn, danach werden 100% der Buchungsgebühr fällig. Preise: €28 wochentags vormittags (07–16 Uhr), €36 abends/am Wochenende.",
    ],
    websiteUrl: "https://hoteldaszeit.com/en/padel/",
    bookingUrl: "https://www.eversports.at/sb/padelzone-attersee-or-padelzeit",
    internalCourtSlug: "padelzone-attersee-padelzeit",
  },
  {
    id: "stanglwirt",
    name: "Stanglwirt",
    city: "Going am Wilden Kaiser",
    bundesland: "Tirol",
    type: "hotel",
    courtInfo: "1 Indoor-Court (Tennishalle)",
    note: "€30 / 30 Min – €45 / 60 Min",
    description: "Indoor-Court in der Tennishalle, am Fuß des Wilden Kaisers. Nicht billig, aber niemand bucht hier wegen des Preises.",
    detailParagraphs: [
      "Der Stanglwirt in Going, am Fuß des Wilden Kaisers im Kitzbüheler Raum, hat seinen Padel-Court in die bestehende Tennishalle integriert — indoor, ganzjährig nutzbar.",
      "Courtmiete: €30 für 30 Minuten, €45 für 60 Minuten. Schlägerverleih €8 pro Stück. Kein Schnäppchen, aber hier geht ohnehin niemand wegen des Preises hin.",
      "Buchung über das hoteleigene System oder telefonisch (+43 5358 2000-7931, tennis@stanglwirt.com).",
    ],
    websiteUrl: "https://www.stanglwirt.com/en/sport/offer/padel-tennis.html",
    bookingUrl: "https://booking.stanglwirt.com/?skd-language-code=en/",
  },
  {
    id: "sporthotel-podersdorf",
    name: "Sporthotel Podersdorf",
    city: "Podersdorf am See",
    bundesland: "Burgenland",
    address: "Steinbruch 1/36, 7141 Podersdorf am See",
    type: "hotel",
    courtInfo: "1 Outdoor-Court",
    note: "Nur telefonische Buchung — kein Onlinesystem",
    description: "Am Neusiedler See, offen für Hotelgäste und alle anderen. Wer online buchen will, hat Pech — hier klingelt noch ein Telefon.",
    detailParagraphs: [
      "Am äußersten Ostrand Österreichs, direkt am Neusiedler See, betreibt das Sporthotel Podersdorf einen Outdoor-Court mit grünem Belag — offen für Hotelgäste genauso wie für alle anderen.",
      "Es gibt kein Online-Buchungssystem. Wer spielen will, ruft an. Das ist keine Lücke im Datenbestand von PadelYara, das ist einfach, wie es hier läuft.",
    ],
    websiteUrl: "https://sporthotel-podersdorf.at",
    internalCourtSlug: "sporthotel-podersdorf",
  },
  {
    id: "schloss-seefels",
    name: "Hotel Schloss Seefels",
    city: "Pörtschach am Wörthersee",
    bundesland: "Kärnten",
    address: "Töschling 1, 9212 Pörtschach am Wörthersee",
    type: "hotel",
    courtInfo: "1 Outdoor-Court",
    note: "Für Hotelgäste inkludiert, je nach Verfügbarkeit",
    description: "Ein Padelcourt im Schlosspark, beschattet von altem Baumbestand, direkt am Wörthersee. Nur für Hotelgäste — wer nicht hier wohnt, kommt nicht rein.",
    detailParagraphs: [
      "Am Eingangsbereich des Schlossparks von Hotel Schloss Seefels in Pörtschach am Wörthersee steht ein Outdoor-Padelcourt, beschattet von altem Baumbestand — direkt neben zwei Tennisplätzen (Sand und Kunstrasen).",
      "Die Nutzung ist für Hotelgäste in der 'Verwöhngarantie' inkludiert, je nach Verfügbarkeit. Ob und wie externe Gäste den Court buchen können, ist auf der Hotelseite nicht angegeben — im Zweifel anrufen.",
    ],
    websiteUrl: "https://www.seefels.at/en/sports-exercise/tennis/",
  },
  {
    id: "padel4fun-camps",
    name: "Padel4Fun Camps & Reisen",
    city: "Wien",
    bundesland: "Wien",
    type: "reiseveranstalter",
    courtInfo: "Padel-Reisen mit Coaching, z. B. Kroatien",
    description: "Wiener Veranstalter, organisiert Trainingscamps im Ausland. Für alle Levels, von Low Starter bis High Advanced.",
    detailParagraphs: [
      "Padel4Fun, ansässig in Wien, organisiert mehrtägige Padel-Trainingscamps im Ausland — 2026 etwa im Aminess Maestral Hotel in Kroatien (30.09.–04.10.2026).",
      "Coaching durch zwei Trainer (Noah und Luca), Unterkunft in Einzel- oder Doppelzimmern, Training für alle Levels von Low Starter bis High Advanced, Kinderermäßigung bis 100%.",
      "Anmeldung über Online-Formular, Anmeldeschluss 15. August 2026. Stornoversicherung optional (7% der Reisekosten) mit gestaffelter Rückerstattung.",
    ],
    websiteUrl: "https://padel4fun.at/camps-reisen/",
  },
  {
    id: "playpadel-camps",
    name: "PlayPadel Camps",
    city: "Wien",
    bundesland: "Wien",
    type: "reiseveranstalter",
    courtInfo: "Padel-Reisen mit Coaching, Umag/Kroatien",
    description: "Wiener Padel-Akademie (SPORTUNION), organisiert Trainingscamps in Kroatien. Drei Leistungsstufen, klare Preise.",
    detailParagraphs: [
      "PlayPadel — eine Wiener Padel-Akademie von Christoph Krenn und David Alten, angesiedelt bei SPORTUNION Wien — organisiert Trainingscamps im Hotel Sipar Plava Laguna in Umag, Kroatien.",
      "2026 im Angebot: Camp 3 (6.–12. September, ausgebucht, nur Warteliste) und Camp 4 (13.–19. September, Doppelzimmer noch verfügbar). Tägliches Training mit Coaching-Team, Matches, Padel- und Pool-Bar-Zugang, Halbpension im 4-Sterne-Hotel, Welcome-Package, Abschlussevent.",
      "Drei Leistungsstufen: Newcomer/Starter (1.0–2.5 APN), Advanced (2.5–4 APN), Expert/Elite (4+ APN). Preise: €1.140 p. P. im Doppelzimmer, €1.340 im Einzelzimmer. Anzahlung 20%, Rest 20 Tage vor Anreise fällig.",
    ],
    websiteUrl: "https://www.playpadel.at/camps",
  },
]
