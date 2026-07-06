export interface QuartierEntry {
  id: string
  name: string
  city: string
  bundesland: string
  type: "hotel" | "reiseveranstalter"
  courtInfo: string
  note?: string
  description: string
  link: string
  isInternal: boolean
}

export const PADELQUARTIER_ENTRIES: QuartierEntry[] = [
  {
    id: "hotel-das-zeit-attersee",
    name: "Hotel Das Zeit — Padelzone Attersee",
    city: "Lenzing",
    bundesland: "Oberösterreich",
    type: "hotel",
    courtInfo: "7 Courts — 3 outdoor, 3 indoor, 1 indoor Single",
    description: "Die größte Padel-Anlage außerhalb Wiens steht direkt neben dem Hotel. World-Padel-Tour-Belag, Umkleiden, Schlägerverleih, Gastro. Man muss nicht mal das Grundstück verlassen.",
    link: "/court/padelzone-attersee-padelzeit",
    isInternal: true,
  },
  {
    id: "stanglwirt",
    name: "Stanglwirt",
    city: "Going, Kitzbühel",
    bundesland: "Tirol",
    type: "hotel",
    courtInfo: "1 Indoor-Court (Tennishalle)",
    note: "€30 / 30 Min – €45 / 60 Min",
    description: "Indoor-Court in der Tennishalle, am Fuß des Wilden Kaisers. Nicht billig, aber niemand bucht hier wegen des Preises.",
    link: "https://booking.stanglwirt.com/?skd-language-code=en/",
    isInternal: false,
  },
  {
    id: "sporthotel-podersdorf",
    name: "Sporthotel Podersdorf",
    city: "Podersdorf am See",
    bundesland: "Burgenland",
    type: "hotel",
    courtInfo: "1 Outdoor-Court",
    note: "Nur telefonische Buchung — kein Onlinesystem",
    description: "Am Neusiedler See, offen für Hotelgäste und alle anderen. Wer online buchen will, hat Pech — hier klingelt noch ein Telefon.",
    link: "/court/sporthotel-podersdorf",
    isInternal: true,
  },
  {
    id: "padel4fun-camps",
    name: "Padel4Fun Camps & Reisen",
    city: "Wien",
    bundesland: "Wien",
    type: "reiseveranstalter",
    courtInfo: "Padel-Reisen mit Coaching, z. B. Kroatien",
    description: "Wiener Veranstalter, organisiert Trainingscamps im Ausland. Für alle Levels, von Low Starter bis High Advanced.",
    link: "https://padel4fun.at/camps-reisen/",
    isInternal: false,
  },
]
