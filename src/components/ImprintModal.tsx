import { useEffect } from "react"

interface Props {
  onClose: () => void
}

export default function ImprintModal({ onClose }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.7)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-gray-700 p-6 text-sm text-gray-300 space-y-3"
        style={{ backgroundColor: "#111118" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-white font-semibold text-base">Impressum</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-200 transition-colors text-lg leading-none"
            aria-label="Schließen"
          >
            ✕
          </button>
        </div>

        <div className="space-y-1">
          <p className="text-white font-medium">Cornelia Mayer</p>
          <p>Griesgasse 2</p>
          <p>2340 Mödling</p>
          <p>Österreich</p>
          <p>
            <a
              href="mailto:cornelia.mayer@adventure-it.at"
              className="text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              cornelia.mayer@adventure-it.at
            </a>
          </p>
        </div>

        <div className="border-t border-gray-800 pt-3 space-y-2 text-gray-400 text-xs leading-relaxed">
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
            Berufsrechtliche Vorschriften: Gewerbeordnung verfügbar unter{" "}
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
      </div>
    </div>
  )
}
