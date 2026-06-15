import { Helmet } from "react-helmet-async"

const eUser = "cornelia.mayer"
const eDomain = "adventure-it.at"
const email = `${eUser}@${eDomain}`

export default function ImprintPage() {
  return (
    <>
      <Helmet>
        <title>Impressum — PadelYara</title>
        <meta name="robots" content="noindex, follow" />
      </Helmet>
      <section className="max-w-lg mx-auto py-10 px-1 text-sm text-gray-400 space-y-6">
        <h1 className="text-white text-xl font-semibold">Impressum</h1>

        <div className="space-y-1">
          <p className="text-white font-medium">Cornelia Mayer</p>
          <p>Griesgasse 2</p>
          <p>2340 Mödling</p>
          <p>Österreich</p>
          <p>
            <a href={`mailto:${email}`} className="text-indigo-400 hover:text-indigo-300 transition-colors">
              {email}
            </a>
          </p>
        </div>

        <div className="border-t border-gray-800 pt-4 space-y-2 text-xs leading-relaxed">
          <p>
            Mitglied der WKO, WKO NÖ, Fachgruppe Unternehmensberatung,
            Buchhaltung und Informationstechnik
          </p>
          <p>
            Freies Gewerbe: Dienstleistungen in der automatischen
            Datenverarbeitung und Informationstechnik
          </p>
          <p>Bezirkshauptmannschaft Mödling</p>
          <p>
            Berufsrechtliche Vorschriften:{" "}
            <a
              href="https://www.ris.bka.gv.at/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer=10007517"
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              Gewerbeordnung
            </a>{" "}
            verfügbar unter{" "}
            <a
              href="https://www.ris.bka.gv.at"
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              www.ris.bka.gv.at
            </a>
          </p>
        </div>
      </section>
    </>
  )
}
