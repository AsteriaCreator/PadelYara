import { Helmet } from "react-helmet-async"

export default function AboutSection() {
  return (
    <section className="mt-2 pb-12">
      <Helmet>
        <title>Über PadelYara — Österreichs Padel Court Aggregator</title>
        <meta name="description" content="PadelYara wurde gebaut, weil das Court-Suchen in Österreich zu viele Tabs braucht. Eine Seite, alle Courts, alle Zeiten." />
        <link rel="canonical" href="https://www.padelyara.at/about" />
      </Helmet>

      {/* Hero image */}
      <div className="rounded-2xl overflow-hidden mb-8 border border-gray-800">
        <img
          src="/yaraoncourt.png"
          alt="Yara – schwarze Katze auf einem Padel-Platz in Österreich, Maskottchen von PadelYara"
          className="w-full object-cover"
          style={{ maxHeight: "520px", objectPosition: "center 30%" }}
        />
      </div>

      {/* Main copy */}
      <div className="mb-10 space-y-5 text-gray-400 text-base leading-relaxed px-1">

        <p className="text-white text-lg font-semibold">Ich bin Yara.</p>

        <p>
          Während du diesen Satz liest, wurde irgendwo ein Court storniert.
        </p>
        <p style={{ color: "#d4f53c" }} className="font-medium">Ich weiß welcher.</p>

        <div className="border-t border-gray-800 my-2" />

        <p>
          Lange habe ich beobachtet, wie meine Menschin einen Padel-Platz gesucht hat.
        </p>
        <p>
          Zu viele Tabs. Zu viele Buchungsseiten. Verzweiflung, sobald das Wetter umschlägt.
        </p>
        <p>Immer dieselbe Frage:</p>
        <p className="text-white italic text-lg px-4 py-3 rounded-lg" style={{ background: "rgba(212,245,60,0.05)" }}>
          "Gibt es heute irgendwo einen freien Court?"
        </p>
        <p>Also habe ich ihr Problem gelöst.</p>
        <p>Ich gehe für sie Courts jagen.</p>

        <div className="border-t border-gray-800 my-2" />

        <p>Dann seh ich: meine Menschin ist kein Einzelfall.</p>
        <p>Es gibt noch mehr von euch.</p>
        <p className="text-white font-bold text-xl tracking-wide">Pathetic.</p>
        <p>Irgendjemand musste die Situation in den Griff bekommen.</p>
        <p className="text-white font-medium">Also gibt es jetzt PadelYara.</p>

        <div className="border-t border-gray-800 my-2" />

        <div className="space-y-1">
          <p>Weniger Tabs.</p>
          <p>Weniger Suchen.</p>
          <p style={{ color: "#d4f53c" }} className="font-semibold">Mehr Padel.</p>
        </div>

        <div className="border-t border-gray-800 my-2" />

        <p>Einen Court finden ist das eine.</p>
        <p className="text-gray-400">Dort auch zu gewinnen, ist jetzt euer Problem.</p>

        <p className="text-gray-400 pt-2">— Yara</p>

        <div className="border-t border-gray-800 my-2" />

        <p className="text-gray-400 italic leading-relaxed">
          Yara bin ich übrigens wirklich. Cornelia Mayer ist meine Menschin. Sie spielt leidenschaftlich gerne Padel, schreibt den Code — und ich beaufsichtige beides.
        </p>
      </div>

      {/* Divider */}
      <div className="border-t border-gray-800 mb-10" />

      {/* Roadmap */}
      <div className="mb-10">
        <p className="text-xs text-gray-500 mb-4 tracking-widest uppercase">Was Yara noch plant</p>
        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          {[
            { phase: "Jetzt", title: "Platz finden", desc: "Alle Padel-Anlagen Österreichs auf einen Blick", live: true },
            { phase: "Bald", title: "Spiel verstehen", desc: "Turnierstatistiken & persönliche Spielanalyse", live: false },
            { phase: "Später", title: "Den Look tragen", desc: "Padel-Merch. Designed in Österreich.", live: false },
          ].map(({ phase, title, desc, live }) => (
            <div
              key={phase}
              className="rounded-xl p-3 sm:p-4 border flex flex-col gap-2"
              style={{
                background: live ? "rgba(212,245,60,0.06)" : "rgba(255,255,255,0.03)",
                borderColor: live ? "rgba(212,245,60,0.25)" : "rgba(255,255,255,0.07)",
              }}
            >
              <span
                className="text-xs font-bold tracking-widest uppercase"
                style={{ color: live ? "#d4f53c" : "#9ca3af" }}
              >
                {phase} {live && "✓"}
              </span>
              <p className="text-white text-sm font-semibold leading-tight">{title}</p>
              <p className="text-gray-500 text-xs leading-snug">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Contact */}
      <div className="text-center">
        <p className="text-gray-500 text-sm mb-3">
          Dir fehlt ein Platz?
        </p>
        <a
          href="mailto:yara@adventure-it.at"
          className="inline-block text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors"
          style={{
            border: "1px solid rgba(212,245,60,0.3)",
            color: "rgba(212,245,60,0.8)",
            fontFamily: "'Barlow Condensed', sans-serif",
            letterSpacing: "0.05em",
          }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = "rgba(212,245,60,0.7)")}
          onMouseLeave={e => (e.currentTarget.style.borderColor = "rgba(212,245,60,0.3)")}
        >
          SCHREIB YARA
        </a>
        <div className="flex items-center justify-center gap-4 mt-4">
          {[
            { href: "https://www.instagram.com/padelyara", label: "Instagram", path: "M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" },
            { href: "https://www.facebook.com/padelyara", label: "Facebook", path: "M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" },
          ].map(({ href, label, path }) => (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={label}
              style={{ color: "rgba(212,245,60,0.5)" }}
              onMouseEnter={e => (e.currentTarget.style.color = "rgba(212,245,60,0.9)")}
              onMouseLeave={e => (e.currentTarget.style.color = "rgba(212,245,60,0.5)")}
            >
              <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                <path d={path} />
              </svg>
            </a>
          ))}
        </div>
      </div>
    </section>
  )
}
