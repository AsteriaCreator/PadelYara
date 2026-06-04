export default function AboutSection() {
  return (
    <section className="mt-2 pb-12">

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
        <p className="text-white italic text-lg pl-4 border-l-2" style={{ borderColor: "rgba(212,245,60,0.4)" }}>
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
      </div>

      {/* Divider */}
      <div className="border-t border-gray-800 mb-10" />

      {/* Roadmap */}
      <div className="mb-10">
        <p className="text-xs text-gray-600 mb-4 tracking-widest uppercase">Was Yara noch plant</p>
        <div className="grid grid-cols-3 gap-3">
          {[
            { phase: "Jetzt", title: "Platz finden", desc: "Alle Padel-Anlagen Österreichs auf einen Blick", live: true },
            { phase: "Bald", title: "Spiel verstehen", desc: "Turnierstatistiken & persönliche Spielanalyse", live: false },
            { phase: "Später", title: "Den Look tragen", desc: "Padel-Merch. Designed in Österreich.", live: false },
          ].map(({ phase, title, desc, live }) => (
            <div
              key={phase}
              className="rounded-xl p-4 border flex flex-col gap-2"
              style={{
                background: live ? "rgba(212,245,60,0.06)" : "rgba(255,255,255,0.03)",
                borderColor: live ? "rgba(212,245,60,0.25)" : "rgba(255,255,255,0.07)",
              }}
            >
              <span
                className="text-xs font-bold tracking-widest uppercase"
                style={{ color: live ? "#d4f53c" : "#4b5563" }}
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
          href="mailto:kontakt@padelyara.at"
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
      </div>
    </section>
  )
}
